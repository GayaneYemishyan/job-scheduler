# tests/test_heap_extra.py
#
# These tests complement the existing test_heap.py.
# They cover gaps identified in the review:
#   - MinHeap edge cases (single element, heap_index on all operations)
#   - HeapMap edge cases (pop empty, cancel only/top task)
#   - refresh_priorities / _rebuild_heap correctness
#   - heap property invariant after every mutation

import pytest
from datetime import datetime, timedelta
from core.models import Task, PriorityLevel, Status
from core.heap import MinHeap, HeapMap


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_task(task_id, priority, hours_waiting=0):
    t = Task(
        task_id=task_id,
        name=f"Task {task_id}",
        priority=priority,
        deadline=datetime.now() + timedelta(days=7),
        department="Engineering",
        priority_level=PriorityLevel.MEDIUM,
    )
    t.created_at = datetime.now() - timedelta(hours=hours_waiting)
    t.mark_ready()
    return t


def assert_heap_property(heap: MinHeap):
    """
    Walk every parent-child pair and assert the parent's effective_priority
    is >= the child's. Fails with a descriptive message if violated.
    """
    data = heap._data
    for i in range(len(data)):
        left  = 2 * i + 1
        right = 2 * i + 2
        if left < len(data):
            assert data[i].effective_priority() >= data[left].effective_priority(), (
                f"Heap property violated at i={i} (priority {data[i].priority}) "
                f"vs left child i={left} (priority {data[left].priority})"
            )
        if right < len(data):
            assert data[i].effective_priority() >= data[right].effective_priority(), (
                f"Heap property violated at i={i} (priority {data[i].priority}) "
                f"vs right child i={right} (priority {data[right].priority})"
            )


def assert_heap_index_sync(heap: MinHeap):
    """Every task's heap_index must match its actual position in _data."""
    for idx, task in enumerate(heap._data):
        assert task.heap_index == idx, (
            f"heap_index mismatch: '{task.task_id}' stores {task.heap_index} but sits at {idx}"
        )


# ==================================================================
# 1. MinHeap — edge cases
# ==================================================================

class TestMinHeapEdgeCases:

    def test_single_element_extract_leaves_empty(self):
        heap = MinHeap()
        t = make_task("t1", priority=5)
        heap.insert(t)
        result = heap.extract_max()
        assert result.task_id == "t1"
        assert heap.is_empty()

    def test_single_element_heap_index_after_insert(self):
        heap = MinHeap()
        t = make_task("t1", priority=5)
        heap.insert(t)
        assert t.heap_index == 0

    def test_heap_index_cleared_after_extract(self):
        heap = MinHeap()
        t = make_task("t1", priority=5)
        heap.insert(t)
        heap.extract_max()
        assert t.heap_index is None

    def test_heap_property_after_every_insert(self):
        """Heap property must hold after each of 50 random-ish inserts."""
        heap = MinHeap()
        priorities = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9,
                      3, 2, 3, 8, 4, 6, 2, 6, 4, 3, 3, 8, 3, 2, 7,
                      9, 5, 0, 2, 8, 8, 4, 1, 9, 7, 1, 6, 9, 3, 9,
                      8, 8, 7, 5, 1]
        for i, p in enumerate(priorities):
            heap.insert(make_task(f"t{i}", priority=p))
            assert_heap_property(heap)
            assert_heap_index_sync(heap)

    def test_heap_property_after_every_extract(self):
        """Heap property must hold after each extraction."""
        heap = MinHeap()
        for i in range(20):
            heap.insert(make_task(f"t{i}", priority=i % 7))

        while not heap.is_empty():
            heap.extract_max()
            assert_heap_property(heap)
            assert_heap_index_sync(heap)

    def test_insert_descending_order(self):
        """Insert highest first — each insert is already in place."""
        heap = MinHeap()
        for i in range(10, 0, -1):
            heap.insert(make_task(f"t{i}", priority=i))
        assert heap.peek().priority == 10
        assert_heap_property(heap)

    def test_insert_ascending_order(self):
        """Insert lowest first — every insert must bubble to root."""
        heap = MinHeap()
        for i in range(1, 11):
            heap.insert(make_task(f"t{i}", priority=i))
        assert heap.peek().priority == 10
        assert_heap_property(heap)

    def test_extract_all_returns_descending(self):
        """All extractions must come out in non-increasing priority order."""
        heap = MinHeap()
        priorities = [5, 2, 8, 1, 9, 3, 7, 4, 6, 10]
        for i, p in enumerate(priorities):
            heap.insert(make_task(f"t{i}", priority=p))

        extracted = []
        while not heap.is_empty():
            extracted.append(heap.extract_max().priority)

        assert extracted == sorted(priorities, reverse=True)

    def test_peek_does_not_change_size(self):
        heap = MinHeap()
        heap.insert(make_task("t1", priority=5))
        heap.insert(make_task("t2", priority=3))
        heap.peek()
        assert heap.size() == 2

    def test_two_element_heap_correct_root(self):
        heap = MinHeap()
        heap.insert(make_task("low",  priority=1))
        heap.insert(make_task("high", priority=9))
        assert heap.peek().task_id == "high"
        assert_heap_property(heap)

    def test_two_element_extract_both(self):
        heap = MinHeap()
        heap.insert(make_task("low",  priority=1))
        heap.insert(make_task("high", priority=9))
        first  = heap.extract_max()
        second = heap.extract_max()
        assert first.task_id  == "high"
        assert second.task_id == "low"
        assert heap.is_empty()


