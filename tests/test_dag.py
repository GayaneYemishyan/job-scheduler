# tests/test_dag.py

import pytest
from datetime import datetime, timedelta
from core.models import Task, Status, PriorityLevel
from core.graph import DAG


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def make_task(task_id: str, priority: int = 5, duration: float = 1.0,
              department: str = "Engineering") -> Task:
    """Create a minimal Task for testing purposes."""
    return Task(
        task_id=task_id,
        name=f"Task {task_id}",
        priority=priority,
        deadline=datetime.now() + timedelta(days=3),
        department=department,
        estimated_duration=duration,
    )


def build_linear_dag() -> DAG:
    """
    T1 -> T2 -> T3 -> T4
    Simple chain, one valid topo order.
    """
    dag = DAG()
    for tid in ["T1", "T2", "T3", "T4"]:
        dag.add_task(make_task(tid))
    dag.add_dependency("T1", "T2")
    dag.add_dependency("T2", "T3")
    dag.add_dependency("T3", "T4")
    return dag


def build_diamond_dag() -> DAG:
    """
         T1
        /  \\
       T2   T3
        \\  /
         T4
    T1 must finish before T2 and T3.
    T4 must wait for both T2 and T3.
    """
    dag = DAG()
    for tid in ["T1", "T2", "T3", "T4"]:
        dag.add_task(make_task(tid))
    dag.add_dependency("T1", "T2")
    dag.add_dependency("T1", "T3")
    dag.add_dependency("T2", "T4")
    dag.add_dependency("T3", "T4")
    return dag


def build_wide_dag() -> DAG:
    """
    T1 -> T3
    T2 -> T3
    T2 -> T4
    Two roots, two leaves.
    """
    dag = DAG()
    for tid in ["T1", "T2", "T3", "T4"]:
        dag.add_task(make_task(tid))
    dag.add_dependency("T1", "T3")
    dag.add_dependency("T2", "T3")
    dag.add_dependency("T2", "T4")
    return dag


# ==================================================================
# 1. DAG construction
# ==================================================================

class TestDAGConstruction:

    def test_add_single_task(self):
        dag = DAG()
        t = make_task("T1")
        dag.add_task(t)
        assert "T1" in dag.tasks
        assert dag.in_degree["T1"] == 0
        assert dag.successors["T1"] == []
        assert dag.predecessors["T1"] == []

    def test_add_multiple_tasks(self):
        dag = DAG()
        for tid in ["T1", "T2", "T3"]:
            dag.add_task(make_task(tid))
        assert len(dag.tasks) == 3

    def test_add_dependency_updates_structures(self):
        dag = DAG()
        dag.add_task(make_task("T1"))
        dag.add_task(make_task("T2"))
        dag.add_dependency("T1", "T2")

        assert "T2" in dag.successors["T1"]
        assert "T1" in dag.predecessors["T2"]
        assert dag.in_degree["T2"] == 1
        assert dag.in_degree["T1"] == 0

    def test_multiple_dependencies_on_one_task(self):
        dag = build_diamond_dag()
        assert dag.in_degree["T4"] == 2
        assert dag.in_degree["T1"] == 0

    def test_task_with_multiple_successors(self):
        dag = build_diamond_dag()
        assert set(dag.successors["T1"]) == {"T2", "T3"}

    def test_add_dependency_unknown_from_raises(self):
        dag = DAG()
        dag.add_task(make_task("T2"))
        with pytest.raises(KeyError):
            dag.add_dependency("GHOST", "T2")

    def test_add_dependency_unknown_to_raises(self):
        dag = DAG()
        dag.add_task(make_task("T1"))
        with pytest.raises(KeyError):
            dag.add_dependency("T1", "GHOST")

    def test_repr(self):
        dag = build_linear_dag()
        r = repr(dag)
        assert "DAG" in r
        assert "tasks=4" in r

    def test_all_edges(self):
        dag = build_linear_dag()
        edges = dag.all_edges()
        assert ("T1", "T2") in edges
        assert ("T2", "T3") in edges
        assert ("T3", "T4") in edges
        assert len(edges) == 3

    def test_all_tasks_returns_all(self):
        dag = build_diamond_dag()
        ids = {t.task_id for t in dag.all_tasks()}
        assert ids == {"T1", "T2", "T3", "T4"}

    def test_get_task_by_id(self):
        dag = DAG()
        t = make_task("T1")
        dag.add_task(t)
        assert dag.get_task("T1") is t

    def test_get_task_unknown_raises(self):
        dag = DAG()
        with pytest.raises(KeyError):
            dag.get_task("GHOST")


