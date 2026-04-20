# tests/test_scheduler.py

import pytest
from datetime import datetime, timedelta
from core.models import Task, Status, PriorityLevel
from core.graph import DAG
from core.history import TaskHistory


# ------------------------------------------------------------------
# We import the scheduler here — adjust the path if yours differs
# ------------------------------------------------------------------
from api.scheduler import Scheduler


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def make_task(
    task_id: str,
    priority: int = 5,
    duration: float = 1.0,
    department: str = "Engineering",
    dependencies: list = None,
    deadline_days: int = 3,
) -> Task:
    return Task(
        task_id=task_id,
        name=f"Task {task_id}",
        priority=priority,
        deadline=datetime.now() + timedelta(days=deadline_days),
        department=department,
        estimated_duration=duration,
        dependencies=dependencies or [],
    )


def build_scheduler_with_tasks(*tasks: Task) -> "Scheduler":
    """Create a fresh Scheduler and submit all given tasks."""
    scheduler = Scheduler()
    for task in tasks:
        scheduler.submit(task)
    return scheduler


# ==================================================================
# 1. Scheduler initialisation
# ==================================================================

class TestSchedulerInit:

    def test_scheduler_creates_successfully(self):
        scheduler = Scheduler()
        assert scheduler is not None

    def test_empty_scheduler_has_no_ready_tasks(self):
        scheduler = Scheduler()
        assert scheduler.queue_size() == 0

    def test_empty_scheduler_next_task_returns_none(self):
        scheduler = Scheduler()
        assert scheduler.next_task() is None

    def test_scheduler_has_dag(self):
        scheduler = Scheduler()
        assert hasattr(scheduler, "dag")
        assert isinstance(scheduler.dag, DAG)

    def test_scheduler_has_history(self):
        scheduler = Scheduler()
        assert hasattr(scheduler, "history")
        assert isinstance(scheduler.history, TaskHistory)


# ==================================================================
# 2. Submitting tasks
# ==================================================================

