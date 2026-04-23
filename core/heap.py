# core/heap.py

from core.models import Task, Status
from datetime import datetime
from core.hash_map import HashMap


class MinHeap:
    def __init__(self):
        self._data = []

    def _parent(self, i):
        return (i - 1) // 2

    def _left(self, i):
        return 2 * i + 1

    def _right(self, i):
        return 2 * i + 2

    def _swap(self, i, j):
        self._data[i].heap_index = j
        self._data[j].heap_index = i
        self._data[i], self._data[j] = self._data[j], self._data[i]

    def _compare(self, i, j):
        return self._data[i].effective_priority() > self._data[j].effective_priority()

    def size(self):
        return len(self._data)

    def is_empty(self):
        return len(self._data) == 0

    def peek(self):
        if self.is_empty():
            raise IndexError("Heap is empty")
        return self._data[0]

    def insert(self, task: Task):
        task.heap_index = len(self._data)
        self._data.append(task)
        self._heapify_up(len(self._data) - 1)

    def extract_max(self):
        if self.is_empty():
            raise IndexError("Heap is empty")
        self._swap(0, len(self._data) - 1)
        top_task = self._data.pop()
        top_task.heap_index = None
        if not self.is_empty():
            self._heapify_down(0)
        return top_task

    def _heapify_up(self, i):
        while i > 0:
            parent = self._parent(i)
            if self._compare(i, parent):
                self._swap(i, parent)
                i = parent
            else:
                break

    def _heapify_down(self, i):
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


class HeapMap:
    def __init__(self):
        self._heap = MinHeap()
        self._map = HashMap()

    def push(self, task: Task) -> None:
        if self._map.has(task.task_id):
            raise ValueError(f"Task '{task.task_id}' already exists")
        self._heap.insert(task)
        self._map.put(task.task_id, task)

    def pop(self) -> Task:
        task = self._heap.extract_max()
        self._map.delete(task.task_id)
        return task

    def peek(self) -> Task:
        return self._heap.peek()

    def update_priority(self, task_id: str, new_priority: int) -> None:
        task = self._map.get(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found")
        old_priority = task.priority
        task.priority = new_priority
        idx = task.heap_index
        if new_priority > old_priority:
            self._heap._heapify_up(idx)
        elif new_priority < old_priority:
            self._heap._heapify_down(idx)

    def get_task(self, task_id: str) -> Task:
        return self._map.get(task_id)

    def cancel_task(self, task_id: str) -> Task:
        task = self._map.get(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found")

        # Direct in-place removal — no magic sentinel needed.
        #
        # Old approach: boost to 999, then pop().
        # Problem: any task with priority > 999 (e.g. after a critical-path
        # boost takes base_priority=997 to 1000) would not float to the root,
        # so pop() would silently remove the wrong task.
        #
        # Correct approach:
        #   1. Swap the target with the last element.
        #   2. Pop the last slot (the target is now safely gone).
        #   3. Rebalance the node that landed at the vacated index — it may
        #      need to go up *or* down depending on its priority relative
        #      to its new neighbours.
        idx = task.heap_index
        last_idx = self._heap.size() - 1

        self._heap._swap(idx, last_idx)        # move target to the tail
        self._heap._data.pop()                 # remove it
        task.heap_index = None
        self._map.delete(task_id)

        if idx < self._heap.size():            # only rebalance if not last
            self._heap._heapify_up(idx)        # handles case: replacement > parent
            self._heap._heapify_down(idx)      # handles case: replacement < child

        task.mark_cancelled()
        return task

    def size(self) -> int:
        return self._heap.size()

    def is_empty(self) -> bool:
        return self._heap.is_empty()

    def refresh_priorities(self) -> None:
        for slot in self._heap._data:
            slot.update_wait_time()
        self._rebuild_heap()

    def _rebuild_heap(self) -> None:
        # Floyd's algorithm: heapify_down every non-leaf, bottom-up.
        n = self._heap.size()
        for i in range(n // 2 - 1, -1, -1):
            self._heap._heapify_down(i)
        # _heapify_down only updates heap_index via _swap when it actually
        # moves a node.  Nodes that were already in a valid position are
        # never swapped, so their heap_index fields stay at whatever value
        # they had before the loop (which may be stale after a shuffle or
        # a manual corruption).  A single O(n) pass after the Floyd loop
        # guarantees every node's heap_index matches its actual position.
        for idx, task in enumerate(self._heap._data):
            task.heap_index = idx

    def __repr__(self):
        return f"HeapMap(size={self.size()}, top={self.peek() if not self.is_empty() else None})"