# ==================================================================
# 2. Cycle detection
# ==================================================================

class TestCycleDetection:

    def test_self_loop_raises(self):
        dag = DAG()
        dag.add_task(make_task("T1"))
        with pytest.raises(ValueError, match="cycle"):
            dag.add_dependency("T1", "T1")

    def test_two_node_cycle_raises(self):
        dag = DAG()
        dag.add_task(make_task("T1"))
        dag.add_task(make_task("T2"))
        dag.add_dependency("T1", "T2")
        with pytest.raises(ValueError, match="cycle"):
            dag.add_dependency("T2", "T1")

    def test_three_node_cycle_raises(self):
        dag = DAG()
        for tid in ["T1", "T2", "T3"]:
            dag.add_task(make_task(tid))
        dag.add_dependency("T1", "T2")
        dag.add_dependency("T2", "T3")
        with pytest.raises(ValueError, match="cycle"):
            dag.add_dependency("T3", "T1")

    def test_long_chain_cycle_raises(self):
        dag = DAG()
        for i in range(1, 7):
            dag.add_task(make_task(f"T{i}"))
        for i in range(1, 6):
            dag.add_dependency(f"T{i}", f"T{i+1}")
        with pytest.raises(ValueError, match="cycle"):
            dag.add_dependency("T6", "T1")

    def test_valid_dag_does_not_raise(self):
        dag = build_diamond_dag()
        assert dag is not None

    def test_parallel_paths_no_cycle(self):
        dag = build_wide_dag()
        assert dag is not None

    def test_dag_state_unchanged_after_rejected_cycle(self):
        """Rejected edges must not partially modify the graph."""
        dag = DAG()
        dag.add_task(make_task("T1"))
        dag.add_task(make_task("T2"))
        dag.add_dependency("T1", "T2")

        try:
            dag.add_dependency("T2", "T1")
        except ValueError:
            pass

        assert "T1" not in dag.successors["T2"]
        assert dag.in_degree["T1"] == 0

    def test_no_false_cycle_on_shared_successor(self):
        """
        T1 -> T3
        T2 -> T3
        Adding T2->T3 should NOT be flagged as a cycle.
        """
        dag = DAG()
        for tid in ["T1", "T2", "T3"]:
            dag.add_task(make_task(tid))
        dag.add_dependency("T1", "T3")
        dag.add_dependency("T2", "T3")
        assert dag.in_degree["T3"] == 2


# ==================================================================
# 3. Topological sort
# ==================================================================

class TestTopologicalSort:

    def test_linear_chain_order(self):
        dag = build_linear_dag()
        order = dag.topological_sort()
        assert order.index("T1") < order.index("T2")
        assert order.index("T2") < order.index("T3")
        assert order.index("T3") < order.index("T4")

    def test_all_tasks_present_in_order(self):
        dag = build_linear_dag()
        order = dag.topological_sort()
        assert set(order) == {"T1", "T2", "T3", "T4"}

    def test_diamond_dag_order(self):
        dag = build_diamond_dag()
        order = dag.topological_sort()
        assert order.index("T1") < order.index("T2")
        assert order.index("T1") < order.index("T3")
        assert order.index("T2") < order.index("T4")
        assert order.index("T3") < order.index("T4")

    def test_wide_dag_order(self):
        dag = build_wide_dag()
        order = dag.topological_sort()
        assert order.index("T1") < order.index("T3")
        assert order.index("T2") < order.index("T3")
        assert order.index("T2") < order.index("T4")

    def test_single_task_dag(self):
        dag = DAG()
        dag.add_task(make_task("T1"))
        order = dag.topological_sort()
        assert order == ["T1"]

    def test_no_dependencies_any_order_valid(self):
        """All tasks independent — any order is valid, all must appear."""
        dag = DAG()
        for tid in ["T1", "T2", "T3"]:
            dag.add_task(make_task(tid))
        order = dag.topological_sort()
        assert set(order) == {"T1", "T2", "T3"}
        assert len(order) == 3

    def test_topo_sort_does_not_modify_in_degree(self):
        """topological_sort must work on a copy — real in_degree unchanged."""
        dag = build_linear_dag()
        original_in_degrees = dict(dag.in_degree)
        dag.topological_sort()
        assert dag.in_degree == original_in_degrees

    def test_topo_sort_called_twice_same_result(self):
        """Sort must be repeatable — calling twice gives same ordering."""
        dag = build_linear_dag()
        order1 = dag.topological_sort()
        order2 = dag.topological_sort()
        assert order1 == order2

    def test_empty_dag_returns_empty_list(self):
        dag = DAG()
        assert dag.topological_sort() == []

    def test_large_chain(self):
        """100-node linear chain — order must be strictly T1 < T2 < ... < T100."""
        dag = DAG()
        for i in range(1, 101):
            dag.add_task(make_task(f"T{i}"))
        for i in range(1, 100):
            dag.add_dependency(f"T{i}", f"T{i+1}")
        order = dag.topological_sort()
        assert len(order) == 100
        for i in range(1, 100):
            assert order.index(f"T{i}") < order.index(f"T{i+1}")


