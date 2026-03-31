#!/usr/bin/env python3
# DEPRECATED: Uses retired chatgptrest-* orch fleet topology.
# See config/topology.yaml for the canonical production baseline (Issue #126).
from __future__ import annotations

import argparse
import logging as _logging
import warnings as _warnings

_warnings.warn(
    "openclaw_orch_agent.py uses the retired chatgptrest-* fleet topology. "
    "See config/topology.yaml for the current production baseline.",
    DeprecationWarning,
    stacklevel=1,
)
_logging.getLogger(__name__).warning(
    "openclaw_orch_agent.py: retired chatgptrest-* fleet topology — see config/topology.yaml"
)
import json
import os
import sqlite3
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = REPO_ROOT / "artifacts" / "monitor" / "openclaw_orch" / "latest_report.json"
DEFAULT_DB = REPO_ROOT / "state" / "jobdb.sqlite3"
DEFAULT_UI_CANARY_REPORT = REPO_ROOT / "artifacts" / "monitor" / "ui_canary" / "latest.json"
DEFAULT_WAKE_STATE = REPO_ROOT / "artifacts" / "monitor" / "openclaw_orch" / "wake_state.json"


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    workspace: str
    model: str
    session_id: str


def _default_openclaw_cmd() -> str:
    env_cmd = str(os.environ.get("OPENCLAW_CMD") or "").strip()
    if env_cmd:
        return env_cmd
    which = shutil.which("openclaw")
    if which:
        return which
    candidate_roots = [Path.home()]
    if Path.home().name != ".home-codex-official":
        candidate_roots.append(Path.home() / ".home-codex-official")
    for root in candidate_roots:
        fallback = root / ".local" / "bin" / "openclaw"
        if fallback.exists():
            return str(fallback)
    return "openclaw"


def _required_agents(workspace: Path) -> list[AgentSpec]:
    ws = str(workspace.resolve())
    return [
        AgentSpec("chatgptrest-orch", ws, "openai-codex/gpt-5.3-codex-spark", "chatgptrest-orch-main"),
        AgentSpec("chatgptrest-codex-w1", ws, "codex-cli/gpt-5.3-codex", "chatgptrest-codex-w1-main"),
        AgentSpec("chatgptrest-codex-w2", ws, "codex-cli/gpt-5.3-codex", "chatgptrest-codex-w2-main"),
        AgentSpec("chatgptrest-codex-w3", ws, "codex-cli/gpt-5.3-codex", "chatgptrest-codex-w3-main"),
        AgentSpec("chatgptrest-guardian", ws, "openai-codex/gpt-5.3-codex-spark", "chatgptrest-guardian-main"),
    ]


def _agent_dir_required(spec: AgentSpec) -> bool:
    # codex-cli worker agents are lazily materialized by OpenClaw on first real turn.
    return not str(spec.model).startswith("codex-cli/")


def _run(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)


def _parse_json_loose(text: str) -> Any | None:
    s = str(text or "")
    decoder = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch not in "{[":
            continue
        try:
            obj, end = decoder.raw_decode(s[i:])
        except Exception:
            continue
        if isinstance(obj, (dict, list)) and not s[i + end :].strip():
            return obj
    return None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _parse_iso_ts(raw: str | None) -> float:
    text = str(raw or "").strip()
    if not text:
        return 0.0
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return float(datetime.fromisoformat(text).timestamp())
    except Exception:
        return 0.0


def _collect_ui_canary_report(
    *,
    report_path: Path,
    stale_seconds: int,
    fail_threshold: int,
) -> dict[str, Any]:
    payload = _read_json(report_path)
    if payload is None:
        return {
            "enabled": True,
            "ok": False,
            "reason": "missing_or_invalid_report",
            "report_path": str(report_path),
            "providers": [],
            "failed_providers": [],
            "stale": True,
        }

    providers = payload.get("providers")
    rows = providers if isinstance(providers, list) else []
    state_obj = payload.get("state")
    state_map = state_obj if isinstance(state_obj, dict) else {}

    now = time.time()
    ts_iso = str(payload.get("ts") or "")
    ts_epoch = _parse_iso_ts(ts_iso)
    age_seconds = (now - ts_epoch) if ts_epoch > 0 else None
    stale = bool(age_seconds is None or age_seconds > float(max(60, int(stale_seconds))))
    threshold = max(1, int(fail_threshold))

    failed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        provider = str(row.get("provider") or "").strip().lower()
        if not provider:
            continue
        state_row = state_map.get(provider) if isinstance(state_map, dict) else None
        consecutive = int(
            (state_row or {}).get("consecutive_failures")
            if isinstance(state_row, dict)
            else (row.get("consecutive_failures") or 0)
        )
        row_ok = row.get("ok")
        if row_ok is False and consecutive >= threshold:
            failed.append(
                {
                    "provider": provider,
                    "status": str(row.get("status") or ""),
                    "error_type": str(row.get("error_type") or ""),
                    "error": str(row.get("error") or ""),
                    "consecutive_failures": consecutive,
                    "threshold": threshold,
                }
            )

    return {
        "enabled": True,
        "ok": bool((not stale) and (not failed)),
        "report_path": str(report_path),
        "ts": ts_iso,
        "age_seconds": (round(float(age_seconds), 3) if isinstance(age_seconds, (int, float)) else None),
        "stale": bool(stale),
        "provider_count": len([r for r in rows if isinstance(r, dict)]),
        "providers": rows,
        "failed_providers": failed,
        "fail_threshold": threshold,
    }


