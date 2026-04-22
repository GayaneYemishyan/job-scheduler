# tests/test_history.py

import pytest
from datetime import datetime, timedelta
from core.models import Task, Status
from core.history import TaskHistory, HistoryNode


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def make_task(
    task_id: str,
    status: Status = Status.DONE,
    department: str = "Engineering",
    deadline_days: int = 3,
    delay: float = 0.0,
) -> Task:
    """Create a minimal Task and put it in the given terminal status."""
    t = Task(
        task_id=task_id,
        name=f"Task {task_id}",
        priority=5,
        deadline=datetime.now() + timedelta(days=deadline_days),
        department=department,
        estimated_duration=1.0,
    )
    t.mark_ready()
    t.mark_in_progress()

    if status == Status.DONE:
        t.mark_done()
        t.delay = delay          # override computed delay for test control
    elif status == Status.CANCELLED:
        t.mark_cancelled()

    return t


def make_done(task_id: str, **kwargs) -> Task:
    return make_task(task_id, status=Status.DONE, **kwargs)


def make_cancelled(task_id: str, **kwargs) -> Task:
    return make_task(task_id, status=Status.CANCELLED, **kwargs)


def populate(history: TaskHistory, n: int, prefix: str = "T") -> list:
    """Insert n DONE tasks and return them in insertion order."""
    tasks = []
    for i in range(n):
        t = make_done(f"{prefix}{i:03d}")
        history.record(t)
        tasks.append(t)
    return tasks


# ==================================================================
# 1. Initialisation
# ==================================================================

class TestInit:

    def test_empty_history_size_zero(self):
        h = TaskHistory()
        assert h.size == 0

    def test_empty_history_len(self):
        h = TaskHistory()
        assert len(h) == 0

    def test_empty_head_is_none(self):
        h = TaskHistory()
        assert h.head is None

    def test_empty_tail_is_none(self):
        h = TaskHistory()
        assert h.tail is None

    def test_default_max_size(self):
        h = TaskHistory()
        assert h.max_size == 100

    def test_custom_max_size(self):
        h = TaskHistory(max_size=10)
        assert h.max_size == 10

    def test_repr(self):
        h = TaskHistory(max_size=50)
        r = repr(h)
        assert "TaskHistory" in r
        assert "50" in r

    def test_contains_empty_returns_false(self):
        h = TaskHistory()
        assert h.contains("T001") is False

    def test_dunder_contains_empty(self):
        h = TaskHistory()
        assert "T001" not in h


# ==================================================================
# 2. record — insertion at head
# ==================================================================

