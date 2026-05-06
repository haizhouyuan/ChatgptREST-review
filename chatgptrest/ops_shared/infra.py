"""Infrastructure probing + management shared between maint daemon and repair executor."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# DB access — deferred import to avoid forcing import chain in daemon scripts.
# ---------------------------------------------------------------------------


def _connect_db(db_path: Path):
    """Lazy import of chatgptrest.core.db.connect."""
    from chatgptrest.core.db import connect  # noqa: WPS433

    return connect(db_path)


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_text(path: Path, *, limit: int = 120_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def truncate_text(value: object, *, limit: int = 800) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if len(s) <= limit:
        return s
    return f"{s[:limit]}…<truncated {len(s) - limit} chars>"


# ---------------------------------------------------------------------------
# HTTP (stdlib-only)
# ---------------------------------------------------------------------------


def http_json(url: str, *, timeout_seconds: float) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            obj = json.loads(text) if text.strip() else {}
            return obj if isinstance(obj, dict) else {"_raw": obj}
    except urllib.error.HTTPError as e:
        raw_err = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": f"http_{e.code}", "error": raw_err[:500]}
    except Exception as exc:
        return {"ok": False, "status": "error", "error_type": type(exc).__name__, "error": str(exc)[:500]}


def _http_request_json(
    url: str,
    *,
    method: str,
    timeout_seconds: float,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=str(method or "GET").upper(), headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            obj = json.loads(text) if text.strip() else {}
            return obj if isinstance(obj, dict) else {"ok": True, "_raw": obj}
    except urllib.error.HTTPError as e:
        raw_err = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": f"http_{e.code}", "error": raw_err[:500]}
    except Exception as exc:
        return {"ok": False, "status": "error", "error_type": type(exc).__name__, "error": str(exc)[:500]}


def mihomo_controller_url() -> str:
    raw = (os.environ.get("MIHOMO_CONTROLLER_URL") or "").strip()
    return raw or "http://127.0.0.1:9090"


def mihomo_get_proxy(group: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    group_name = str(group or "").strip()
    if not group_name:
        return {"ok": False, "error_type": "ValueError", "error": "empty proxy group"}
    url = f"{mihomo_controller_url().rstrip('/')}/proxies/{urllib.parse.quote(group_name, safe='')}"
    obj = _http_request_json(url, method="GET", timeout_seconds=timeout_seconds)
    if not isinstance(obj, dict):
        return {"ok": False, "error_type": "TypeError", "error": "invalid mihomo proxy response"}
    out = {
        "ok": bool(obj.get("ok", True)),
        "group": group_name,
        "controller_url": mihomo_controller_url(),
        "name": str(obj.get("name") or group_name),
        "type": str(obj.get("type") or ""),
        "now": str(obj.get("now") or ""),
        "all": ([str(x) for x in obj.get("all", []) if str(x or "").strip()] if isinstance(obj.get("all"), list) else []),
    }
    if obj.get("ok") is False:
        out["status"] = obj.get("status")
        out["error_type"] = obj.get("error_type")
        out["error"] = obj.get("error")
    return out


def mihomo_set_proxy(group: str, name: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    group_name = str(group or "").strip()
    node_name = str(name or "").strip()
    if not group_name or not node_name:
        return {"ok": False, "error_type": "ValueError", "error": "empty proxy group or node name"}
    url = f"{mihomo_controller_url().rstrip('/')}/proxies/{urllib.parse.quote(group_name, safe='')}"
    obj = _http_request_json(url, method="PUT", timeout_seconds=timeout_seconds, payload={"name": node_name})
    out = {
        "ok": bool(obj.get("ok", True)),
        "group": group_name,
        "name": node_name,
        "controller_url": mihomo_controller_url(),
    }
    if obj.get("ok") is False:
        out["status"] = obj.get("status")
        out["error_type"] = obj.get("error_type")
        out["error"] = obj.get("error")
    return out


def mihomo_find_connections(*, host_substring: str, timeout_seconds: float = 5.0, limit: int = 5) -> dict[str, Any]:
    needle = str(host_substring or "").strip().lower()
    if not needle:
        return {"ok": False, "error_type": "ValueError", "error": "empty host_substring"}
    url = f"{mihomo_controller_url().rstrip('/')}/connections"
    obj = _http_request_json(url, method="GET", timeout_seconds=timeout_seconds)
    if not isinstance(obj, dict):
        return {"ok": False, "error_type": "TypeError", "error": "invalid mihomo connections response"}
    if obj.get("ok") is False:
        return obj
    rows = obj.get("connections")
    if not isinstance(rows, list):
        return {"ok": False, "error_type": "TypeError", "error": "mihomo connections payload missing list"}
    matches: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        host = str(item.get("metadata", {}).get("host") if isinstance(item.get("metadata"), dict) else item.get("host") or "").strip()
        rule_payload = str(item.get("rulePayload") or "").strip()
        haystack = " ".join((host, rule_payload)).lower()
        if needle not in haystack:
            continue
        matches.append(
            {
                "id": str(item.get("id") or ""),
                "host": host,
                "rule": str(item.get("rule") or ""),
                "rulePayload": rule_payload,
                "chains": ([str(x) for x in item.get("chains", []) if str(x or "").strip()] if isinstance(item.get("chains"), list) else []),
            }
        )
        if len(matches) >= max(1, int(limit)):
            break
    return {
        "ok": True,
        "controller_url": mihomo_controller_url(),
        "host_substring": needle,
        "matches": matches,
        "count": len(matches),
    }


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def parse_host_port_from_url(url: str, *, default_port: int) -> tuple[str, int] | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return None
    host = (parsed.hostname or "").strip()
    if not host:
        return None
    port = int(parsed.port or default_port)
    return host, port


def conversation_platform(url: str | None) -> str | None:
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


# ---------------------------------------------------------------------------
# TCP / process probing
# ---------------------------------------------------------------------------


def port_open(host: str, port: int, *, timeout_seconds: float = 0.2) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(float(timeout_seconds))
    try:
        return sock.connect_ex((str(host), int(port))) == 0
    except Exception:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def run_cmd(args: list[str], *, cwd: Path | None = None, timeout_seconds: float = 60.0) -> tuple[bool, str]:
    try:
        p = subprocess.run(
            list(args),
            cwd=(str(cwd) if cwd is not None else None),
            check=False,
            capture_output=True,
            text=True,
            timeout=float(timeout_seconds),
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    out = (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")
    out = out.strip()
    if len(out) > 4000:
        out = out[:2000] + "\n…<truncated>…\n" + out[-2000:]
    return p.returncode == 0, out


def systemd_unit_load_state(unit: str, *, cwd: Path | None = None) -> str | None:
    ok, out = run_cmd(
        ["systemctl", "--user", "show", str(unit), "--property=LoadState", "--value"],
        cwd=cwd,
        timeout_seconds=10.0,
    )
    if not ok:
        return None
    state = str((out or "").splitlines()[-1] if out else "").strip().lower()
    return state or None


# ---------------------------------------------------------------------------
# Job DB queries
# ---------------------------------------------------------------------------


def active_send_jobs(*, db_path: Path, limit: int = 5, exclude_kind_prefixes: tuple[str, ...] = ("repair.",)) -> dict[str, Any]:
    where_kind: list[str] = []
    params: list[Any] = []
    for p in exclude_kind_prefixes:
        where_kind.append("kind NOT LIKE ?")
        params.append(f"{str(p).strip()}%")
    where_kind_sql = " AND ".join(where_kind) if where_kind else "1=1"
    try:
        with _connect_db(db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT job_id, kind, status, phase, updated_at
                FROM jobs
                WHERE status = 'in_progress'
                  AND phase = 'send'
                  AND {where_kind_sql}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                tuple(params + [int(limit)]),
            ).fetchall()
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:800]}

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
