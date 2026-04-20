# core/graph.py

from collections import deque
from core.models import Task, Status


class DAG:
    def __init__(self):
        self.tasks = {}        # task_id -> Task object
        self.successors = {}   # task_id -> list of task_ids it unlocks
        self.predecessors = {} # task_id -> list of task_ids it waits for
        self.in_degree = {}    # task_id -> count of unfinished predecessors

    # ------------------------------------------------------------------
    # Adding tasks and edges
    # ------------------------------------------------------------------

    def add_task(self, task: Task):
        """Register a task in the graph with no edges yet."""
        tid = task.task_id
        self.tasks[tid] = task
        self.successors[tid] = []
        self.predecessors[tid] = []
        self.in_degree[tid] = 0

    def add_dependency(self, from_id: str, to_id: str):
        """
        Add edge: from_id must finish BEFORE to_id can start.
        Raises ValueError if adding this edge would create a cycle.
        """
        if from_id not in self.tasks:
            raise KeyError(f"Task '{from_id}' not found in graph.")
        if to_id not in self.tasks:
            raise KeyError(f"Task '{to_id}' not found in graph.")
        if self._would_create_cycle(from_id, to_id):
            raise ValueError(
                f"Adding {from_id} -> {to_id} would create a cycle. Rejected."
            )
        self.successors[from_id].append(to_id)
        self.predecessors[to_id].append(from_id)
        self.in_degree[to_id] += 1

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    def _would_create_cycle(self, from_id: str, to_id: str) -> bool:
        """
        DFS from to_id forward through successors.
        If we can reach from_id, adding this edge creates a cycle.
        """
        visited = set()
        stack = [to_id]
        while stack:
            current = stack.pop()
            if current == from_id:
                return True
            if current not in visited:
                visited.add(current)
                stack.extend(self.successors.get(current, []))
        return False

    # ------------------------------------------------------------------
    # Readiness — bridge to the heap
    # ------------------------------------------------------------------

    def get_ready_tasks(self) -> list:
        """
        Return all tasks with in_degree == 0 and status PENDING.
        Called once at startup to seed the heap with the first wave of tasks.
        """
        return [
            self.tasks[tid]
            for tid in self.tasks
            if self.in_degree[tid] == 0
            and self.tasks[tid].status == Status.PENDING
        ]

    def mark_complete(self, task_id: str) -> list:
        """
        Called by the scheduler when a task finishes execution.
        - Marks the task as done
        - Decrements in_degree of every successor
        - Returns the list of tasks that just became ready (in_degree hit 0)

        The scheduler feeds this return value directly into the heap.
        """
        if task_id not in self.tasks:
            raise KeyError(f"Task '{task_id}' not found in graph.")

        self.tasks[task_id].mark_done()
        newly_ready = []

        for successor_id in self.successors[task_id]:
            self.in_degree[successor_id] -= 1
            if self.in_degree[successor_id] == 0:
                successor = self.tasks[successor_id]
                successor.mark_ready()
                newly_ready.append(successor)

        return newly_ready

    # ------------------------------------------------------------------
    # Algorithms
    # ------------------------------------------------------------------

    def topological_sort(self) -> list:
        """
        Kahn's algorithm.
        Returns a valid execution order, or raises if a cycle exists.
        Time complexity: O(V + E) where V = tasks, E = dependencies.
        """
        in_deg = dict(self.in_degree)
        queue = deque([tid for tid in in_deg if in_deg[tid] == 0])
        order = []

        while queue:
            tid = queue.popleft()
            order.append(tid)
            for successor_id in self.successors[tid]:
                in_deg[successor_id] -= 1
                if in_deg[successor_id] == 0:
                    queue.append(successor_id)

        if len(order) != len(self.tasks):
            raise ValueError("Cycle detected — topological sort failed.")

        return order

    def critical_path(self) -> tuple[list, float]:
        """
        Finds the longest path through the DAG by estimated_duration.
        Returns (list of task_ids on the critical path, total duration).
        Time complexity: O(V + E).
        """
        topo_order = self.topological_sort()

        earliest = {tid: 0.0 for tid in self.tasks}
        came_from = {tid: None for tid in self.tasks}

        for tid in topo_order:
            duration = self.tasks[tid].estimated_duration or 1.0
            finish_time = earliest[tid] + duration

            # Update this task's own earliest finish time
            earliest[tid] = finish_time

            for successor_id in self.successors[tid]:
                if finish_time > earliest[successor_id]:
                    earliest[successor_id] = finish_time
                    came_from[successor_id] = tid

        end_task = max(earliest, key=lambda tid: earliest[tid])
        total_duration = earliest[end_task]

        path = []
        current = end_task
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse()

        return path, total_duration

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def get_task(self, task_id: str) -> Task:
        """Fetch a task by ID. Used by the Admin API."""
        if task_id not in self.tasks:
            raise KeyError(f"Task '{task_id}' not found.")
        return self.tasks[task_id]

    def all_tasks(self) -> list:
        """Return all tasks as a list. Used by visualisation."""
        return list(self.tasks.values())

    def all_edges(self) -> list:
        """
        Return all edges as (from_id, to_id) tuples.
        Used by the visualisation to draw arrows between nodes.
        """
        edges = []
        for from_id, successors in self.successors.items():
            for to_id in successors:
                edges.append((from_id, to_id))
        return edges

    def __repr__(self):
        return (
            f"DAG(tasks={len(self.tasks)}, "
            f"edges={sum(len(v) for v in self.successors.values())})"
        )