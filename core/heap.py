# core/heap.py

import time
from core.models import Task, Status
from datetime import datetime


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