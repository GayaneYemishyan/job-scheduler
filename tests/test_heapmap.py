# tests/test_heapmap.py

from datetime import datetime, timedelta
from core.models import Task, PriorityLevel, Status
from core.heap import HeapMap


def make_task(task_id, name, priority):
    return Task(
        task_id=task_id,
        name=name,
        priority=priority,
        deadline=datetime.now() + timedelta(days=7),
        department="Engineering",
        priority_level=PriorityLevel.MEDIUM,
    )


hm = HeapMap()

t1 = make_task("t1", "Render Video",  priority=5)
t2 = make_task("t2", "Send Email",    priority=1)
t3 = make_task("t3", "Backup DB",     priority=3)
t4 = make_task("t4", "Health Check",  priority=2)
t5 = make_task("t5", "Deploy Hotfix", priority=8)

hm.push(t1)
hm.push(t2)
hm.push(t3)
hm.push(t4)
hm.push(t5)

print("=== Initial top ===")
print("Peek:", hm.peek())                     # t5, priority 8

print("\n=== update_priority: boost t2 (1→10) ===")
hm.update_priority("t2", new_priority=10)
print("Peek:", hm.peek())                     # t2 should now be on top

print("\n=== update_priority: demote t2 (10→1) ===")
hm.update_priority("t2", new_priority=1)
print("Peek:", hm.peek())                     # t5 back on top

print("\n=== cancel_task t3 ===")
cancelled = hm.cancel_task("t3")
print("Cancelled:", cancelled)                # t3, status=cancelled
print("Try get t3:", hm.get_task("t3"))       # None — removed from map

print("\n=== Extract all remaining (should be priority order) ===")
while not hm.is_empty():
    print("Pop:", hm.pop())                   # t5(8), t1(5), t4(2), t2(1)