# ==================================================================
# 2. HeapMap — edge cases
# ==================================================================

class TestHeapMapEdgeCases:

    def test_pop_empty_raises(self):
        hm = HeapMap()
        with pytest.raises(IndexError):
            hm.pop()

    def test_peek_empty_raises(self):
        hm = HeapMap()
        with pytest.raises(IndexError):
            hm.peek()

    def test_get_task_missing_returns_none(self):
        hm = HeapMap()
        assert hm.get_task("ghost") is None

    def test_cancel_only_task_leaves_empty(self):
        hm = HeapMap()
        hm.push(make_task("t1", priority=5))
        hm.cancel_task("t1")
        assert hm.is_empty()
        assert hm.get_task("t1") is None

    def test_cancel_top_priority_task(self):
        """Cancelling the current root must promote the next task correctly."""
        hm = HeapMap()
        hm.push(make_task("top",  priority=10))
        hm.push(make_task("mid",  priority=5))
        hm.push(make_task("low",  priority=1))
        hm.cancel_task("top")
        assert hm.peek().task_id == "mid"
        assert hm.size() == 2
        assert_heap_property(hm._heap)

    def test_cancel_bottom_priority_task(self):
        """Cancelling the lowest task must leave the heap valid."""
        hm = HeapMap()
        hm.push(make_task("top",    priority=10))
        hm.push(make_task("middle", priority=5))
        hm.push(make_task("bottom", priority=1))
        hm.cancel_task("bottom")
        assert hm.peek().task_id == "top"
        assert hm.size() == 2
        assert_heap_property(hm._heap)

    def test_cancel_missing_task_raises(self):
        hm = HeapMap()
        with pytest.raises(KeyError):
            hm.cancel_task("ghost")

    def test_pop_removes_from_map(self):
        hm = HeapMap()
        hm.push(make_task("t1", priority=5))
        task = hm.pop()
        assert hm.get_task("t1") is None
        assert task.task_id == "t1"

    def test_heap_property_after_series_of_updates(self):
        """Run 30 priority updates and assert heap stays valid each time."""
        hm = HeapMap()
        tasks = [make_task(f"t{i}", priority=i + 1) for i in range(10)]
        for t in tasks:
            hm.push(t)

        import random
        random.seed(7)
        for _ in range(30):
            task_id = random.choice([f"t{i}" for i in range(10)])
            new_p   = random.randint(1, 20)
            hm.update_priority(task_id, new_p)
            assert_heap_property(hm._heap)
            assert_heap_index_sync(hm._heap)

    def test_size_consistent_after_mixed_operations(self):
        hm = HeapMap()
        for i in range(10):
            hm.push(make_task(f"t{i}", priority=i + 1))
        hm.pop()
        hm.pop()
        hm.cancel_task("t2")
        assert hm.size() == 7
        assert hm._heap.size() == 7


# ==================================================================
# 3. refresh_priorities / _rebuild_heap
# ==================================================================

