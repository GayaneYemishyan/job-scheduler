# tests/test_heap.py

from datetime import datetime, timedelta
from core.models import Task, PriorityLevel, Status
from core.heap import MinHeap, HeapMap
from core.hash_map import HashMap


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

def make_task(task_id, name, priority, hours_waiting=0):
    t = Task(
        task_id=task_id,
        name=name,
        priority=priority,
        deadline=datetime.now() + timedelta(days=7),
        department="Engineering",
        priority_level=PriorityLevel.MEDIUM,
    )
    t.created_at = datetime.now() - timedelta(hours=hours_waiting)
    t.mark_ready()
    return t


# ─────────────────────────────────────────────
# MIN HEAP TESTS
# ─────────────────────────────────────────────

def test_heap_single_insert_extract():
    """Insert one task, extract it, heap should be empty after."""
    heap = MinHeap()
    t = make_task("t1", "Only Task", priority=5)
    heap.insert(t)
    result = heap.extract_max()
    assert result.task_id == "t1"
    assert heap.is_empty(), "Heap should be empty after extracting the only task"
    print(" test_heap_single_insert_extract")


def test_heap_extract_empty():
    """Extracting from empty heap must raise IndexError."""
    heap = MinHeap()
    try:
        heap.extract_max()
        assert False, "Should have raised IndexError"
    except IndexError:
        pass
    print(" test_heap_extract_empty")


def test_heap_peek_empty():
    """Peeking empty heap must raise IndexError."""
    heap = MinHeap()
    try:
        heap.peek()
        assert False, "Should have raised IndexError"
    except IndexError:
        pass
    print(" test_heap_peek_empty")


def test_heap_priority_order():
    """1000 tasks inserted in reverse order must come out highest priority first."""
    heap = MinHeap()
    for i in range(1, 1001):
        heap.insert(make_task(f"t{i}", f"Task {i}", priority=i))

    last_priority = float("inf")
    while not heap.is_empty():
        task = heap.extract_max()
        assert task.priority <= last_priority, (
            f"Order violated: got priority {task.priority} after {last_priority}"
        )
        last_priority = task.priority
    print(" test_heap_priority_order (1000 tasks)")


def test_heap_duplicate_priorities():
    """Duplicate priorities must not crash and all tasks must be extractable."""
    heap = MinHeap()
    for i in range(5):
        heap.insert(make_task(f"t{i}", f"Task {i}", priority=5))  # all same priority

    extracted = []
    while not heap.is_empty():
        extracted.append(heap.extract_max())

    assert len(extracted) == 5, "All 5 tasks should be extracted"
    print(" test_heap_duplicate_priorities")


def test_heap_index_sync():
    """After extractions, remaining tasks must have correct heap_index values."""
    heap = MinHeap()
    tasks = [make_task(f"t{i}", f"Task {i}", priority=i) for i in range(1, 6)]
    for t in tasks:
        heap.insert(t)

    heap.extract_max()  # remove top

    # every remaining task's heap_index must point back to itself in the array
    for idx, task in enumerate(heap._data):
        assert task.heap_index == idx, (
            f"heap_index mismatch: task '{task.task_id}' has heap_index={task.heap_index} but sits at idx={idx}"
        )
    print(" test_heap_index_sync")


# ─────────────────────────────────────────────
# HASH MAP TESTS
# ─────────────────────────────────────────────

def test_hashmap_get_missing_key():
    """Getting a key that was never inserted must return None."""
    hmap = HashMap()
    assert hmap.get("ghost") is None
    print(" test_hashmap_get_missing_key")


def test_hashmap_delete_missing_key():
    """Deleting a key that never existed must return False."""
    hmap = HashMap()
    assert hmap.delete("ghost") is False
    print(" test_hashmap_delete_missing_key")


def test_hashmap_update_existing():
    """Putting a key twice must update the value, not duplicate it."""
    hmap = HashMap()
    hmap.put("t1", "first")
    hmap.put("t1", "second")
    assert hmap.get("t1") == "second"
    assert hmap._size == 1, "Size should still be 1 after update"
    print(" test_hashmap_update_existing")


def test_hashmap_resize_survives():
    """Insert 100 keys — resize must trigger and all keys must survive rehash."""
    hmap = HashMap(capacity=8)  # small capacity forces early resize
    for i in range(100):
        hmap.put(f"key{i}", i * 10)

    for i in range(100):
        val = hmap.get(f"key{i}")
        assert val == i * 10, f"key{i} lost after resize, got {val}"
    print(" test_hashmap_resize_survives (100 keys)")


