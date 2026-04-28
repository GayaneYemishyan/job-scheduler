import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


class LocalJSONStore:
    """Simple local persistence for users and scheduler events."""

    def __init__(self, file_path: str | None = None):
        default_path = os.getenv("STORE_PATH") or str(
        Path(__file__).resolve().parent.parent / "data" / "store.json"
        )
        self.file_path = Path(file_path) if file_path else Path(default_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self.file_path.exists():
            self._save({"users": {}, "events": {}})

    def _load(self) -> dict[str, Any]:
        with self.file_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, payload: dict[str, Any]) -> None:
        with self.file_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def upsert_user_profile(
        self,
        user_id: str,
        email: str,
        full_name: str,
    ) -> dict[str, str]:
        with self._lock:
            payload = self._load()
            existing = payload["users"].get(user_id)
            created_at = (
                existing.get("created_at")
                if existing
                else datetime.utcnow().isoformat()
            )
            profile = {
                "id": user_id,
                "email": email,
                "full_name": full_name,
                "created_at": created_at,
                "updated_at": datetime.utcnow().isoformat(),
            }
            payload["users"][user_id] = profile
            if user_id not in payload["events"]:
                payload["events"][user_id] = []
            self._save(payload)
            return profile

    def get_user(self, user_id: str) -> dict[str, str] | None:
        payload = self._load()
        return payload["users"].get(user_id)

    def append_event(self, user_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            payload = self._load()
            if user_id not in payload["events"]:
                payload["events"][user_id] = []
            payload["events"][user_id].append(event)
            self._save(payload)

    def list_events(self, user_id: str) -> list[dict[str, Any]]:
        payload = self._load()
        return payload["events"].get(user_id, [])


class FirebaseStore:
    """Firestore-backed persistence. Falls back to LocalJSONStore when unavailable."""

    def __init__(self):
        try:
            import firebase_admin  # type: ignore[import-not-found]
            from firebase_admin import credentials, firestore  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError("firebase-admin is not installed.") from exc

        credentials_path = os.getenv("FIREBASE_CREDENTIALS")
        if not credentials_path:
            raise RuntimeError("FIREBASE_CREDENTIALS is not set.")

        if not firebase_admin._apps:
            cred = credentials.Certificate(credentials_path)
            firebase_admin.initialize_app(cred)

        self.db = firestore.client()
        self.users_collection = self.db.collection("users")

    def upsert_user_profile(
        self,
        user_id: str,
        email: str,
        full_name: str,
    ) -> dict[str, str]:
        doc_ref = self.users_collection.document(user_id)
        snapshot = doc_ref.get()
        existing = snapshot.to_dict() if snapshot.exists else None
        profile = {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "created_at": (
                existing.get("created_at")
                if existing
                else datetime.utcnow().isoformat()
            ),
            "updated_at": datetime.utcnow().isoformat(),
        }
        doc_ref.set(profile)
        return profile

    def get_user(self, user_id: str) -> dict[str, str] | None:
        doc = self.users_collection.document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def append_event(self, user_id: str, event: dict[str, Any]) -> None:
        self.users_collection.document(user_id).collection("events").document().set(event)

    def list_events(self, user_id: str) -> list[dict[str, Any]]:
        events_ref = self.users_collection.document(user_id).collection("events")
        docs = events_ref.order_by("timestamp").stream()
        return [doc.to_dict() for doc in docs]


def build_store() -> LocalJSONStore | FirebaseStore:
    preferred = os.getenv("SCHEDULER_STORE", "local").lower()
    if preferred == "firebase":
        try:
            return FirebaseStore()
        except Exception:
            return LocalJSONStore()
    return LocalJSONStore()