# ==================================================================
# 4. Ready tasks and mark_complete
# ==================================================================

class TestReadinessAndCompletion:

    def test_get_ready_tasks_at_start(self):
        dag = build_diamond_dag()
        ready = {t.task_id for t in dag.get_ready_tasks()}
        assert ready == {"T1"}

    def test_no_deps_all_ready_at_start(self):
        dag = DAG()
        for tid in ["T1", "T2", "T3"]:
            dag.add_task(make_task(tid))
        ready = {t.task_id for t in dag.get_ready_tasks()}
        assert ready == {"T1", "T2", "T3"}

    def test_mark_complete_unlocks_successors(self):
        dag = build_diamond_dag()
        # T1 has no deps — mark it ready manually then complete it
        dag.tasks["T1"].mark_ready()
        dag.tasks["T1"].mark_in_progress()
        newly_ready = dag.mark_complete("T1")
        newly_ready_ids = {t.task_id for t in newly_ready}
        assert newly_ready_ids == {"T2", "T3"}

    def test_mark_complete_decrements_in_degree(self):
        dag = build_diamond_dag()
        dag.tasks["T1"].mark_ready()
        dag.tasks["T1"].mark_in_progress()
        dag.mark_complete("T1")
        assert dag.in_degree["T2"] == 0
        assert dag.in_degree["T3"] == 0

    def test_mark_complete_partial_unlock(self):
        """
        T4 needs both T2 and T3. Completing T2 alone should NOT unlock T4.
        """
        dag = build_diamond_dag()
        dag.tasks["T1"].mark_ready()
        dag.tasks["T1"].mark_in_progress()
        dag.mark_complete("T1")

        dag.tasks["T2"].mark_in_progress()
        newly_ready = dag.mark_complete("T2")
        assert not any(t.task_id == "T4" for t in newly_ready)
        assert dag.in_degree["T4"] == 1

    def test_mark_complete_full_unlock_after_both_predecessors(self):
        """T4 unlocks only after BOTH T2 and T3 complete."""
        dag = build_diamond_dag()
        dag.tasks["T1"].mark_ready()
        dag.tasks["T1"].mark_in_progress()
        dag.mark_complete("T1")

        dag.tasks["T2"].mark_in_progress()
        dag.mark_complete("T2")

        dag.tasks["T3"].mark_in_progress()
        newly_ready = dag.mark_complete("T3")
        assert any(t.task_id == "T4" for t in newly_ready)

    def test_mark_complete_sets_task_status_done(self):
        dag = build_linear_dag()
        dag.tasks["T1"].mark_ready()
        dag.tasks["T1"].mark_in_progress()
        dag.mark_complete("T1")
        assert dag.tasks["T1"].status == Status.DONE

    def test_mark_complete_sets_completed_at(self):
        dag = build_linear_dag()
        dag.tasks["T1"].mark_ready()
        dag.tasks["T1"].mark_in_progress()
        dag.mark_complete("T1")
        assert dag.tasks["T1"].completed_at is not None

    def test_mark_complete_unknown_task_raises(self):
        dag = build_linear_dag()
        with pytest.raises(KeyError):
            dag.mark_complete("GHOST")

    def test_get_ready_tasks_excludes_already_ready(self):
        """
        After T1 is marked ready (status no longer PENDING),
        get_ready_tasks should not return it again.
        """
        dag = build_diamond_dag()
        dag.tasks["T1"].mark_ready()
        ready = dag.get_ready_tasks()
        assert all(t.task_id != "T1" for t in ready)

    def test_full_linear_execution_flow(self):
        """Walk T1->T2->T3->T4 to completion, checking unlocks at each step."""
        dag = build_linear_dag()

        for tid in ["T1", "T2", "T3"]:
            dag.tasks[tid].mark_ready()
            dag.tasks[tid].mark_in_progress()
            newly_ready = dag.mark_complete(tid)
            next_tid = f"T{int(tid[1]) + 1}"
            assert any(t.task_id == next_tid for t in newly_ready)

        dag.tasks["T4"].mark_ready()
        dag.tasks["T4"].mark_in_progress()
        newly_ready = dag.mark_complete("T4")
        assert newly_ready == []
        assert dag.tasks["T4"].status == Status.DONE


