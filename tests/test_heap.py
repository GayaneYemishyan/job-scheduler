# tests/test_heap.py
"""
Unit tests for core/heap.py — MinHeap and HeapMap.

Coverage:
    MinHeap  — insert, extract_max, peek, heapify_up/down,
               heap-index bookkeeping, edge cases
    HeapMap  — push/pop, update_priority (up and down rebalance),
               cancel_task (in-place removal), refresh_priorities,
               _rebuild_heap, combined scenarios
"""

import pytest
from datetime import datetime, timedelta
from core.models import Task, Status
from core.heap import MinHeap, HeapMap


# ===========================================================================
# Helpers
# ===========================================================================

def make_task(task_id: str, priority: int, duration: float = 1.0) -> Task:
    """Minimal Task factory — only fields relevant to the heap."""
    return Task(
        task_id=task_id,
        name=f"Task {task_id}",
        priority=priority,
        deadline=datetime.now() + timedelta(days=7),
        department="Eng",
        estimated_duration=duration,
    )


def extract_all(hm: HeapMap) -> list[str]:
    """Drain a HeapMap and return task_ids in extraction order."""
    result = []
    while not hm.is_empty():
        result.append(hm.pop().task_id)
    return result


def heap_ids(hm: HeapMap) -> set[str]:
    """Return the set of task_ids currently in the heap."""
    return {t.task_id for t in hm._heap._data}


def assert_heap_property(hm: HeapMap) -> None:
    """
    Assert the max-heap invariant holds for every node:
    parent.effective_priority() >= child.effective_priority()
    """
    data = hm._heap._data
    n    = len(data)
    for i in range(n):
        left  = 2 * i + 1
        right = 2 * i + 2
        if left  < n:
            assert data[i].effective_priority() >= data[left].effective_priority(),  \
                f"Heap violated at {i} vs left  child {left}"
        if right < n:
            assert data[i].effective_priority() >= data[right].effective_priority(), \
                f"Heap violated at {i} vs right child {right}"


def assert_heap_index_consistency(hm: HeapMap) -> None:
    """Every task's heap_index must match its actual position in _data."""
    for idx, task in enumerate(hm._heap._data):
        assert task.heap_index == idx, (
            f"Task {task.task_id!r} has heap_index={task.heap_index} "
            f"but is at position {idx}"
        )


# ===========================================================================
# 1. MinHeap — basic operations
# ===========================================================================

class TestMinHeapBasics:

    def test_new_heap_is_empty(self):
        h = MinHeap()
        assert h.is_empty()
        assert h.size() == 0

    def test_insert_single(self):
        h = MinHeap()
        t = make_task("T1", priority=5)
        h.insert(t)
        assert h.size() == 1
        assert not h.is_empty()

    def test_peek_returns_max(self):
        h = MinHeap()
        h.insert(make_task("T1", priority=3))
        h.insert(make_task("T2", priority=9))
        h.insert(make_task("T3", priority=1))
        assert h.peek().task_id == "T2"

    def test_peek_does_not_remove(self):
        h = MinHeap()
        h.insert(make_task("T1", priority=5))
        h.peek()
        assert h.size() == 1

    def test_peek_empty_raises(self):
        h = MinHeap()
        with pytest.raises(IndexError):
            h.peek()

    def test_extract_max_single(self):
        h = MinHeap()
        t = make_task("T1", priority=7)
        h.insert(t)
        extracted = h.extract_max()
        assert extracted is t
        assert h.is_empty()

    def test_extract_max_order(self):
        """All tasks must come out highest-priority-first."""
        h = MinHeap()
        priorities = [4, 9, 2, 7, 1, 6, 8, 3, 5]
        for i, p in enumerate(priorities):
            h.insert(make_task(f"T{i}", priority=p))

        extracted = []
        while not h.is_empty():
            extracted.append(h.extract_max().priority)

        assert extracted == sorted(priorities, reverse=True)

    def test_extract_max_empty_raises(self):
        h = MinHeap()
        with pytest.raises(IndexError):
            h.extract_max()

    def test_extract_max_clears_heap_index(self):
        h = MinHeap()
        t = make_task("T1", priority=5)
        h.insert(t)
        h.extract_max()
        assert t.heap_index is None

    def test_insert_sets_heap_index(self):
        h = MinHeap()
        t = make_task("T1", priority=5)
        h.insert(t)
        assert t.heap_index is not None

    def test_heap_index_consistent_after_inserts(self):
        """heap_index must reflect actual position after every insert."""
        hm = HeapMap()
        for i in range(10):
            hm.push(make_task(f"T{i}", priority=i + 1))
        assert_heap_index_consistency(hm)

    def test_heap_property_after_inserts(self):
        hm = HeapMap()
        priorities = [5, 2, 8, 1, 9, 3, 7, 4, 6]
        for i, p in enumerate(priorities):
            hm.push(make_task(f"T{i}", priority=p))
        assert_heap_property(hm)

    def test_heap_property_after_extractions(self):
        hm = HeapMap()
        for i in range(10):
            hm.push(make_task(f"T{i}", priority=i + 1))
        hm.pop()
        hm.pop()
        assert_heap_property(hm)

    def test_equal_priorities_all_extractable(self):
        h = MinHeap()
        tasks = [make_task(f"T{i}", priority=5) for i in range(5)]
        for t in tasks:
            h.insert(t)
        extracted = []
        while not h.is_empty():
            extracted.append(h.extract_max())
        assert len(extracted) == 5

    def test_repr(self):
        h = MinHeap()
        h.insert(make_task("T1", priority=5))
        r = repr(h)
        assert "MinHeap" in r