class TestRecord:

    def test_record_single_task_size_one(self):
        h = TaskHistory()
        h.record(make_done("T001"))
        assert h.size == 1

    def test_record_single_head_equals_tail(self):
        h = TaskHistory()
        t = make_done("T001")
        h.record(t)
        assert h.head.task is t
        assert h.tail.task is t

    def test_record_single_no_neighbours(self):
        h = TaskHistory()
        h.record(make_done("T001"))
        assert h.head.prev is None
        assert h.head.next is None

    def test_record_two_tasks_order(self):
        """Second insertion becomes new head — newest first."""
        h = TaskHistory()
        t1 = make_done("T001")
        t2 = make_done("T002")
        h.record(t1)
        h.record(t2)
        assert h.head.task is t2
        assert h.tail.task is t1

    def test_record_two_tasks_pointers(self):
        h = TaskHistory()
        t1 = make_done("T001")
        t2 = make_done("T002")
        h.record(t1)
        h.record(t2)
        # head.next → tail, tail.prev → head
        assert h.head.next.task is t1
        assert h.tail.prev.task is t2

    def test_record_three_tasks_size(self):
        h = TaskHistory()
        populate(h, 3)
        assert h.size == 3

    def test_record_three_tasks_head_is_latest(self):
        h = TaskHistory()
        tasks = populate(h, 3)
        # last inserted = head
        assert h.head.task is tasks[-1]

    def test_record_three_tasks_tail_is_oldest(self):
        h = TaskHistory()
        tasks = populate(h, 3)
        assert h.tail.task is tasks[0]

    def test_record_cancelled_task(self):
        h = TaskHistory()
        t = make_cancelled("T001")
        h.record(t)
        assert h.size == 1
        assert h.head.task is t

    def test_record_pending_task_raises(self):
        h = TaskHistory()
        t = Task(
            task_id="T001", name="T", priority=5,
            deadline=datetime.now() + timedelta(days=1),
            department="Eng", estimated_duration=1.0,
        )
        # status is PENDING by default
        with pytest.raises(ValueError):
            h.record(t)

    def test_record_in_progress_task_raises(self):
        h = TaskHistory()
        t = Task(
            task_id="T001", name="T", priority=5,
            deadline=datetime.now() + timedelta(days=1),
            department="Eng", estimated_duration=1.0,
        )
        t.mark_ready()
        t.mark_in_progress()
        with pytest.raises(ValueError):
            h.record(t)

    def test_record_duplicate_id_raises(self):
        h = TaskHistory()
        t1 = make_done("T001")
        t2 = make_done("T001")   # same id
        h.record(t1)
        with pytest.raises(ValueError):
            h.record(t2)

    def test_record_registers_in_node_map(self):
        h = TaskHistory()
        t = make_done("T001")
        h.record(t)
        assert "T001" in h._node_map

    def test_record_node_map_returns_correct_node(self):
        h = TaskHistory()
        t = make_done("T001")
        h.record(t)
        assert h._node_map["T001"].task is t


# ==================================================================
# 3. Doubly linked list pointer integrity
# ==================================================================

class TestPointerIntegrity:

    def test_forward_walk_matches_insertion_order(self):
        """Walking head → tail via .next gives newest-first order."""
        h = TaskHistory()
        tasks = populate(h, 5)
        walked = []
        node = h.head
        while node:
            walked.append(node.task)
            node = node.next
        # newest first (last inserted = head)
        assert walked == list(reversed(tasks))

    def test_backward_walk_matches_insertion_order(self):
        """Walking tail → head via .prev gives oldest-first order."""
        h = TaskHistory()
        tasks = populate(h, 5)
        walked = []
        node = h.tail
        while node:
            walked.append(node.task)
            node = node.prev
        assert walked == tasks

    def test_head_prev_is_none(self):
        h = TaskHistory()
        populate(h, 3)
        assert h.head.prev is None

    def test_tail_next_is_none(self):
        h = TaskHistory()
        populate(h, 3)
        assert h.tail.next is None

    def test_every_node_prev_next_consistent(self):
        """For every node n: n.next.prev is n and n.prev.next is n."""
        h = TaskHistory()
        populate(h, 6)
        node = h.head
        while node:
            if node.next:
                assert node.next.prev is node
            if node.prev:
                assert node.prev.next is node
            node = node.next

    def test_single_node_no_dangling_pointers(self):
        h = TaskHistory()
        h.record(make_done("T001"))
        assert h.head.prev is None
        assert h.head.next is None
        assert h.tail.prev is None
        assert h.tail.next is None


# ==================================================================
# 4. contains and get
# ==================================================================

class TestContainsAndGet:

    def test_contains_existing_task(self):
        h = TaskHistory()
        h.record(make_done("T001"))
        assert h.contains("T001") is True

    def test_contains_missing_task(self):
        h = TaskHistory()
        assert h.contains("GHOST") is False

    def test_dunder_contains(self):
        h = TaskHistory()
        h.record(make_done("T001"))
        assert "T001" in h

    def test_get_returns_correct_task(self):
        h = TaskHistory()
        t = make_done("T001")
        h.record(t)
        assert h.get("T001") is t

    def test_get_missing_raises_key_error(self):
        h = TaskHistory()
        with pytest.raises(KeyError):
            h.get("GHOST")

    def test_get_after_multiple_insertions(self):
        h = TaskHistory()
        populate(h, 5)
        t = make_done("TARGET")
        h.record(t)
        assert h.get("TARGET") is t

    def test_get_is_o1_via_node_map(self):
        """Verify O(1) lookup — node_map must have the entry."""
        h = TaskHistory()
        t = make_done("T001")
        h.record(t)
        assert "T001" in h._node_map


