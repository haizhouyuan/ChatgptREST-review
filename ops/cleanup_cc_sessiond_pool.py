#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _looks_like_versioned_markdown_path(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower().endswith(".md") and "_v" in Path(text).name


@dataclass
class RegistryRecord:
    session_id: str
    state: str
    prompt: str
    prompt_doc_path: str | None
    error: str | None
    created_at: str
    updated_at: str


def load_registry_records(db_path: Path) -> list[RegistryRecord]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT session_id, state, prompt, options, error, created_at, updated_at FROM sessions ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()

    records: list[RegistryRecord] = []
    for row in rows:
        try:
            options = json.loads(str(row["options"] or "{}"))
        except Exception:
            options = {}
        prompt = str(row["prompt"] or "")
        prompt_doc_path = options.get("prompt_doc_path")
        if not prompt_doc_path and _looks_like_versioned_markdown_path(prompt):
            prompt_doc_path = prompt
        records.append(
            RegistryRecord(
                session_id=str(row["session_id"]),
                state=str(row["state"]),
                prompt=prompt,
                prompt_doc_path=(str(prompt_doc_path) if prompt_doc_path else None),
                error=(str(row["error"]) if row["error"] else None),
                created_at=str(row["created_at"] or ""),
                updated_at=str(row["updated_at"] or ""),
            )
        )
    return records


def classify_record(record: RegistryRecord, *, preserve_session_ids: set[str]) -> dict[str, Any]:
    if record.session_id in preserve_session_ids:
        return {"action": "keep", "reason": "preserved_session_id"}

    prompt_doc_path = record.prompt_doc_path
    if not prompt_doc_path:
        return {"action": "delete", "reason": "invalid_prompt_record"}

    prompt_path = Path(prompt_doc_path)
    if prompt_path.parent.name.startswith("tmp."):
        return {"action": "delete", "reason": "volatile_tmp_task_packet", "prompt_doc_path": str(prompt_path)}
    if not prompt_path.exists() or not prompt_path.is_file():
        return {"action": "delete", "reason": "missing_task_packet", "prompt_doc_path": str(prompt_path)}

    return {"action": "keep", "reason": "valid_task_packet", "prompt_doc_path": str(prompt_path)}


def build_cleanup_plan(
    *,
    db_path: Path,
    artifacts_dir: Path,
    preserve_session_ids: set[str],
) -> dict[str, Any]:
    records = load_registry_records(db_path)
    registry_by_id = {record.session_id: record for record in records}
    artifact_dirs = sorted([path for path in artifacts_dir.iterdir() if path.is_dir()]) if artifacts_dir.exists() else []

    keep_registry: list[dict[str, Any]] = []
    delete_registry: list[dict[str, Any]] = []
    keep_artifacts: list[dict[str, Any]] = []
    delete_artifacts: list[dict[str, Any]] = []

    for record in records:
        decision = classify_record(record, preserve_session_ids=preserve_session_ids)
        payload = {
            "session_id": record.session_id,
            "state": record.state,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "prompt": record.prompt,
            "prompt_doc_path": record.prompt_doc_path,
            "error": record.error,
            **decision,
        }
        artifact_path = artifacts_dir / record.session_id
        if decision["action"] == "delete":
            delete_registry.append(payload)
            if artifact_path.exists():
                delete_artifacts.append({"session_id": record.session_id, "path": str(artifact_path), "reason": decision["reason"]})
        else:
            keep_registry.append(payload)
            if artifact_path.exists():
                keep_artifacts.append({"session_id": record.session_id, "path": str(artifact_path), "reason": decision["reason"]})

    for artifact_dir in artifact_dirs:
        session_id = artifact_dir.name
        if session_id in registry_by_id:
            continue
        if session_id in preserve_session_ids:
            keep_artifacts.append({"session_id": session_id, "path": str(artifact_dir), "reason": "preserved_session_id"})
            continue
        delete_artifacts.append({"session_id": session_id, "path": str(artifact_dir), "reason": "artifact_orphan"})

    return {
        "db_path": str(db_path),
        "artifacts_dir": str(artifacts_dir),
        "summary": {
            "registry_total": len(records),
            "registry_keep": len(keep_registry),
            "registry_delete": len(delete_registry),
            "artifact_dirs_total": len(artifact_dirs),
            "artifact_dirs_keep": len(keep_artifacts),
            "artifact_dirs_delete": len(delete_artifacts),
        },
        "preserve_session_ids": sorted(preserve_session_ids),
        "registry_keep": keep_registry,
        "registry_delete": delete_registry,
        "artifact_keep": keep_artifacts,
        "artifact_delete": delete_artifacts,
    }


def apply_cleanup_plan(plan: dict[str, Any]) -> dict[str, Any]:
    db_path = Path(str(plan["db_path"]))
    conn = sqlite3.connect(str(db_path))
    deleted_registry_ids: list[str] = []
    deleted_artifact_paths: list[str] = []
    try:
        conn.execute("BEGIN IMMEDIATE")
        for item in list(plan.get("registry_delete") or []):
            session_id = str(item.get("session_id") or "").strip()
            if not session_id:
                continue
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            deleted_registry_ids.append(session_id)
        conn.commit()
    finally:
        conn.close()

    for item in list(plan.get("artifact_delete") or []):
        path = Path(str(item.get("path") or "")).expanduser()
        if not path.exists():
            continue
        shutil.rmtree(path)
        deleted_artifact_paths.append(str(path))

    return {
        "deleted_registry_ids": deleted_registry_ids,
        "deleted_artifact_paths": deleted_artifact_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run/apply cleanup for cc-sessiond registry + artifact pool.")
    parser.add_argument("--db-path", default="/tmp/cc-sessions.db")
    parser.add_argument("--artifacts-dir", default="/tmp/artifacts/cc_sessions")
    parser.add_argument("--preserve-session-id", action="append", default=[])
    parser.add_argument("--apply", action="store_true", help="Actually delete registry rows and artifact dirs.")
    parser.add_argument("--report-path", default="", help="Optional JSON report output path.")
    args = parser.parse_args()

    plan = build_cleanup_plan(
        db_path=Path(args.db_path).expanduser(),
        artifacts_dir=Path(args.artifacts_dir).expanduser(),
        preserve_session_ids={str(item).strip() for item in list(args.preserve_session_id or []) if str(item).strip()},
    )

    report: dict[str, Any] = {"plan": plan}
    if args.apply:
        report["applied"] = apply_cleanup_plan(plan)

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report_path:
        report_path = Path(args.report_path).expanduser()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