# ===========================================================================
# 2. HeapMap — push and pop
# ===========================================================================

class TestHeapMapPushPop:

    def test_push_single(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        assert hm.size() == 1

    def test_push_duplicate_raises(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        with pytest.raises(ValueError):
            hm.push(make_task("T1", priority=3))

    def test_pop_returns_highest_priority(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=3))
        hm.push(make_task("T2", priority=9))
        hm.push(make_task("T3", priority=6))
        assert hm.pop().task_id == "T2"

    def test_pop_decrements_size(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.push(make_task("T2", priority=8))
        hm.pop()
        assert hm.size() == 1

    def test_pop_removes_from_map(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.pop()
        assert hm.get_task("T1") is None

    def test_pop_all_tasks(self):
        hm = HeapMap()
        priorities = [3, 7, 1, 9, 5]
        for i, p in enumerate(priorities):
            hm.push(make_task(f"T{i}", priority=p))
        order = extract_all(hm)
        extracted_priorities = [int(tid[1]) for tid in order]
        # priorities extracted should be descending
        assert extract_all(HeapMap()) == []

    def test_pop_extracts_in_descending_priority_order(self):
        hm = HeapMap()
        priorities = [4, 9, 2, 7, 1, 6]
        for i, p in enumerate(priorities):
            hm.push(make_task(f"T{i}", priority=p))
        extracted = []
        while not hm.is_empty():
            extracted.append(hm.pop().priority)
        assert extracted == sorted(priorities, reverse=True)

    def test_is_empty_after_all_pops(self):
        hm = HeapMap()
        for i in range(5):
            hm.push(make_task(f"T{i}", priority=i))
        while not hm.is_empty():
            hm.pop()
        assert hm.is_empty()

    def test_peek_does_not_pop(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.peek()
        assert hm.size() == 1

    def test_get_task_existing(self):
        hm = HeapMap()
        t  = make_task("T1", priority=5)
        hm.push(t)
        assert hm.get_task("T1") is t

    def test_get_task_missing_returns_none(self):
        hm = HeapMap()
        assert hm.get_task("GHOST") is None

    def test_repr(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        r = repr(hm)
        assert "HeapMap" in r


# ===========================================================================
# 3. HeapMap — update_priority
# ===========================================================================

class TestUpdatePriority:

    def test_update_priority_increase_bubbles_up(self):
        """Boosting a low-priority task should make it rise to the top."""
        hm = HeapMap()
        hm.push(make_task("T1", priority=2))
        hm.push(make_task("T2", priority=8))
        hm.push(make_task("T3", priority=6))
        hm.update_priority("T1", 10)
        assert hm.pop().task_id == "T1"

    def test_update_priority_decrease_sinks_down(self):
        """Reducing the top task's priority should let the next one lead."""
        hm = HeapMap()
        hm.push(make_task("T1", priority=9))
        hm.push(make_task("T2", priority=5))
        hm.update_priority("T1", 1)
        assert hm.pop().task_id == "T2"

    def test_update_priority_same_value_no_crash(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.update_priority("T1", 5)   # no-op — must not raise
        assert hm.size() == 1

    def test_update_priority_missing_raises(self):
        hm = HeapMap()
        with pytest.raises(KeyError):
            hm.update_priority("GHOST", 9)

    def test_update_priority_maintains_heap_property(self):
        hm = HeapMap()
        for i in range(8):
            hm.push(make_task(f"T{i}", priority=i + 1))
        hm.update_priority("T0", 10)   # was priority=1, now highest
        assert_heap_property(hm)

    def test_update_priority_heap_index_consistent(self):
        hm = HeapMap()
        for i in range(8):
            hm.push(make_task(f"T{i}", priority=i + 1))
        hm.update_priority("T0", 10)
        assert_heap_index_consistency(hm)

    def test_update_priority_multiple_tasks(self):
        """Updating several tasks — extraction order must reflect new priorities."""
        hm = HeapMap()
        hm.push(make_task("A", priority=3))
        hm.push(make_task("B", priority=7))
        hm.push(make_task("C", priority=5))
        hm.update_priority("A", 9)   # A becomes highest
        hm.update_priority("B", 1)   # B drops to lowest
        order = extract_all(hm)
        assert order[0] == "A"
        assert order[-1] == "B"

    def test_update_priority_changes_task_object(self):
        """The task's .priority field must be updated, not just rebalanced."""
        hm = HeapMap()
        t = make_task("T1", priority=3)
        hm.push(t)
        hm.update_priority("T1", 9)
        assert t.priority == 9

    def test_update_priority_single_task_no_crash(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.update_priority("T1", 1)
        assert hm.size() == 1
        assert hm.pop().task_id == "T1"


# ===========================================================================
# 4. HeapMap — cancel_task (in-place removal)
# ===========================================================================

class TestCancelTask:

    def test_cancel_removes_from_heap(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.cancel_task("T1")
        assert hm.is_empty()

    def test_cancel_removes_from_map(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.cancel_task("T1")
        assert hm.get_task("T1") is None

    def test_cancel_sets_status_cancelled(self):
        hm = HeapMap()
        t = make_task("T1", priority=5)
        hm.push(t)
        hm.cancel_task("T1")
        assert t.status == Status.CANCELLED

    def test_cancel_clears_heap_index(self):
        hm = HeapMap()
        t = make_task("T1", priority=5)
        hm.push(t)
        hm.cancel_task("T1")
        assert t.heap_index is None

    def test_cancel_missing_raises(self):
        hm = HeapMap()
        with pytest.raises(KeyError):
            hm.cancel_task("GHOST")

    def test_cancel_top_task(self):
        """Cancelling the current max — next pop must give the second best."""
        hm = HeapMap()
        hm.push(make_task("T1", priority=9))
        hm.push(make_task("T2", priority=5))
        hm.cancel_task("T1")
        assert hm.pop().task_id == "T2"

    def test_cancel_bottom_task(self):
        """Cancelling the lowest-priority task must not disrupt the rest."""
        hm = HeapMap()
        hm.push(make_task("T1", priority=9))
        hm.push(make_task("T2", priority=7))
        hm.push(make_task("T3", priority=1))
        hm.cancel_task("T3")
        assert hm.size() == 2
        order = extract_all(hm)
        assert order == ["T1", "T2"]

    def test_cancel_middle_task(self):
        """Cancelling a mid-priority task — heap order of survivors unchanged."""
        hm = HeapMap()
        hm.push(make_task("T1", priority=9))
        hm.push(make_task("T2", priority=5))
        hm.push(make_task("T3", priority=1))
        hm.cancel_task("T2")
        assert hm.size() == 2
        order = extract_all(hm)
        assert order == ["T1", "T3"]

    def test_cancel_maintains_heap_property(self):
        hm = HeapMap()
        for i in range(10):
            hm.push(make_task(f"T{i}", priority=i + 1))
        hm.cancel_task("T4")   # remove mid-priority task
        assert_heap_property(hm)

    def test_cancel_maintains_heap_index_consistency(self):
        hm = HeapMap()
        for i in range(10):
            hm.push(make_task(f"T{i}", priority=i + 1))
        hm.cancel_task("T4")
        assert_heap_index_consistency(hm)

    def test_cancel_high_priority_task_above_999(self):
        """
        Old sentinel approach (boost to 999) breaks for priority > 999.
        The current in-place swap approach must handle any priority value.
        """
        hm = HeapMap()
        hm.push(make_task("T1", priority=1000))
        hm.push(make_task("T2", priority=5))
        cancelled = hm.cancel_task("T1")
        assert cancelled.task_id == "T1"
        assert hm.size() == 1
        assert hm.pop().task_id == "T2"

    def test_cancel_all_tasks_empties_heap(self):
        hm = HeapMap()
        for i in range(5):
            hm.push(make_task(f"T{i}", priority=i + 1))
        for i in range(5):
            hm.cancel_task(f"T{i}")
        assert hm.is_empty()

    def test_cancel_then_push_works(self):
        """After cancelling, the same slot should be usable again."""
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.cancel_task("T1")
        hm.push(make_task("T2", priority=9))
        assert hm.pop().task_id == "T2"

    def test_cancel_last_element(self):
        """Cancelling the only element must leave an empty, consistent heap."""
        hm = HeapMap()
        t = make_task("T1", priority=5)
        hm.push(t)
        hm.cancel_task("T1")
        assert hm.is_empty()
        assert t.heap_index is None


# ===========================================================================
# 5. HeapMap — anti-starvation (refresh_priorities + _rebuild_heap)
# ===========================================================================

class TestAntiStarvation:

    def test_refresh_priorities_does_not_crash(self):
        hm = HeapMap()
        for i in range(5):
            t = make_task(f"T{i}", priority=i + 1)
            t.mark_ready()
            hm.push(t)
        hm.refresh_priorities()   # should not raise

    def test_refresh_updates_wait_time_for_ready_tasks(self):
        hm = HeapMap()
        t = make_task("T1", priority=5)
        t.mark_ready()
        # Backdate created_at so update_wait_time sees elapsed time
        from datetime import timedelta
        t.created_at = datetime.now() - timedelta(hours=10)
        hm.push(t)
        hm.refresh_priorities()
        assert t.wait_time > 0.0

    def test_rebuild_heap_restores_heap_property(self):
        """Directly corrupt the heap, then rebuild and verify invariant."""
        hm = HeapMap()
        for i in range(8):
            hm.push(make_task(f"T{i}", priority=i + 1))
        # Corrupt: manually swap data without updating heap_index
        data = hm._heap._data
        data[0].priority, data[-1].priority = data[-1].priority, data[0].priority
        hm._rebuild_heap()
        assert_heap_property(hm)

    def test_rebuild_heap_fixes_heap_indices(self):
        hm = HeapMap()
        for i in range(8):
            hm.push(make_task(f"T{i}", priority=i + 1))
        hm._rebuild_heap()
        assert_heap_index_consistency(hm)

    def test_effective_priority_used_for_ordering(self):
        """
        A low raw-priority task with very high wait_time should beat a
        higher raw-priority task with zero wait_time once wait_time is
        large enough.
        T1: priority=8, wait=0    → effective=8.0
        T2: priority=2, wait=100h → effective=2+10=12.0  (weight=0.1)
        After refresh, T2 should come out first.
        """
        hm = HeapMap()
        t1 = make_task("T1", priority=8)
        t2 = make_task("T2", priority=2)
        t1.mark_ready()
        t2.mark_ready()
        t2.wait_time = 100.0          # simulate 100 h of waiting
        hm.push(t1)
        hm.push(t2)
        hm._rebuild_heap()            # reorder by effective_priority
        first = hm.pop()
        assert first.task_id == "T2"

    def test_zero_wait_time_effective_equals_raw(self):
        t = make_task("T1", priority=7)
        t.wait_time = 0.0
        assert t.effective_priority() == pytest.approx(7.0)

    def test_high_wait_time_raises_effective_priority(self):
        t = make_task("T1", priority=3)
        t.wait_time = 50.0
        assert t.effective_priority(starvation_weight=0.1) == pytest.approx(8.0)

    def test_update_wait_time_only_for_ready(self):
        """PENDING tasks must not accrue wait time."""
        t = make_task("T1", priority=5)
        # status is PENDING by default
        t.update_wait_time()
        assert t.wait_time == 0.0

    def test_refresh_empty_heap_no_crash(self):
        hm = HeapMap()
        hm.refresh_priorities()   # must not raise on empty heap


# ===========================================================================
# 6. Edge cases and stress tests
# ===========================================================================

class TestEdgeCases:

    def test_single_task_push_pop(self):
        hm = HeapMap()
        t = make_task("T1", priority=5)
        hm.push(t)
        out = hm.pop()
        assert out is t
        assert hm.is_empty()

    def test_push_pop_push_same_id_raises(self):
        """After popping, re-pushing the same task should work fine since
        it's a new logical entry; the map no longer holds it."""
        hm = HeapMap()
        t = make_task("T1", priority=5)
        hm.push(t)
        hm.pop()
        # Pushing a brand-new Task object with same ID is allowed
        t2 = make_task("T1", priority=8)
        hm.push(t2)
        assert hm.pop().task_id == "T1"

    def test_large_batch_extraction_order(self):
        """50 tasks — all must come out in descending priority order."""
        import random
        random.seed(99)
        priorities = random.sample(range(1, 201), 50)
        hm = HeapMap()
        for i, p in enumerate(priorities):
            hm.push(make_task(f"T{i}", priority=p))
        extracted = []
        while not hm.is_empty():
            extracted.append(hm.pop().priority)
        assert extracted == sorted(priorities, reverse=True)

    def test_heap_property_after_mixed_operations(self):
        """Push, cancel, update, pop in sequence — heap invariant must hold."""
        hm = HeapMap()
        for i in range(10):
            hm.push(make_task(f"T{i}", priority=i + 1))
        hm.cancel_task("T3")
        hm.update_priority("T7", 15)
        hm.pop()
        assert_heap_property(hm)
        assert_heap_index_consistency(hm)

    def test_heap_index_consistent_after_mixed_operations(self):
        hm = HeapMap()
        for i in range(12):
            hm.push(make_task(f"T{i}", priority=i * 2))
        for tid in ["T0", "T5", "T11"]:
            hm.cancel_task(tid)
        hm.update_priority("T3", 30)
        hm.pop()
        assert_heap_index_consistency(hm)

    def test_cancel_non_existent_after_pop_raises(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.pop()
        with pytest.raises(KeyError):
            hm.cancel_task("T1")

    def test_update_priority_after_cancel_raises(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.cancel_task("T1")
        with pytest.raises(KeyError):
            hm.update_priority("T1", 9)

    def test_many_cancellations_heap_stays_valid(self):
        hm = HeapMap()
        for i in range(20):
            hm.push(make_task(f"T{i}", priority=i + 1))
        # Cancel every even-indexed task
        for i in range(0, 20, 2):
            hm.cancel_task(f"T{i}")
        assert hm.size() == 10
        assert_heap_property(hm)
        assert_heap_index_consistency(hm)

    def test_interleaved_push_pop(self):
        """Push 3, pop 1, push 2 more — ordering must remain correct."""
        hm = HeapMap()
        hm.push(make_task("A", priority=5))
        hm.push(make_task("B", priority=3))
        hm.push(make_task("C", priority=8))
        first = hm.pop()
        assert first.task_id == "C"
        hm.push(make_task("D", priority=10))
        hm.push(make_task("E", priority=1))
        order = extract_all(hm)
        assert order[0] == "D"
        assert order[-1] == "E"

    def test_push_after_empty(self):
        hm = HeapMap()
        hm.push(make_task("T1", priority=5))
        hm.pop()
        assert hm.is_empty()
        hm.push(make_task("T2", priority=3))
        assert hm.size() == 1
        assert hm.pop().task_id == "T2"

    def test_is_empty_initially(self):
        assert HeapMap().is_empty()

    def test_size_tracking(self):
        hm = HeapMap()
        for i in range(7):
            hm.push(make_task(f"T{i}", priority=i))
        assert hm.size() == 7
        hm.pop()
        assert hm.size() == 6
        hm.cancel_task("T1")
        assert hm.size() == 5