# ==================================================================
# 5. remove — O(1) deletion anywhere in the list
# ==================================================================

class TestRemove:

    def test_remove_only_task(self):
        h = TaskHistory()
        h.record(make_done("T001"))
        h.remove("T001")
        assert h.size == 0
        assert h.head is None
        assert h.tail is None

    def test_remove_head(self):
        h = TaskHistory()
        tasks = populate(h, 3)
        # head is tasks[2] (last inserted)
        head_id = h.head.task.task_id
        h.remove(head_id)
        assert h.head.task is not tasks[2]
        assert h.size == 2

    def test_remove_tail(self):
        h = TaskHistory()
        tasks = populate(h, 3)
        tail_id = h.tail.task.task_id   # tasks[0]
        h.remove(tail_id)
        assert h.tail.task is tasks[1]
        assert h.size == 2

    def test_remove_middle(self):
        h = TaskHistory()
        tasks = populate(h, 3)
        # insertion order: T000, T001, T002 → head=T002, tail=T000
        mid_id = tasks[1].task_id   # T001 is in the middle
        h.remove(mid_id)
        assert h.size == 2
        assert h.contains(mid_id) is False

    def test_remove_fixes_pointers_head(self):
        """After removing head, new head's prev must be None."""
        h = TaskHistory()
        populate(h, 3)
        h.remove(h.head.task.task_id)
        assert h.head.prev is None

    def test_remove_fixes_pointers_tail(self):
        """After removing tail, new tail's next must be None."""
        h = TaskHistory()
        populate(h, 3)
        h.remove(h.tail.task.task_id)
        assert h.tail.next is None

    def test_remove_fixes_pointers_middle(self):
        """After removing middle node, neighbours point directly to each other."""
        h = TaskHistory()
        tasks = populate(h, 3)
        mid = tasks[1]
        h.remove(mid.task_id)
        # head (tasks[2]) → next → tail (tasks[0])
        assert h.head.next is h.tail
        assert h.tail.prev is h.head

    def test_remove_deletes_from_node_map(self):
        h = TaskHistory()
        h.record(make_done("T001"))
        h.remove("T001")
        assert "T001" not in h._node_map

    def test_remove_returns_task(self):
        h = TaskHistory()
        t = make_done("T001")
        h.record(t)
        returned = h.remove("T001")
        assert returned is t

    def test_remove_missing_raises_key_error(self):
        h = TaskHistory()
        with pytest.raises(KeyError):
            h.remove("GHOST")

    def test_remove_all_tasks_empties_list(self):
        h = TaskHistory()
        ids = [t.task_id for t in populate(h, 5)]
        for tid in ids:
            h.remove(tid)
        assert h.size == 0
        assert h.head is None
        assert h.tail is None

    def test_remove_does_not_corrupt_remaining_pointers(self):
        """Remove several nodes and verify full pointer consistency."""
        h = TaskHistory()
        populate(h, 6)
        # Remove every other node
        all_ids = [n.task.task_id for n in h._iter_nodes()]
        for tid in all_ids[::2]:
            h.remove(tid)
        # Walk forward and backward — must be consistent
        node = h.head
        while node:
            if node.next:
                assert node.next.prev is node
            if node.prev:
                assert node.prev.next is node
            node = node.next


# ==================================================================
# 6. Capacity cap and tail eviction
# ==================================================================