# ==================================================================
# 5. Critical path
# ==================================================================

class TestCriticalPath:

    def test_linear_chain_full_path(self):
        """In a linear chain every task is on the critical path."""
        dag = build_linear_dag()
        path, duration = dag.critical_path()
        assert set(path) == {"T1", "T2", "T3", "T4"}

    def test_linear_chain_duration(self):
        """Each task has duration=1.0 so total should be 4.0."""
        dag = build_linear_dag()
        _, duration = dag.critical_path()
        assert duration == pytest.approx(4.0)

    def test_diamond_critical_path_includes_endpoints(self):
        """T1 and T4 must always be on the critical path in a diamond."""
        dag = build_diamond_dag()
        path, _ = dag.critical_path()
        assert "T1" in path
        assert "T4" in path

    def test_diamond_critical_path_picks_longer_branch(self):
        """
        Give T2 duration=5.0 and T3 duration=1.0.
        Critical path should go through T2 not T3.
        """
        dag = DAG()
        dag.add_task(make_task("T1", duration=1.0))
        dag.add_task(make_task("T2", duration=5.0))
        dag.add_task(make_task("T3", duration=1.0))
        dag.add_task(make_task("T4", duration=1.0))
        dag.add_dependency("T1", "T2")
        dag.add_dependency("T1", "T3")
        dag.add_dependency("T2", "T4")
        dag.add_dependency("T3", "T4")
        path, duration = dag.critical_path()
        assert "T2" in path
        assert duration == pytest.approx(7.0)   # T1(1) + T2(5) + T4(1)

    def test_critical_path_duration_correctness(self):
        """
        T1(2h) -> T2(3h) -> T4(1h)
        T1(2h) -> T3(1h) -> T4(1h)
        Critical path = T1->T2->T4, duration = 6.0
        """
        dag = DAG()
        dag.add_task(make_task("T1", duration=2.0))
        dag.add_task(make_task("T2", duration=3.0))
        dag.add_task(make_task("T3", duration=1.0))
        dag.add_task(make_task("T4", duration=1.0))
        dag.add_dependency("T1", "T2")
        dag.add_dependency("T1", "T3")
        dag.add_dependency("T2", "T4")
        dag.add_dependency("T3", "T4")
        path, duration = dag.critical_path()
        assert duration == pytest.approx(6.0)
        assert "T2" in path

    def test_single_task_critical_path(self):
        dag = DAG()
        dag.add_task(make_task("T1", duration=3.0))
        path, duration = dag.critical_path()
        assert path == ["T1"]
        assert duration == pytest.approx(3.0)

    def test_critical_path_returns_list(self):
        dag = build_linear_dag()
        path, duration = dag.critical_path()
        assert isinstance(path, list)
        assert isinstance(duration, float)

    def test_critical_path_order_is_valid_topo_order(self):
        """Every step in the critical path must respect dependency order."""
        dag = build_diamond_dag()
        path, _ = dag.critical_path()
        topo = dag.topological_sort()
        for i in range(len(path) - 1):
            assert topo.index(path[i]) < topo.index(path[i + 1])

    def test_none_duration_defaults_to_1(self):
        """Tasks with no estimated_duration should default to 1.0 hours."""
        dag = DAG()
        t = Task(
            task_id="T1",
            name="No duration task",
            priority=5,
            deadline=datetime.now() + timedelta(days=1),
            department="Engineering",
            estimated_duration=None,
        )
        dag.add_task(t)
        path, duration = dag.critical_path()
        assert duration == pytest.approx(1.0)

    def test_parallel_independent_tasks_longest_wins(self):
        """
        T1(1h), T2(5h), T3(2h) — no dependencies.
        Critical path is just T2 with duration 5.0.
        """
        dag = DAG()
        dag.add_task(make_task("T1", duration=1.0))
        dag.add_task(make_task("T2", duration=5.0))
        dag.add_task(make_task("T3", duration=2.0))
        _, duration = dag.critical_path()
        assert duration == pytest.approx(5.0)

    def test_critical_path_not_affected_by_topo_sort_side_effects(self):
        """critical_path calls topological_sort internally — in_degree must stay intact."""
        dag = build_diamond_dag()
        original_in_degrees = dict(dag.in_degree)
        dag.critical_path()
        assert dag.in_degree == original_in_degrees


