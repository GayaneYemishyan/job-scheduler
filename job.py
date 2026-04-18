# job.py

class Job:
    def __init__(self, job_id, name, priority, deadline=None):
        self.job_id   = job_id        # unique string ID, e.g. "job_42"
        self.name     = name          # human-readable name
        self.priority = priority      # int: LOWER number = HIGHER priority (min-heap logic)
        self.deadline = deadline      # optional: unix timestamp or int
        self.enqueue_time = None      # set when inserted into the heap (for anti-starvation later)
        self.heap_index = None        # CRITICAL: tracks position inside heap array (for update_priority)
        self.status   = "PENDING"     # PENDING | RUNNING | DONE | KILLED

    def __repr__(self):
        return f"Job(id={self.job_id}, name={self.name}, priority={self.priority}, status={self.status})"