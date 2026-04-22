# api/scheduler.py

from core.models import Task, Status
from core.graph import DAG
from core.history import TaskHistory
from core.heap import HeapMap

# Critical path boost added to tasks on the longest dependency chain.
# This is additive on top of base_priority.
CRITICAL_PATH_BOOST = 3


class Scheduler:
    """
    Orchestrator — connects HeapMap + DAG + TaskHistory.

    Responsibilities:
        - Accept task submissions and wire up dependencies in the DAG
        - Seed the HeapMap with tasks that are immediately ready
        - Extract the next highest-priority task for execution
        - Complete or kill tasks, unlocking dependents as needed
        - Provide the Admin API surface (get_status, update_priority,
          kill_task, list_queue)
        - Record all finished/cancelled tasks in the history log
    """

    def __init__(self, history_max_size: int = 100):
        self.dag = DAG()
        self.heap_map = HeapMap()
        self.history = TaskHistory(max_size=history_max_size)

        # Tracks tasks currently extracted and being worked on.
        # task_id -> Task
        self._in_progress: dict = {}

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit(self, task: Task) -> None:
        """
        Register a new task with the scheduler.

        Steps:
            1. Validate all declared dependencies exist in the DAG
            2. Add task to the DAG
            3. Wire dependency edges (raises ValueError on cycle)
            4. Recompute critical-path boosts across the whole graph
            5. If no unmet dependencies, mark READY and push onto heap

        Raises:
            KeyError   — if a declared dependency has not been submitted yet
            ValueError — if adding this task would create a dependency cycle
            ValueError — if a task with this ID was already submitted
        """
        if task.task_id in self.dag.tasks:
            raise ValueError(
                f"Task '{task.task_id}' has already been submitted."
            )

        for dep_id in task.dependencies:
            if dep_id not in self.dag.tasks:
                raise ValueError(
                    f"Dependency '{dep_id}' not found. "
                    f"Submit '{dep_id}' before '{task.task_id}'."
                )

        self.dag.add_task(task)

        for dep_id in task.dependencies:
            self.dag.add_dependency(dep_id, task.task_id)

        # Recompute boosts from scratch now that the graph has changed.
        self._apply_critical_path_boosts()

        if self.dag.in_degree[task.task_id] == 0:
            task.mark_ready()
            self.heap_map.push(task)

    # ------------------------------------------------------------------
    # Next task
    # ------------------------------------------------------------------

    def next_task(self) -> Task | None:
        """
        Extract and return the highest effective-priority task.
        Marks it IN_PROGRESS and tracks it internally.
        Returns None if the queue is empty.
        """
        if self.heap_map.is_empty():
            return None

        task = self.heap_map.pop()
        task.mark_in_progress()
        self._in_progress[task.task_id] = task
        return task

    # ------------------------------------------------------------------
    # Complete task
    # ------------------------------------------------------------------

    def complete_task(self, task_id: str) -> list:
        """
        Mark a task as done, record it in history, and unlock
        any dependents whose dependencies are now all satisfied.

        Returns the list of newly ready Task objects pushed onto the heap.

        Raises:
            KeyError    — task_id not found anywhere
            ValueError  — task was not IN_PROGRESS (never extracted)
        """
        if task_id not in self._in_progress:
            if task_id in self.dag.tasks:
                raise ValueError(
                    f"Task '{task_id}' is not in progress. "
                    f"Call next_task() first to extract it."
                )
            raise KeyError(f"Task '{task_id}' not found.")

        task = self._in_progress.pop(task_id)

        newly_ready = self.dag.mark_complete(task_id)

        self.history.record(task)

        for ready_task in newly_ready:
            self.heap_map.push(ready_task)

        return newly_ready

    # ------------------------------------------------------------------
    # Kill task
    # ------------------------------------------------------------------

    def kill_task(self, task_id: str) -> Task:
        """
        Cancel a task regardless of its current state.

        Handles three cases:
            1. Task is in the heap (READY)       — remove via HeapMap
            2. Task is in progress (IN_PROGRESS) — pull from _in_progress
            3. Task is pending (PENDING)         — update status in DAG only

        Killed tasks are recorded in history but do NOT unlock dependents.

        Raises:
            KeyError   — task_id not found anywhere
            ValueError — task already done or already cancelled
        """
        if task_id not in self.dag.tasks:
            raise KeyError(f"Task '{task_id}' not found.")

        task = self.dag.tasks[task_id]

        if task.status in (Status.DONE, Status.CANCELLED):
            raise ValueError(
                f"Task '{task_id}' is already {task.status.value} "
                f"and cannot be killed."
            )

        if task.status == Status.READY:
            self.heap_map.cancel_task(task_id)
            task = self.dag.tasks[task_id]

        elif task.status == Status.IN_PROGRESS:
            task = self._in_progress.pop(task_id)
            task.mark_cancelled()

        elif task.status == Status.PENDING:
            task.mark_cancelled()

        self.history.record(task)
        return task

    # ------------------------------------------------------------------
    # Admin API
    # ------------------------------------------------------------------

    def get_status(self, task_id: str) -> Status:
        """
        Return the current Status of any task.

        Raises:
            KeyError — task_id not found
        """
        if task_id in self.dag.tasks:
            return self.dag.tasks[task_id].status

        if self.history.contains(task_id):
            return self.history.get(task_id).status

        raise KeyError(f"Task '{task_id}' not found.")

    def update_priority(self, task_id: str, new_priority: int) -> None:
        """
        Change a task's priority at any point in its lifecycle.

        Updates base_priority so subsequent critical-path recomputations
        start from the new caller-supplied value rather than the old one.

        - READY (in heap)    → HeapMap rebalances immediately, O(log n)
        - PENDING/IN_PROGRESS → model update only; heap rebalance on entry

        Raises:
            KeyError — task_id not found
        """
        if task_id not in self.dag.tasks:
            raise KeyError(f"Task '{task_id}' not found.")

        task = self.dag.tasks[task_id]

        # Keep base_priority in sync so future boost recomputations are
        # anchored to what the caller actually requested.
        task.base_priority = new_priority

        if task.status == Status.READY:
            self.heap_map.update_priority(task_id, new_priority)

        elif task.status in (Status.PENDING, Status.IN_PROGRESS):
            task.priority = new_priority

        else:
            raise ValueError(
                f"Cannot update priority of a {task.status.value} task."
            )

    def list_queue(self) -> list:
        """
        Return all READY tasks sorted by effective priority, highest first.
        Does NOT consume the queue — safe to call at any time.
        O(n log n).
        """
        tasks = list(self.heap_map._heap._data)
        return sorted(
            tasks,
            key=lambda t: t.effective_priority(),
            reverse=True
        )

    def queue_size(self) -> int:
        """Return the number of tasks currently in the ready queue."""
        return self.heap_map.size()

    # ------------------------------------------------------------------
    # Anti-starvation refresh
    # ------------------------------------------------------------------

    def refresh_wait_times(self) -> None:
        """
        Update wait_times for all queued tasks and rebuild the heap so
        long-waiting low-priority tasks bubble up naturally.
        O(n log n).
        """
        self.heap_map.refresh_priorities()

    # ------------------------------------------------------------------
    # Internal: critical path boost — clean-slate recompute
    # ------------------------------------------------------------------

    def _apply_critical_path_boosts(self) -> None:
        """
        Recompute which tasks sit on the critical path and apply a
        CRITICAL_PATH_BOOST on top of each task's base_priority.

        Design: clean-slate on every call
        ---------------------------------
        Every call starts by resetting ALL tasks to their base_priority,
        then adds the boost only to tasks currently on the critical path.

        This is correct across all submission orderings:
          - A task that becomes critical after a later high-duration task
            is added will now receive its boost.
          - A task that was previously critical but is no longer (because
            a new shorter path made the old critical path irrelevant) will
            have its boost correctly revoked.

        The old approach stored a `_boosted_tasks` set and only boosted
        each task once, which meant tasks could be permanently over-boosted
        or permanently under-boosted depending on submission order.

        Complexity: O(V + E) for critical_path() + O(V) for the reset pass
        + O(log n) per READY task whose priority changes in the heap.
        """
        total_edges = sum(len(v) for v in self.dag.successors.values())
        if total_edges == 0:
            # No dependencies — flat task list, critical path is meaningless.
            return

        try:
            critical_task_ids, _ = self.dag.critical_path()
        except ValueError:
            # Cycle detected — will be caught properly by add_dependency.
            return

        critical_set = set(critical_task_ids)

        # Pass 1: reset every task back to base_priority.
        for task in self.dag.all_tasks():
            desired = task.base_priority
            if task.priority != desired:
                task.priority = desired
                if task.status == Status.READY:
                    self.heap_map.update_priority(task.task_id, desired)

        # Pass 2: apply boost to tasks currently on the critical path.
        for task_id in critical_set:
            task = self.dag.tasks[task_id]
            boosted = task.base_priority + CRITICAL_PATH_BOOST
            if task.priority != boosted:
                task.priority = boosted
                if task.status == Status.READY:
                    self.heap_map.update_priority(task_id, boosted)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def status_report(self) -> str:
        pending = [
            t for t in self.dag.all_tasks()
            if t.status == Status.PENDING
        ]
        in_progress = list(self._in_progress.values())

        lines = [
            "=" * 50,
            "  Scheduler status report",
            "=" * 50,
            f"  Ready (in queue) : {self.queue_size()}",
            f"  In progress      : {len(in_progress)}",
            f"  Pending (blocked): {len(pending)}",
            f"  Completed/History: {len(self.history)}",
            "-" * 50,
        ]

        if not self.heap_map.is_empty():
            top = self.heap_map.peek()
            lines.append(
                f"  Next up          : {top.task_id} "
                f"(effective priority {top.effective_priority():.1f})"
            )

        if in_progress:
            lines.append(
                f"  Running          : "
                + ", ".join(t.task_id for t in in_progress)
            )

        lines.append("=" * 50)
        lines.append(self.history.summary())
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"Scheduler("
            f"queued={self.queue_size()}, "
            f"in_progress={len(self._in_progress)}, "
            f"history={len(self.history)})"
        )