class TestCapAndEviction:

    def test_size_never_exceeds_max(self):
        h = TaskHistory(max_size=5)
        populate(h, 10)
        assert h.size == 5

    def test_oldest_entry_evicted_first(self):
        """When cap is exceeded, the oldest (tail) task is removed."""
        h = TaskHistory(max_size=3)
        t0 = make_done("T000")
        t1 = make_done("T001")
        t2 = make_done("T002")
        t3 = make_done("T003")   # this should evict T000

        h.record(t0)
        h.record(t1)
        h.record(t2)
        h.record(t3)

        assert h.contains("T000") is False   # evicted
        assert h.contains("T001") is True
        assert h.contains("T002") is True
        assert h.contains("T003") is True

    def test_eviction_updates_tail(self):
        h = TaskHistory(max_size=3)
        populate(h, 4)
        # After 4 inserts into cap-3: T000 evicted, tail should be T001
        assert h.tail.task.task_id == "T001"

    def test_eviction_removes_from_node_map(self):
        h = TaskHistory(max_size=2)
        h.record(make_done("T000"))
        h.record(make_done("T001"))
        h.record(make_done("T002"))   # evicts T000
        assert "T000" not in h._node_map

    def test_eviction_does_not_corrupt_pointers(self):
        h = TaskHistory(max_size=3)
        populate(h, 6)
        assert h.head.prev is None
        assert h.tail.next is None

    def test_cap_of_one(self):
        """A history capped at 1 always holds only the latest task."""
        h = TaskHistory(max_size=1)
        for i in range(5):
            h.record(make_done(f"T{i:03d}"))
        assert h.size == 1
        assert h.head.task.task_id == "T004"
        assert h.tail.task.task_id == "T004"

    def test_multiple_evictions_maintain_size(self):
        h = TaskHistory(max_size=5)
        for i in range(20):
            h.record(make_done(f"T{i:03d}"))
        assert h.size == 5

    def test_evicted_tasks_are_most_recent_five(self):
        """After 20 inserts into cap-5, only the last 5 remain."""
        h = TaskHistory(max_size=5)
        for i in range(20):
            h.record(make_done(f"T{i:03d}"))
        remaining = {n.task.task_id for n in h._iter_nodes()}
        expected = {f"T{i:03d}" for i in range(15, 20)}
        assert remaining == expected


# ==================================================================
# 7. most_recent and all_records
# ==================================================================

class TestQueries:

    def test_most_recent_returns_n_items(self):
        h = TaskHistory()
        populate(h, 10)
        result = h.most_recent(5)
        assert len(result) == 5

    def test_most_recent_order_newest_first(self):
        h = TaskHistory()
        tasks = populate(h, 5)
        result = h.most_recent(5)
        # head is tasks[4], tail is tasks[0]
        assert result[0] is tasks[4]
        assert result[-1] is tasks[0]

    def test_most_recent_n_larger_than_size(self):
        """Asking for more than available returns all."""
        h = TaskHistory()
        populate(h, 3)
        result = h.most_recent(100)
        assert len(result) == 3

    def test_most_recent_empty(self):
        h = TaskHistory()
        assert h.most_recent(5) == []

    def test_most_recent_one(self):
        h = TaskHistory()
        t = make_done("T001")
        h.record(t)
        result = h.most_recent(1)
        assert result == [t]

    def test_all_records_returns_all(self):
        h = TaskHistory()
        tasks = populate(h, 5)
        result = h.all_records()
        assert len(result) == 5

    def test_all_records_newest_first(self):
        h = TaskHistory()
        tasks = populate(h, 5)
        result = h.all_records()
        assert result[0] is tasks[4]   # newest
        assert result[-1] is tasks[0]  # oldest

    def test_all_records_empty(self):
        h = TaskHistory()
        assert h.all_records() == []

    def test_all_records_does_not_modify_list(self):
        """Calling all_records twice returns same results."""
        h = TaskHistory()
        populate(h, 4)
        r1 = h.all_records()
        r2 = h.all_records()
        assert [t.task_id for t in r1] == [t.task_id for t in r2]


# ==================================================================
# 8. filter methods
# ==================================================================

