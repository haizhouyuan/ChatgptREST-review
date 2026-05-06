#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from chatgptrest.core.codex_runner import codex_exec_with_schema


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path, *, limit: int = 120_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _tail_lines(path: Path, *, max_lines: int = 80, max_bytes: int = 120_000) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            size = min(int(max_bytes), end)
            f.seek(max(0, end - size))
            raw = f.read()
    except Exception:
        return ""
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if len(lines) > int(max_lines):
        lines = lines[-int(max_lines) :]
    return "\n".join(lines)


def _append_section(lines: list[str], *, title: str, body: str) -> None:
    text = (body or "").strip()
    if not text:
        return
    lines.append(f"=== {title} ===")
    lines.append(text)
    lines.append("")


def _build_prompt(incident_dir: Path, *, global_memory_md: Path | None = None) -> str:
    manifest_text = _read_text(incident_dir / "manifest.json", limit=60_000)
    summary_text = _read_text(incident_dir / "summary.md", limit=60_000)
    manifest_obj = _read_json(incident_dir / "manifest.json") or {}

    lines: list[str] = []
    lines.append("You are an SRE/incident commander for ChatgptREST.")
    lines.append("")
    lines.append("Goal: given an incident evidence pack directory, propose a safe diagnosis + action plan.")
    lines.append("")
    lines.append("Hard constraints:")
    lines.append("- Do NOT send any ChatGPT Web test prompts (no smoke tests).")
    lines.append("- Do NOT change ChatGPT send pacing (61s).")
    lines.append("- Prefer read-only actions first (evidence capture, status probes).")
    lines.append("- Treat browser actions as side-effectful and require guardrails (cooldowns, max attempts).")
    lines.append("")
    lines.append("Context:")
    lines.append("- The incident pack is on disk under the provided path (you can read files).")
    lines.append("- Driver side-effect actions that are allowed (when guarded): refresh, regenerate.")
    lines.append("- Driver has netlog capture (optional) and Answer-now click blocker.")
    lines.append("")
    lines.append(f"Incident dir: {incident_dir}")
    lines.append("")
    lines.append("Produce JSON that matches the provided JSON Schema.")
    lines.append("")

    _append_section(lines, title="manifest.json (truncated)", body=manifest_text)
    _append_section(lines, title="summary.md (truncated)", body=summary_text)

    if global_memory_md is not None:
        _append_section(lines, title="global_memory.md (truncated)", body=_read_text(global_memory_md, limit=60_000))

    for rel in [
        "snapshots/issues_registry.yaml",
        "snapshots/repair_check/repair_report.json",
        "snapshots/cdp_version.json",
        "snapshots/mihomo_delay_last.json",
        "snapshots/chatgptmcp/blocked_status.json",
        "snapshots/chatgptmcp/rate_limit_status.json",
        "snapshots/chatgptmcp/self_check.json",
        "snapshots/chatgptmcp/tab_stats.json",
    ]:
        _append_section(lines, title=f"{rel} (truncated)", body=_read_text(incident_dir / rel, limit=60_000))

    job_ids: list[str] = []
    job_ids_raw = manifest_obj.get("job_ids") if isinstance(manifest_obj, dict) else None
    if isinstance(job_ids_raw, list):
        for x in job_ids_raw:
            s = str(x or "").strip()
            if s:
                job_ids.append(s)
    if not job_ids:
        jobs_dir = incident_dir / "jobs"
        try:
            job_ids = sorted([p.name for p in jobs_dir.iterdir() if p.is_dir()])
        except Exception:
            job_ids = []

    for job_id in job_ids[-2:]:
        job_dir = incident_dir / "jobs" / job_id
        _append_section(lines, title=f"jobs/{job_id}/job_row.json (truncated)", body=_read_text(job_dir / "job_row.json", limit=60_000))
        _append_section(lines, title=f"jobs/{job_id}/run_meta.json (truncated)", body=_read_text(job_dir / "run_meta.json", limit=60_000))
        _append_section(lines, title=f"jobs/{job_id}/result.json (truncated)", body=_read_text(job_dir / "result.json", limit=60_000))
        _append_section(lines, title=f"jobs/{job_id}/events.jsonl (tail)", body=_tail_lines(job_dir / "events.jsonl", max_lines=120))

    lines.append("If you need more context, read additional files under the incident dir, but prefer the evidence above.")
    lines.append("")
    return "\n".join(lines).strip()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Run Codex (read-only) to analyze a maint_daemon incident pack.")
    ap.add_argument("incident_dir", help="Path to artifacts/monitor/maint_daemon/incidents/<incident_id>")
    ap.add_argument("--model", default=os.environ.get("CODEX_SRE_MODEL") or "", help="Optional codex model override")
    ap.add_argument("--global-memory-md", default="", help="Optional path to a markdown digest of global memory (included in prompt)")
    ap.add_argument("--timeout-seconds", type=int, default=int(os.environ.get("CODEX_SRE_TIMEOUT_SECONDS") or 600), help="Timeout for codex exec (seconds)")
    ap.add_argument(
        "--schema",
        default=str((_repo_root() / "ops" / "schemas" / "codex_sre_actions.schema.json").resolve()),
        help="JSON schema path for structured output",
    )
    ap.add_argument(
        "--out",
        default="",
        help="Output JSON path (default: <incident_dir>/codex/sre_actions.json)",
    )
    args = ap.parse_args(argv)

    incident_dir = Path(str(args.incident_dir)).expanduser()
    if not incident_dir.is_absolute():
        incident_dir = (_repo_root() / incident_dir).resolve(strict=False)
    if not incident_dir.exists():
        raise SystemExit(f"incident_dir not found: {incident_dir}")

    schema_path = Path(str(args.schema)).expanduser()
    if not schema_path.is_absolute():
        schema_path = (_repo_root() / schema_path).resolve(strict=False)
    if not schema_path.exists():
        raise SystemExit(f"schema not found: {schema_path}")

    out_path_raw = str(args.out).strip()
    out_path = Path(out_path_raw).expanduser() if out_path_raw else (incident_dir / "codex" / "sre_actions.json")
    if not out_path.is_absolute():
        out_path = (incident_dir / out_path).resolve(strict=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    global_memory_md: Path | None = None
    raw_global_md = str(getattr(args, "global_memory_md", "") or "").strip()
    if raw_global_md:
        gm = Path(raw_global_md).expanduser()
        if not gm.is_absolute():
            gm = (_repo_root() / gm).resolve(strict=False)
        if gm.exists():
            global_memory_md = gm

    if global_memory_md is None:
        candidate = incident_dir / "snapshots" / "codex_global_memory.md"
        if candidate.exists():
            global_memory_md = candidate

    prompt = _build_prompt(incident_dir, global_memory_md=global_memory_md)
    res = codex_exec_with_schema(
        prompt=prompt,
        schema_path=schema_path,
        out_json=out_path,
        model=(str(args.model).strip() if str(args.model).strip() else None),
        timeout_seconds=int(max(1, int(args.timeout_seconds))),
        cd=_repo_root(),
        sandbox="read-only",
    )
    if not res.ok:
        err = (str(res.error or "").strip() or str(res.stderr or "").strip() or "codex exec failed")
        if len(err) <= 4000:
            raise SystemExit(f"codex exec failed (rc={res.returncode}):\n{err}")
        head = err[:2000]
        tail = err[-2000:]
        raise SystemExit("codex exec failed (rc=%s):\n--- head ---\n%s\n--- tail ---\n%s" % (res.returncode, head, tail))

    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(list(sys.argv[1:])))
