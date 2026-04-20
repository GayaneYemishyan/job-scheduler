# core/history.py

from datetime import datetime
from core.models import Task, Status


class HistoryNode:
    """A single node in the doubly linked list."""

    def __init__(self, task: Task):
        self.task = task
        self.prev = None   # pointer to the previous node (more recent)
        self.next = None   # pointer to the next node (older)

    def __repr__(self):
        return f"HistoryNode({self.task.task_id})"


class TaskHistory:
    """
    Doubly linked list that maintains a chronological log
    of completed and cancelled tasks.

    Structure:
        head <-> node <-> node <-> ... <-> tail
        (most recent)                  (oldest)

    Key properties:
        - O(1) insertion at the head
        - O(1) deletion from anywhere (given the node reference)
        - O(1) eviction from the tail when cap is exceeded
        - Capped at max_size entries to prevent unbounded memory growth
    """

    def __init__(self, max_size: int = 100):
        self.head = None          # most recently completed task
        self.tail = None          # oldest completed task
        self.max_size = max_size
        self.size = 0
        self._node_map = {}       # task_id -> HistoryNode for O(1) lookup

    # ------------------------------------------------------------------
    # Core insertion
    # ------------------------------------------------------------------

    def record(self, task: Task) -> None:
        """
        Prepend a completed or cancelled task to the head of the list.
        If the list exceeds max_size, evict the oldest entry from the tail.
        Time complexity: O(1)
        """
        if task.status not in (Status.DONE, Status.CANCELLED):
            raise ValueError(
                f"Only DONE or CANCELLED tasks can be recorded. "
                f"Task '{task.task_id}' has status '{task.status.value}'."
            )

        if task.task_id in self._node_map:
            raise ValueError(
                f"Task '{task.task_id}' is already in the history log."
            )

        new_node = HistoryNode(task)

        if self.head is None:
            # List is empty — new node is both head and tail
            self.head = new_node
            self.tail = new_node
        else:
            # Prepend to head
            new_node.next = self.head
            self.head.prev = new_node
            self.head = new_node

        self._node_map[task.task_id] = new_node
        self.size += 1

        # Evict oldest if over capacity
        if self.size > self.max_size:
            self._evict_tail()

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def remove(self, task_id: str) -> Task:
        """
        Remove a specific task from the history log by task_id.
        Uses the node map for O(1) lookup, then O(1) pointer surgery.
        Time complexity: O(1)
        """
        if task_id not in self._node_map:
            raise KeyError(
                f"Task '{task_id}' not found in history log."
            )

        node = self._node_map[task_id]
        self._unlink(node)
        del self._node_map[task_id]
        self.size -= 1
        return node.task

    def _unlink(self, node: HistoryNode) -> None:
        """
        Remove a node from the linked list by rewiring its neighbours.
        Does not update size or node_map — callers handle that.
        Time complexity: O(1)
        """
        prev_node = node.prev
        next_node = node.next

        if prev_node:
            prev_node.next = next_node
        else:
            # node was the head
            self.head = next_node

        if next_node:
            next_node.prev = prev_node
        else:
            # node was the tail
            self.tail = prev_node

        # Clean up the node's own pointers
        node.prev = None
        node.next = None

    def _evict_tail(self) -> Task:
        """
        Remove and return the oldest entry (tail) when capacity is exceeded.
        Time complexity: O(1)
        """
        if self.tail is None:
            return None

        evicted_task = self.tail.task
        del self._node_map[evicted_task.task_id]
        self._unlink(self.tail)
        self.size -= 1
        return evicted_task

    # ------------------------------------------------------------------
    # Lookup and queries
    # ------------------------------------------------------------------

    def get(self, task_id: str) -> Task:
        """
        Fetch a specific completed task by ID.
        Time complexity: O(1) via node map.
        """
        if task_id not in self._node_map:
            raise KeyError(
                f"Task '{task_id}' not found in history log."
            )
        return self._node_map[task_id].task

    def contains(self, task_id: str) -> bool:
        """Check whether a task exists in the history log."""
        return task_id in self._node_map

    def most_recent(self, n: int = 10) -> list:
        """
        Return the n most recently completed tasks, newest first.
        Time complexity: O(n)
        """
        results = []
        current = self.head
        while current and len(results) < n:
            results.append(current.task)
            current = current.next
        return results

    def all_records(self) -> list:
        """
        Return all completed tasks as a list, newest first.
        Time complexity: O(n)
        """
        results = []
        current = self.head
        while current:
            results.append(current.task)
            current = current.next
        return results

    def filter_by_status(self, status: Status) -> list:
        """
        Return all tasks matching a given status (DONE or CANCELLED).
        Time complexity: O(n)
        """
        return [
            node.task
            for node in self._iter_nodes()
            if node.task.status == status
        ]

    def filter_by_department(self, department: str) -> list:
        """
        Return all completed tasks belonging to a specific department.
        Time complexity: O(n)
        """
        return [
            node.task
            for node in self._iter_nodes()
            if node.task.department.lower() == department.lower()
        ]

    def filter_delayed(self) -> list:
        """
        Return all completed tasks that finished past their deadline.
        Time complexity: O(n)
        """
        return [
            node.task
            for node in self._iter_nodes()
            if node.task.delay is not None and node.task.delay > 0
        ]

    def _iter_nodes(self):
        """Internal generator to walk the list from head to tail."""
        current = self.head
        while current:
            yield current
            current = current.next

    # ------------------------------------------------------------------
    # Statistics — useful for the demo and presentation
    # ------------------------------------------------------------------

    def average_delay(self) -> float:
        """
        Average delay in hours across all completed tasks that were late.
        Returns 0.0 if no delayed tasks exist.
        """
        delayed = self.filter_delayed()
        if not delayed:
            return 0.0
        return sum(t.delay for t in delayed) / len(delayed)

    def completion_rate(self) -> dict:
        """
        Returns a breakdown of how many tasks completed on time vs late.
        Useful for the demo to show scheduler performance.
        """
        on_time = 0
        late = 0
        cancelled = 0

        for node in self._iter_nodes():
            task = node.task
            if task.status == Status.CANCELLED:
                cancelled += 1
            elif task.delay == 0.0:
                on_time += 1
            else:
                late += 1

        return {
            "total": self.size,
            "on_time": on_time,
            "late": late,
            "cancelled": cancelled,
        }

    def summary(self) -> str:
        """
        Human-readable summary of the history log.
        Called by the Admin API's status report.
        """
        stats = self.completion_rate()
        avg = self.average_delay()
        return (
            f"History log — {stats['total']}/{self.max_size} entries\n"
            f"  On time  : {stats['on_time']}\n"
            f"  Late     : {stats['late']} (avg delay: {avg:.2f}h)\n"
            f"  Cancelled: {stats['cancelled']}\n"
            f"  Oldest   : {self.tail.task.task_id if self.tail else 'none'}\n"
            f"  Newest   : {self.head.task.task_id if self.head else 'none'}"
        )

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return self.size

    def __contains__(self, task_id: str) -> bool:
        return self.contains(task_id)

    def __repr__(self) -> str:
        return f"TaskHistory(size={self.size}, max={self.max_size})"