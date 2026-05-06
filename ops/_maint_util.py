"""Shared utility functions for maint daemon submodules.

Extracted from maint_daemon.py to enable modular decomposition.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _tail_last_jsonl(path: Path, *, max_bytes: int = 64_000) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
    except Exception:
        return None
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            size = min(int(max_bytes), end)
            f.seek(max(0, end - size))
            raw = f.read()
    except Exception:
        return None
    lines = raw.decode("utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        s = (line or "").strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        return obj if isinstance(obj, dict) else {"_raw": s}
    return None


def _sig_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def _safe_copy(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def _normalize_error(text: str) -> str:
    s = (text or "").strip().replace("\r\n", "\n")
    if len(s) > 500:
        s = s[:500] + "..."
    return s



def _incident_dir(base: Path, incident_id: str) -> Path:
    return base / "incidents" / incident_id


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(path, payload)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")



def _read_text(path: Path, *, limit: int = 120_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[: int(limit)]
    except Exception:
        return ""


def _codex_input_fingerprint(inc_dir: Path) -> str:
    parts: list[str] = []
    manifest_obj = _read_json(inc_dir / "manifest.json") or {}
    if isinstance(manifest_obj, dict):
        stable_manifest = {
            "incident_id": str(manifest_obj.get("incident_id") or "").strip(),
            "sig_hash": str(manifest_obj.get("sig_hash") or "").strip(),
            "signature": str(manifest_obj.get("signature") or "").strip(),
            "severity": str(manifest_obj.get("severity") or "").strip(),
            "job_ids": sorted(str(x) for x in (manifest_obj.get("job_ids") or []) if str(x).strip()),
            "repair_job_id": (str(manifest_obj.get("repair_job_id") or "").strip() or None),
        }
        parts.append(json.dumps(stable_manifest, ensure_ascii=False, sort_keys=True))
    else:
        parts.append(_read_text(inc_dir / "manifest.json", limit=80_000))
    parts.append(_read_text(inc_dir / "summary.md", limit=80_000))
    parts.append(_read_text(inc_dir / "snapshots" / "repair_check" / "repair_report.json", limit=80_000))
    parts.append(_read_text(inc_dir / "snapshots" / "issues_registry.yaml", limit=80_000))
    try:
        job_rows = sorted((inc_dir / "jobs").glob("*/job_row.json"))
    except Exception:
        job_rows = []
    for p in job_rows[-5:]:
        obj = _read_json(p)
        if isinstance(obj, dict):
            stable_job_row = {
                "job_id": str(obj.get("job_id") or "").strip(),
                "kind": str(obj.get("kind") or "").strip(),
                "status": str(obj.get("status") or "").strip(),
                "last_error_type": str(obj.get("last_error_type") or "").strip(),
                "last_error": str(obj.get("last_error") or "").strip(),
                "conversation_url": str(obj.get("conversation_url") or "").strip(),
            }
            parts.append(json.dumps(stable_job_row, ensure_ascii=False, sort_keys=True))
        else:
            parts.append(_read_text(p, limit=12_000))
    return _sig_hash("\n\n".join(parts))


def _truncate_text(text: str, *, limit: int) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    if len(s) <= int(limit):
        return s
    return f"{s[: int(limit)]}...<truncated {len(s) - int(limit)} chars>"


def _write_text(path: Path, text: str, *, limit: int = 50_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _truncate_text(text, limit=int(limit))
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")

