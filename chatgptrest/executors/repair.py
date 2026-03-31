from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import subprocess
import time

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chatgptrest.core.config import AppConfig
from chatgptrest.core.build_info import get_build_info
from chatgptrest.core.codex_runner import codex_exec_with_schema
from chatgptrest.core.db import connect
from chatgptrest.core.repair_jobs import default_repair_autofix_model
from chatgptrest.driver.api import ToolCaller
from chatgptrest.executors.base import BaseExecutor, ExecutorResult
from chatgptrest.ops_shared.maint_memory import load_maintagent_bootstrap_memory, load_maintagent_repo_memory

# Phase 2 refactoring: shared utilities extracted to ops_shared.
from chatgptrest.ops_shared.infra import (
    now_iso as _now_iso,
    read_json as _read_json,
    atomic_write_json as _atomic_write_json,
    read_text as _read_text,
    http_json as _http_json,
    parse_host_port_from_url as _parse_host_port_from_url,
    port_open as _port_open,
    run_cmd as _run_cmd,
    systemd_unit_load_state as _systemd_unit_load_state,
    active_send_jobs as _active_send_jobs,
    truncate_text as _truncate_text,
    conversation_platform as _conversation_platform,
    mihomo_get_proxy as _mihomo_get_proxy,
    mihomo_set_proxy as _mihomo_set_proxy,
    mihomo_find_connections as _mihomo_find_connections,
)
from chatgptrest.ops_shared.provider import (
    provider_from_kind as _provider_from_kind,
    default_chatgpt_cdp_url as _default_chatgpt_cdp_url,
    provider_cdp_url as _provider_cdp_url,
    provider_chrome_start_script as _provider_chrome_start_script,
    provider_chrome_stop_script as _provider_chrome_stop_script,
    provider_tools as _provider_tools,
)
from chatgptrest.ops_shared.actions import (
    RISK_RANK as _RISK_RANK,
    risk_allows as _risk_allows,
    parse_allow_actions as _parse_allow_actions,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return int(default)
        try:
            return int(s)
        except Exception:
            return int(default)
    return int(default)


def _as_bool(value: object, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if not s:
            return bool(default)
        if s in {"1", "true", "yes", "y", "on"}:
            return True
        if s in {"0", "false", "no", "n", "off"}:
            return False
    return bool(default)


def _as_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return default


def _read_repair_playbook(*, limit: int = 60_000) -> str:
    path = (_REPO_ROOT / "docs" / "repair_agent_playbook.md").resolve()
    if not path.exists():
        return ""
    return _read_text(path, limit=limit).strip()


def _default_blocked_state_path() -> Path:
    raw = (os.environ.get("CHATGPT_BLOCKED_STATE_FILE") or os.environ.get("CHATGPTREST_BLOCKED_STATE_FILE") or "").strip()
    if raw:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (_REPO_ROOT / p).resolve()
        return p
    preferred = (_REPO_ROOT / "state" / "driver" / "chatgpt_blocked_state.json").resolve()
    if preferred.exists():
        return preferred
    return (_REPO_ROOT / ".run" / "chatgpt_blocked_state.json").resolve()


def _proxy_env_snapshot() -> dict[str, bool]:
    no_proxy = (os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or "").strip()
    no_proxy_l = no_proxy.lower()
    return {
        "http_proxy": bool((os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "").strip()),
        "https_proxy": bool((os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "").strip()),
        "all_proxy": bool((os.environ.get("ALL_PROXY") or os.environ.get("all_proxy") or "").strip()),
        "no_proxy": bool(no_proxy),
        "no_proxy_contains_googleapis": ("googleapis.com" in no_proxy_l or "www.googleapis.com" in no_proxy_l),
    }


def _csv_env(name: str) -> list[str]:
    raw = _as_str(os.environ.get(name), "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _gemini_mihomo_proxy_group() -> str:
    return _as_str(os.environ.get("CHATGPTREST_GEMINI_MIHOMO_PROXY_GROUP"), "💻 Codex").strip() or "💻 Codex"


def _gemini_mihomo_candidates() -> list[str]:
    return _csv_env("CHATGPTREST_GEMINI_MIHOMO_CANDIDATES")


def _gemini_region_haystack(*parts: object) -> str:
    return "\n".join(_as_str(part, "").strip() for part in parts if _as_str(part, "").strip()).lower()


def _looks_like_gemini_region_issue(*parts: object) -> bool:
    haystack = _gemini_region_haystack(*parts)
    if not haystack:
        return False
    needles = (
        "geminiunsupportedregion",
        "unsupported region",
        "not supported in your region",
        "not available in this region",
        "not available in your country",
        "目前不支持你所在的地区",
        "不支持你所在的地区",
    )
    return any(needle in haystack for needle in needles)


def _collect_gemini_mihomo_probe() -> dict[str, Any]:
    group = _gemini_mihomo_proxy_group()
    candidates = _gemini_mihomo_candidates()
    proxy = _mihomo_get_proxy(group, timeout_seconds=5.0)
    connections = _mihomo_find_connections(host_substring="gemini.google.com", timeout_seconds=5.0, limit=5)
    return {
        "group": group,
        "configured_candidates": candidates,
        "proxy": proxy,
        "connections": connections,
        "ok": bool(proxy.get("ok")) and bool(connections.get("ok")),
    }


@dataclass(frozen=True)
class _BlockedStatus:
    blocked: bool
    blocked_until: float
    seconds_until_unblocked: float
    reason: str | None
    state_file: str
    artifacts: dict[str, Any] | None


def _parse_blocked_state(path: Path) -> _BlockedStatus:
    obj = _read_json(path) if path.exists() else None
    until = 0.0
    reason = None
    artifacts = None
    if isinstance(obj, dict):
        try:
            until = float(obj.get("blocked_until") or 0.0)
        except Exception:
            until = 0.0
        reason_raw = obj.get("reason")
        reason = str(reason_raw).strip() if isinstance(reason_raw, str) and reason_raw.strip() else None
        artifacts_raw = obj.get("artifacts")
        artifacts = artifacts_raw if isinstance(artifacts_raw, dict) else None
    now = time.time()
    blocked = bool(until > 0.0 and now < until)
    return _BlockedStatus(
        blocked=blocked,
        blocked_until=until,
        seconds_until_unblocked=(max(0.0, until - now) if until > 0 else 0.0),
        reason=reason,
        state_file=str(path),
        artifacts=artifacts,
    )


def _job_summary_row(row: Any) -> dict[str, Any]:
    # sqlite3.Row is Mapping-like; keep robust fallbacks.
    def _get(k: str) -> Any:
        try:
            return row[k]
        except Exception:
            return None

    return {
        "job_id": str(_get("job_id") or ""),
        "kind": str(_get("kind") or ""),
        "status": str(_get("status") or ""),
        "phase": str(_get("phase") or ""),
        "created_at": float(_get("created_at") or 0.0),
        "updated_at": float(_get("updated_at") or 0.0),
        "not_before": float(_get("not_before") or 0.0),
        "attempts": int(_get("attempts") or 0),
        "max_attempts": int(_get("max_attempts") or 0),
        "conversation_url": (str(_get("conversation_url") or "").strip() or None),
        "answer_path": (str(_get("answer_path") or "").strip() or None),
        "answer_chars": (int(_get("answer_chars") or 0) if _get("answer_chars") is not None else None),
        "conversation_export_path": (str(_get("conversation_export_path") or "").strip() or None),
        "conversation_export_chars": (
            int(_get("conversation_export_chars") or 0) if _get("conversation_export_chars") is not None else None
        ),
        "last_error_type": (str(_get("last_error_type") or "").strip() or None),
        "last_error": (str(_get("last_error") or "").strip() or None),
    }


def _summarize_target_run_meta(obj: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    out: dict[str, Any] = {}
    for k in ("error_type", "retry_after_seconds", "not_before", "drive_name_fallback"):
        if k in obj:
            out[k] = obj.get(k)
    if "error" in obj:
        out["error"] = _truncate_text(obj.get("error"), limit=1200)

    drive_uploads_raw = obj.get("drive_uploads")
    if isinstance(drive_uploads_raw, list):
        uploads: list[dict[str, Any]] = []
        for u in drive_uploads_raw[:5]:
            if not isinstance(u, dict):
                continue
            item: dict[str, Any] = {
                "src_path": str(u.get("src_path") or ""),
                "drive_remote_path": str(u.get("drive_remote_path") or ""),
                "drive_url": str(u.get("drive_url") or ""),
                "drive_id": str(u.get("drive_id") or ""),
                "upload_completed": bool(u.get("upload_completed")),
                "drive_error_kind": str(u.get("drive_error_kind") or ""),
            }
            if u.get("drive_resolve_error"):
                item["drive_resolve_error"] = _truncate_text(u.get("drive_resolve_error"), limit=800)
            rclone_copyto = u.get("rclone_copyto")
            if isinstance(rclone_copyto, dict):
                item["rclone_copyto"] = {
                    "ok": bool(rclone_copyto.get("ok")),
                    "timed_out": bool(rclone_copyto.get("timed_out")),
                    "returncode": rclone_copyto.get("returncode"),
                    "elapsed_seconds": rclone_copyto.get("elapsed_seconds"),
                    "error": _truncate_text(rclone_copyto.get("error"), limit=500),
                    "proxy_env": (rclone_copyto.get("proxy_env") if isinstance(rclone_copyto.get("proxy_env"), dict) else None),
                }
            uploads.append(item)
        if uploads:
            out["drive_uploads"] = uploads
    return out


def _format_seconds(ts: float) -> str:
    if ts <= 0:
        return "(unset)"
    try:
        return datetime.fromtimestamp(float(ts), UTC).isoformat().replace("+00:00", "Z")
    except Exception:
        return str(ts)


def _suggestions(*, report: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []

    provider = str(report.get("provider") or "chatgpt").strip().lower() or "chatgpt"
    chrome_start_script = _provider_chrome_start_script(provider)
    cdp_url = str(((report.get("cdp_probe") or {}) or {}).get("cdp_url") or _provider_cdp_url(provider))
    blocked = bool(((report.get("blocked_state") or {}) or {}).get("blocked"))
    driver_probe = report.get("driver_probe") or {}
    driver_ok = bool(driver_probe.get("ok"))
    cdp = report.get("cdp_probe") or {}
    cdp_ok = bool(cdp.get("ok"))

    if not cdp_ok:
        suggestions.append(
            f"Chrome/CDP seems down: run `bash {chrome_start_script}` and verify `{cdp_url.rstrip('/')}/json/version`."
        )

    if not driver_ok:
        suggestions.append("Driver MCP seems unreachable: restart the internal driver via `bash ops/start_driver.sh` (or fix CHATGPTREST_DRIVER_URL).")

    if blocked and provider == "chatgpt":
        suggestions.append(
            "ChatGPT blocked detected: do not assume re-login first. Verify CHATGPT_CDP_URL is a real DevTools endpoint (`/json/version` has `webSocketDebuggerUrl`) and not a hijacked local port."
        )
        suggestions.append(
            "Then clear blocked state via `chatgpt_web_clear_blocked`, run `chatgpt_web_self_check`, and retry the same job wait (driver includes verification auto-click attempt)."
        )
        suggestions.append(
            "Only if still blocked after endpoint verification + clear/self_check, use noVNC on the same profile for manual verification/login."
        )

    target = report.get("target_job")
    if isinstance(target, dict):
        status = str(target.get("status") or "").strip().lower()
        if status in {"cooldown", "blocked", "needs_followup"}:
            suggestions.append("For ask jobs: prefer polling `/v1/jobs/{job_id}/wait` instead of creating a new job (avoid duplicate prompts).")

    target_run_meta = report.get("target_run_meta")
    if isinstance(target_run_meta, dict):
        err_type = str(target_run_meta.get("error_type") or "").strip()
        err_text = str(target_run_meta.get("error") or "").strip()
        if err_type == "DriveUploadNotReady" or "DriveUploadNotReady" in err_text:
            suggestions.append("Gemini Drive upload is not ready (rclone -> Google Drive). Prefer waiting/retrying the same job instead of resubmitting.")
            proxy_env = ((report.get("env") or {}) or {}).get("proxy_env")
            if isinstance(proxy_env, dict):
                http_proxy = bool(proxy_env.get("http_proxy"))
                https_proxy = bool(proxy_env.get("https_proxy"))
                all_proxy = bool(proxy_env.get("all_proxy"))
                if not http_proxy and not https_proxy:
                    if all_proxy:
                        suggestions.append(
                            "Only ALL_PROXY is set; rclone/Go often requires HTTP(S)_PROXY. Set `CHATGPTREST_RCLONE_PROXY=$ALL_PROXY` (or export HTTP_PROXY/HTTPS_PROXY)."
                        )
                    else:
                        suggestions.append(
                            "No proxy env detected for rclone. In restricted networks, set `CHATGPTREST_RCLONE_PROXY` (or HTTP_PROXY/HTTPS_PROXY) for the worker/service."
                        )
                if bool(proxy_env.get("no_proxy_contains_googleapis")):
                    suggestions.append(
                        "NO_PROXY seems to include googleapis.com; this can force direct (non-proxied) connections and cause timeouts in restricted networks."
                    )
            if "www.googleapis.com" in err_text and ("i/o timeout" in err_text or "timeout" in err_text):
                suggestions.append("Network timeout to Google APIs detected; check proxy health (mihomo delay logs) and DNS/firewall rules.")

    driver_probe = report.get("driver_probe") or {}
    self_check = (driver_probe.get("self_check") if isinstance(driver_probe, dict) else None) or {}
    region_issue = (
        provider == "gemini"
        and _looks_like_gemini_region_issue(
            (target_run_meta or {}).get("error_type") if isinstance(target_run_meta, dict) else None,
            (target_run_meta or {}).get("error") if isinstance(target_run_meta, dict) else None,
            self_check.get("error_type") if isinstance(self_check, dict) else None,
            self_check.get("error") if isinstance(self_check, dict) else None,
            symptom if isinstance(symptom := report.get("symptom"), str) else None,
        )
    )
    if region_issue:
        mihomo_probe = report.get("mihomo_proxy_probe") or {}
        proxy = mihomo_probe.get("proxy") if isinstance(mihomo_probe, dict) else {}
        connections = mihomo_probe.get("connections") if isinstance(mihomo_probe, dict) else {}
        group = _as_str((proxy or {}).get("group"), "").strip() or _gemini_mihomo_proxy_group()
        now = _as_str((proxy or {}).get("now"), "").strip()
        candidates = mihomo_probe.get("configured_candidates") if isinstance(mihomo_probe, dict) else []
        suggestions.append(
            f"Gemini region block detected: switch mihomo group `{group}` to a supported-region node, then restart `chatgptrest-chrome.service` to flush reused Google/Gemini browser connections."
        )
        if now:
            suggestions.append(f"Current mihomo selection for `{group}` is `{now}`.")
        if isinstance(candidates, list) and candidates:
            suggestions.append(f"Configured Gemini failover candidates: {', '.join(str(x) for x in candidates[:6])}.")
        matches = connections.get("matches") if isinstance(connections, dict) else None
        if isinstance(matches, list) and matches:
            chains = matches[0].get("chains") if isinstance(matches[0], dict) else None
            if isinstance(chains, list) and chains:
                suggestions.append(f"Current Gemini connection chain: {' -> '.join(str(x) for x in chains[:6])}.")

    if not suggestions:
        suggestions.append("No obvious incident detected; if you still see failures, include `input.job_id` and `input.symptom` for a more targeted report.")
    return suggestions


class RepairExecutor(BaseExecutor):
    def __init__(self, *, cfg: AppConfig, tool_caller: ToolCaller | None, tool_caller_init_error: str | None = None) -> None:
        self._cfg = cfg
        self._tool_caller = tool_caller
        self._tool_caller_init_error = tool_caller_init_error

    async def run(self, *, job_id: str, kind: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:  # noqa: A002
        started = time.time()
        timeout_seconds = max(5, _as_int(params.get("timeout_seconds"), 60))
        mode = _as_str(params.get("mode"), "quick").strip().lower() or "quick"
        probe_driver = _as_bool(params.get("probe_driver"), default=True)
        capture_ui = _as_bool(params.get("capture_ui"), default=False)
        include_recent = max(0, min(50, _as_int(params.get("recent_failures"), 5)))

        target_job_id = _as_str(input.get("job_id"), "").strip() or None
        symptom = _as_str(input.get("symptom") or input.get("error"), "").strip() or None
        conversation_url = _as_str(input.get("conversation_url"), "").strip() or None

        report: dict[str, Any] = {
            "ok": True,
            "ts": _now_iso(),
            "elapsed_ms": None,
            "repair_job_id": job_id,
            "kind": kind,
            "mode": mode,
            "symptom": symptom,
            "target_job_id": target_job_id,
            "env": {
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                "driver_mode": self._cfg.driver_mode,
                "driver_url": self._cfg.driver_url,
                "db_path": str(self._cfg.db_path),
                "artifacts_dir": str(self._cfg.artifacts_dir),
                "chatgpt_cdp_url": (os.environ.get("CHATGPT_CDP_URL") or "").strip() or None,
                "gemini_cdp_url": (os.environ.get("GEMINI_CDP_URL") or "").strip() or None,
                "qwen_cdp_url": (os.environ.get("QWEN_CDP_URL") or "").strip() or None,
                "proxy_env": _proxy_env_snapshot(),
            },
        }
        report["build"] = get_build_info(include_dirty=True)

        # DB summary
        db_probe: dict[str, Any] = {"ok": True}
        try:
            with connect(self._cfg.db_path) as conn:
                rows = conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status ORDER BY n DESC").fetchall()
                db_probe["jobs_summary"] = {str(r["status"]): int(r["n"]) for r in rows}
                if include_recent > 0:
                    recent = conn.execute(
                        """
                        SELECT job_id, kind, status, phase, updated_at, last_error_type, last_error
                        FROM jobs
                        WHERE status IN ('error','blocked','cooldown','needs_followup')
                        ORDER BY updated_at DESC
                        LIMIT ?
                        """,
                        (int(include_recent),),
                    ).fetchall()
                    db_probe["recent_failures"] = [
                        {
                            "job_id": str(r["job_id"]),
                            "kind": str(r["kind"]),
                            "status": str(r["status"]),
                            "phase": str(r["phase"] or ""),
                            "updated_at": float(r["updated_at"] or 0.0),
                            "last_error_type": (str(r["last_error_type"] or "").strip() or None),
                            "last_error": (str(r["last_error"] or "").strip() or None),
                        }
                        for r in recent
                    ]
        except Exception as exc:
            db_probe = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:500]}
        report["db_probe"] = db_probe

        # Target job
        target_job: dict[str, Any] | None = None
        if target_job_id:
            try:
                with connect(self._cfg.db_path) as conn:
                    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (str(target_job_id),)).fetchone()
                if row is None:
                    target_job = {"ok": False, "error_type": "NotFound", "error": "job not found"}
                else:
                    target_job = {"ok": True, **_job_summary_row(row)}
            except Exception as exc:
                target_job = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:500]}
        report["target_job"] = target_job

        target_kind = ""
        if isinstance(target_job, dict) and bool(target_job.get("ok")):
            target_kind = _as_str(target_job.get("kind"), "").strip()
        provider = _provider_from_kind(target_kind) or _conversation_platform(conversation_url) or "chatgpt"
        provider_tools = _provider_tools(provider)
        report["provider"] = provider
        report["provider_tools"] = {k: v for k, v in provider_tools.items() if isinstance(v, str) and v.strip()}
        if provider == "gemini":
            report["mihomo_proxy_probe"] = _collect_gemini_mihomo_probe()

        # Target run meta (best-effort, truncated)
        target_run_meta: dict[str, Any] | None = None
        if target_job_id:
            try:
                run_meta_path = (self._cfg.artifacts_dir / "jobs" / target_job_id / "run_meta.json").resolve()
                if run_meta_path.exists():
                    target_run_meta = _summarize_target_run_meta(_read_json(run_meta_path))
                    if isinstance(target_run_meta, dict):
                        target_run_meta["run_meta_path"] = str(run_meta_path)
            except Exception:
                target_run_meta = None
        report["target_run_meta"] = target_run_meta

        # blocked state (local file; ChatGPT-only today)
        blocked = _BlockedStatus(
            blocked=False,
            blocked_until=0.0,
            seconds_until_unblocked=0.0,
            reason=None,
            state_file="",
            artifacts=None,
        )
        if provider == "chatgpt":
            blocked_state_path = _default_blocked_state_path()
            blocked = _parse_blocked_state(blocked_state_path)
            report["blocked_state"] = {
                "supported": True,
                "provider": provider,
                "blocked": blocked.blocked,
                "blocked_until": blocked.blocked_until,
                "seconds_until_unblocked": round(float(blocked.seconds_until_unblocked), 3),
                "reason": blocked.reason,
                "state_file": blocked.state_file,
                "artifacts": blocked.artifacts,
            }
        else:
            report["blocked_state"] = {
                "supported": False,
                "provider": provider,
                "blocked": False,
                "blocked_until": 0.0,
                "seconds_until_unblocked": 0.0,
                "reason": None,
                "state_file": None,
                "artifacts": None,
            }

        # Chrome / CDP probe (optional, best-effort)
        cdp_url = _provider_cdp_url(provider)
        report["cdp_probe"] = {
            "ok": True,
            "provider": provider,
            "cdp_url": cdp_url,
            "version": _http_json(f"{cdp_url.rstrip('/')}/json/version", timeout_seconds=3.0),
        }
        if isinstance(report["cdp_probe"].get("version"), dict) and report["cdp_probe"]["version"].get("ok") is False:
            report["cdp_probe"]["ok"] = False

        # Driver probes (best-effort)
        driver_probe: dict[str, Any] = {"ok": True}
        if self._tool_caller_init_error:
            driver_probe["ok"] = False
            driver_probe["init_error"] = self._tool_caller_init_error

        if probe_driver and self._tool_caller is not None:
            blocked_status_tool = provider_tools.get("blocked_status")
            if blocked_status_tool:
                try:
                    driver_probe["blocked_status"] = await asyncio.to_thread(
                        self._tool_caller.call_tool,
                        tool_name=blocked_status_tool,
                        tool_args={},
                        timeout_sec=min(15.0, float(timeout_seconds)),
                    )
                except Exception as exc:
                    driver_probe["ok"] = False
                    driver_probe["blocked_status_error"] = f"{type(exc).__name__}: {exc}"

            rate_limit_tool = provider_tools.get("rate_limit_status")
            if rate_limit_tool:
                try:
                    driver_probe["rate_limit_status"] = await asyncio.to_thread(
                        self._tool_caller.call_tool,
                        tool_name=rate_limit_tool,
                        tool_args={},
                        timeout_sec=min(15.0, float(timeout_seconds)),
                    )
                except Exception as exc:
                    driver_probe["ok"] = False
                    driver_probe["rate_limit_status_error"] = f"{type(exc).__name__}: {exc}"

            tab_stats_tool = provider_tools.get("tab_stats")
            if tab_stats_tool:
                try:
                    driver_probe["tab_stats"] = await asyncio.to_thread(
                        self._tool_caller.call_tool,
                        tool_name=tab_stats_tool,
                        tool_args={},
                        timeout_sec=min(15.0, float(timeout_seconds)),
                    )
                except Exception as exc:
                    driver_probe["ok"] = False
                    driver_probe["tab_stats_error"] = f"{type(exc).__name__}: {exc}"

            # Optional: self-check and UI capture (no prompt send).
            #
            # "capture_ui" is useful on its own (without the rest of the full probe), so do not
            # gate it behind mode=full/debug.
            should_self_check = mode in {"full", "debug"}
            should_capture_ui = bool(capture_ui) or mode == "capture_ui"
            if should_self_check or should_capture_ui:
                effective_url = conversation_url
                if not effective_url and isinstance(target_job, dict):
                    effective_url = _as_str(target_job.get("conversation_url"), "").strip() or None
                if should_self_check and effective_url:
                    self_check_tool = provider_tools.get("self_check")
                    if self_check_tool:
                        try:
                            driver_probe["self_check"] = await asyncio.to_thread(
                                self._tool_caller.call_tool,
                                tool_name=self_check_tool,
                                tool_args={"conversation_url": effective_url, "timeout_seconds": min(30, timeout_seconds)},
                                timeout_sec=min(45.0, float(timeout_seconds) + 5.0),
                            )
                        except Exception as exc:
                            driver_probe["ok"] = False
                            driver_probe["self_check_error"] = f"{type(exc).__name__}: {exc}"
                    else:
                        driver_probe["self_check"] = {
                            "skipped": True,
                            "skip_reason": "provider_self_check_not_supported",
                            "provider": provider,
                        }

                if should_capture_ui:
                    capture_ui_tool = provider_tools.get("capture_ui")
                    if capture_ui_tool:
                        out_dir = (self._cfg.artifacts_dir / "jobs" / job_id / f"{provider}_ui_snapshots").resolve()
                        try:
                            driver_probe["capture_ui"] = await asyncio.to_thread(
                                self._tool_caller.call_tool,
                                tool_name=capture_ui_tool,
                                tool_args={
                                    "conversation_url": effective_url,
                                    "mode": "basic",
                                    "timeout_seconds": min(90, max(10, timeout_seconds)),
                                    "out_dir": str(out_dir),
                                    "write_doc": False,
                                },
                                timeout_sec=min(120.0, float(timeout_seconds) + 30.0),
                            )
                        except Exception as exc:
                            driver_probe["ok"] = False
                            driver_probe["capture_ui_error"] = f"{type(exc).__name__}: {exc}"
                    else:
                        driver_probe["capture_ui"] = {
                            "skipped": True,
                            "skip_reason": "provider_capture_ui_not_supported",
                            "provider": provider,
                        }
        else:
            if probe_driver:
                driver_probe["ok"] = False
                driver_probe["error"] = "tool_caller unavailable"

        report["driver_probe"] = driver_probe

        report["suggestions"] = _suggestions(report=report)

        elapsed_ms = int(round((time.time() - started) * 1000))
        report["elapsed_ms"] = elapsed_ms

        job_dir = self._cfg.artifacts_dir / "jobs" / job_id
        report_path = (job_dir / "repair_report.json").resolve()
        try:
            _atomic_write_json(report_path, report)
        except Exception:
            # Avoid failing the repair check due to secondary IO errors.
            pass

        return self._format_report(
            report=report,
            job_id=job_id,
            target_job_id=target_job_id,
            symptom=symptom,
            provider=provider,
            blocked=blocked,
            cdp_url=cdp_url,
            elapsed_ms=elapsed_ms,
        )

    def _format_report(
        self,
        *,
        report: dict[str, Any],
        job_id: str,
        target_job_id: str | None,
        symptom: str | None,
        provider: str,
        blocked: _BlockedStatus,
        cdp_url: str,
        elapsed_ms: int,
    ) -> ExecutorResult:
        """Format the repair report as markdown and return the executor result."""
        lines: list[str] = []
        lines.append("# repair.check report")
        lines.append("")
        lines.append(f"- ts: `{report.get('ts')}`")
        lines.append(f"- repair_job_id: `{job_id}`")
        if target_job_id:
            lines.append(f"- target_job_id: `{target_job_id}`")
        if symptom:
            lines.append(f"- symptom: {symptom}")
        lines.append(f"- report_path: `{(Path('jobs') / job_id / 'repair_report.json').as_posix()}`")
        lines.append("")
        lines.append("## Stack")
        db_probe = report.get("db_probe") or {}
        lines.append(f"- db: {'ok' if db_probe.get('ok') else 'error'} (`{self._cfg.db_path}`)")
        lines.append(f"- artifacts_dir: `{self._cfg.artifacts_dir}`")
        lines.append(f"- driver_mode: `{self._cfg.driver_mode}`")
        lines.append(f"- driver_url: `{self._cfg.driver_url}`")
        lines.append(f"- provider: `{provider}`")
        build = report.get("build") or {}
        lines.append(f"- git_sha: `{_as_str(build.get('git_sha'), '').strip()}` dirty=`{build.get('git_dirty')}`")
        lines.append("")
        lines.append("## Blocked State")
        blocked_state = report.get("blocked_state") or {}
        if bool(blocked_state.get("supported")):
            lines.append(f"- blocked: `{blocked.blocked}` reason=`{blocked.reason or ''}` until=`{_format_seconds(blocked.blocked_until)}`")
            if blocked.artifacts:
                for k in ["screenshot", "html", "text"]:
                    v = blocked.artifacts.get(k)
                    if isinstance(v, str) and v.strip():
                        lines.append(f"- {k}: `{v.strip()}`")
        else:
            lines.append(f"- not_supported_for_provider: `{provider}`")
        lines.append("")
        lines.append("## Chrome / CDP")
        cdp_probe = report.get("cdp_probe") or {}
        lines.append(f"- provider: `{provider}`")
        lines.append(f"- cdp_url: `{cdp_url}` ok=`{bool(cdp_probe.get('ok'))}`")
        version = cdp_probe.get("version")
        if isinstance(version, dict) and version.get("ok") is False:
            lines.append(f"- error: `{version.get('error_type')}` {version.get('error')}")
        elif isinstance(version, dict):
            browser = _as_str(version.get("Browser"), "").strip()
            if browser:
                lines.append(f"- Browser: `{browser}`")
        lines.append("")
        lines.append("## Driver Probe")
        driver_probe = report.get("driver_probe") or {}
        lines.append(f"- ok: `{bool(driver_probe.get('ok'))}`")
        if driver_probe.get("blocked_status_error"):
            lines.append(f"- blocked_status_error: `{driver_probe.get('blocked_status_error')}`")
        if driver_probe.get("rate_limit_status_error"):
            lines.append(f"- rate_limit_status_error: `{driver_probe.get('rate_limit_status_error')}`")
        if driver_probe.get("tab_stats_error"):
            lines.append(f"- tab_stats_error: `{driver_probe.get('tab_stats_error')}`")
        if driver_probe.get("self_check_error"):
            lines.append(f"- self_check_error: `{driver_probe.get('self_check_error')}`")
        if driver_probe.get("capture_ui_error"):
            lines.append(f"- capture_ui_error: `{driver_probe.get('capture_ui_error')}`")
        lines.append("")
        mihomo_probe = report.get("mihomo_proxy_probe")
        if isinstance(mihomo_probe, dict):
            lines.append("## Mihomo / Gemini Egress")
            proxy = mihomo_probe.get("proxy") if isinstance(mihomo_probe.get("proxy"), dict) else {}
            connections = mihomo_probe.get("connections") if isinstance(mihomo_probe.get("connections"), dict) else {}
            lines.append(f"- group: `{_as_str(proxy.get('group'), '')}` now=`{_as_str(proxy.get('now'), '')}` ok=`{bool(proxy.get('ok'))}`")
            candidates = mihomo_probe.get("configured_candidates")
            if isinstance(candidates, list) and candidates:
                lines.append(f"- configured_candidates: `{', '.join(str(x) for x in candidates[:8])}`")
            matches = connections.get("matches") if isinstance(connections, dict) else None
            if isinstance(matches, list) and matches:
                first = matches[0] if isinstance(matches[0], dict) else {}
                chains = first.get("chains") if isinstance(first, dict) else None
                if isinstance(chains, list) and chains:
                    lines.append(f"- gemini_chain: `{' -> '.join(str(x) for x in chains[:8])}`")
            lines.append("")
        target_job = report.get("target_job")
        if isinstance(target_job, dict):
            lines.append("## Target Job")
            if not bool(target_job.get("ok")):
                lines.append(f"- error: `{target_job.get('error_type')}` {target_job.get('error')}")
            else:
                lines.append(f"- kind: `{target_job.get('kind')}` status=`{target_job.get('status')}` phase=`{target_job.get('phase')}`")
                lines.append(
                    f"- updated_at: `{_format_seconds(float(target_job.get('updated_at') or 0.0))}` not_before=`{_format_seconds(float(target_job.get('not_before') or 0.0))}`"
                )
                lines.append(
                    f"- attempts: `{target_job.get('attempts')}`/`{target_job.get('max_attempts')}` last_error_type=`{target_job.get('last_error_type') or ''}`"
                )
                last_error = _as_str(target_job.get("last_error"), "").strip()
                if last_error:
                    lines.append(f"- last_error: {last_error}")
                if target_job.get("answer_path"):
                    lines.append(f"- answer_path: `{target_job.get('answer_path')}`")
                if target_job.get("conversation_export_path"):
                    lines.append(f"- conversation_export_path: `{target_job.get('conversation_export_path')}`")
            lines.append("")
        target_run_meta = report.get("target_run_meta")
        if isinstance(target_run_meta, dict):
            lines.append("## Target Run Meta")
            if target_run_meta.get("error_type"):
                lines.append(f"- error_type: `{target_run_meta.get('error_type')}`")
            if target_run_meta.get("error"):
                lines.append(f"- error: {target_run_meta.get('error')}")
            if target_run_meta.get("run_meta_path"):
                lines.append(f"- run_meta_path: `{target_run_meta.get('run_meta_path')}`")
            drive_uploads = target_run_meta.get("drive_uploads")
            if isinstance(drive_uploads, list) and drive_uploads:
                lines.append(f"- drive_uploads: `{len(drive_uploads)}` (truncated)")
            lines.append("")
        lines.append("## Suggestions")
        for s in report.get("suggestions") or []:
            lines.append(f"- {s}")
        lines.append("")

        meta = {
            "repair_report_path": (Path("jobs") / job_id / "repair_report.json").as_posix(),
            "repair_elapsed_ms": elapsed_ms,
            "provider": provider,
            "blocked": blocked.blocked,
            "blocked_until": blocked.blocked_until,
            "blocked_reason": blocked.reason,
            "target_job_id": target_job_id,
        }
        return ExecutorResult(status="completed", answer="\n".join(lines), answer_format="markdown", meta=meta)


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    raw = raw.strip().lower()
    if not raw:
        return bool(default)
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def _conversation_platform(url: str | None) -> str | None:
    raw = str(url or "").strip().lower()
    if not raw:
        return None
    if "chatgpt.com" in raw or "chat.openai.com" in raw:
        return "chatgpt"
    if "gemini.google.com" in raw:
        return "gemini"
    if "qianwen.com" in raw:
        return "qwen"
    return None


async def _call_tool_with_hard_timeout(
    *,
    tool_caller: ToolCaller,
    tool_name: str,
    tool_args: dict[str, Any],
    timeout_sec: float,
    hard_timeout_sec: float | None = None,
) -> dict[str, Any]:
    per_call_timeout = max(1.0, float(timeout_sec))
    hard_timeout = float(hard_timeout_sec) if hard_timeout_sec is not None else (per_call_timeout + 5.0)
    if hard_timeout <= 0:
        hard_timeout = per_call_timeout + 5.0
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                tool_caller.call_tool,
                tool_name=tool_name,
                tool_args=dict(tool_args or {}),
                timeout_sec=per_call_timeout,
            ),
            timeout=hard_timeout,
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"tool timed out after {hard_timeout:.1f}s: {tool_name}") from exc


