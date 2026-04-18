# min_heap.py

import time

class MinHeap:
    def __init__(self):
        self._data = []   # the array that stores Job objects

    # ── helpers ──────────────────────────────────────────────

    def _parent(self, i):
        return (i - 1) // 2

    def _left(self, i):
        return 2 * i + 1

    def _right(self, i):
        return 2 * i + 2

    def _swap(self, i, j):
        # swap two jobs in the array AND update their heap_index fields
        self._data[i].heap_index = j
        self._data[j].heap_index = i
        self._data[i], self._data[j] = self._data[j], self._data[i]

    def size(self):
        return len(self._data)

    def is_empty(self):
        return len(self._data) == 0

    def peek(self):
        """Return highest-priority job without removing it. O(1)."""
        if self.is_empty():
            raise IndexError("Heap is empty")
        return self._data[0]

    # ── core operations ───────────────────────────────────────

    def insert(self, job):
        """Add a job to the heap. O(log n)."""
        job.enqueue_time = time.time()   # stamp it so anti-starvation can measure wait time
        job.heap_index = len(self._data) # it goes to the last position first
        self._data.append(job)
        self._heapify_up(len(self._data) - 1)

    def extract_min(self):
        """Remove and return the highest-priority job (lowest priority number). O(log n)."""
        if self.is_empty():
            raise IndexError("Heap is empty")

        # Step 1: swap root with the last element
        self._swap(0, len(self._data) - 1)

        # Step 2: pop the last element (the old root, now at the end)
        min_job = self._data.pop()
        min_job.heap_index = None   # it's out of the heap

        # Step 3: fix the heap downward from the new root
        if not self.is_empty():
            self._heapify_down(0)

        return min_job

    # ── heapify ───────────────────────────────────────────────

    def _heapify_up(self, i):
        """Bubble element at index i upward until heap property is restored."""
        while i > 0:
            parent = self._parent(i)
            if self._data[i].priority < self._data[parent].priority:
                self._swap(i, parent)
                i = parent
            else:
                break   # heap property satisfied, stop

    def _heapify_down(self, i):
        """Push element at index i downward until heap property is restored."""
        n = len(self._data)

        while True:
            smallest = i          # assume current node is smallest
            left  = self._left(i)
            right = self._right(i)

            # check if left child exists and is smaller
            if left < n and self._data[left].priority < self._data[smallest].priority:
                smallest = left

            # check if right child exists and is even smaller
            if right < n and self._data[right].priority < self._data[smallest].priority:
                smallest = right

            # if smallest is not the current node, swap and continue
            if smallest != i:
                self._swap(i, smallest)
                i = smallest
            else:
                break   # heap property satisfied, stop

    def __repr__(self):
        return f"MinHeap({[str(job) for job in self._data]})"