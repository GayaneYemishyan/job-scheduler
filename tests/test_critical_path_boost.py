# tests/test_critical_path_boost.py

import pytest
from datetime import datetime, timedelta
from core.models import Task, Status
from api.scheduler import Scheduler, CRITICAL_PATH_BOOST


def make_task(task_id, priority=5, duration=1.0, deps=None):
    return Task(
        task_id=task_id,
        name=f"Task {task_id}",
        priority=priority,
        deadline=datetime.now() + timedelta(days=7),
        department="Eng",
        estimated_duration=duration,
        dependencies=deps or [],
    )


# ------------------------------------------------------------------
# 1. base_priority is set and never drifts on normal submission
# ------------------------------------------------------------------

def test_base_priority_set_on_construction():
    t = make_task("T1", priority=7)
    assert t.base_priority == 7
    assert t.priority == 7


def test_base_priority_unchanged_after_boost():
    """Boost must not touch base_priority."""
    scheduler = Scheduler()
    t1 = make_task("T1", priority=5, duration=1.0)
    t2 = make_task("T2", priority=5, duration=10.0, deps=["T1"])
    scheduler.submit(t1)
    scheduler.submit(t2)

    # T2 is on the critical path — it should be boosted
    assert t2.priority == t2.base_priority + CRITICAL_PATH_BOOST
    # base_priority must be exactly what the caller passed in
    assert t2.base_priority == 5


# ------------------------------------------------------------------
# 2. update_priority keeps base_priority in sync
# ------------------------------------------------------------------

def test_update_priority_updates_base_priority():
    scheduler = Scheduler()
    t1 = make_task("T1", priority=5, duration=1.0)
    t2 = make_task("T2", priority=5, duration=10.0, deps=["T1"])
    scheduler.submit(t1)
    scheduler.submit(t2)

    scheduler.update_priority("T2", 8)

    assert scheduler.dag.tasks["T2"].base_priority == 8


def test_update_priority_then_boost_anchors_to_new_base():
    """
    After update_priority the next boost recompute must be based on
    the new base, not the old one.
    """
    scheduler = Scheduler()
    t1 = make_task("T1", priority=5, duration=1.0)
    t2 = make_task("T2", priority=5, duration=10.0, deps=["T1"])
    scheduler.submit(t1)
    scheduler.submit(t2)

    scheduler.update_priority("T2", 9)
    # Force a recompute (submitting an unrelated task triggers it)
    scheduler.submit(make_task("T3", priority=1))

    t2_task = scheduler.dag.tasks["T2"]
    assert t2_task.base_priority == 9
    assert t2_task.priority == 9 + CRITICAL_PATH_BOOST


# ------------------------------------------------------------------
# 3. Late-arriving long task makes a previously non-critical task critical
#    (this was broken with the _boosted_tasks guard)
# ------------------------------------------------------------------

def test_late_arrival_makes_previously_noncritical_task_critical():
    """
    Submission order:
      1. T1 (root, dur=1)
      2. T2 (depends on T1, dur=1) — NOT critical yet (same duration as T3)
      3. T3 (depends on T1, dur=1) — NOT critical yet
      4. T4 (depends on T2, dur=10) — NOW T1->T2->T4 is the critical path,
         so T1 and T2 must gain the boost even though they were already
         submitted before T4 existed.

    Old code: T1 and T2 were in _boosted_tasks before T4 arrived, so
              their boost was never reconsidered → wrong priority.
    New code: every submit resets and reapplies → correct.
    """
    scheduler = Scheduler()
    t1 = make_task("T1", priority=5, duration=1.0)
    t2 = make_task("T2", priority=5, duration=1.0, deps=["T1"])
    t3 = make_task("T3", priority=5, duration=1.0, deps=["T1"])
    scheduler.submit(t1)
    scheduler.submit(t2)
    scheduler.submit(t3)

    # Before T4: no single branch is clearly longer; T1's path leads to
    # both T2 and T3, so critical path may or may not include T1/T2 yet.
    # Add T4 with a long duration hanging off T2.
    t4 = make_task("T4", priority=5, duration=10.0, deps=["T2"])
    scheduler.submit(t4)

    # Critical path is now T1 -> T2 -> T4 (total = 12.0)
    # T1, T2, T4 must all have the boost; T3 must not.
    assert scheduler.dag.tasks["T1"].priority == 5 + CRITICAL_PATH_BOOST, \
        "T1 must be boosted after T4 joins the graph"
    assert scheduler.dag.tasks["T2"].priority == 5 + CRITICAL_PATH_BOOST, \
        "T2 must be boosted after T4 joins the graph"
    assert scheduler.dag.tasks["T4"].priority == 5 + CRITICAL_PATH_BOOST, \
        "T4 must be boosted (it's the long tail)"
    assert scheduler.dag.tasks["T3"].priority == 5, \
        "T3 is not on the critical path and must not be boosted"