def _collect_open_incidents(
    *,
    db_path: Path,
    categories: list[str],
    lookback_minutes: int,
    limit: int,
) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "ok": False,
            "error": f"db_not_found:{db_path}",
            "categories": categories,
            "rows": [],
            "attention": False,
        }
    q_categories = [c for c in categories if c]
    if not q_categories:
        q_categories = ["ui_canary", "proxy"]
    cutoff = time.time() - float(max(1, int(lookback_minutes)) * 60)
    placeholders = ",".join("?" for _ in q_categories)
    sql = (
        "SELECT incident_id, category, severity, status, updated_at, last_seen_at, signature, count, evidence_dir "
        "FROM incidents "
        "WHERE status != 'resolved' AND updated_at >= ? AND category IN (" + placeholders + ") "
        "ORDER BY updated_at DESC LIMIT ?"
    )
    rows: list[dict[str, Any]] = []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql, [float(cutoff), *q_categories, int(max(1, limit))])
        for r in cur.fetchall():
            rows.append(
                {
                    "incident_id": str(r["incident_id"] or ""),
                    "category": str(r["category"] or ""),
                    "severity": str(r["severity"] or ""),
                    "status": str(r["status"] or ""),
                    "updated_at": float(r["updated_at"] or 0.0),
                    "last_seen_at": float(r["last_seen_at"] or 0.0),
                    "count": int(r["count"] or 0),
                    "signature": str(r["signature"] or ""),
                    "evidence_dir": (str(r["evidence_dir"] or "").strip() or None),
                }
            )
    finally:
        conn.close()
    return {
        "ok": True,
        "db_path": str(db_path),
        "categories": q_categories,
        "lookback_minutes": int(lookback_minutes),
        "rows": rows,
        "attention": bool(rows),
    }


def _run_orch_wake(
    *,
    openclaw_cmd: str,
    agent_id: str,
    session_id: str,
    timeout_seconds: int,
    report_path: Path,
) -> dict[str, Any]:
    prompt = (
        "你是 ChatgptREST orch agent。"
        "请读取巡检报告并只给最多 5 条可执行动作。"
        "禁止发起 Pro trivial/smoke 测试。"
        "只输出一行 JSON："
        '{"ok":true|false,"summary":"...","actions":[...],"escalate":true|false}。'
        f" 报告文件：{report_path}"
    )
    cmd = [
        openclaw_cmd,
        "agent",
        "--agent",
        agent_id,
        "--session-id",
        session_id,
        "--message",
        prompt,
        "--json",
        "--timeout",
        str(int(timeout_seconds)),
    ]
    started = time.time()
    proc = _run(cmd, timeout=max(30, int(timeout_seconds) + 15))
    parsed = _parse_json_loose(proc.stdout)
    payload_json: dict[str, Any] | None = None
    if isinstance(parsed, dict):
        result = parsed.get("result")
        payloads = (result or {}).get("payloads") if isinstance(result, dict) else None
        if isinstance(payloads, list) and payloads and isinstance(payloads[0], dict):
            text = str(payloads[0].get("text") or "")
            maybe = _parse_json_loose(text)
            if isinstance(maybe, dict):
                payload_json = maybe
    return {
        "ok": proc.returncode == 0,
        "returncode": int(proc.returncode),
        "elapsed_seconds": round(time.time() - started, 3),
        "command": cmd,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "payload_json": payload_json,
    }


def _load_wake_state(path: Path) -> dict[str, Any]:
    obj = _read_json(path)
    return obj if isinstance(obj, dict) else {}


