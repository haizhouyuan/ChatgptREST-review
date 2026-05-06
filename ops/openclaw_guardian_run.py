#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_DB = "/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3"
DEFAULT_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_REPORT = "/vol1/1000/projects/ChatgptREST/artifacts/monitor/openclaw_guardian/latest_report.json"
DEFAULT_ORCH_REPORT = "/vol1/1000/projects/ChatgptREST/artifacts/monitor/openclaw_orch/latest_report.json"
DEFAULT_OPENCLAW = "openclaw"
# Aligned with config/topology.yaml sidecars.guardian (Issue #126)
DEFAULT_AGENT_ID = "main"
DEFAULT_SESSION_ID = "main-guardian"

TRIVIAL_EXACT = {
    "ok",
    "yes",
    "no",
    "ping",
    "test",
    "hello",
    "你好",
    "测试",
    "请回复ok",
    "回复ok",
}

VIOLATION_ACTIVE_STATUSES = {"queued", "in_progress", "cooldown", "blocked", "needs_followup"}
_SYSTEM_CLIENT_PREFIXES = (
    "maint_daemon",
    "openclaw_guardian",
    "chatgptrest-guardian",
    "repair",
    "sre",
)

logger = logging.getLogger(__name__)
_MISSING_TOKEN_WARNING_EMITTED = False


def _resolve_openclaw_cmd(raw_cmd: str) -> str:
    cmd = str(raw_cmd or "").strip() or DEFAULT_OPENCLAW
    if os.path.sep in cmd:
        return str(Path(cmd).expanduser())
    which = shutil.which(cmd)
    if which:
        return which
    candidate_roots = [Path.home()]
    if Path.home().name != ".home-codex-official":
        candidate_roots.append(Path.home() / ".home-codex-official")
    for candidate in [root / ".local" / "bin" / cmd for root in candidate_roots]:
        if candidate.exists():
            return str(candidate)
    return cmd


def _default_openclaw_cmd() -> str:
    env_cmd = str(os.environ.get("OPENCLAW_CMD") or "").strip()
    if env_cmd:
        return _resolve_openclaw_cmd(env_cmd)
    return _resolve_openclaw_cmd(DEFAULT_OPENCLAW)


def _is_pro_preset(preset: str) -> bool:
    return str(preset or "").strip().lower().startswith("pro")


