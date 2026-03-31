from __future__ import annotations

import os
from typing import Any

from chatgptrest.core.completion_contract import COMPLETION_CONTRACT_VERSION

PUBLIC_AGENT_MCP_SURFACE_VERSION = "public-advisor-agent-mcp-v1"


def public_agent_client_name() -> str:
    return (
        os.environ.get("CHATGPTREST_AGENT_MCP_CLIENT_NAME")
        or os.environ.get("CHATGPTREST_CLIENT_NAME")
        or "chatgptrest-mcp"
    ).strip() or "chatgptrest-mcp"


def public_agent_base_url() -> str:
    raw = os.environ.get("CHATGPTREST_AGENT_MCP_BASE_URL", "").strip()
    if raw:
        return raw.rstrip("/")
    return os.environ.get("CHATGPTREST_BASE_URL", "http://127.0.0.1:18711").rstrip("/")


def public_agent_mcp_host_port() -> tuple[str, int]:
    host = os.environ.get("FASTMCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port_raw = (os.environ.get("FASTMCP_PORT") or "").strip()
    if not port_raw:
        return host, 18712
    try:
        return host, int(port_raw)
    except ValueError:
        return host, 18712


def parse_client_name_allowlist(raw: str | None) -> set[str]:
    parts = [str(part or "").strip().lower() for part in str(raw or "").replace(";", ",").split(",")]
    return {part for part in parts if part}


def public_agent_allowlist_state() -> dict[str, Any]:
    allowlist = parse_client_name_allowlist(os.environ.get("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", ""))
    client_name = public_agent_client_name().strip().lower()
    if not allowlist:
        return {
            "enforced": False,
            "allowlisted": True,
            "client_name": client_name,
            "allowlist": [],
        }
    return {
        "enforced": True,
        "allowlisted": client_name in allowlist,
        "client_name": client_name,
        "allowlist": sorted(allowlist),
    }


def public_agent_mcp_runtime_contract_state() -> dict[str, Any]:
    openmind_api_key = os.environ.get("OPENMIND_API_KEY", "").strip()
    bearer_token = os.environ.get("CHATGPTREST_API_TOKEN", "").strip()
    source = ""
    token = ""
    if openmind_api_key:
        source = "OPENMIND_API_KEY"
        token = openmind_api_key
    elif bearer_token:
        source = "CHATGPTREST_API_TOKEN"
        token = bearer_token
    allowlist_state = public_agent_allowlist_state()
    host, port = public_agent_mcp_host_port()
    return {
        "ok": bool(token) and bool(allowlist_state.get("allowlisted")),
        "source": source,
        "token_present": bool(token),
        "base_url": public_agent_base_url(),
        "mcp_host": host,
        "mcp_port": port,
        "service_identity": allowlist_state.get("client_name"),
        "client_name": allowlist_state.get("client_name"),
        "allowlist_enforced": bool(allowlist_state.get("enforced")),
        "allowlist": list(allowlist_state.get("allowlist") or []),
        "allowlisted": bool(allowlist_state.get("allowlisted")),
        "runtime_contract_ok": bool(token) and bool(allowlist_state.get("allowlisted")),
        "completion_contract_version": COMPLETION_CONTRACT_VERSION,
        "mcp_surface_version": PUBLIC_AGENT_MCP_SURFACE_VERSION,
    }
