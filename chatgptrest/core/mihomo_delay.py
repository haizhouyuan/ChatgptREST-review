from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:  # pragma: no cover - platform dependent
    import fcntl  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - platform dependent
    fcntl = None


def _env(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return raw.strip() if raw is not None and raw.strip() else default


def _auth_header() -> Optional[str]:
    raw = os.environ.get("MIHOMO_AUTHORIZATION")
    if raw and raw.strip():
        return raw.strip()
    secret = os.environ.get("MIHOMO_SECRET")
    if secret and secret.strip():
        return f"Bearer {secret.strip()}"
    return None


def _urlopen_json(url: str, *, headers: Dict[str, str], timeout_sec: float) -> Any:
    req = urllib.request.Request(url, headers=headers, method="GET")
    # Always bypass env proxy vars for local controller access.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=float(timeout_sec)) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8", errors="replace") or "{}")


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as f:
        if fcntl is not None:  # pragma: no cover - platform dependent
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except Exception:
                pass
        f.write(line)
        f.flush()
        if fcntl is not None:  # pragma: no cover - platform dependent
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass


def parse_groups(raw: str) -> list[str]:
    parts = [p.strip() for p in (raw or "").split(",")]
    return [p for p in parts if p]


def parse_targets(raw: str) -> dict[str, str]:
    """
    Parse group-specific delay targets.

    Format: "GroupA=https://...,GroupB=https://...".
    """
    out: dict[str, str] = {}
    parts = [p.strip() for p in (raw or "").split(",")]
    for part in parts:
        if not part:
            continue
        if "=" not in part:
            continue
        group, url = part.split("=", 1)
        g = group.strip()
        u = url.strip()
        if not g or not u:
            continue
        out[g] = u
    return out


def resolve_log_dir(*, artifacts_dir: Path) -> Path:
    raw = os.environ.get("MIHOMO_DELAY_LOG_DIR")
    if raw and raw.strip():
        return Path(raw.strip()).expanduser()
    return artifacts_dir / "monitor" / "mihomo_delay"


def daily_log_path(*, artifacts_dir: Path, when_ts: float | None = None) -> Path:
    when_ts = float(when_ts or time.time())
    day = time.strftime("%Y%m%d", time.localtime(when_ts))
    return resolve_log_dir(artifacts_dir=artifacts_dir) / f"mihomo_delay_{day}.jsonl"


@dataclass(frozen=True)
class MihomoDelayConfig:
    controller: str
    groups: list[str]
    url: str
    timeout_ms: int
    group_urls: dict[str, str] = field(default_factory=dict)


def load_mihomo_delay_config() -> MihomoDelayConfig:
    controller = _env("MIHOMO_CONTROLLER_URL", "http://127.0.0.1:9090").rstrip("/")

    raw_targets = os.environ.get("MIHOMO_DELAY_TARGETS")
    raw_groups = os.environ.get("MIHOMO_GROUPS")
    if raw_targets is not None and raw_targets.strip():
        group_urls = parse_targets(raw_targets)
        groups = list(group_urls.keys())
    elif raw_groups is not None and raw_groups.strip():
        group_urls = {}
        groups = parse_groups(raw_groups)
    else:
        # Default: track business paths rather than generic gstatic.
        group_urls = {
            "🤖 ChatGPT": "https://chatgpt.com/cdn-cgi/trace",
            "💻 Codex": "https://api.openai.com/v1/models",
        }
        groups = list(group_urls.keys())

    url = _env("MIHOMO_DELAY_URL", "https://www.gstatic.com/generate_204").strip()
    timeout_ms = max(1000, int(_env("MIHOMO_DELAY_TIMEOUT_MS", "8000")))
    return MihomoDelayConfig(controller=controller, groups=groups, url=url, group_urls=group_urls, timeout_ms=timeout_ms)


def snapshot_once(*, cfg: MihomoDelayConfig) -> list[dict[str, Any]]:
    headers: Dict[str, str] = {"Accept": "application/json"}
    auth = _auth_header()
    if auth:
        headers["Authorization"] = auth

    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    base: Dict[str, Any] = {
        "ts": ts,
        "pid": os.getpid(),
        "controller": cfg.controller,
        "url": cfg.url,
        "timeout_ms": int(cfg.timeout_ms),
    }

    proxies_payload = _urlopen_json(f"{cfg.controller}/proxies", headers=headers, timeout_sec=10.0)
    proxies = (proxies_payload or {}).get("proxies")
    if not isinstance(proxies, dict):
        return [
            {
                **base,
                "ok": False,
                "status": "error",
                "error_type": "ValueError",
                "error": "mihomo /proxies returned unexpected JSON shape (missing `proxies` object).",
            }
        ]

    records: list[dict[str, Any]] = []
    for group in (cfg.groups or []):
        target_url = str(cfg.group_urls.get(group) or cfg.url or "").strip()
        if not target_url:
            target_url = "https://www.gstatic.com/generate_204"

        entry = proxies.get(group)
        selected = None
        if isinstance(entry, dict):
            selected = entry.get("now") if isinstance(entry.get("now"), str) else None
        if not selected:
            selected = group

        quoted_name = urllib.parse.quote(str(selected), safe="")
        quoted_url = urllib.parse.quote(target_url, safe="")
        delay_endpoint = f"{cfg.controller}/proxies/{quoted_name}/delay?timeout={int(cfg.timeout_ms)}&url={quoted_url}"

        started = time.time()
        delay_ms = None
        error_type = None
        error = None
        try:
            payload = _urlopen_json(delay_endpoint, headers=headers, timeout_sec=max(5.0, cfg.timeout_ms / 1000.0) + 5.0)
            if isinstance(payload, dict) and isinstance(payload.get("delay"), (int, float)):
                delay_ms = int(payload["delay"])
            else:
                error_type = "ValueError"
                error = f"unexpected delay payload: {payload!r}"
        except urllib.error.HTTPError as exc:
            error_type = "HTTPError"
            try:
                body = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                body = ""
            error = f"HTTP {exc.code} {body}".strip()
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            error_type = type(exc).__name__
            error = str(exc)

        record: Dict[str, Any] = {
            **base,
            "url": target_url,
            "ok": bool(delay_ms is not None),
            "status": "completed" if delay_ms is not None else "error",
            "group": group,
            "selected": selected,
            "delay_ms": delay_ms,
            "elapsed_ms": int(round((time.time() - started) * 1000)),
        }
        if error_type:
            record["error_type"] = error_type
        if error:
            record["error"] = error
        records.append(record)

    return records


def tail_jsonl(path: Path, *, max_lines: int = 200) -> list[dict[str, Any]]:
    try:
        if not path.exists():
            return []
    except Exception:
        return []

    max_lines = max(1, int(max_lines))
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            size = min(end, 256 * 1024)
            f.seek(end - size)
            raw = f.read()
    except Exception:
        return []

    lines = raw.decode("utf-8", errors="replace").splitlines()
    out: list[dict[str, Any]] = []
    for line in reversed(lines):
        s = (line or "").strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
        if len(out) >= max_lines:
            break
    out.reverse()
    return out


def summarize_recent(*, log_path: Path, group: str, selected: str, max_records: int = 50) -> dict[str, Any] | None:
    rows = tail_jsonl(log_path, max_lines=max(500, max_records * 4))
    matches: list[int] = []
    for r in reversed(rows):
        if str(r.get("group") or "") != str(group):
            continue
        if str(r.get("selected") or "") != str(selected):
            continue
        if not bool(r.get("ok")):
            continue
        dm = r.get("delay_ms")
        if isinstance(dm, (int, float)):
            matches.append(int(dm))
        if len(matches) >= max_records:
            break
    if not matches:
        return None
    matches.sort()
    n = len(matches)
    median = matches[n // 2]
    p90 = matches[max(0, int(round(n * 0.9)) - 1)]
    return {"n": n, "median_ms": median, "p90_ms": p90}


def parse_record_ts(ts: Any) -> float | None:
    """
    Parse `mihomo_delay` record timestamps.

    Records use `time.strftime("%Y-%m-%dT%H:%M:%S%z")`, e.g. "2025-12-26T23:55:03+0800".
    """
    raw = str(ts or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z").timestamp()
    except Exception:
        return None


def consecutive_failures(*, records: list[dict[str, Any]], group: str, selected: str) -> int:
    """
    Count consecutive non-ok records for (group, selected) from the end of the list.
    Non-matching records are ignored (so interleaved groups won't break the streak).
    """
    g = str(group or "")
    s = str(selected or "")
    n = 0
    for r in reversed(records or []):
        if str(r.get("group") or "") != g:
            continue
        if str(r.get("selected") or "") != s:
            continue
        if bool(r.get("ok")):
            break
        n += 1
    return int(n)


def last_success_record(*, records: list[dict[str, Any]], group: str, selected: str) -> dict[str, Any] | None:
    g = str(group or "")
    s = str(selected or "")
    for r in reversed(records or []):
        if str(r.get("group") or "") != g:
            continue
        if str(r.get("selected") or "") != s:
            continue
        if bool(r.get("ok")):
            return r
    return None


def recent_health_summary(*, records: list[dict[str, Any]], group: str, selected: str, max_records: int = 50) -> dict[str, Any]:
    """
    Compute a compact health summary for a (group, selected) pair.
    """
    g = str(group or "")
    s = str(selected or "")
    window: list[dict[str, Any]] = []
    for r in reversed(records or []):
        if str(r.get("group") or "") != g:
            continue
        if str(r.get("selected") or "") != s:
            continue
        window.append(r)
        if len(window) >= max(1, int(max_records)):
            break
    window.reverse()

    ok_n = sum(1 for r in window if bool(r.get("ok")))
    err_n = len(window) - ok_n
    last_ok = last_success_record(records=window, group=g, selected=s)
    last_ok_ts = parse_record_ts(last_ok.get("ts")) if isinstance(last_ok, dict) else None
    now = time.time()
    last_ok_age_s = (now - float(last_ok_ts)) if last_ok_ts else None

    return {
        "group": g,
        "selected": s,
        "window_n": len(window),
        "ok_n": int(ok_n),
        "error_n": int(err_n),
        "consecutive_failures": consecutive_failures(records=window, group=g, selected=s),
        "last_ok_ts": (float(last_ok_ts) if last_ok_ts is not None else None),
        "last_ok_age_seconds": (float(last_ok_age_s) if last_ok_age_s is not None else None),
    }
