#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from chatgptrest.core.conversation_exports import extract_last_assistant_text, normalize_dom_export_text


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(_read_text(path))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _fence_balanced(answer: str) -> bool:
    return answer.count("```") % 2 == 0


def _strip_single_fence(text: str) -> str:
    m = re.match(r"^```[a-zA-Z0-9_-]*\n(.*)\n```\s*$", text, flags=re.S)
    if m:
        return m.group(1).strip()
    return text.strip()


def _normalize_plain(text: str) -> str:
    text = re.sub(r"[`*_>#\-\|]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_json_if_fenced(answer: str) -> tuple[bool, str | None]:
    m = re.match(r"^```json\n(.*)\n```\s*$", answer.strip(), flags=re.S | re.I)
    if not m:
        return False, None
    payload = m.group(1)
    try:
        json.loads(payload)
    except Exception as e:
        return True, f"{e.__class__.__name__}: {e}"
    return True, None


def _find_answer_path(job_dir: Path) -> Path | None:
    for name in ["answer.md", "answer.txt", "answer.json"]:
        p = job_dir / name
        if p.exists():
            return p
    return None


def _extract_last_assistant(conversation: dict[str, Any]) -> str:
    return extract_last_assistant_text(obj=conversation) or ""


def _as_str(v: object) -> str:
    return str(v or "")


def _format_md(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# verify_report: {report.get('job_id')}")
    lines.append("")
    lines.append(f"- status: `{report.get('status')}` (phase `{report.get('phase')}`)")
    reason_type = _as_str(report.get("reason_type")).strip()
    reason = _as_str(report.get("reason")).strip()
    if reason_type or reason:
        lines.append(f"- reason: `{reason_type}` {reason}".rstrip())

    answer = report.get("answer") or {}
    answer_path = answer.get("path")
    if answer_path:
        lines.append(f"- answer: `{answer_path}` ({answer.get('chars')} chars)")
        if answer.get("fenced_json"):
            fenced_json_error = answer.get("fenced_json_error")
            lines.append(f"- fenced_json: {'ok' if not fenced_json_error else 'ERROR: ' + str(fenced_json_error)}")
        if answer.get("fence_balanced") is False:
            lines.append("- fence_balanced: false")
    else:
        lines.append("- answer: (missing)")

    export = report.get("conversation_export") or {}
    export_path = export.get("path") or "(missing)"
    if export.get("has_assistant"):
        lines.append(f"- export: `{export_path}` (last assistant {export.get('last_assistant_chars')} chars)")
    else:
        lines.append(f"- export: `{export_path}` (no assistant)")

    compare = report.get("compare") or {}
    if compare.get("ok") is not None:
        sim = compare.get("similarity")
        sim_str = "" if sim is None else f"{float(sim):.3f}"
        lines.append(f"- compare: {compare.get('mode')} (similarity={sim_str}) ok={compare.get('ok')}")

    warnings = report.get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        lines.extend([f"- {w}" for w in warnings])

    notes = report.get("notes") or []
    if notes:
        lines.append("")
        lines.append("## Notes")
        lines.extend([f"- {n}" for n in notes])

    lines.append("")
    return "\n".join(lines)


def verify_job(*, artifacts_dir: Path, job_id: str, min_similarity: float) -> dict[str, Any]:
    job_dir = artifacts_dir / "jobs" / job_id
    report_path = job_dir / "verify_report.json"
    markdown_path = job_dir / "verify_report.md"

    warnings: list[str] = []
    notes: list[str] = []

    result = _read_json(job_dir / "result.json") or {}
    run_meta = _read_json(job_dir / "run_meta.json") or {}
    conv = _read_json(job_dir / "conversation.json") or {}

    status = _as_str(result.get("status"))
    phase = _as_str(result.get("phase"))
    reason_type = _as_str(result.get("reason_type"))
    reason = _as_str(result.get("reason"))

    answer_path = _find_answer_path(job_dir)
    answer_text = ""
    answer_sha256 = ""
    answer_chars = 0
    fence_balanced = True
    fenced_json = False
    fenced_json_error = None

    if answer_path is None:
        warnings.append("missing_answer")
    else:
        raw = answer_path.read_bytes()
        answer_sha256 = _sha256_bytes(raw)
        answer_text = raw.decode("utf-8", errors="replace")
        answer_chars = len(answer_text)
        fence_balanced = _fence_balanced(answer_text)
        if not fence_balanced:
            warnings.append("unbalanced_fences")
        fenced_json, fenced_json_error = _parse_json_if_fenced(answer_text)
        if fenced_json and fenced_json_error:
            warnings.append("fenced_json_parse_error")

    answer_truncated = bool(run_meta.get("answer_truncated"))
    # Older/newer run_meta variants may not explicitly report rehydration.
    # Infer from increased saved answer chars when possible.
    answer_returned_chars = int(run_meta.get("answer_returned_chars") or 0)
    answer_meta_chars = int(run_meta.get("answer_chars") or 0)
    answer_rehydrated = bool(run_meta.get("answer_rehydrated"))
    if not answer_rehydrated and answer_truncated and answer_returned_chars and answer_meta_chars:
        answer_rehydrated = answer_meta_chars > (answer_returned_chars + 200)

    if answer_truncated and not answer_rehydrated:
        warnings.append("tool_answer_truncated_not_rehydrated")
    elif answer_truncated and answer_rehydrated:
        notes.append("tool_answer_truncated_but_rehydrated")

    conv_last = _extract_last_assistant(conv)
    export_has_assistant = bool(conv_last)
    compare_mode = "none"
    similarity: float | None = None
    compare_ok: bool | None = None

    if not export_has_assistant:
        notes.append("conversation_export_has_no_assistant")
    else:
        dom_norm = _normalize_dom_export_text(conv_last)
        ans_strip = _strip_single_fence(answer_text) if answer_text else ""
        if dom_norm and ans_strip and dom_norm == ans_strip:
            compare_mode = "dom_norm_equals_stripped_answer"
            similarity = 1.0
            compare_ok = True
        else:
            compare_mode = "plain_similarity"
            a = _normalize_plain(answer_text)
            c = _normalize_plain(conv_last)
            similarity = SequenceMatcher(None, a, c).ratio() if a and c else 0.0
            compare_ok = similarity >= float(min_similarity)
            if compare_ok is False:
                warnings.append("answer_export_low_similarity")

    if status == "completed" and answer_chars and answer_chars < 200:
        notes.append("short_completed_answer")

    report: dict[str, Any] = {
        "job_id": job_id,
        "status": status,
        "phase": phase,
        "reason_type": reason_type,
        "reason": reason,
        "answer": {
            "path": (str(answer_path) if answer_path else None),
            "sha256": (answer_sha256 if answer_sha256 else None),
            "chars": answer_chars,
            "fence_balanced": fence_balanced,
            "fenced_json": fenced_json,
            "fenced_json_error": fenced_json_error,
        },
        "conversation_export": {
            "path": (str(job_dir / "conversation.json") if (job_dir / "conversation.json").exists() else None),
            "export_kind": conv.get("export_kind"),
            "backend_status": conv.get("backend_status"),
            "has_assistant": export_has_assistant,
            "last_assistant_chars": (len(conv_last) if export_has_assistant else 0),
        },
        "compare": {
            "mode": compare_mode,
            "similarity": similarity,
            "ok": compare_ok,
        },
        "run_meta": {
            "answer_truncated": answer_truncated,
            "answer_rehydrated": answer_rehydrated,
            "answer_returned_chars": run_meta.get("answer_returned_chars"),
            "answer_rehydrated_chars": run_meta.get("answer_rehydrated_chars"),
            "conversation_url": run_meta.get("conversation_url"),
            "run_id": run_meta.get("run_id"),
            "worker_role": run_meta.get("worker_role"),
        },
        "warnings": warnings,
        "notes": notes,
    }

    _atomic_write_json(report_path, report)
    _atomic_write_text(markdown_path, _format_md(report))
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify ChatgptREST job answers vs conversation exports (offline).")
    parser.add_argument("--artifacts-dir", default="artifacts", help="Artifacts directory (default: ./artifacts)")
    parser.add_argument("--job-id", action="append", required=True, help="Job id to verify (repeatable)")
    parser.add_argument("--min-similarity", type=float, default=0.85, help="Threshold for plain-text similarity")
    args = parser.parse_args(argv)

    artifacts_dir = Path(args.artifacts_dir).resolve()
    failures = 0
    for job_id in args.job_id:
        job_id = str(job_id or "").strip()
        if not job_id:
            continue
        report = verify_job(artifacts_dir=artifacts_dir, job_id=job_id, min_similarity=float(args.min_similarity))
        md_path = artifacts_dir / "jobs" / job_id / "verify_report.md"
        print(str(md_path))
        if report.get("warnings"):
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
