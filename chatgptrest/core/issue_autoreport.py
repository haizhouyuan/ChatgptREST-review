from __future__ import annotations

import json
import re
from typing import Any


AUTO_ISSUE_SOURCE = "worker_auto"


def ws_single(value: Any, *, max_chars: int = 400) -> str:
    out = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(out) > max_chars:
        return out[:max_chars]
    return out


def issue_autoreport_statuses(raw: str | None) -> set[str]:
    default_raw = "error,blocked,needs_followup"
    value = str(raw or "").strip() or default_raw
    out: set[str] = set()
    for part in value.split(","):
        p = str(part or "").strip().lower()
        if p:
            out.add(p)
    if not out:
        out.update({"error", "blocked", "needs_followup"})
    return out


def error_signature_fragment(*, error_type: str, error: str) -> str:
    et = ws_single(error_type, max_chars=120).lower()
    msg = ws_single(error, max_chars=500).lower()
    msg = re.sub(r"https?://\S+", "<url>", msg)
    msg = re.sub(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        "<uuid>",
        msg,
    )
    msg = re.sub(r"\b[0-9a-f]{16,}\b", "<hex>", msg)
    msg = re.sub(r"\b\d{4,}\b", "<num>", msg)
    msg = re.sub(r":\d{4,5}(?=/|\b)", ":<cdp_port>", msg)
    if len(msg) > 240:
        msg = msg[:240]
    return f"{et}|{msg}"


def auto_issue_fingerprint(*, kind: str, status: str, error_type: str, error: str) -> str:
    return (
        f"auto:{ws_single(kind, max_chars=200)}:"
        f"{ws_single(status, max_chars=40).lower()}:"
        f"{error_signature_fragment(error_type=error_type, error=error)}"
    )


def issue_project_from_client_json(client_json: str | None, *, default_project: str) -> str:
    default_project_n = ws_single(default_project, max_chars=200) or "chatgptrest"
    try:
        obj = json.loads(str(client_json or ""))
        if not isinstance(obj, dict):
            return default_project_n
        for key in ("project", "project_id", "topic_id", "repo", "name", "app"):
            val = ws_single(obj.get(key), max_chars=200) if key in obj else ""
            if val:
                return val
        meta = obj.get("meta")
        if isinstance(meta, dict):
            for key in ("project", "project_id", "topic_id", "repo", "name", "app"):
                val = ws_single(meta.get(key), max_chars=200) if key in meta else ""
                if val:
                    return val
    except Exception:
        pass
    return default_project_n


def issue_severity_for_status(*, status: str, error_type: str, error: str) -> str:
    st = str(status or "").strip().lower()
    et = str(error_type or "").strip().lower()
    msg = str(error or "").strip().lower()
    if st == "blocked":
        return "P1"
    if st == "error":
        if et == "maxattemptsexceeded":
            return "P1"
        if "cloudflare" in msg or "challenge" in msg or "err_connection_closed" in msg:
            return "P1"
        if et == "infraerror" or "connection refused" in msg or "cdp" in msg:
            return "P2"
        return "P2"
    if st == "needs_followup":
        return "P2"
    if st == "cooldown":
        return "P2"
    return "P3"