class TestFilters:

    def test_filter_by_status_done(self):
        h = TaskHistory()
        done = make_done("T001")
        cancelled = make_cancelled("T002")
        h.record(done)
        h.record(cancelled)
        result = h.filter_by_status(Status.DONE)
        assert len(result) == 1
        assert result[0] is done

    def test_filter_by_status_cancelled(self):
        h = TaskHistory()
        done = make_done("T001")
        cancelled = make_cancelled("T002")
        h.record(done)
        h.record(cancelled)
        result = h.filter_by_status(Status.CANCELLED)
        assert len(result) == 1
        assert result[0] is cancelled

    def test_filter_by_status_empty_result(self):
        h = TaskHistory()
        h.record(make_done("T001"))
        result = h.filter_by_status(Status.CANCELLED)
        assert result == []

    def test_filter_by_department_exact(self):
        h = TaskHistory()
        eng = make_done("T001", department="Engineering")
        hr  = make_done("T002", department="HR")
        h.record(eng)
        h.record(hr)
        result = h.filter_by_department("Engineering")
        assert len(result) == 1
        assert result[0] is eng

    def test_filter_by_department_case_insensitive(self):
        h = TaskHistory()
        h.record(make_done("T001", department="Engineering"))
        result = h.filter_by_department("engineering")
        assert len(result) == 1

    def test_filter_by_department_no_match(self):
        h = TaskHistory()
        h.record(make_done("T001", department="Engineering"))
        result = h.filter_by_department("Finance")
        assert result == []

    def test_filter_delayed_only_late_tasks(self):
        h = TaskHistory()
        on_time = make_done("T001", delay=0.0)
        late    = make_done("T002", delay=3.5)
        h.record(on_time)
        h.record(late)
        result = h.filter_delayed()
        assert len(result) == 1
        assert result[0] is late

    def test_filter_delayed_none_late(self):
        h = TaskHistory()
        h.record(make_done("T001", delay=0.0))
        h.record(make_done("T002", delay=0.0))
        assert h.filter_delayed() == []

    def test_filter_delayed_all_late(self):
        h = TaskHistory()
        for i in range(4):
            h.record(make_done(f"T{i:03d}", delay=float(i + 1)))
        assert len(h.filter_delayed()) == 4

    def test_filter_delayed_ignores_none_delay(self):
        """Tasks whose delay is None (not computed) must not appear."""
        h = TaskHistory()
        t = make_done("T001")
        t.delay = None
        h.record(t)
        assert h.filter_delayed() == []


# ==================================================================
# 9. Statistics — average_delay and completion_rate
# ==================================================================

class TestStatistics:

    def test_average_delay_no_delayed_tasks(self):
        h = TaskHistory()
        h.record(make_done("T001", delay=0.0))
        h.record(make_done("T002", delay=0.0))
        assert h.average_delay() == pytest.approx(0.0)

    def test_average_delay_all_delayed(self):
        h = TaskHistory()
        h.record(make_done("T001", delay=2.0))
        h.record(make_done("T002", delay=4.0))
        assert h.average_delay() == pytest.approx(3.0)

    def test_average_delay_mixed(self):
        h = TaskHistory()
        h.record(make_done("T001", delay=0.0))  # on time
        h.record(make_done("T002", delay=6.0))  # late
        # Only delayed tasks count: average = 6.0
        assert h.average_delay() == pytest.approx(6.0)

    def test_average_delay_empty(self):
        h = TaskHistory()
        assert h.average_delay() == pytest.approx(0.0)

    def test_completion_rate_all_on_time(self):
        h = TaskHistory()
        for i in range(3):
            h.record(make_done(f"T{i:03d}", delay=0.0))
        stats = h.completion_rate()
        assert stats["total"] == 3
        assert stats["on_time"] == 3
        assert stats["late"] == 0
        assert stats["cancelled"] == 0

    def test_completion_rate_mixed(self):
        h = TaskHistory()
        h.record(make_done("T001", delay=0.0))
        h.record(make_done("T002", delay=2.0))
        h.record(make_cancelled("T003"))
        stats = h.completion_rate()
        assert stats["total"] == 3
        assert stats["on_time"] == 1
        assert stats["late"] == 1
        assert stats["cancelled"] == 1

    def test_completion_rate_empty(self):
        h = TaskHistory()
        stats = h.completion_rate()
        assert stats["total"] == 0
        assert stats["on_time"] == 0
        assert stats["late"] == 0
        assert stats["cancelled"] == 0

    def test_completion_rate_all_cancelled(self):
        h = TaskHistory()
        for i in range(4):
            h.record(make_cancelled(f"T{i:03d}"))
        stats = h.completion_rate()
        assert stats["cancelled"] == 4
        assert stats["on_time"] == 0
        assert stats["late"] == 0

    def test_summary_contains_total(self):
        h = TaskHistory()
        for i in range(3):
            h.record(make_done(f"T{i:03d}"))
        summary = h.summary()
        assert "3" in summary

    def test_summary_contains_history_log(self):
        h = TaskHistory()
        h.record(make_done("T001"))
        summary = h.summary()
        assert "History log" in summary

    def test_summary_contains_newest_and_oldest(self):
        h = TaskHistory()
        populate(h, 3)
        summary = h.summary()
        assert "T000" in summary   # oldest
        assert "T002" in summary   # newest

    def test_summary_empty_history_no_crash(self):
        h = TaskHistory()
        summary = h.summary()
        assert "none" in summary.lower()


