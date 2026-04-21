import time
from datetime import datetime
from enum import Enum


class Status(Enum):
    PENDING = "pending"  # created but dependencies not met yet
    READY = "ready"  # dependencies done, waiting in queue
    IN_PROGRESS = "in_progress"  # currently being worked on
    DONE = "done"  # completed successfully
    DELAYED = "delayed"  # past deadline, still not done
    CANCELLED = "cancelled"  # killed via admin API


class PriorityLevel(Enum):
    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1


class Task:
    def __init__(
            self,
            task_id: str,
            name: str,
            priority: int,  # numeric 1–10, used by the heap
            deadline: datetime,  # hard deadline as a date
            department: str,  # e.g. "Engineering", "HR"
            assigned_to: str = None,  # person within the department
            estimated_duration: float = None,  # expected hours to complete
            dependencies: list = None,  # list of task_ids that must finish first
            priority_level: PriorityLevel = PriorityLevel.MEDIUM,  # human-readable label
    ):
        # --- Identity ---
        self.task_id = task_id
        self.name = name

        # --- Priority ---]
        self.base_priority = priority
        self.priority = priority  # used directly by the heap
        self.priority_level = priority_level  # label for display

        # --- Scheduling ---
        self.deadline = deadline
        self.estimated_duration = estimated_duration  # in hours
        self.dependencies = dependencies if dependencies else []

        # --- Assignment ---
        self.department = department
        self.assigned_to = assigned_to

        # --- Status & Timing ---
        self.status = Status.PENDING
        self.created_at = datetime.now()  # when task was submitted
        self.started_at = None  # set when status → IN_PROGRESS
        self.completed_at = None  # set when status → DONE

        # --- Computed fields ---
        self.wait_time = 0.0  # updated by anti-starvation logic
        self.delay = None  # computed on completion (see below)

    # -----------------------------------------------------------------
    # Status transitions — clean controlled updates
    # -----------------------------------------------------------------

    def mark_ready(self):
        """Dependencies satisfied, task enters the queue."""
        self.status = Status.READY

    def mark_in_progress(self):
        """Task extracted from heap and started."""
        self.status = Status.IN_PROGRESS
        self.started_at = datetime.now()

    def mark_done(self):
        """Task completed. Compute delay if past deadline."""
        self.status = Status.DONE
        self.completed_at = datetime.now()
        self._compute_delay()

    def mark_cancelled(self):
        """Task killed via admin API."""
        self.status = Status.CANCELLED
        self.completed_at = datetime.now()

    # -----------------------------------------------------------------
    # Delay computation
    # -----------------------------------------------------------------

    def _compute_delay(self):
        """
        If completed after deadline, delay = how many hours late.
        If completed on time, delay = 0.
        """
        if self.completed_at and self.deadline:
            diff = self.completed_at - self.deadline
            self.delay = max(0.0, diff.total_seconds() / 3600)  # in hours
        else:
            self.delay = None

    def is_overdue(self) -> bool:
        """Check right now whether the task has passed its deadline."""
        if self.status in (Status.DONE, Status.CANCELLED):
            return False
        return datetime.now() > self.deadline

    # -----------------------------------------------------------------
    # Anti-starvation support
    # -----------------------------------------------------------------

    def update_wait_time(self):
        """Called periodically by the scheduler to age the task."""
        if self.status == Status.READY:
            self.wait_time = (datetime.now() - self.created_at).total_seconds() / 3600

    def effective_priority(self, starvation_weight: float = 0.1) -> float:
        """
        The value the heap actually sorts by.
        Combines raw priority with time waited to prevent starvation.

        effective = priority + (starvation_weight * wait_time)
        """
        return self.priority + (starvation_weight * self.wait_time)

    # -----------------------------------------------------------------
    # Display
    # -----------------------------------------------------------------

    def __repr__(self):
        return (
            f"Task(id={self.task_id!r}, name={self.name!r}, "
            f"priority={self.priority}, base={self.base_priority}, "
            f"status={self.status.value}, "
            f"dept={self.department!r}, deadline={self.deadline.strftime('%Y-%m-%d')})"
        )
    








