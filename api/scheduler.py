# api/scheduler.py

from core.models import Task, Status
from core.graph import DAG
from core.history import TaskHistory
from core.heap import HeapMap

# Critical path boost added to tasks on the longest dependency chain
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

        # Tracks tasks currently extracted and being worked on
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
            4. Apply critical path boost if task sits on the longest chain
            5. If no unmet dependencies, mark READY and push onto heap

        Raises:
            KeyError   — if a declared dependency has not been submitted yet
            ValueError — if adding this task would create a dependency cycle
            ValueError — if a task with this ID was already submitted
        """
        # Guard: duplicate submission
        if task.task_id in self.dag.tasks:
            raise ValueError(
                f"Task '{task.task_id}' has already been submitted."
            )

        # Guard: all declared dependencies must already exist in the DAG
        for dep_id in task.dependencies:
            if dep_id not in self.dag.tasks:
                raise ValueError(
                    f"Dependency '{dep_id}' not found. "
                    f"Submit '{dep_id}' before '{task.task_id}'."
                )

        # Register in DAG (no edges yet)
        self.dag.add_task(task)

        # Wire dependency edges — raises ValueError on cycle
        for dep_id in task.dependencies:
            self.dag.add_dependency(dep_id, task.task_id)

        # Apply critical path boost across the whole graph
        # (recalculated on every submit so boosts stay accurate)
        self._apply_critical_path_boosts()

        # If this task is immediately ready, push to heap
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

        Returns the list of newly ready Task objects that were
        pushed onto the heap as a result.

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

        # DAG marks done, decrements successors' in_degree,
        # returns list of tasks whose in_degree just hit 0
        newly_ready = self.dag.mark_complete(task_id)

        # Record in history log
        self.history.record(task)

        # Push newly unblocked tasks onto the heap
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

        Killed tasks are recorded in history but do NOT unlock dependents
        (a cancelled task is not a completed one).

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
            # Task is in the heap — use HeapMap's cancel mechanism
            self.heap_map.cancel_task(task_id)
            # cancel_task already calls mark_cancelled() internally
            # but we re-fetch from dag to get the same object
            task = self.dag.tasks[task_id]

        elif task.status == Status.IN_PROGRESS:
            # Task was extracted — remove from in_progress tracker
            task = self._in_progress.pop(task_id)
            task.mark_cancelled()

        elif task.status == Status.PENDING:
            # Task never entered the heap — just update status
            task.mark_cancelled()

        # Record in history
        self.history.record(task)
        return task

    # ------------------------------------------------------------------
    # Admin API
    # ------------------------------------------------------------------

    def get_status(self, task_id: str) -> Status:
        """
        Return the current Status of any task.
        Checks DAG (covers all states) and history (done/cancelled).

        Raises:
            KeyError — task_id not found
        """
        if task_id in self.dag.tasks:
            return self.dag.tasks[task_id].status

        # Also check history for tasks that completed before DAG was queried
        if self.history.contains(task_id):
            return self.history.get(task_id).status

        raise KeyError(f"Task '{task_id}' not found.")

    def update_priority(self, task_id: str, new_priority: int) -> None:
        """
        Change a task's priority at any point in its lifecycle.

        - If READY (in heap): HeapMap rebalances immediately → O(log n)
        - If PENDING (not in heap yet): updates the model only,
          so when it enters the heap it starts with the new priority
        - If IN_PROGRESS: updates model (no heap rebalancing needed)

        Raises:
            KeyError — task_id not found
        """
        if task_id not in self.dag.tasks:
            raise KeyError(f"Task '{task_id}' not found.")

        task = self.dag.tasks[task_id]

        if task.status == Status.READY:
            # Task is in the heap — update and rebalance
            self.heap_map.update_priority(task_id, new_priority)

        elif task.status in (Status.PENDING, Status.IN_PROGRESS):
            # Not in heap — just update the model
            task.priority = new_priority

        else:
            raise ValueError(
                f"Cannot update priority of a {task.status.value} task."
            )

    def list_queue(self) -> list:
        """
        Return all READY tasks sorted by effective priority, highest first.
        Does NOT consume the queue — safe to call at any time.
        Time complexity: O(n log n)
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
        Update wait_times for all queued tasks and rebuild the heap
        so long-waiting low-priority tasks bubble up naturally.

        Call this periodically (e.g. every 60 seconds in a real system).
        O(n log n).
        """
        self.heap_map.refresh_priorities()

    # ------------------------------------------------------------------
    # Internal: critical path boost
    # ------------------------------------------------------------------

    def _apply_critical_path_boosts(self) -> None:
        """
        Recalculate the critical path and give tasks on it a priority boost.

        Only runs if the DAG has at least one dependency edge — no point
        computing the critical path for a flat list of independent tasks.

        The boost is additive and applied once. To avoid double-boosting
        on repeated submissions, we store which tasks were already boosted.
        """
        total_edges = sum(
            len(v) for v in self.dag.successors.values()
        )
        if total_edges == 0:
            return

        try:
            critical_task_ids, _ = self.dag.critical_path()
        except ValueError:
            # Cycle detected — critical path cannot be computed.
            # The cycle will be caught properly by add_dependency.
            return

        if not hasattr(self, "_boosted_tasks"):
            self._boosted_tasks = set()

        for task_id in critical_task_ids:
            if task_id not in self._boosted_tasks:
                task = self.dag.tasks[task_id]
                task.priority += CRITICAL_PATH_BOOST
                self._boosted_tasks.add(task_id)

                # If already in heap, rebalance to reflect new priority
                if task.status == Status.READY:
                    self.heap_map.update_priority(
                        task_id, task.priority
                    )

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def status_report(self) -> str:
        """
        Human-readable overview of the scheduler's current state.
        Useful for the demo and presentation.
        """
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