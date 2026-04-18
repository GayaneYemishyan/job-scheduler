# test_heap.py
from core.models import Job
from core.heap import MinHeap

heap = MinHeap()

j1 = Job("j1", "Render Video",   priority=5)
j2 = Job("j2", "Send Email",     priority=1)
j3 = Job("j3", "Backup DB",      priority=3)
j4 = Job("j4", "Health Check",   priority=2)

heap.insert(j1)
heap.insert(j2)
heap.insert(j3)
heap.insert(j4)

print("Peek:", heap.peek())             # should be j2 (priority 1)
print("Extract:", heap.extract_min())   # should be j2
print("Extract:", heap.extract_min())   # should be j4 (priority 2)
print("Extract:", heap.extract_min())   # should be j3 (priority 3)
print("Extract:", heap.extract_min())   # should be j1 (priority 5)