# ==================================================================
# 6. Edge cases and stress tests
# ==================================================================

class TestEdgeCases:

    def test_empty_dag_get_ready_tasks(self):
        dag = DAG()
        assert dag.get_ready_tasks() == []

    def test_empty_dag_all_edges(self):
        dag = DAG()
        assert dag.all_edges() == []

    def test_empty_dag_all_tasks(self):
        dag = DAG()
        assert dag.all_tasks() == []

    def test_duplicate_task_id_overwrites(self):
        """Adding a task with an existing ID replaces it."""
        dag = DAG()
        t1 = make_task("T1", priority=3)
        t1_new = make_task("T1", priority=9)
        dag.add_task(t1)
        dag.add_task(t1_new)
        assert dag.tasks["T1"].priority == 9

    def test_wide_fan_out(self):
        """One root task unlocking 10 successors simultaneously."""
        dag = DAG()
        dag.add_task(make_task("ROOT"))
        for i in range(10):
            dag.add_task(make_task(f"T{i}"))
            dag.add_dependency("ROOT", f"T{i}")

        dag.tasks["ROOT"].mark_ready()
        dag.tasks["ROOT"].mark_in_progress()
        newly_ready = dag.mark_complete("ROOT")
        assert len(newly_ready) == 10

    def test_wide_fan_in(self):
        """One task that needs 10 predecessors — only unlocks after all complete."""
        dag = DAG()
        dag.add_task(make_task("FINAL"))
        for i in range(10):
            tid = f"T{i}"
            dag.add_task(make_task(tid))
            dag.add_dependency(tid, "FINAL")

        for i in range(9):
            dag.tasks[f"T{i}"].mark_ready()
            dag.tasks[f"T{i}"].mark_in_progress()
            newly_ready = dag.mark_complete(f"T{i}")
            assert not any(t.task_id == "FINAL" for t in newly_ready)

        dag.tasks["T9"].mark_ready()
        dag.tasks["T9"].mark_in_progress()
        newly_ready = dag.mark_complete("T9")
        assert any(t.task_id == "FINAL" for t in newly_ready)

    def test_50_node_chain_no_errors(self):
        """Stress test — 50 node linear chain builds and sorts without error."""
        dag = DAG()
        for i in range(1, 51):
            dag.add_task(make_task(f"T{i}"))
        for i in range(1, 50):
            dag.add_dependency(f"T{i}", f"T{i+1}")
        order = dag.topological_sort()
        assert len(order) == 50

    def test_mixed_department_tasks(self):
        dag = DAG()
        dag.add_task(make_task("T1", department="Engineering"))
        dag.add_task(make_task("T2", department="HR"))
        dag.add_task(make_task("T3", department="Finance"))
        assert len(dag.all_tasks()) == 3

    def test_dependency_does_not_affect_unrelated_tasks(self):
        """Adding T1->T2 must not change in_degree of T3."""
        dag = DAG()
        for tid in ["T1", "T2", "T3"]:
            dag.add_task(make_task(tid))
        dag.add_dependency("T1", "T2")
        assert dag.in_degree["T3"] == 0
        assert dag.successors["T3"] == []