def test_hashmap_tombstone_chain():
    """
    Delete a middle key — keys inserted after it must still be findable.
    This is the critical tombstone test.
    """
    hmap = HashMap(capacity=8)

    # force all three into the same probe chain by using keys
    # that hash to nearby slots
    hmap.put("a", 1)
    hmap.put("b", 2)
    hmap.put("c", 3)

    hmap.delete("b")  # place tombstone in the middle

    assert hmap.get("a") == 1, "a should still be findable"
    assert hmap.get("b") is None, "b should be gone"
    assert hmap.get("c") == 3, "c must survive past the tombstone"
    print(" test_hashmap_tombstone_chain")


def test_hashmap_has():
    """has() must return True for existing keys and False for missing ones."""
    hmap = HashMap()
    hmap.put("x", 42)
    assert hmap.has("x") is True
    assert hmap.has("y") is False
    print(" test_hashmap_has")


# ─────────────────────────────────────────────
# HEAPMAP TESTS
# ─────────────────────────────────────────────

def test_heapmap_push_duplicate():
    """Pushing a task with an existing ID must raise ValueError."""
    hm = HeapMap()
    t = make_task("t1", "Task", priority=5)
    hm.push(t)
    try:
        hm.push(make_task("t1", "Duplicate", priority=3))
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print(" test_heapmap_push_duplicate")


def test_heapmap_update_missing():
    """update_priority on nonexistent task must raise KeyError."""
    hm = HeapMap()
    try:
        hm.update_priority("ghost", new_priority=9)
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
    print(" test_heapmap_update_missing")


def test_heapmap_update_same_priority():
    """update_priority with same value must not crash and heap stays valid."""
    hm = HeapMap()
    t = make_task("t1", "Task", priority=5)
    hm.push(t)
    hm.update_priority("t1", new_priority=5)  # no change
    assert hm.peek().task_id == "t1"
    print(" test_heapmap_update_same_priority")


def test_heapmap_cancel_removes_from_both():
    """cancel_task must remove task from heap AND from the map."""
    hm = HeapMap()
    hm.push(make_task("t1", "Task A", priority=5))
    hm.push(make_task("t2", "Task B", priority=3))

    cancelled = hm.cancel_task("t2")

    assert cancelled.status == Status.CANCELLED
    assert hm.get_task("t2") is None, "t2 must be gone from the map"
    assert hm.size() == 1, "Only t1 should remain"
    print(" test_heapmap_cancel_removes_from_both")


def test_heapmap_update_bubbles_up():
    """Boosting a low-priority task must bring it to the top."""
    hm = HeapMap()
    hm.push(make_task("t1", "High",   priority=9))
    hm.push(make_task("t2", "Low",    priority=1))
    hm.push(make_task("t3", "Medium", priority=5))

    assert hm.peek().task_id == "t1"       # t1 on top before boost

    hm.update_priority("t2", new_priority=10)
    assert hm.peek().task_id == "t2", "t2 should bubble to top after boost"
    print(" test_heapmap_update_bubbles_up")


def test_heapmap_update_sinks_down():
    """Demoting the top task must sink it and promote the next best."""
    hm = HeapMap()
    hm.push(make_task("t1", "High",   priority=9))
    hm.push(make_task("t2", "Medium", priority=5))
    hm.push(make_task("t3", "Low",    priority=2))

    assert hm.peek().task_id == "t1"

    hm.update_priority("t1", new_priority=1)
    assert hm.peek().task_id == "t2", "t2 should rise after t1 is demoted"
    print(" test_heapmap_update_sinks_down")


def test_starvation_flips_order():
    """A low-priority task waiting long enough must overtake a fresh high-priority task."""
    hm = HeapMap()
    hm.push(make_task("fresh",   "New Job",     priority=9, hours_waiting=0))
    hm.push(make_task("starved", "Old Low Job", priority=1, hours_waiting=100))

    hm.refresh_priorities()

    # starved: 1 + (0.1 × 100) = 11.0 → beats fresh: 9.0
    assert hm.peek().task_id == "starved", (
        f"Starved task should be on top, got {hm.peek().task_id}"
    )
    print(" test_starvation_flips_order")


# ─────────────────────────────────────────────
# RUN ALL
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n── MinHeap ──────────────────────────────")
    test_heap_single_insert_extract()
    test_heap_extract_empty()
    test_heap_peek_empty()
    test_heap_priority_order()
    test_heap_duplicate_priorities()
    test_heap_index_sync()

    print("\n── HashMap ──────────────────────────────")
    test_hashmap_get_missing_key()
    test_hashmap_delete_missing_key()
    test_hashmap_update_existing()
    test_hashmap_resize_survives()
    test_hashmap_tombstone_chain()
    test_hashmap_has()

    print("\n── HeapMap ──────────────────────────────")
    test_heapmap_push_duplicate()
    test_heapmap_update_missing()
    test_heapmap_update_same_priority()
    test_heapmap_cancel_removes_from_both()
    test_heapmap_update_bubbles_up()
    test_heapmap_update_sinks_down()
    test_starvation_flips_order()

    print("\n All tests passed!")