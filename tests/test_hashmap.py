# tests/test_hashmap.py

from core.hash_map import HashMap
from datetime import datetime, timedelta
from core.models import Task, PriorityLevel


def make_task(task_id, name, priority):
    return Task(
        task_id=task_id,
        name=name,
        priority=priority,
        deadline=datetime.now() + timedelta(days=7),
        department="Engineering",
        priority_level=PriorityLevel.MEDIUM,
    )


hmap = HashMap()

t1 = make_task("t1", "Render Video",  priority=5)
t2 = make_task("t2", "Send Email",    priority=1)
t3 = make_task("t3", "Backup DB",     priority=3)

# --- put & get ---
hmap.put("t1", t1)
hmap.put("t2", t2)
hmap.put("t3", t3)

print("Get t1:", hmap.get("t1"))           # Task t1
print("Get t2:", hmap.get("t2"))           # Task t2
print("Has t3:", hmap.has("t3"))           # True
print("Has t99:", hmap.has("t99"))         # False

# --- update ---
hmap.put("t1", "updated_value")
print("Updated t1:", hmap.get("t1"))       # updated_value

# --- delete ---
hmap.delete("t2")
print("After delete, get t2:", hmap.get("t2"))   # None
print("Has t2:", hmap.has("t2"))                  # False

# --- tombstone safety check ---
# t3 was inserted after t2, so if tombstone breaks probing, t3 disappears
print("t3 still there:", hmap.get("t3"))   # Task t3  ← this is the important one