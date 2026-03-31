#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import sqlite3
import socket
import threading
import sys
import time
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chatgptrest.core import job_store, mihomo_delay
from chatgptrest.core.db import ensure_db_initialized
from chatgptrest.core import incidents as incident_db
from chatgptrest.core.build_info import get_build_info
from chatgptrest.core.control_plane import (
    is_local_host as _shared_is_local_host,
    port_open as port_open,
    resolve_chatgptrest_api_host_port as _shared_chatgptrest_api_host_port,
    start_local_api as _shared_start_local_api,
)
from chatgptrest.core.completion_contract import (
    canonical_answer_from_job_like,
    completion_contract_from_job_like,
    resolve_authoritative_answer_artifact,
)
from chatgptrest.core.pause import clear_pause_state, get_pause_state, set_pause_state
from chatgptrest.core.repair_jobs import (
    create_repair_autofix_job as _create_repair_autofix_job,
    create_repair_check_job as _create_repair_check_job,
    source_job_uses_synthetic_or_trivial_prompt as _source_job_uses_synthetic_or_trivial_prompt,
    requested_by_transport as _requested_by_transport,
)
from chatgptrest.executors.sre import execute_sre_fix_request_controller
from chatgptrest.driver import ToolCallError, ToolCaller, build_tool_caller, normalize_driver_mode
from chatgptrest.ops_shared.actions import parse_allow_actions, risk_allows
from chatgptrest.ops_shared.infra import (
    atomic_write_json,
    http_json,
    now_iso,
    port_open,
    read_json,
    read_text,
    run_cmd,
    systemd_unit_load_state,
    truncate_text,
)
from chatgptrest.ops_shared.provider import provider_from_kind, provider_tools
from chatgptrest.ops_shared.budget import parse_ts_list, trim_window
from chatgptrest.ops_shared.correlation import (
    incident_freshness_gate,
    incident_should_rollover_for_signal,
    incident_signal_is_fresh,
    looks_like_infra_job_error,
    normalize_error,
    sig_hash,
)
from chatgptrest.ops_shared.models import IncidentState, job_expected_max_seconds
from chatgptrest.ops_shared.subsystem import SubsystemRunner, TickContext
from chatgptrest.ops_shared.behavior_issues import BehaviorIssueSubsystem
from chatgptrest.ops_shared.subsystems import (
    AutoResolveSubsystem,
    BlockedStateSubsystem,
    HealthCheckSubsystem,
    JobsSummarySubsystem,
)
from chatgptrest.ops_shared.maint_memory import load_maintagent_action_preferences, merge_maintagent_bootstrap_into_markdown

# ── submodule imports (extracted for decomposition) ───────────────────
# Sibling modules live in the same ops/ directory.
# Ensure they are importable whether we are loaded as a package member
# or via spec_from_file_location (test harness).
import importlib.util as _ilu

def _load_sibling(name: str) -> Any:
    """Import a sibling .py from the same directory as this file."""
    _p = Path(__file__).resolve().parent / f"{name}.py"
    _spec = _ilu.spec_from_file_location(name, _p)
    assert _spec and _spec.loader, f"Cannot find sibling module: {_p}"
    _mod = _ilu.module_from_spec(_spec)
    sys.modules.setdefault(name, _mod)
    _spec.loader.exec_module(_mod)
    return _mod

_maint_util = _load_sibling("_maint_util")
_maint_codex_memory = _load_sibling("_maint_codex_memory")


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
def _http_json_no_proxy(url: str, *, headers: dict[str, str] | None = None, timeout_seconds: float = 5.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=(headers or {}), method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=float(timeout_seconds)) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            return json.loads(text) if text.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": f"http_{e.code}", "error": raw[:500]}
    except Exception as exc:
        return {"ok": False, "status": "error", "error_type": type(exc).__name__, "error": str(exc)[:500]}


def _mihomo_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    auth = os.environ.get("MIHOMO_AUTHORIZATION")
    if auth and auth.strip():
        headers["Authorization"] = auth.strip()
        return headers
    secret = os.environ.get("MIHOMO_SECRET")
    if secret and secret.strip():
        headers["Authorization"] = f"Bearer {secret.strip()}"
    return headers


