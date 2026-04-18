# tests/test_heap.py

from datetime import datetime, timedelta
from core.models import Task, PriorityLevel, Status
from core.heap import MinHeap


def make_task(task_id, name, priority):
    """Helper to quickly create a Task with a deadline 7 days from now."""
    return Task(
        task_id=task_id,
        name=name,
        priority=priority,
        deadline=datetime.now() + timedelta(days=7),
        department="Engineering",
        priority_level=PriorityLevel.MEDIUM,
    )


heap = MinHeap()

t1 = make_task("t1", "Render Video",  priority=5)
t2 = make_task("t2", "Send Email",    priority=1)
t3 = make_task("t3", "Backup DB",     priority=3)
t4 = make_task("t4", "Health Check",  priority=2)
t5 = make_task("t5", "Deploy Hotfix", priority=10)

heap.insert(t1)
heap.insert(t2)
heap.insert(t3)
heap.insert(t4)
heap.insert(t5)

print("Peek:", heap.peek())              # should be t5 (priority 10)
print("Extract:", heap.extract_max())    # t5
print("Extract:", heap.extract_max())    # t1 (priority 5)
print("Extract:", heap.extract_max())    # t3 (priority 3)
print("Extract:", heap.extract_max())    # t4 (priority 2)
print("Extract:", heap.extract_max())    # t2 (priority 1)