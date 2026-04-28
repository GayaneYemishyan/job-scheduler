# FlowDesk — Priority-Driven Task Scheduler

FlowDesk is a web-based task scheduling system built from scratch using custom data structures and algorithms. It enforces task dependencies, ranks work by priority and deadline pressure, highlights the critical path, and prevents low-priority tasks from being starved indefinitely.

---

## What it does

- **Dependency enforcement** — tasks cannot start until all their prerequisites are complete
- **Priority queue** — the next task to work on is always the highest effective-priority one that is ready
- **Critical path detection** — the longest chain of dependent tasks is computed and highlighted; tasks on it receive a priority boost
- **Anti-starvation** — tasks that wait too long gradually gain effective priority so nothing is ignored forever
- **Execution history** — every completed or cancelled task is recorded with delay metrics
- **Live dependency graph** — an interactive SVG graph shows the current state of all tasks and edges

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Flask |
| Frontend | Jinja2, vanilla JS, custom SVG |
| Auth | Firebase Auth (optional) |
| Persistence | Local JSON event log / Firestore |
| Testing | pytest |

All core data structures and algorithms are implemented from scratch — no third-party collections or graph libraries.

---

## Data structures (all hand-built)

| Structure | Location | Purpose |
|---|---|---|
| Directed Acyclic Graph | `core/graph.py` | Dependency tracking and readiness detection |
| Binary Max-Heap + HeapMap | `core/heap.py` | Ready-task priority queue |
| Open-addressing Hash Map | `core/hash_map.py` | O(1) task lookup inside the heap |
| Doubly Linked List | `core/history.py` | Ordered execution history with O(1) eviction |

## Algorithms

| Algorithm | Location | Complexity |
|---|---|---|
| Kahn's topological sort | `core/graph.py` | O(V + E) |
| DFS cycle detection | `core/graph.py` | O(V + E) |
| Critical path (longest path) | `core/graph.py` | O(V + E) |
| Heapify up / down | `core/heap.py` | O(log n) |
| Anti-starvation refresh | `core/heap.py` | O(n) Floyd rebuild |

---

## Project structure

```
.
├── core/
│   ├── models.py        # Task model, Status enum
│   ├── graph.py         # DAG — topo sort, cycle detection, critical path
│   ├── heap.py          # MinHeap, HeapMap
│   ├── hash_map.py      # Open-addressing hash map
│   └── history.py       # Doubly linked list history log
├── api/
│   └── scheduler.py     # Orchestrator — wires all core components
├── web/
│   ├── app.py           # Flask routes and event sourcing
│   ├── storage.py       # LocalJSONStore / FirebaseStore
│   ├── templates/       # Jinja2 HTML templates
│   └── static/          # CSS and dashboard JS
├── visualisation/
│   └── graph_view.py    # Matplotlib graph renderer (offline demo)
├── tests/               # pytest test suite
├── main.py              # Entry point
└── requirements.txt
```

---

## Getting started

### 1. Clone and install

```bash
git clone https://github.com/your-org/flowdesk.git
cd flowdesk
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key

# Optional — leave blank to run without login
FIREBASE_API_KEY=
FIREBASE_CREDENTIALS=
```

### 3. Run

```bash
python main.py
```

### 4. Run tests

```bash
pytest tests/
```

---

## Authentication

Firebase Auth is optional. If `FIREBASE_API_KEY` is not set, the app runs in local mode and skips login. To enable auth, create a Firebase project, enable email/password sign-in, and add the Web API key to `.env`.

For Firestore persistence, also add a service account key:

```env
FIREBASE_CREDENTIALS=path/to/serviceAccountKey.json
SCHEDULER_STORE=firebase
```

---

## How the scheduler works

1. A task is submitted with a name, department, priority (1–4), deadline, estimated duration, and optional dependencies.
2. The scheduler adds the task to the DAG and wires dependency edges. A cycle check rejects any submission that would create a circular dependency.
3. Tasks with no unmet dependencies are marked READY and pushed onto the max-heap.
4. The critical path is recomputed. Tasks on it receive a `CRITICAL_PATH_BOOST` on top of their base priority.
5. Calling **Start Next** extracts the highest effective-priority task and marks it IN_PROGRESS.
6. Completing a task decrements the in-degree of its successors; any that reach zero are immediately enqueued.
7. **Re-balance** updates wait times for all queued tasks and rebuilds the heap so long-waiting low-priority tasks bubble up.

---

## Authors

| Name | Contributions |
|---|---|
| **Monika Yepremyan** | Binary heap, HeapMap, open-addressing hash map, anti-starvation formula, priority update with rebalance, unit tests |
| **Gayane Yemishyan** | DAG, doubly linked list, topological sort, cycle detection, critical path algorithm, admin API, visualisation, integration tests |