def _mihomo_probe_delay(
    *,
    controller: str,
    name: str,
    url: str,
    timeout_ms: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    quoted_name = urllib.parse.quote(str(name), safe="")
    quoted_url = urllib.parse.quote(str(url), safe="")
    endpoint = f"{str(controller).rstrip('/')}/proxies/{quoted_name}/delay?timeout={int(timeout_ms)}&url={quoted_url}"
    started = time.time()
    headers = _mihomo_headers()
    payload = _http_json_no_proxy(endpoint, headers=headers, timeout_seconds=float(timeout_seconds))
    delay = payload.get("delay") if isinstance(payload, dict) else None
    ok = isinstance(delay, (int, float))
    return {
        "name": str(name),
        "ok": bool(ok),
        "delay_ms": (int(delay) if ok else None),
        "elapsed_ms": int(round((time.time() - started) * 1000)),
        "endpoint": endpoint,
        "error": (None if ok else (payload.get("error") if isinstance(payload, dict) else str(payload))),
        "error_type": (None if ok else (payload.get("error_type") if isinstance(payload, dict) else None)),
        "status": (payload.get("status") if isinstance(payload, dict) else None),
    }


def _pick_latest_mihomo_log(mihomo_delay_dir: Path) -> Path | None:
    # Prefer local day (matches mihomo_delay_snapshot.py).
    candidates = [
        mihomo_delay_dir / f"mihomo_delay_{time.strftime('%Y%m%d')}.jsonl",
        mihomo_delay_dir / f"mihomo_delay_{datetime.now(UTC).strftime('%Y%m%d')}.jsonl",
    ]
    for p in candidates:
        if p.exists():
            return p
    # Fallback: newest by filename.
    try:
        paths = sorted(mihomo_delay_dir.glob("mihomo_delay_*.jsonl"))
    except Exception:
        paths = []
    return paths[-1] if paths else None


def _robust_percentile(values: list[int], q: float) -> int | None:
    if not values:
        return None
    v = sorted(int(x) for x in values)
    n = len(v)
    if q <= 0:
        return v[0]
    if q >= 1:
        return v[-1]
    idx = max(0, min(n - 1, int(round((n - 1) * float(q)))))
    return v[idx]


def _collect_recent_ok_delays(*, log_paths_desc: list[Path], group: str, selected: str, max_samples: int) -> list[int]:
    g = str(group or "")
    s = str(selected or "")
    out: list[int] = []
    for p in log_paths_desc:
        rows = mihomo_delay.tail_jsonl(p, max_lines=2000)
        for r in reversed(rows):
            if str(r.get("group") or "") != g:
                continue
            if str(r.get("selected") or "") != s:
                continue
            if not bool(r.get("ok")):
                continue
            dm = r.get("delay_ms")
            if isinstance(dm, (int, float)):
                out.append(int(dm))
            if len(out) >= max(1, int(max_samples)):
                return out
    return out


def _collect_last_ok_record(*, log_paths_desc: list[Path], group: str, selected: str) -> dict[str, Any] | None:
    g = str(group or "")
    s = str(selected or "")
    for p in log_paths_desc:
        rows = mihomo_delay.tail_jsonl(p, max_lines=2000)
        last_ok = mihomo_delay.last_success_record(records=rows, group=g, selected=s)
        if last_ok is not None:
            return last_ok
    return None


_MIHOMO_CANDIDATE_SKIP_RE = re.compile(r"(套餐到期日期|订阅获取时间)")


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


def _incident_provider(*, kind: str | None, conversation_url: str | None) -> str:
    return provider_from_kind(kind) or _conversation_platform(conversation_url) or "chatgpt"


_UI_CANARY_PROVIDERS = ("chatgpt", "gemini")


def _default_ui_canary_providers() -> list[str]:
    return ["chatgpt", "gemini"]


def _parse_ui_canary_providers(raw: str | None) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return _default_ui_canary_providers()
    parts = re.split(r"[,\s]+", text)
    out: list[str] = []
    for p in parts:
        s = str(p or "").strip().lower()
        if not s:
            continue
        if s not in _UI_CANARY_PROVIDERS:
            continue
        if s in out:
            continue
        out.append(s)
    return out or _default_ui_canary_providers()


def _ui_canary_default_state() -> dict[str, Any]:
    return {
        "last_run_ts": 0.0,
        "last_ok_ts": 0.0,
        "last_failure_ts": 0.0,
        "consecutive_failures": 0,
        "last_capture_ts": 0.0,
        "last_incident_ts": 0.0,
        "last_status": "",
        "last_error_type": "",
        "last_error": "",
        "last_signature": "",
        "last_conversation_url": "",
        "last_mode_text": "",
        "last_run_id": "",
        "last_fingerprint": "",
    }


def _ui_canary_fingerprint(*, provider: str, summary: dict[str, Any]) -> str:
    """Compute a fingerprint of the UI state for change detection."""
    parts = [
        str(provider),
        str(summary.get("status") or ""),
        str(summary.get("mode_text") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _load_ui_canary_state(obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    raw = obj.get("ui_canary")
    if not isinstance(raw, dict):
        return out
    for provider in _UI_CANARY_PROVIDERS:
        row = raw.get(provider)
        if not isinstance(row, dict):
            continue
        cur = _ui_canary_default_state()
        cur["last_run_ts"] = float(row.get("last_run_ts") or 0.0)
        cur["last_ok_ts"] = float(row.get("last_ok_ts") or 0.0)
        cur["last_failure_ts"] = float(row.get("last_failure_ts") or 0.0)
        cur["consecutive_failures"] = int(row.get("consecutive_failures") or 0)
        cur["last_capture_ts"] = float(row.get("last_capture_ts") or 0.0)
        cur["last_incident_ts"] = float(row.get("last_incident_ts") or 0.0)
        cur["last_status"] = str(row.get("last_status") or "")
        cur["last_error_type"] = str(row.get("last_error_type") or "")
        cur["last_error"] = str(row.get("last_error") or "")
        cur["last_signature"] = str(row.get("last_signature") or "")
        cur["last_conversation_url"] = str(row.get("last_conversation_url") or "")
        cur["last_mode_text"] = str(row.get("last_mode_text") or "")
        cur["last_run_id"] = str(row.get("last_run_id") or "")
        cur["last_fingerprint"] = str(row.get("last_fingerprint") or "")
        out[provider] = cur
    return out


def _dump_ui_canary_state(state: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for provider in _UI_CANARY_PROVIDERS:
        row = state.get(provider)
        if not isinstance(row, dict):
            continue
        out[provider] = {
            "last_run_ts": float(row.get("last_run_ts") or 0.0),
            "last_ok_ts": float(row.get("last_ok_ts") or 0.0),
            "last_failure_ts": float(row.get("last_failure_ts") or 0.0),
            "consecutive_failures": int(row.get("consecutive_failures") or 0),
            "last_capture_ts": float(row.get("last_capture_ts") or 0.0),
            "last_incident_ts": float(row.get("last_incident_ts") or 0.0),
            "last_status": str(row.get("last_status") or ""),
            "last_error_type": str(row.get("last_error_type") or ""),
            "last_error": str(row.get("last_error") or ""),
            "last_signature": str(row.get("last_signature") or ""),
            "last_conversation_url": str(row.get("last_conversation_url") or ""),
            "last_mode_text": str(row.get("last_mode_text") or ""),
            "last_run_id": str(row.get("last_run_id") or ""),
            "last_fingerprint": str(row.get("last_fingerprint") or ""),
        }
    return out


def _ui_canary_probe_summary(*, provider: str, wrapped: dict[str, Any]) -> dict[str, Any]:
    payload = wrapped.get("result") if isinstance(wrapped, dict) else None
    payload = payload if isinstance(payload, dict) else {}
    wrapped_ok = bool(isinstance(wrapped, dict) and wrapped.get("ok"))
    probe_ok = bool(payload.get("ok")) if isinstance(payload, dict) else False
    success = bool(wrapped_ok and probe_ok)
    error_type = str(payload.get("error_type") or "").strip()
    error_text = str(payload.get("error") or "").strip()
    if not wrapped_ok:
        error_type = str((wrapped or {}).get("error_type") or error_type or "ToolCallError").strip()
        error_text = str((wrapped or {}).get("error") or error_text).strip()
    return {
        "provider": str(provider),
        "success": bool(success),
        "status": str(payload.get("status") or ("completed" if success else "error")),
        "error_type": error_type,
        "error": normalize_error(error_text),
        "mode_text": str(payload.get("mode_text") or payload.get("model_text") or "").strip(),
        "conversation_url": str(payload.get("conversation_url") or "").strip(),
        "run_id": str(payload.get("run_id") or "").strip(),
        "wrapped_ok": bool(wrapped_ok),
        "payload_ok": bool(probe_ok),
        "raw": wrapped,
    }


def _ui_canary_signature(*, provider: str, summary: dict[str, Any]) -> str:
    return (
        "ui_canary:"
        f"{str(provider)}:"
        f"{str(summary.get('status') or '')}:"
        f"{str(summary.get('error_type') or '')}:"
        f"{normalize_error(str(summary.get('error') or ''))}"
    )


def _default_chatgpt_cdp_url() -> str:
    raw_port = (os.environ.get("CHROME_DEBUG_PORT") or "9222").strip() or "9222"
    try:
        port = int(raw_port)
    except Exception:
        port = 9222
    return f"http://127.0.0.1:{port}"


def _replace_url_port(url: str, *, port: int) -> str:
    raw = str(url or "").strip()
    if not raw:
        return f"http://127.0.0.1:{int(port)}"
    if "://" not in raw:
        raw = f"http://{raw}"
    try:
        parsed = urllib.parse.urlparse(raw)
        host = str(parsed.hostname or "127.0.0.1").strip() or "127.0.0.1"
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        rebuilt = parsed._replace(netloc=f"{host}:{int(port)}")
        return urllib.parse.urlunparse(rebuilt)
    except Exception:
        return f"http://127.0.0.1:{int(port)}"


def _resolve_loopback_cdp_url(url: str) -> str:
    """
    Resolve local CDP config drift:
    when configured localhost CDP port is down, prefer an actually-open local fallback
    (CHROME_DEBUG_PORT, then 9222/9226).
    """
    candidate = str(url or "").strip()
    if not candidate:
        return candidate
    host_port = _parse_host_port_from_url(candidate, default_port=9222)
    if host_port is None:
        return candidate
    host, port = host_port
    if not _is_local_host(host):
        return candidate
    probe_host = "127.0.0.1" if str(host).strip() == "0.0.0.0" else str(host).strip()
    if port_open(probe_host, int(port), timeout_seconds=0.2):
        return candidate

    fallback_ports: list[int] = []
    raw_debug_port = str(os.environ.get("CHROME_DEBUG_PORT") or "").strip()
    if raw_debug_port.isdigit():
        fallback_ports.append(int(raw_debug_port))
    for p in (9222, 9226):
        if p not in fallback_ports:
            fallback_ports.append(p)

    for alt_port in fallback_ports:
        if int(alt_port) == int(port):
            continue
        if port_open(probe_host, int(alt_port), timeout_seconds=0.2):
            return _replace_url_port(candidate, port=int(alt_port))
    return candidate


def _provider_cdp_url(*, provider: str, args: argparse.Namespace) -> str:
    p = str(provider or "").strip().lower()
    default_chatgpt_cdp = _default_chatgpt_cdp_url()
    args_cdp = str(getattr(args, "cdp_url", "") or "").strip()
    if p == "qwen":
        return (os.environ.get("QWEN_CDP_URL") or "http://127.0.0.1:9335").strip() or "http://127.0.0.1:9335"
    if p == "gemini":
        candidate = (
            os.environ.get("GEMINI_CDP_URL")
            or args_cdp
            or os.environ.get("CHATGPT_CDP_URL")
            or default_chatgpt_cdp
        ).strip() or default_chatgpt_cdp
        return _resolve_loopback_cdp_url(candidate)
    candidate = args_cdp or default_chatgpt_cdp
    return _resolve_loopback_cdp_url(candidate)


def _provider_chrome_start_script(*, provider: str, driver_root: Path) -> Path:
    p = str(provider or "").strip().lower()
    if p == "qwen":
        raw = (os.environ.get("QWEN_CHROME_START_SCRIPT") or "").strip()
        if raw:
            return Path(raw).expanduser()
        return (driver_root / "ops" / "qwen_chrome_start.sh").resolve()
    raw = (os.environ.get("CHROME_START_SCRIPT") or os.environ.get("CHATGPT_CHROME_START_SCRIPT") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return (driver_root / "ops" / "chrome_start.sh").resolve()



def _filter_mihomo_candidates(names: list[str], *, selected: str) -> list[str]:
    out: list[str] = []
    for n in names:
        name = str(n or "").strip()
        if not name or name == selected:
            continue
        if name == "REJECT":
            continue
        if _MIHOMO_CANDIDATE_SKIP_RE.search(name):
            continue
        out.append(name)
    return out


def _connect(db_path: Path) -> sqlite3.Connection:
    ensure_db_initialized(db_path)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Autocommit by default; explicit BEGIN/COMMIT still work for atomic sequences.
    conn.isolation_level = None
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


# ── Phase 0: Subsystem isolation & self-monitoring ────────────────
import contextlib
import resource


@contextlib.contextmanager
def _subsystem_guard(name: str, *, log_path: Path):
    """Wrap a subsystem tick so exceptions are logged but never propagate.

    Usage inside the main loop::

        with _subsystem_guard("auto_resolve", log_path=log_path):
            ... subsystem code ...
    """
    try:
        yield
    except Exception as exc:
        try:
            _append_jsonl(
                log_path,
                {
                    "ts": now_iso(),
                    "type": "subsystem_error",
                    "subsystem": name,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:800],
                },
            )
        except Exception:
            pass  # last-resort: never let logging itself crash the loop


def _rss_mb() -> float:
    """Return current RSS in megabytes (Linux only, fail-safe 0.0)."""
    try:
        # resource.getrusage returns maxrss in KB on Linux
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return 0.0


_WATCHDOG_HEARTBEAT_INTERVAL_SECONDS = 5.0
_watchdog_thread_lock = threading.Lock()
_watchdog_thread: threading.Thread | None = None
_watchdog_thread_active = False


def _systemd_notify(*lines: str) -> bool:
    """Send a best-effort notification to systemd without requiring sdnotify."""
    notify_socket = str(os.environ.get("NOTIFY_SOCKET") or "").strip()
    if not notify_socket:
        return False
    payload = "\n".join(str(line).strip() for line in lines if str(line).strip())
    if not payload:
        return False
    addr: str | bytes = notify_socket
    if notify_socket.startswith("@"):
        addr = b"\0" + notify_socket[1:].encode("utf-8", errors="ignore")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(addr)
            sock.sendall(payload.encode("utf-8"))
        return True
    except Exception:
        return False


def _watchdog_heartbeat_loop(interval_seconds: float) -> None:
    while True:
        with _watchdog_thread_lock:
            active = bool(_watchdog_thread_active)
        if not active:
            return
        _systemd_notify("WATCHDOG=1")
        time.sleep(max(1.0, float(interval_seconds)))


def _start_watchdog_heartbeat(*, status: str = "") -> None:
    global _watchdog_thread, _watchdog_thread_active
    with _watchdog_thread_lock:
        _watchdog_thread_active = True
        _systemd_notify("READY=1", *( [f"STATUS={status}"] if status else [] ))
        if _watchdog_thread is not None and _watchdog_thread.is_alive():
            return
        _watchdog_thread = threading.Thread(
            target=_watchdog_heartbeat_loop,
            args=(_WATCHDOG_HEARTBEAT_INTERVAL_SECONDS,),
            name="maint-daemon-watchdog",
            daemon=True,
        )
        _watchdog_thread.start()


def _stop_watchdog_heartbeat() -> None:
    global _watchdog_thread_active
    with _watchdog_thread_lock:
        _watchdog_thread_active = False
        thread = _watchdog_thread
    if thread is not None and thread.is_alive() and thread is not threading.current_thread():
        thread.join(timeout=1.0)


def _kick_watchdog(*, status: str = "") -> None:
    """Notify systemd WatchdogSec that the daemon is alive (fail-safe)."""
    _systemd_notify("WATCHDOG=1", *( [f"STATUS={status}"] if status else [] ))


def _fetch_events(conn: sqlite3.Connection, after_id: int) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT id, job_id, ts, type, payload_json FROM job_events WHERE id > ? ORDER BY id ASC", (after_id,)).fetchall())


def _jobs_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status ORDER BY n DESC").fetchall()
    return {str(r["status"]): int(r["n"]) for r in rows}


def _safe_copy(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def _file_sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _safe_copy_if_changed(src: Path, dst: Path) -> bool:
    """Copy only when content changed. Returns True when dst was updated."""
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        try:
            if int(src.stat().st_size) == int(dst.stat().st_size):
                src_hash = _file_sha256(src)
                dst_hash = _file_sha256(dst)
                if src_hash and dst_hash and src_hash == dst_hash:
                    return False
        except Exception:
            pass
    dst.write_bytes(src.read_bytes())
    return True
    repair_job_id: str | None = None
    codex_input_hash: str | None = None
    codex_last_run_ts: float | None = None
    codex_run_count: int = 0
    codex_last_ok: bool | None = None
    codex_last_error: str | None = None
    codex_autofix_last_ts: float | None = None
    codex_autofix_run_count: int = 0


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _copy_incident_job_artifacts(
    *,
    artifacts_dir: Path,
    job_id: str,
    job_pack_dir: Path,
) -> dict[str, Any]:
    job_art_dir = artifacts_dir / "jobs" / job_id
    for name in [
        "request.json",
        "events.jsonl",
        "result.json",
        "run_meta.json",
        "mihomo_delay_snapshot.json",
        "answer.md",
        "answer.txt",
        "answer_raw.md",
        "answer_raw.txt",
        "conversation.json",
    ]:
        _safe_copy(job_art_dir / name, job_pack_dir / name)

    result_payload = _load_json_object(job_art_dir / "result.json")
    authoritative_src = resolve_authoritative_answer_artifact(result_payload, artifacts_dir=artifacts_dir)
    if authoritative_src is not None and authoritative_src.exists():
        try:
            relative_target = authoritative_src.relative_to(job_art_dir)
        except Exception:
            relative_target = Path(authoritative_src.name)
        _safe_copy(authoritative_src, job_pack_dir / relative_target)
    return result_payload


def _incident_job_row_payload(row: sqlite3.Row, *, result_payload: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "job_id": row["job_id"],
        "kind": row["kind"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_error_type": row["last_error_type"],
        "last_error": row["last_error"],
        "conversation_url": row["conversation_url"],
        "answer_path": row["answer_path"],
        "conversation_export_path": row["conversation_export_path"],
    }
    if result_payload:
        payload["completion_contract"] = completion_contract_from_job_like(result_payload)
        payload["canonical_answer"] = canonical_answer_from_job_like(result_payload)
    return payload


def _load_incident_state(obj: dict[str, Any]) -> dict[str, IncidentState]:
    out: dict[str, IncidentState] = {}
    raw = obj.get("incidents")
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        if not isinstance(v, dict):
            continue
        try:
            codex_last_run_ts = float(v.get("codex_last_run_ts") or 0.0)
            codex_last_run_ts = codex_last_run_ts if codex_last_run_ts > 0 else None
            codex_autofix_last_ts = float(v.get("codex_autofix_last_ts") or 0.0)
            codex_autofix_last_ts = codex_autofix_last_ts if codex_autofix_last_ts > 0 else None

            codex_last_ok_raw = v.get("codex_last_ok")
            codex_last_ok: bool | None
            if isinstance(codex_last_ok_raw, bool):
                codex_last_ok = codex_last_ok_raw
            elif codex_last_ok_raw is None:
                codex_last_ok = None
            else:
                codex_last_ok = bool(codex_last_ok_raw)

            out[str(k)] = IncidentState(
                incident_id=str(v.get("incident_id") or ""),
                signature=str(v.get("signature") or ""),
                sig_hash=str(v.get("sig_hash") or ""),
                created_ts=float(v.get("created_ts") or 0.0),
                last_seen_ts=float(v.get("last_seen_ts") or 0.0),
                count=int(v.get("count") or 0),
                job_ids=[str(x) for x in (v.get("job_ids") or []) if str(x)],
                repair_job_id=(str(v.get("repair_job_id") or "").strip() or None),
                codex_input_hash=(str(v.get("codex_input_hash") or "").strip() or None),
                codex_last_run_ts=codex_last_run_ts,
                codex_run_count=int(v.get("codex_run_count") or 0),
                codex_last_ok=codex_last_ok,
                codex_last_error=(str(v.get("codex_last_error") or "").strip() or None),
                codex_autofix_last_ts=codex_autofix_last_ts,
                codex_autofix_run_count=int(v.get("codex_autofix_run_count") or 0),
            )
        except Exception:
            continue
    return out


def _dump_incident_state(incidents: dict[str, IncidentState]) -> dict[str, Any]:
    return {
        k: {
            "incident_id": v.incident_id,
            "signature": v.signature,
            "sig_hash": v.sig_hash,
            "created_ts": v.created_ts,
            "last_seen_ts": v.last_seen_ts,
            "count": v.count,
            "job_ids": list(v.job_ids),
            "repair_job_id": (v.repair_job_id or None),
            "codex_input_hash": (v.codex_input_hash or None),
            "codex_last_run_ts": (float(v.codex_last_run_ts) if v.codex_last_run_ts else None),
            "codex_run_count": int(v.codex_run_count),
            "codex_last_ok": (v.codex_last_ok if v.codex_last_ok is not None else None),
            "codex_last_error": (v.codex_last_error or None),
            "codex_autofix_last_ts": (float(v.codex_autofix_last_ts) if v.codex_autofix_last_ts else None),
            "codex_autofix_run_count": int(v.codex_autofix_run_count),
        }
        for k, v in incidents.items()
    }


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        obj = json.loads(raw)
    except Exception:
        return []
    if not isinstance(obj, list):
        return []
    out: list[str] = []
    for x in obj:
        s = str(x or "").strip()
        if s:
            out.append(s)
    return out


def _dump_json_list(values: list[str]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        s = str(v or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def _load_incident_state_from_db(conn: sqlite3.Connection) -> dict[str, IncidentState]:
    try:
        rows = conn.execute(
            """
            SELECT incident_id, fingerprint_hash, signature, created_at, last_seen_at, count, job_ids_json,
                   repair_job_id, codex_input_hash, codex_last_run_ts, codex_run_count, codex_last_ok, codex_last_error,
                   codex_autofix_last_ts, codex_autofix_run_count, status
            FROM incidents
            WHERE status != ?
            ORDER BY last_seen_at DESC
            LIMIT 2000
            """,
            ("resolved",),
        ).fetchall()
    except Exception:
        return {}

    out: dict[str, IncidentState] = {}
    for r in rows:
        try:
            sig_hash = str(r["fingerprint_hash"] or "")
            if not sig_hash:
                continue
            if sig_hash in out:
                continue
            codex_last_ok_raw = r["codex_last_ok"]
            codex_last_ok: bool | None
            if codex_last_ok_raw is None:
                codex_last_ok = None
            elif isinstance(codex_last_ok_raw, bool):
                codex_last_ok = codex_last_ok_raw
            else:
                try:
                    codex_last_ok = bool(int(codex_last_ok_raw))
                except Exception:
                    codex_last_ok = bool(codex_last_ok_raw)

            out[sig_hash] = IncidentState(
                incident_id=str(r["incident_id"] or ""),
                signature=str(r["signature"] or ""),
                sig_hash=sig_hash,
                created_ts=float(r["created_at"] or 0.0),
                last_seen_ts=float(r["last_seen_at"] or 0.0),
                count=int(r["count"] or 0),
                job_ids=_parse_json_list(str(r["job_ids_json"]) if r["job_ids_json"] is not None else None),
                repair_job_id=(str(r["repair_job_id"]).strip() if r["repair_job_id"] is not None else None) or None,
                codex_input_hash=(str(r["codex_input_hash"]).strip() if r["codex_input_hash"] is not None else None) or None,
                codex_last_run_ts=(float(r["codex_last_run_ts"]) if r["codex_last_run_ts"] is not None else None),
                codex_run_count=int(r["codex_run_count"] or 0),
                codex_last_ok=codex_last_ok,
                codex_last_error=(str(r["codex_last_error"]).strip() if r["codex_last_error"] is not None else None) or None,
                codex_autofix_last_ts=(float(r["codex_autofix_last_ts"]) if r["codex_autofix_last_ts"] is not None else None),
                codex_autofix_run_count=int(r["codex_autofix_run_count"] or 0),
            )
        except Exception:
            continue
    return out


def _upsert_incident_db(
    conn: sqlite3.Connection,
    *,
    incident: IncidentState,
    category: str | None,
    severity: str | None,
    status: str | None,
    evidence_dir: Path | None,
) -> None:
    now = time.time()
    codex_last_ok_int: int | None
    if incident.codex_last_ok is None:
        codex_last_ok_int = None
    else:
        codex_last_ok_int = 1 if bool(incident.codex_last_ok) else 0
    conn.execute(
        """
        INSERT INTO incidents(
          incident_id, fingerprint_hash, signature, category, severity, status,
          created_at, updated_at, last_seen_at, count, job_ids_json, evidence_dir,
          repair_job_id, codex_input_hash, codex_last_run_ts, codex_run_count, codex_last_ok, codex_last_error,
          codex_autofix_last_ts, codex_autofix_run_count
        )
        VALUES (?1,?2,?3,?4,COALESCE(?5,'P2'),COALESCE(?6,'open'),?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20)
        ON CONFLICT(incident_id) DO UPDATE SET
          fingerprint_hash=excluded.fingerprint_hash,
          signature=excluded.signature,
          category=COALESCE(?4, incidents.category),
          severity=COALESCE(?5, incidents.severity),
          status=COALESCE(?6, incidents.status),
          updated_at=excluded.updated_at,
          last_seen_at=excluded.last_seen_at,
          count=excluded.count,
          job_ids_json=excluded.job_ids_json,
          evidence_dir=COALESCE(excluded.evidence_dir, incidents.evidence_dir),
          repair_job_id=COALESCE(excluded.repair_job_id, incidents.repair_job_id),
          codex_input_hash=COALESCE(excluded.codex_input_hash, incidents.codex_input_hash),
          codex_last_run_ts=COALESCE(excluded.codex_last_run_ts, incidents.codex_last_run_ts),
          codex_run_count=excluded.codex_run_count,
          codex_last_ok=excluded.codex_last_ok,
          codex_last_error=COALESCE(excluded.codex_last_error, incidents.codex_last_error),
          codex_autofix_last_ts=COALESCE(excluded.codex_autofix_last_ts, incidents.codex_autofix_last_ts),
          codex_autofix_run_count=excluded.codex_autofix_run_count
        """,
        (
            str(incident.incident_id),
            str(incident.sig_hash),
            str(incident.signature),
            (str(category).strip() if category else None),
            (str(severity).strip() if severity else None),
            (str(status).strip() if status else None),
            float(incident.created_ts or now),
            float(now),
            float(incident.last_seen_ts or now),
            int(incident.count),
            _dump_json_list(list(incident.job_ids)),
            (str(evidence_dir) if evidence_dir is not None else None),
            (str(incident.repair_job_id).strip() if incident.repair_job_id else None),
            (str(incident.codex_input_hash).strip() if incident.codex_input_hash else None),
            (float(incident.codex_last_run_ts) if incident.codex_last_run_ts else None),
            int(incident.codex_run_count),
            codex_last_ok_int,
            (str(incident.codex_last_error).strip() if incident.codex_last_error else None),
            (float(incident.codex_autofix_last_ts) if incident.codex_autofix_last_ts else None),
            int(incident.codex_autofix_run_count),
        ),
    )


def _incident_dir(base: Path, incident_id: str) -> Path:
    return base / "incidents" / incident_id


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _resolve_incident_rollover(
    conn: sqlite3.Connection,
    *,
    monitor_dir: Path,
    incident: IncidentState,
    now: float,
    replaced_by_incident_id: str,
    log_path: Path,
) -> None:
    """Best-effort: mark a prior incident as resolved when creating a new incident for the same fingerprint.

    This keeps the incidents table actionable (at most one open incident per fingerprint_hash).
    """
    prior_id = str(incident.incident_id or '').strip()
    if not prior_id:
        return
    try:
        conn.execute(
            'UPDATE incidents SET status = ?, updated_at = ? WHERE incident_id = ?',
            (incident_db.INCIDENT_STATUS_RESOLVED, float(now), prior_id),
        )
    except Exception as exc:
        _append_jsonl(
            log_path,
            {
                'ts': now_iso(),
                'type': 'incident_rollover_resolve_error',
                'incident_id': prior_id,
                'sig_hash': str(incident.sig_hash or ''),
                'replaced_by_incident_id': str(replaced_by_incident_id),
                'error_type': type(exc).__name__,
                'error': str(exc)[:800],
            },
        )
        return

    # Update the prior incident manifest on disk (best-effort; audit trail).
    try:
        inc_dir = _incident_dir(monitor_dir, prior_id)
        manifest_path = inc_dir / 'manifest.json'
        manifest_obj = read_json(manifest_path)
        manifest = manifest_obj if isinstance(manifest_obj, dict) else {}
        manifest['resolved'] = {
            'ts': now_iso(),
            'reason': 'rollover',
            'replaced_by_incident_id': str(replaced_by_incident_id),
        }
        _write_manifest(manifest_path, manifest)
    except Exception:
        pass

    _append_jsonl(
        log_path,
        {
            'ts': now_iso(),
            'type': 'incident_rollover_resolved',
            'incident_id': prior_id,
            'sig_hash': str(incident.sig_hash or ''),
            'replaced_by_incident_id': str(replaced_by_incident_id),
        },
    )

def _record_action(inc_dir: Path, *, action: str, ok: bool, error: str | None = None, elapsed_ms: int | None = None, details: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {
        "ts": now_iso(),
        "action": str(action),
        "ok": bool(ok),
        "error": (str(error) if error else None),
        "elapsed_ms": (int(elapsed_ms) if elapsed_ms is not None else None),
        "details": (details or None),
    }
    _append_jsonl(inc_dir / "actions.jsonl", payload)


def _maint_requested_by() -> dict[str, Any]:
    """Return the ``requested_by`` transport identity for the maint daemon."""
    return _requested_by_transport("maint_daemon")


def _ensure_repair_check_job(
    *,
    conn: sqlite3.Connection,
    artifacts_dir: Path,
    incident: IncidentState,
    target_job_id: str,
    signature: str,
    conversation_url: str | None,
    timeout_seconds: int,
    mode: str,
    probe_driver: bool,
    recent_failures: int,
) -> str:
    if _source_job_uses_synthetic_or_trivial_prompt(conn, str(target_job_id)):
        return ""
    idem_key = f"maint_daemon:repair_check:{incident.incident_id}"
    job = _create_repair_check_job(
        conn=conn,
        artifacts_dir=artifacts_dir,
        idempotency_key=idem_key,
        client_name="maint_daemon",
        job_id=str(target_job_id),
        symptom=str(signature),
        conversation_url=(str(conversation_url).strip() if conversation_url else None),
        timeout_seconds=int(timeout_seconds),
        mode=str(mode),
        probe_driver=bool(probe_driver),
        recent_failures=int(recent_failures),
        max_attempts=1,
        requested_by=_maint_requested_by(),
    )
    return str(job.job_id)


def _ensure_repair_autofix_job(
    *,
    conn: sqlite3.Connection,
    artifacts_dir: Path,
    incident: IncidentState,
    target_job_id: str,
    signature: str,
    conversation_url: str | None,
    timeout_seconds: int,
    allow_actions: str,
    max_risk: str,
) -> str:
    if _source_job_uses_synthetic_or_trivial_prompt(conn, str(target_job_id)):
        return ""
    idem_key = f"maint_daemon:repair_autofix:{incident.incident_id}"
    job = _create_repair_autofix_job(
        conn=conn,
        artifacts_dir=artifacts_dir,
        idempotency_key=idem_key,
        client_name="maint_daemon",
        job_id=str(target_job_id),
        symptom=str(signature),
        conversation_url=(str(conversation_url).strip() if conversation_url else None),
        timeout_seconds=int(timeout_seconds),
        allow_actions=str(allow_actions or "").strip(),
        max_risk=str(max_risk or "").strip() or "medium",
        apply_actions=True,
        max_attempts=1,
        requested_by=_maint_requested_by(),
    )
    return str(job.job_id)


def _attach_repair_artifacts(
    *,
    artifacts_dir: Path,
    inc_dir: Path,
    repair_job_id: str,
    log_path: Path,
    incident_id: str,
) -> bool:
    report_src = artifacts_dir / "jobs" / repair_job_id / "repair_report.json"
    answer_src = artifacts_dir / "jobs" / repair_job_id / "answer.md"
    result_src = artifacts_dir / "jobs" / repair_job_id / "result.json"
    out_dir = inc_dir / "snapshots" / "repair_check"
    copied_any = False
    for src, name in [
        (report_src, "repair_report.json"),
        (answer_src, "answer.md"),
        (result_src, "result.json"),
    ]:
        if src.exists():
            copied_any = _safe_copy_if_changed(src, out_dir / name) or copied_any
    if copied_any:
        _append_jsonl(
            log_path,
            {
                "ts": now_iso(),
                "type": "auto_repair_attached",
                "incident_id": str(incident_id),
                "repair_job_id": str(repair_job_id),
                "dst_dir": str(out_dir),
            },
        )
    return copied_any


def _attach_repair_autofix_artifacts(
    *,
    artifacts_dir: Path,
    inc_dir: Path,
    repair_job_id: str,
    log_path: Path,
    incident_id: str,
) -> bool:
    report_src = artifacts_dir / "jobs" / repair_job_id / "repair_autofix_report.json"
    answer_src = artifacts_dir / "jobs" / repair_job_id / "answer.md"
    result_src = artifacts_dir / "jobs" / repair_job_id / "result.json"
    out_dir = inc_dir / "snapshots" / "repair_autofix"
    copied_any = False
    for src, name in [
        (report_src, "repair_autofix_report.json"),
        (answer_src, "answer.md"),
        (result_src, "result.json"),
    ]:
        if src.exists():
            copied_any = _safe_copy_if_changed(src, out_dir / name) or copied_any
    if copied_any:
        _append_jsonl(
            log_path,
            {
                "ts": now_iso(),
                "type": "codex_maint_fallback_attached",
                "incident_id": str(incident_id),
                "repair_job_id": str(repair_job_id),
                "dst_dir": str(out_dir),
            },
        )
    return copied_any




def _chatgptmcp_call(client: ToolCaller, *, tool_name: str, tool_args: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    try:
        res = client.call_tool(tool_name=tool_name, tool_args=tool_args, timeout_sec=float(timeout_seconds))
        return {"ok": True, "tool": tool_name, "result": res}
    except ToolCallError as exc:
        return {"ok": False, "tool": tool_name, "error_type": "ToolCallError", "error": str(exc)[:800]}
    except Exception as exc:
        return {"ok": False, "tool": tool_name, "error_type": type(exc).__name__, "error": str(exc)[:800]}


def read_text(path: Path, *, limit: int = 120_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[: int(limit)]
    except Exception:
        return ""


def _codex_input_fingerprint(inc_dir: Path) -> str:
    parts: list[str] = []
    manifest_obj = read_json(inc_dir / "manifest.json") or {}
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
        parts.append(read_text(inc_dir / "manifest.json", limit=80_000))
    parts.append(read_text(inc_dir / "summary.md", limit=80_000))
    parts.append(read_text(inc_dir / "snapshots" / "repair_check" / "repair_report.json", limit=80_000))
    parts.append(read_text(inc_dir / "snapshots" / "issues_registry.yaml", limit=80_000))
    try:
        job_rows = sorted((inc_dir / "jobs").glob("*/job_row.json"))
    except Exception:
        job_rows = []
    for p in job_rows[-5:]:
        obj = read_json(p)
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
            parts.append(read_text(p, limit=12_000))
    return sig_hash("\n\n".join(parts))



def _write_text(path: Path, text: str, *, limit: int = 50_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = truncate_text(text, limit=int(limit))
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


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
    lines.append(f"Updated: {now_iso()}")
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
        summary = truncate_text(summary, limit=240)

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
                "reason": (truncate_text(str(a.get("reason") or "").strip().replace("\n", " "), limit=400) or None),
            }
        )

    trimmed_risks: list[str] = []
    if isinstance(risks, list):
        for r in risks[:8]:
            rs = str(r or "").strip().replace("\n", " ")
            if rs:
                trimmed_risks.append(truncate_text(rs, limit=300))

    trimmed_next: list[str] = []
    if isinstance(next_steps, list):
        for n in next_steps[:8]:
            ns = str(n or "").strip().replace("\n", " ")
            if ns:
                trimmed_next.append(truncate_text(ns, limit=300))

    return {
        "ts": now_iso(),
        "type": "codex_global_memory",
        "trigger": (str(trigger).strip() or None),
        "incident_id": str(incident_id),
        "sig_hash": str(sig_hash),
        "provider": (str(provider).strip() if provider else None),
        "signature": truncate_text(str(signature or "").strip().replace("\n", " "), limit=500),
        "summary": truncate_text(summary, limit=1200),
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

    actions_payload = read_json(actions_path)
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
        atomic_write_json(record_path, record)
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
                    "ts": now_iso(),
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
                "ts": now_iso(),
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


def _render_codex_sre_actions_markdown(payload: dict[str, Any]) -> str:
    summary = str(payload.get("summary") or "").strip()
    hypotheses = payload.get("hypotheses") if isinstance(payload.get("hypotheses"), list) else []
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    risks = payload.get("risks") if isinstance(payload.get("risks"), list) else []
    next_steps = payload.get("next_steps") if isinstance(payload.get("next_steps"), list) else []

    lines: list[str] = []
    lines.append("# Codex SRE report")
    lines.append("")
    if summary:
        lines.append("## Summary")
        lines.append(summary)
        lines.append("")

    if hypotheses:
        lines.append("## Hypotheses")
        for h in hypotheses[:10]:
            if not isinstance(h, dict):
                continue
            title = str(h.get("title") or "").strip() or "(untitled)"
            confidence = str(h.get("confidence") or "").strip() or "unknown"
            lines.append(f"- {title} (confidence: `{confidence}`)")
            evidence = h.get("evidence")
            if isinstance(evidence, list):
                for e in evidence[:8]:
                    ev = str(e or "").strip()
                    if ev:
                        lines.append(f"  - {ev}")
        lines.append("")

    if actions:
        lines.append("## Suggested actions (plan)")
        for a in actions[:12]:
            if not isinstance(a, dict):
                continue
            name = str(a.get("name") or "").strip() or "(unknown)"
            risk = str(a.get("risk") or "").strip() or "unknown"
            reason = str(a.get("reason") or "").strip()
            lines.append(f"- `{name}` risk=`{risk}`")
            if reason:
                lines.append(f"  - reason: {reason}")
            guardrails = a.get("guardrails")
            if isinstance(guardrails, list) and guardrails:
                lines.append("  - guardrails:")
                for g in guardrails[:8]:
                    gs = str(g or "").strip()
                    if gs:
                        lines.append(f"    - {gs}")
            signals = a.get("success_signal")
            if isinstance(signals, list) and signals:
                lines.append("  - success_signal:")
                for s0 in signals[:8]:
                    ss = str(s0 or "").strip()
                    if ss:
                        lines.append(f"    - {ss}")
        lines.append("")

    if risks:
        lines.append("## Risks")
        for r in risks[:12]:
            rs = str(r or "").strip()
            if rs:
                lines.append(f"- {rs}")
        lines.append("")

    if next_steps:
        lines.append("## Next steps")
        for n in next_steps[:12]:
            ns = str(n or "").strip()
            if ns:
                lines.append(f"- {ns}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


_RISK_RANK = {"low": 0, "medium": 1, "high": 2}


def _incident_target_job_id(inc_dir: Path, *, explicit_job_id: str | None = None) -> str | None:
    candidate = str(explicit_job_id or "").strip()
    if candidate:
        return candidate
    manifest_obj = read_json(inc_dir / "manifest.json") or {}
    if isinstance(manifest_obj, dict):
        job_ids = manifest_obj.get("job_ids")
        if isinstance(job_ids, list):
            for item in reversed(job_ids):
                raw = str(item or "").strip()
                if raw:
                    return raw
    jobs_dir = inc_dir / "jobs"
    try:
        for item in sorted(jobs_dir.iterdir(), reverse=True):
            if item.is_dir():
                raw = str(item.name or "").strip()
                if raw:
                    return raw
    except Exception:
        return None
    return None


def _incident_context_pack(inc_dir: Path) -> dict[str, Any]:
    manifest_obj = read_json(inc_dir / "manifest.json")
    summary_md = read_text(inc_dir / "summary.md", limit=20_000)
    repair_check_report = read_json(inc_dir / "snapshots" / "repair_check" / "repair_report.json")
    issues_registry_excerpt = read_text(inc_dir / "snapshots" / "issues_registry.yaml", limit=20_000)
    job_rows: list[dict[str, Any]] = []
    try:
        rows = sorted((inc_dir / "jobs").glob("*/job_row.json"))
    except Exception:
        rows = []
    for path in rows[-3:]:
        payload = read_json(path)
        if isinstance(payload, dict):
            job_rows.append(payload)
    pack: dict[str, Any] = {
        "incident_dir": str(inc_dir),
        "manifest": manifest_obj if isinstance(manifest_obj, dict) else None,
        "summary_md": (summary_md or None),
        "repair_check_report": repair_check_report if isinstance(repair_check_report, dict) else None,
        "issues_registry_excerpt": (issues_registry_excerpt or None),
        "job_rows": job_rows,
    }
    return {key: value for key, value in pack.items() if value not in (None, [], "")}


def _legacy_codex_actions_from_controller(
    *,
    decision: dict[str, Any],
    lane_id: str,
    decision_path: str,
    report_path: str,
    target_job_id: str | None,
) -> dict[str, Any]:
    summary = str(decision.get("summary") or "").strip() or "Controller completed without a summary."
    root_cause = str(decision.get("root_cause") or "").strip() or "Controller did not provide a root cause."
    rationale = str(decision.get("rationale") or "").strip() or summary
    confidence = str(decision.get("confidence") or "").strip().lower() or "medium"
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    route = str(decision.get("route") or "").strip() or "manual"
    runtime_fix = decision.get("runtime_fix") if isinstance(decision.get("runtime_fix"), dict) else {}
    actions: list[dict[str, Any]] = []
    if route == "repair.autofix":
        allow_actions_raw = runtime_fix.get("allow_actions")
        if isinstance(allow_actions_raw, list):
            allow_actions = [str(item or "").strip() for item in allow_actions_raw if str(item or "").strip()]
        else:
            allow_actions = []
        if not allow_actions:
            allow_actions = ["no_action"]
        risk = str(runtime_fix.get("max_risk") or "low").strip().lower() or "low"
        if risk not in {"low", "medium", "high"}:
            risk = "low"
        reason = str(runtime_fix.get("reason") or "").strip() or summary
        for name in allow_actions:
            action_name = name if name in {"no_action", "capture_ui", "enable_netlog", "disable_netlog", "refresh", "regenerate", "clear_blocked", "restart_chrome", "restart_driver", "pause_processing"} else "no_action"
            actions.append(
                {
                    "name": action_name,
                    "reason": reason,
                    "risk": risk,
                    "guardrails": [
                        "Incident-side codex artifacts are mirror-only; canonical state lives in the SRE lane.",
                        f"Review canonical decision at {decision_path}.",
                    ],
                    "success_signal": [
                        f"Target job {target_job_id or '(unknown)'} progresses after guarded action.",
                        f"Canonical lane report remains available at {report_path}.",
                    ],
                }
            )
    else:
        actions.append(
            {
                "name": "no_action",
                "reason": rationale,
                "risk": "low",
                "guardrails": [
                    "Do not mutate runtime state directly from the incident-side mirror.",
                    f"Follow canonical lane decision at {decision_path}.",
                ],
                "success_signal": [
                    "Operator can continue from the canonical lane artifacts.",
                ],
            }
        )
    risks = [note for note in decision.get("notes") if isinstance(note, str) and note.strip()] if isinstance(decision.get("notes"), list) else []
    next_steps = [f"Review canonical lane {lane_id}."]
    if route == "repair.open_pr":
        next_steps.append("Continue via repair.open_pr / code change workflow, not incident-side runtime autofix.")
    elif route == "repair.autofix":
        next_steps.append("If autofix is enabled, execute only the allowed low-risk actions from this mirrored payload.")
    else:
        next_steps.append("Operator review is required before further action.")
    return {
        "summary": summary,
        "hypotheses": [
            {
                "title": root_cause,
                "evidence": [
                    f"lane_id={lane_id}",
                    f"decision_path={decision_path}",
                    f"report_path={report_path}",
                ],
                "confidence": confidence,
            }
        ],
        "actions": actions,
        "risks": risks,
        "next_steps": next_steps,
    }




def _parse_host_port_from_url(url: str, *, default_port: int) -> tuple[str, int] | None:
    try:
        parsed = urllib.parse.urlparse(str(url))
    except Exception:
        return None
    host = str(parsed.hostname or "").strip() or "127.0.0.1"
    port = int(parsed.port or default_port)
    return host, port



def _chatgptrest_api_host_port(*, base_url: str | None = None) -> tuple[str, int]:
    return _shared_chatgptrest_api_host_port(base_url=base_url)


def _start_api_if_down(
    *,
    repo_root: Path,
    host: str,
    port: int,
    log_file: Path,
    wait_seconds: float = 6.0,
) -> tuple[bool, dict[str, Any]]:
    ok, details = _shared_start_local_api(
        repo_root=repo_root,
        host=str(host),
        port=int(port),
        action_log=log_file,
        out_log=(repo_root / "logs" / "chatgptrest_api.log").resolve(),
        wait_seconds=float(wait_seconds),
        timestamp_fn=_now_iso,
        action_label="starting api",
    )
    if "action_log" in details and "log_file" not in details:
        details = dict(details)
        details["log_file"] = str(details.get("action_log"))
    return bool(ok), details


def _run_codex_sre_analyze_incident(
    *,
    repo_root: Path,
    inc_dir: Path,
    db_path: Path,
    artifacts_dir: Path,
    model: str,
    timeout_seconds: int,
    global_memory_md: Path | None = None,
    global_memory_jsonl: Path | None = None,
    target_job_id: str | None = None,
) -> dict[str, Any]:
    codex_dir = inc_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    actions_json = codex_dir / "sre_actions.json"
    actions_md = codex_dir / "sre_actions.md"
    run_meta_path = codex_dir / "run_meta.json"
    runs_log_path = codex_dir / "runs.jsonl"
    stdout_path = codex_dir / "stdout.txt"
    stderr_path = codex_dir / "stderr.txt"

    input_hash = _codex_input_fingerprint(inc_dir)
    started_at = time.time()
    stdout = ""
    stderr = ""
    returncode: int | None = None
    ok = False
    error: str | None = None
    pointer_path = codex_dir / "source_lane.json"
    incident_id = str((read_json(inc_dir / "manifest.json") or {}).get("incident_id") or inc_dir.name).strip() or inc_dir.name
    resolved_target_job_id = _incident_target_job_id(inc_dir, explicit_job_id=target_job_id)
    context_pack = _incident_context_pack(inc_dir)
    manifest_obj = read_json(inc_dir / "manifest.json") or {}
    incident_sig_hash = str(manifest_obj.get("sig_hash") or "").strip() or None
    if global_memory_jsonl is not None:
        action_preferences = load_maintagent_action_preferences(
            jsonl_path=global_memory_jsonl,
            sig_hash=incident_sig_hash,
        )
        if action_preferences.get("preferred_actions"):
            context_pack["preferred_action_families"] = action_preferences
    if global_memory_md is not None and global_memory_md.exists():
        context_pack["global_memory_snapshot_path"] = str(global_memory_md)
        context_pack["global_memory_md"] = str(global_memory_md)
        context_pack["global_memory_excerpt"] = read_text(global_memory_md, limit=20_000)
    controller_request_id = f"incident_{incident_id}_{time.time_ns()}"
    cmd: list[str] = ["controller:sre.fix_request", f"incident_id={incident_id}"]
    try:
        controller = execute_sre_fix_request_controller(
            db_path=db_path,
            artifacts_dir=artifacts_dir,
            request_job_id=controller_request_id,
            kind="sre.fix_request",
            input_obj={
                "incident_id": incident_id,
                "job_id": resolved_target_job_id,
                "symptom": str(manifest_obj.get("signature") or read_text(inc_dir / "summary.md", limit=300) or "incident escalation").strip(),
                "context_pack": context_pack,
                "run_kind": "incident_maintenance",
                "escalation_source": "maint_daemon",
            },
            params_obj={
                "timeout_seconds": int(max(30, int(timeout_seconds))),
                "model": (str(model).strip() if str(model or "").strip() else None),
                "route_mode": "plan_only",
                "runtime_apply_actions": False,
                "resume_lane": True,
            },
            report_path=None,
        )
        report = dict(controller["report"])
        decision = dict(controller["decision"])
        lane_id = str(controller.get("lane_id") or report.get("lane_id") or "")
        legacy_actions = _legacy_codex_actions_from_controller(
            decision=decision,
            lane_id=lane_id,
            decision_path=str(report.get("decision_path") or ""),
            report_path=str(report.get("report_path") or ""),
            target_job_id=resolved_target_job_id,
        )
        atomic_write_json(actions_json, legacy_actions)
        actions_md.write_text(_render_codex_sre_actions_markdown(legacy_actions), encoding="utf-8")
        pointer_payload = {
            "artifact_mode": "mirror_pointer",
            "source_lane_id": lane_id,
            "controller_kind": "codex_maint",
            "controller_phase": ((report.get("controller") or {}).get("phase") if isinstance(report.get("controller"), dict) else None),
            "canonical_request_path": report.get("request_path"),
            "canonical_prompt_path": report.get("prompt_path"),
            "canonical_decision_path": report.get("decision_path"),
            "canonical_report_path": report.get("report_path"),
            "task_pack_projection_path": report.get("task_pack_projection_path"),
            "mirror_actions_json": str(actions_json),
            "mirror_actions_md": str(actions_md),
        }
        atomic_write_json(pointer_path, pointer_payload)
        stdout = (
            f"incident codex artifacts are mirror/pointer only\n"
            f"source_lane_id={lane_id}\n"
            f"canonical_report_path={report.get('report_path')}\n"
            f"canonical_decision_path={report.get('decision_path')}\n"
        )
        stderr = ""
        returncode = 0
        ok = True
        error = None
    except Exception as exc:
        ok = False
        returncode = 1
        error = f"{type(exc).__name__}: {exc}"
        stdout = ""
        stderr = error

    elapsed_ms = int(round((time.time() - started_at) * 1000))
    _write_text(stdout_path, stdout, limit=80_000)
    _write_text(stderr_path, stderr, limit=80_000)

    run_meta: dict[str, Any] = {
        "ts": now_iso(),
        "ok": bool(ok),
        "elapsed_ms": elapsed_ms,
        "input_hash": input_hash,
        "model": (str(model).strip() if str(model or "").strip() else None),
        "global_memory_md": (str(global_memory_md) if global_memory_md is not None else None),
        "cmd": cmd,
        "returncode": returncode,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "actions_json": str(actions_json),
        "actions_md": str(actions_md),
        "pointer_path": str(pointer_path),
        "artifact_mode": "mirror_pointer",
        "target_job_id": resolved_target_job_id,
        "error": error,
    }
    atomic_write_json(run_meta_path, run_meta)
    _append_jsonl(runs_log_path, run_meta)

    return run_meta


def _fallback_controller_decision(
    *,
    signature: str,
    allow_actions: str,
    max_risk: str,
    trigger: str,
) -> dict[str, Any]:
    normalized_allow_actions = [
        action
        for action in parse_allow_actions(str(allow_actions or "").strip())
        if action in {"no_action", "capture_ui", "enable_netlog", "disable_netlog", "refresh", "regenerate", "clear_blocked", "restart_chrome", "restart_driver", "pause_processing"}
    ]
    if not normalized_allow_actions:
        normalized_allow_actions = ["capture_ui", "restart_driver"]
    risk = str(max_risk or "").strip().lower() or "medium"
    if risk not in {"low", "medium", "high"}:
        risk = "medium"
    summary = "Codex incident analysis failed, so the controller is routing to guarded runtime autofix fallback."
    return {
        "summary": summary,
        "root_cause": f"Upstream incident Codex analysis did not converge (`{trigger}`) for signature `{signature}`.",
        "route": "repair.autofix",
        "confidence": "medium",
        "rationale": "The maintenance controller should preserve the canonical lane and fall back to guarded runtime recovery rather than creating an incident-side second control path.",
        "recommended_actions": [
            "Continue inside the canonical lane rather than submitting incident-side standalone repair jobs.",
            "Keep runtime recovery within the configured action allowlist and risk ceiling.",
        ],
        "runtime_fix": {
            "allow_actions": normalized_allow_actions,
            "max_risk": risk,
            "reason": summary,
        },
        "open_pr": {},
        "notes": ["maint_daemon_fallback", str(trigger or "").strip() or "codex_sre_failed"],
    }


def _route_repair_autofix_fallback_via_controller(
    *,
    inc_dir: Path,
    db_path: Path,
    artifacts_dir: Path,
    target_job_id: str,
    signature: str,
    timeout_seconds: int,
    allow_actions: str,
    max_risk: str,
    trigger: str,
    global_memory_md: Path | None = None,
    global_memory_jsonl: Path | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    codex_dir = inc_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    pointer_path = codex_dir / "source_lane.json"
    incident_id = str((read_json(inc_dir / "manifest.json") or {}).get("incident_id") or inc_dir.name).strip() or inc_dir.name
    check_conn = _connect(db_path)
    try:
        if _source_job_uses_synthetic_or_trivial_prompt(check_conn, str(target_job_id)):
            return {"ok": False, "skipped": True, "reason": "synthetic_source_blocked"}
    finally:
        check_conn.close()
    context_pack = _incident_context_pack(inc_dir)
    manifest_obj = read_json(inc_dir / "manifest.json") or {}
    incident_sig_hash = str(manifest_obj.get("sig_hash") or "").strip() or None
    if global_memory_jsonl is not None:
        action_preferences = load_maintagent_action_preferences(
            jsonl_path=global_memory_jsonl,
            sig_hash=incident_sig_hash,
        )
        if action_preferences.get("preferred_actions"):
            context_pack["preferred_action_families"] = action_preferences
    if global_memory_md is not None and global_memory_md.exists():
        context_pack["global_memory_snapshot_path"] = str(global_memory_md)
        context_pack["global_memory_md"] = str(global_memory_md)
        context_pack["global_memory_excerpt"] = read_text(global_memory_md, limit=20_000)

    controller = execute_sre_fix_request_controller(
        db_path=db_path,
        artifacts_dir=artifacts_dir,
        request_job_id=f"incident_fallback_{incident_id}_{time.time_ns()}",
        kind="sre.fix_request",
        input_obj={
            "incident_id": incident_id,
            "job_id": str(target_job_id),
            "symptom": str(signature or "").strip() or "incident fallback",
            "context_pack": context_pack,
            "run_kind": "incident_maintenance",
            "escalation_source": "maint_daemon",
        },
        params_obj={
            "timeout_seconds": int(max(30, int(timeout_seconds))),
            "model": (str(model or "").strip() or None),
            "route_mode": "auto_runtime",
            "runtime_apply_actions": True,
            "runtime_allow_actions": parse_allow_actions(str(allow_actions or "").strip()),
            "runtime_max_risk": str(max_risk or "").strip() or "medium",
            "resume_lane": True,
            "decision_override": _fallback_controller_decision(
                signature=signature,
                allow_actions=allow_actions,
                max_risk=max_risk,
                trigger=trigger,
            ),
        },
        report_path=None,
    )
    report = dict(controller["report"])
    lane_id = str(controller.get("lane_id") or report.get("lane_id") or "")
    pointer_payload = {
        "artifact_mode": "mirror_pointer",
        "source_lane_id": lane_id,
        "controller_kind": "codex_maint",
        "controller_phase": ((report.get("controller") or {}).get("phase") if isinstance(report.get("controller"), dict) else None),
        "canonical_request_path": report.get("request_path"),
        "canonical_prompt_path": report.get("prompt_path"),
        "canonical_decision_path": report.get("decision_path"),
        "canonical_report_path": report.get("report_path"),
        "task_pack_projection_path": report.get("task_pack_projection_path"),
        "source": "maint_daemon_fallback_controller",
    }
    atomic_write_json(pointer_path, pointer_payload)
    downstream = dict(controller.get("downstream") or {})
    downstream_job_id = str(downstream.get("job_id") or "").strip()
    if not downstream_job_id:
        return {
            "ok": False,
            "skipped": False,
            "reason": "missing_downstream_job",
            "lane_id": lane_id,
            "downstream": downstream,
            "report_path": report.get("report_path"),
            "decision_path": report.get("decision_path"),
            "pointer_path": str(pointer_path),
            "controller_phase": ((report.get("controller") or {}).get("phase") if isinstance(report.get("controller"), dict) else None),
        }
    return {
        "ok": True,
        "skipped": False,
        "lane_id": lane_id,
        "downstream": downstream,
        "report_path": report.get("report_path"),
        "decision_path": report.get("decision_path"),
        "pointer_path": str(pointer_path),
        "controller_phase": ((report.get("controller") or {}).get("phase") if isinstance(report.get("controller"), dict) else None),
    }


def _route_incident_runtime_fix_via_controller(
    *,
    inc_dir: Path,
    db_path: Path,
    artifacts_dir: Path,
    target_job_id: str,
    signature: str,
    global_memory_md: Path | None = None,
    global_memory_jsonl: Path | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    pointer_path = inc_dir / "codex" / "source_lane.json"
    pointer_payload = read_json(pointer_path)
    if not isinstance(pointer_payload, dict):
        return {"ok": False, "reason": "missing_source_lane_pointer", "pointer_path": str(pointer_path)}
    canonical_decision_path = str(pointer_payload.get("canonical_decision_path") or "").strip()
    if not canonical_decision_path:
        return {"ok": False, "reason": "missing_canonical_decision_path", "pointer_path": str(pointer_path)}
    decision_payload = read_json(Path(canonical_decision_path))
    if not isinstance(decision_payload, dict):
        return {"ok": False, "reason": "invalid_canonical_decision", "decision_path": canonical_decision_path}
    if str(decision_payload.get("route") or "").strip() != "repair.autofix":
        return {
            "ok": False,
            "reason": "non_runtime_fix_route",
            "decision_path": canonical_decision_path,
            "route": str(decision_payload.get("route") or "").strip(),
        }

    context_pack = _incident_context_pack(inc_dir)
    manifest_obj = read_json(inc_dir / "manifest.json") or {}
    incident_id = str(manifest_obj.get("incident_id") or inc_dir.name).strip() or inc_dir.name
    incident_sig_hash = str(manifest_obj.get("sig_hash") or "").strip() or None
    if global_memory_jsonl is not None:
        action_preferences = load_maintagent_action_preferences(
            jsonl_path=global_memory_jsonl,
            sig_hash=incident_sig_hash,
        )
        if action_preferences.get("preferred_actions"):
            context_pack["preferred_action_families"] = action_preferences
    if global_memory_md is not None and global_memory_md.exists():
        context_pack["global_memory_snapshot_path"] = str(global_memory_md)
        context_pack["global_memory_md"] = str(global_memory_md)
        context_pack["global_memory_excerpt"] = read_text(global_memory_md, limit=20_000)

    controller = execute_sre_fix_request_controller(
        db_path=db_path,
        artifacts_dir=artifacts_dir,
        request_job_id=f"incident_autofix_{incident_id}_{time.time_ns()}",
        kind="sre.fix_request",
        input_obj={
            "incident_id": incident_id,
            "job_id": str(target_job_id),
            "symptom": str(signature or "").strip() or "incident runtime fix",
            "context_pack": context_pack,
            "run_kind": "incident_maintenance",
            "escalation_source": "maint_daemon",
        },
        params_obj={
            "route_mode": "auto_runtime",
            "runtime_apply_actions": True,
            "runtime_allow_actions": decision_payload.get("runtime_fix", {}).get("allow_actions"),
            "runtime_max_risk": decision_payload.get("runtime_fix", {}).get("max_risk"),
            "resume_lane": True,
            "model": (str(model or "").strip() or None),
            "decision_override": decision_payload,
        },
        report_path=None,
    )
    report = dict(controller["report"])
    downstream = dict(controller.get("downstream") or {})
    downstream_job_id = str(downstream.get("job_id") or "").strip()
    if not downstream_job_id:
        return {
            "ok": False,
            "reason": "missing_downstream_job",
            "lane_id": str(controller.get("lane_id") or report.get("lane_id") or ""),
            "report_path": report.get("report_path"),
        }
    return {
        "ok": True,
        "lane_id": str(controller.get("lane_id") or report.get("lane_id") or ""),
        "downstream": downstream,
        "report_path": report.get("report_path"),
        "decision_path": report.get("decision_path"),
        "pointer_path": str(pointer_path),
        "controller_phase": ((report.get("controller") or {}).get("phase") if isinstance(report.get("controller"), dict) else None),
    }


def _start_driver_if_down(
    *,
    driver_root: Path,
    driver_url: str,
    cdp_url: str,
    log_file: Path,
    wait_seconds: float = 8.0,
) -> tuple[bool, dict[str, Any]]:
    hp = _parse_host_port_from_url(driver_url, default_port=18701)
    if hp is None:
        return False, {"error": f"invalid driver_url: {driver_url}"}
    host, port = hp
    probe_host = "127.0.0.1" if str(host).strip() == "0.0.0.0" else str(host)
    if port_open(probe_host, port, timeout_seconds=0.2):
        return True, {"skipped": True, "reason": "driver port already open", "host": host, "port": port}

    details: dict[str, Any] = {"host": host, "port": int(port)}
    started_at = time.time()
    unit_name = "chatgptrest-driver.service"
    load_state = systemd_unit_load_state(unit_name, cwd=driver_root)
    details["systemd_load_state"] = load_state
    systemd_managed = load_state == "loaded"

    # Prefer systemd-managed driver if available, to avoid "orphan" instances holding the MCP singleton lock.
    # When systemd marks the unit as start-limit-hit, `restart` alone will keep failing until
    # we clear the failed state.
    ok_reset, out_reset = run_cmd(
        ["systemctl", "--user", "reset-failed", unit_name],
        cwd=driver_root,
        timeout_seconds=10,
    )
    details["systemd_reset_failed"] = {"ok": bool(ok_reset), "unit": unit_name, "output": out_reset}

    ok_sys, out_sys = run_cmd(
        ["systemctl", "--user", "restart", unit_name],
        cwd=driver_root,
        timeout_seconds=20,
    )
    if (not ok_sys) and ("start-limit-hit" in str(out_sys or "").lower()):
        ok_reset2, out_reset2 = run_cmd(
            ["systemctl", "--user", "reset-failed", unit_name],
            cwd=driver_root,
            timeout_seconds=10,
        )
        details["systemd_reset_failed_retry"] = {"ok": bool(ok_reset2), "unit": unit_name, "output": out_reset2}
        ok_sys, out_sys = run_cmd(
            ["systemctl", "--user", "restart", unit_name],
            cwd=driver_root,
            timeout_seconds=20,
        )
    details["systemd_restart"] = {"ok": bool(ok_sys), "unit": unit_name, "output": out_sys}
    if ok_sys:
        deadline = time.time() + float(max(1.0, wait_seconds))
        while time.time() < deadline:
            if port_open(probe_host, port, timeout_seconds=0.2):
                details["elapsed_ms"] = int(round((time.time() - started_at) * 1000))
                return True, {"started": True, "via": "systemd", **details}
            time.sleep(0.25)

    # In systemd-managed setups, avoid script fallback to prevent unmanaged/orphan
    # driver processes that can hold the singleton lock and block service restarts.
    if systemd_managed:
        details["script_fallback_skipped"] = True
        details["error"] = (
            "systemd-managed driver restart failed; script fallback disabled to avoid singleton-lock conflicts"
        )
        return False, details

    # Best-effort: stop the systemd unit before falling back to a direct script start.
    ok_stop, out_stop = run_cmd(
        ["systemctl", "--user", "stop", unit_name],
        cwd=driver_root,
        timeout_seconds=10,
    )
    details["systemd_stop_before_script"] = {"ok": bool(ok_stop), "unit": unit_name, "output": out_stop}

    script = driver_root / "ops" / "start_driver.sh"
    if not script.exists():
        details["error"] = f"start_driver.sh not found: {script}"
        return False, details

    env = dict(os.environ)
    env["CHATGPT_CDP_URL"] = str(cdp_url)
    env["FASTMCP_HOST"] = str(host)
    env["FASTMCP_PORT"] = str(port)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    proc = None
    try:
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{now_iso()}] starting driver via {script}\n")
            f.flush()
            proc = subprocess.Popen(
                ["bash", str(script)],
                cwd=str(driver_root),
                env=env,
                stdout=f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        deadline = time.time() + float(max(1.0, wait_seconds))
        while time.time() < deadline:
            if port_open(probe_host, port, timeout_seconds=0.2):
                return True, {
                    "started": True,
                    "pid": (proc.pid if proc is not None else None),
                    "host": host,
                    "port": port,
                    "elapsed_ms": int(round((time.time() - started_at) * 1000)),
                    "log_file": str(log_file),
                    "via": "script",
                    **details,
                }
            if proc is not None:
                rc = proc.poll()
                if rc is not None:
                    return False, {
                        "started": False,
                        "pid": proc.pid,
                        "returncode": int(rc),
                        "elapsed_ms": int(round((time.time() - started_at) * 1000)),
                        "log_file": str(log_file),
                        "via": "script",
                        **details,
                    }
            time.sleep(0.25)
    except Exception as exc:
        details["error"] = f"{type(exc).__name__}: {exc}"
        details["log_file"] = str(log_file)
        details["via"] = "script"
        return False, details
    return False, {
        "started": False,
        "pid": (proc.pid if proc is not None else None),
        "elapsed_ms": int(round((time.time() - started_at) * 1000)),
        "log_file": str(log_file),
        "error": "driver did not open port in time",
        "via": "script",
        **details,
    }
def _is_local_host(host: str) -> bool:
    return _shared_is_local_host(host)


def _force_kill_port_listener(*, host: str, port: int) -> dict[str, Any]:
    meta: dict[str, Any] = {"host": str(host), "port": int(port), "pids": [], "signals": [], "ok": False}
    if not _is_local_host(host):
        meta["error"] = "non-local host; refusing to kill listener"
        return meta

    ok, out = run_cmd(["bash", "-lc", f"lsof -nP -iTCP:{int(port)} -sTCP:LISTEN -t"], timeout_seconds=3)
    if not ok and not out:
        meta["error"] = "failed to query listening pids"
        return meta

    pids: list[int] = []
    for part in (out or "").split():
        if part.isdigit():
            try:
                pids.append(int(part))
            except Exception:
                continue
    pids = sorted(set(pids))
    meta["pids"] = pids
    if not pids:
        meta["ok"] = True
        meta["note"] = "no listening pids found"
        return meta

    started_at = time.time()
    probe_host = "127.0.0.1" if str(host).strip() == "0.0.0.0" else str(host)

    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGTERM)
            meta["signals"].append({"pid": int(pid), "signal": "TERM", "ok": True})
        except Exception as exc:
            meta["signals"].append({"pid": int(pid), "signal": "TERM", "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    deadline = time.time() + 4.0
    while time.time() < deadline:
        if not port_open(probe_host, int(port), timeout_seconds=0.2):
            break
        time.sleep(0.2)

    if port_open(probe_host, int(port), timeout_seconds=0.2):
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
                meta["signals"].append({"pid": int(pid), "signal": "KILL", "ok": True})
            except Exception as exc:
                meta["signals"].append({"pid": int(pid), "signal": "KILL", "ok": False, "error": f"{type(exc).__name__}: {exc}"})

        deadline = time.time() + 2.0
        while time.time() < deadline:
            if not port_open(probe_host, int(port), timeout_seconds=0.2):
                break
            time.sleep(0.2)

    meta["port_open_after"] = port_open(probe_host, int(port), timeout_seconds=0.2)
    meta["elapsed_ms"] = int(round((time.time() - started_at) * 1000))
    meta["ok"] = not bool(meta["port_open_after"])
    return meta


def _restart_driver_autofix(
    *,
    driver_root: Path,
    driver_url: str,
    cdp_url: str,
    log_file: Path,
    mcp_client: ToolCaller | None,
    self_check_tool: str | None = "chatgpt_web_self_check",
    conversation_url: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    hp = _parse_host_port_from_url(driver_url, default_port=18701)
    if hp is None:
        return False, {"error": f"invalid driver_url: {driver_url}"}
    host, port = hp
    probe_host = "127.0.0.1" if str(host).strip() == "0.0.0.0" else str(host)

    is_port_open = port_open(probe_host, port, timeout_seconds=0.2)
    details: dict[str, Any] = {"host": host, "port": int(port), "port_open": bool(is_port_open)}

    if not is_port_open:
        ok, start = _start_driver_if_down(driver_root=driver_root, driver_url=driver_url, cdp_url=cdp_url, log_file=log_file)
        details["start"] = start
        return ok, details

    # If we have an MCP client, try a fast self-check to detect "port open but hung".
    if mcp_client is not None and isinstance(self_check_tool, str) and self_check_tool.strip():
        tool_args: dict[str, Any] = {"timeout_seconds": 10}
        if isinstance(conversation_url, str) and conversation_url.strip():
            tool_args["conversation_url"] = conversation_url.strip()
        self_check = _chatgptmcp_call(
            mcp_client,
            tool_name=self_check_tool,
            tool_args=tool_args,
            timeout_seconds=15,
        )
        details["self_check"] = self_check
        if bool(self_check.get("ok")):
            details["skipped"] = True
            details["skip_reason"] = "driver self_check ok"
            return True, details

    # Force restart: kill listener then attempt to start again.
    kill_meta = _force_kill_port_listener(host=host, port=port)
    details["force_kill"] = kill_meta
    ok, start = _start_driver_if_down(driver_root=driver_root, driver_url=driver_url, cdp_url=cdp_url, log_file=log_file)
    details["start"] = start
    if not ok:
        details["error"] = str(start.get("error") or "restart_driver failed")
    return ok, details


def _active_send_jobs(
    *, db_path: Path, limit: int = 5, include_queued: bool = False, exclude_kind_prefixes: tuple[str, ...] = ("repair.",)
) -> dict[str, Any]:
    """Best-effort guardrail: avoid restart actions while a send-stage prompt is in-flight."""
    statuses = ["in_progress"]
    if include_queued:
        statuses.append("queued")
    where_kind: list[str] = []
    params: list[Any] = []
    for p in exclude_kind_prefixes:
        where_kind.append("kind NOT LIKE ?")
        params.append(f"{str(p).strip()}%")
    if not where_kind:
        where_kind_sql = "1=1"
    else:
        where_kind_sql = " AND ".join(where_kind)

    try:
        conn = _connect(db_path)
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:800]}

    try:
        rows = conn.execute(
            f"""
            SELECT job_id, kind, status, phase, updated_at
            FROM jobs
            WHERE status IN ({",".join("?" for _ in statuses)})
              AND phase = 'send'
              AND {where_kind_sql}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            tuple(statuses + params + [int(limit)]),
        ).fetchall()
    except Exception as exc:
        try:
            conn.close()
        except Exception:
            pass
        return {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:800]}

    try:
        conn.close()
    except Exception:
        pass

    active: list[dict[str, Any]] = []
    for r in rows:
        try:
            active.append(
                {
                    "job_id": str(r["job_id"] or ""),
                    "kind": str(r["kind"] or ""),
                    "status": str(r["status"] or ""),
                    "phase": str(r["phase"] or ""),
                    "updated_at": float(r["updated_at"] or 0.0),
                }
            )
        except Exception:
            continue

    return {"ok": True, "active": active, "count": len(active)}


def _apply_codex_sre_autofix(
    *,
    inc_dir: Path,
    incident_id: str,
    actions_payload: dict[str, Any],
    allowed_actions: set[str],
    max_risk: str,
    db_path: Path,
    driver_root: Path,
    driver_url: str,
    cdp_url: str,
    mcp_client: ToolCaller | None,
    provider: str = "chatgpt",
    conversation_url: str | None = None,
) -> dict[str, Any]:
    codex_dir = inc_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    log_path = codex_dir / "autofix_actions.jsonl"

    actions = actions_payload.get("actions")
    if not isinstance(actions, list):
        actions = []

    executed = 0
    attempted = 0
    skipped = 0
    errors = 0
    tools = provider_tools(provider)
    chrome_start_script = _provider_chrome_start_script(provider=provider, driver_root=driver_root)

    for idx, item in enumerate(actions[:20]):
        if not isinstance(item, dict):
            continue
        name = re.sub(r"[^a-z0-9_]+", "", str(item.get("name") or "").strip().lower())
        risk = str(item.get("risk") or "").strip().lower()
        reason = str(item.get("reason") or "").strip()
        if not name:
            continue

        record: dict[str, Any] = {
            "ts": now_iso(),
            "type": "codex_autofix_action",
            "incident_id": str(incident_id),
            "index": int(idx),
            "name": name,
            "risk": (risk or None),
            "reason": (reason or None),
            "allowed": (name in allowed_actions),
            "max_risk": str(max_risk),
            "executed": False,
            "ok": None,
            "error": None,
            "details": None,
        }

        if name not in allowed_actions:
            skipped += 1
            record["ok"] = True
            record["details"] = {"skipped": True, "skip_reason": "not allowed by allowlist"}
            _append_jsonl(log_path, record)
            continue
        if not risk_allows(risk=risk, max_risk=max_risk):
            skipped += 1
            record["ok"] = True
            record["details"] = {"skipped": True, "skip_reason": f"risk '{risk}' exceeds max_risk '{max_risk}'"}
            _append_jsonl(log_path, record)
            continue

        if name in {"restart_chrome", "restart_driver"}:
            drain = _active_send_jobs(db_path=db_path, limit=5, include_queued=False, exclude_kind_prefixes=("repair.",))
            if not bool(drain.get("ok")):
                skipped += 1
                record["ok"] = True
                record["details"] = {"skipped": True, "skip_reason": "drain_guard_error", "drain_guard": drain}
                _append_jsonl(log_path, record)
                continue
            active = drain.get("active")
            if isinstance(active, list) and active:
                skipped += 1
                record["ok"] = True
                record["details"] = {"skipped": True, "skip_reason": "send_in_progress", "drain_guard": drain}
                _append_jsonl(log_path, record)
                continue

        attempted += 1
        record["executed"] = True

        if name == "restart_chrome":
            chrome_start = chrome_start_script
            if not chrome_start.exists():
                errors += 1
                record["ok"] = False
                record["error"] = f"chrome_start.sh not found: {chrome_start}"
            else:
                ok, out = run_cmd(["bash", str(chrome_start)], cwd=driver_root, timeout_seconds=90)
                record["ok"] = bool(ok)
                record["details"] = {"provider": provider, "cmd": str(chrome_start), "output": out}
                if ok:
                    executed += 1
                else:
                    errors += 1
                    record["error"] = out

        elif name == "restart_driver":
            ok, details = _restart_driver_autofix(
                driver_root=driver_root,
                driver_url=driver_url,
                cdp_url=cdp_url,
                log_file=codex_dir / "driver_autostart.log",
                mcp_client=mcp_client,
                self_check_tool=tools.get("self_check"),
                conversation_url=conversation_url,
            )
            record["ok"] = bool(ok)
            record["details"] = details
            if ok:
                executed += 1
            else:
                errors += 1
                record["error"] = str(details.get("error") or "restart_driver failed")

        elif name == "clear_blocked":
            if mcp_client is None:
                errors += 1
                record["ok"] = False
                record["error"] = "mcp_client unavailable"
            else:
                clear_tool = tools.get("clear_blocked")
                if not (isinstance(clear_tool, str) and clear_tool.strip()):
                    skipped += 1
                    record["ok"] = True
                    record["details"] = {"skipped": True, "skip_reason": "unsupported for provider", "provider": provider}
                else:
                    res = _chatgptmcp_call(mcp_client, tool_name=clear_tool, tool_args={}, timeout_seconds=30)
                    ok = bool(res.get("ok"))
                    record["ok"] = ok
                    record["details"] = res
                    if ok:
                        executed += 1
                    else:
                        errors += 1
                        record["error"] = str(res.get("error") or res.get("error_type") or "tool call failed")

        elif name == "capture_ui":
            if mcp_client is None:
                errors += 1
                record["ok"] = False
                record["error"] = "mcp_client unavailable"
            else:
                capture_tool = tools.get("capture_ui")
                if not (isinstance(capture_tool, str) and capture_tool.strip()):
                    skipped += 1
                    record["ok"] = True
                    record["details"] = {"skipped": True, "skip_reason": "unsupported for provider", "provider": provider}
                else:
                    out_dir = inc_dir / "snapshots" / f"codex_capture_ui_{provider}"
                    tool_args: dict[str, Any] = {
                        "mode": "basic",
                        "timeout_seconds": 120,
                        "out_dir": str(out_dir),
                        "write_doc": False,
                    }
                    if isinstance(conversation_url, str) and conversation_url.strip():
                        tool_args["conversation_url"] = conversation_url.strip()
                    res = _chatgptmcp_call(
                        mcp_client,
                        tool_name=capture_tool,
                        tool_args=tool_args,
                        timeout_seconds=150,
                    )
                    ok = bool(res.get("ok"))
                    record["ok"] = ok
                    record["details"] = res
                    if ok:
                        executed += 1
                    else:
                        errors += 1
                        record["error"] = str(res.get("error") or res.get("error_type") or "tool call failed")

        else:
            skipped += 1
            record["ok"] = True
            record["details"] = {"skipped": True, "skip_reason": f"unsupported action: {name}"}

        _append_jsonl(log_path, record)

    return {
        "ok": True,
        "incident_id": str(incident_id),
        "provider": str(provider),
        "allowed_actions": sorted(allowed_actions),
        "max_risk": str(max_risk),
        "attempted": attempted,
        "executed": executed,
        "skipped": skipped,
        "errors": errors,
        "log_path": str(log_path),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Resident maint daemon for ChatgptREST (monitor + incident evidence packs).")
    ap.add_argument("--db", default=os.environ.get("CHATGPTREST_DB_PATH") or "state/jobdb.sqlite3")
    ap.add_argument("--artifacts-dir", default=os.environ.get("CHATGPTREST_ARTIFACTS_DIR") or "artifacts")
    ap.add_argument("--state-file", default="state/maint_daemon_state.json")
    ap.add_argument("--poll-seconds", type=float, default=2.0)
    ap.add_argument("--summary-every-seconds", type=int, default=60)
    ap.add_argument("--scan-every-seconds", type=int, default=15)
    ap.add_argument("--dedupe-seconds", type=int, default=1800)
    ap.add_argument(
        "--incident-max-job-ids",
        type=int,
        default=int(os.environ.get("CHATGPTREST_INCIDENT_MAX_JOB_IDS") or 50),
        help="Keep at most N recent job_ids per incident (0 = unlimited).",
    )
    ap.add_argument(
        "--incident-auto-resolve-after-hours",
        type=int,
        default=int(os.environ.get("CHATGPTREST_INCIDENT_AUTO_RESOLVE_AFTER_HOURS") or 72),
        help="Auto-resolve incidents not seen for N hours (0 = disable).",
    )
    ap.add_argument(
        "--incident-auto-resolve-every-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_INCIDENT_AUTO_RESOLVE_EVERY_SECONDS") or 300),
        help="How often to sweep stale incidents.",
    )
    ap.add_argument(
        "--incident-auto-resolve-max-per-run",
        type=int,
        default=int(os.environ.get("CHATGPTREST_INCIDENT_AUTO_RESOLVE_MAX_PER_RUN") or 50),
        help="Max incidents to auto-resolve per sweep.",
    )
    behavior_issue_default = True
    behavior_issue_env = (os.environ.get("CHATGPTREST_ENABLE_BEHAVIOR_ISSUE_DETECTION") or "").strip().lower()
    if behavior_issue_env in {"0", "false", "no", "n", "off"}:
        behavior_issue_default = False
    elif behavior_issue_env in {"1", "true", "yes", "y", "on"}:
        behavior_issue_default = True
    ap.add_argument(
        "--enable-behavior-issue-detection",
        dest="enable_behavior_issue_detection",
        action="store_true",
        default=behavior_issue_default,
        help="(Default on) Detect high-confidence client behavior regressions and auto-promote them into incidents/issues.",
    )
    ap.add_argument(
        "--disable-behavior-issue-detection",
        dest="enable_behavior_issue_detection",
        action="store_false",
        help="Disable behavior-based issue detection.",
    )
    ap.add_argument(
        "--behavior-issue-every-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_BEHAVIOR_ISSUE_EVERY_SECONDS") or 60),
        help="How often to scan recent jobs for behavior-driven issue signals.",
    )
    ap.add_argument(
        "--behavior-issue-lookback-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_BEHAVIOR_ISSUE_LOOKBACK_SECONDS") or 7200),
        help="Lookback window for behavior issue detection.",
    )
    ap.add_argument(
        "--behavior-issue-jobs-limit",
        type=int,
        default=int(os.environ.get("CHATGPTREST_BEHAVIOR_ISSUE_JOBS_LIMIT") or 1200),
        help="Max recent jobs to inspect per behavior issue sweep.",
    )
    ap.add_argument(
        "--behavior-short-answer-chars-max",
        type=int,
        default=int(os.environ.get("CHATGPTREST_BEHAVIOR_SHORT_ANSWER_CHARS_MAX") or 120),
        help="Completed answers at or below this char count count as suspiciously short for resubmit detection.",
    )
    ap.add_argument(
        "--behavior-short-resubmit-window-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_BEHAVIOR_SHORT_RESUBMIT_WINDOW_SECONDS") or 900),
        help="How quickly a repeated human ask must reappear after a short completion to count as a behavior signal.",
    )
    ap.add_argument(
        "--behavior-short-resubmit-min-occurrences",
        type=int,
        default=int(os.environ.get("CHATGPTREST_BEHAVIOR_SHORT_RESUBMIT_MIN_OCCURRENCES") or 2),
        help="Minimum suspicious short-completion resubmits before promoting an issue.",
    )
    ap.add_argument(
        "--behavior-needs-followup-min-chain",
        type=int,
        default=int(os.environ.get("CHATGPTREST_BEHAVIOR_NEEDS_FOLLOWUP_MIN_CHAIN") or 3),
        help="Minimum needs_followup chain length before promoting a loop issue.",
    )
    behavior_auto_sre_default = True
    behavior_auto_sre_env = (os.environ.get("CHATGPTREST_ENABLE_BEHAVIOR_AUTO_SRE_FIX") or "").strip().lower()
    if behavior_auto_sre_env in {"0", "false", "no", "n", "off"}:
        behavior_auto_sre_default = False
    elif behavior_auto_sre_env in {"1", "true", "yes", "y", "on"}:
        behavior_auto_sre_default = True
    ap.add_argument(
        "--enable-behavior-auto-sre-fix",
        dest="enable_behavior_auto_sre_fix",
        action="store_true",
        default=behavior_auto_sre_default,
        help="(Default on) Auto-submit one idempotent sre.fix_request per promoted behavior issue incident.",
    )
    ap.add_argument(
        "--disable-behavior-auto-sre-fix",
        dest="enable_behavior_auto_sre_fix",
        action="store_false",
        help="Disable auto-submission of sre.fix_request for behavior issues.",
    )
    ap.add_argument(
        "--behavior-issue-max-promotions-per-tick",
        type=int,
        default=int(os.environ.get("CHATGPTREST_BEHAVIOR_ISSUE_MAX_PROMOTIONS_PER_TICK") or 8),
        help="Max behavior issues to promote per maint_daemon tick.",
    )
    ap.add_argument(
        "--behavior-issue-auto-mitigate-after-hours",
        type=float,
        default=float(os.environ.get("CHATGPTREST_BEHAVIOR_ISSUE_AUTO_MITIGATE_AFTER_HOURS") or 24),
        help="Auto-mitigate stale behavior_auto issues after this quiet period (0 disables).",
    )
    ap.add_argument(
        "--behavior-issue-auto-mitigate-max-per-tick",
        type=int,
        default=int(os.environ.get("CHATGPTREST_BEHAVIOR_ISSUE_AUTO_MITIGATE_MAX_PER_TICK") or 10),
        help="Max stale behavior_auto issues to mitigate per tick.",
    )

    ap.add_argument(
        "--issues-registry-path",
        default=os.environ.get("CHATGPTREST_ISSUES_REGISTRY_PATH") or "docs/issues_registry.yaml",
        help="Path to issues_registry.yaml (used for incident packs + Codex input).",
    )
    ap.add_argument(
        "--issues-registry-probe-every-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_ISSUES_REGISTRY_PROBE_EVERY_SECONDS") or 60),
        help="How often to check issues_registry.yaml for changes.",
    )
    ap.add_argument(
        "--issues-registry-sync-max-per-loop",
        type=int,
        default=int(os.environ.get("CHATGPTREST_ISSUES_REGISTRY_SYNC_MAX_PER_LOOP") or 10),
        help="Max open incidents to resync per loop after a registry change.",
    )
    issues_watch_default = True
    issues_watch_env = (os.environ.get("CHATGPTREST_ENABLE_ISSUES_REGISTRY_WATCH") or "").strip().lower()
    if issues_watch_env in {"0", "false", "no", "n", "off"}:
        issues_watch_default = False
    elif issues_watch_env in {"1", "true", "yes", "y", "on"}:
        issues_watch_default = True
    ap.add_argument(
        "--enable-issues-registry-watch",
        dest="enable_issues_registry_watch",
        action="store_true",
        default=issues_watch_default,
        help="(Default on) Watch issues_registry changes and resync open incidents; can retrigger Codex for open incidents.",
    )
    ap.add_argument(
        "--disable-issues-registry-watch",
        dest="enable_issues_registry_watch",
        action="store_false",
        help="Disable issues_registry watch/sync.",
    )

    default_blocked = os.environ.get("CHATGPT_BLOCKED_STATE_FILE") or os.environ.get("CHATGPTREST_BLOCKED_STATE_FILE")
    if not default_blocked:
        repo_root = Path(__file__).resolve().parents[1]
        state_driver = (repo_root / "state" / "driver" / "chatgpt_blocked_state.json").resolve()
        if state_driver.parent.exists():
            default_blocked = str(state_driver)
        else:
            default_blocked = str((repo_root / ".run/chatgpt_blocked_state.json").resolve())
    ap.add_argument("--chatgptmcp-blocked-state-file", default=default_blocked)
    ap.add_argument("--blocked-state-every-seconds", type=int, default=120)
    ap.add_argument(
        "--enable-auto-pause",
        action="store_true",
        help="If blocked_state indicates blocked, pause processing via DB meta (affects workers' claim_next_job).",
    )
    ap.add_argument(
        "--auto-pause-mode",
        default=(os.environ.get("CHATGPTREST_AUTO_PAUSE_MODE") or "send"),
        help="Pause mode: send|all (send pauses send-phase only; all pauses all non-repair jobs).",
    )
    ap.add_argument(
        "--auto-pause-default-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_AUTO_PAUSE_DEFAULT_SECONDS") or 1800),
        help="If blocked_until is missing/invalid, pause for this many seconds.",
    )
    ap.add_argument("--mihomo-delay-log-dir", default=os.environ.get("MIHOMO_DELAY_LOG_DIR") or "artifacts/monitor/mihomo_delay")
    ap.add_argument("--mihomo-delay-every-seconds", type=int, default=300)
    ap.add_argument("--proxy-scan-every-seconds", type=int, default=60)
    ap.add_argument("--proxy-incident-min-consecutive-failures", type=int, default=3)
    ap.add_argument("--proxy-incident-recent-records", type=int, default=50)
    ap.add_argument("--proxy-incident-history-days", type=int, default=7)
    ap.add_argument("--proxy-incident-ok-baseline-samples", type=int, default=50)
    ap.add_argument("--proxy-incident-probe-candidates", type=int, default=5)
    ap.add_argument("--proxy-incident-probe-timeout-seconds", type=float, default=20.0)
    ap.add_argument("--proxy-incident-severity", default="P1")
    ap.add_argument("--cdp-url", default=os.environ.get("CHATGPT_CDP_URL") or _default_chatgpt_cdp_url())
    ap.add_argument("--cdp-every-seconds", type=int, default=120)
    ap.add_argument(
        "--enable-api-autostart",
        action="store_true",
        help="If ChatgptREST API port is down, start it in-process (safe: does not send prompts).",
    )
    ap.add_argument(
        "--api-autostart-every-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_API_AUTOSTART_EVERY_SECONDS") or 15),
        help="How often to probe ChatgptREST API port (when --enable-api-autostart).",
    )
    ap.add_argument(
        "--api-autostart-min-interval-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_API_AUTOSTART_MIN_INTERVAL_SECONDS") or 60),
        help="Min seconds between API autostart attempts (when --enable-api-autostart).",
    )
    default_driver_root = os.environ.get("CHATGPTREST_DRIVER_ROOT") or str(Path(__file__).resolve().parents[1])
    ap.add_argument(
        "--chatgptmcp-root",
        default=str(Path(default_driver_root).expanduser()),
        help="Path to driver repo root for safe restart helpers (override for external chatgptMCP).",
    )
    ap.add_argument("--driver-mode", default=os.environ.get("CHATGPTREST_DRIVER_MODE") or "external_mcp")
    ap.add_argument(
        "--chatgpt-mcp-url",
        default=os.environ.get("CHATGPTREST_DRIVER_URL")
        or os.environ.get("CHATGPTREST_CHATGPT_MCP_URL")
        or "http://127.0.0.1:18701/mcp",
    )
    ap.add_argument("--enable-chatgptmcp-evidence", action="store_true", help="On incident, collect chatgptMCP self_check/blocked/rate_limit as evidence (no prompt send).")
    ap.add_argument("--enable-chatgptmcp-capture-ui", action="store_true", help="On incident, run chatgpt_web_capture_ui(mode=basic) to save UI snapshots (no prompt send).")
    ap.add_argument("--enable-chrome-autostart", action="store_true", help="If CDP is down, run chatgptMCP/ops/chrome_start.sh (safe: no-op when already running).")
    infra_healer_default = True
    infra_healer_env = (os.environ.get("CHATGPTREST_ENABLE_INFRA_HEALER") or "").strip().lower()
    if infra_healer_env in {"0", "false", "no", "n", "off"}:
        infra_healer_default = False
    elif infra_healer_env in {"1", "true", "yes", "y", "on"}:
        infra_healer_default = True
    ap.add_argument(
        "--enable-infra-healer",
        dest="enable_infra_healer",
        action="store_true",
        default=infra_healer_default,
        help="(Default on) Auto-heal infra issues by restarting driver/Chrome when jobs are stuck due to CDP/TargetClosed errors.",
    )
    ap.add_argument("--disable-infra-healer", dest="enable_infra_healer", action="store_false", help="Disable infra healer.")
    ap.add_argument("--infra-healer-window-seconds", type=int, default=3600, help="Rate-limit window for infra healer actions.")
    ap.add_argument("--infra-healer-max-per-window", type=int, default=10, help="Max infra healer actions per window.")
    ap.add_argument("--infra-healer-min-interval-seconds", type=int, default=120, help="Min seconds between infra healer actions.")
    ap.add_argument(
        "--enable-auto-repair-check",
        action="store_true",
        help="On incident, submit a read-only `repair.check` job (no prompt send) and attach its report into the incident pack.",
    )
    ap.add_argument("--auto-repair-check-mode", default="quick", help="repair.check params.mode (quick|full|debug).")
    ap.add_argument("--auto-repair-check-timeout-seconds", type=int, default=60, help="repair.check params.timeout_seconds.")
    ap.add_argument("--auto-repair-check-recent-failures", type=int, default=5, help="repair.check params.recent_failures.")
    ap.add_argument(
        "--auto-repair-check-probe-driver",
        dest="auto_repair_check_probe_driver",
        action="store_true",
        default=True,
        help="Enable repair.check driver probe calls (no prompt send).",
    )
    ap.add_argument(
        "--auto-repair-check-no-probe-driver",
        dest="auto_repair_check_probe_driver",
        action="store_false",
        help="Disable repair.check driver probe calls.",
    )
    ap.add_argument("--auto-repair-check-window-seconds", type=int, default=3600, help="Rate-limit window for auto repair.check submissions.")
    ap.add_argument("--auto-repair-check-max-per-window", type=int, default=20, help="Max auto-submitted repair.check jobs per window.")
    codex_maint_fallback_default = True
    codex_maint_fallback_env = (os.environ.get("CHATGPTREST_ENABLE_CODEX_MAINT_FALLBACK") or "").strip().lower()
    if codex_maint_fallback_env in {"0", "false", "no", "n", "off"}:
        codex_maint_fallback_default = False
    elif codex_maint_fallback_env in {"1", "true", "yes", "y", "on"}:
        codex_maint_fallback_default = True
    ap.add_argument(
        "--enable-codex-maint-fallback",
        dest="enable_codex_maint_fallback",
        action="store_true",
        default=codex_maint_fallback_default,
        help=(
            "(Default on) If codex_sre analyze/autofix fails on an incident, submit one "
            "idempotent repair.autofix job as Codex-backed maint fallback."
        ),
    )
    ap.add_argument(
        "--disable-codex-maint-fallback",
        dest="enable_codex_maint_fallback",
        action="store_false",
        help="Disable Codex-backed maint fallback submission.",
    )
    ap.add_argument(
        "--codex-maint-fallback-timeout-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CODEX_MAINT_FALLBACK_TIMEOUT_SECONDS") or 600),
        help="repair.autofix params.timeout_seconds for maint fallback jobs.",
    )
    ap.add_argument(
        "--codex-maint-fallback-allow-actions",
        default=(
            os.environ.get("CHATGPTREST_CODEX_MAINT_FALLBACK_ALLOW_ACTIONS")
            or "restart_chrome,restart_driver,refresh,regenerate,capture_ui,clear_blocked"
        ),
        help="Comma-separated allow_actions passed to repair.autofix fallback jobs.",
    )
    ap.add_argument(
        "--codex-maint-fallback-max-risk",
        default=(os.environ.get("CHATGPTREST_CODEX_MAINT_FALLBACK_MAX_RISK") or "medium"),
        help="max_risk passed to repair.autofix fallback jobs (low|medium|high).",
    )
    ap.add_argument(
        "--codex-maint-fallback-window-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CODEX_MAINT_FALLBACK_WINDOW_SECONDS") or 3600),
        help="Global rate-limit window for Codex maint fallback submissions.",
    )
    ap.add_argument(
        "--codex-maint-fallback-max-per-window",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CODEX_MAINT_FALLBACK_MAX_PER_WINDOW") or 6),
        help="Max Codex maint fallback submissions per window.",
    )
    ap.add_argument(
        "--codex-maint-fallback-max-per-incident",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CODEX_MAINT_FALLBACK_MAX_PER_INCIDENT") or 1),
        help="Max Codex maint fallback submissions per incident.",
    )
    ui_canary_default = True
    ui_canary_env = (os.environ.get("CHATGPTREST_ENABLE_UI_CANARY") or "").strip().lower()
    if ui_canary_env in {"0", "false", "no", "n", "off"}:
        ui_canary_default = False
    elif ui_canary_env in {"1", "true", "yes", "y", "on"}:
        ui_canary_default = True
    ap.add_argument(
        "--enable-ui-canary",
        dest="enable_ui_canary",
        action="store_true",
        default=ui_canary_default,
        help="(Default on) Run periodic provider UI self-check canary (no prompt send).",
    )
    ap.add_argument(
        "--disable-ui-canary",
        dest="enable_ui_canary",
        action="store_false",
        help="Disable periodic UI self-check canary.",
    )
    ap.add_argument(
        "--ui-canary-providers",
        default=(
            os.environ.get("CHATGPTREST_UI_CANARY_PROVIDERS")
            or ",".join(_default_ui_canary_providers())
        ),
        help="Comma-separated providers for periodic canary (chatgpt,gemini).",
    )
    ap.add_argument(
        "--ui-canary-every-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_UI_CANARY_EVERY_SECONDS") or 1800),
        help="Interval between periodic UI canary rounds.",
    )
    ap.add_argument(
        "--ui-canary-timeout-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_UI_CANARY_TIMEOUT_SECONDS") or 45),
        help="Timeout per provider self-check probe.",
    )
    ap.add_argument(
        "--ui-canary-fail-threshold",
        type=int,
        default=int(os.environ.get("CHATGPTREST_UI_CANARY_FAIL_THRESHOLD") or 2),
        help="Create/refresh incident after N consecutive canary failures per provider.",
    )
    ap.add_argument(
        "--ui-canary-capture-on-failure",
        action="store_true",
        default=True,
        help="Capture provider UI snapshots when canary fails (subject to cooldown).",
    )
    ap.add_argument(
        "--ui-canary-no-capture-on-failure",
        dest="ui_canary_capture_on_failure",
        action="store_false",
        help="Disable canary capture_ui on failure.",
    )
    ap.add_argument(
        "--ui-canary-capture-cooldown-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_UI_CANARY_CAPTURE_COOLDOWN_SECONDS") or 1800),
        help="Min seconds between canary capture_ui runs per provider.",
    )
    ap.add_argument(
        "--ui-canary-capture-timeout-seconds",
        type=int,
        default=int(os.environ.get("CHATGPTREST_UI_CANARY_CAPTURE_TIMEOUT_SECONDS") or 120),
        help="Timeout for canary capture_ui tool calls.",
    )
    ap.add_argument(
        "--ui-canary-incident-severity",
        default=(os.environ.get("CHATGPTREST_UI_CANARY_INCIDENT_SEVERITY") or "P2"),
        help="Severity used for ui_canary incidents.",
    )
    ap.add_argument(
        "--ui-canary-snapshot-retention-days",
        type=int,
        default=int(os.environ.get("CHATGPTREST_UI_CANARY_SNAPSHOT_RETENTION_DAYS") or 30),
        help="Delete UI-canary snapshot directories older than this many days.",
    )
    ap.add_argument(
        "--enable-codex-sre-analyze",
        action="store_true",
        help="On incident, run Codex (read-only) to analyze the incident pack and write `codex/sre_actions.json` + `codex/sre_actions.md`.",
    )
    ap.add_argument("--codex-sre-model", default=os.environ.get("CODEX_SRE_MODEL") or "", help="Optional codex model override.")
    ap.add_argument("--codex-sre-timeout-seconds", type=int, default=600, help="Timeout for a single codex analysis run.")
    ap.add_argument("--codex-sre-min-interval-seconds", type=int, default=900, help="Min seconds between codex analyses per incident.")
    ap.add_argument("--codex-sre-window-seconds", type=int, default=3600, help="Global rate-limit window for codex analyses.")
    ap.add_argument("--codex-sre-max-per-window", type=int, default=12, help="Max codex analyses per window.")
    ap.add_argument("--codex-sre-max-per-incident", type=int, default=3, help="Max codex analyses per incident.")
    codex_memory_default = True
    codex_memory_env = (os.environ.get("CHATGPTREST_ENABLE_CODEX_GLOBAL_MEMORY") or "").strip().lower()
    if codex_memory_env in {"0", "false", "no", "n", "off"}:
        codex_memory_default = False
    elif codex_memory_env in {"1", "true", "yes", "y", "on"}:
        codex_memory_default = True
    ap.add_argument(
        "--enable-codex-global-memory",
        dest="enable_codex_global_memory",
        action="store_true",
        default=codex_memory_default,
        help="(Default on) Maintain a global Codex memory file and include a snapshot in SRE prompts.",
    )
    ap.add_argument(
        "--disable-codex-global-memory",
        dest="enable_codex_global_memory",
        action="store_false",
        help="Disable global Codex memory.",
    )
    ap.add_argument(
        "--codex-global-memory-jsonl",
        default=os.environ.get("CHATGPTREST_CODEX_GLOBAL_MEMORY_JSONL") or "",
        help="Path for global memory JSONL (default: artifacts/monitor/maint_daemon/codex_global_memory.jsonl).",
    )
    ap.add_argument(
        "--codex-global-memory-md",
        default=os.environ.get("CHATGPTREST_CODEX_GLOBAL_MEMORY_MD") or "",
        help="Path for global memory markdown digest (default: artifacts/monitor/maint_daemon/codex_global_memory.md).",
    )
    ap.add_argument(
        "--codex-global-memory-digest-max-records",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CODEX_GLOBAL_MEMORY_DIGEST_MAX_RECORDS") or 200),
        help="Max records to include in the markdown digest.",
    )
    ap.add_argument(
        "--codex-global-memory-prompt-max-chars",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CODEX_GLOBAL_MEMORY_PROMPT_MAX_CHARS") or 60000),
        help="Max chars of global memory snapshot injected into a Codex prompt.",
    )
    ap.add_argument(
        "--codex-global-memory-max-bytes",
        type=int,
        default=int(os.environ.get("CHATGPTREST_CODEX_GLOBAL_MEMORY_MAX_BYTES") or 0),
        help="Optional max bytes for the JSONL log (0 = unlimited).",
    )

    ap.add_argument(
        "--enable-codex-sre-autofix",
        action="store_true",
        help="(Disabled by default) Execute a whitelisted subset of low-risk actions from the codex SRE report.",
    )
    ap.add_argument(
        "--codex-sre-autofix-allow-actions",
        default="restart_chrome,restart_driver",
        help="Comma-separated allowed action names to execute (default: restart_chrome,restart_driver).",
    )
    ap.add_argument("--codex-sre-autofix-max-risk", default="low", help="Max risk to execute automatically (low|medium|high).")
    ap.add_argument("--codex-sre-autofix-window-seconds", type=int, default=3600, help="Global rate-limit window for codex autofix runs.")
    ap.add_argument("--codex-sre-autofix-max-per-window", type=int, default=10, help="Max codex autofix runs per window.")
    ap.add_argument("--codex-sre-autofix-max-per-incident", type=int, default=1, help="Max codex autofix runs per incident.")
    ap.add_argument("--incident-severity-default", default="P2")
    ap.add_argument("--run-seconds", type=int, default=0, help="0 = run forever (until SIGINT).")
    args = ap.parse_args(argv)
    if bool(args.enable_codex_sre_autofix):
        # Auto-fix depends on having a codex report.
        args.enable_codex_sre_analyze = True
    args.cdp_url = _resolve_loopback_cdp_url(str(getattr(args, "cdp_url", "") or ""))

    repo_root = Path(__file__).resolve().parents[1]
    db_path = Path(str(args.db)).expanduser()
    if not db_path.is_absolute():
        db_path = (repo_root / db_path).resolve(strict=False)
    if not db_path.exists():
        raise SystemExit(f"db not found: {db_path}")

    artifacts_dir = Path(str(args.artifacts_dir)).expanduser()
    if not artifacts_dir.is_absolute():
        artifacts_dir = (repo_root / artifacts_dir).resolve(strict=False)

    monitor_dir = (artifacts_dir / "monitor" / "maint_daemon").resolve(strict=False)
    monitor_dir.mkdir(parents=True, exist_ok=True)
    ui_canary_dir = (artifacts_dir / "monitor" / "ui_canary").resolve(strict=False)
    ui_canary_dir.mkdir(parents=True, exist_ok=True)
    ui_canary_latest_path = ui_canary_dir / "latest.json"
    day = datetime.now(UTC).strftime("%Y%m%d")
    log_path = monitor_dir / f"maint_{day}.jsonl"

    codex_global_memory_jsonl = (
        Path(str(args.codex_global_memory_jsonl)).expanduser()
        if str(getattr(args, "codex_global_memory_jsonl", "")).strip()
        else (monitor_dir / "codex_global_memory.jsonl")
    )
    if not codex_global_memory_jsonl.is_absolute():
        codex_global_memory_jsonl = (repo_root / codex_global_memory_jsonl).resolve(strict=False)

    codex_global_memory_md = (
        Path(str(args.codex_global_memory_md)).expanduser()
        if str(getattr(args, "codex_global_memory_md", "")).strip()
        else (monitor_dir / "codex_global_memory.md")
    )
    if not codex_global_memory_md.is_absolute():
        codex_global_memory_md = (repo_root / codex_global_memory_md).resolve(strict=False)

    state_path = Path(str(args.state_file)).expanduser()
    if not state_path.is_absolute():
        state_path = (repo_root / state_path).resolve(strict=False)

    state_obj = read_json(state_path) or {}
    last_event_id = int(state_obj.get("last_event_id") or 0)
    incidents: dict[str, IncidentState] = {}
    ui_canary_state: dict[str, dict[str, Any]] = _load_ui_canary_state(state_obj)
    last_ui_canary_ts = float(state_obj.get("ui_canary_last_ts") or 0.0)
    # NOTE: historical submission timestamps were previously persisted in the state file.
    # Rate limiting is now derived from the DB-backed remediation_actions table.

    chatgptmcp_state_path = Path(str(args.chatgptmcp_blocked_state_file)).expanduser()
    legacy_blocked_path = (repo_root / "../chatgptMCP/.run/chatgpt_blocked_state.json").resolve()
    chatgptmcp_root = Path(str(args.chatgptmcp_root)).expanduser()
    if not chatgptmcp_root.is_absolute():
        chatgptmcp_root = (repo_root / chatgptmcp_root).resolve(strict=False)
    mihomo_delay_dir = Path(str(args.mihomo_delay_log_dir)).expanduser()
    if not mihomo_delay_dir.is_absolute():
        mihomo_delay_dir = (repo_root / mihomo_delay_dir).resolve(strict=False)

    issues_registry_src = Path(str(args.issues_registry_path)).expanduser()
    if not issues_registry_src.is_absolute():
        issues_registry_src = (repo_root / issues_registry_src).resolve(strict=False)

    # Load persisted daemon state + active incidents from DB.
    try:
        boot_conn = _connect(db_path)
    except Exception:
        boot_conn = None
    if boot_conn is not None:
        try:
            daemon_state = incident_db.load_daemon_state(boot_conn)
            if isinstance(daemon_state, dict):
                last_event_id = int(daemon_state.get("last_event_id") or last_event_id)
            if not daemon_state and state_obj:
                incident_db.save_daemon_state(boot_conn, {"last_event_id": int(last_event_id)})

            # One-time cleanup at boot: keep only one active incident per fingerprint_hash.
            # This prevents the incidents table from accumulating many duplicates after restarts.
            try:
                boot_conn.execute("BEGIN IMMEDIATE")
                resolved_dups = incident_db.resolve_duplicate_open_incidents(
                    boot_conn,
                    now=time.time(),
                    limit=20_000,
                )
                boot_conn.commit()
                if resolved_dups:
                    _append_jsonl(
                        log_path,
                        {
                            "ts": now_iso(),
                            "type": "incident_duplicate_compacted",
                            "resolved": int(len(resolved_dups)),
                        },
                    )
            except Exception as exc:
                try:
                    boot_conn.rollback()
                except Exception:
                    pass
                _append_jsonl(
                    log_path,
                    {
                        "ts": now_iso(),
                        "type": "incident_duplicate_compaction_error",
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:800],
                    },
                )

            incidents = _load_incident_state_from_db(boot_conn)
            if not incidents:
                incidents = _load_incident_state(state_obj)
                # One-time best-effort migration: persist legacy state-file incidents into DB.
                for inc in incidents.values():
                    category = "proxy" if str(inc.signature or "").startswith("proxy_degraded:") else "job"
                    sev = str(args.proxy_incident_severity) if category == "proxy" else str(args.incident_severity_default)
                    inc_dir = _incident_dir(monitor_dir, inc.incident_id)
                    _upsert_incident_db(
                        boot_conn,
                        incident=inc,
                        category=category,
                        severity=sev,
                        status="open",
                        evidence_dir=inc_dir,
                    )
        finally:
            try:
                boot_conn.close()
            except Exception:
                pass

    codex_autofix_allowed = parse_allow_actions(str(args.codex_sre_autofix_allow_actions or ""))
    codex_autofix_max_risk = str(args.codex_sre_autofix_max_risk or "").strip().lower() or "low"
    if codex_autofix_max_risk not in _RISK_RANK:
        codex_autofix_max_risk = "low"
    codex_maint_fallback_allow_actions = str(args.codex_maint_fallback_allow_actions or "").strip()
    codex_maint_fallback_max_risk = str(args.codex_maint_fallback_max_risk or "").strip().lower() or "medium"
    if codex_maint_fallback_max_risk not in _RISK_RANK:
        codex_maint_fallback_max_risk = "medium"

    started = time.time()
    deadline = None if int(args.run_seconds) <= 0 else (started + float(max(1, int(args.run_seconds))))
    last_summary_ts = 0.0
    last_scan_ts = 0.0
    last_blocked_ts = 0.0
    last_mihomo_ts = 0.0
    last_cdp_ts = 0.0
    last_proxy_scan_ts = 0.0
    last_api_probe_ts = 0.0
    last_api_autostart_ts = 0.0
    last_incident_auto_resolve_ts = 0.0
    last_issues_registry_probe_ts = 0.0
    issues_registry_sha256 = str(state_obj.get("issues_registry_sha256") or "").strip()
    pending_issues_registry_sync: list[str] = []

    mcp_client = None
    if (
        bool(args.enable_chatgptmcp_evidence)
        or bool(args.enable_chatgptmcp_capture_ui)
        or bool(args.enable_ui_canary)
        or bool(args.enable_codex_sre_autofix)
        or bool(args.enable_infra_healer)
    ):
        mcp_client = build_tool_caller(
            mode=normalize_driver_mode(args.driver_mode),
            url=str(args.chatgpt_mcp_url),
            client_name="chatgptrest-maint-daemon",
            client_version="0.1.0",
        )

    _append_jsonl(
        log_path,
        {
            "ts": now_iso(),
            "type": "maint_started",
            "db": str(db_path),
            "artifacts": str(artifacts_dir),
            "ui_canary_enabled": bool(args.enable_ui_canary),
            "behavior_issue_detection_enabled": bool(args.enable_behavior_issue_detection),
            "behavior_auto_sre_fix_enabled": bool(args.enable_behavior_auto_sre_fix),
            "ui_canary_providers": _parse_ui_canary_providers(str(args.ui_canary_providers)),
            "build": get_build_info(include_dirty=True),
        },
    )
    _stop_watchdog_heartbeat()
    _start_watchdog_heartbeat(status="maint_daemon booted")

    if not issues_registry_sha256:
        try:
            if issues_registry_src.exists():
                issues_registry_sha256 = hashlib.sha256(issues_registry_src.read_bytes()).hexdigest()
        except Exception:
            issues_registry_sha256 = ""

    # ── Phase 2: SubsystemRunner initialization ─────────────────
    _pre_db_subsystem_runner = SubsystemRunner([
        HealthCheckSubsystem(),
    ])
    _post_db_subsystem_runner = SubsystemRunner([
        AutoResolveSubsystem(
            interval_seconds=float(max(5, int(args.incident_auto_resolve_every_seconds))),
        ),
        BlockedStateSubsystem(
            interval_seconds=float(max(10, int(args.blocked_state_every_seconds))),
        ),
        JobsSummarySubsystem(
            interval_seconds=float(max(5, int(args.summary_every_seconds))),
        ),
        BehaviorIssueSubsystem(
            interval_seconds=float(max(10, int(args.behavior_issue_every_seconds))),
        ),
    ])

    while deadline is None or time.time() < deadline:
        time.sleep(max(0.2, float(args.poll_seconds)))
        now = time.time()

        # ── Phase 2: SubsystemRunner tick ──────────────────────
        _tick_ctx = TickContext(
            now=now,
            args=args,
            conn=None,  # set after DB connect below
            state={
                "log_path": log_path,
                "incidents": incidents,
                "incident_auto_resolve_after_hours": int(args.incident_auto_resolve_after_hours),
                "incident_auto_resolve_max_per_run": int(args.incident_auto_resolve_max_per_run),
                "incident_db": incident_db,
                "artifacts_dir": artifacts_dir,
                "monitor_dir": monitor_dir,
                "dedupe_seconds": int(args.dedupe_seconds),
                "chatgptmcp_state_path": str(chatgptmcp_state_path),
                "legacy_blocked_path": str(legacy_blocked_path),
                "enable_auto_pause": bool(args.enable_auto_pause),
                "auto_pause_mode": str(args.auto_pause_mode or "send"),
                "auto_pause_default_seconds": int(args.auto_pause_default_seconds),
                "jobs_summary_fn": _jobs_summary,
                "enable_behavior_issue_detection": bool(args.enable_behavior_issue_detection),
                "behavior_issue_lookback_seconds": int(args.behavior_issue_lookback_seconds),
                "behavior_issue_jobs_limit": int(args.behavior_issue_jobs_limit),
                "behavior_short_answer_chars_max": int(args.behavior_short_answer_chars_max),
                "behavior_short_resubmit_window_seconds": int(args.behavior_short_resubmit_window_seconds),
                "behavior_short_resubmit_min_occurrences": int(args.behavior_short_resubmit_min_occurrences),
                "behavior_needs_followup_min_chain": int(args.behavior_needs_followup_min_chain),
                "enable_behavior_auto_sre_fix": bool(args.enable_behavior_auto_sre_fix),
                "behavior_issue_max_promotions_per_tick": int(args.behavior_issue_max_promotions_per_tick),
                "behavior_issue_auto_mitigate_after_hours": float(args.behavior_issue_auto_mitigate_after_hours),
                "behavior_issue_auto_mitigate_max_per_tick": int(args.behavior_issue_auto_mitigate_max_per_tick),
            },
        )
        # Run subsystems that don't need DB (e.g. health_check)
        _pre_db_obs = _pre_db_subsystem_runner.tick_all(_tick_ctx)
        for _obs in _pre_db_obs:
            _append_jsonl(log_path, {"ts": now_iso(), "subsystem": _obs.subsystem, **_obs.data})

        try:
            conn = _connect(db_path)
        except Exception as exc:
            _append_jsonl(log_path, {"ts": now_iso(), "type": "db_connect_error", "error": str(exc)})
            continue

        try:
            events = _fetch_events(conn, last_event_id)
            for row in events:
                payload_raw = row["payload_json"]
                payload = None
                if payload_raw:
                    try:
                        payload = json.loads(str(payload_raw))
                    except Exception:
                        payload = {"_raw": str(payload_raw)}
                _append_jsonl(
                    log_path,
                    {
                        "ts": now_iso(),
                        "type": "job_event",
                        "event_id": int(row["id"]),
                        "job_id": str(row["job_id"]),
                        "event_ts": float(row["ts"]),
                        "event_type": str(row["type"]),
                        "payload": payload,
                    },
                )
                last_event_id = int(row["id"])

            # Jobs summary — now delegated to JobsSummarySubsystem via tick_all.

            # Auto-resolve stale incidents — delegated to SubsystemRunner.
            _tick_ctx.conn = conn  # update with live connection
            _post_db_obs = _post_db_subsystem_runner.tick_all(_tick_ctx)
            for _obs in _post_db_obs:
                _append_jsonl(log_path, {"ts": now_iso(), "subsystem": _obs.subsystem, **_obs.data})

            # Trigger: issue registry changes can retrigger Codex analysis for open incidents.
            if bool(args.enable_issues_registry_watch) and now - last_issues_registry_probe_ts >= float(
                max(5, int(args.issues_registry_probe_every_seconds))
            ):
                last_issues_registry_probe_ts = now
                new_sha = ""
                try:
                    if issues_registry_src.exists():
                        new_sha = hashlib.sha256(issues_registry_src.read_bytes()).hexdigest()
                except Exception:
                    new_sha = ""
                if new_sha and new_sha != issues_registry_sha256:
                    old_sha = issues_registry_sha256 or None
                    issues_registry_sha256 = new_sha
                    pending_issues_registry_sync = sorted(
                        list(incidents.keys()),
                        key=lambda k: float(incidents[k].last_seen_ts if k in incidents else 0.0),
                        reverse=True,
                    )
                    _append_jsonl(
                        log_path,
                        {
                            "ts": now_iso(),
                            "type": "issues_registry_changed",
                            "path": str(issues_registry_src),
                            "old_sha256": old_sha,
                            "new_sha256": new_sha,
                            "pending_incidents": len(pending_issues_registry_sync),
                        },
                    )

            if bool(args.enable_issues_registry_watch) and pending_issues_registry_sync:
                max_sync = int(max(0, int(args.issues_registry_sync_max_per_loop)))
                for _ in range(min(max_sync, len(pending_issues_registry_sync))):
                    pending_signature_hash = pending_issues_registry_sync.pop(0)
                    inc = incidents.get(pending_signature_hash)
                    if inc is None:
                        continue
                    inc_dir = _incident_dir(monitor_dir, inc.incident_id)
                    inc_dir.mkdir(parents=True, exist_ok=True)
                    snapshots = inc_dir / "snapshots"
                    snapshots.mkdir(parents=True, exist_ok=True)
                    _safe_copy(issues_registry_src, snapshots / "issues_registry.yaml")
                    atomic_write_json(
                        snapshots / "issues_registry_sync.json",
                        {"ts": now_iso(), "sha256": issues_registry_sha256, "source_path": str(issues_registry_src)},
                    )
                    _append_jsonl(
                        log_path,
                        {
                            "ts": now_iso(),
                            "type": "issues_registry_synced",
                            "incident_id": inc.incident_id,
                            "sig_hash": pending_signature_hash,
                            "sha256": (issues_registry_sha256 or None),
                        },
                    )

                    # Optional: re-run Codex analysis for open incidents (no new job events required).
                    if bool(args.enable_codex_sre_analyze) and ("repair." not in str(inc.signature or "")):
                        input_hash = _codex_input_fingerprint(inc_dir)
                        min_interval = max(30, int(args.codex_sre_min_interval_seconds))
                        max_per_incident = max(0, int(args.codex_sre_max_per_incident))
                        should_run_codex = False

                        if max_per_incident > 0 and int(inc.codex_run_count) >= max_per_incident:
                            _append_jsonl(
                                log_path,
                                {
                                    "ts": now_iso(),
                                    "type": "codex_sre_incident_run_capped",
                                    "trigger": "issues_registry_change",
                                    "incident_id": inc.incident_id,
                                    "sig_hash": inc.sig_hash,
                                    "run_count": int(inc.codex_run_count),
                                    "max_per_incident": int(max_per_incident),
                                },
                            )
                        else:
                            if inc.codex_last_run_ts is None:
                                should_run_codex = True
                            else:
                                age = float(now) - float(inc.codex_last_run_ts or 0.0)
                                if age >= float(min_interval):
                                    if inc.codex_last_ok is not True:
                                        should_run_codex = True
                                    elif inc.codex_input_hash != input_hash:
                                        should_run_codex = True

                        if should_run_codex:
                            window_seconds = float(max(1, int(args.codex_sre_window_seconds)))
                            recent_submissions = incident_db.count_actions(
                                conn,
                                action_type="codex_sre_analyze",
                                since_ts=(now - window_seconds),
                            )
                            if int(recent_submissions) >= int(args.codex_sre_max_per_window):
                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "codex_sre_rate_limited",
                                        "trigger": "issues_registry_change",
                                        "incident_id": inc.incident_id,
                                        "sig_hash": inc.sig_hash,
                                        "window_seconds": int(window_seconds),
                                        "max_per_window": int(args.codex_sre_max_per_window),
                                        "recent_submissions": int(recent_submissions),
                                    },
                                )
                            else:
                                global_mem_snapshot = None
                                if bool(args.enable_codex_global_memory):
                                    global_mem_snapshot = _snapshot_codex_global_memory_md(
                                        global_md=codex_global_memory_md,
                                        inc_dir=inc_dir,
                                        max_chars=int(args.codex_global_memory_prompt_max_chars),
                                    )

                                run_meta = _run_codex_sre_analyze_incident(
                                    repo_root=repo_root,
                                    inc_dir=inc_dir,
                                    db_path=db_path,
                                    artifacts_dir=artifacts_dir,
                                    model=str(args.codex_sre_model),
                                    timeout_seconds=int(args.codex_sre_timeout_seconds),
                                    global_memory_md=global_mem_snapshot,
                                    global_memory_jsonl=codex_global_memory_jsonl,
                                )
                                inc.codex_input_hash = input_hash
                                inc.codex_last_run_ts = float(now)
                                inc.codex_run_count = int(inc.codex_run_count) + 1
                                inc.codex_last_ok = bool(run_meta.get("ok"))
                                inc.codex_last_error = (str(run_meta.get("error") or "").strip() or None)

                                manifest_obj = read_json(inc_dir / "manifest.json")
                                manifest = manifest_obj if isinstance(manifest_obj, dict) else {}
                                provider_for_mem = str(manifest.get("provider") or "").strip() or None
                                _maybe_update_codex_global_memory_after_run(
                                    enabled=bool(args.enable_codex_global_memory),
                                    trigger="issues_registry_change",
                                    inc_dir=inc_dir,
                                    incident_id=inc.incident_id,
                                    sig_hash=inc.sig_hash,
                                    signature=str(inc.signature),
                                    provider=provider_for_mem,
                                    run_meta=run_meta,
                                    jsonl_path=codex_global_memory_jsonl,
                                    md_path=codex_global_memory_md,
                                    digest_max_records=int(args.codex_global_memory_digest_max_records),
                                    max_bytes=int(args.codex_global_memory_max_bytes),
                                    log_path=log_path,
                                )
                                manifest["codex_input_hash"] = inc.codex_input_hash
                                manifest["codex_last_run_ts"] = inc.codex_last_run_ts
                                manifest["codex_run_count"] = int(inc.codex_run_count)
                                manifest["codex_last_ok"] = inc.codex_last_ok
                                manifest["codex_last_error"] = inc.codex_last_error
                                _write_manifest(inc_dir / "manifest.json", manifest)
                                _upsert_incident_db(
                                    conn,
                                    incident=inc,
                                    category=None,
                                    severity=None,
                                    status="open",
                                    evidence_dir=inc_dir,
                                )
                                incident_db.create_action(
                                    conn,
                                    incident_id=inc.incident_id,
                                    action_type="codex_sre_analyze",
                                    status=(
                                        incident_db.ACTION_STATUS_COMPLETED
                                        if bool(run_meta.get("ok"))
                                        else incident_db.ACTION_STATUS_FAILED
                                    ),
                                    risk_level="low",
                                    result={
                                        "trigger": "issues_registry_change",
                                        "ok": bool(run_meta.get("ok")),
                                        "elapsed_ms": run_meta.get("elapsed_ms"),
                                        "input_hash": run_meta.get("input_hash"),
                                        "model": run_meta.get("model"),
                                        "actions_json": run_meta.get("actions_json"),
                                        "actions_md": run_meta.get("actions_md"),
                                        "error": run_meta.get("error"),
                                    },
                                )

                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "codex_sre_analyzed",
                                        "trigger": "issues_registry_change",
                                        "incident_id": inc.incident_id,
                                        "sig_hash": inc.sig_hash,
                                        "ok": bool(run_meta.get("ok")),
                                        "elapsed_ms": run_meta.get("elapsed_ms"),
                                        "input_hash": run_meta.get("input_hash"),
                                        "model": run_meta.get("model"),
                                        "actions_json": run_meta.get("actions_json"),
                                        "actions_md": run_meta.get("actions_md"),
                                        "error": run_meta.get("error"),
                                    },
                                )

            if bool(args.enable_api_autostart) and now - last_api_probe_ts >= float(max(5, int(args.api_autostart_every_seconds))):
                last_api_probe_ts = now
                host, port = _chatgptrest_api_host_port()
                probe_host = "127.0.0.1" if str(host).strip() == "0.0.0.0" else str(host)
                is_port_open = port_open(probe_host, int(port), timeout_seconds=0.2)
                if not is_port_open:
                    min_interval = float(max(0, int(args.api_autostart_min_interval_seconds)))
                    if now - last_api_autostart_ts < min_interval:
                        _append_jsonl(
                            log_path,
                            {
                                "ts": now_iso(),
                                "type": "api_autostart_rate_limited",
                                "host": str(host),
                                "port": int(port),
                                "min_interval_seconds": min_interval,
                            },
                        )
                    else:
                        last_api_autostart_ts = now
                        api_log = (repo_root / "logs" / "chatgptrest_api.autostart.log").resolve()
                        started_at = time.time()
                        ok, details = _start_api_if_down(
                            repo_root=repo_root,
                            host=str(host),
                            port=int(port),
                            log_file=api_log,
                            wait_seconds=8.0,
                        )
                        _append_jsonl(
                            log_path,
                            {
                                "ts": now_iso(),
                                "type": "api_autostart",
                                "ok": bool(ok),
                                "elapsed_ms": int((time.time() - started_at) * 1000),
                                "details": details,
                            },
                        )

            # Blocked-state + auto-pause — delegated to BlockedStateSubsystem via tick_all.

            if now - last_mihomo_ts >= float(max(30, int(args.mihomo_delay_every_seconds))):
                day_local = datetime.now(UTC).strftime("%Y%m%d")
                p = mihomo_delay_dir / f"mihomo_delay_{day_local}.jsonl"
                rec = _tail_last_jsonl(p)
                if rec is not None:
                    _append_jsonl(log_path, {"ts": now_iso(), "type": "mihomo_delay_last", "path": str(p), "record": rec})
                last_mihomo_ts = now

            if now - last_cdp_ts >= float(max(15, int(args.cdp_every_seconds))):
                cdp = http_json(str(args.cdp_url).rstrip("/") + "/json/version", timeout_seconds=5.0)
                _append_jsonl(log_path, {"ts": now_iso(), "type": "cdp_version", "cdp_url": str(args.cdp_url), "result": cdp})
                last_cdp_ts = now

            if (
                bool(args.enable_ui_canary)
                and mcp_client is not None
                and now - float(last_ui_canary_ts) >= float(max(30, int(args.ui_canary_every_seconds)))
            ):
                providers = _parse_ui_canary_providers(str(args.ui_canary_providers))
                threshold = max(1, int(args.ui_canary_fail_threshold))
                capture_cooldown = float(max(60, int(args.ui_canary_capture_cooldown_seconds)))
                round_rows: list[dict[str, Any]] = []
                for provider in providers:
                    state_row = ui_canary_state.get(provider) or _ui_canary_default_state()
                    ui_canary_state[provider] = state_row

                    prov_tools = provider_tools(provider)
                    self_check_tool = prov_tools.get("self_check")
                    if not (isinstance(self_check_tool, str) and self_check_tool.strip()):
                        print(
                            f"[ui_canary] provider={provider} skipped: no self_check tool available",
                            flush=True,
                        )
                        state_row["last_run_ts"] = float(now)
                        state_row["last_status"] = "skipped"
                        round_rows.append(
                            {
                                "provider": provider,
                                "ok": None,
                                "status": "skipped",
                                "reason": "provider_self_check_not_supported",
                                "consecutive_failures": int(state_row.get("consecutive_failures") or 0),
                            }
                        )
                        continue

                    self_wrapped = _chatgptmcp_call(
                        mcp_client,
                        tool_name=self_check_tool,
                        tool_args={"timeout_seconds": int(max(10, int(args.ui_canary_timeout_seconds)))},
                        timeout_seconds=int(max(15, int(args.ui_canary_timeout_seconds) + 15)),
                    )
                    summary = _ui_canary_probe_summary(provider=provider, wrapped=self_wrapped)
                    state_row["last_run_ts"] = float(now)
                    state_row["last_status"] = str(summary.get("status") or "")
                    state_row["last_error_type"] = str(summary.get("error_type") or "")
                    state_row["last_error"] = str(summary.get("error") or "")
                    state_row["last_conversation_url"] = str(summary.get("conversation_url") or "")
                    state_row["last_mode_text"] = str(summary.get("mode_text") or "")
                    state_row["last_run_id"] = str(summary.get("run_id") or "")

                    capture_wrapped: dict[str, Any] | None = None
                    capture_reason: str | None = None
                    if bool(summary.get("success")):
                        state_row["consecutive_failures"] = 0
                        state_row["last_ok_ts"] = float(now)
                        # P2 #6: UI fingerprint change detection.
                        new_fp = _ui_canary_fingerprint(provider=provider, summary=summary)
                        old_fp = str(state_row.get("last_fingerprint") or "")
                        if old_fp and new_fp != old_fp:
                            _append_jsonl(
                                log_path,
                                {
                                    "ts": now_iso(),
                                    "type": "ui_canary_fingerprint_changed",
                                    "provider": provider,
                                    "old_fingerprint": old_fp,
                                    "new_fingerprint": new_fp,
                                    "mode_text": str(summary.get("mode_text") or ""),
                                    "status": str(summary.get("status") or ""),
                                },
                            )
                            print(
                                f"[ui_canary] fingerprint changed for {provider}: "
                                f"{old_fp} -> {new_fp} (mode_text={summary.get('mode_text') or ''})",
                                flush=True,
                            )
                        state_row["last_fingerprint"] = new_fp
                    else:
                        state_row["consecutive_failures"] = int(state_row.get("consecutive_failures") or 0) + 1
                        state_row["last_failure_ts"] = float(now)
                        state_row["last_signature"] = _ui_canary_signature(provider=provider, summary=summary)

                        capture_tool = prov_tools.get("capture_ui")
                        can_capture = bool(args.ui_canary_capture_on_failure) and isinstance(capture_tool, str) and capture_tool.strip()
                        if can_capture:
                            since_capture = float(now - float(state_row.get("last_capture_ts") or 0.0))
                            if since_capture >= capture_cooldown:
                                capture_out_dir = (
                                    ui_canary_dir
                                    / "snapshots"
                                    / str(provider)
                                    / f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}Z"
                                )
                                capture_args: dict[str, Any] = {
                                    "mode": "basic",
                                    "timeout_seconds": int(max(20, int(args.ui_canary_capture_timeout_seconds))),
                                    "out_dir": str(capture_out_dir),
                                    "write_doc": False,
                                }
                                conversation_hint = str(summary.get("conversation_url") or "").strip()
                                if conversation_hint:
                                    capture_args["conversation_url"] = conversation_hint
                                capture_wrapped = _chatgptmcp_call(
                                    mcp_client,
                                    tool_name=capture_tool,
                                    tool_args=capture_args,
                                    timeout_seconds=int(max(30, int(args.ui_canary_capture_timeout_seconds) + 30)),
                                )
                                state_row["last_capture_ts"] = float(now)
                            else:
                                capture_reason = f"capture_cooldown:{int(capture_cooldown - since_capture)}s"
                        elif bool(args.ui_canary_capture_on_failure):
                            capture_reason = "provider_capture_ui_not_supported"
                        else:
                            capture_reason = "capture_disabled"

                    round_row: dict[str, Any] = {
                        "provider": provider,
                        "ok": bool(summary.get("success")),
                        "status": str(summary.get("status") or ""),
                        "mode_text": str(summary.get("mode_text") or ""),
                        "error_type": str(summary.get("error_type") or ""),
                        "error": str(summary.get("error") or ""),
                        "conversation_url": str(summary.get("conversation_url") or ""),
                        "consecutive_failures": int(state_row.get("consecutive_failures") or 0),
                        "threshold": int(threshold),
                    }
                    if capture_reason:
                        round_row["capture_skipped"] = capture_reason
                    if isinstance(capture_wrapped, dict):
                        round_row["capture_ok"] = bool(capture_wrapped.get("ok"))
                        round_row["capture_error_type"] = str(capture_wrapped.get("error_type") or "")

                    round_rows.append(round_row)

                    if bool(summary.get("success")) or int(state_row.get("consecutive_failures") or 0) < threshold:
                        continue

                    signature = _ui_canary_signature(provider=provider, summary=summary)
                    signature_hash = sig_hash(signature)
                    existing = incidents.get(signature_hash)
                    if existing is not None and (now - existing.last_seen_ts) < float(max(60, int(args.dedupe_seconds))):
                        incident = existing
                    else:
                        incident_id = f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}Z_{signature_hash}"
                        if existing is not None:
                            _resolve_incident_rollover(
                                conn,
                                monitor_dir=monitor_dir,
                                incident=existing,
                                now=float(now),
                                replaced_by_incident_id=str(incident_id),
                                log_path=log_path,
                            )
                        incident = IncidentState(
                            incident_id=incident_id,
                            signature=signature,
                            sig_hash=signature_hash,
                            created_ts=now,
                            last_seen_ts=now,
                            count=0,
                            job_ids=[],
                        )
                        incidents[signature_hash] = incident
                        _append_jsonl(
                            log_path,
                            {
                                "ts": now_iso(),
                                "type": "ui_canary_incident_created",
                                "incident_id": incident.incident_id,
                                "sig_hash": signature_hash,
                                "provider": provider,
                                "signature": signature,
                            },
                        )

                    incident.last_seen_ts = float(now)
                    incident.count = int(incident.count) + 1
                    state_row["last_incident_ts"] = float(now)

                    inc_dir = _incident_dir(monitor_dir, incident.incident_id)
                    inc_dir.mkdir(parents=True, exist_ok=True)
                    snapshots = inc_dir / "snapshots"
                    snapshots.mkdir(parents=True, exist_ok=True)
                    _safe_copy(issues_registry_src, snapshots / "issues_registry.yaml")
                    if chatgptmcp_state_path.exists():
                        _safe_copy(chatgptmcp_state_path, snapshots / "chatgptmcp_blocked_state.json")
                    elif legacy_blocked_path.exists():
                        _safe_copy(legacy_blocked_path, snapshots / "chatgptmcp_blocked_state.json")

                    provider_cdp_url = _provider_cdp_url(provider=provider, args=args)
                    provider_cdp = http_json(provider_cdp_url.rstrip("/") + "/json/version", timeout_seconds=5.0)
                    atomic_write_json(
                        snapshots / "cdp_version.json",
                        {"provider": provider, "cdp_url": provider_cdp_url, "result": provider_cdp},
                    )

                    atomic_write_json(
                        snapshots / "ui_canary_probe.json",
                        {
                            "provider": provider,
                            "observed_at": now_iso(),
                            "threshold": int(threshold),
                            "consecutive_failures": int(state_row.get("consecutive_failures") or 0),
                            "summary": summary,
                            "self_check": self_wrapped,
                            "capture_ui": (capture_wrapped or {"skipped": True, "reason": (capture_reason or "")}),
                        },
                    )

                    manifest = {
                        "incident_id": incident.incident_id,
                        "sig_hash": incident.sig_hash,
                        "signature": incident.signature,
                        "category": "ui_canary",
                        "provider": provider,
                        "severity": str(args.ui_canary_incident_severity),
                        "created_ts": incident.created_ts,
                        "last_seen_ts": incident.last_seen_ts,
                        "count": incident.count,
                        "job_ids": [],
                    }
                    _write_manifest(inc_dir / "manifest.json", manifest)
                    _upsert_incident_db(
                        conn,
                        incident=incident,
                        category="ui_canary",
                        severity=str(args.ui_canary_incident_severity),
                        status="open",
                        evidence_dir=inc_dir,
                    )

                    incident_db.create_action(
                        conn,
                        incident_id=incident.incident_id,
                        action_type="ui_canary_probe",
                        status=incident_db.ACTION_STATUS_COMPLETED,
                        risk_level="low",
                        result={
                            "provider": provider,
                            "consecutive_failures": int(state_row.get("consecutive_failures") or 0),
                            "threshold": int(threshold),
                            "status": str(summary.get("status") or ""),
                            "error_type": str(summary.get("error_type") or ""),
                            "error": str(summary.get("error") or ""),
                        },
                    )

                canary_snapshot = {
                    "ts": now_iso(),
                    "providers": round_rows,
                    "state": _dump_ui_canary_state(ui_canary_state),
                }
                atomic_write_json(ui_canary_latest_path, canary_snapshot)
                _append_jsonl(
                    log_path,
                    {
                        "ts": now_iso(),
                        "type": "ui_canary_round",
                        "providers": round_rows,
                    },
                )
                last_ui_canary_ts = float(now)

                # P1 #5: snapshot retention cleanup.
                try:
                    retention_days = max(1, int(args.ui_canary_snapshot_retention_days))
                    cutoff = time.time() - (retention_days * 86400)
                    snap_root = ui_canary_dir / "snapshots"
                    if snap_root.is_dir():
                        cleaned = 0
                        for prov_dir in snap_root.iterdir():
                            if not prov_dir.is_dir():
                                continue
                            for ts_dir in sorted(prov_dir.iterdir()):
                                if not ts_dir.is_dir():
                                    continue
                                try:
                                    mtime = ts_dir.stat().st_mtime
                                except OSError:
                                    continue
                                if mtime < cutoff:
                                    import shutil
                                    shutil.rmtree(ts_dir, ignore_errors=True)
                                    cleaned += 1
                        if cleaned:
                            _append_jsonl(
                                log_path,
                                {
                                    "ts": now_iso(),
                                    "type": "ui_canary_snapshot_cleanup",
                                    "retention_days": retention_days,
                                    "cleaned": cleaned,
                                },
                            )
                except Exception as exc:
                    print(f"[ui_canary] snapshot cleanup error: {exc}", flush=True)

            if now - last_proxy_scan_ts >= float(max(10, int(args.proxy_scan_every_seconds))):
                try:
                    mihomo_log = _pick_latest_mihomo_log(mihomo_delay_dir)
                    if mihomo_log is not None:
                        rows = mihomo_delay.tail_jsonl(mihomo_log, max_lines=max(200, int(args.proxy_incident_recent_records) * 4))
                        if rows:
                            allowed_groups = set(mihomo_delay.load_mihomo_delay_config().groups or [])
                            latest_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
                            for r in rows:
                                group = str(r.get("group") or "")
                                selected = str(r.get("selected") or "")
                                if not group or not selected:
                                    continue
                                if isinstance(r, dict):
                                    latest_by_pair[(group, selected)] = r

                            for (group, selected), last in sorted(latest_by_pair.items(), key=lambda x: x[0]):
                                if allowed_groups and group not in allowed_groups:
                                    continue
                                if bool(last.get("ok")):
                                    continue

                                summary = mihomo_delay.recent_health_summary(
                                    records=rows,
                                    group=group,
                                    selected=selected,
                                    max_records=int(args.proxy_incident_recent_records),
                                )
                                min_fail = max(1, int(args.proxy_incident_min_consecutive_failures))
                                if int(summary.get("consecutive_failures") or 0) >= min_fail:
                                    err_type = str(last.get("error_type") or "")
                                    err = normalize_error(str(last.get("error") or ""))
                                    delay_url = str(last.get("url") or "")
                                    signature = f"proxy_degraded:{group}:{selected}:{delay_url}:{err_type}:{err}"

                                    signature_hash = sig_hash(signature)
                                    existing = incidents.get(signature_hash)
                                    if existing is not None and (now - existing.last_seen_ts) < float(max(60, int(args.dedupe_seconds))):
                                        incident = existing
                                        created = False
                                    else:
                                        incident_id = f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}Z_{signature_hash}"
                                        if existing is not None:
                                            _resolve_incident_rollover(
                                                conn,
                                                monitor_dir=monitor_dir,
                                                incident=existing,
                                                now=float(now),
                                                replaced_by_incident_id=str(incident_id),
                                                log_path=log_path,
                                            )
                                        incident = IncidentState(
                                            incident_id=incident_id,
                                            signature=signature,
                                            sig_hash=signature_hash,
                                            created_ts=now,
                                            last_seen_ts=now,
                                            count=0,
                                            job_ids=[],
                                        )
                                        incidents[signature_hash] = incident
                                        created = True
                                        _append_jsonl(
                                            log_path,
                                            {
                                                "ts": now_iso(),
                                                "type": "proxy_incident_created",
                                                "incident_id": incident.incident_id,
                                                "sig_hash": signature_hash,
                                                "group": group,
                                                "selected": selected,
                                                "consecutive_failures": int(summary.get("consecutive_failures") or 0),
                                                "delay_url": delay_url,
                                                "last_error_type": err_type,
                                                "last_error": err,
                                            },
                                        )

                                    incident.last_seen_ts = now
                                    incident.count += 1

                                    inc_dir = _incident_dir(monitor_dir, incident.incident_id)
                                    inc_dir.mkdir(parents=True, exist_ok=True)
                                    snapshots = inc_dir / "snapshots"
                                    snapshots.mkdir(parents=True, exist_ok=True)
                                    _safe_copy(issues_registry_src, snapshots / "issues_registry.yaml")

                                    manifest = {
                                        "incident_id": incident.incident_id,
                                        "sig_hash": incident.sig_hash,
                                        "signature": incident.signature,
                                        "category": "proxy",
                                        "severity": str(args.proxy_incident_severity),
                                        "created_ts": incident.created_ts,
                                        "last_seen_ts": incident.last_seen_ts,
                                        "count": incident.count,
                                        "job_ids": [],
                                        "proxy": {"group": group, "selected": selected},
                                    }
                                    _write_manifest(inc_dir / "manifest.json", manifest)
                                    _upsert_incident_db(
                                        conn,
                                        incident=incident,
                                        category="proxy",
                                        severity=str(args.proxy_incident_severity),
                                        status="open",
                                        evidence_dir=inc_dir,
                                    )

                                    if chatgptmcp_state_path.exists():
                                        _safe_copy(chatgptmcp_state_path, snapshots / "chatgptmcp_blocked_state.json")
                                    elif legacy_blocked_path.exists():
                                        _safe_copy(legacy_blocked_path, snapshots / "chatgptmcp_blocked_state.json")

                                    atomic_write_json(snapshots / "mihomo_delay_last.json", {"path": str(mihomo_log), "record": last})
                                    recent = [r for r in rows if str(r.get("group") or "") == group and str(r.get("selected") or "") == selected][
                                        -int(args.proxy_incident_recent_records) :
                                    ]
                                    atomic_write_json(snapshots / "mihomo_delay_recent.json", {"path": str(mihomo_log), "records": recent})

                                    cdp = http_json(str(args.cdp_url).rstrip("/") + "/json/version", timeout_seconds=5.0)
                                    atomic_write_json(snapshots / "cdp_version.json", {"cdp_url": str(args.cdp_url), "result": cdp})

                                    # Compare against historical ok baseline (last N days).
                                    log_paths_desc: list[Path] = []
                                    try:
                                        all_logs = sorted(mihomo_delay_dir.glob("mihomo_delay_*.jsonl"), reverse=True)
                                    except Exception:
                                        all_logs = []
                                    for p in all_logs:
                                        log_paths_desc.append(p)
                                        if len(log_paths_desc) >= max(1, int(args.proxy_incident_history_days)):
                                            break
                                    if mihomo_log not in log_paths_desc:
                                        log_paths_desc.insert(0, mihomo_log)

                                    baseline_delays = _collect_recent_ok_delays(
                                        log_paths_desc=log_paths_desc,
                                        group=group,
                                        selected=selected,
                                        max_samples=int(args.proxy_incident_ok_baseline_samples),
                                    )
                                    baseline_median = _robust_percentile(baseline_delays, 0.5)
                                    baseline_p90 = _robust_percentile(baseline_delays, 0.9)
                                    last_ok = _collect_last_ok_record(log_paths_desc=log_paths_desc, group=group, selected=selected)
                                    last_ok_ts = mihomo_delay.parse_record_ts(last_ok.get("ts")) if isinstance(last_ok, dict) else None

                                    proxy_health = {
                                        "observed_at": now_iso(),
                                        "log_path": str(mihomo_log),
                                        "group": group,
                                        "selected": selected,
                                        "recent": summary,
                                        "last_error_type": err_type,
                                        "last_error": err,
                                        "delay_url": str(last.get("url") or ""),
                                        "timeout_ms": int(last.get("timeout_ms") or 0),
                                        "baseline_ok_delay": {
                                            "n": len(baseline_delays),
                                            "median_ms": baseline_median,
                                            "p90_ms": baseline_p90,
                                        },
                                        "last_ok_ts": last_ok_ts,
                                        "last_ok_age_seconds": (time.time() - float(last_ok_ts)) if last_ok_ts else None,
                                    }
                                    atomic_write_json(snapshots / "proxy_health_summary.json", proxy_health)

                                    controller = str(last.get("controller") or "").rstrip("/")
                                    if controller and not (snapshots / "mihomo_proxies_group.json").exists():
                                        proxies_payload = _http_json_no_proxy(f"{controller}/proxies", headers=_mihomo_headers(), timeout_seconds=10.0)
                                        proxies_obj = proxies_payload.get("proxies") if isinstance(proxies_payload, dict) else None
                                        group_obj = proxies_obj.get(group) if isinstance(proxies_obj, dict) and isinstance(proxies_obj.get(group), dict) else None
                                        selected_obj = (
                                            proxies_obj.get(selected) if isinstance(proxies_obj, dict) and isinstance(proxies_obj.get(selected), dict) else None
                                        )
                                        group_all = group_obj.get("all") if isinstance(group_obj, dict) else None
                                        all_names = [str(x) for x in (group_all or []) if isinstance(x, str)]
                                        filtered = _filter_mihomo_candidates(all_names, selected=selected)
                                        max_probe = max(0, int(args.proxy_incident_probe_candidates))

                                        probe_candidates: list[str] = []
                                        if "DIRECT" in filtered:
                                            probe_candidates.append("DIRECT")
                                        others = [n for n in filtered if n != "DIRECT"]
                                        remaining = max(0, max_probe - len(probe_candidates))
                                        if remaining > 0:
                                            if len(others) <= remaining:
                                                probe_candidates.extend(others)
                                            elif remaining == 1:
                                                probe_candidates.append(others[len(others) // 2])
                                            else:
                                                for i in range(remaining):
                                                    idx = int(round(i * (len(others) - 1) / float(remaining - 1)))
                                                    probe_candidates.append(others[max(0, min(len(others) - 1, idx))])
                                        # De-dupe while preserving order.
                                        seen: set[str] = set()
                                        candidates = []
                                        for name in probe_candidates:
                                            if name in seen:
                                                continue
                                            seen.add(name)
                                            candidates.append(name)

                                        atomic_write_json(
                                            snapshots / "mihomo_proxies_group.json",
                                            {
                                                "controller": controller,
                                                "group": group,
                                                "selected": selected,
                                                "group_proxy": {
                                                    "type": (group_obj.get("type") if isinstance(group_obj, dict) else None),
                                                    "now": (group_obj.get("now") if isinstance(group_obj, dict) else None),
                                                    "all": (group_all if isinstance(group_all, list) else None),
                                                },
                                                "selected_proxy": (
                                                    {
                                                        "type": selected_obj.get("type") if isinstance(selected_obj, dict) else None,
                                                        "now": selected_obj.get("now") if isinstance(selected_obj, dict) else None,
                                                        "all": (selected_obj.get("all") if isinstance(selected_obj.get("all"), list) else None),
                                                    }
                                                    if isinstance(selected_obj, dict)
                                                    else None
                                                ),
                                            },
                                        )

                                        url = str(last.get("url") or "")
                                        timeout_ms = int(last.get("timeout_ms") or 8000)
                                        if candidates and url and not (snapshots / "mihomo_candidate_probes.json").exists():
                                            probes: list[dict[str, Any]] = []
                                            for cand in candidates:
                                                probes.append(
                                                    _mihomo_probe_delay(
                                                        controller=controller,
                                                        name=cand,
                                                        url=url,
                                                        timeout_ms=timeout_ms,
                                                        timeout_seconds=float(args.proxy_incident_probe_timeout_seconds),
                                                    )
                                                )
                                            atomic_write_json(snapshots / "mihomo_candidate_probes.json", {"candidates": candidates, "probes": probes})

                                            ok_probes = [p for p in probes if bool(p.get("ok")) and isinstance(p.get("delay_ms"), int)]
                                            ok_probes.sort(key=lambda x: int(x.get("delay_ms") or 10**9))
                                            direct_ok = next((p for p in ok_probes if str(p.get("name") or "") == "DIRECT"), None)
                                            suggestions = [p for p in ok_probes if str(p.get("name") or "") != "DIRECT"][:3]
                                            atomic_write_json(
                                                snapshots / "proxy_switch_suggestions.json",
                                                {"group": group, "selected": selected, "suggestions": suggestions, "direct_probe": direct_ok},
                                            )

                                            if created or not (inc_dir / "summary.md").exists():
                                                lines: list[str] = []
                                                lines.append(f"# Proxy incident: {group} -> {selected}")
                                                lines.append("")
                                                lines.append(f"- Consecutive failures: {int(summary.get('consecutive_failures') or 0)} (threshold={min_fail})")
                                                lines.append(f"- Last error: {err_type} {err}")
                                                if last_ok_ts:
                                                    lines.append(
                                                        f"- Last OK: {datetime.fromtimestamp(float(last_ok_ts), UTC).isoformat().replace('+00:00','Z')}"
                                                    )
                                                if baseline_median is not None:
                                                    lines.append(
                                                        f"- Baseline OK delay: median={baseline_median}ms p90={baseline_p90}ms (n={len(baseline_delays)})"
                                                    )
                                                lines.append("")
                                                if suggestions:
                                                    lines.append("## Suggested nodes (manual switch)")
                                                    for s0 in suggestions:
                                                        lines.append(f"- {s0.get('name')}: {s0.get('delay_ms')}ms")
                                                    lines.append("")
                                                    lines.append("Switch (mihomo API, manual):")
                                                    lines.append(f"- PUT {controller}/proxies/{group}  body: " + '{"name":"<node>"}')
                                                else:
                                                    lines.append("## No healthy candidate found")
                                                    lines.append("- No healthy proxy candidate found among probed nodes.")
                                                    if isinstance(direct_ok, dict):
                                                        lines.append(f"- DIRECT probe: {direct_ok.get('delay_ms')}ms (control; may not work for ChatGPT)")
                                                    lines.append("- Check mihomo connectivity / subscription / switch node group manually.")
                                                (inc_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
                except Exception as exc:
                    _append_jsonl(log_path, {"ts": now_iso(), "type": "proxy_scan_error", "error_type": type(exc).__name__, "error": str(exc)[:500]})

                last_proxy_scan_ts = now

            if now - last_scan_ts >= float(max(5, int(args.scan_every_seconds))):
              try:  # ── Phase 0: subsystem isolation (scan/evidence/heal/repair/codex) ──
                # Find new abnormal jobs and bundle evidence packs.
                scan_rows = conn.execute(
                    "SELECT job_id, kind, status, created_at, updated_at, last_error_type, last_error, input_json, params_json, conversation_url, answer_path, conversation_export_path "
                    "FROM jobs ORDER BY updated_at DESC LIMIT 200"
                ).fetchall()

                for r in scan_rows:
                    job_id = str(r["job_id"])
                    status = str(r["status"] or "")
                    kind = str(r["kind"] or "")
                    conversation_url = str(r["conversation_url"] or "").strip()
                    provider = _incident_provider(kind=kind, conversation_url=conversation_url)
                    created_at = float(r["created_at"] or 0.0)
                    updated_at = float(r["updated_at"] or 0.0)

                    abnormal = False
                    signature = ""
                    if status in {"blocked", "cooldown"}:
                        abnormal = True
                        signature = (
                            f"{status}:{provider}:{kind}:{str(r['last_error_type'] or '')}:"
                            f"{normalize_error(str(r['last_error'] or ''))}"
                        )
                    elif status == "needs_followup":
                        # Avoid bloating incident signatures with potentially large user/assistant content.
                        # needs_followup is actionable on the client side; group by kind+error_type only.
                        abnormal = True
                        signature = f"needs_followup:{provider}:{kind}:{str(r['last_error_type'] or '')}"
                    elif status == "error":
                        abnormal = True
                        signature = (
                            f"error:{provider}:{kind}:{str(r['last_error_type'] or '')}:"
                            f"{normalize_error(str(r['last_error'] or ''))}"
                        )
                    elif status == "in_progress":
                        expected = job_expected_max_seconds(str(r["params_json"] or ""))
                        if now - created_at > float(expected):
                            abnormal = True
                            signature = f"stuck:{provider}:{kind}:created>{expected}s"

                    if not abnormal:
                        continue

                    signature_hash = sig_hash(signature)
                    signal_ts = float(updated_at if updated_at > 0 else created_at if created_at > 0 else now)
                    existing = incidents.get(signature_hash)
                    incident: IncidentState
                    is_new_incident = False
                    if existing is not None and not incident_should_rollover_for_signal(
                        signal_ts=signal_ts,
                        last_seen_ts=float(existing.last_seen_ts),
                        dedupe_seconds=int(args.dedupe_seconds),
                    ):
                        incident = existing
                    else:
                        incident_id = f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}Z_{signature_hash}"
                        if existing is not None:
                            _resolve_incident_rollover(
                                conn,
                                monitor_dir=monitor_dir,
                                incident=existing,
                                now=float(now),
                                replaced_by_incident_id=str(incident_id),
                                log_path=log_path,
                            )
                        incident = IncidentState(
                            incident_id=incident_id,
                            signature=signature,
                            sig_hash=signature_hash,
                            created_ts=signal_ts,
                            last_seen_ts=signal_ts,
                            count=0,
                            job_ids=[],
                        )
                        incidents[signature_hash] = incident
                        is_new_incident = True
                        _append_jsonl(
                            log_path,
                            {"ts": now_iso(), "type": "incident_created", "incident_id": incident.incident_id, "sig_hash": signature_hash, "signature": signature},
                        )

                    freshness = incident_freshness_gate(
                        incident=incident,
                        signal_ts=signal_ts,
                        is_new_incident=bool(is_new_incident),
                        job_id=job_id,
                    )
                    has_fresh_signal = bool(freshness.get("has_fresh_signal"))
                    if bool(freshness.get("should_skip_touch")):
                        # No new evidence and no pending automated follow-up work.
                        # Skip touch/write to keep last_seen_at meaningful and reduce noisy churn.
                        continue

                    if has_fresh_signal:
                        incident.last_seen_ts = float(signal_ts)

                    if job_id not in incident.job_ids:
                        incident.job_ids.append(job_id)
                        incident.count += 1
                        max_job_ids = int(getattr(args, "incident_max_job_ids", 50) or 0)
                        if max_job_ids > 0 and len(incident.job_ids) > max_job_ids:
                            incident.job_ids = incident.job_ids[-max_job_ids:]

                    inc_dir = _incident_dir(monitor_dir, incident.incident_id)
                    inc_dir.mkdir(parents=True, exist_ok=True)

                    # Write/update manifest.
                    manifest = {
                        "incident_id": incident.incident_id,
                        "sig_hash": incident.sig_hash,
                        "signature": incident.signature,
                        "provider": provider,
                        "severity": str(args.incident_severity_default),
                        "created_ts": incident.created_ts,
                        "last_seen_ts": incident.last_seen_ts,
                        "count": incident.count,
                        "job_ids": list(incident.job_ids),
                        "repair_job_id": (incident.repair_job_id or None),
                        "codex_input_hash": (incident.codex_input_hash or None),
                        "codex_last_run_ts": (float(incident.codex_last_run_ts) if incident.codex_last_run_ts else None),
                        "codex_run_count": int(incident.codex_run_count),
                        "codex_last_ok": (incident.codex_last_ok if incident.codex_last_ok is not None else None),
                        "codex_last_error": (incident.codex_last_error or None),
                        "codex_autofix_last_ts": (
                            float(incident.codex_autofix_last_ts) if incident.codex_autofix_last_ts else None
                        ),
                        "codex_autofix_run_count": int(incident.codex_autofix_run_count),
                    }
                    _write_manifest(inc_dir / "manifest.json", manifest)
                    _upsert_incident_db(
                        conn,
                        incident=incident,
                        category="job",
                        severity=str(args.incident_severity_default),
                        status="open",
                        evidence_dir=inc_dir,
                    )

                    # Snapshot key runtime signals.
                    snapshots = inc_dir / "snapshots"
                    _safe_copy(issues_registry_src, snapshots / "issues_registry.yaml")
                    if chatgptmcp_state_path.exists():
                        _safe_copy(chatgptmcp_state_path, snapshots / "chatgptmcp_blocked_state.json")
                    elif legacy_blocked_path.exists():
                        _safe_copy(legacy_blocked_path, snapshots / "chatgptmcp_blocked_state.json")

                    day_local = datetime.now(UTC).strftime("%Y%m%d")
                    p = mihomo_delay_dir / f"mihomo_delay_{day_local}.jsonl"
                    last_mh = _tail_last_jsonl(p)
                    if last_mh is not None:
                        atomic_write_json(snapshots / "mihomo_delay_last.json", {"path": str(p), "record": last_mh})

                    prov_tools = provider_tools(provider)
                    provider_cdp_url = _provider_cdp_url(provider=provider, args=args)
                    provider_chrome_start = _provider_chrome_start_script(provider=provider, driver_root=chatgptmcp_root)
                    cdp = http_json(provider_cdp_url.rstrip("/") + "/json/version", timeout_seconds=5.0)
                    atomic_write_json(
                        snapshots / "cdp_version.json",
                        {"provider": provider, "cdp_url": provider_cdp_url, "result": cdp},
                    )

                    # Optional: safe remediation hooks (no prompt sending).
                    if mcp_client is not None:
                        try:
                            if bool(args.enable_chatgptmcp_evidence):
                                out_dir = snapshots / f"{provider}_mcp"
                                out_dir.mkdir(parents=True, exist_ok=True)
                                blocked_status_tool = prov_tools.get("blocked_status")
                                if blocked_status_tool and not (out_dir / "blocked_status.json").exists():
                                    atomic_write_json(
                                        out_dir / "blocked_status.json",
                                        _chatgptmcp_call(mcp_client, tool_name=blocked_status_tool, tool_args={}, timeout_seconds=20),
                                    )
                                rate_limit_tool = prov_tools.get("rate_limit_status")
                                if rate_limit_tool and not (out_dir / "rate_limit_status.json").exists():
                                    atomic_write_json(
                                        out_dir / "rate_limit_status.json",
                                        _chatgptmcp_call(mcp_client, tool_name=rate_limit_tool, tool_args={}, timeout_seconds=20),
                                    )
                                self_check_tool = prov_tools.get("self_check")
                                if self_check_tool and not (out_dir / "self_check.json").exists():
                                    self_check_args: dict[str, Any] = {"timeout_seconds": 60}
                                    if conversation_url:
                                        self_check_args["conversation_url"] = conversation_url
                                    atomic_write_json(
                                        out_dir / "self_check.json",
                                        _chatgptmcp_call(mcp_client, tool_name=self_check_tool, tool_args=self_check_args, timeout_seconds=75),
                                    )
                                tab_stats_tool = prov_tools.get("tab_stats")
                                if tab_stats_tool and not (out_dir / "tab_stats.json").exists():
                                    atomic_write_json(
                                        out_dir / "tab_stats.json",
                                        _chatgptmcp_call(mcp_client, tool_name=tab_stats_tool, tool_args={}, timeout_seconds=20),
                                    )

                            if bool(args.enable_chatgptmcp_capture_ui):
                                out_dir = snapshots / f"{provider}_mcp"
                                out_dir.mkdir(parents=True, exist_ok=True)
                                capture_ui_tool = prov_tools.get("capture_ui")
                                if capture_ui_tool and not (out_dir / "capture_ui.json").exists():
                                    capture_args: dict[str, Any] = {"mode": "basic"}
                                    if conversation_url:
                                        capture_args["conversation_url"] = conversation_url
                                    atomic_write_json(
                                        out_dir / "capture_ui.json",
                                        _chatgptmcp_call(mcp_client, tool_name=capture_ui_tool, tool_args=capture_args, timeout_seconds=120),
                                    )
                        except Exception:
                            pass

                    if bool(args.enable_chrome_autostart):
                        try:
                            cdp_ok = bool(cdp.get("Browser") or cdp.get("webSocketDebuggerUrl"))
                        except Exception:
                            cdp_ok = False
                        if not cdp_ok:
                            chrome_start = provider_chrome_start
                            if chrome_start.exists():
                                started_at = time.time()
                                ok, out = run_cmd(["bash", str(chrome_start)], cwd=chatgptmcp_root, timeout_seconds=90)
                                _record_action(
                                    inc_dir,
                                    action="chrome_autostart",
                                    ok=ok,
                                    error=(None if ok else out),
                                    elapsed_ms=int((time.time() - started_at) * 1000),
                                    details={"provider": provider, "cmd": str(chrome_start)},
                                )
                                incident_db.create_action(
                                    conn,
                                    incident_id=incident.incident_id,
                                    action_type="chrome_autostart",
                                    status=(
                                        incident_db.ACTION_STATUS_COMPLETED
                                        if ok
                                        else incident_db.ACTION_STATUS_FAILED
                                    ),
                                    risk_level="low",
                                    result={
                                        "ok": bool(ok),
                                        "provider": provider,
                                        "cmd": str(chrome_start),
                                        "output": out,
                                    },
                                )

                    # Infra healer: if jobs are failing due to CDP/TargetClosed issues, try a guarded restart.
                    if bool(args.enable_infra_healer) and looks_like_infra_job_error(
                        error_type=str(r["last_error_type"] or ""), error=str(r["last_error"] or "")
                    ):
                        try:
                            window_seconds = float(max(1, int(args.infra_healer_window_seconds)))
                            recent_runs = incident_db.count_actions(
                                conn,
                                action_type="infra_heal_restart_driver",
                                since_ts=(now - window_seconds),
                            )
                            last_run_ts = incident_db.last_action_ts(conn, action_type="infra_heal_restart_driver")
                            min_interval = float(max(0, int(args.infra_healer_min_interval_seconds)))

                            if last_run_ts is not None and min_interval > 0 and (now - float(last_run_ts)) < min_interval:
                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "infra_heal_skipped_min_interval",
                                        "incident_id": incident.incident_id,
                                        "sig_hash": incident.sig_hash,
                                        "seconds_since_last": round(float(now - float(last_run_ts)), 3),
                                        "min_interval_seconds": int(min_interval),
                                    },
                                )
                            elif int(recent_runs) >= int(args.infra_healer_max_per_window):
                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "infra_heal_rate_limited",
                                        "incident_id": incident.incident_id,
                                        "sig_hash": incident.sig_hash,
                                        "window_seconds": int(window_seconds),
                                        "max_per_window": int(args.infra_healer_max_per_window),
                                        "recent_runs": int(recent_runs),
                                    },
                                )
                            else:
                                active = _active_send_jobs(db_path=db_path, include_queued=False)
                                driver_host_port = _parse_host_port_from_url(str(args.chatgpt_mcp_url), default_port=18701)
                                driver_listening = (
                                    port_open(driver_host_port[0], driver_host_port[1]) if driver_host_port else False
                                )
                                try:
                                    cdp_ok_probe = bool(cdp.get("Browser") or cdp.get("webSocketDebuggerUrl"))
                                except Exception:
                                    cdp_ok_probe = False

                                skip_restart = False
                                if not bool(active.get("ok")):
                                    skip_restart = True
                                    _record_action(
                                        inc_dir,
                                        action="infra_heal_guard_error",
                                        ok=False,
                                        error=str(active.get("error") or "active send guard failed"),
                                        details=active,
                                    )
                                elif int(active.get("count") or 0) > 0:
                                    # Guardrail: avoid restarts while a send-stage prompt is likely in-flight.
                                    # However, if the driver/CDP is already down, any "active" send jobs are not making
                                    # forward progress. In that case, allow infra-heal to recover the system without
                                    # requiring client intervention.
                                    allow = False
                                    reason = ""
                                    if not driver_listening:
                                        allow = True
                                        reason = "driver_down"
                                    elif not cdp_ok_probe:
                                        allow = True
                                        reason = "cdp_down"

                                    if not allow:
                                        skip_restart = True
                                        _record_action(
                                            inc_dir,
                                            action="infra_heal_deferred_active_send",
                                            ok=False,
                                            error="active send jobs present; deferring restart",
                                            details={
                                                **active,
                                                "driver_listening": bool(driver_listening),
                                                "cdp_ok": bool(cdp_ok_probe),
                                            },
                                        )
                                    else:
                                        _record_action(
                                            inc_dir,
                                            action="infra_heal_override_active_send",
                                            ok=True,
                                            details={
                                                **active,
                                                "driver_listening": bool(driver_listening),
                                                "cdp_ok": bool(cdp_ok_probe),
                                                "override_reason": reason,
                                            },
                                        )

                                if not skip_restart:
                                    # If CDP is down, try starting Chrome first (idempotent helper).
                                    try:
                                        cdp_ok = bool(cdp.get("Browser") or cdp.get("webSocketDebuggerUrl"))
                                    except Exception:
                                        cdp_ok = False
                                    if not cdp_ok:
                                        chrome_start = provider_chrome_start
                                        if chrome_start.exists():
                                            started_at = time.time()
                                            ok, out = run_cmd(["bash", str(chrome_start)], cwd=chatgptmcp_root, timeout_seconds=90)
                                            _record_action(
                                                inc_dir,
                                                action="infra_heal_chrome_start",
                                                ok=ok,
                                                error=(None if ok else out),
                                                elapsed_ms=int((time.time() - started_at) * 1000),
                                                details={"provider": provider, "cmd": str(chrome_start)},
                                            )
                                            incident_db.create_action(
                                                conn,
                                                incident_id=incident.incident_id,
                                                action_type="infra_heal_chrome_start",
                                                status=(
                                                    incident_db.ACTION_STATUS_COMPLETED
                                                    if ok
                                                    else incident_db.ACTION_STATUS_FAILED
                                                ),
                                                risk_level="low",
                                                result={"ok": bool(ok), "provider": provider, "cmd": str(chrome_start), "output": out},
                                            )

                                    started_at = time.time()
                                    ok, details = _restart_driver_autofix(
                                        driver_root=chatgptmcp_root,
                                        driver_url=str(args.chatgpt_mcp_url),
                                        cdp_url=provider_cdp_url,
                                        log_file=inc_dir / "snapshots" / "infra_heal" / "driver_restart.log",
                                        mcp_client=mcp_client,
                                        self_check_tool=prov_tools.get("self_check"),
                                        conversation_url=conversation_url,
                                    )
                                    _record_action(
                                        inc_dir,
                                        action="infra_heal_restart_driver",
                                        ok=ok,
                                        error=(None if ok else str(details.get("error") or "restart_driver failed")),
                                        elapsed_ms=int((time.time() - started_at) * 1000),
                                        details=details,
                                    )
                                    incident_db.create_action(
                                        conn,
                                        incident_id=incident.incident_id,
                                        action_type="infra_heal_restart_driver",
                                        status=(
                                            incident_db.ACTION_STATUS_COMPLETED
                                            if ok
                                            else incident_db.ACTION_STATUS_FAILED
                                        ),
                                        risk_level="low",
                                        result={"ok": bool(ok), "details": details},
                                        error=(None if ok else str(details.get("error") or "restart_driver failed")),
                                    )
                        except Exception as exc:
                            _append_jsonl(
                                log_path,
                                {
                                    "ts": now_iso(),
                                    "type": "infra_heal_error",
                                    "incident_id": incident.incident_id,
                                    "sig_hash": incident.sig_hash,
                                    "error_type": type(exc).__name__,
                                    "error": str(exc)[:800],
                                },
                            )

                    # Copy job artifacts into the incident pack.
                    job_pack_dir = inc_dir / "jobs" / job_id
                    job_pack_dir.mkdir(parents=True, exist_ok=True)
                    result_payload = _copy_incident_job_artifacts(
                        artifacts_dir=artifacts_dir,
                        job_id=job_id,
                        job_pack_dir=job_pack_dir,
                    )

                    # Also snapshot the current DB row for the job.
                    atomic_write_json(
                        job_pack_dir / "job_row.json",
                        _incident_job_row_payload(r, result_payload=result_payload),
                    )

                    # P0 (optional): submit a read-only repair.check job per incident and attach its report.
                    if bool(args.enable_auto_repair_check) and (not kind.startswith("repair.")):
                        window_seconds = float(max(1, int(args.auto_repair_check_window_seconds)))
                        recent_submissions = incident_db.count_actions(
                            conn,
                            action_type="submit_repair_check",
                            since_ts=(now - window_seconds),
                        )
                        if incident.repair_job_id is None:
                            if int(recent_submissions) >= int(args.auto_repair_check_max_per_window):
                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "auto_repair_rate_limited",
                                        "incident_id": incident.incident_id,
                                        "sig_hash": incident.sig_hash,
                                        "window_seconds": int(window_seconds),
                                        "max_per_window": int(args.auto_repair_check_max_per_window),
                                        "recent_submissions": int(recent_submissions),
                                    },
                                )
                            else:
                                try:
                                    conn.execute("BEGIN IMMEDIATE")
                                    repair_job_id = _ensure_repair_check_job(
                                        conn=conn,
                                        artifacts_dir=artifacts_dir,
                                        incident=incident,
                                        target_job_id=job_id,
                                        signature=signature,
                                        conversation_url=(str(r["conversation_url"] or "").strip() or None),
                                        timeout_seconds=int(args.auto_repair_check_timeout_seconds),
                                        mode=str(args.auto_repair_check_mode),
                                        probe_driver=bool(args.auto_repair_check_probe_driver),
                                        recent_failures=int(args.auto_repair_check_recent_failures),
                                    )
                                    conn.commit()
                                    if not str(repair_job_id or "").strip():
                                        _append_jsonl(
                                            log_path,
                                            {
                                                "ts": now_iso(),
                                                "type": "auto_repair_skipped_synthetic_source",
                                                "incident_id": incident.incident_id,
                                                "sig_hash": incident.sig_hash,
                                                "target_job_id": str(job_id),
                                            },
                                        )
                                        continue
                                    incident.repair_job_id = repair_job_id
                                    manifest["repair_job_id"] = repair_job_id
                                    _write_manifest(inc_dir / "manifest.json", manifest)
                                    _upsert_incident_db(
                                        conn,
                                        incident=incident,
                                        category="job",
                                        severity=str(args.incident_severity_default),
                                        status="open",
                                        evidence_dir=inc_dir,
                                    )
                                    incident_db.create_action(
                                        conn,
                                        incident_id=incident.incident_id,
                                        action_type="submit_repair_check",
                                        status=incident_db.ACTION_STATUS_COMPLETED,
                                        risk_level="low",
                                        result={
                                            "repair_job_id": str(repair_job_id),
                                            "target_job_id": str(job_id),
                                            "mode": str(args.auto_repair_check_mode),
                                        },
                                    )
                                    _append_jsonl(
                                        log_path,
                                        {
                                            "ts": now_iso(),
                                            "type": "auto_repair_submitted",
                                            "incident_id": incident.incident_id,
                                            "sig_hash": incident.sig_hash,
                                            "repair_job_id": repair_job_id,
                                            "target_job_id": job_id,
                                        },
                                    )
                                except Exception as exc:
                                    try:
                                        conn.rollback()
                                    except Exception:
                                        pass
                                    _append_jsonl(
                                        log_path,
                                        {
                                            "ts": now_iso(),
                                            "type": "auto_repair_submit_error",
                                            "incident_id": incident.incident_id,
                                            "sig_hash": incident.sig_hash,
                                            "error_type": type(exc).__name__,
                                            "error": str(exc)[:800],
                                        },
                                    )

                        # Harvest the repair report once it exists (best-effort).
                        if incident.repair_job_id:
                            try:
                                row2 = conn.execute(
                                    "SELECT status FROM jobs WHERE job_id = ?",
                                    (str(incident.repair_job_id),),
                                ).fetchone()
                                if row2 is not None and str(row2["status"] or "") == "completed":
                                    _attach_repair_artifacts(
                                        artifacts_dir=artifacts_dir,
                                        inc_dir=inc_dir,
                                        repair_job_id=str(incident.repair_job_id),
                                        log_path=log_path,
                                        incident_id=incident.incident_id,
                                    )
                            except Exception:
                                pass

                    codex_run_meta: dict[str, Any] | None = None
                    codex_autofix_summary: dict[str, Any] | None = None

                    # P0 (optional): Codex SRE analysis (read-only) + optional autofix (whitelisted).
                    if bool(args.enable_codex_sre_analyze) and (not kind.startswith("repair.")):
                        input_hash = _codex_input_fingerprint(inc_dir)
                        min_interval = max(30, int(args.codex_sre_min_interval_seconds))
                        max_per_incident = max(0, int(args.codex_sre_max_per_incident))
                        should_run_codex = False

                        if max_per_incident > 0 and int(incident.codex_run_count) >= max_per_incident:
                            _append_jsonl(
                                log_path,
                                {
                                    "ts": now_iso(),
                                    "type": "codex_sre_incident_run_capped",
                                    "incident_id": incident.incident_id,
                                    "sig_hash": incident.sig_hash,
                                    "run_count": int(incident.codex_run_count),
                                    "max_per_incident": int(max_per_incident),
                                },
                            )
                        else:
                            if incident.codex_last_run_ts is None:
                                should_run_codex = True
                            else:
                                age = float(now) - float(incident.codex_last_run_ts or 0.0)
                                if age >= float(min_interval):
                                    if incident.codex_last_ok is not True:
                                        should_run_codex = True
                                    elif incident.codex_input_hash != input_hash:
                                        should_run_codex = True

                        if should_run_codex:
                            window_seconds = float(max(1, int(args.codex_sre_window_seconds)))
                            recent_submissions = incident_db.count_actions(
                                conn,
                                action_type="codex_sre_analyze",
                                since_ts=(now - window_seconds),
                            )
                            if int(recent_submissions) >= int(args.codex_sre_max_per_window):
                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "codex_sre_rate_limited",
                                        "incident_id": incident.incident_id,
                                        "sig_hash": incident.sig_hash,
                                        "window_seconds": int(window_seconds),
                                        "max_per_window": int(args.codex_sre_max_per_window),
                                        "recent_submissions": int(recent_submissions),
                                    },
                                )
                            else:
                                global_mem_snapshot = None
                                if bool(args.enable_codex_global_memory):
                                    global_mem_snapshot = _snapshot_codex_global_memory_md(
                                        global_md=codex_global_memory_md,
                                        inc_dir=inc_dir,
                                        max_chars=int(args.codex_global_memory_prompt_max_chars),
                                    )

                                run_meta = _run_codex_sre_analyze_incident(
                                    repo_root=repo_root,
                                    inc_dir=inc_dir,
                                    db_path=db_path,
                                    artifacts_dir=artifacts_dir,
                                    model=str(args.codex_sre_model),
                                    timeout_seconds=int(args.codex_sre_timeout_seconds),
                                    global_memory_md=global_mem_snapshot,
                                    global_memory_jsonl=codex_global_memory_jsonl,
                                    target_job_id=str(job_id),
                                )
                                codex_run_meta = run_meta

                                _maybe_update_codex_global_memory_after_run(
                                    enabled=bool(args.enable_codex_global_memory),
                                    trigger="incident_scan",
                                    inc_dir=inc_dir,
                                    incident_id=incident.incident_id,
                                    sig_hash=incident.sig_hash,
                                    signature=str(incident.signature),
                                    provider=provider,
                                    run_meta=run_meta,
                                    jsonl_path=codex_global_memory_jsonl,
                                    md_path=codex_global_memory_md,
                                    digest_max_records=int(args.codex_global_memory_digest_max_records),
                                    max_bytes=int(args.codex_global_memory_max_bytes),
                                    log_path=log_path,
                                )
                                incident.codex_input_hash = input_hash
                                incident.codex_last_run_ts = float(now)
                                incident.codex_run_count = int(incident.codex_run_count) + 1
                                incident.codex_last_ok = bool(run_meta.get("ok"))
                                incident.codex_last_error = (str(run_meta.get("error") or "").strip() or None)

                                manifest["codex_input_hash"] = incident.codex_input_hash
                                manifest["codex_last_run_ts"] = incident.codex_last_run_ts
                                manifest["codex_run_count"] = int(incident.codex_run_count)
                                manifest["codex_last_ok"] = incident.codex_last_ok
                                manifest["codex_last_error"] = incident.codex_last_error
                                _write_manifest(inc_dir / "manifest.json", manifest)
                                _upsert_incident_db(
                                    conn,
                                    incident=incident,
                                    category="job",
                                    severity=str(args.incident_severity_default),
                                    status="open",
                                    evidence_dir=inc_dir,
                                )
                                incident_db.create_action(
                                    conn,
                                    incident_id=incident.incident_id,
                                    action_type="codex_sre_analyze",
                                    status=(
                                        incident_db.ACTION_STATUS_COMPLETED
                                        if bool(run_meta.get("ok"))
                                        else incident_db.ACTION_STATUS_FAILED
                                    ),
                                    risk_level="low",
                                    result={
                                        "ok": bool(run_meta.get("ok")),
                                        "elapsed_ms": run_meta.get("elapsed_ms"),
                                        "input_hash": run_meta.get("input_hash"),
                                        "model": run_meta.get("model"),
                                        "actions_json": run_meta.get("actions_json"),
                                        "actions_md": run_meta.get("actions_md"),
                                        "error": run_meta.get("error"),
                                    },
                                )

                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "codex_sre_analyzed",
                                        "incident_id": incident.incident_id,
                                        "sig_hash": incident.sig_hash,
                                        "ok": bool(run_meta.get("ok")),
                                        "elapsed_ms": run_meta.get("elapsed_ms"),
                                        "input_hash": run_meta.get("input_hash"),
                                        "model": run_meta.get("model"),
                                        "actions_json": run_meta.get("actions_json"),
                                        "actions_md": run_meta.get("actions_md"),
                                        "error": run_meta.get("error"),
                                    },
                                )

                        # Optional: execute whitelisted low-risk actions from the latest codex report.
                        if bool(args.enable_codex_sre_autofix):
                            actions_json = inc_dir / "codex" / "sre_actions.json"
                            if incident.codex_autofix_run_count >= int(args.codex_sre_autofix_max_per_incident):
                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "codex_autofix_incident_run_capped",
                                        "incident_id": incident.incident_id,
                                        "sig_hash": incident.sig_hash,
                                        "run_count": int(incident.codex_autofix_run_count),
                                        "max_per_incident": int(args.codex_sre_autofix_max_per_incident),
                                    },
                                )
                            elif not actions_json.exists():
                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "codex_autofix_skipped",
                                        "incident_id": incident.incident_id,
                                        "sig_hash": incident.sig_hash,
                                        "reason": "missing codex/sre_actions.json",
                                    },
                                )
                            elif not codex_autofix_allowed:
                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "codex_autofix_skipped",
                                        "incident_id": incident.incident_id,
                                        "sig_hash": incident.sig_hash,
                                        "reason": "allowlist empty",
                                    },
                                )
                            else:
                                window_seconds = float(max(1, int(args.codex_sre_autofix_window_seconds)))
                                recent_runs = incident_db.count_actions(
                                    conn,
                                    action_type="codex_sre_autofix",
                                    since_ts=(now - window_seconds),
                                )
                                if int(recent_runs) >= int(args.codex_sre_autofix_max_per_window):
                                    _append_jsonl(
                                        log_path,
                                        {
                                            "ts": now_iso(),
                                            "type": "codex_autofix_rate_limited",
                                            "incident_id": incident.incident_id,
                                            "sig_hash": incident.sig_hash,
                                            "window_seconds": int(window_seconds),
                                            "max_per_window": int(args.codex_sre_autofix_max_per_window),
                                            "recent_runs": int(recent_runs),
                                        },
                                    )
                                else:
                                    routed = _route_incident_runtime_fix_via_controller(
                                        inc_dir=inc_dir,
                                        db_path=db_path,
                                        artifacts_dir=artifacts_dir,
                                        target_job_id=str(job_id),
                                        signature=signature,
                                        global_memory_md=global_mem_snapshot,
                                        global_memory_jsonl=codex_global_memory_jsonl,
                                        model=str(args.codex_sre_model or "").strip() or None,
                                    )
                                    if not bool(routed.get("ok")):
                                        _append_jsonl(
                                            log_path,
                                            {
                                                "ts": now_iso(),
                                                "type": "codex_autofix_error",
                                                "incident_id": incident.incident_id,
                                                "sig_hash": incident.sig_hash,
                                                "error_type": "RuntimeError",
                                                "error": str(routed.get("reason") or "controller_runtime_fix_route_failed"),
                                            },
                                        )
                                    else:
                                        summary = {
                                            "ok": True,
                                            "lane_id": routed.get("lane_id"),
                                            "repair_job_id": ((routed.get("downstream") or {}).get("job_id") if isinstance(routed.get("downstream"), dict) else None),
                                            "controller_phase": routed.get("controller_phase"),
                                            "report_path": routed.get("report_path"),
                                            "decision_path": routed.get("decision_path"),
                                            "pointer_path": routed.get("pointer_path"),
                                        }
                                        codex_autofix_summary = summary
                                        incident.codex_autofix_last_ts = float(now)
                                        incident.codex_autofix_run_count = int(incident.codex_autofix_run_count) + 1

                                        manifest["codex_autofix_last_ts"] = incident.codex_autofix_last_ts
                                        manifest["codex_autofix_run_count"] = int(incident.codex_autofix_run_count)
                                        manifest["repair_autofix_job_id"] = str(summary.get("repair_job_id") or "").strip() or manifest.get("repair_autofix_job_id")
                                        manifest["source_lane_id"] = str(summary.get("lane_id") or "").strip() or manifest.get("source_lane_id")
                                        _write_manifest(inc_dir / "manifest.json", manifest)
                                        _upsert_incident_db(
                                            conn,
                                            incident=incident,
                                            category="job",
                                            severity=str(args.incident_severity_default),
                                            status="open",
                                            evidence_dir=inc_dir,
                                        )
                                        incident_db.create_action(
                                            conn,
                                            incident_id=incident.incident_id,
                                            action_type="codex_sre_autofix",
                                            status=(
                                                incident_db.ACTION_STATUS_COMPLETED
                                                if bool(summary.get("ok"))
                                                else incident_db.ACTION_STATUS_FAILED
                                            ),
                                            risk_level=str(codex_autofix_max_risk),
                                            result=summary,
                                        )

                                        _append_jsonl(
                                            log_path,
                                            {
                                                "ts": now_iso(),
                                                "type": "codex_autofix_routed",
                                                "incident_id": incident.incident_id,
                                                "sig_hash": incident.sig_hash,
                                                "summary": summary,
                                            },
                                        )

                    # Fallback path: if Codex SRE failed, delegate recovery to repair.autofix
                    # (it is itself Codex-backed with guarded actions + evidence report).
                    if bool(args.enable_codex_maint_fallback) and (not kind.startswith("repair.")):
                        fallback_trigger = ""
                        if isinstance(codex_run_meta, dict) and (not bool(codex_run_meta.get("ok"))):
                            fallback_trigger = "codex_sre_failed"
                        elif isinstance(codex_autofix_summary, dict) and (not bool(codex_autofix_summary.get("ok"))):
                            fallback_trigger = "codex_sre_autofix_failed"

                        fallback_job_id = str(manifest.get("repair_autofix_job_id") or "").strip() or None
                        if fallback_trigger:
                            max_per_incident = max(0, int(args.codex_maint_fallback_max_per_incident))
                            per_incident_runs = incident_db.count_actions(
                                conn,
                                action_type="submit_repair_autofix",
                                since_ts=0.0,
                                incident_id=incident.incident_id,
                            )
                            if max_per_incident > 0 and int(per_incident_runs) >= max_per_incident:
                                _append_jsonl(
                                    log_path,
                                    {
                                        "ts": now_iso(),
                                        "type": "codex_maint_fallback_incident_capped",
                                        "incident_id": incident.incident_id,
                                        "sig_hash": incident.sig_hash,
                                        "run_count": int(per_incident_runs),
                                        "max_per_incident": int(max_per_incident),
                                        "trigger": fallback_trigger,
                                    },
                                )
                            else:
                                window_seconds = float(max(1, int(args.codex_maint_fallback_window_seconds)))
                                recent_submissions = incident_db.count_actions(
                                    conn,
                                    action_type="submit_repair_autofix",
                                    since_ts=(now - window_seconds),
                                )
                                if int(recent_submissions) >= int(args.codex_maint_fallback_max_per_window):
                                    _append_jsonl(
                                        log_path,
                                        {
                                            "ts": now_iso(),
                                            "type": "codex_maint_fallback_rate_limited",
                                            "incident_id": incident.incident_id,
                                            "sig_hash": incident.sig_hash,
                                            "window_seconds": int(window_seconds),
                                            "max_per_window": int(args.codex_maint_fallback_max_per_window),
                                            "recent_submissions": int(recent_submissions),
                                            "trigger": fallback_trigger,
                                        },
                                    )
                                else:
                                    try:
                                        controller_fallback = _route_repair_autofix_fallback_via_controller(
                                            inc_dir=inc_dir,
                                            db_path=db_path,
                                            artifacts_dir=artifacts_dir,
                                            target_job_id=str(job_id),
                                            signature=signature,
                                            timeout_seconds=int(args.codex_maint_fallback_timeout_seconds),
                                            allow_actions=str(codex_maint_fallback_allow_actions),
                                            max_risk=str(codex_maint_fallback_max_risk),
                                            trigger=fallback_trigger,
                                            global_memory_md=global_mem_snapshot,
                                            global_memory_jsonl=codex_global_memory_jsonl,
                                            model=str(args.codex_model or "").strip() or None,
                                        )
                                        if bool(controller_fallback.get("skipped")):
                                            _append_jsonl(
                                                log_path,
                                                {
                                                    "ts": now_iso(),
                                                    "type": "codex_maint_fallback_skipped_synthetic_source",
                                                    "incident_id": incident.incident_id,
                                                    "sig_hash": incident.sig_hash,
                                                    "target_job_id": str(job_id),
                                                    "trigger": fallback_trigger,
                                                },
                                            )
                                            continue
                                        if not bool(controller_fallback.get("ok")):
                                            _append_jsonl(
                                                log_path,
                                                {
                                                    "ts": now_iso(),
                                                    "type": "codex_maint_fallback_controller_error",
                                                    "incident_id": incident.incident_id,
                                                    "sig_hash": incident.sig_hash,
                                                    "target_job_id": str(job_id),
                                                    "trigger": fallback_trigger,
                                                    "reason": controller_fallback.get("reason"),
                                                    "lane_id": controller_fallback.get("lane_id"),
                                                    "report_path": controller_fallback.get("report_path"),
                                                },
                                            )
                                            continue
                                        downstream = controller_fallback.get("downstream") if isinstance(controller_fallback.get("downstream"), dict) else {}
                                        fallback_job_id = str(downstream.get("job_id") or "").strip()
                                        conn.execute("BEGIN IMMEDIATE")
                                        manifest["repair_autofix_job_id"] = str(fallback_job_id)
                                        manifest["source_lane_id"] = str(controller_fallback.get("lane_id") or "").strip() or None
                                        _write_manifest(inc_dir / "manifest.json", manifest)
                                        _upsert_incident_db(
                                            conn,
                                            incident=incident,
                                            category="job",
                                            severity=str(args.incident_severity_default),
                                            status="open",
                                            evidence_dir=inc_dir,
                                        )
                                        incident_db.create_action(
                                            conn,
                                            incident_id=incident.incident_id,
                                            action_type="submit_repair_autofix",
                                            status=incident_db.ACTION_STATUS_COMPLETED,
                                            risk_level=str(codex_maint_fallback_max_risk),
                                            result={
                                                "repair_job_id": str(fallback_job_id),
                                                "target_job_id": str(job_id),
                                                "trigger": fallback_trigger,
                                                "lane_id": controller_fallback.get("lane_id"),
                                                "controller_phase": controller_fallback.get("controller_phase"),
                                                "report_path": controller_fallback.get("report_path"),
                                                "allow_actions": str(codex_maint_fallback_allow_actions),
                                                "max_risk": str(codex_maint_fallback_max_risk),
                                            },
                                        )
                                        conn.commit()
                                        _append_jsonl(
                                            log_path,
                                            {
                                                "ts": now_iso(),
                                                "type": "codex_maint_fallback_submitted",
                                                "incident_id": incident.incident_id,
                                                "sig_hash": incident.sig_hash,
                                                "repair_job_id": str(fallback_job_id),
                                                "target_job_id": str(job_id),
                                                "lane_id": controller_fallback.get("lane_id"),
                                                "trigger": fallback_trigger,
                                            },
                                        )
                                    except Exception as exc:
                                        try:
                                            conn.rollback()
                                        except Exception:
                                            pass
                                        _append_jsonl(
                                            log_path,
                                            {
                                                "ts": now_iso(),
                                                "type": "codex_maint_fallback_submit_error",
                                                "incident_id": incident.incident_id,
                                                "sig_hash": incident.sig_hash,
                                                "trigger": fallback_trigger,
                                                "error_type": type(exc).__name__,
                                                "error": str(exc)[:800],
                                            },
                                        )

                        # Harvest fallback repair.autofix artifacts once ready.
                        if fallback_job_id:
                            try:
                                row3 = conn.execute(
                                    "SELECT status FROM jobs WHERE job_id = ?",
                                    (str(fallback_job_id),),
                                ).fetchone()
                                if row3 is not None and str(row3["status"] or "") == "completed":
                                    _attach_repair_autofix_artifacts(
                                        artifacts_dir=artifacts_dir,
                                        inc_dir=inc_dir,
                                        repair_job_id=str(fallback_job_id),
                                        log_path=log_path,
                                        incident_id=incident.incident_id,
                                    )
                            except Exception:
                                pass

                last_scan_ts = now
              except Exception as _e:
                _append_jsonl(log_path, {"ts": now_iso(), "type": "subsystem_error", "subsystem": "job_scan", "error_type": type(_e).__name__, "error": str(_e)[:800]})
                last_scan_ts = now  # avoid tight retry loop on persistent errors

            # Persist daemon state.
            try:
                incident_db.save_daemon_state(conn, {"last_event_id": int(last_event_id), "updated_at": float(now)})
            except Exception:
                pass
            pause = get_pause_state(conn)
            atomic_write_json(
                state_path,
                {
                    "last_event_id": last_event_id,
                    "updated_at": now,
                    "issues_registry_sha256": (issues_registry_sha256 or None),
                    "incidents": _dump_incident_state(incidents),
                    "ui_canary_last_ts": float(last_ui_canary_ts),
                    "ui_canary": _dump_ui_canary_state(ui_canary_state),
                    "pause": {
                        "mode": pause.mode,
                        "until_ts": pause.until_ts,
                        "reason": pause.reason,
                    },
                },
            )
        finally:
            conn.close()

    _append_jsonl(log_path, {"ts": now_iso(), "type": "maint_finished"})
    print(str(log_path))
    _stop_watchdog_heartbeat()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


# ── __getattr__ shim for backward-compat split ───────────────────────
# Tests use spec_from_file_location to import us; any name not found here
# is looked up in the extracted submodules so callers keep working.
#
# Phase 1 renamed private functions to public ops_shared imports. Map
# the legacy underscore-prefixed names back to the current module globals
# so old test harnesses still resolve.
_LEGACY_ALIASES: dict[str, str] = {
    "_provider_tools": "provider_tools",
    "_incident_signal_is_fresh": "incident_signal_is_fresh",
    "_incident_should_rollover_for_signal": "incident_should_rollover_for_signal",
    "_incident_freshness_gate": "incident_freshness_gate",
    "_looks_like_infra_job_error": "looks_like_infra_job_error",
    "_normalize_error": "normalize_error",
    "_sig_hash": "sig_hash",
    "_parse_ts_list": "parse_ts_list",
    "_trim_window": "trim_window",
    "_job_expected_max_seconds": "job_expected_max_seconds",
}

def __getattr__(name: str) -> Any:
    # 1. Legacy private-name aliases → current module globals (ops_shared imports).
    canonical = _LEGACY_ALIASES.get(name)
    if canonical is not None:
        g = globals()
        if canonical in g:
            return g[canonical]
    # 2. Sibling submodule fallback.
    for mod in (_maint_util, _maint_codex_memory):
        try:
            return getattr(mod, name)
        except AttributeError:
            continue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
