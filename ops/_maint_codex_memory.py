"""Codex global memory management for maint daemon.

Extracted from maint_daemon.py — JSONL I/O, global memory digest rendering,
and memory update logic.  Re-exported by maint_daemon via __getattr__.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from chatgptrest.ops_shared.maint_memory import merge_maintagent_bootstrap_into_markdown

from _maint_util import (
    _now_iso,
    _read_json,
    _atomic_write_json,
    _append_jsonl,
    _truncate_text,
    _write_text,
    _read_text,
)

def _tail_jsonl_objects(path: Path, *, max_bytes: int, max_records: int) -> list[dict[str, Any]]:
    if int(max_bytes) <= 0 or int(max_records) <= 0:
        return []
    try:
        if not path.exists():
            return []
    except Exception:
        return []

    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            size = min(int(max_bytes), int(end))
            f.seek(max(0, int(end) - size))
            raw = f.read()
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        s = (line or "").strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    if len(out) > int(max_records):
        out = out[-int(max_records) :]
    return out


def _trim_jsonl_file_by_bytes(path: Path, *, max_bytes: int) -> None:
    if int(max_bytes) <= 0:
        return
    try:
        size = int(path.stat().st_size)
    except Exception:
        return
    if size <= int(max_bytes):
        return

    try:
        with path.open("rb") as f:
            f.seek(max(0, size - int(max_bytes)))
            raw = f.read()
    except Exception:
        return

    # Drop the first (possibly partial) line.
    nl = raw.find(b"\n")
    if nl >= 0:
        raw = raw[nl + 1 :]

    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(raw)
    tmp.replace(path)


def _render_codex_global_memory_digest(records: list[dict[str, Any]], *, max_groups: int = 50) -> str:
    lines: list[str] = []
    lines.append("# Codex Global Memory (ChatgptREST)")
    lines.append("")
    lines.append(f"Updated: {_now_iso()}")
    lines.append("")

    if not records:
        lines.append("_empty_")
        return "\n".join(lines).strip() + "\n"

    lines.append("## Known patterns (newest first)")
    seen: set[str] = set()
    groups = 0
    for rec in reversed(records):
        sig_hash = str(rec.get("sig_hash") or "").strip()
        if not sig_hash or sig_hash in seen:
            continue
        seen.add(sig_hash)
        groups += 1
        if groups > int(max_groups):
            break

        provider = str(rec.get("provider") or "").strip() or "unknown"
        incident_id = str(rec.get("incident_id") or "").strip()
        ts = str(rec.get("ts") or "").strip()
        summary = str(rec.get("summary") or "").strip().replace("\n", " ")
        summary = _truncate_text(summary, limit=240)

        top_actions: list[str] = []
        raw_actions = rec.get("top_actions")
        if isinstance(raw_actions, list):
            for a in raw_actions[:10]:
                if isinstance(a, str):
                    name = a
                elif isinstance(a, dict):
                    name = str(a.get("name") or "")
                else:
                    name = ""
                name = str(name or "").strip()
                if name:
                    top_actions.append(name)
        actions_s = ",".join(top_actions[:8])

        parts = [f"`{sig_hash}`", f"provider=`{provider}`"]
        if incident_id:
            parts.append(f"incident=`{incident_id}`")
        if ts:
            parts.append(f"ts=`{ts}`")
        if actions_s:
            parts.append(f"actions={actions_s}")
        if summary:
            parts.append(f"summary={summary}")
        lines.append("- " + " ".join(parts))

    lines.append("")
    return merge_maintagent_bootstrap_into_markdown("\n".join(lines).strip() + "\n")


def _snapshot_codex_global_memory_md(*, global_md: Path, inc_dir: Path, max_chars: int) -> Path | None:
    if int(max_chars) <= 0:
        return None
    text = ""
    try:
        if global_md.exists():
            text = global_md.read_text(encoding="utf-8", errors="replace")
    except Exception:
        text = ""
    text = merge_maintagent_bootstrap_into_markdown(text)
    if not str(text or "").strip():
        return None

    snapshots = inc_dir / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    dst = snapshots / "codex_global_memory.md"
    _write_text(dst, text, limit=int(max_chars))
    return dst


def _update_codex_global_memory(
    *,
    jsonl_path: Path,
    md_path: Path,
    record: dict[str, Any],
    digest_max_records: int,
    max_bytes: int,
) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    _trim_jsonl_file_by_bytes(jsonl_path, max_bytes=int(max_bytes))

    # Prefer a bounded tail read to keep digest generation cheap even if JSONL grows.
    tail_bytes = int(max_bytes) if int(max_bytes) > 0 else 2_000_000
    tail = _tail_jsonl_objects(jsonl_path, max_bytes=max(200_000, tail_bytes), max_records=int(digest_max_records))
    md_text = _render_codex_global_memory_digest(
        tail,
        max_groups=min(80, int(digest_max_records) if int(digest_max_records) > 0 else 50),
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_text, encoding="utf-8")


def _codex_global_memory_record(
    *,
    trigger: str,
    incident_id: str,
    sig_hash: str,
    provider: str | None,
    signature: str,
    run_meta: dict[str, Any],
    actions_payload: dict[str, Any],
) -> dict[str, Any]:
    summary = str(actions_payload.get("summary") or "").strip().replace("\n", " ")
    hypotheses = actions_payload.get("hypotheses") if isinstance(actions_payload.get("hypotheses"), list) else []
    actions = actions_payload.get("actions") if isinstance(actions_payload.get("actions"), list) else []
    risks = actions_payload.get("risks") if isinstance(actions_payload.get("risks"), list) else []
    next_steps = actions_payload.get("next_steps") if isinstance(actions_payload.get("next_steps"), list) else []

    hyp_titles: list[str] = []
    for h in hypotheses[:8]:
        if not isinstance(h, dict):
            continue
        t = str(h.get("title") or "").strip()
        if t:
            hyp_titles.append(t)

    top_actions: list[dict[str, Any]] = []
    for a in actions[:10]:
        if not isinstance(a, dict):
            continue
        name = str(a.get("name") or "").strip()
        if not name:
            continue
        top_actions.append(
            {
                "name": name,
                "risk": (str(a.get("risk") or "").strip() or None),
                "reason": (_truncate_text(str(a.get("reason") or "").strip().replace("\n", " "), limit=400) or None),
            }
        )

    trimmed_risks: list[str] = []
    if isinstance(risks, list):
        for r in risks[:8]:
            rs = str(r or "").strip().replace("\n", " ")
            if rs:
                trimmed_risks.append(_truncate_text(rs, limit=300))

    trimmed_next: list[str] = []
    if isinstance(next_steps, list):
        for n in next_steps[:8]:
            ns = str(n or "").strip().replace("\n", " ")
            if ns:
                trimmed_next.append(_truncate_text(ns, limit=300))

    return {
        "ts": _now_iso(),
        "type": "codex_global_memory",
        "trigger": (str(trigger).strip() or None),
        "incident_id": str(incident_id),
        "sig_hash": str(sig_hash),
        "provider": (str(provider).strip() if provider else None),
        "signature": _truncate_text(str(signature or "").strip().replace("\n", " "), limit=500),
        "summary": _truncate_text(summary, limit=1200),
        "hypotheses": hyp_titles,
        "top_actions": top_actions,
        "risks": trimmed_risks,
        "next_steps": trimmed_next,
        "codex": {
            "ok": bool(run_meta.get("ok")),
            "elapsed_ms": run_meta.get("elapsed_ms"),
            "input_hash": run_meta.get("input_hash"),
            "model": run_meta.get("model"),
            "actions_json": run_meta.get("actions_json"),
            "actions_md": run_meta.get("actions_md"),
            "global_memory_md": run_meta.get("global_memory_md"),
        },
    }


def _maybe_update_codex_global_memory_after_run(
    *,
    enabled: bool,
    trigger: str,
    inc_dir: Path,
    incident_id: str,
    sig_hash: str,
    signature: str,
    provider: str | None,
    run_meta: dict[str, Any],
    jsonl_path: Path,
    md_path: Path,
    digest_max_records: int,
    max_bytes: int,
    log_path: Path | None = None,
) -> dict[str, Any]:
    if not bool(enabled):
        return {"ok": True, "skipped": True, "reason": "disabled"}
    if not bool(run_meta.get("ok")):
        return {"ok": True, "skipped": True, "reason": "codex_failed"}

    actions_raw = str(run_meta.get("actions_json") or "").strip()
    if not actions_raw:
        return {"ok": True, "skipped": True, "reason": "missing_actions_json"}

    actions_path = Path(actions_raw).expanduser()
    if not actions_path.is_absolute():
        actions_path = (inc_dir / actions_path).resolve(strict=False)

    actions_payload = _read_json(actions_path)
    if not isinstance(actions_payload, dict):
        return {"ok": True, "skipped": True, "reason": "invalid_actions_payload", "actions_json": str(actions_path)}

    record = _codex_global_memory_record(
        trigger=str(trigger),
        incident_id=str(incident_id),
        sig_hash=str(sig_hash),
        provider=(str(provider).strip() if provider else None),
        signature=str(signature),
        run_meta=run_meta,
        actions_payload=actions_payload,
    )

    record_path: Path | None = None
    try:
        snapshots = inc_dir / "snapshots"
        snapshots.mkdir(parents=True, exist_ok=True)
        record_path = snapshots / "codex_global_memory_record.json"
        _atomic_write_json(record_path, record)
    except Exception:
        record_path = None

    try:
        _update_codex_global_memory(
            jsonl_path=jsonl_path,
            md_path=md_path,
            record=record,
            digest_max_records=int(digest_max_records),
            max_bytes=int(max_bytes),
        )
    except Exception as exc:
        if log_path is not None:
            _append_jsonl(
                log_path,
                {
                    "ts": _now_iso(),
                    "type": "codex_global_memory_update_error",
                    "trigger": str(trigger),
                    "incident_id": str(incident_id),
                    "sig_hash": str(sig_hash),
                    "provider": (str(provider).strip() if provider else None),
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:800],
                    "record_path": (str(record_path) if record_path is not None else None),
                    "actions_json": str(actions_path),
                },
            )
        return {
            "ok": False,
            "skipped": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:800],
            "record_path": (str(record_path) if record_path is not None else None),
            "actions_json": str(actions_path),
        }

    if log_path is not None:
        _append_jsonl(
            log_path,
            {
                "ts": _now_iso(),
                "type": "codex_global_memory_updated",
                "trigger": str(trigger),
                "incident_id": str(incident_id),
                "sig_hash": str(sig_hash),
                "provider": (str(provider).strip() if provider else None),
                "record_path": (str(record_path) if record_path is not None else None),
                "global_jsonl": str(jsonl_path),
                "global_md": str(md_path),
            },
        )

    return {
        "ok": True,
        "skipped": False,
        "record_path": (str(record_path) if record_path is not None else None),
        "global_jsonl": str(jsonl_path),
        "global_md": str(md_path),
    }

