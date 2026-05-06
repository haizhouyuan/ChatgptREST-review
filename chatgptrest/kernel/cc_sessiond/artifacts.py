import json
import os
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Any
from datetime import datetime


class ArtifactManager:
    """Manages session artifacts on disk."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(os.environ.get(
            "CC_SESSIOND_ARTIFACTS",
            "/tmp/artifacts/cc_sessions"
        ))

    def get_session_dir(self, session_id: str) -> Path:
        return self.base_dir / session_id

    def _normalize(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if is_dataclass(value):
            return self._normalize(asdict(value))
        if isinstance(value, dict):
            return {str(key): self._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._normalize(item) for item in value]
        if hasattr(value, "model_dump"):
            try:
                return self._normalize(value.model_dump())
            except Exception:
                pass
        if hasattr(value, "__dict__"):
            try:
                return self._normalize(
                    {
                        key: item
                        for key, item in vars(value).items()
                        if not str(key).startswith("_")
                    }
                )
            except Exception:
                pass
        return str(value)

    def write_request(self, session_id: str, prompt: str, options: dict):
        session_dir = self.get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        with open(session_dir / "request.json", "w") as f:
            json.dump(self._normalize({
                "prompt": prompt,
                "options": options,
                "created_at": datetime.now().isoformat(),
            }), f, indent=2)

    def write_status(self, session_id: str, state: str, metadata: dict = None):
        session_dir = self.get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        with open(session_dir / "status.json", "w") as f:
            json.dump(self._normalize({
                "state": state,
                "updated_at": datetime.now().isoformat(),
                "metadata": metadata or {},
            }), f, indent=2)

    def write_result(self, session_id: str, result: dict):
        session_dir = self.get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        with open(session_dir / "result.json", "w") as f:
            json.dump(self._normalize(result), f, indent=2)

    def write_error(self, session_id: str, error: str):
        session_dir = self.get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        with open(session_dir / "error.json", "w") as f:
            json.dump(self._normalize({
                "error": error,
                "timestamp": datetime.now().isoformat(),
            }), f, indent=2)

    def write_backend_meta(self, session_id: str, backend: str, backend_run_id: str, meta: dict = None):
        session_dir = self.get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        with open(session_dir / "backend_meta.json", "w") as f:
            json.dump(self._normalize({
                "backend": backend,
                "backend_run_id": backend_run_id,
                "timestamp": datetime.now().isoformat(),
                "meta": meta or {},
            }), f, indent=2)

    def append_event(self, session_id: str, event: dict):
        session_dir = self.get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        with open(session_dir / "events.jsonl", "a") as f:
            f.write(json.dumps(self._normalize(event)) + "\n")

    def get_request(self, session_id: str) -> Optional[dict]:
        path = self.get_session_dir(session_id) / "request.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def get_status(self, session_id: str) -> Optional[dict]:
        path = self.get_session_dir(session_id) / "status.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def get_result(self, session_id: str) -> Optional[dict]:
        path = self.get_session_dir(session_id) / "result.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def get_error(self, session_id: str) -> Optional[dict]:
        path = self.get_session_dir(session_id) / "error.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def get_events(self, session_id: str) -> list[dict]:
        path = self.get_session_dir(session_id) / "events.jsonl"
        events = []
        if path.exists():
            with open(path) as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        return events