def _build_codex_autofix_prompt(
    *,
    agents_md: str,
    playbook_md: str,
    evidence: dict[str, Any],
    repo_memory_text: str,
    bootstrap_memory_text: str,
) -> str:
    lines: list[str] = []
    lines.append("You are an SRE/autofix agent for ChatgptREST.")
    lines.append("")
    lines.append("Goal: help a single ChatgptREST ask job recover to completed WITHOUT sending any new user prompts.")
    lines.append("")
    lines.append("Hard constraints:")
    lines.append("- Do NOT send any ChatGPT/Gemini/Qwen prompts (no ask jobs, no follow-ups).")
    lines.append("- Prefer refresh/regenerate/wait/export over re-sending questions.")
    lines.append("- Restart actions are allowed but MUST be guarded: never restart while any non-repair job is in phase=send.")
    lines.append("- For blocked/captcha/login: verify CDP endpoint first, then try clear_blocked + self_check + built-in verification auto-click; only then escalate to manual verification.")
    lines.append("")
    lines.append("You can recommend these actions (choose 0..N, ordered by priority):")
    lines.append("- no_action")
    lines.append("- capture_ui")
    lines.append("- enable_netlog / disable_netlog (optional)")
    lines.append("- refresh (ChatGPT only; no prompt send)")
    lines.append("- regenerate (ChatGPT only; no prompt send)")
    lines.append("- clear_blocked (only if safe and clearly stale)")
    lines.append("- restart_chrome / restart_driver (only when guarded)")
    lines.append("- pause_processing (manual-required)")
    lines.append("")
    lines.append("Return JSON matching the provided JSON Schema.")
    lines.append("")
    if playbook_md.strip():
        lines.append("=== Repair Agent Playbook (authoritative policy) ===")
        lines.append(playbook_md.strip())
        lines.append("")
    if agents_md.strip():
        lines.append("=== AGENTS.md (truncated) ===")
        lines.append(agents_md.strip())
        lines.append("")
    if repo_memory_text.strip():
        lines.append("=== Maintagent Repo Memory ===")
        lines.append(repo_memory_text.strip())
        lines.append("")
    if bootstrap_memory_text.strip():
        lines.append("=== Maintagent Bootstrap Memory ===")
        lines.append(bootstrap_memory_text.strip())
        lines.append("")
    lines.append("=== Evidence (JSON) ===")
    lines.append(json.dumps(evidence, ensure_ascii=False, indent=2)[:120_000])
    lines.append("")
    return "\n".join(lines).strip()


