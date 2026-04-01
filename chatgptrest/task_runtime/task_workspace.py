"""Task Workspace - File-based task artifacts and handoff protocol.

This module manages the filesystem layout for task execution artifacts.
Files serve as handoff anchors and audit trails, but the database remains
the source of truth for state machine transitions.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from chatgptrest.core.config import load_config


def get_tasks_root() -> Path:
    """Get the root directory for all task workspaces."""
    config = load_config()
    # Store task workspaces under the configured artifacts root so runtime
    # residue stays out of the repository root and inherits artifact hygiene.
    root = config.artifacts_dir / "tasks"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_task_workspace(task_id: str) -> Path:
    """Get the workspace directory for a specific task."""
    workspace = get_tasks_root() / task_id
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


class TaskWorkspace:
    """Manages task workspace filesystem layout."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.root = get_task_workspace(task_id)

    def initialize(self) -> None:
        """Initialize workspace directory structure."""
        (self.root / "chunks").mkdir(exist_ok=True)
        (self.root / "outcomes").mkdir(exist_ok=True)
        (self.root / "artifacts").mkdir(exist_ok=True)
        (self.root / "reviews").mkdir(exist_ok=True)
        (self.root / "logs").mkdir(exist_ok=True)

    def write_task_request(self, content: str) -> Path:
        """Write TASK_REQUEST.md."""
        path = self.root / "TASK_REQUEST.md"
        path.write_text(content, encoding="utf-8")
        return path

    def write_task_context_lock(self, context: dict[str, Any]) -> Path:
        """Write TASK_CONTEXT.lock.json."""
        path = self.root / "TASK_CONTEXT.lock.json"
        path.write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def write_task_spec(self, spec: dict[str, Any]) -> Path:
        """Write TASK_SPEC.yaml."""
        import yaml
        path = self.root / "TASK_SPEC.yaml"
        path.write_text(yaml.dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def write_execution_plan(self, plan: str) -> Path:
        """Write EXECUTION_PLAN.md."""
        path = self.root / "EXECUTION_PLAN.md"
        path.write_text(plan, encoding="utf-8")
        return path

    def write_acceptance_checks(self, checks: dict[str, Any]) -> Path:
        """Write ACCEPTANCE_CHECKS.json."""
        path = self.root / "ACCEPTANCE_CHECKS.json"
        path.write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def write_state_snapshot(self, state: dict[str, Any]) -> Path:
        """Write TASK_STATE.snapshot.json (audit mirror, not truth source)."""
        path = self.root / "TASK_STATE.snapshot.json"
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def write_bug_queue(self, bugs: list[dict[str, Any]]) -> Path:
        """Write BUG_QUEUE.json."""
        path = self.root / "BUG_QUEUE.json"
        path.write_text(json.dumps(bugs, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def append_progress_ledger(self, entry: dict[str, Any]) -> Path:
        """Append to PROGRESS_LEDGER.jsonl."""
        path = self.root / "PROGRESS_LEDGER.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return path

    def write_chunk_contract(self, chunk_id: str, contract: dict[str, Any]) -> Path:
        """Write chunk contract file."""
        path = self.root / "chunks" / f"{chunk_id}.contract.json"
        path.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def write_chunk_evaluation(self, chunk_id: str, evaluation: dict[str, Any]) -> Path:
        """Write chunk evaluation file."""
        path = self.root / "chunks" / f"{chunk_id}.evaluation.json"
        path.write_text(json.dumps(evaluation, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def write_final_outcome(self, outcome: dict[str, Any]) -> Path:
        """Write FINAL_OUTCOME.json."""
        path = self.root / "outcomes" / "FINAL_OUTCOME.json"
        path.write_text(json.dumps(outcome, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def write_artifact(self, name: str, content: bytes | str) -> Path:
        """Write an artifact file."""
        path = self.root / "artifacts" / name
        path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

        return path

    def write_review(self, review_id: str, review: dict[str, Any]) -> Path:
        """Write a review file."""
        path = self.root / "reviews" / f"{review_id}.json"
        path.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def read_task_request(self) -> str | None:
        """Read TASK_REQUEST.md if exists."""
        path = self.root / "TASK_REQUEST.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def read_task_context_lock(self) -> dict[str, Any] | None:
        """Read TASK_CONTEXT.lock.json if exists."""
        path = self.root / "TASK_CONTEXT.lock.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def read_task_spec(self) -> dict[str, Any] | None:
        """Read TASK_SPEC.yaml if exists."""
        import yaml
        path = self.root / "TASK_SPEC.yaml"
        if not path.exists():
            return None
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def read_execution_plan(self) -> str | None:
        """Read EXECUTION_PLAN.md if exists."""
        path = self.root / "EXECUTION_PLAN.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def read_bug_queue(self) -> list[dict[str, Any]]:
        """Read BUG_QUEUE.json."""
        path = self.root / "BUG_QUEUE.json"
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def read_progress_ledger(self) -> list[dict[str, Any]]:
        """Read PROGRESS_LEDGER.jsonl."""
        path = self.root / "PROGRESS_LEDGER.jsonl"
        if not path.exists():
            return []

        entries = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def list_chunks(self) -> list[str]:
        """List all chunk IDs in workspace."""
        chunks_dir = self.root / "chunks"
        if not chunks_dir.exists():
            return []

        chunk_ids = set()
        for path in chunks_dir.glob("*.contract.json"):
            chunk_id = path.stem.replace(".contract", "")
            chunk_ids.add(chunk_id)

        return sorted(chunk_ids)

    def list_artifacts(self) -> list[Path]:
        """List all artifact files."""
        artifacts_dir = self.root / "artifacts"
        if not artifacts_dir.exists():
            return []

        return sorted(artifacts_dir.rglob("*"))

    def cleanup(self) -> None:
        """Remove workspace directory (use with caution)."""
        if self.root.exists():
            shutil.rmtree(self.root)

    def archive(self, archive_root: Path) -> Path:
        """Archive workspace to a different location."""
        archive_path = archive_root / self.task_id
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        if archive_path.exists():
            shutil.rmtree(archive_path)

        shutil.copytree(self.root, archive_path)
        return archive_path
