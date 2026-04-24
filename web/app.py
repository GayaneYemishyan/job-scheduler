from __future__ import annotations

import json
import os
import sys
from urllib import error, request as urllib_request
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, flash, redirect, render_template, request, session, url_for

from api.scheduler import Scheduler
from core.models import Status, Task
from web.storage import build_store


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY",
        "replace-this-secret-before-production",
    )
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)

    store = build_store()
    firebase_api_key = os.getenv("FIREBASE_API_KEY", "").strip()

    def firebase_auth_enabled() -> bool:
        return bool(firebase_api_key)

    def firebase_request(endpoint: str, payload: dict) -> dict:
        if not firebase_api_key:
            raise RuntimeError(
                "Missing FIREBASE_API_KEY. Configure it to enable Firebase Auth."
            )
        url = (
            f"https://identitytoolkit.googleapis.com/v1/{endpoint}"
            f"?key={firebase_api_key}"
        )
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8")
            try:
                parsed = json.loads(details)
                message = parsed.get("error", {}).get("message", "Authentication failed.")
            except Exception:
                message = "Authentication failed."
            raise ValueError(message) from exc

    def firebase_sign_up(email: str, password: str, full_name: str) -> dict:
        data = firebase_request(
            "accounts:signUp",
            {"email": email, "password": password, "returnSecureToken": True},
        )
        id_token = data.get("idToken")
        if id_token:
            firebase_request(
                "accounts:update",
                {"idToken": id_token, "displayName": full_name, "returnSecureToken": False},
            )
        return data

    def firebase_sign_in(email: str, password: str) -> dict:
        return firebase_request(
            "accounts:signInWithPassword",
            {"email": email, "password": password, "returnSecureToken": True},
        )

    def login_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("signin"))
            return fn(*args, **kwargs)
        return wrapper

    def replay_scheduler(user_id: str) -> tuple[Scheduler, int, str | None]:
        scheduler = Scheduler()
        counter = 0
        running_task_id = None

        events = store.list_events(user_id)
        for event in events:
            etype = event.get("type")
            data = event.get("data", {})

            if etype == "submit":
                payload = data["task"]
                deadline = datetime.fromisoformat(payload["deadline"])
                task = Task(
                    task_id=payload["task_id"],
                    name=payload["name"],
                    priority=int(payload["priority"]),
                    deadline=deadline,
                    department=payload["department"],
                    estimated_duration=float(payload["estimated_duration"]),
                    dependencies=payload.get("dependencies", []),
                )
                scheduler.submit(task)
                counter = max(counter, int(payload["task_id"].replace("T", "")))

            elif etype == "start_next":
                task = scheduler.next_task()
                if task:
                    running_task_id = task.task_id

            elif etype == "complete":
                task_id = data.get("task_id")
                if task_id:
                    try:
                        scheduler.complete_task(task_id)
                    except Exception:
                        continue

            elif etype == "cancel":
                task_id = data.get("task_id")
                if task_id:
                    try:
                        scheduler.kill_task(task_id)
                    except Exception:
                        continue

            elif etype == "update":
                task_id = data.get("task_id")
                payload = data.get("updates", {})
                if task_id and task_id in scheduler.dag.tasks:
                    if "deadline" in payload:
                        payload["deadline"] = datetime.fromisoformat(payload["deadline"])
                    try:
                        scheduler.update_task(task_id, **payload)
                    except Exception:
                        continue

            elif etype == "rebalance":
                scheduler.refresh_wait_times()

        return scheduler, counter, running_task_id

    def append_event(user_id: str, event_type: str, data: dict) -> None:
        store.append_event(
            user_id,
            {"type": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()},
        )

    def status_label(task: Task) -> str:
        if task.status in (Status.DONE, Status.CANCELLED):
            return task.status.value
        if task.is_overdue():
            return "delayed"
        return task.status.value

    # ── Routes ─────────────────────────────────────────────────────────

    @app.get("/")
    def home():
        return render_template("home.html", user_id=session.get("user_id"))

    # Separate Sign In page
    @app.get("/signin")
    def signin():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        return render_template("signin.html")

    # Separate Sign Up page
    @app.get("/signup")
    def signup():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        return render_template("signup.html")

    # Single POST handler for both modes (forms still POST to /auth)
    @app.route("/auth", methods=["GET", "POST"])
    def auth():
        if request.method == "GET":
            return redirect(url_for("signin"))

        if not firebase_auth_enabled():
            flash("Firebase Auth is not configured. Set FIREBASE_API_KEY first.", "error")
            return redirect(url_for("signin"))

        mode = request.form.get("mode", "signin")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if mode == "signup":
            full_name = request.form.get("full_name", "").strip()
            if len(full_name) < 2:
                flash("Please enter a valid full name.", "error")
                return redirect(url_for("signup"))
            try:
                signup_data = firebase_sign_up(email=email, password=password, full_name=full_name)
                user = store.upsert_user_profile(
                    user_id=signup_data["localId"],
                    email=signup_data.get("email", email),
                    full_name=full_name,
                )
                session["user_id"] = user["id"]
                session.permanent = True
                flash("Account created successfully.", "success")
                return redirect(url_for("dashboard"))
            except (ValueError, RuntimeError) as exc:
                flash(str(exc), "error")
                return redirect(url_for("signup"))

        try:
            signin_data = firebase_sign_in(email=email, password=password)
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")
            return redirect(url_for("signin"))

        user = store.upsert_user_profile(
            user_id=signin_data["localId"],
            email=signin_data.get("email", email),
            full_name=signin_data.get("displayName", "").strip() or "User",
        )
        session["user_id"] = user["id"]
        session.permanent = True
        flash("Welcome back.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        user = store.get_user(session["user_id"])
        scheduler, _, running_task_id = replay_scheduler(session["user_id"])

        tasks = scheduler.dag.all_tasks()
        history = scheduler.history.all_records()
        queue = scheduler.list_queue()
        stats = scheduler.history.completion_rate()
        in_progress = list(scheduler._in_progress.values())
        edges = scheduler.dag.all_edges()

        nodes = [
            {
                "id": task.task_id,
                "label": f"{task.task_id}\\n{task.name[:18]}",
                "title": f"{task.name} | {task.department} | p{task.priority} | {status_label(task)}",
                "group": status_label(task),
            }
            for task in tasks if status_label(task) not in ("cancelled", "pending")
        ]

        # Filter edges to only include those between non-cancelled/non-pending tasks
        visible_task_ids = {n["id"] for n in nodes}
        edges = [
            {"from": u, "to": v} for u, v in edges 
            if u in visible_task_ids and v in visible_task_ids
        ]

        critical_path, critical_duration = [], 0
        if edges:
            try:
                critical_path, critical_duration = scheduler.dag.critical_path()
            except Exception:
                pass

        return render_template(
            "dashboard.html",
            user=user,
            tasks=tasks,
            history=history,
            queue=queue[:5],
            in_progress=in_progress,
            running_task_id=running_task_id,
            stats=stats,
            avg_delay=scheduler.history.average_delay(),
            nodes=nodes,
            edges=edges,
            critical_path=critical_path,
            critical_duration=critical_duration,
            now=datetime.utcnow(),
        )

    @app.post("/tasks/create")
    @login_required
    def create_task():
        scheduler, counter, _ = replay_scheduler(session["user_id"])
        name = request.form.get("name", "").strip()
        department = request.form.get("department")
        custom_dept = request.form.get("custom_department", "").strip()
        
        if department == "Other" and custom_dept:
            department = custom_dept
        elif not department:
            department = "Operations"
            
        priority = int(request.form.get("priority", 2))
        estimated_duration = float(request.form.get("estimated_duration", 1.0))
        deadline_raw = request.form.get("deadline")
        dependencies = request.form.getlist("dependencies")

        if not name:
            flash("Task name is required.", "error")
            return redirect(url_for("dashboard"))

        task_id = f"T{counter + 1:04d}"
        try:
            deadline = datetime.fromisoformat(deadline_raw)
        except Exception:
            flash("Please enter a valid deadline.", "error")
            return redirect(url_for("dashboard"))

        task_payload = {
            "task_id": task_id,
            "name": name,
            "priority": priority,
            "deadline": deadline.isoformat(),
            "department": department,
            "estimated_duration": estimated_duration,
            "dependencies": dependencies,
        }

        try:
            task = Task(
                task_id=task_id, name=name, priority=priority, deadline=deadline,
                department=department, estimated_duration=estimated_duration,
                dependencies=dependencies,
            )
            scheduler.submit(task)
            append_event(session["user_id"], "submit", {"task": task_payload})
            flash(f"Task {task_id} added.", "success")
        except Exception as exc:
            flash(str(exc), "error")

        return redirect(url_for("dashboard"))

    @app.post("/tasks/start-next")
    @login_required
    def start_next():
        scheduler, _, _ = replay_scheduler(session["user_id"])
        task = scheduler.next_task()
        if not task:
            flash("No ready tasks to start.", "error")
            return redirect(url_for("dashboard"))
        append_event(session["user_id"], "start_next", {"task_id": task.task_id})
        flash(f"Started {task.task_id}: {task.name}", "success")
        return redirect(url_for("dashboard"))

    @app.post("/tasks/<task_id>/complete")
    @login_required
    def complete_task(task_id: str):
        scheduler, _, _ = replay_scheduler(session["user_id"])
        try:
            scheduler.complete_task(task_id)
            append_event(session["user_id"], "complete", {"task_id": task_id})
            flash(f"Completed {task_id}.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("dashboard"))

    @app.post("/tasks/<task_id>/cancel")
    @login_required
    def cancel_task(task_id: str):
        scheduler, _, _ = replay_scheduler(session["user_id"])
        try:
            scheduler.kill_task(task_id)
            append_event(session["user_id"], "cancel", {"task_id": task_id})
            flash(f"Cancelled {task_id}.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("dashboard"))

    @app.post("/tasks/rebalance")
    @login_required
    def rebalance():
        scheduler, _, _ = replay_scheduler(session["user_id"])
        scheduler.refresh_wait_times()
        append_event(session["user_id"], "rebalance", {})
        flash("Queue re-balanced.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/tasks/<task_id>/edit")
    @login_required
    def edit_task_page(task_id: str):
        scheduler, _, _ = replay_scheduler(session["user_id"])
        if task_id not in scheduler.dag.tasks:
            flash(f"Task {task_id} not found.", "error")
            return redirect(url_for("dashboard"))
        
        task = scheduler.dag.tasks[task_id]
        if task.status in (Status.DONE, Status.CANCELLED):
            flash(f"Cannot edit a {task.status.value} task.", "error")
            return redirect(url_for("dashboard"))

        return render_template("edit_task.html", task=task)

    @app.post("/tasks/<task_id>/edit")
    @login_required
    def edit_task(task_id: str):
        scheduler, _, _ = replay_scheduler(session["user_id"])
        if task_id not in scheduler.dag.tasks:
            flash(f"Task {task_id} not found.", "error")
            return redirect(url_for("dashboard"))

        name = request.form.get("name", "").strip()
        department = request.form.get("department")
        custom_dept = request.form.get("custom_department", "").strip()
        if department == "Other" and custom_dept:
            department = custom_dept
        
        priority = int(request.form.get("priority", 2))
        estimated_duration = float(request.form.get("estimated_duration", 1.0))
        deadline_raw = request.form.get("deadline")

        try:
            deadline = datetime.fromisoformat(deadline_raw)
        except Exception:
            flash("Invalid deadline date.", "error")
            return redirect(url_for("edit_task_page", task_id=task_id))

        updates = {
            "name": name,
            "department": department,
            "priority": priority,
            "estimated_duration": estimated_duration,
            "deadline": deadline.isoformat()
        }

        try:
            # Replay friendly update
            scheduler.update_task(task_id, **{**updates, "deadline": deadline})
            append_event(session["user_id"], "update", {"task_id": task_id, "updates": updates})
            flash(f"Task {task_id} updated.", "success")
        except Exception as exc:
            flash(str(exc), "error")

        return redirect(url_for("dashboard"))

    return app