def _build_codex_autofix_fallback_prompt(*, evidence: dict[str, Any], prior_error: str | None) -> str:
    """
    Secondary fallback prompt for Codex in repair.autofix.

    Keep this prompt short and concrete so it remains robust when the primary
    Codex run failed due to verbosity/schema pressure or transient tool issues.
    """
    lines: list[str] = []
    lines.append("You are the ChatgptREST maint fallback agent.")
    lines.append("")
    lines.append("Goal: return a conservative action plan to recover ONE existing ask job.")
    lines.append("")
    lines.append("Hard constraints:")
    lines.append("- Never send new prompts/questions.")
    lines.append("- Use only allowed actions from Evidence.allowed_actions.")
    lines.append("- Prefer low-risk actions first; restart actions only for clear infra/CDP faults.")
    lines.append("- Return strict JSON that matches the schema.")
    lines.append("")
    if str(prior_error or "").strip():
        lines.append("Previous Codex run failed with:")
        lines.append(str(prior_error or "").strip()[:1500])
        lines.append("")
    lines.append("Evidence JSON:")
    lines.append(json.dumps(evidence, ensure_ascii=False, indent=2)[:80_000])
    lines.append("")
    return "\n".join(lines).strip()


def _run_codex_with_schema(
    *,
    prompt: str,
    schema_path: Path,
    out_json: Path,
    model: str | None,
    timeout_seconds: int,
    cd: Path | None = None,
    config_overrides: list[str] | None = None,
    enable_features: list[str] | None = None,
    disable_features: list[str] | None = None,
) -> dict[str, Any]:
    res = codex_exec_with_schema(
        prompt=prompt,
        schema_path=schema_path,
        out_json=out_json,
        model=model,
        timeout_seconds=int(timeout_seconds),
        cd=cd,
        sandbox="read-only",
        config_overrides=config_overrides,
        enable_features=enable_features,
        disable_features=disable_features,
    )
    meta: dict[str, Any] = {
        "ok": bool(res.ok),
        "returncode": (int(res.returncode) if res.returncode is not None else None),
        "elapsed_ms": int(res.elapsed_ms),
        "cmd": list(res.cmd),
        "stderr": (str(res.stderr) if res.stderr is not None else None),
    }
    if res.error_type:
        meta["error_type"] = str(res.error_type)
    if res.error:
        meta["error"] = str(res.error)
    if isinstance(res.output, dict):
        meta["output"] = res.output
    return meta