class TestSubmit:

    def test_submit_single_task_no_deps(self):
        scheduler = Scheduler()
        t = make_task("T1")
        scheduler.submit(t)
        assert scheduler.queue_size() == 1

    def test_submit_task_with_unmet_deps_not_in_queue(self):
        scheduler = Scheduler()
        t1 = make_task("T1")
        t2 = make_task("T2", dependencies=["T1"])
        scheduler.submit(t1)
        scheduler.submit(t2)
        # T2 depends on T1 which is not done yet — only T1 in queue
        assert scheduler.queue_size() == 1

    def test_submit_multiple_independent_tasks(self):
        scheduler = Scheduler()
        for i in range(5):
            scheduler.submit(make_task(f"T{i}"))
        assert scheduler.queue_size() == 5

    def test_submit_duplicate_task_id_raises(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1"))
        with pytest.raises((ValueError, KeyError)):
            scheduler.submit(make_task("T1"))

    def test_submit_task_registers_in_dag(self):
        scheduler = Scheduler()
        t = make_task("T1")
        scheduler.submit(t)
        assert "T1" in scheduler.dag.tasks

    def test_submit_sets_task_status_ready_when_no_deps(self):
        scheduler = Scheduler()
        t = make_task("T1")
        scheduler.submit(t)
        assert t.status == Status.READY

    def test_submit_sets_task_status_pending_when_has_deps(self):
        scheduler = Scheduler()
        t1 = make_task("T1")
        t2 = make_task("T2", dependencies=["T1"])
        scheduler.submit(t1)
        scheduler.submit(t2)
        assert t2.status == Status.PENDING

    def test_submit_dependency_before_dependent_works(self):
        scheduler = Scheduler()
        t1 = make_task("T1")
        t2 = make_task("T2", dependencies=["T1"])
        scheduler.submit(t1)
        scheduler.submit(t2)
        assert scheduler.queue_size() == 1

    def test_submit_with_circular_dependency_raises(self):
        scheduler = Scheduler()
        t1 = make_task("T1")
        t2 = make_task("T2", dependencies=["T1"])
        scheduler.submit(t1)
        scheduler.submit(t2)
        with pytest.raises(ValueError, match="cycle"):
            scheduler.dag.add_dependency("T2", "T1")

    def test_submit_task_with_unknown_dependency_raises(self):
        """Submitting a task whose dependency was never submitted."""
        scheduler = Scheduler()
        t = make_task("T1", dependencies=["GHOST"])
        with pytest.raises((ValueError, KeyError)):
            scheduler.submit(t)


# ==================================================================
# 3. next_task — heap extraction and priority ordering
# ==================================================================

class TestNextTask:

    def test_next_task_returns_highest_priority(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1", priority=3))
        scheduler.submit(make_task("T2", priority=9))
        scheduler.submit(make_task("T3", priority=6))
        task = scheduler.next_task()
        assert task.task_id == "T2"

    def test_next_task_removes_from_queue(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1", priority=5))
        scheduler.submit(make_task("T2", priority=8))
        scheduler.next_task()
        assert scheduler.queue_size() == 1

    def test_next_task_empty_returns_none(self):
        scheduler = Scheduler()
        assert scheduler.next_task() is None

    def test_next_task_sets_status_in_progress(self):
        scheduler = Scheduler()
        t = make_task("T1")
        scheduler.submit(t)
        task = scheduler.next_task()
        assert task.status == Status.IN_PROGRESS

    def test_next_task_sequential_order(self):
        scheduler = Scheduler()
        priorities = [4, 9, 2, 7, 1, 6]
        for i, p in enumerate(priorities):
            scheduler.submit(make_task(f"T{i}", priority=p))

        extracted = []
        while scheduler.queue_size() > 0:
            extracted.append(scheduler.next_task().priority)

        assert extracted == sorted(priorities, reverse=True)

    def test_next_task_single_item(self):
        scheduler = Scheduler()
        t = make_task("T1", priority=7)
        scheduler.submit(t)
        task = scheduler.next_task()
        assert task.task_id == "T1"
        assert scheduler.queue_size() == 0

    def test_next_task_equal_priorities_both_extractable(self):
        """Two tasks with same priority — both must be extractable."""
        scheduler = Scheduler()
        scheduler.submit(make_task("T1", priority=5))
        scheduler.submit(make_task("T2", priority=5))
        t1 = scheduler.next_task()
        t2 = scheduler.next_task()
        assert t1 is not None
        assert t2 is not None
        assert {t1.task_id, t2.task_id} == {"T1", "T2"}


# ==================================================================
# 4. complete_task — finishing work and unlocking dependents
# ==================================================================

class TestCompleteTask:

    def test_complete_task_records_in_history(self):
        scheduler = Scheduler()
        t = make_task("T1")
        scheduler.submit(t)
        scheduler.next_task()
        scheduler.complete_task("T1")
        assert scheduler.history.contains("T1")

    def test_complete_task_sets_status_done(self):
        scheduler = Scheduler()
        t = make_task("T1")
        scheduler.submit(t)
        scheduler.next_task()
        scheduler.complete_task("T1")
        assert t.status == Status.DONE

    def test_complete_task_unlocks_dependents(self):
        scheduler = Scheduler()
        t1 = make_task("T1")
        t2 = make_task("T2", dependencies=["T1"])
        scheduler.submit(t1)
        scheduler.submit(t2)

        scheduler.next_task()           # extracts T1
        scheduler.complete_task("T1")   # should unlock T2

        assert scheduler.queue_size() == 1
        next_t = scheduler.next_task()
        assert next_t.task_id == "T2"

    def test_complete_task_partial_unlock(self):
        """T3 needs T1 and T2 — completing only T1 must not unlock T3."""
        scheduler = Scheduler()
        t1 = make_task("T1")
        t2 = make_task("T2")
        t3 = make_task("T3", dependencies=["T1", "T2"])
        scheduler.submit(t1)
        scheduler.submit(t2)
        scheduler.submit(t3)

        # Extract and complete T1
        t = scheduler.next_task()
        if t.task_id == "T1":
            scheduler.complete_task("T1")
        else:
            scheduler.complete_task("T2")
            scheduler.next_task()

        # T3 should still not be in the queue
        statuses = [task.status for task in scheduler.dag.all_tasks()
                    if task.task_id == "T3"]
        assert statuses[0] == Status.PENDING

    def test_complete_task_unknown_raises(self):
        scheduler = Scheduler()
        with pytest.raises((KeyError, ValueError)):
            scheduler.complete_task("GHOST")

    def test_complete_task_not_in_progress_raises(self):
        """Completing a task that was never extracted should raise."""
        scheduler = Scheduler()
        t = make_task("T1")
        scheduler.submit(t)
        with pytest.raises((ValueError, RuntimeError)):
            scheduler.complete_task("T1")

    def test_complete_task_twice_raises(self):
        scheduler = Scheduler()
        t = make_task("T1")
        scheduler.submit(t)
        scheduler.next_task()
        scheduler.complete_task("T1")
        with pytest.raises((KeyError, ValueError)):
            scheduler.complete_task("T1")

    def test_complete_task_chain_fully_executes(self):
        """T1 -> T2 -> T3 — full chain completes in order."""
        scheduler = Scheduler()
        t1 = make_task("T1", priority=5)
        t2 = make_task("T2", priority=5, dependencies=["T1"])
        t3 = make_task("T3", priority=5, dependencies=["T2"])
        scheduler.submit(t1)
        scheduler.submit(t2)
        scheduler.submit(t3)

        order = []
        for expected in ["T1", "T2", "T3"]:
            task = scheduler.next_task()
            assert task.task_id == expected
            order.append(task.task_id)
            scheduler.complete_task(task.task_id)

        assert order == ["T1", "T2", "T3"]
        assert scheduler.queue_size() == 0


# ==================================================================
# 5. kill_task — cancellation via admin API
# ==================================================================

class TestKillTask:

    def test_kill_removes_from_queue(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1"))
        scheduler.kill_task("T1")
        assert scheduler.queue_size() == 0

    def test_kill_sets_status_cancelled(self):
        scheduler = Scheduler()
        t = make_task("T1")
        scheduler.submit(t)
        scheduler.kill_task("T1")
        assert t.status == Status.CANCELLED

    def test_kill_records_in_history(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1"))
        scheduler.kill_task("T1")
        assert scheduler.history.contains("T1")

    def test_kill_unknown_task_raises(self):
        scheduler = Scheduler()
        with pytest.raises((KeyError, ValueError)):
            scheduler.kill_task("GHOST")

    def test_kill_in_progress_task(self):
        scheduler = Scheduler()
        t = make_task("T1")
        scheduler.submit(t)
        scheduler.next_task()
        scheduler.kill_task("T1")
        assert t.status == Status.CANCELLED

    def test_kill_does_not_unlock_dependents(self):
        """
        If T1 is killed, T2 which depends on T1 should never become ready.
        A killed task is not a completed task.
        """
        scheduler = Scheduler()
        t1 = make_task("T1")
        t2 = make_task("T2", dependencies=["T1"])
        scheduler.submit(t1)
        scheduler.submit(t2)
        scheduler.kill_task("T1")

        assert t2.status == Status.PENDING
        assert scheduler.queue_size() == 0

    def test_kill_highest_priority_next_is_second(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1", priority=10))
        scheduler.submit(make_task("T2", priority=7))
        scheduler.kill_task("T1")
        task = scheduler.next_task()
        assert task.task_id == "T2"


# ==================================================================
# 6. get_status and update_priority
# ==================================================================

class TestGetStatusAndUpdatePriority:

    def test_get_status_ready_task(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1"))
        assert scheduler.get_status("T1") == Status.READY

    def test_get_status_pending_task(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1"))
        scheduler.submit(make_task("T2", dependencies=["T1"]))
        assert scheduler.get_status("T2") == Status.PENDING

    def test_get_status_in_progress(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1"))
        scheduler.next_task()
        assert scheduler.get_status("T1") == Status.IN_PROGRESS

    def test_get_status_done(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1"))
        scheduler.next_task()
        scheduler.complete_task("T1")
        assert scheduler.get_status("T1") == Status.DONE

    def test_get_status_cancelled(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1"))
        scheduler.kill_task("T1")
        assert scheduler.get_status("T1") == Status.CANCELLED

    def test_get_status_unknown_raises(self):
        scheduler = Scheduler()
        with pytest.raises((KeyError, ValueError)):
            scheduler.get_status("GHOST")

    def test_update_priority_changes_value(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1", priority=3))
        scheduler.update_priority("T1", 9)
        assert scheduler.dag.tasks["T1"].priority == 9

    def test_update_priority_reorders_queue(self):
        """
        T1 starts at priority 2, T2 at priority 8.
        After boosting T1 to 10, T1 should come out first.
        """
        scheduler = Scheduler()
        scheduler.submit(make_task("T1", priority=2))
        scheduler.submit(make_task("T2", priority=8))
        scheduler.update_priority("T1", 10)
        task = scheduler.next_task()
        assert task.task_id == "T1"

    def test_update_priority_unknown_raises(self):
        scheduler = Scheduler()
        with pytest.raises((KeyError, ValueError)):
            scheduler.update_priority("GHOST", 5)

    def test_update_priority_pending_task(self):
        """Priority update on a pending (not yet queued) task updates the model."""
        scheduler = Scheduler()
        scheduler.submit(make_task("T1"))
        scheduler.submit(make_task("T2", dependencies=["T1"]))
        scheduler.update_priority("T2", 10)
        assert scheduler.dag.tasks["T2"].priority == 10


# ==================================================================
# 7. list_queue
# ==================================================================

class TestListQueue:

    def test_list_queue_returns_all_ready_tasks(self):
        scheduler = Scheduler()
        for i in range(4):
            scheduler.submit(make_task(f"T{i}"))
        queue = scheduler.list_queue()
        assert len(queue) == 4

    def test_list_queue_sorted_by_priority(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1", priority=3))
        scheduler.submit(make_task("T2", priority=9))
        scheduler.submit(make_task("T3", priority=6))
        queue = scheduler.list_queue()
        priorities = [t.priority for t in queue]
        assert priorities == sorted(priorities, reverse=True)

    def test_list_queue_empty_returns_empty_list(self):
        scheduler = Scheduler()
        assert scheduler.list_queue() == []

    def test_list_queue_does_not_modify_queue(self):
        """Peeking the queue must not consume any tasks."""
        scheduler = Scheduler()
        for i in range(3):
            scheduler.submit(make_task(f"T{i}"))
        scheduler.list_queue()
        assert scheduler.queue_size() == 3

    def test_list_queue_excludes_pending_tasks(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1"))
        scheduler.submit(make_task("T2", dependencies=["T1"]))
        queue = scheduler.list_queue()
        ids = [t.task_id for t in queue]
        assert "T2" not in ids
        assert "T1" in ids


# ==================================================================
# 8. Anti-starvation
# ==================================================================

class TestAntiStarvation:

    def test_effective_priority_increases_with_wait_time(self):
        """
        A low-priority task that has been waiting a long time should
        have a higher effective_priority than its raw priority alone.
        """
        t = make_task("T1", priority=1)
        t.wait_time = 100.0   # simulate 100 hours waiting
        effective = t.effective_priority(starvation_weight=0.1)
        assert effective > t.priority

    def test_high_wait_time_can_overtake_higher_raw_priority(self):
        """
        T1: priority=8, wait=0
        T2: priority=2, wait=100h, weight=0.1  → effective = 2 + 10 = 12
        T2 should have higher effective priority.
        """
        t1 = make_task("T1", priority=8)
        t2 = make_task("T2", priority=2)
        t1.wait_time = 0.0
        t2.wait_time = 100.0
        assert t2.effective_priority(0.1) > t1.effective_priority(0.1)

    def test_zero_wait_time_effective_equals_raw(self):
        t = make_task("T1", priority=7)
        t.wait_time = 0.0
        assert t.effective_priority(0.1) == pytest.approx(7.0)

    def test_update_wait_time_increases_over_time(self):
        """
        After calling update_wait_time on a READY task,
        wait_time should be > 0.
        """
        import time
        t = make_task("T1")
        t.status = Status.READY
        # Manually backdate created_at to simulate waiting
        t.created_at = datetime.now() - timedelta(hours=5)
        t.update_wait_time()
        assert t.wait_time > 0.0

    def test_update_wait_time_not_updated_for_non_ready(self):
        """
        update_wait_time should only affect READY tasks.
        A PENDING task's wait_time should remain 0.
        """
        t = make_task("T1")
        t.status = Status.PENDING
        t.wait_time = 0.0
        t.update_wait_time()
        assert t.wait_time == 0.0


# ==================================================================
# 9. Critical path integration
# ==================================================================

class TestCriticalPathIntegration:

    def test_critical_path_tasks_get_priority_boost(self):
        """
        After submitting tasks, tasks on the critical path should have
        a higher priority than their original value.
        """
        scheduler = Scheduler()
        t1 = make_task("T1", priority=5, duration=1.0)
        t2 = make_task("T2", priority=5, duration=10.0, dependencies=["T1"])
        t3 = make_task("T3", priority=5, duration=1.0, dependencies=["T1"])

        original_t2_priority = t2.priority
        scheduler.submit(t1)
        scheduler.submit(t2)
        scheduler.submit(t3)

        # T2 is on the critical path (longer duration)
        # Its effective or stored priority should be boosted
        assert scheduler.dag.tasks["T2"].priority >= original_t2_priority

    def test_critical_path_task_extracted_before_non_critical(self):
        """
        T1 → T2 (duration 10h, critical)
        T1 → T3 (duration 1h, non-critical)
        Both T2 and T3 depend on T1. After T1 completes,
        T2 should come out of the heap before T3 due to its boost.
        """
        scheduler = Scheduler()
        t1 = make_task("T1", priority=5, duration=1.0)
        t2 = make_task("T2", priority=5, duration=10.0, dependencies=["T1"])
        t3 = make_task("T3", priority=5, duration=1.0, dependencies=["T1"])
        scheduler.submit(t1)
        scheduler.submit(t2)
        scheduler.submit(t3)

        # Complete T1 to unlock T2 and T3
        first = scheduler.next_task()
        assert first.task_id == "T1"
        scheduler.complete_task("T1")

        # T2 should be next due to critical path boost
        second = scheduler.next_task()
        assert second.task_id == "T2"


# ==================================================================
# 10. End-to-end integration scenarios
# ==================================================================

class TestEndToEnd:

    def test_full_diamond_execution(self):
        """
        T1 → T2, T3 → T4
        All tasks complete in a valid topological order.
        """
        scheduler = Scheduler()
        scheduler.submit(make_task("T1", priority=5))
        scheduler.submit(make_task("T2", priority=6, dependencies=["T1"]))
        scheduler.submit(make_task("T3", priority=4, dependencies=["T1"]))
        scheduler.submit(make_task("T4", priority=8, dependencies=["T2", "T3"]))

        completed = []

        # Step 1: only T1 is ready
        t = scheduler.next_task()
        assert t.task_id == "T1"
        scheduler.complete_task("T1")
        completed.append("T1")

        # Step 2: T2 and T3 unlocked — T2 has higher priority
        t = scheduler.next_task()
        assert t.task_id == "T2"
        scheduler.complete_task("T2")
        completed.append("T2")

        # Step 3: T3 still waiting
        t = scheduler.next_task()
        assert t.task_id == "T3"
        scheduler.complete_task("T3")
        completed.append("T3")

        # Step 4: T4 now unlocked
        t = scheduler.next_task()
        assert t.task_id == "T4"
        scheduler.complete_task("T4")
        completed.append("T4")

        assert completed == ["T1", "T2", "T3", "T4"]
        assert scheduler.queue_size() == 0

    def test_mixed_departments_all_complete(self):
        scheduler = Scheduler()
        scheduler.submit(make_task("T1", department="Engineering", priority=7))
        scheduler.submit(make_task("T2", department="HR", priority=5))
        scheduler.submit(make_task("T3", department="Finance", priority=9))

        completed = []
        while scheduler.queue_size() > 0:
            t = scheduler.next_task()
            scheduler.complete_task(t.task_id)
            completed.append(t.task_id)

        assert set(completed) == {"T1", "T2", "T3"}
        assert completed[0] == "T3"   # highest priority first

    def test_history_populated_after_full_run(self):
        scheduler = Scheduler()
        for i in range(5):
            scheduler.submit(make_task(f"T{i}", priority=i + 1))

        while scheduler.queue_size() > 0:
            t = scheduler.next_task()
            scheduler.complete_task(t.task_id)

        assert len(scheduler.history) == 5

    def test_kill_mid_run_does_not_break_scheduler(self):
        scheduler = Scheduler()
        for i in range(4):
            scheduler.submit(make_task(f"T{i}", priority=i + 1))

        scheduler.kill_task("T3")   # kill highest priority before it runs

        completed = []
        while scheduler.queue_size() > 0:
            t = scheduler.next_task()
            scheduler.complete_task(t.task_id)
            completed.append(t.task_id)

        assert "T3" not in completed
        assert len(completed) == 3

    def test_large_independent_batch(self):
        """20 independent tasks — all must complete, order by priority."""
        scheduler = Scheduler()
        import random
        random.seed(42)
        priorities = random.sample(range(1, 101), 20)
        for i, p in enumerate(priorities):
            scheduler.submit(make_task(f"T{i}", priority=p))

        extracted_priorities = []
        while scheduler.queue_size() > 0:
            t = scheduler.next_task()
            extracted_priorities.append(t.priority)
            scheduler.complete_task(t.task_id)

        assert extracted_priorities == sorted(priorities, reverse=True)

    def test_chain_with_priority_variation(self):
        """
        Linear chain T1->T2->T3->T4->T5.
        Each task has different priority but must still execute in chain order.
        """
        scheduler = Scheduler()
        scheduler.submit(make_task("T1", priority=1))
        scheduler.submit(make_task("T2", priority=9, dependencies=["T1"]))
        scheduler.submit(make_task("T3", priority=3, dependencies=["T2"]))
        scheduler.submit(make_task("T4", priority=7, dependencies=["T3"]))
        scheduler.submit(make_task("T5", priority=5, dependencies=["T4"]))

        order = []
        for _ in range(5):
            t = scheduler.next_task()
            order.append(t.task_id)
            scheduler.complete_task(t.task_id)

        assert order == ["T1", "T2", "T3", "T4", "T5"]

    def test_scheduler_summary_after_run(self):
        """history.summary() must not crash after a full run."""
        scheduler = Scheduler()
        for i in range(3):
            scheduler.submit(make_task(f"T{i}"))
        while scheduler.queue_size() > 0:
            t = scheduler.next_task()
            scheduler.complete_task(t.task_id)
        summary = scheduler.history.summary()
        assert "History log" in summary
        assert "3" in summary

    def test_overdue_tasks_recorded_with_delay(self):
        """Tasks submitted with a past deadline should record a delay > 0."""
        scheduler = Scheduler()
        t = Task(
            task_id="LATE",
            name="Overdue task",
            priority=5,
            deadline=datetime.now() - timedelta(hours=10),  # already past
            department="Engineering",
            estimated_duration=1.0,
        )
        scheduler.submit(t)
        scheduler.next_task()
        scheduler.complete_task("LATE")
        recorded = scheduler.history.get("LATE")
        assert recorded.delay is not None
        assert recorded.delay > 0