def _is_trivial_prompt(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return True
    normalized = "".join(s.split()).lower()
    if normalized in TRIVIAL_EXACT:
        return True
    if len(normalized) <= 4 and normalized.isalpha():
        return True
    if len(normalized) <= 4 and normalized.isdigit():
        return True
    if normalized in {"请回复ok", "回复ok"}:
        return True
    return False


def _chatgptrest_auth_headers(*, url: str) -> dict[str, str]:
    path = str(urllib.parse.urlsplit(url).path or "").strip()
    api_token = str(os.environ.get("CHATGPTREST_API_TOKEN") or "").strip()
    ops_token = str(os.environ.get("CHATGPTREST_OPS_TOKEN") or "").strip()
    token = ""
    if path.startswith("/v1/ops/"):
        token = ops_token or api_token
    else:
        token = api_token or ops_token
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _warn_if_missing_chatgptrest_tokens() -> None:
    global _MISSING_TOKEN_WARNING_EMITTED
    if _MISSING_TOKEN_WARNING_EMITTED:
        return
    api_token = str(os.environ.get("CHATGPTREST_API_TOKEN") or "").strip()
    ops_token = str(os.environ.get("CHATGPTREST_OPS_TOKEN") or "").strip()
    if api_token or ops_token:
        return
    logger.warning(
        "guardian is running without CHATGPTREST_API_TOKEN/CHATGPTREST_OPS_TOKEN; "
        "authenticated ChatgptREST probes may fail with 401"
    )
    _MISSING_TOKEN_WARNING_EMITTED = True


def _api_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{str(path or '').lstrip('/')}"


def _auth_headers_for_url(url: str) -> dict[str, str]:
    return _chatgptrest_auth_headers(url=url)


def _http_json(url: str, timeout_seconds: float, *, headers: dict[str, str] | None = None) -> tuple[bool, Any]:
    request_headers = {
        **_auth_headers_for_url(url),
        **dict(headers or {}),
    }
    req = urllib.request.Request(url=url, method="GET", headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return True, json.loads(raw)
            except Exception:
                return True, {"raw": raw, "status": int(getattr(resp, "status", 200))}
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(exc)
        return False, {"error": f"HTTP {exc.code}", "body": body}
    except Exception as exc:
        return False, {"error": f"{type(exc).__name__}: {exc}"}


def _http_json_request(
    *,
    method: str,
    url: str,
    timeout_seconds: float,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[bool, Any, int | None]:
    data = None
    request_headers = {
        "Accept": "application/json",
        **_auth_headers_for_url(url),
        **dict(headers or {}),
    }
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, method=method.upper(), headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status = int(getattr(resp, "status", 200))
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw.strip() else {}
            except Exception:
                payload = {"raw": raw}
            return True, payload, status
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw = str(exc)
        try:
            payload = json.loads(raw) if raw.strip() else {"error": f"HTTP {int(exc.code)}"}
        except Exception:
            payload = {"error": f"HTTP {int(exc.code)}", "raw": raw}
        return False, payload, int(exc.code)
    except Exception as exc:
        return False, {"error": f"{type(exc).__name__}: {exc}"}, None


def _safe_json_load(text: str) -> dict[str, Any]:
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {}


def _client_name_from_job_client(client_payload: dict[str, Any]) -> str:
    for key in ("name", "project", "client_name"):
        value = client_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def _is_system_client_name(name: str) -> bool:
    raw = str(name or "").strip().lower()
    if not raw:
        return True
    return any(raw.startswith(prefix) for prefix in _SYSTEM_CLIENT_PREFIXES)


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _extract_last_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    s = str(text or "")
    for i in range(len(s) - 1, -1, -1):
        if s[i] != "{":
            continue
        try:
            obj, end = decoder.raw_decode(s[i:])
        except Exception:
            continue
        if isinstance(obj, dict) and not s[i + end :].strip():
            return obj
    return None


def _resolve_guardian_agent_target(agent_id: str, session_id: str) -> tuple[str, str]:
    requested_agent = str(agent_id or "").strip() or DEFAULT_AGENT_ID
    requested_session = str(session_id or "").strip() or DEFAULT_SESSION_ID
    state_dir = Path(
        str(os.environ.get("OPENCLAW_STATE_DIR") or (Path.home() / ".openclaw")).strip()
    ).expanduser()
    requested_dir = state_dir / "agents" / requested_agent
    if requested_dir.exists():
        return requested_agent, requested_session
    main_dir = state_dir / "agents" / "main"
    if main_dir.exists():
        return "main", requested_session
    return requested_agent, requested_session


def _collect_report(
    db_path: Path,
    base_url: str,
    lookback_minutes: int,
    max_rows: int,
    *,
    include_orch_report: bool,
    orch_report_path: Path,
) -> dict[str, Any]:
    now = time.time()
    cutoff = now - max(1, int(lookback_minutes)) * 60
    _warn_if_missing_chatgptrest_tokens()

    health_url = _api_url(base_url, "/healthz")
    ops_url = _api_url(base_url, "/v1/ops/status")
    health_ok, health = _http_json(
        health_url,
        timeout_seconds=5,
        headers=_chatgptrest_auth_headers(url=health_url),
    )
    ops_ok, ops = _http_json(
        ops_url,
        timeout_seconds=5,
        headers=_chatgptrest_auth_headers(url=ops_url),
    )

    rows: list[sqlite3.Row] = []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT job_id, kind, status, phase, created_at, updated_at,
                   input_json, params_json, last_error_type, last_error
            FROM jobs
            WHERE updated_at >= ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (cutoff, int(max_rows)),
        )
        rows = list(cur.fetchall())
    finally:
        conn.close()

    anomalies: list[dict[str, Any]] = []
    policy_violations: list[dict[str, Any]] = []

    for row in rows:
        job_id = str(row["job_id"])
        kind = str(row["kind"])
        status = str(row["status"])
        phase = str(row["phase"])
        input_obj = _safe_json_load(str(row["input_json"] or "{}"))
        params_obj = _safe_json_load(str(row["params_json"] or "{}"))
        question = str(input_obj.get("question") or "").strip()
        preset = str(params_obj.get("preset") or "").strip()

        if status in {"error", "blocked", "cooldown", "needs_followup"}:
            anomalies.append(
                {
                    "job_id": job_id,
                    "kind": kind,
                    "status": status,
                    "phase": phase,
                    "updated_at": float(row["updated_at"]),
                    "last_error_type": row["last_error_type"],
                    "last_error": row["last_error"],
                    "preset": preset,
                }
            )

        if (
            kind == "chatgpt_web.ask"
            and status in VIOLATION_ACTIVE_STATUSES
            and _is_pro_preset(preset)
            and _is_trivial_prompt(question)
        ):
            policy_violations.append(
                {
                    "job_id": job_id,
                    "status": status,
                    "phase": phase,
                    "updated_at": float(row["updated_at"]),
                    "preset": preset,
                    "question": question,
                }
            )

    orch_report: dict[str, Any] | None = None
    orch_attention = False
    if bool(include_orch_report):
        orch_report = _read_json_file(orch_report_path)
        if isinstance(orch_report, dict):
            orch_attention = bool(
                orch_report.get("needs_attention")
                or (orch_report.get("ok") is False)
                or bool(orch_report.get("attention_reasons"))
            )
        else:
            orch_attention = True
            orch_report = {
                "ok": False,
                "needs_attention": True,
                "error_type": "OrchReportMissingOrInvalid",
                "report_path": str(orch_report_path),
            }

    report = {
        "ok": bool(health_ok and ops_ok and (not orch_attention)),
        "generated_at": now,
        "lookback_minutes": int(lookback_minutes),
        "base_url": base_url,
        "db_path": str(db_path),
        "health": {"ok": health_ok, "payload": health},
        "ops_status": {"ok": ops_ok, "payload": ops},
        "anomalies": anomalies,
        "policy_violations": policy_violations,
        "orch_report": orch_report,
        "needs_attention": bool((not health_ok) or (not ops_ok) or anomalies or policy_violations or orch_attention),
    }
    return report


def _run_guardian_agent(
    *,
    openclaw_cmd: str,
    agent_id: str,
    session_id: str,
    report_path: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    resolved_cmd = _resolve_openclaw_cmd(openclaw_cmd)
    resolved_agent_id, resolved_session_id = _resolve_guardian_agent_target(agent_id, session_id)
    prompt = (
        "你是 ChatgptREST 托管巡查 agent。"
        "请只做最小必要动作：先读巡查报告文件，再处理可自动修复项。"
        "异常 job 可执行 /wait 或 repair.check；禁止发送新的 Pro 测试问题。"
        "若有 policy_violation（例如 Pro 上的\"请回复OK\"）仅登记为未解决，不要重发测试。"
        "不要调用 ops/openclaw_orch_agent.py --reconcile；legacy chatgptrest-* orch/worker 拓扑不属于当前主基线。"
        "最后只输出一行 JSON："
        '{"resolved":true|false,"summary":"...","actions":["..."],"unresolved":["..."]}。'
        f"报告文件：{report_path}"
    )
    cmd = [
        resolved_cmd,
        "agent",
        "--agent",
        resolved_agent_id,
        "--session-id",
        resolved_session_id,
        "--message",
        prompt,
        "--json",
        "--timeout",
        str(int(timeout_seconds)),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": None,
            "command": cmd,
            "resolved": False,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "top": None,
            "payload_json": None,
            "requested_agent_id": str(agent_id),
            "resolved_agent_id": str(resolved_agent_id),
            "resolved_session_id": str(resolved_session_id),
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": None,
            "command": cmd,
            "resolved": False,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "top": None,
            "payload_json": None,
            "requested_agent_id": str(agent_id),
            "resolved_agent_id": str(resolved_agent_id),
            "resolved_session_id": str(resolved_session_id),
        }
    output = (proc.stdout or "")
    top = _extract_last_json_object(output)

    payload_text = ""
    if isinstance(top, dict):
        payloads = (((top.get("result") or {}).get("payloads") or []))
        if payloads and isinstance(payloads[0], dict):
            payload_text = str(payloads[0].get("text") or "")

    parsed_payload = _extract_last_json_object(payload_text) if payload_text else None
    resolved = bool(parsed_payload.get("resolved")) if isinstance(parsed_payload, dict) else False
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "command": cmd,
        "resolved": resolved,
        "stdout": output,
        "stderr": (proc.stderr or ""),
        "top": top,
        "payload_json": parsed_payload,
        "requested_agent_id": str(agent_id),
        "resolved_agent_id": str(resolved_agent_id),
        "resolved_session_id": str(resolved_session_id),
    }


def _notify_feishu_webhook(webhook_url: str, text: str, timeout_seconds: float) -> dict[str, Any]:
    body = {
        "msg_type": "text",
        "content": {
            "text": text,
        },
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": int(getattr(resp, "status", 200)), "raw": raw}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _notify_feishu_channel(
    *,
    openclaw_cmd: str,
    target: str,
    text: str,
    account: str | None,
) -> dict[str, Any]:
    resolved_cmd = _resolve_openclaw_cmd(openclaw_cmd)
    cmd = [
        resolved_cmd,
        "message",
        "send",
        "--channel",
        "feishu",
        "--target",
        target,
        "--message",
        text,
        "--json",
    ]
    if account:
        cmd.extend(["--account", account])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "command": cmd,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "command": cmd,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "command": cmd,
    }


def _brief_alert(report: dict[str, Any], agent_result: dict[str, Any] | None) -> str:
    anomalies = report.get("anomalies") or []
    violations = report.get("policy_violations") or []
    orch_report = report.get("orch_report") if isinstance(report.get("orch_report"), dict) else {}
    lines = [
        "[ChatgptREST Guardian告警]",
        f"巡查时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(report.get('generated_at') or time.time())))}",
        f"health_ok={report.get('health', {}).get('ok')} ops_ok={report.get('ops_status', {}).get('ok')}",
        f"anomalies={len(anomalies)} policy_violations={len(violations)}",
    ]
    if orch_report:
        lines.append(
            f"orch_ok={orch_report.get('ok')} orch_needs_attention={orch_report.get('needs_attention')}"
        )
    if anomalies:
        lines.append(f"异常示例job_id={anomalies[0].get('job_id')} status={anomalies[0].get('status')}")
    if violations:
        lines.append(
            f"违规示例job_id={violations[0].get('job_id')} prompt={violations[0].get('question')}"
        )
    if agent_result is not None:
        lines.append(
            f"agent_attempt_ok={agent_result.get('ok')} resolved={agent_result.get('resolved')}"
        )
    lines.append("请检查 /vol1/1000/projects/ChatgptREST/artifacts/monitor/openclaw_guardian/latest_report.json")
    return "\n".join(lines)


def _iter_client_issues(
    *,
    base_url: str,
    statuses: list[str],
    source: str,
    page_limit: int,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    base = base_url.rstrip("/")
    out: list[dict[str, Any]] = []
    before_ts: float | None = None
    before_issue_id: str | None = None
    for _ in range(20):
        query: dict[str, str] = {
            "status": ",".join(statuses),
            "source": source,
            "limit": str(int(max(1, page_limit))),
        }
        if before_ts is not None:
            query["before_ts"] = str(float(before_ts))
        if before_issue_id:
            query["before_issue_id"] = str(before_issue_id)
        qs = urllib.parse.urlencode(query)
        url = _api_url(base, f"/v1/issues?{qs}")
        ok, payload, _status = _http_json_request(
            method="GET",
            url=url,
            timeout_seconds=timeout_seconds,
            headers=_chatgptrest_auth_headers(url=url),
        )
        if not ok or not isinstance(payload, dict):
            break
        rows = payload.get("issues")
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            if isinstance(row, dict):
                out.append(row)
        nbt = payload.get("next_before_ts")
        nbi = payload.get("next_before_issue_id")
        if nbt is None or nbi is None:
            break
        try:
            before_ts = float(nbt)
        except Exception:
            break
        before_issue_id = str(nbi)
    return out


def _sweep_client_issue_autoclose(
    *,
    base_url: str,
    stale_hours: int,
    max_updates: int,
    source: str,
    statuses: list[str],
    actor: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    if int(stale_hours) <= 0 or int(max_updates) <= 0:
        return {
            "enabled": False,
            "stale_hours": int(stale_hours),
            "max_updates": int(max_updates),
            "source": source,
            "statuses": statuses,
            "listed": 0,
            "eligible": 0,
            "updated": 0,
            "failures": [],
            "updated_issue_ids": [],
        }

    now = time.time()
    cutoff = now - (float(max(1, int(stale_hours))) * 3600.0)
    listed = _iter_client_issues(
        base_url=base_url,
        statuses=statuses,
        source=source,
        page_limit=200,
        timeout_seconds=timeout_seconds,
    )

    candidates: list[dict[str, Any]] = []
    for issue in listed:
        try:
            last_seen = float(issue.get("last_seen_at") or issue.get("updated_at") or 0.0)
        except Exception:
            last_seen = 0.0
        if last_seen <= cutoff:
            candidates.append(issue)
    candidates = sorted(
        candidates,
        key=lambda x: float(x.get("last_seen_at") or x.get("updated_at") or 0.0),
    )

    updated_issue_ids: list[str] = []
    failures: list[dict[str, Any]] = []
    for issue in candidates[: int(max_updates)]:
        issue_id = str(issue.get("issue_id") or "").strip()
        if not issue_id:
            continue
        last_seen = float(issue.get("last_seen_at") or issue.get("updated_at") or 0.0)
        quiet_hours = max(0.0, (now - last_seen) / 3600.0)
        issue_url = _api_url(base_url, f"/v1/issues/{urllib.parse.quote(issue_id)}/status")
        body = {
            "status": "mitigated",
            "actor": actor,
            "note": f"guardian auto-mitigated: no recurrence in {quiet_hours:.1f}h",
            "linked_job_id": issue.get("latest_job_id"),
            "metadata": {
                "auto": True,
                "source": "openclaw_guardian",
                "quiet_hours": round(quiet_hours, 3),
                "stale_hours_threshold": int(stale_hours),
                "verification_type": "quiet_window",
                "verification": {
                    "type": "quiet_window",
                    "status": "passed",
                    "verifier": actor,
                    "job_id": issue.get("latest_job_id"),
                    "metadata": {
                        "quiet_hours": round(quiet_hours, 3),
                        "stale_hours_threshold": int(stale_hours),
                    },
                },
            },
        }
        ok, payload, status = _http_json_request(
            method="POST",
            url=issue_url,
            body=body,
            timeout_seconds=timeout_seconds,
            headers=_chatgptrest_auth_headers(url=issue_url),
        )
        if ok:
            updated_issue_ids.append(issue_id)
        else:
            failures.append({"issue_id": issue_id, "status": status, "payload": payload})

    return {
        "enabled": True,
        "stale_hours": int(stale_hours),
        "max_updates": int(max_updates),
        "source": source,
        "statuses": statuses,
        "listed": len(listed),
        "eligible": len(candidates),
        "updated": len(updated_issue_ids),
        "failures": failures,
        "updated_issue_ids": updated_issue_ids,
    }


def _latest_mitigated_ts(conn: sqlite3.Connection, *, issue_id: str) -> float | None:
    rows = conn.execute(
        """
        SELECT ts, payload_json
        FROM client_issue_events
        WHERE issue_id = ?
          AND type = 'issue_status_updated'
        ORDER BY id DESC
        LIMIT 100
        """,
        (str(issue_id),),
    ).fetchall()
    for row in rows:
        payload = _safe_json_load(str(row["payload_json"] or "{}"))
        if str(payload.get("to") or "").strip().lower() == "mitigated":
            try:
                return float(row["ts"])
            except Exception:
                return None
    return None


def _issue_recurred_since(conn: sqlite3.Connection, *, issue_id: str, since_ts: float) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM client_issue_events
        WHERE issue_id = ?
          AND type = 'issue_reported'
          AND ts > ?
        LIMIT 1
        """,
        (str(issue_id), float(since_ts)),
    ).fetchone()
    return row is not None


def _qualifying_successes_since(
    conn: sqlite3.Connection,
    *,
    issue: dict[str, Any],
    since_ts: float,
    limit: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT job_id, kind, status, created_at, updated_at, client_json, answer_chars
        FROM jobs
        WHERE kind = ?
          AND status = 'completed'
          AND created_at > ?
        ORDER BY created_at ASC, job_id ASC
        LIMIT ?
        """,
        (
            str(issue.get("kind") or ""),
            float(since_ts),
            max(1, int(limit * 10)),
        ),
    ).fetchall()
    out: list[dict[str, Any]] = []
    target_project = str(issue.get("project") or "").strip().lower()
    for row in rows:
        payload = _safe_json_load(str(row["client_json"] or "{}"))
        client_name = _client_name_from_job_client(payload)
        if _is_system_client_name(client_name):
            continue
        if target_project and client_name.strip().lower() != target_project:
            continue
        out.append(
            {
                "job_id": str(row["job_id"] or ""),
                "client_name": client_name,
                "created_at": float(row["created_at"] or 0.0),
                "updated_at": float(row["updated_at"] or 0.0),
                "answer_chars": (int(row["answer_chars"]) if row["answer_chars"] is not None else None),
            }
        )
        if len(out) >= int(limit):
            break
    return out


def _sweep_client_issue_autoclose_closed(
    *,
    db_path: Path,
    base_url: str,
    source: str,
    actor: str,
    timeout_seconds: float,
    required_successes: int,
    max_updates: int,
) -> dict[str, Any]:
    if int(required_successes) <= 0 or int(max_updates) <= 0:
        return {
            "enabled": False,
            "required_successes": int(required_successes),
            "max_updates": int(max_updates),
            "source": source,
            "listed": 0,
            "eligible": 0,
            "updated": 0,
            "failures": [],
            "updated_issue_ids": [],
        }

    with sqlite3.connect(str(db_path), timeout=30.0) as conn:
        conn.row_factory = sqlite3.Row
        listed = conn.execute(
            """
            SELECT issue_id, project, kind, status, source, updated_at, latest_job_id
            FROM client_issues
            WHERE status = 'mitigated'
              AND source = ?
            ORDER BY updated_at ASC, issue_id ASC
            LIMIT ?
            """,
            (str(source), max(1, int(max_updates * 20))),
        ).fetchall()

        candidates: list[dict[str, Any]] = []
        for row in listed:
            issue = {
                "issue_id": str(row["issue_id"] or "").strip(),
                "project": str(row["project"] or "").strip(),
                "kind": str(row["kind"] or "").strip(),
                "status": str(row["status"] or "").strip(),
                "source": str(row["source"] or "").strip(),
                "updated_at": float(row["updated_at"] or 0.0),
                "latest_job_id": (str(row["latest_job_id"]).strip() if row["latest_job_id"] is not None else None) or None,
            }
            if not issue["issue_id"] or not issue["kind"]:
                continue
            mitigated_ts = _latest_mitigated_ts(conn, issue_id=issue["issue_id"])
            if mitigated_ts is None:
                continue
            if _issue_recurred_since(conn, issue_id=issue["issue_id"], since_ts=mitigated_ts):
                continue
            successes = _qualifying_successes_since(
                conn,
                issue=issue,
                since_ts=mitigated_ts,
                limit=int(required_successes),
            )
            if len(successes) < int(required_successes):
                continue
            candidates.append(
                {
                    **issue,
                    "mitigated_ts": mitigated_ts,
                    "qualifying_successes": successes,
                }
            )

    updated_issue_ids: list[str] = []
    failures: list[dict[str, Any]] = []
    for issue in candidates[: int(max_updates)]:
        sample_jobs = [row["job_id"] for row in issue["qualifying_successes"]]
        issue_url = _api_url(base_url, f"/v1/issues/{urllib.parse.quote(str(issue['issue_id']))}/status")
        body = {
            "status": "closed",
            "actor": actor,
            "note": f"guardian auto-closed: {len(sample_jobs)} qualifying client successes after mitigated",
            "linked_job_id": sample_jobs[-1] if sample_jobs else issue.get("latest_job_id"),
            "metadata": {
                "auto": True,
                "source": "openclaw_guardian",
                "required_successes": int(required_successes),
                "qualifying_success_job_ids": sample_jobs,
                "qualifying_successes": issue["qualifying_successes"],
                "mitigated_ts": float(issue["mitigated_ts"]),
            },
        }
        ok, payload, status = _http_json_request(
            method="POST",
            url=issue_url,
            body=body,
            timeout_seconds=timeout_seconds,
            headers=_chatgptrest_auth_headers(url=issue_url),
        )
        if ok:
            updated_issue_ids.append(str(issue["issue_id"]))
        else:
            failures.append({"issue_id": issue["issue_id"], "status": status, "payload": payload})

    return {
        "enabled": True,
        "required_successes": int(required_successes),
        "max_updates": int(max_updates),
        "source": source,
        "listed": len(listed),
        "eligible": len(candidates),
        "updated": len(updated_issue_ids),
        "failures": failures,
        "updated_issue_ids": updated_issue_ids,
    }


def _apply_projection_only_mode(args: argparse.Namespace) -> argparse.Namespace:
    if not bool(getattr(args, "projection_only", False)):
        return args
    args.no_autofix = True
    args.no_notify = True
    args.include_orch_report = False
    return args


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChatgptREST guardian runner: inspect -> attempt fix -> notify")
    p.add_argument("--db-path", default=DEFAULT_DB)
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--lookback-minutes", type=int, default=30)
    p.add_argument("--max-rows", type=int, default=200)
    p.add_argument("--orch-report-path", default=DEFAULT_ORCH_REPORT)
    p.add_argument("--include-orch-report", action="store_true", default=True)
    p.add_argument("--no-include-orch-report", dest="include_orch_report", action="store_false")
    p.add_argument("--report-out", default=DEFAULT_REPORT)

    p.add_argument("--openclaw-cmd", default=_default_openclaw_cmd())
    p.add_argument("--agent-id", default=DEFAULT_AGENT_ID)
    p.add_argument("--session-id", default=DEFAULT_SESSION_ID)
    p.add_argument("--agent-timeout-seconds", type=int, default=180)
    p.add_argument("--no-autofix", action="store_true")
    p.add_argument(
        "--projection-only",
        action="store_true",
        help="Refresh latest_report in read-only mode (implies --no-autofix --no-notify --no-include-orch-report).",
    )

    p.add_argument("--notify-webhook-url", default="")
    p.add_argument("--notify-feishu-target", default="")
    p.add_argument("--notify-feishu-account", default="")
    p.add_argument("--no-notify", action="store_true")

    p.add_argument(
        "--client-issue-autoclose-hours",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_HOURS") or 72),
        help="Auto-mark stale worker_auto client issues as mitigated after N quiet hours (0=disable).",
    )
    p.add_argument(
        "--client-issue-autoclose-max",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_MAX") or 50),
        help="Max stale client issues to auto-mitigate per guardian run.",
    )
    p.add_argument(
        "--client-issue-source",
        default=os.environ.get("CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_SOURCE") or "worker_auto",
        help="Issue source filter for autoclose sweep.",
    )
    p.add_argument(
        "--client-issue-statuses",
        default=os.environ.get("CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_STATUSES") or "open,in_progress",
        help="Comma-separated issue statuses eligible for autoclose sweep.",
    )
    p.add_argument(
        "--client-issue-actor",
        default=os.environ.get("CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_ACTOR") or "openclaw_guardian",
        help="Actor name written to issue status updates.",
    )
    p.add_argument(
        "--client-issue-close-after-successes",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CLIENT_ISSUE_CLOSE_AFTER_SUCCESSES") or 3),
        help="Auto-close mitigated issues after N qualifying client successes (0=disable).",
    )
    p.add_argument(
        "--client-issue-close-max",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CLIENT_ISSUE_CLOSE_MAX") or 20),
        help="Max mitigated issues to auto-close per guardian run.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _apply_projection_only_mode(build_parser().parse_args(argv))

    db_path = Path(str(args.db_path)).expanduser()
    report = _collect_report(
        db_path=db_path,
        base_url=str(args.base_url),
        lookback_minutes=int(args.lookback_minutes),
        max_rows=int(args.max_rows),
        include_orch_report=bool(args.include_orch_report),
        orch_report_path=Path(str(args.orch_report_path)).expanduser(),
    )

    report_path = Path(str(args.report_out)).expanduser()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    statuses = [x.strip() for x in str(args.client_issue_statuses or "").split(",") if x.strip()]
    if not statuses:
        statuses = ["open", "in_progress"]
    if bool(args.no_autofix):
        issue_sweep = {
            "enabled": False,
            "reason": "disabled_by_no_autofix",
            "stale_hours": int(args.client_issue_autoclose_hours),
            "max_updates": int(args.client_issue_autoclose_max),
            "source": str(args.client_issue_source),
            "statuses": statuses,
            "listed": 0,
            "eligible": 0,
            "updated": 0,
            "failures": [],
            "updated_issue_ids": [],
        }
    else:
        issue_sweep = _sweep_client_issue_autoclose(
            base_url=str(args.base_url),
            stale_hours=int(args.client_issue_autoclose_hours),
            max_updates=int(args.client_issue_autoclose_max),
            source=str(args.client_issue_source),
            statuses=statuses,
            actor=str(args.client_issue_actor),
            timeout_seconds=8.0,
        )
    report["client_issue_sweep"] = issue_sweep
    if bool(args.no_autofix):
        close_sweep = {
            "enabled": False,
            "reason": "disabled_by_no_autofix",
            "required_successes": int(args.client_issue_close_after_successes),
            "max_updates": int(args.client_issue_close_max),
            "source": str(args.client_issue_source),
            "listed": 0,
            "eligible": 0,
            "updated": 0,
            "failures": [],
            "updated_issue_ids": [],
        }
    else:
        close_sweep = _sweep_client_issue_autoclose_closed(
            db_path=db_path,
            base_url=str(args.base_url),
            source=str(args.client_issue_source),
            actor=str(args.client_issue_actor),
            timeout_seconds=8.0,
            required_successes=int(args.client_issue_close_after_successes),
            max_updates=int(args.client_issue_close_max),
        )
    report["client_issue_close_sweep"] = close_sweep
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    agent_result: dict[str, Any] | None = None
    resolved = not bool(report.get("needs_attention"))

    if report.get("needs_attention") and not bool(args.no_autofix):
        agent_result = _run_guardian_agent(
            openclaw_cmd=str(args.openclaw_cmd),
            agent_id=str(args.agent_id),
            session_id=str(args.session_id),
            report_path=report_path,
            timeout_seconds=int(args.agent_timeout_seconds),
        )
        resolved = bool(agent_result.get("ok") and agent_result.get("resolved"))

    notify_result: dict[str, Any] | None = None
    if report.get("needs_attention") and (not resolved) and (not bool(args.no_notify)):
        alert_text = _brief_alert(report, agent_result)
        webhook = str(args.notify_webhook_url or "").strip() or str((os.environ.get("FEISHU_BOT_WEBHOOK_URL") or "")).strip()
        if webhook:
            notify_result = _notify_feishu_webhook(webhook, alert_text, timeout_seconds=8)
        else:
            target = str(args.notify_feishu_target or "").strip() or str((os.environ.get("FEISHU_BOT_TARGET") or "")).strip()
            account = str(args.notify_feishu_account or "").strip() or str((os.environ.get("FEISHU_BOT_ACCOUNT") or "")).strip()
            if target:
                notify_result = _notify_feishu_channel(
                    openclaw_cmd=str(args.openclaw_cmd),
                    target=target,
                    text=alert_text,
                    account=(account or None),
                )
            else:
                notify_result = {"ok": False, "error": "no feishu webhook/target configured"}

    output = {
        "ok": bool(report.get("needs_attention") is False or resolved),
        "report_path": str(report_path),
        "needs_attention": bool(report.get("needs_attention")),
        "resolved": bool(resolved),
        "report": report,
        "agent_result": agent_result,
        "notify_result": notify_result,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