def _extract_actions_payload(codex_meta: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(codex_meta, dict):
        return None
    output = codex_meta.get("output")
    if not isinstance(output, dict):
        return None
    actions = output.get("actions")
    if isinstance(actions, list):
        return output
    return None


def _fallback_autofix_actions(
    *,
    provider: str,
    conversation_url: str | None,
    symptom: str | None,
    target_job: dict[str, Any] | None,
    target_run_meta: dict[str, Any] | None,
    allowed: set[str],
) -> list[dict[str, Any]]:
    """
    Conservative fallback planner when Codex fails/timeouts.

    Goal: do something useful (evidence + low-risk recovery) without sending any new prompts.
    """

    def _get(d: dict[str, Any] | None, k: str) -> str:
        if not isinstance(d, dict):
            return ""
        return str(d.get(k) or "").strip()

    haystack = "\n".join(
        [
            str(symptom or "").strip(),
            _get(target_job, "last_error_type"),
            _get(target_job, "last_error"),
            _get(target_run_meta, "error_type"),
            _get(target_run_meta, "error"),
        ]
    ).lower()

    actions: list[dict[str, Any]] = []

    if "capture_ui" in allowed:
        actions.append(
            {
                "name": "capture_ui",
                "risk": "low",
                "reason": "codex failed; capture UI snapshot for debugging (no prompt send)",
            }
        )
    if provider == "chatgpt" and conversation_url and "refresh" in allowed:
        actions.append(
            {
                "name": "refresh",
                "risk": "low",
                "reason": "best-effort refresh to coax final message render (no prompt send)",
            }
        )

    if provider == "gemini" and _looks_like_gemini_region_issue(haystack):
        if "switch_gemini_proxy" in allowed:
            actions.append(
                {
                    "name": "switch_gemini_proxy",
                    "risk": "medium",
                    "reason": "Gemini region block detected; switch the configured mihomo group to a supported-region node",
                }
            )
        if "restart_chrome" in allowed:
            actions.append(
                {
                    "name": "restart_chrome",
                    "risk": "medium",
                    "reason": "Gemini region proxy changes require a Chrome restart to flush reused Google/Gemini connections",
                }
            )

    infra_tokens = [
        "page.goto",
        "timeout",
        "connect_over_cdp",
        "cdp connect failed",
        "target page, context or browser has been closed",
        "browsercontext.new_page",
        "driver blocked: network",
    ]
    if any(t in haystack for t in infra_tokens):
        if "restart_driver" in allowed:
            actions.append(
                {
                    "name": "restart_driver",
                    "risk": "medium",
                    "reason": "suspected driver/CDP instability; restart driver (guarded)",
                }
            )
        if "restart_chrome" in allowed:
            actions.append(
                {
                    "name": "restart_chrome",
                    "risk": "medium",
                    "reason": "suspected Chrome/CDP instability; restart Chrome (guarded)",
                }
            )

    return actions


class RepairAutofixExecutor(BaseExecutor):
    """
    Codex-driven auto-fix job.

    This executor does NOT send any new prompts. It can perform guarded infra/UI actions (refresh/regenerate/restart)
    to help an existing ask job recover to completed, and writes a report under the repair job artifacts.
    """

    def __init__(self, *, cfg: AppConfig, tool_caller: ToolCaller | None, tool_caller_init_error: str | None = None) -> None:
        self._cfg = cfg
        self._tool_caller = tool_caller
        self._tool_caller_init_error = tool_caller_init_error

    async def run(self, *, job_id: str, kind: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:  # noqa: A002
        started = time.time()
        timeout_seconds = max(30, _as_int(params.get("timeout_seconds"), 600))
        model = _as_str(params.get("model"), "").strip() or default_repair_autofix_model()
        max_risk_raw = params.get("max_risk")
        max_risk = _as_str(max_risk_raw, "").strip().lower()
        max_risk_explicit = max_risk_raw is not None
        if not max_risk:
            env_default = _as_str(os.environ.get("CHATGPTREST_CODEX_AUTOFIX_MAX_RISK_DEFAULT"), "").strip().lower()
            if env_default:
                max_risk = env_default
                max_risk_explicit = True
        if not max_risk:
            max_risk = "low"
        apply_actions = _as_bool(params.get("apply_actions"), default=True)

        allow_actions = params.get("allow_actions")
        if allow_actions is None:
            allow_actions = os.environ.get(
                "CHATGPTREST_CODEX_AUTOFIX_ALLOW_ACTIONS",
                "restart_chrome,restart_driver,refresh,regenerate,capture_ui,clear_blocked,switch_gemini_proxy",
            )
        allowed = _parse_allow_actions(allow_actions)
        if not allowed:
            allowed = {"restart_chrome", "restart_driver"}

        target_job_id = _as_str(input.get("job_id") or input.get("target_job_id"), "").strip() or None
        symptom = _as_str(input.get("symptom") or input.get("error"), "").strip() or None
        conversation_url = _as_str(input.get("conversation_url"), "").strip() or None

        target_job_row: dict[str, Any] | None = None
        if target_job_id:
            try:
                with connect(self._cfg.db_path) as conn:
                    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (str(target_job_id),)).fetchone()
                if row is not None:
                    target_job_row = {"ok": True, **_job_summary_row(row)}
                    if not conversation_url:
                        conversation_url = _as_str(target_job_row.get("conversation_url"), "").strip() or None
                else:
                    target_job_row = {"ok": False, "error_type": "NotFound", "error": "job not found"}
            except Exception as exc:
                target_job_row = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:800]}
        target_kind = ""
        if isinstance(target_job_row, dict) and bool(target_job_row.get("ok")):
            target_kind = _as_str(target_job_row.get("kind"), "").strip()
        provider = _provider_from_kind(target_kind) or _conversation_platform(conversation_url) or "chatgpt"
        provider_tools = _provider_tools(provider)
        provider_cdp_url = _provider_cdp_url(provider)
        provider_chrome_start = _provider_chrome_start_script(provider)
        provider_chrome_stop = _provider_chrome_stop_script(provider)

        # Artifacts / evidence (best-effort)
        job_dir = (self._cfg.artifacts_dir / "jobs" / job_id).resolve()
        job_dir.mkdir(parents=True, exist_ok=True)
        codex_dir = job_dir / "codex"
        codex_dir.mkdir(parents=True, exist_ok=True)

        agents_md = _read_text((_REPO_ROOT / "AGENTS.md").resolve(), limit=50_000)
        playbook_md = _read_repair_playbook(limit=50_000)
        bootstrap_memory = load_maintagent_bootstrap_memory(max_chars=12_000)
        repo_memory = load_maintagent_repo_memory(max_chars=6_000)
        target_run_meta = None
        events_tail = ""
        if target_job_id:
            try:
                target_run_meta = _read_json((self._cfg.artifacts_dir / "jobs" / target_job_id / "run_meta.json").resolve())
            except Exception:
                target_run_meta = None
            try:
                ev_path = (self._cfg.artifacts_dir / "jobs" / target_job_id / "events.jsonl").resolve()
                if ev_path.exists():
                    # Tail last ~120 lines (best-effort)
                    raw = ev_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    events_tail = "\n".join(raw[-120:])
            except Exception:
                events_tail = ""

        # Default risk escalation for infra incidents: allow medium-risk actions (restart) unless the
        # caller explicitly pinned max_risk.
        if not max_risk_explicit:
            infra_tokens = [
                "page.goto",
                "timeout",
                "connect_over_cdp",
                "cdp connect failed",
                "target page, context or browser has been closed",
                "browsercontext.new_page",
                "driver blocked: network",
                "connection refused",
                "urlopen error",
            ]
            haystack = "\n".join(
                [
                    str(symptom or "").strip(),
                    _as_str((target_job_row or {}).get("last_error_type"), ""),
                    _as_str((target_job_row or {}).get("last_error"), ""),
                    _as_str((target_run_meta or {}).get("error_type"), "") if isinstance(target_run_meta, dict) else "",
                    _as_str((target_run_meta or {}).get("error"), "") if isinstance(target_run_meta, dict) else "",
                ]
            ).lower()
            if any(t in haystack for t in infra_tokens):
                max_risk = "medium"
            if provider == "gemini" and _looks_like_gemini_region_issue(haystack):
                max_risk = "medium"

        driver_probe: dict[str, Any] = {"ok": True}
        if self._tool_caller_init_error:
            driver_probe["ok"] = False
            driver_probe["init_error"] = self._tool_caller_init_error
        if self._tool_caller is not None:
            probe_tools: list[tuple[str, str]] = []
            for key in ("blocked_status", "rate_limit_status", "tab_stats"):
                tool_name = provider_tools.get(key)
                if isinstance(tool_name, str) and tool_name.strip():
                    probe_tools.append((key, tool_name))
            for key, tool_name in probe_tools:
                try:
                    driver_probe[key] = await _call_tool_with_hard_timeout(
                        tool_caller=self._tool_caller,
                        tool_name=tool_name,
                        tool_args={},
                        timeout_sec=min(15.0, float(timeout_seconds)),
                        hard_timeout_sec=min(25.0, float(timeout_seconds) + 10.0),
                    )
                except Exception as exc:
                    driver_probe["ok"] = False
                    driver_probe[f"{key}_error"] = f"{type(exc).__name__}: {exc}"
            if conversation_url:
                self_check_tool = provider_tools.get("self_check")
                if isinstance(self_check_tool, str) and self_check_tool.strip():
                    try:
                        driver_probe["self_check"] = await _call_tool_with_hard_timeout(
                            tool_caller=self._tool_caller,
                            tool_name=self_check_tool,
                            tool_args={"conversation_url": conversation_url, "timeout_seconds": 20},
                            timeout_sec=min(30.0, float(timeout_seconds)),
                            hard_timeout_sec=min(40.0, float(timeout_seconds) + 10.0),
                        )
                    except Exception as exc:
                        driver_probe["ok"] = False
                        driver_probe["self_check_error"] = f"{type(exc).__name__}: {exc}"
                else:
                    driver_probe["self_check"] = {
                        "skipped": True,
                        "skip_reason": "provider_self_check_not_supported",
                        "provider": provider,
                    }

        evidence: dict[str, Any] = {
            "ts": _now_iso(),
            "repair_job_id": job_id,
            "kind": kind,
            "symptom": symptom,
            "target_job": target_job_row,
            "target_run_meta": (_summarize_target_run_meta(target_run_meta) if isinstance(target_run_meta, dict) else None),
            "events_tail": (events_tail[:30_000] if events_tail else None),
            "conversation_url": conversation_url,
            "conversation_platform": _conversation_platform(conversation_url),
            "provider": provider,
            "env": {
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                "driver_mode": self._cfg.driver_mode,
                "driver_url": self._cfg.driver_url,
                "db_path": str(self._cfg.db_path),
                "artifacts_dir": str(self._cfg.artifacts_dir),
                "provider_cdp_url": provider_cdp_url,
                "proxy_env": _proxy_env_snapshot(),
            },
            "driver_probe": driver_probe,
            "provider_tools": {k: v for k, v in provider_tools.items() if isinstance(v, str) and v.strip()},
            "allowed_actions": sorted(allowed),
            "max_risk": max_risk,
        }
        if provider == "gemini":
            evidence["mihomo_proxy_probe"] = _collect_gemini_mihomo_probe()

        prompt = _build_codex_autofix_prompt(
            agents_md=agents_md,
            playbook_md=playbook_md,
            evidence=evidence,
            repo_memory_text=str(repo_memory.get("text") or ""),
            bootstrap_memory_text=str(bootstrap_memory.get("text") or ""),
        )
        prompt_path = codex_dir / "prompt.txt"
        try:
            prompt_path.write_text(prompt + "\n", encoding="utf-8")
        except Exception:
            pass

        # ── Circuit breaker: skip Codex if it failed too many times recently ──
        _circuit_breaker_max = _as_int(
            os.environ.get("CHATGPTREST_CODEX_AUTOFIX_CIRCUIT_BREAKER_MAX"), 3
        )
        _circuit_breaker_window = 600.0  # 10 minutes
        _codex_circuit_open = False
        if _circuit_breaker_max > 0 and target_job_id:
            try:
                from chatgptrest.core.incidents import count_actions
                with connect(self._cfg.db_path) as conn:
                    recent_failures = count_actions(
                        conn,
                        action_type="codex_autofix",
                        since_ts=time.time() - _circuit_breaker_window,
                    )
                if recent_failures >= _circuit_breaker_max:
                    _codex_circuit_open = True
                    evidence["codex_circuit_breaker"] = {
                        "open": True,
                        "recent_failures": recent_failures,
                        "max": _circuit_breaker_max,
                        "window_seconds": _circuit_breaker_window,
                    }
            except Exception:
                pass

        schema_path = (_REPO_ROOT / "ops" / "schemas" / "codex_sre_actions.schema.json").resolve()
        out_json = codex_dir / "sre_actions.json"
        reasoning_effort = _as_str(
            os.environ.get("CHATGPTREST_CODEX_AUTOFIX_REASONING_EFFORT"), "low"
        ).strip() or "low"
        codex_config_overrides = [f'model_reasoning_effort=\"{reasoning_effort}\"']
        disable_features_raw = _as_str(os.environ.get("CHATGPTREST_CODEX_AUTOFIX_DISABLE_FEATURES"), "").strip()
        codex_disable_features = (
            [p.strip() for p in disable_features_raw.split(",") if p.strip()]
            if disable_features_raw
            else []
        )
        codex_timeout_seconds = _as_int(
            os.environ.get("CHATGPTREST_CODEX_AUTOFIX_CODEX_TIMEOUT_SECONDS"),
            timeout_seconds,
        )
        if _codex_circuit_open:
            codex_meta = {"ok": False, "error": "circuit_breaker_open", "skipped": True}
        else:
            codex_meta = await asyncio.to_thread(
                _run_codex_with_schema,
                prompt=prompt,
                schema_path=schema_path,
                out_json=out_json,
                model=model,
                timeout_seconds=min(timeout_seconds, max(60, codex_timeout_seconds)),
                config_overrides=codex_config_overrides,
                disable_features=codex_disable_features,
            )

        actions_payload = _extract_actions_payload(codex_meta)
        codex_fallback_meta: dict[str, Any] | None = None
        fallback: dict[str, Any] | None = None
        enable_codex_maint_fallback = _as_bool(
            os.environ.get("CHATGPTREST_CODEX_AUTOFIX_ENABLE_MAINT_FALLBACK"),
            True,
        )
        if apply_actions and actions_payload is None and enable_codex_maint_fallback:
            fallback_prompt = _build_codex_autofix_fallback_prompt(
                evidence=evidence,
                prior_error=_as_str(codex_meta.get("error"), "") or _as_str(codex_meta.get("stderr"), ""),
            )
            fallback_prompt_path = codex_dir / "prompt_fallback.txt"
            try:
                fallback_prompt_path.write_text(fallback_prompt + "\n", encoding="utf-8")
            except Exception:
                pass

            fallback_out_json = codex_dir / "sre_actions_fallback.json"
            fallback_timeout_seconds = _as_int(
                os.environ.get("CHATGPTREST_CODEX_AUTOFIX_FALLBACK_TIMEOUT_SECONDS"),
                min(timeout_seconds, 180),
            )
            fallback_reasoning = _as_str(
                os.environ.get("CHATGPTREST_CODEX_AUTOFIX_FALLBACK_REASONING_EFFORT"),
                "minimal",
            ).strip() or "minimal"
            codex_fallback_meta = await asyncio.to_thread(
                _run_codex_with_schema,
                prompt=fallback_prompt,
                schema_path=schema_path,
                out_json=fallback_out_json,
                model=model,
                timeout_seconds=min(timeout_seconds, max(45, fallback_timeout_seconds)),
                config_overrides=[f'model_reasoning_effort=\"{fallback_reasoning}\"'],
                disable_features=codex_disable_features,
            )
            actions_payload = _extract_actions_payload(codex_fallback_meta)
            if actions_payload is not None:
                fallback = {
                    "used": True,
                    "reason": "codex_maint_agent_fallback",
                    "codex_fallback_ok": bool(codex_fallback_meta.get("ok")),
                }

        if apply_actions and actions_payload is None:
            planned = _fallback_autofix_actions(
                provider=provider,
                conversation_url=conversation_url,
                symptom=symptom,
                target_job=target_job_row,
                target_run_meta=target_run_meta if isinstance(target_run_meta, dict) else None,
                allowed=allowed,
            )
            if planned:
                actions_payload = {"actions": planned}
                fallback = {
                    "used": True,
                    "reason": "heuristic_fallback_after_codex_failure",
                    "planned_actions": planned,
                }
        applied: list[dict[str, Any]] = []

        def _record_applied(name: str, *, ok: bool, details: Any = None, error: str | None = None) -> None:
            item: dict[str, Any] = {"name": name, "ok": bool(ok)}
            if error:
                item["error"] = str(error)[:800]
            if details is not None:
                item["details"] = details
            applied.append(item)

        if apply_actions and isinstance(actions_payload, dict):
            actions = actions_payload.get("actions")
            if not isinstance(actions, list):
                actions = []
            for item in actions[:20]:
                if not isinstance(item, dict):
                    continue
                name = re.sub(r"[^a-z0-9_]+", "", str(item.get("name") or "").strip().lower())
                risk = str(item.get("risk") or "").strip().lower()
                if not name:
                    continue
                if name not in allowed:
                    _record_applied(name, ok=True, details={"skipped": True, "skip_reason": "not allowed"})
                    continue
                if not _risk_allows(risk=risk, max_risk=max_risk):
                    _record_applied(name, ok=True, details={"skipped": True, "skip_reason": "risk exceeds max_risk"})
                    continue

                # Guardrail: avoid infra restarts while any send-stage job is in flight.
                if name in {"restart_chrome", "restart_driver"}:
                    drain = _active_send_jobs(db_path=self._cfg.db_path)
                    if not bool(drain.get("ok")):
                        _record_applied(name, ok=False, error=str(drain.get("error") or "drain guard failed"), details=drain)
                        continue
                    if int(drain.get("count") or 0) > 0:
                        _record_applied(name, ok=True, details={"skipped": True, "skip_reason": "send_in_progress", "drain_guard": drain})
                        continue

                if name == "switch_gemini_proxy":
                    if provider != "gemini":
                        _record_applied(name, ok=True, details={"skipped": True, "skip_reason": "unsupported for provider", "provider": provider})
                        continue
                    mihomo_probe = evidence.get("mihomo_proxy_probe")
                    if not isinstance(mihomo_probe, dict):
                        mihomo_probe = _collect_gemini_mihomo_probe()
                    proxy = mihomo_probe.get("proxy") if isinstance(mihomo_probe.get("proxy"), dict) else {}
                    group = _as_str(proxy.get("group"), "").strip() or _gemini_mihomo_proxy_group()
                    current = _as_str(proxy.get("now"), "").strip()
                    choices = proxy.get("all") if isinstance(proxy.get("all"), list) else []
                    choices_set = {str(x).strip() for x in choices if str(x).strip()}
                    candidates = mihomo_probe.get("configured_candidates") if isinstance(mihomo_probe.get("configured_candidates"), list) else []
                    ordered_candidates = [str(x).strip() for x in candidates if str(x).strip()]
                    if not ordered_candidates:
                        _record_applied(
                            name,
                            ok=False,
                            error="CHATGPTREST_GEMINI_MIHOMO_CANDIDATES is empty; cannot choose a failover node",
                            details={"group": group, "current": current, "choices": sorted(choices_set)},
                        )
                        continue
                    target_node = None
                    for node in ordered_candidates:
                        if node == current:
                            continue
                        if choices_set and node not in choices_set:
                            continue
                        target_node = node
                        break
                    if not target_node:
                        _record_applied(
                            name,
                            ok=True,
                            details={
                                "skipped": True,
                                "skip_reason": "no_alternative_candidate",
                                "group": group,
                                "current": current,
                                "candidates": ordered_candidates,
                                "choices": sorted(choices_set),
                            },
                        )
                        continue
                    switched = _mihomo_set_proxy(group, target_node, timeout_seconds=10.0)
                    confirmed = _mihomo_get_proxy(group, timeout_seconds=5.0)
                    ok = bool(switched.get("ok")) and bool(confirmed.get("ok")) and _as_str(confirmed.get("now"), "").strip() == target_node
                    _record_applied(
                        name,
                        ok=ok,
                        details={
                            "group": group,
                            "current": current,
                            "target": target_node,
                            "switch": switched,
                            "confirmed": confirmed,
                        },
                        error=(None if ok else str(switched.get("error") or confirmed.get("error") or "mihomo switch verification failed")),
                    )
                    evidence["mihomo_proxy_probe"] = {
                        **(mihomo_probe if isinstance(mihomo_probe, dict) else {}),
                        "proxy": confirmed if isinstance(confirmed, dict) else proxy,
                    }
                    continue

                if name == "restart_chrome":
                    default_chatgpt_port = int(_parse_host_port_from_url(_default_chatgpt_cdp_url(), default_port=9222)[1])
                    hp = _parse_host_port_from_url(
                        provider_cdp_url,
                        default_port=(9335 if provider == "qwen" else default_chatgpt_port),
                    )
                    host, port = ("127.0.0.1", int(9335 if provider == "qwen" else default_chatgpt_port)) if hp is None else hp
                    probe_host = "127.0.0.1" if host == "0.0.0.0" else host
                    details: dict[str, Any] = {
                        "provider": provider,
                        "cdp_url": provider_cdp_url,
                        "host": host,
                        "port": int(port),
                    }

                    # Prefer systemd unit when available (prevents duplicate watchdogs/scripts).
                    if provider != "qwen":
                        ok_sys, out_sys = _run_cmd(
                            ["systemctl", "--user", "restart", "chatgptrest-chrome.service"],
                            cwd=_REPO_ROOT,
                            timeout_seconds=20.0,
                        )
                        details["systemd_restart"] = {
                            "ok": ok_sys,
                            "unit": "chatgptrest-chrome.service",
                            "output": out_sys,
                        }
                        if ok_sys:
                            deadline = time.time() + 20.0
                            opened = False
                            while time.time() < deadline:
                                if _port_open(probe_host, int(port), timeout_seconds=0.2):
                                    opened = True
                                    break
                                time.sleep(0.25)
                            _record_applied(
                                name,
                                ok=opened,
                                details=details,
                                error=(None if opened else f"CDP port did not open: {probe_host}:{int(port)}"),
                            )
                            continue

                    chrome_stop = provider_chrome_stop
                    chrome_start = provider_chrome_start
                    if not chrome_stop.exists():
                        _record_applied(name, ok=False, error=f"missing: {chrome_stop}", details=details)
                        continue
                    if not chrome_start.exists():
                        _record_applied(name, ok=False, error=f"missing: {chrome_start}", details=details)
                        continue

                    # Force local endpoints to bypass proxy for the stop/start scripts.
                    cmd = (
                        "NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost "
                        f"bash {chrome_stop} || true; "
                        "NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost "
                        f"bash {chrome_start}"
                    )
                    ok, out = _run_cmd(["bash", "-lc", cmd], cwd=_REPO_ROOT, timeout_seconds=120.0)
                    details["cmd"] = cmd
                    details["output"] = out
                    if ok:
                        deadline = time.time() + 20.0
                        opened = False
                        while time.time() < deadline:
                            if _port_open(probe_host, int(port), timeout_seconds=0.2):
                                opened = True
                                break
                            time.sleep(0.25)
                        details["port_open"] = bool(opened)
                        ok = bool(opened)
                        if not ok:
                            out = f"{out}\nCDP port did not open: {probe_host}:{int(port)}".strip()
                    _record_applied(name, ok=ok, details=details, error=(None if ok else out))
                    continue

                if name == "restart_driver":
                    # Best-effort: kill listener (if any) then start driver via ops/start_driver.sh.
                    hp = _parse_host_port_from_url(self._cfg.driver_url, default_port=18701)
                    if hp is None:
                        _record_applied(name, ok=False, error=f"invalid driver_url: {self._cfg.driver_url}")
                        continue
                    host, port = hp
                    probe_host = "127.0.0.1" if host == "0.0.0.0" else host
                    details: dict[str, Any] = {"host": host, "port": int(port)}
                    unit_name = "chatgptrest-driver.service"
                    load_state = _systemd_unit_load_state(unit_name, cwd=_REPO_ROOT)
                    details["systemd_load_state"] = load_state
                    systemd_managed = load_state == "loaded"

                    ok_reset, out_reset = _run_cmd(
                        ["systemctl", "--user", "reset-failed", unit_name],
                        cwd=_REPO_ROOT,
                        timeout_seconds=10.0,
                    )
                    details["systemd_reset_failed"] = {
                        "ok": ok_reset,
                        "unit": unit_name,
                        "output": out_reset,
                    }

                    ok_sys, out_sys = _run_cmd(
                        ["systemctl", "--user", "restart", unit_name],
                        cwd=_REPO_ROOT,
                        timeout_seconds=20.0,
                    )
                    if (not ok_sys) and ("start-limit-hit" in str(out_sys or "").lower()):
                        ok_reset2, out_reset2 = _run_cmd(
                            ["systemctl", "--user", "reset-failed", unit_name],
                            cwd=_REPO_ROOT,
                            timeout_seconds=10.0,
                        )
                        details["systemd_reset_failed_retry"] = {
                            "ok": ok_reset2,
                            "unit": unit_name,
                            "output": out_reset2,
                        }
                        ok_sys, out_sys = _run_cmd(
                            ["systemctl", "--user", "restart", unit_name],
                            cwd=_REPO_ROOT,
                            timeout_seconds=20.0,
                        )
                    details["systemd_restart"] = {
                        "ok": ok_sys,
                        "unit": unit_name,
                        "output": out_sys,
                    }
                    if ok_sys:
                        deadline = time.time() + 20.0
                        opened = False
                        while time.time() < deadline:
                            if _port_open(probe_host, int(port), timeout_seconds=0.2):
                                opened = True
                                break
                            time.sleep(0.25)
                        details["port_open"] = bool(opened)
                        _record_applied(name, ok=opened, details=details, error=(None if opened else "driver port did not open"))
                        continue

                    if systemd_managed:
                        _record_applied(
                            name,
                            ok=False,
                            error=(
                                "systemd-managed driver restart failed; "
                                "script fallback skipped to avoid singleton-lock conflicts"
                            ),
                            details=details,
                        )
                        continue

                    try:
                        ok, out = _run_cmd(["bash", "-lc", f"lsof -nP -iTCP:{int(port)} -sTCP:LISTEN -t"], timeout_seconds=3.0)
                        pids = [int(x) for x in out.split() if x.isdigit()]
                    except Exception:
                        pids = []
                    details["listener_pids"] = pids
                    for pid in pids:
                        try:
                            os.kill(int(pid), 15)
                        except Exception:
                            pass
                    if pids:
                        time.sleep(0.4)
                    if pids and _port_open(probe_host, int(port), timeout_seconds=0.2):
                        for pid in pids:
                            try:
                                os.kill(int(pid), 9)
                            except Exception:
                                pass
                        time.sleep(0.4)

                    start_script = (_REPO_ROOT / "ops" / "start_driver.sh").resolve()
                    if not start_script.exists():
                        _record_applied(name, ok=False, error=f"missing: {start_script}", details=details)
                        continue

                    log_file = codex_dir / "driver_restart.log"
                    env = dict(os.environ)
                    env.setdefault("CHATGPT_CDP_URL", (os.environ.get("CHATGPT_CDP_URL") or "http://127.0.0.1:9222").strip())
                    env.setdefault("GEMINI_CDP_URL", (os.environ.get("GEMINI_CDP_URL") or env.get("CHATGPT_CDP_URL") or "").strip())
                    env.setdefault("QWEN_CDP_URL", (os.environ.get("QWEN_CDP_URL") or "http://127.0.0.1:9335").strip())
                    try:
                        with log_file.open("a", encoding="utf-8") as f:
                            proc = subprocess.Popen(
                                ["bash", str(start_script)],
                                cwd=str(_REPO_ROOT),
                                env=env,
                                stdout=f,
                                stderr=subprocess.STDOUT,
                                start_new_session=True,
                            )
                        details["started_pid"] = int(proc.pid)
                    except Exception as exc:
                        _record_applied(name, ok=False, error=f"{type(exc).__name__}: {exc}", details=details)
                        continue

                    deadline = time.time() + 15.0
                    opened = False
                    while time.time() < deadline:
                        if _port_open(probe_host, int(port), timeout_seconds=0.2):
                            opened = True
                            break
                        time.sleep(0.25)
                    details["port_open"] = bool(opened)
                    details["provider"] = provider
                    _record_applied(name, ok=opened, details=details, error=(None if opened else "driver port did not open"))
                    continue

                if name in {"refresh", "regenerate"}:
                    if self._tool_caller is None:
                        _record_applied(name, ok=False, error="driver tool_caller unavailable")
                        continue
                    if not conversation_url:
                        _record_applied(name, ok=True, details={"skipped": True, "skip_reason": "missing conversation_url"})
                        continue
                    refresh_tool = provider_tools.get("refresh")
                    regenerate_tool = provider_tools.get("regenerate")
                    tool = refresh_tool if name == "refresh" else regenerate_tool
                    if not (isinstance(tool, str) and tool.strip()):
                        _record_applied(name, ok=True, details={"skipped": True, "skip_reason": "unsupported for provider", "provider": provider})
                        continue
                    tool_args: dict[str, Any] = {"conversation_url": conversation_url}
                    if name == "regenerate":
                        tool_args["timeout_seconds"] = min(900, timeout_seconds)
                        tool_args["min_chars"] = 0
                    else:
                        tool_args["timeout_seconds"] = min(90, timeout_seconds)
                    try:
                        res = await _call_tool_with_hard_timeout(
                            tool_caller=self._tool_caller,
                            tool_name=tool,
                            tool_args=tool_args,
                            timeout_sec=min(float(timeout_seconds), 120.0),
                            hard_timeout_sec=min(float(timeout_seconds), 120.0) + 10.0,
                        )
                        ok = bool((res or {}).get("ok")) and str((res or {}).get("status") or "").strip().lower() in {"completed"}
                        _record_applied(name, ok=ok, details=res, error=(None if ok else str((res or {}).get("error") or "tool failed")))
                    except Exception as exc:
                        _record_applied(name, ok=False, error=f"{type(exc).__name__}: {exc}")
                    continue

                if name == "clear_blocked":
                    if self._tool_caller is None:
                        _record_applied(name, ok=False, error="driver tool_caller unavailable")
                        continue
                    clear_blocked_tool = provider_tools.get("clear_blocked")
                    if not (isinstance(clear_blocked_tool, str) and clear_blocked_tool.strip()):
                        _record_applied(name, ok=True, details={"skipped": True, "skip_reason": "unsupported for provider", "provider": provider})
                        continue
                    try:
                        res = await _call_tool_with_hard_timeout(
                            tool_caller=self._tool_caller,
                            tool_name=clear_blocked_tool,
                            tool_args={},
                            timeout_sec=30.0,
                            hard_timeout_sec=40.0,
                        )
                        ok = bool((res or {}).get("ok"))
                        _record_applied(name, ok=ok, details=res, error=(None if ok else str((res or {}).get("error") or "tool failed")))
                    except Exception as exc:
                        _record_applied(name, ok=False, error=f"{type(exc).__name__}: {exc}")
                    continue

                if name == "capture_ui":
                    if self._tool_caller is None:
                        _record_applied(name, ok=False, error="driver tool_caller unavailable")
                        continue
                    capture_ui_tool = provider_tools.get("capture_ui")
                    if not (isinstance(capture_ui_tool, str) and capture_ui_tool.strip()):
                        _record_applied(name, ok=True, details={"skipped": True, "skip_reason": "unsupported for provider", "provider": provider})
                        continue
                    out_dir = (job_dir / f"{provider}_ui_snapshots").resolve()
                    try:
                        tool_args: dict[str, Any] = {
                            "mode": "basic",
                            "timeout_seconds": 120,
                            "out_dir": str(out_dir),
                            "write_doc": False,
                        }
                        if conversation_url:
                            tool_args["conversation_url"] = conversation_url
                        res = await _call_tool_with_hard_timeout(
                            tool_caller=self._tool_caller,
                            tool_name=capture_ui_tool,
                            tool_args=tool_args,
                            timeout_sec=150.0,
                            hard_timeout_sec=165.0,
                        )
                        ok = bool((res or {}).get("ok"))
                        _record_applied(name, ok=ok, details=res, error=(None if ok else str((res or {}).get("error") or "tool failed")))
                    except Exception as exc:
                        _record_applied(name, ok=False, error=f"{type(exc).__name__}: {exc}")
                    continue

                _record_applied(name, ok=True, details={"skipped": True, "skip_reason": f"unsupported action: {name}"})

        report: dict[str, Any] = {
            "ok": True,
            "ts": _now_iso(),
            "repair_job_id": job_id,
            "target_job_id": target_job_id,
            "conversation_url": conversation_url,
            "provider": provider,
            "codex": codex_meta,
            "codex_fallback": codex_fallback_meta,
            "fallback": fallback,
            "applied_actions": applied,
            "elapsed_ms": int(round((time.time() - started) * 1000)),
        }
        report_path = (job_dir / "repair_autofix_report.json").resolve()
        try:
            _atomic_write_json(report_path, report)
        except Exception:
            pass

        lines: list[str] = []
        lines.append("# repair.autofix report")
        lines.append("")
        lines.append(f"- ts: `{report.get('ts')}`")
        lines.append(f"- repair_job_id: `{job_id}`")
        if target_job_id:
            lines.append(f"- target_job_id: `{target_job_id}`")
        if conversation_url:
            lines.append(f"- conversation_url: `{conversation_url}`")
        lines.append(f"- codex_ok: `{bool(codex_meta.get('ok'))}`")
        if isinstance(codex_fallback_meta, dict):
            lines.append(f"- codex_fallback_ok: `{bool(codex_fallback_meta.get('ok'))}`")
        if isinstance(fallback, dict) and fallback.get("used"):
            lines.append(f"- fallback_used: `true` ({str(fallback.get('reason') or 'unknown')})")
        lines.append(f"- report_path: `{(Path('jobs') / job_id / 'repair_autofix_report.json').as_posix()}`")
        lines.append("")
        lines.append("## Applied Actions")
        if not applied:
            lines.append("- (none)")
        else:
            for a in applied[:20]:
                name = str(a.get("name") or "")
                ok = bool(a.get("ok"))
                err = str(a.get("error") or "").strip()
                if err:
                    lines.append(f"- {name}: ok=`{ok}` error={err}")
                else:
                    lines.append(f"- {name}: ok=`{ok}`")
        lines.append("")

        meta = {
            "repair_autofix_report_path": (Path("jobs") / job_id / "repair_autofix_report.json").as_posix(),
            "repair_elapsed_ms": report.get("elapsed_ms"),
            "target_job_id": target_job_id,
            "provider": provider,
            "codex_ok": bool(codex_meta.get("ok")),
        }
        return ExecutorResult(status="completed", answer="\n".join(lines), answer_format="markdown", meta=meta)


