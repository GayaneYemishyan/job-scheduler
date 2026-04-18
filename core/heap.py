# core/heap.py

import time
from core.models import Task, Status
from datetime import datetime

from core.hash_map import HashMap


class MinHeap:
    def __init__(self):
        self._data = []  # list of Task objects

    # ── helpers ──────────────────────────────────────────────

    def _parent(self, i):
        return (i - 1) // 2

    def _left(self, i):
        return 2 * i + 1

    def _right(self, i):
        return 2 * i + 2

    def _swap(self, i, j):
        # swap positions AND update each task's heap_index
        self._data[i].heap_index = j
        self._data[j].heap_index = i
        self._data[i], self._data[j] = self._data[j], self._data[i]

    def _compare(self, i, j):
        """
        Returns True if task at i should be above task at j.
        Uses effective_priority() so anti-starvation is baked in.
        Higher effective_priority = closer to root.
        """
        return self._data[i].effective_priority() > self._data[j].effective_priority()

    def size(self):
        return len(self._data)

    def is_empty(self):
        return len(self._data) == 0

    def peek(self):
        """Return highest-priority task without removing. O(1)."""
        if self.is_empty():
            raise IndexError("Heap is empty")
        return self._data[0]

    # ── core operations ───────────────────────────────────────

    def insert(self, task: Task):
        """Add a task to the heap. O(log n)."""
        task.heap_index = len(self._data)
        self._data.append(task)
        self._heapify_up(len(self._data) - 1)

    def extract_max(self):
        """
        Remove and return the highest effective-priority task. O(log n).
        (We call it extract_max because higher priority number = more urgent)
        """
        if self.is_empty():
            raise IndexError("Heap is empty")

        self._swap(0, len(self._data) - 1)
        top_task = self._data.pop()
        top_task.heap_index = None

        if not self.is_empty():
            self._heapify_down(0)

        return top_task

    # ── heapify ───────────────────────────────────────────────

    def _heapify_up(self, i):
        """Bubble element at i upward until heap property restored."""
        while i > 0:
            parent = self._parent(i)
            if self._compare(i, parent):  # i is more urgent than parent
                self._swap(i, parent)
                i = parent
            else:
                break

    def _heapify_down(self, i):
        """Push element at i downward until heap property restored."""
        n = len(self._data)

        while True:
            largest = i
            left = self._left(i)
            right = self._right(i)

            if left < n and self._compare(left, largest):
                largest = left
            if right < n and self._compare(right, largest):
                largest = right

            if largest != i:
                self._swap(i, largest)
                i = largest
            else:
                break

    def __repr__(self):
        return f"MinHeap([{', '.join(str(t) for t in self._data)}])"
    

    from core.hash_map import HashMap













class HeapMap:
    """
    The Heap-Map hybrid.
    All scheduler interactions go through this class, never directly
    to MinHeap or HashMap separately. This guarantees they stay in sync.
    """

    def __init__(self):
        self._heap = MinHeap()
        self._map = HashMap()

    # ── insert ────────────────────────────────────────────────

    def push(self, task: Task) -> None:
        """Insert a task into both structures. O(log n)."""
        if self._map.has(task.task_id):
            raise ValueError(f"Task '{task.task_id}' already exists")
        self._heap.insert(task)          # heap sets task.heap_index
        self._map.put(task.task_id, task)

    # ── extract ───────────────────────────────────────────────

    def pop(self) -> Task:
        """Remove and return highest-priority task. O(log n)."""
        task = self._heap.extract_max()
        self._map.delete(task.task_id)
        return task

    def peek(self) -> Task:
        """See highest-priority task without removing. O(1)."""
        return self._heap.peek()

    # ── update_priority ───────────────────────────────────────

    def update_priority(self, task_id: str, new_priority: int) -> None:
        """
        Change a task's priority and fix its position in the heap.
        This is the core hard operation. O(log n).

        Steps:
        1. Find the task via HashMap          → O(1)
        2. Read its heap_index                → O(1)
        3. Update its priority value          → O(1)
        4. Rebalance from that index          → O(log n)
        """
        task = self._map.get(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found")

        old_priority = task.priority
        task.priority = new_priority        # mutate in place — heap sees it immediately
                                            # because the heap stores the same object

        idx = task.heap_index

        if new_priority > old_priority:
            # task became MORE urgent → might need to go up
            self._heap._heapify_up(idx)
        elif new_priority < old_priority:
            # task became LESS urgent → might need to go down
            self._heap._heapify_down(idx)
        # if equal, nothing to do

    # ── admin controls ────────────────────────────────────────

    def get_task(self, task_id: str) -> Task:
        """Retrieve any task by ID instantly. O(1)."""
        return self._map.get(task_id)

    def cancel_task(self, task_id: str) -> Task:
        """
        Kill a task mid-queue. O(log n).

        Strategy: boost it to priority 999 (highest possible),
        it bubbles to the root, then extract it cleanly.
        """
        task = self._map.get(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found")

        self.update_priority(task_id, new_priority=999)  # float to root
        removed = self.pop()                              # extract from root
        removed.mark_cancelled()
        return removed

    def size(self) -> int:
        return self._heap.size()

    def is_empty(self) -> bool:
        return self._heap.is_empty()

    def __repr__(self):
        return f"HeapMap(size={self.size()}, top={self.peek() if not self.is_empty() else None})"