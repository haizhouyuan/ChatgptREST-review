#!/usr/bin/env python3
"""Check and optionally repair known coding-agent public MCP configs."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path


PUBLIC_MCP_URL = "http://127.0.0.1:18712/mcp"
SKILL_WRAPPER_PATH = Path("/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py")
CHROME_WATCHDOG_PATH = Path("/vol1/1000/projects/ChatgptREST/ops/chrome_watchdog.sh")

KNOWN_CODEX_CONFIGS = [
    Path("/home/yuanhaizhou/.codex/config.toml"),
    Path("/vol1/1000/home-yuanhaizhou/.codex-shared/config.toml"),
    Path("/vol1/1000/home-yuanhaizhou/.home-codex-official/.codex/config.toml"),
    Path("/vol1/1000/home-yuanhaizhou/.codex2/config.toml"),
]

KNOWN_CLAUDE_CONFIGS = [
    Path("/home/yuanhaizhou/.claude.json"),
    Path("/vol1/1000/home-yuanhaizhou/.home-codex-official/.claude.json"),
    Path("/vol1/1000/home-yuanhaizhou/.claude-minimax/.claude.json"),
]

KNOWN_ANTIGRAVITY_CONFIGS = [
    Path("/home/yuanhaizhou/.gemini/antigravity/mcp_config.json"),
    Path("/vol1/1000/home-yuanhaizhou/.home-codex-official/.antigravity/mcp_config.json"),
]


def extract_chatgptrest_block(text: str) -> str:
    lines = text.splitlines()
    in_block = False
    collected: list[str] = []
    for line in lines:
        if line.strip() == "[mcp_servers.chatgptrest]":
            in_block = True
            collected.append(line)
            continue
        if in_block and line.startswith("[") and line.strip() != "[mcp_servers.chatgptrest]":
            break
        if in_block:
            collected.append(line)
    return "\n".join(collected)


def _backup_file(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, backup)
    return backup


def _write_json(path: Path, payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _canonical_http_server() -> dict[str, str]:
    return {"type": "http", "url": PUBLIC_MCP_URL}


def inspect_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "ok": False,
            "reason": "missing",
        }
    block = extract_chatgptrest_block(path.read_text())
    url_ok = f'url = "{PUBLIC_MCP_URL}"' in block
    has_stdio = "chatgptrest_agent_mcp_server.py" in block or "--transport\", \"stdio\"" in block
    enabled = "enabled = true" in block
    ok = bool(block) and enabled and url_ok and not has_stdio
    reason = "ok"
    if not block:
        reason = "missing_chatgptrest_block"
    elif not enabled:
        reason = "disabled"
    elif has_stdio:
        reason = "uses_local_stdio_server"
    elif not url_ok:
        reason = "wrong_or_missing_public_url"
    return {
        "path": str(path),
        "exists": True,
        "ok": ok,
        "reason": reason,
        "uses_public_url": url_ok,
        "enabled": enabled,
    }


def inspect_json_http_mcp(path: Path, *, server_names: tuple[str, ...]) -> dict[str, object]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "ok": False,
            "reason": "missing",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "path": str(path),
            "exists": True,
            "ok": False,
            "reason": "invalid_json",
        }
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict):
        return {
            "path": str(path),
            "exists": True,
            "ok": False,
            "reason": "missing_mcp_servers",
        }
    server_name = next((name for name in server_names if name in servers), None)
    if server_name is None:
        return {
            "path": str(path),
            "exists": True,
            "ok": False,
            "reason": "missing_chatgptrest_server",
        }
    server = servers.get(server_name)
    if not isinstance(server, dict):
        return {
            "path": str(path),
            "exists": True,
            "ok": False,
            "reason": "invalid_server_block",
        }
    server_type = str(server.get("type", "")).strip()
    url = str(server.get("url", "")).strip()
    legacy_server_url = str(server.get("serverURL", "")).strip()
    server_blob = json.dumps(server, ensure_ascii=False)
    has_stdio = server_type == "stdio" or "chatgptrest_agent_mcp_server.py" in server_blob
    url_ok = url == PUBLIC_MCP_URL
    legacy_public_url = legacy_server_url == PUBLIC_MCP_URL
    ok = server_type == "http" and url_ok and not has_stdio
    reason = "ok"
    if has_stdio:
        reason = "uses_local_stdio_server"
    elif legacy_public_url and not url_ok:
        reason = "legacy_serverURL_field"
    elif server_type != "http":
        reason = "wrong_transport"
    elif not url_ok:
        reason = "wrong_or_missing_public_url"
    return {
        "path": str(path),
        "exists": True,
        "ok": ok,
        "reason": reason,
        "server_name": server_name,
        "server_type": server_type,
        "uses_public_url": url_ok,
        "legacy_server_url": legacy_server_url,
        "uses_legacy_public_url": legacy_public_url,
    }


def _repair_json_http_mcp(
    path: Path,
    *,
    server_names: tuple[str, ...],
    canonical_server_name: str,
) -> dict[str, object]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "changed": False,
            "ok": False,
            "reason": "missing",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "path": str(path),
            "exists": True,
            "changed": False,
            "ok": False,
            "reason": "invalid_json",
        }
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict):
        return {
            "path": str(path),
            "exists": True,
            "changed": False,
            "ok": False,
            "reason": "missing_mcp_servers",
        }
    server_name = next((name for name in server_names if name in servers), canonical_server_name)
    before = servers.get(server_name)
    canonical = _canonical_http_server()
    if before == canonical:
        return {
            "path": str(path),
            "exists": True,
            "changed": False,
            "ok": True,
            "reason": "already_canonical",
            "server_name": server_name,
            "backup_path": "",
        }
    backup = _backup_file(path)
    servers[server_name] = canonical
    payload["mcpServers"] = servers
    _write_json(path, payload)
    return {
        "path": str(path),
        "exists": True,
        "changed": True,
        "ok": True,
        "reason": "repaired",
        "server_name": server_name,
        "backup_path": str(backup),
    }


def inspect_claude_config(path: Path) -> dict[str, object]:
    return inspect_json_http_mcp(path, server_names=("chatgptrest", "chatgptrest-mcp"))


def inspect_antigravity_config(path: Path) -> dict[str, object]:
    return inspect_json_http_mcp(path, server_names=("chatgptrest",))


def repair_antigravity_config(path: Path) -> dict[str, object]:
    return _repair_json_http_mcp(path, server_names=("chatgptrest",), canonical_server_name="chatgptrest")


def inspect_skill_wrapper(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "ok": False,
            "reason": "missing",
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    uses_public_default = 'DEFAULT_PUBLIC_MCP_URL = "http://127.0.0.1:18712/mcp"' in text
    routes_agent_mode_via_mcp = "_run_mcp_tool(" in text
    avoids_agent_rest_submit = 'cmd.extend([' not in text.split("def _run_agent_turn", 1)[-1].split("def _run_legacy_jobs", 1)[0]
    supports_workspace_request = "--workspace-request-json" in text and "--workspace-request-file" in text
    requires_maintenance_legacy_gate = "--maintenance-legacy-jobs" in text and "args.maintenance_legacy_jobs" in text
    uses_maintenance_client_name = "chatgptrestctl-maint" in text and "CHATGPTREST_CLIENT_NAME" in text
    ok = (
        uses_public_default
        and routes_agent_mode_via_mcp
        and avoids_agent_rest_submit
        and supports_workspace_request
        and requires_maintenance_legacy_gate
        and uses_maintenance_client_name
    )
    reason = "ok"
    if not uses_public_default:
        reason = "missing_public_mcp_default"
    elif not routes_agent_mode_via_mcp:
        reason = "agent_mode_not_using_public_mcp"
    elif not avoids_agent_rest_submit:
        reason = "agent_mode_still_builds_rest_cli"
    elif not supports_workspace_request:
        reason = "missing_workspace_request_support"
    elif not requires_maintenance_legacy_gate:
        reason = "legacy_jobs_not_maintenance_gated"
    elif not uses_maintenance_client_name:
        reason = "legacy_jobs_missing_maintenance_client"
    return {
        "path": str(path),
        "exists": True,
        "ok": ok,
        "reason": reason,
        "uses_public_mcp_default": uses_public_default,
        "routes_agent_mode_via_mcp": routes_agent_mode_via_mcp,
        "supports_workspace_request": supports_workspace_request,
        "requires_maintenance_legacy_gate": requires_maintenance_legacy_gate,
        "uses_maintenance_client_name": uses_maintenance_client_name,
    }


def inspect_chrome_watchdog_contract(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "ok": False,
            "reason": "missing",
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    api_port_ok = 'API_PORT="${CHATGPTREST_API_PORT:-18711}"' in text
    wrong_mcp_default = 'API_PORT="${CHATGPTREST_API_PORT:-18712}"' in text
    issue_url_ok = 'http://127.0.0.1:${API_PORT}/v1/issues/report' in text
    ok = api_port_ok and issue_url_ok and not wrong_mcp_default
    reason = "ok"
    if wrong_mcp_default:
        reason = "wrong_default_api_port"
    elif not api_port_ok:
        reason = "missing_api_port_contract"
    elif not issue_url_ok:
        reason = "missing_issue_report_target"
    return {
        "path": str(path),
        "exists": True,
        "ok": ok,
        "reason": reason,
        "api_port_ok": api_port_ok,
        "issue_url_ok": issue_url_ok,
    }


def collect_alignment_report(*, apply_fix: bool = False) -> dict[str, object]:
    fixes = [repair_antigravity_config(path) for path in KNOWN_ANTIGRAVITY_CONFIGS] if apply_fix else []
    codex_checks = [inspect_config(path) for path in KNOWN_CODEX_CONFIGS]
    claude_checks = [inspect_claude_config(path) for path in KNOWN_CLAUDE_CONFIGS]
    antigravity_checks = [inspect_antigravity_config(path) for path in KNOWN_ANTIGRAVITY_CONFIGS]
    runtime_checks = [inspect_chrome_watchdog_contract(CHROME_WATCHDOG_PATH)]
    wrapper_check = inspect_skill_wrapper(SKILL_WRAPPER_PATH)
    all_checks = codex_checks + claude_checks + antigravity_checks + runtime_checks
    overall_ok = all(item["ok"] for item in all_checks) and bool(wrapper_check["ok"])
    return {
        "ok": overall_ok,
        "public_mcp_url": PUBLIC_MCP_URL,
        "num_checked": len(all_checks) + 1,
        "num_failed": sum(1 for item in all_checks if not item["ok"]) + (0 if wrapper_check["ok"] else 1),
        "codex_configs": codex_checks,
        "claude_configs": claude_checks,
        "antigravity_configs": antigravity_checks,
        "runtime_checks": runtime_checks,
        "checks": all_checks,
        "skill_wrapper": wrapper_check,
        "fixes": fixes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and optionally repair public MCP client config alignment.")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Repair known Antigravity MCP config drift to the canonical HTTP public MCP block.",
    )
    args = parser.parse_args()
    payload = collect_alignment_report(apply_fix=args.fix)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