class TestRefreshPriorities:

    def test_refresh_on_empty_heap_does_not_crash(self):
        hm = HeapMap()
        hm.refresh_priorities()   # must not raise
        assert hm.is_empty()

    def test_refresh_on_single_task_does_not_crash(self):
        hm = HeapMap()
        hm.push(make_task("t1", priority=5, hours_waiting=10))
        hm.refresh_priorities()
        assert hm.size() == 1
        assert hm.peek().task_id == "t1"

    def test_refresh_updates_wait_times(self):
        """After refresh, wait_time on each READY task must be > 0."""
        hm = HeapMap()
        for i in range(5):
            hm.push(make_task(f"t{i}", priority=i + 1, hours_waiting=i + 1))
        hm.refresh_priorities()
        for task in hm._heap._data:
            assert task.wait_time > 0, f"{task.task_id} wait_time not updated"

    def test_refresh_heap_property_preserved(self):
        """After refresh the heap must still satisfy the max-heap property."""
        hm = HeapMap()
        for i in range(15):
            hm.push(make_task(f"t{i}", priority=i % 5 + 1, hours_waiting=i * 2))
        hm.refresh_priorities()
        assert_heap_property(hm._heap)
        assert_heap_index_sync(hm._heap)

    def test_refresh_reorders_starved_task_to_top(self):
        """
        Classic starvation scenario:
        fresh task priority=9, wait=0   → effective = 9.0
        starved task priority=1, wait=100h → effective = 1 + 0.1*100 = 11.0
        After refresh the starved task must be at the root.
        """
        hm = HeapMap()
        hm.push(make_task("fresh",   priority=9, hours_waiting=0))
        hm.push(make_task("starved", priority=1, hours_waiting=100))
        hm.refresh_priorities()
        assert hm.peek().task_id == "starved"

    def test_refresh_called_twice_stable(self):
        """Calling refresh twice must not corrupt the heap."""
        hm = HeapMap()
        for i in range(8):
            hm.push(make_task(f"t{i}", priority=i + 1, hours_waiting=i * 3))
        hm.refresh_priorities()
        hm.refresh_priorities()
        assert_heap_property(hm._heap)
        assert_heap_index_sync(hm._heap)
        assert hm.size() == 8

    def test_rebuild_heap_correct_root_after_floyd(self):
        """
        Manually corrupt the heap array order, then call _rebuild_heap.
        After rebuild the root must be the task with the highest priority.
        """
        hm = HeapMap()
        tasks = [make_task(f"t{i}", priority=i + 1) for i in range(7)]
        for t in tasks:
            hm.push(t)

        # Manually scramble the internal array (bypassing heap logic)
        import random
        random.seed(42)
        random.shuffle(hm._heap._data)
        # fix heap_index after shuffle
        for idx, t in enumerate(hm._heap._data):
            t.heap_index = idx

        # Now rebuild
        hm._rebuild_heap()

        assert hm.peek().priority == 7       # highest priority task
        assert_heap_property(hm._heap)
        assert_heap_index_sync(hm._heap)


# ==================================================================
# 4. Heap + HashMap sync invariant
# ==================================================================

class TestHeapMapSyncInvariant:
    """
    Every task in the heap must also be in the map, and vice versa.
    These tests probe that invariant under various operation sequences.
    """

    def _check_sync(self, hm: HeapMap):
        heap_ids = {t.task_id for t in hm._heap._data}
        map_ids  = set()
        for slot in hm._map._buckets:
            if slot is not None and slot is not hm._map._TOMBSTONE:
                map_ids.add(slot[0])
        assert heap_ids == map_ids, (
            f"Heap/Map out of sync.\n  heap={heap_ids}\n  map={map_ids}"
        )

    def test_sync_after_pushes(self):
        hm = HeapMap()
        for i in range(10):
            hm.push(make_task(f"t{i}", priority=i + 1))
        self._check_sync(hm)

    def test_sync_after_pops(self):
        hm = HeapMap()
        for i in range(10):
            hm.push(make_task(f"t{i}", priority=i + 1))
        for _ in range(5):
            hm.pop()
        self._check_sync(hm)

    def test_sync_after_cancels(self):
        hm = HeapMap()
        for i in range(6):
            hm.push(make_task(f"t{i}", priority=i + 1))
        hm.cancel_task("t0")
        hm.cancel_task("t3")
        self._check_sync(hm)

    def test_sync_after_priority_updates(self):
        hm = HeapMap()
        for i in range(8):
            hm.push(make_task(f"t{i}", priority=i + 1))
        hm.update_priority("t0", 99)
        hm.update_priority("t7", 1)
        hm.update_priority("t3", 50)
        self._check_sync(hm)

    def test_sync_after_refresh(self):
        hm = HeapMap()
        for i in range(8):
            hm.push(make_task(f"t{i}", priority=i + 1, hours_waiting=i * 5))
        hm.refresh_priorities()
        self._check_sync(hm)

    def test_sync_after_mixed_operations(self):
        hm = HeapMap()
        for i in range(12):
            hm.push(make_task(f"t{i}", priority=i + 1))
        hm.pop()
        hm.cancel_task("t5")
        hm.update_priority("t2", 20)
        hm.pop()
        hm.refresh_priorities()
        self._check_sync(hm)
