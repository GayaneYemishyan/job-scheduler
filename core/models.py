from datetime import datetime
from enum import Enum


class Status(Enum):
    PENDING     = "pending"      # created but dependencies not met yet
    READY       = "ready"        # dependencies done, waiting in queue
    IN_PROGRESS = "in_progress"  # currently being worked on
    DONE        = "done"         # completed successfully
    DELAYED     = "delayed"      # past deadline, still not done
    CANCELLED   = "cancelled"    # killed via admin API


class PriorityLevel(Enum):
    CRITICAL = 4
    HIGH     = 3
    MEDIUM   = 2
    LOW      = 1


class Task:
    """
    Core data object managed by the scheduler.

    Priority model
    --------------
    base_priority   — the caller-supplied value; never touched by the scheduler
                      after submission (except via update_priority).
    priority        — the value the heap actually sorts on; may be raised by
                      CRITICAL_PATH_BOOST on top of base_priority.
    effective_priority() — priority + starvation_weight * wait_time; used by
                      the heap's _compare() so long-waiting low-priority tasks
                      eventually bubble to the top.

    Anti-starvation
    ---------------
    wait_time is updated by the scheduler's refresh_wait_times() pass
    (which calls update_wait_time() on every READY task). The starvation
    weight is intentionally small (default 0.1) so a task needs to wait
    ~10 hours before it gains 1 unit of effective priority.
    """

    def __init__(
        self,
        task_id:            str,
        name:               str,
        priority:           int,
        deadline:           datetime,
        department:         str,
        assigned_to:        str            = None,
        estimated_duration: float          = None,
        dependencies:       list           = None,
        priority_level:     PriorityLevel  = PriorityLevel.MEDIUM,
    ):
        # --- Identity ---
        self.task_id    = task_id
        self.name       = name

        # --- Priority ---
        self.base_priority  = priority   # anchor; never drifts with boosts
        self.priority       = priority   # heap sorts on this
        self.priority_level = priority_level

        # --- Scheduling ---
        self.deadline           = deadline
        self.estimated_duration = estimated_duration   # hours; None → 1.0 in DAG
        self.dependencies       = list(dependencies) if dependencies else []

        # --- Assignment ---
        self.department = department
        self.assigned_to = assigned_to

        # --- Status & timing ---
        self.status       = Status.PENDING
        self.created_at   = datetime.now()
        self.started_at   = None
        self.completed_at = None

        # --- Anti-starvation ---
        self.wait_time = 0.0   # hours spent READY; updated by scheduler

        # --- Computed on completion ---
        self.delay = None      # hours past deadline; 0.0 if on time

        # --- Heap bookkeeping ---
        self.heap_index: int | None = None   # set/cleared by MinHeap

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def mark_ready(self) -> None:
        """Dependencies satisfied — task enters the heap."""
        self.status = Status.READY

    def mark_in_progress(self) -> None:
        """Extracted from heap and handed to a worker."""
        self.status     = Status.IN_PROGRESS
        self.started_at = datetime.now()

    def mark_done(self) -> None:
        """Task finished successfully. Delay is computed here."""
        self.status       = Status.DONE
        self.completed_at = datetime.now()
        self._compute_delay()

    def mark_cancelled(self) -> None:
        """Killed via admin API at any lifecycle stage."""
        self.status       = Status.CANCELLED
        self.completed_at = datetime.now()

    # ------------------------------------------------------------------
    # Delay computation
    # ------------------------------------------------------------------

    def _compute_delay(self) -> None:
        """
        If the task finished after its deadline, delay = hours overdue.
        If on time, delay = 0.0.
        Only meaningful for DONE tasks.
        """
        if self.completed_at and self.deadline:
            diff       = self.completed_at - self.deadline
            self.delay = max(0.0, diff.total_seconds() / 3600)
        else:
            self.delay = None

    def is_overdue(self) -> bool:
        """True if the deadline has passed and the task is still active."""
        if self.status in (Status.DONE, Status.CANCELLED):
            return False
        return datetime.now() > self.deadline

    # ------------------------------------------------------------------
    # Anti-starvation support
    # ------------------------------------------------------------------

    def update_wait_time(self) -> None:
        """
        Refresh wait_time to the number of hours this task has been READY.
        Called periodically by the scheduler's refresh_wait_times() pass.
        Only READY tasks accrue wait time — tasks in other states are skipped.
        """
        if self.status == Status.READY:
            elapsed    = datetime.now() - self.created_at
            self.wait_time = elapsed.total_seconds() / 3600

    def effective_priority(self, starvation_weight: float = 0.1) -> float:
        """
        The value MinHeap._compare() uses for ordering.

            effective = priority + starvation_weight * wait_time

        With the default weight of 0.1, a task must wait 10 hours to gain
        1 unit of effective priority — enough to prevent starvation without
        disrupting normal priority ordering.

        Args:
            starvation_weight: multiplier applied to wait_time.
                               Tune upward to age tasks faster.
        Returns:
            float — higher means extracted sooner.
        """
        return self.priority + starvation_weight * self.wait_time

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Task(id={self.task_id!r}, name={self.name!r}, "
            f"priority={self.priority}, base={self.base_priority}, "
            f"status={self.status.value}, "
            f"dept={self.department!r}, "
            f"deadline={self.deadline.strftime('%Y-%m-%d')})"
        )