def _write_wake_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _list_agents(openclaw_cmd: str, timeout: int) -> list[dict[str, Any]]:
    proc = _run([openclaw_cmd, "agents", "list", "--json"], timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"openclaw agents list failed rc={proc.returncode}: {(proc.stderr or proc.stdout).strip()}")
    parsed = _parse_json_loose(proc.stdout)
    if not isinstance(parsed, list):
        raise RuntimeError("openclaw agents list returned non-list JSON")
    out: list[dict[str, Any]] = []
    for row in parsed:
        if isinstance(row, dict):
            out.append(row)
    return out


def _delete_agent(openclaw_cmd: str, agent_id: str, timeout: int) -> dict[str, Any]:
    cmd = [openclaw_cmd, "agents", "delete", agent_id, "--force", "--json"]
    proc = _run(cmd, timeout=timeout)
    ok = proc.returncode == 0
    return {
        "op": "delete",
        "agent_id": agent_id,
        "ok": ok,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or ""),
        "stderr": (proc.stderr or ""),
    }


def _add_agent(openclaw_cmd: str, spec: AgentSpec, timeout: int) -> dict[str, Any]:
    cmd = [
        openclaw_cmd,
        "agents",
        "add",
        spec.agent_id,
        "--non-interactive",
        "--workspace",
        spec.workspace,
        "--model",
        spec.model,
        "--json",
    ]
    proc = _run(cmd, timeout=timeout)
    ok = proc.returncode == 0
    return {
        "op": "add",
        "agent_id": spec.agent_id,
        "ok": ok,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or ""),
        "stderr": (proc.stderr or ""),
    }


def _agent_ping(openclaw_cmd: str, spec: AgentSpec, timeout: int) -> dict[str, Any]:
    prompt = (
        "You are a healthcheck turn. Reply with one line JSON only: "
        '{"ok":true,"agent":"'
        + spec.agent_id
        + '"}.'
    )
    cmd = [
        openclaw_cmd,
        "agent",
        "--agent",
        spec.agent_id,
        "--session-id",
        spec.session_id,
        "--message",
        prompt,
        "--json",
        "--timeout",
        str(int(timeout)),
    ]
    started = time.time()
    proc = _run(cmd, timeout=max(10, int(timeout) + 10))
    elapsed = round(time.time() - started, 3)
    parsed = _parse_json_loose(proc.stdout)
    status = ""
    session_id = ""
    if isinstance(parsed, dict):
        status = str(parsed.get("status") or "")
        meta = (((parsed.get("result") or {}).get("meta") or {}).get("agentMeta") or {})
        if isinstance(meta, dict):
            session_id = str(meta.get("sessionId") or "")
    ok = proc.returncode == 0 and status == "ok"
    return {
        "agent_id": spec.agent_id,
        "expected_session_id": spec.session_id,
        "reported_session_id": session_id,
        "session_id_matches": (session_id == spec.session_id),
        "ok": ok,
        "status": status,
        "elapsed_seconds": elapsed,
        "returncode": proc.returncode,
    }


def _normalize_agent_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if "agentDir" in out and out["agentDir"] is not None:
        out["agentDir"] = str(out["agentDir"])
    if "workspace" in out and out["workspace"] is not None:
        out["workspace"] = str(out["workspace"])
    return out


