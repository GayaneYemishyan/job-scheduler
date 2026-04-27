"""
JSON API routes for the React frontend.
Add these routes to your Flask app by importing and calling register_api_routes(app).
"""

from flask import jsonify, session, request
from datetime import datetime
from core.models import Status


def status_label(task):
    if task.status in (Status.DONE, Status.CANCELLED):
        return task.status.value
    if task.is_overdue():
        return "delayed"
    return task.status.value


def task_to_dict(task):
    """Convert a Task object to a JSON-serializable dict."""
    return {
        "task_id": task.task_id,
        "name": task.name,
        "priority": task.priority,
        "base_priority": task.base_priority,
        "priority_level": task.priority_level.value if task.priority_level else 2,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "department": task.department,
        "assigned_to": task.assigned_to,
        "estimated_duration": task.estimated_duration,
        "dependencies": list(task.dependencies) if task.dependencies else [],
        "description": task.description,
        "status": status_label(task),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "wait_time": task.wait_time,
        "delay": task.delay,
        "heap_index": task.heap_index,
        "effective_priority": task.effective_priority(),
    }


def register_api_routes(app, store, replay_scheduler, login_required, append_event):
    """Register JSON API routes for the React frontend."""

    @app.get("/api/me")
    def api_me():
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        user = store.get_user(session["user_id"])
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name", "User"),
        })

    @app.get("/dashboard-data")
    @login_required
    def dashboard_data():
        user = store.get_user(session["user_id"])
        scheduler, counter, running_task_id = replay_scheduler(session["user_id"])

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
            for task in tasks if status_label(task) not in ("cancelled",)
        ]

        visible_task_ids = {n["id"] for n in nodes}
        edges_filtered = [
            {"from": u, "to": v} for u, v in edges
            if u in visible_task_ids and v in visible_task_ids
        ]

        critical_path, critical_duration = [], 0
        if edges_filtered:
            try:
                critical_path, critical_duration = scheduler.dag.critical_path()
            except Exception:
                pass

        return jsonify({
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user.get("full_name", "User"),
            },
            "tasks": [task_to_dict(t) for t in tasks],
            "history": [task_to_dict(t) for t in history],
            "queue": [task_to_dict(t) for t in queue],
            "in_progress": [task_to_dict(t) for t in in_progress],
            "running_task_id": running_task_id,
            "stats": stats,
            "avg_delay": scheduler.history.average_delay(),
            "nodes": nodes,
            "edges": edges_filtered,
            "critical_path": critical_path,
            "critical_duration": critical_duration,
            "now": datetime.utcnow().isoformat(),
        })

    @app.post("/auth")
    def api_auth():
        """Handle both sign-in and sign-up via JSON/form data."""
        import os
        from urllib import error, request as urllib_request
        import json as json_mod

        firebase_api_key = os.getenv("FIREBASE_API_KEY", "").strip()

        if not firebase_api_key:
            return jsonify({"error": "Firebase Auth is not configured"}), 400

        mode = request.form.get("mode", "signin")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        def firebase_request(endpoint, payload):
            url = (
                f"https://identitytoolkit.googleapis.com/v1/{endpoint}"
                f"?key={firebase_api_key}"
            )
            body = json_mod.dumps(payload).encode("utf-8")
            req = urllib_request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib_request.urlopen(req, timeout=15) as response:
                    return json_mod.loads(response.read().decode("utf-8"))
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8")
                try:
                    parsed = json_mod.loads(details)
                    message = parsed.get("error", {}).get("message", "Authentication failed.")
                except Exception:
                    message = "Authentication failed."
                raise ValueError(message)

        if mode == "signup":
            full_name = request.form.get("full_name", "").strip()
            if len(full_name) < 2:
                return jsonify({"error": "Please enter a valid full name."}), 400
            try:
                signup_data = firebase_request(
                    "accounts:signUp",
                    {"email": email, "password": password, "returnSecureToken": True},
                )
                id_token = signup_data.get("idToken")
                if id_token:
                    firebase_request(
                        "accounts:update",
                        {"idToken": id_token, "displayName": full_name, "returnSecureToken": False},
                    )
                user = store.upsert_user_profile(
                    user_id=signup_data["localId"],
                    email=signup_data.get("email", email),
                    full_name=full_name,
                )
                session["user_id"] = user["id"]
                session.permanent = True
                return jsonify({
                    "id": user["id"],
                    "email": user["email"],
                    "full_name": user.get("full_name", ""),
                })
            except (ValueError, RuntimeError) as exc:
                return jsonify({"error": str(exc)}), 400

        try:
            signin_data = firebase_request(
                "accounts:signInWithPassword",
                {"email": email, "password": password, "returnSecureToken": True},
            )
        except (ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 400

        user = store.upsert_user_profile(
            user_id=signin_data["localId"],
            email=signin_data.get("email", email),
            full_name=signin_data.get("displayName", "").strip() or "User",
        )
        session["user_id"] = user["id"]
        session.permanent = True
        return jsonify({
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name", ""),
        })
