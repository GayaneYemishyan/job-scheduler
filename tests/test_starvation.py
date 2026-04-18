# tests/test_starvation.py

from datetime import datetime, timedelta
from core.models import Task, PriorityLevel
from core.heap import HeapMap


def make_task(task_id, name, priority, hours_waiting=0):
    """
    Create a task and backdating created_at to simulate wait time.
    hours_waiting=5 means this task has been sitting in queue 5 hours.
    """
    t = Task(
        task_id=task_id,
        name=name,
        priority=priority,
        deadline=datetime.now() + timedelta(days=7),
        department="Engineering",
        priority_level=PriorityLevel.MEDIUM,
    )
    # backdate created_at to simulate the task having waited
    t.created_at = datetime.now() - timedelta(hours=hours_waiting)
    t.mark_ready()  # must be READY for update_wait_time to count
    return t


hm = HeapMap()

# High priority task — just arrived
t_new = make_task("t_new", "New Critical Job",  priority=9, hours_waiting=0)

# Low priority task — has been waiting 30 hours
t_old = make_task("t_old", "Old Boring Job",    priority=1, hours_waiting=30)

# Medium priority task — waiting 10 hours
t_mid = make_task("t_mid", "Medium Task",       priority=4, hours_waiting=10)

hm.push(t_new)
hm.push(t_old)
hm.push(t_mid)

print("=== BEFORE refresh (raw priority order) ===")
print(f"t_new  effective_priority: {t_new.effective_priority():.2f}  (raw={t_new.priority})")
print(f"t_mid  effective_priority: {t_mid.effective_priority():.2f}  (raw={t_mid.priority})")
print(f"t_old  effective_priority: {t_old.effective_priority():.2f}  (raw={t_old.priority})")
print(f"Top of heap: {hm.peek().task_id}")   # should be t_new (priority 9)

print("\n=== AFTER refresh_priorities (starvation kicks in) ===")
hm.refresh_priorities()

print(f"t_new  effective_priority: {t_new.effective_priority():.2f}")
print(f"t_mid  effective_priority: {t_mid.effective_priority():.2f}")
print(f"t_old  effective_priority: {t_old.effective_priority():.2f}")
print(f"Top of heap: {hm.peek().task_id}")   # should now be t_old (1 + 0.1*30 = 4.0... let's see)

print("\n=== Extraction order after anti-starvation ===")
while not hm.is_empty():
    task = hm.pop()
    print(f"  Popped: {task.task_id} | raw_priority={task.priority} | effective={task.effective_priority():.2f}")


    print("\n=== Extreme wait: what if t_old waited 100 hours? ===")
t_old.created_at = datetime.now() - timedelta(hours=100)
hm2 = HeapMap()
hm2.push(make_task("t_new2", "New Critical Job", priority=9, hours_waiting=0))
t_starved = make_task("t_starved", "Starved Job", priority=1, hours_waiting=100)
hm2.push(t_starved)
hm2.refresh_priorities()
print(f"t_new2   effective: 9.00")
print(f"t_starved effective: {t_starved.effective_priority():.2f}")  # 1 + 0.1*100 = 11.0
print(f"Top of heap: {hm2.peek().task_id}")  # t_starved wins!