def _reconcile(
    *,
    openclaw_cmd: str,
    timeout: int,
    specs: list[AgentSpec],
    do_reconcile: bool,
) -> dict[str, Any]:
    existing_rows = _list_agents(openclaw_cmd, timeout)
    existing: dict[str, dict[str, Any]] = {
        str(row.get("id")): _normalize_agent_row(row)
        for row in existing_rows
        if isinstance(row, dict) and row.get("id")
    }

    checks: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    for spec in specs:
        row = existing.get(spec.agent_id)
        if row is None:
            check = {
                "agent_id": spec.agent_id,
                "exists": False,
                "workspace_ok": False,
                "model_ok": False,
                "agent_dir_ok": False,
                "needs_reconcile": True,
            }
            checks.append(check)
            if do_reconcile:
                actions.append(_add_agent(openclaw_cmd, spec, timeout))
            continue

        workspace = str(row.get("workspace") or "")
        model = str(row.get("model") or "")
        agent_dir = str(row.get("agentDir") or "")
        workspace_ok = workspace == spec.workspace
        model_ok = model == spec.model
        agent_dir_ok = bool(agent_dir and Path(agent_dir).exists())
        agent_dir_required = _agent_dir_required(spec)
        agent_dir_effective_ok = bool(agent_dir_ok or (not agent_dir_required))
        needs_reconcile = not (workspace_ok and model_ok and agent_dir_effective_ok)
        checks.append(
            {
                "agent_id": spec.agent_id,
                "exists": True,
                "workspace": workspace,
                "workspace_ok": workspace_ok,
                "model": model,
                "model_ok": model_ok,
                "agent_dir": agent_dir,
                "agent_dir_required": agent_dir_required,
                "agent_dir_ok": agent_dir_ok,
                "agent_dir_effective_ok": agent_dir_effective_ok,
                "needs_reconcile": needs_reconcile,
            }
        )

        if do_reconcile and needs_reconcile:
            actions.append(_delete_agent(openclaw_cmd, spec.agent_id, timeout))
            actions.append(_add_agent(openclaw_cmd, spec, timeout))

    if do_reconcile:
        # Re-read after actions for final state.
        final_rows = _list_agents(openclaw_cmd, timeout)
        existing = {
            str(row.get("id")): _normalize_agent_row(row)
            for row in final_rows
            if isinstance(row, dict) and row.get("id")
        }
        refreshed: list[dict[str, Any]] = []
        for spec in specs:
            row = existing.get(spec.agent_id)
            workspace = str((row or {}).get("workspace") or "")
            model = str((row or {}).get("model") or "")
            agent_dir = str((row or {}).get("agentDir") or "")
            refreshed.append(
                {
                    "agent_id": spec.agent_id,
                    "exists": row is not None,
                    "workspace_ok": workspace == spec.workspace,
                    "model_ok": model == spec.model,
                    "agent_dir_required": _agent_dir_required(spec),
                    "agent_dir_ok": bool(agent_dir and Path(agent_dir).exists()),
                    "agent_dir_effective_ok": bool(
                        (agent_dir and Path(agent_dir).exists()) or (not _agent_dir_required(spec))
                    ),
                }
            )
        checks = refreshed

    ok = all(
        bool(c.get("exists") and c.get("workspace_ok") and c.get("model_ok") and c.get("agent_dir_effective_ok"))
        for c in checks
    )
    return {
        "ok": ok,
        "checks": checks,
        "actions": actions,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Bootstrap/reconcile OpenClaw ChatgptREST orchestrator agents.")
    p.add_argument("--openclaw-cmd", default=_default_openclaw_cmd())
    p.add_argument("--workspace", default=str(REPO_ROOT))
    p.add_argument("--db-path", default=str(DEFAULT_DB))
    p.add_argument("--timeout-seconds", type=int, default=90)
    p.add_argument("--reconcile", action="store_true", help="Recreate mismatched/missing-dir agents.")
    p.add_argument("--ping", action="store_true", help="Run one healthcheck turn for each required agent.")
    p.add_argument(
        "--ping-agent",
        action="append",
        default=[],
        help="Limit --ping to specific agent id(s); repeatable.",
    )
    p.add_argument(
        "--include-ui-canary",
        action="store_true",
        default=True,
        help="Include periodic UI canary report in orch doctor summary (default on).",
    )
    p.add_argument(
        "--no-include-ui-canary",
        dest="include_ui_canary",
        action="store_false",
        help="Skip UI canary report checks.",
    )
    p.add_argument("--ui-canary-report", default=str(DEFAULT_UI_CANARY_REPORT))
    p.add_argument("--ui-canary-stale-seconds", type=int, default=5400)
    p.add_argument("--ui-canary-fail-threshold", type=int, default=2)
    p.add_argument(
        "--incident-categories",
        default="ui_canary,proxy",
        help="Comma-separated incident categories considered by orch doctor.",
    )
    p.add_argument("--incident-lookback-minutes", type=int, default=180)
    p.add_argument("--incident-open-limit", type=int, default=50)
    p.add_argument("--wake-on-attention", action="store_true", help="Wake orch agent when doctor report needs attention.")
    p.add_argument("--wake-agent-id", default="chatgptrest-orch")
    p.add_argument("--wake-session-id", default="chatgptrest-orch-main")
    p.add_argument("--wake-timeout-seconds", type=int, default=180)
    p.add_argument("--wake-cooldown-seconds", type=int, default=1800)
    p.add_argument("--wake-state-file", default=str(DEFAULT_WAKE_STATE))
    p.add_argument("--report-out", default=str(DEFAULT_REPORT))
    p.add_argument("--strict", action="store_true", help="Exit non-zero when any check fails.")
    return p


def main() -> int:
    args = build_parser().parse_args()
    specs = _required_agents(Path(str(args.workspace)).expanduser())
    db_path = Path(str(args.db_path)).expanduser()

    started = time.time()
    reconcile = _reconcile(
        openclaw_cmd=str(args.openclaw_cmd),
        timeout=max(10, int(args.timeout_seconds)),
        specs=specs,
        do_reconcile=bool(args.reconcile),
    )

    pings: list[dict[str, Any]] = []
    if bool(args.ping):
        wanted = {str(x).strip() for x in (args.ping_agent or []) if str(x).strip()}
        ping_specs = [s for s in specs if (not wanted or s.agent_id in wanted)]
        for spec in ping_specs:
            pings.append(
                _agent_ping(
                    openclaw_cmd=str(args.openclaw_cmd),
                    spec=spec,
                    timeout=max(15, int(args.timeout_seconds)),
                )
            )

    ui_canary_report: dict[str, Any]
    if bool(args.include_ui_canary):
        ui_canary_report = _collect_ui_canary_report(
            report_path=Path(str(args.ui_canary_report)).expanduser(),
            stale_seconds=max(60, int(args.ui_canary_stale_seconds)),
            fail_threshold=max(1, int(args.ui_canary_fail_threshold)),
        )
    else:
        ui_canary_report = {"enabled": False, "ok": True, "reason": "disabled"}

    categories = [x.strip() for x in str(args.incident_categories or "").split(",") if x.strip()]
    incidents_report = _collect_open_incidents(
        db_path=db_path,
        categories=categories,
        lookback_minutes=max(1, int(args.incident_lookback_minutes)),
        limit=max(1, int(args.incident_open_limit)),
    )

    reconcile_ok = bool(reconcile.get("ok"))
    ping_ok = all(bool(x.get("ok")) for x in pings)
    ui_ok = bool(ui_canary_report.get("ok"))
    incidents_attention = bool(incidents_report.get("attention"))
    needs_attention = bool((not reconcile_ok) or (not ping_ok) or (not ui_ok) or incidents_attention)

    attention_reasons: list[str] = []
    if not reconcile_ok:
        attention_reasons.append("reconcile_not_ok")
    if not ping_ok:
        attention_reasons.append("ping_not_ok")
    if bool(args.include_ui_canary) and not ui_ok:
        if bool(ui_canary_report.get("stale")):
            attention_reasons.append("ui_canary_stale")
        if ui_canary_report.get("failed_providers"):
            attention_reasons.append("ui_canary_failed")
        if not ui_canary_report.get("failed_providers") and not bool(ui_canary_report.get("stale")):
            attention_reasons.append("ui_canary_not_ok")
    if incidents_attention:
        attention_reasons.append("open_incidents")

    wake_result: dict[str, Any] | None = None
    if bool(args.wake_on_attention) and needs_attention:
        wake_state_path = Path(str(args.wake_state_file)).expanduser()
        wake_state = _load_wake_state(wake_state_path)
        now = time.time()
        last_wake_ts = float(wake_state.get("last_wake_ts") or 0.0)
        cooldown = float(max(60, int(args.wake_cooldown_seconds)))
        if last_wake_ts > 0 and (now - last_wake_ts) < cooldown:
            wake_result = {
                "ok": True,
                "skipped": True,
                "reason": "cooldown",
                "seconds_since_last": round(now - last_wake_ts, 3),
                "cooldown_seconds": int(cooldown),
            }
        else:
            out_path_preview = Path(str(args.report_out)).expanduser()
            wake_result = _run_orch_wake(
                openclaw_cmd=str(args.openclaw_cmd),
                agent_id=str(args.wake_agent_id),
                session_id=str(args.wake_session_id),
                timeout_seconds=max(30, int(args.wake_timeout_seconds)),
                report_path=out_path_preview,
            )
            if bool(wake_result.get("ok")):
                _write_wake_state(
                    wake_state_path,
                    {
                        "last_wake_ts": float(now),
                        "updated_at": float(now),
                        "report_path": str(out_path_preview),
                        "attention_reasons": attention_reasons,
                    },
                )

    report = {
        "ok": bool(reconcile_ok and ping_ok and ui_ok and (not incidents_attention)),
        "needs_attention": bool(needs_attention),
        "attention_reasons": attention_reasons,
        "generated_at": time.time(),
        "elapsed_seconds": round(time.time() - started, 3),
        "reconcile": reconcile,
        "pings": pings,
        "ui_canary": ui_canary_report,
        "incidents": incidents_report,
        "wake_result": wake_result,
        "required_agents": [spec.__dict__ for spec in specs],
    }
    out_path = Path(str(args.report_out)).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "report_path": str(out_path), "summary": report}, ensure_ascii=False, indent=2))

    if bool(args.strict) and not bool(report["ok"]):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