class RepairOpenPrExecutor(BaseExecutor):
    """
    Codex-driven PR generator.

    This job is intended for maintainers: it asks Codex to propose a minimal patch (git diff) and
    can optionally apply it in a git worktree, run tests, commit, push, and open a GitHub PR.
    """

    def __init__(self, *, cfg: AppConfig, tool_caller: ToolCaller | None, tool_caller_init_error: str | None = None) -> None:
        self._cfg = cfg
        self._tool_caller = tool_caller
        self._tool_caller_init_error = tool_caller_init_error

    async def run(self, *, job_id: str, kind: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:  # noqa: A002
        started = time.time()

        mode = _as_str(params.get("mode"), "p0").strip().lower() or "p0"
        if mode not in {"p0", "p1", "p2"}:
            mode = "p0"

        timeout_seconds = max(60, _as_int(params.get("timeout_seconds"), 900))
        model = _as_str(params.get("model"), "").strip() or None

        remote = _as_str(params.get("remote"), "origin").strip() or "origin"
        base_ref = _as_str(params.get("base_ref"), "HEAD").strip() or "HEAD"
        base_branch = _as_str(params.get("base_branch"), "master").strip() or "master"

        run_tests = _as_bool(params.get("run_tests"), default=(mode in {"p1", "p2"}))
        push = _as_bool(params.get("push"), default=(mode == "p2"))
        create_pr = _as_bool(params.get("create_pr"), default=(mode == "p2"))

        target_job_id = _as_str(input.get("job_id") or input.get("target_job_id"), "").strip() or None
        symptom = _as_str(input.get("symptom") or input.get("error"), "").strip() or None
        extra_instructions = _as_str(input.get("instructions"), "").strip() or None

        job_dir = (self._cfg.artifacts_dir / "jobs" / job_id).resolve()
        codex_dir = (job_dir / "codex_pr").resolve()
        codex_dir.mkdir(parents=True, exist_ok=True)

        target_job_row: dict[str, Any] | None = None
        if target_job_id:
            try:
                with connect(self._cfg.db_path) as conn:
                    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (str(target_job_id),)).fetchone()
                if row is not None:
                    target_job_row = {"ok": True, **_job_summary_row(row)}
                else:
                    target_job_row = {"ok": False, "error_type": "NotFound", "error": "job not found"}
            except Exception as exc:
                target_job_row = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:500]}

        target_run_meta: dict[str, Any] | None = None
        debug_text = ""
        if target_job_id:
            try:
                run_meta_path = (self._cfg.artifacts_dir / "jobs" / target_job_id / "run_meta.json").resolve()
                if run_meta_path.exists():
                    raw = _read_json(run_meta_path)
                    if isinstance(raw, dict):
                        target_run_meta = raw
                        da = raw.get("debug_artifacts")
                        if isinstance(da, dict):
                            txt = da.get("text")
                            if isinstance(txt, str) and txt.strip():
                                p = (self._cfg.artifacts_dir / txt.strip()).resolve()
                                if p.exists():
                                    debug_text = _read_text(p, limit=80_000)
            except Exception:
                target_run_meta = None
                debug_text = ""

        agents_md = _read_text((_REPO_ROOT / "AGENTS.md").resolve(), limit=60_000)

        evidence: dict[str, Any] = {
            "ts": _now_iso(),
            "repair_job_id": job_id,
            "kind": kind,
            "mode": mode,
            "symptom": symptom,
            "target_job": target_job_row,
            "target_run_meta": (_summarize_target_run_meta(target_run_meta) if isinstance(target_run_meta, dict) else None),
            "target_debug_text": (debug_text[:30_000] if debug_text else None),
            "env": {
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                "db_path": str(self._cfg.db_path),
                "artifacts_dir": str(self._cfg.artifacts_dir),
                "repo_root": str(_REPO_ROOT),
            },
        }

        prompt_lines: list[str] = []
        prompt_lines.append("You are a senior maintainer agent for the ChatgptREST repository.")
        prompt_lines.append("")
        prompt_lines.append("Goal: propose a minimal, correct patch that fixes the incident described in the Evidence.")
        prompt_lines.append("")
        prompt_lines.append("Hard constraints:")
        prompt_lines.append("- Return JSON matching the provided JSON Schema.")
        prompt_lines.append("- The `diff` must be a unified diff that is `git apply` compatible.")
        prompt_lines.append("- Keep changes minimal; do not touch unrelated files.")
        prompt_lines.append("- Prefer fixing root cause (selectors/status semantics/robust retries) over superficial workarounds.")
        prompt_lines.append("- If you add tests, keep them small and focused.")
        prompt_lines.append("")
        if extra_instructions:
            prompt_lines.append("=== Extra Instructions ===")
            prompt_lines.append(extra_instructions)
            prompt_lines.append("")
        if agents_md.strip():
            prompt_lines.append("=== AGENTS.md (truncated) ===")
            prompt_lines.append(agents_md.strip())
            prompt_lines.append("")
        prompt_lines.append("=== Evidence (JSON) ===")
        prompt_lines.append(json.dumps(evidence, ensure_ascii=False, indent=2)[:120_000])
        prompt_lines.append("")
        prompt = "\n".join(prompt_lines).strip()

        prompt_path = codex_dir / "prompt.txt"
        try:
            prompt_path.write_text(prompt + "\n", encoding="utf-8")
        except Exception:
            pass

        schema_path = (_REPO_ROOT / "ops" / "schemas" / "codex_sre_patch.schema.json").resolve()
        out_json = codex_dir / "codex_patch.json"
        codex_meta = await asyncio.to_thread(
            _run_codex_with_schema,
            prompt=prompt,
            schema_path=schema_path,
            out_json=out_json,
            model=model,
            timeout_seconds=min(timeout_seconds, max(120, timeout_seconds)),
            cd=_REPO_ROOT,
        )

        output = codex_meta.get("output") if isinstance(codex_meta.get("output"), dict) else None
        diff_text = str((output or {}).get("diff") or "").strip() if isinstance(output, dict) else ""
        tests_suggested = (output or {}).get("tests") if isinstance(output, dict) else None
        commit_message = str((output or {}).get("commit_message") or "").strip() if isinstance(output, dict) else ""
        pr_title = str((output or {}).get("pr_title") or "").strip() if isinstance(output, dict) else ""
        pr_body = str((output or {}).get("pr_body") or "").strip() if isinstance(output, dict) else ""

        patch_path = codex_dir / "patch.diff"
        if diff_text:
            try:
                patch_path.write_text(diff_text + ("\n" if not diff_text.endswith("\n") else ""), encoding="utf-8")
            except Exception:
                pass

        worktree_path: Path | None = None
        branch_name: str | None = None
        git_ops: dict[str, Any] = {"ok": True, "mode": mode}
        if mode in {"p1", "p2"} and diff_text:
            worktrees_root = (_REPO_ROOT / "state" / "worktrees").resolve()
            try:
                worktrees_root.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            worktree_path = (worktrees_root / f"repair_pr_{job_id}").resolve()
            branch_name = f"repair/{job_id}"

            ok, out = _run_cmd(
                [
                    "git",
                    "worktree",
                    "add",
                    "-b",
                    branch_name,
                    str(worktree_path),
                    str(base_ref),
                ],
                cwd=_REPO_ROOT,
                timeout_seconds=120.0,
            )
            git_ops["worktree_add"] = {"ok": ok, "out": out}
            if not ok:
                worktree_path = None
                branch_name = None

        applied_ok = False
        tests_ok = None
        commit_ok = None
        push_ok = None
        pr_url: str | None = None

        if worktree_path is not None and branch_name is not None and diff_text:
            ok, out = _run_cmd(["git", "apply", "--whitespace=fix", str(patch_path)], cwd=worktree_path, timeout_seconds=120.0)
            git_ops["git_apply"] = {"ok": ok, "out": out}
            applied_ok = ok

            if ok and run_tests:
                tests_cmd = "./.venv/bin/pytest -q"
                if isinstance(tests_suggested, list) and tests_suggested:
                    first = str(tests_suggested[0] or "").strip()
                    if first:
                        tests_cmd = first
                ok_t, out_t = _run_cmd(["bash", "-lc", tests_cmd], cwd=worktree_path, timeout_seconds=float(timeout_seconds))
                git_ops["tests"] = {"ok": ok_t, "cmd": tests_cmd, "out": out_t}
                tests_ok = ok_t

            if ok:
                ok_names, out_names = _run_cmd(["git", "diff", "--name-only"], cwd=worktree_path, timeout_seconds=30.0)
                names = [ln.strip() for ln in out_names.splitlines() if ln.strip()] if ok_names else []
                if names:
                    _run_cmd(["git", "add", "--"] + names, cwd=worktree_path, timeout_seconds=30.0)
                ok_c, out_c = _run_cmd(
                    ["git", "commit", "-m", commit_message or f"repair: propose fix for {target_job_id or job_id}"],
                    cwd=worktree_path,
                    timeout_seconds=60.0,
                )
                git_ops["commit"] = {"ok": ok_c, "out": out_c}
                commit_ok = ok_c

                if ok_c and push:
                    ok_p, out_p = _run_cmd(["git", "push", "-u", remote, branch_name], cwd=worktree_path, timeout_seconds=120.0)
                    git_ops["push"] = {"ok": ok_p, "out": out_p}
                    push_ok = ok_p

                if ok_c and push and create_pr:
                    ok_pr, out_pr = _run_cmd(
                        [
                            "gh",
                            "pr",
                            "create",
                            "--head",
                            branch_name,
                            "--base",
                            base_branch,
                            "--title",
                            pr_title or (commit_message.splitlines()[0] if commit_message else f"repair: {job_id}"),
                            "--body",
                            pr_body or "Automated PR generated by ChatgptREST repair.open_pr.",
                        ],
                        cwd=worktree_path,
                        timeout_seconds=120.0,
                    )
                    git_ops["pr_create"] = {"ok": ok_pr, "out": out_pr}
                    if ok_pr:
                        for line in out_pr.splitlines():
                            if "http" in line:
                                pr_url = line.strip()
                                break

        report: dict[str, Any] = {
            "ok": True,
            "ts": _now_iso(),
            "repair_job_id": job_id,
            "target_job_id": target_job_id,
            "mode": mode,
            "codex": codex_meta,
            "git": git_ops,
            "applied_ok": applied_ok,
            "tests_ok": tests_ok,
            "commit_ok": commit_ok,
            "push_ok": push_ok,
            "pr_url": pr_url,
            "elapsed_ms": int(round((time.time() - started) * 1000)),
        }
        report_path = (job_dir / "repair_open_pr_report.json").resolve()
        try:
            _atomic_write_json(report_path, report)
        except Exception:
            pass

        lines: list[str] = []
        lines.append("# repair.open_pr report")
        lines.append("")
        lines.append(f"- ts: `{report.get('ts')}`")
        lines.append(f"- repair_job_id: `{job_id}`")
        lines.append(f"- mode: `{mode}`")
        if target_job_id:
            lines.append(f"- target_job_id: `{target_job_id}`")
        if worktree_path is not None:
            lines.append(f"- worktree: `{worktree_path}`")
        if branch_name is not None:
            lines.append(f"- branch: `{branch_name}` remote=`{remote}` base_ref=`{base_ref}` base_branch=`{base_branch}`")
        if pr_url:
            lines.append(f"- pr_url: `{pr_url}`")
        lines.append(f"- codex_ok: `{bool(codex_meta.get('ok'))}`")
        lines.append(f"- report_path: `{(Path('jobs') / job_id / 'repair_open_pr_report.json').as_posix()}`")
        lines.append("")
        if diff_text:
            lines.append("## Patch")
            lines.append(f"- patch_path: `{(Path('jobs') / job_id / 'codex_pr' / 'patch.diff').as_posix()}`")
            lines.append("")
        lines.append("## Results")
        lines.append(f"- applied_ok: `{applied_ok}`")
        if tests_ok is not None:
            lines.append(f"- tests_ok: `{tests_ok}`")
        if commit_ok is not None:
            lines.append(f"- commit_ok: `{commit_ok}`")
        if push_ok is not None:
            lines.append(f"- push_ok: `{push_ok}`")
        lines.append("")

        meta = {
            "repair_open_pr_report_path": (Path("jobs") / job_id / "repair_open_pr_report.json").as_posix(),
            "target_job_id": target_job_id,
            "branch": branch_name,
            "worktree": (str(worktree_path) if worktree_path is not None else None),
            "pr_url": pr_url,
        }
        return ExecutorResult(status="completed", answer="\n".join(lines), answer_format="markdown", meta=meta)