# ------------------------------------------------------------------
# 4. Boost is revoked when a task is no longer on the critical path
#    (this was also broken with the _boosted_tasks guard)
# ------------------------------------------------------------------

def test_boost_revoked_when_critical_path_shifts():
    """
    Submission order:
      1. T1 (root, dur=1)
      2. T2 (depends on T1, dur=10) — critical path is T1->T2

    After these two submissions T1 and T2 are both boosted.

      3. T3 (depends on T1, dur=20) — critical path is NOW T1->T3

    T2 should lose its boost; T3 should gain it.
    T1 remains on the critical path (it's still the root of the longest chain).

    Old code: T2 was in _boosted_tasks and kept its boost forever.
    New code: reset pass strips T2's boost, apply pass skips T2.
    """
    scheduler = Scheduler()
    t1 = make_task("T1", priority=5, duration=1.0)
    t2 = make_task("T2", priority=5, duration=10.0, deps=["T1"])
    scheduler.submit(t1)
    scheduler.submit(t2)

    # Sanity: T1 and T2 are on critical path here.
    assert scheduler.dag.tasks["T2"].priority == 5 + CRITICAL_PATH_BOOST

    # Now submit T3 with a longer duration — critical path shifts to T1->T3.
    t3 = make_task("T3", priority=5, duration=20.0, deps=["T1"])
    scheduler.submit(t3)

    assert scheduler.dag.tasks["T3"].priority == 5 + CRITICAL_PATH_BOOST, \
        "T3 must be boosted as the new critical-path tail"
    assert scheduler.dag.tasks["T2"].priority == 5, \
        "T2 must lose its boost now that T3 is the longer branch"
    assert scheduler.dag.tasks["T1"].priority == 5 + CRITICAL_PATH_BOOST, \
        "T1 remains on the critical path as the shared root"


# ------------------------------------------------------------------
# 5. No boost applied when there are no dependency edges
# ------------------------------------------------------------------

def test_no_boost_for_independent_tasks():
    """Flat task list — no edges, so boosts must not be applied."""
    scheduler = Scheduler()
    for i in range(5):
        scheduler.submit(make_task(f"T{i}", priority=5))
    for i in range(5):
        t = scheduler.dag.tasks[f"T{i}"]
        assert t.priority == t.base_priority == 5


# ------------------------------------------------------------------
# 6. boost does not accumulate across multiple recomputes
# ------------------------------------------------------------------

def test_boost_does_not_accumulate():
    """
    Submitting many tasks must not stack multiple boosts on the same task.
    After N submissions the critical-path tasks must have exactly
    base_priority + CRITICAL_PATH_BOOST, not base + N * CRITICAL_PATH_BOOST.
    """
    scheduler = Scheduler()
    t1 = make_task("T1", priority=5, duration=1.0)
    t2 = make_task("T2", priority=5, duration=10.0, deps=["T1"])
    scheduler.submit(t1)
    scheduler.submit(t2)

    # Submit several more tasks hanging off other roots — each triggers
    # a full recompute, but T2's boost must stay at exactly one BOOST.
    for i in range(3, 8):
        scheduler.submit(make_task(f"T{i}", priority=3, duration=0.5))

    t2_task = scheduler.dag.tasks["T2"]
    assert t2_task.priority == t2_task.base_priority + CRITICAL_PATH_BOOST


# ------------------------------------------------------------------
# 7. Integration: critical-path task extracted before non-critical peer
# ------------------------------------------------------------------

def test_critical_path_task_extracted_before_noncritical():
    """
    After T1 completes, T2 (critical, long) and T3 (non-critical, short)
    both unlock.  T2 must come out of the heap first because it has the boost.
    """
    scheduler = Scheduler()
    t1 = make_task("T1", priority=5, duration=1.0)
    t2 = make_task("T2", priority=5, duration=10.0, deps=["T1"])
    t3 = make_task("T3", priority=5, duration=1.0,  deps=["T1"])
    scheduler.submit(t1)
    scheduler.submit(t2)
    scheduler.submit(t3)

    first = scheduler.next_task()
    assert first.task_id == "T1"
    scheduler.complete_task("T1")

    second = scheduler.next_task()
    assert second.task_id == "T2", \
        f"Expected T2 (critical, boosted) but got {second.task_id}"


if __name__ == "__main__":
    test_base_priority_set_on_construction()
    test_base_priority_unchanged_after_boost()
    test_update_priority_updates_base_priority()
    test_update_priority_then_boost_anchors_to_new_base()
    test_late_arrival_makes_previously_noncritical_task_critical()
    test_boost_revoked_when_critical_path_shifts()
    test_no_boost_for_independent_tasks()
    test_boost_does_not_accumulate()
    test_critical_path_task_extracted_before_noncritical()
    print("\nAll critical-path boost tests passed!")