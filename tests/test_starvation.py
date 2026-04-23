# tests/test_starvation.py

import pytest
from datetime import datetime, timedelta
from core.models import Task, PriorityLevel, Status
from core.heap import HeapMap


# ─────────────────────────────────────────────
# Helper
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


# ==================================================================
# 1. effective_priority() formula
# ==================================================================

class TestEffectivePriority:

    def test_zero_wait_equals_raw_priority(self):
        t = make_task("t1", priority=7, hours_waiting=0)
        t.wait_time = 0.0
        assert t.effective_priority(starvation_weight=0.1) == pytest.approx(7.0)

    def test_effective_grows_with_wait_time(self):
        t = make_task("t1", priority=5, hours_waiting=0)
        t.wait_time = 20.0
        assert t.effective_priority(0.1) == pytest.approx(7.0)  # 5 + 0.1*20

    def test_weight_scales_boost_correctly(self):
        t = make_task("t1", priority=3, hours_waiting=0)
        t.wait_time = 10.0
        assert t.effective_priority(0.2) == pytest.approx(5.0)  # 3 + 0.2*10
        assert t.effective_priority(0.5) == pytest.approx(8.0)  # 3 + 0.5*10

    def test_high_wait_overtakes_higher_raw_priority(self):
        """
        t1: priority=8, wait=0   → effective=8.0
        t2: priority=2, wait=100 → effective=2 + 0.1*100 = 12.0
        t2 wins despite lower raw priority.
        """
        t1 = make_task("t1", priority=8)
        t2 = make_task("t2", priority=2)
        t1.wait_time = 0.0
        t2.wait_time = 100.0
        assert t2.effective_priority(0.1) > t1.effective_priority(0.1)

    def test_effective_priority_never_below_raw(self):
        """Wait time is always >= 0 so effective can never be less than raw."""
        t = make_task("t1", priority=6)
        t.wait_time = 0.0
        assert t.effective_priority(0.1) >= t.priority

    def test_exact_crossover_point(self):
        """
        t1 priority=9, t2 priority=1, weight=0.1.
        t2 needs wait_time > 80h to overtake t1 (1 + 0.1*80 = 9.0).
        At 79h t1 still leads; at 81h t2 leads.
        """
        t1 = make_task("t1", priority=9)
        t2 = make_task("t2", priority=1)
        t1.wait_time = 0.0

        t2.wait_time = 79.0
        assert t1.effective_priority(0.1) > t2.effective_priority(0.1)

        t2.wait_time = 81.0
        assert t2.effective_priority(0.1) > t1.effective_priority(0.1)


# ==================================================================
# 2. update_wait_time()
# ==================================================================

class TestUpdateWaitTime:

    def test_ready_task_wait_time_increases(self):
        t = make_task("t1", priority=5, hours_waiting=5)
        t.update_wait_time()
        assert t.wait_time > 0.0

    def test_wait_time_reflects_actual_hours(self):
        """Task backdated 10h should report ~10h wait after update."""
        t = make_task("t1", priority=5, hours_waiting=10)
        t.update_wait_time()
        assert t.wait_time == pytest.approx(10.0, abs=0.1)

    def test_pending_task_wait_time_not_updated(self):
        t = make_task("t1", priority=5)
        t.status = Status.PENDING
        t.wait_time = 0.0
        t.update_wait_time()
        assert t.wait_time == 0.0

    def test_in_progress_task_wait_time_not_updated(self):
        t = make_task("t1", priority=5)
        t.status = Status.IN_PROGRESS
        t.wait_time = 0.0
        t.update_wait_time()
        assert t.wait_time == 0.0

    def test_done_task_wait_time_not_updated(self):
        t = make_task("t1", priority=5)
        t.status = Status.DONE
        t.wait_time = 5.0
        t.update_wait_time()
        assert t.wait_time == 5.0   # unchanged

    def test_wait_time_monotonically_increases(self):
        """Calling update_wait_time repeatedly must never decrease wait_time."""
        t = make_task("t1", priority=5, hours_waiting=3)
        t.update_wait_time()
        first = t.wait_time
        t.update_wait_time()
        second = t.wait_time
        assert second >= first


# ==================================================================
# 3. Heap ordering before refresh (raw priority)
# ==================================================================

class TestHeapOrderBeforeRefresh:

    def test_highest_raw_priority_on_top_before_refresh(self):
        hm = HeapMap()
        hm.push(make_task("t_new", priority=9, hours_waiting=0))
        hm.push(make_task("t_old", priority=1, hours_waiting=30))
        hm.push(make_task("t_mid", priority=4, hours_waiting=10))
        # wait_time starts at 0 for all — raw priority dominates
        assert hm.peek().task_id == "t_new"

    def test_extraction_order_before_refresh_is_by_raw_priority(self):
        hm = HeapMap()
        hm.push(make_task("low",  priority=1, hours_waiting=50))
        hm.push(make_task("high", priority=9, hours_waiting=0))
        hm.push(make_task("mid",  priority=5, hours_waiting=20))
        order = [hm.pop().task_id for _ in range(3)]
        assert order == ["high", "mid", "low"]


