from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any


class AgentSessionStore:
    """File-backed persistence for public agent facade sessions and SSE events."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @classmethod
    def from_env(cls) -> "AgentSessionStore":
        raw = str(os.environ.get("CHATGPTREST_AGENT_SESSION_DIR", "")).strip()
        if raw:
            return cls(Path(raw).expanduser().resolve())

        db_path = str(os.environ.get("CHATGPTREST_DB_PATH", "")).strip()
        if db_path:
            return cls(Path(db_path).expanduser().resolve().parent / "agent_sessions")

        if os.environ.get("PYTEST_CURRENT_TEST"):
            return cls(Path(tempfile.mkdtemp(prefix="agent-session-store-")))

        return cls(Path("/tmp/chatgptrest-agent-sessions"))

    def _session_path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def _events_path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.events.jsonl"

    def get(self, session_id: str) -> dict[str, Any] | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        with self._lock:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None

    def put(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._session_path(session_id)
        tmp_path = path.with_suffix(".tmp")
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock:
            tmp_path.write_text(data, encoding="utf-8")
            tmp_path.replace(path)
        return dict(payload)

    def latest_event_seq(self, session_id: str) -> int:
        events_path = self._events_path(session_id)
        if not events_path.exists():
            return 0
        latest = 0
        with self._lock:
            with events_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except Exception:
                        continue
                    latest = max(latest, int(event.get("seq") or 0))
        return latest

    def append_event(self, session_id: str, event: dict[str, Any]) -> dict[str, Any]:
        events_path = self._events_path(session_id)
        payload = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with events_path.open("a", encoding="utf-8") as fh:
                fh.write(payload)
                fh.write("\n")
        return dict(event)

    def events_after(self, session_id: str, after_seq: int) -> list[dict[str, Any]]:
        events_path = self._events_path(session_id)
        if not events_path.exists():
            return []
        results: list[dict[str, Any]] = []
        with self._lock:
            with events_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except Exception:
                        continue
                    if int(event.get("seq") or 0) > after_seq:
                        results.append(event)
        return results

    def count_sessions(self) -> int:
        return sum(
            1
            for path in self.base_dir.glob("*.json")
            if not path.name.endswith(".events.json")
        )