# ==================================================================
# 10. Edge cases and stress tests
# ==================================================================

class TestEdgeCases:

    def test_len_matches_size(self):
        h = TaskHistory()
        populate(h, 7)
        assert len(h) == h.size == 7

    def test_record_and_remove_repeatedly(self):
        """Insert and remove the same slot many times without corruption."""
        h = TaskHistory()
        for i in range(10):
            t = make_done(f"SLOT{i:03d}")
            h.record(t)
            h.remove(t.task_id)
        assert h.size == 0
        assert h.head is None
        assert h.tail is None

    def test_mixed_done_and_cancelled_all_recorded(self):
        h = TaskHistory()
        for i in range(5):
            if i % 2 == 0:
                h.record(make_done(f"T{i:03d}"))
            else:
                h.record(make_cancelled(f"T{i:03d}"))
        assert h.size == 5

    def test_large_insertion_size_correct(self):
        h = TaskHistory(max_size=200)
        populate(h, 150)
        assert h.size == 150

    def test_large_insertion_cap_respected(self):
        h = TaskHistory(max_size=50)
        populate(h, 200)
        assert h.size == 50

    def test_pointer_integrity_after_cap_eviction(self):
        """Full pointer consistency check after heavy eviction."""
        h = TaskHistory(max_size=10)
        populate(h, 50)
        node = h.head
        while node:
            if node.next:
                assert node.next.prev is node
            if node.prev:
                assert node.prev.next is node
            node = node.next
        assert h.head.prev is None
        assert h.tail.next is None

    def test_node_map_size_matches_list_size(self):
        h = TaskHistory(max_size=10)
        populate(h, 25)
        assert len(h._node_map) == h.size

    def test_filter_on_large_history(self):
        h = TaskHistory(max_size=100)
        for i in range(50):
            dept = "Engineering" if i % 2 == 0 else "HR"
            h.record(make_done(f"T{i:03d}", department=dept))
        eng = h.filter_by_department("Engineering")
        assert len(eng) == 25

    def test_most_recent_after_eviction(self):
        """most_recent must only return tasks still in the list."""
        h = TaskHistory(max_size=5)
        populate(h, 10)
        recent = h.most_recent(10)
        recent_ids = {t.task_id for t in recent}
        all_ids = {n.task.task_id for n in h._iter_nodes()}
        assert recent_ids == all_ids

    def test_history_node_repr(self):
        t = make_done("T001")
        node = HistoryNode(t)
        r = repr(node)
        assert "T001" in r

    def test_remove_then_reinsert_same_id(self):
        """After removing a task, the same ID can be inserted again."""
        h = TaskHistory()
        t1 = make_done("T001")
        h.record(t1)
        h.remove("T001")
        t2 = make_done("T001")
        h.record(t2)
        assert h.size == 1
        assert h.get("T001") is t2