# ==================================================================
# 4. Starvation prevention after refresh
# ==================================================================

class TestStarvationAfterRefresh:

    def test_starved_low_priority_overtakes_fresh_high_priority(self):
        """
        fresh: priority=9, wait=0   → effective=9.0
        starved: priority=1, wait=100h → effective=1+0.1*100=11.0
        After refresh starved must be on top.
        """
        hm = HeapMap()
        hm.push(make_task("fresh",   priority=9, hours_waiting=0))
        hm.push(make_task("starved", priority=1, hours_waiting=100))
        hm.refresh_priorities()
        assert hm.peek().task_id == "starved"

    def test_three_tasks_correct_order_after_refresh(self):
        """
        t_new:  priority=9, wait=0   → effective=9.0
        t_mid:  priority=4, wait=10  → effective=5.0
        t_old:  priority=1, wait=30  → effective=4.0
        After refresh order must be: t_new, t_mid, t_old.
        """
        hm = HeapMap()
        hm.push(make_task("t_new", priority=9, hours_waiting=0))
        hm.push(make_task("t_old", priority=1, hours_waiting=30))
        hm.push(make_task("t_mid", priority=4, hours_waiting=10))
        hm.refresh_priorities()
        order = [hm.pop().task_id for _ in range(3)]
        assert order == ["t_new", "t_mid", "t_old"]

    def test_extreme_wait_dominates_any_raw_priority(self):
        """
        Starved task priority=1, wait=100h → effective=11.0
        beats any task with raw priority ≤ 10 and no wait time.
        """
        hm = HeapMap()
        for i in range(5):
            hm.push(make_task(f"fresh{i}", priority=10 - i, hours_waiting=0))
        hm.push(make_task("starved", priority=1, hours_waiting=100))
        hm.refresh_priorities()
        assert hm.peek().task_id == "starved"

    def test_no_starvation_when_all_tasks_are_fresh(self):
        """
        All tasks just arrived — raw priority must still determine order.
        """
        hm = HeapMap()
        hm.push(make_task("low",  priority=1, hours_waiting=0))
        hm.push(make_task("high", priority=9, hours_waiting=0))
        hm.push(make_task("mid",  priority=5, hours_waiting=0))
        hm.refresh_priorities()
        assert hm.peek().task_id == "high"

    def test_equal_effective_priority_both_extractable(self):
        """
        Two tasks with identical effective priority — both must come out.
        """
        hm = HeapMap()
        # effective = 5 + 0.1*0 = 5.0 for both
        hm.push(make_task("t1", priority=5, hours_waiting=0))
        hm.push(make_task("t2", priority=5, hours_waiting=0))
        hm.refresh_priorities()
        ids = {hm.pop().task_id, hm.pop().task_id}
        assert ids == {"t1", "t2"}

    def test_refresh_does_not_change_heap_size(self):
        hm = HeapMap()
        for i in range(6):
            hm.push(make_task(f"t{i}", priority=i + 1, hours_waiting=i * 5))
        hm.refresh_priorities()
        assert hm.size() == 6

    def test_multiple_refreshes_converge_stably(self):
        """Calling refresh several times must not corrupt ordering."""
        hm = HeapMap()
        hm.push(make_task("fresh",   priority=9, hours_waiting=0))
        hm.push(make_task("starved", priority=1, hours_waiting=100))
        hm.push(make_task("mid",     priority=5, hours_waiting=20))
        for _ in range(5):
            hm.refresh_priorities()
        # starved (effective=11) must still beat fresh (effective=9)
        assert hm.peek().task_id == "starved"

    def test_just_below_crossover_not_starved(self):
        """
        priority=9 vs priority=1 weight=0.1 crossover at 80h.
        At 79h the high-priority task must still lead.
        """
        hm = HeapMap()
        hm.push(make_task("high", priority=9, hours_waiting=0))
        hm.push(make_task("low",  priority=1, hours_waiting=79))
        hm.refresh_priorities()
        assert hm.peek().task_id == "high"

    def test_just_above_crossover_is_starved(self):
        """At 81h the low-priority task must overtake."""
        hm = HeapMap()
        hm.push(make_task("high", priority=9, hours_waiting=0))
        hm.push(make_task("low",  priority=1, hours_waiting=81))
        hm.refresh_priorities()
        assert hm.peek().task_id == "low"
