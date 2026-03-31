#!/usr/bin/env python3
"""Run live verification for the rebuilt OpenClaw + OpenMind baseline."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw"))).expanduser()
DEFAULT_OPENCLAW_BIN = Path(os.environ.get("OPENCLAW_BIN", str(Path.home() / ".local" / "bin" / "openclaw"))).expanduser()
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "verify_openclaw_openmind"
DEFAULT_REVIEW_DOCS_DIR = REPO_ROOT / "docs" / "reviews"
VERIFY_PING_RE = re.compile(r"VERIFY_PING_[A-Za-z0-9]+")
MAIN_OPENMIND_TOOLS = {
    "openmind_memory_status",
    "openmind_memory_recall",
    "openmind_memory_capture",
    "openmind_graph_query",
    "openmind_advisor_ask",
}
OPS_MAIN_COMM_TOOLS = {"sessions_send", "sessions_list", "sessions_history"}
MAINT_REQUIRED_TOOLS = {"sessions_send", "sessions_list", "session_status"}
PROFILE_CORE_TOOLS = {
    "minimal": {"session_status"},
    "messaging": {"message", "sessions_list", "sessions_history", "sessions_send", "session_status"},
    "coding": {
        "read",
        "write",
        "edit",
        "apply_patch",
        "exec",
        "process",
        "memory_search",
        "memory_get",
        "sessions_list",
        "sessions_history",
        "sessions_send",
        "sessions_spawn",
        "subagents",
        "session_status",
        "cron",
        "image",
    },
    "full": set(),
}
EXPECTED_FEISHU_TOOL_FLAGS = {
    "doc": False,
    "chat": False,
    "wiki": False,
    "drive": False,
    "perm": False,
    "scopes": False,
}
TOOL_GROUPS = {
    "group:fs": {"read", "write", "edit", "apply_patch"},
    "group:runtime": {"exec", "process"},
    "group:memory": {"memory_search", "memory_get"},
    "group:sessions": {"sessions_list", "sessions_history", "sessions_send", "sessions_spawn", "session_status"},
    "group:ui": {"browser", "canvas"},
    "group:automation": {"cron", "gateway"},
}
# Load from topology.yaml if available (Issue #126), otherwise hardcoded fallback.
def _load_topology_agent_ids() -> dict[str, set[str]]:
    try:
        from chatgptrest.kernel.topology_loader import load_topology
        topo = load_topology()
        return topo.all_topology_agent_ids()
    except Exception:
        return {"lean": {"main"}, "ops": {"main", "maintagent"}}


def _load_retired_agent_ids() -> set[str]:
    try:
        from chatgptrest.kernel.topology_loader import load_topology
        topo = load_topology()
        return set(topo.retired_agents)
    except Exception:
        return set()


TOPOLOGY_AGENT_IDS = _load_topology_agent_ids()
RETIRED_AGENT_IDS = _load_retired_agent_ids()
LEGACY_TOPOLOGY_AGENT_IDS = {
    "ops": {"main", "maintagent", "autoorch"},
}
BASE_TOPOLOGY_AGENT_IDS = {
    "lean": {"main"},
    "ops": {"main", "maintagent"},
}
OPTIONAL_TOPOLOGY_AGENT_IDS = {
    "ops": {"finbot", "autoorch"},
}
LEGACY_ROLE_AGENT_IDS = {"planning", "research-orch", "openclaw-orch"}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def run_cmd(
    args: list[str],
    *,
    timeout: int = 180,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd or REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, **(env or {})},
    )


def ensure_ok(proc: subprocess.CompletedProcess[str], *, name: str) -> str:
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        raise RuntimeError(f"{name} failed: rc={proc.returncode} stderr={stderr or '<empty>'} stdout={stdout or '<empty>'}")
    return proc.stdout


def extract_json_payload(text: str) -> Any:
    for marker in ("{", "["):
        start = text.find(marker)
        while start != -1:
            candidate = text[start:].strip()
            try:
                return json.loads(candidate)
            except JSONDecodeError:
                start = text.find(marker, start + 1)
    raise ValueError("no JSON payload found in command output")


def load_sessions_index(state_dir: Path, agent_id: str) -> dict[str, Any]:
    path = state_dir / "agents" / agent_id / "sessions" / "sessions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_openclaw_config(state_dir: Path) -> dict[str, Any]:
    return json.loads((state_dir / "openclaw.json").read_text(encoding="utf-8"))


def resolve_session_transcript_path(state_dir: Path, agent_id: str, session_key: str) -> Path:
    sessions = load_sessions_index(state_dir, agent_id)
    entry = sessions.get(session_key)
    if not isinstance(entry, dict):
        raise RuntimeError(f"missing session entry for {agent_id}:{session_key}")
    session_file = str(entry.get("sessionFile") or "").strip()
    if session_file:
        return Path(session_file)
    if not entry.get("sessionId"):
        raise RuntimeError(f"missing session entry for {agent_id}:{session_key}")
    return state_dir / "agents" / agent_id / "sessions" / f"{entry['sessionId']}.jsonl"


def wait_for_text(path: Path, needle: str, *, timeout_sec: int = 30, poll_sec: float = 1.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            if needle in text:
                return True
        time.sleep(poll_sec)
    return False


def latest_token_in_transcript(path: Path, pattern: re.Pattern[str] = VERIFY_PING_RE) -> str:
    if not path.exists():
        return ""
    matches = pattern.findall(path.read_text(encoding="utf-8", errors="replace"))
    return matches[-1] if matches else ""


def _content_text(message: dict[str, Any]) -> str:
    return message_text(message)


def load_transcript_messages(path: Path) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if not path.exists():
        return messages
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except JSONDecodeError:
            continue
        message = payload.get("message")
        if isinstance(message, dict):
            messages.append(message)
    return messages


def message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    chunks = [
        str(block.get("text"))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    ]
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def normalize_assistant_text(text: str) -> str:
    normalized = text.strip()
    if normalized.startswith("[[reply_to_current]]"):
        normalized = normalized[len("[[reply_to_current]]") :].strip()
    return normalized


def is_provider_fallback_bridge_user_message(message: dict[str, Any]) -> bool:
    if str(message.get("role") or "") != "user":
        return False
    text = message_text(message)
    normalized = normalize_assistant_text(text)
    return "Continue where you left off. The previous model attempt failed or timed out." in normalized


def inspect_tool_round(
    transcript_path: Path,
    *,
    user_needle: str,
    tool_name: str,
    assistant_reply: str,
) -> dict[str, Any]:
    messages = load_transcript_messages(transcript_path)
    candidate_indexes = [
        index
        for index, message in enumerate(messages)
        if str(message.get("role") or "") == "user" and user_needle in message_text(message)
    ]
    if not candidate_indexes:
        return {
            "ok": False,
            "detail": "missing user marker in transcript",
            "tool_called": False,
            "tool_result": False,
            "assistant_text": "",
            "tool_details": {},
        }

    last_result: dict[str, Any] | None = None
    for start_index in reversed(candidate_indexes):
        tool_called = False
        tool_result = False
        final_assistant_text = ""
        tool_details: dict[str, Any] = {}
        for message in messages[start_index + 1 :]:
            role = str(message.get("role") or "")
            if role == "user":
                if is_provider_fallback_bridge_user_message(message):
                    continue
                break
            if role == "assistant":
                content = message.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "toolCall" and str(block.get("name") or "") == tool_name:
                            tool_called = True
                text = message_text(message)
                if text:
                    final_assistant_text = normalize_assistant_text(text)
            elif role == "toolResult" and str(message.get("toolName") or "") == tool_name and not bool(message.get("isError")):
                tool_result = True
                if isinstance(message.get("details"), dict):
                    tool_details = message["details"]

        ok = tool_called and tool_result and final_assistant_text.strip() == normalize_assistant_text(assistant_reply)
        detail = f"tool_called={tool_called} tool_result={tool_result} assistant={final_assistant_text!r}"
        result = {
            "ok": ok,
            "detail": detail,
            "tool_called": tool_called,
            "tool_result": tool_result,
            "assistant_text": final_assistant_text,
            "tool_details": tool_details,
        }
        if ok:
            return result
        last_result = result
    return last_result or {
        "ok": False,
        "detail": "missing user marker in transcript",
        "tool_called": False,
        "tool_result": False,
        "assistant_text": "",
        "tool_details": {},
    }


def inspect_unavailable_tool_round(
    transcript_path: Path,
    *,
    user_needle: str,
    tool_name: str,
    assistant_reply: str,
) -> dict[str, Any]:
    messages = load_transcript_messages(transcript_path)
    candidate_indexes = [
        index
        for index, message in enumerate(messages)
        if str(message.get("role") or "") == "user" and user_needle in message_text(message)
    ]
    if not candidate_indexes:
        return {
            "ok": False,
            "detail": "missing user marker in transcript",
            "tool_called": False,
            "tool_result": False,
            "assistant_text": "",
        }

    last_result: dict[str, Any] | None = None
    for start_index in reversed(candidate_indexes):
        tool_called = False
        tool_result = False
        final_assistant_text = ""
        for message in messages[start_index + 1 :]:
            role = str(message.get("role") or "")
            if role == "user":
                if is_provider_fallback_bridge_user_message(message):
                    continue
                break
            if role == "assistant":
                content = message.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "toolCall" and str(block.get("name") or "") == tool_name:
                            tool_called = True
                text = message_text(message)
                if text:
                    final_assistant_text = normalize_assistant_text(text)
            elif role == "toolResult" and str(message.get("toolName") or "") == tool_name and not bool(message.get("isError")):
                tool_result = True

        ok = (not tool_called) and (not tool_result) and final_assistant_text.strip() == normalize_assistant_text(assistant_reply)
        detail = f"tool_called={tool_called} tool_result={tool_result} assistant={final_assistant_text!r}"
        result = {
            "ok": ok,
            "detail": detail,
            "tool_called": tool_called,
            "tool_result": tool_result,
            "assistant_text": final_assistant_text,
        }
        if ok:
            return result
        last_result = result
    return last_result or {
        "ok": False,
        "detail": "missing user marker in transcript",
        "tool_called": False,
        "tool_result": False,
        "assistant_text": "",
    }


def probe_reply_ok(reply: str, expected_reply: str, *, transcript_round_ok: bool = False) -> bool:
    normalized = reply.strip()
    if normalized == expected_reply:
        return True
    return not normalized and transcript_round_ok


def transcript_excerpt(transcript_path: Path, *, user_needle: str) -> list[dict[str, Any]]:
    messages = load_transcript_messages(transcript_path)
    start_index = -1
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if str(message.get("role") or "") == "user" and user_needle in message_text(message):
            start_index = index
            break
    if start_index < 0:
        return []

    excerpt: list[dict[str, Any]] = []
    for message in messages[start_index:]:
        role = str(message.get("role") or "")
        if excerpt and role == "user":
            break
        item: dict[str, Any] = {"role": role}
        text = _content_text(message)
        if text:
            item["text"] = normalize_assistant_text(text) if role == "assistant" else text
        if role == "toolResult":
            item["toolName"] = str(message.get("toolName") or "")
            item["isError"] = bool(message.get("isError"))
            if isinstance(message.get("details"), dict):
                item["details"] = message["details"]
        elif role == "assistant":
            content = message.get("content")
            tool_calls: list[str] = []
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "toolCall":
                        name = str(block.get("name") or "").strip()
                        if name:
                            tool_calls.append(name)
            if tool_calls:
                item["toolCalls"] = tool_calls
        excerpt.append(item)
    return excerpt


def capture_details_ok(details: dict[str, Any]) -> bool:
    results = details.get("results")
    if not isinstance(results, list) or not results:
        return False
    first = results[0]
    if not isinstance(first, dict):
        return False
    return bool(first.get("ok")) and bool(str(first.get("record_id") or "").strip()) and isinstance(first.get("audit_trail"), list)


def recall_details_have_captured_block(details: dict[str, Any]) -> bool:
    blocks = details.get("context_blocks")
    if not isinstance(blocks, list):
        return False
    return any(isinstance(block, dict) and str(block.get("source_type") or "") == "captured" for block in blocks)


def recall_details_contain_text(details: dict[str, Any], needle: str) -> bool:
    probe = needle.strip()
    if not probe:
        return False
    prompt_prefix = details.get("prompt_prefix")
    if isinstance(prompt_prefix, str) and probe in prompt_prefix:
        return True
    blocks = details.get("context_blocks")
    if not isinstance(blocks, list):
        return False
    for block in blocks:
        if isinstance(block, dict) and isinstance(block.get("text"), str) and probe in block["text"]:
            return True
    return False


def recall_details_role_id(details: dict[str, Any]) -> str:
    metadata = details.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    return str(metadata.get("role_id") or "").strip()


def recall_details_scope_tags(details: dict[str, Any]) -> list[str]:
    metadata = details.get("metadata")
    if not isinstance(metadata, dict):
        return []
    values = metadata.get("kb_scope_tags")
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if isinstance(value, str) and str(value).strip()]


def summarize_security(status_payload: dict[str, Any]) -> str:
    summary = (((status_payload.get("securityAudit") or {}).get("summary")) or {})
    critical = summary.get("critical", 0)
    warn = summary.get("warn", 0)
    info = summary.get("info", 0)
    return f"critical={critical} warn={warn} info={info}"


def expand_tool_tokens(tokens: list[str] | set[str] | tuple[str, ...]) -> set[str]:
    expanded: set[str] = set()
    for token in tokens:
        if not isinstance(token, str):
            continue
        expanded |= TOOL_GROUPS.get(token, {token})
    return expanded


def effective_tools(tool_cfg: dict[str, Any]) -> set[str]:
    profile = str(tool_cfg.get("profile") or "").strip()
    effective = set(PROFILE_CORE_TOOLS.get(profile, set()))
    effective |= expand_tool_tokens(tool_cfg.get("allow") or [])
    effective |= expand_tool_tokens(tool_cfg.get("alsoAllow") or [])
    effective -= expand_tool_tokens(tool_cfg.get("deny") or [])
    return effective


def infer_topology(agent_ids: set[str]) -> str:
    for topology, expected_ids in TOPOLOGY_AGENT_IDS.items():
        if agent_ids == expected_ids:
            return topology
    for topology, expected_ids in TOPOLOGY_AGENT_IDS.items():
        extras = set(agent_ids) - set(expected_ids)
        if expected_ids.issubset(agent_ids) and extras and extras.issubset(RETIRED_AGENT_IDS):
            return topology
    for topology, expected_ids in LEGACY_TOPOLOGY_AGENT_IDS.items():
        if agent_ids == expected_ids:
            return topology
    for topology, expected_ids in LEGACY_TOPOLOGY_AGENT_IDS.items():
        extras = set(agent_ids) - set(expected_ids)
        if expected_ids.issubset(agent_ids) and extras and extras.issubset(RETIRED_AGENT_IDS):
            return topology
    for topology, base_ids in BASE_TOPOLOGY_AGENT_IDS.items():
        optional_ids = OPTIONAL_TOPOLOGY_AGENT_IDS.get(topology, set())
        extras = set(agent_ids) - set(base_ids)
        if not base_ids.issubset(agent_ids):
            continue
        if extras and extras.issubset(optional_ids | RETIRED_AGENT_IDS):
            return topology
        if not extras:
            return topology
    return "custom"


def normalize_path_list(values: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text:
            continue
        resolved = str(Path(text).expanduser().resolve())
        if resolved not in normalized:
            normalized.append(resolved)
    return normalized


def is_repo_skill_dir(path_str: str) -> bool:
    path = Path(path_str).expanduser().resolve()
    required_skill = path / "chatgptrest-call" / "SKILL.md"
    repo_marker = path.parent / "chatgptrest" / "api" / "app.py"
    return path.name == "skills-src" and required_skill.is_file() and repo_marker.is_file()


def skills_repo_only_ok(extra_dirs: list[str], allow_bundled: list[str]) -> bool:
    return bool(extra_dirs) and not allow_bundled and all(is_repo_skill_dir(item) for item in extra_dirs)


def expected_heartbeat_agent_count(agent_ids: set[str], inferred_topology: str) -> int:
    expected_ids = set(TOPOLOGY_AGENT_IDS.get(inferred_topology, set()))
    extras = set(agent_ids) - expected_ids
    if expected_ids and extras and extras.issubset(RETIRED_AGENT_IDS):
        return len(agent_ids)
    if expected_ids:
        return len(expected_ids)
    return len(agent_ids)


def redact_auth_dict(auth_cfg: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(auth_cfg)
    if "token" in redacted and str(redacted.get("token") or "").strip():
        redacted["token"] = "<redacted>"
    return redacted


def redact_gateway_config(gateway_cfg: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(gateway_cfg)
    auth_cfg = redacted.get("auth")
    if isinstance(auth_cfg, dict):
        redacted["auth"] = redact_auth_dict(auth_cfg)
    return redacted


def redact_recursive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lower_key = str(key).lower()
            if any(token in lower_key for token in ("token", "secret", "apikey", "api_key", "password")) and item:
                redacted[key] = "<redacted>"
            else:
                redacted[key] = redact_recursive(item)
        return redacted
    if isinstance(value, list):
        return [redact_recursive(item) for item in value]
    return value


def gateway_token_present(gateway_cfg: dict[str, Any]) -> bool:
    auth_cfg = gateway_cfg.get("auth") or {}
    return bool(str(auth_cfg.get("token") or "").strip())


def advisor_auth_probe(*, base_url: str, api_key: str = "", timeout: int = 10) -> dict[str, Any]:
    base = base_url.rstrip("/")
    url = f"{base}/v2/advisor/ask"
    payload = json.dumps({"question": "ping"}).encode("utf-8")

    def _send(req: urllib_request.Request) -> tuple[int, str]:
        try:
            with urllib_request.urlopen(req, timeout=timeout) as resp:
                return int(resp.status), resp.read().decode("utf-8", errors="replace")
        except urllib_error.HTTPError as exc:
            return int(exc.code), exc.read().decode("utf-8", errors="replace")

    common_headers = {"Content-Type": "application/json"}
    unauth_status, unauth_body = _send(
        urllib_request.Request(url, data=payload, headers=common_headers, method="POST")
    )
    result = {
        "url": url,
        "unauthenticated_status": unauth_status,
        "unauthenticated_body": unauth_body[:1000],
    }
    if api_key:
        auth_headers = {"X-Api-Key": api_key}
        auth_status, auth_body = _send(
            urllib_request.Request(f"{base}/v2/advisor/evomap/stats", headers=auth_headers, method="GET")
        )
        result["authenticated_status"] = auth_status
        result["authenticated_body"] = auth_body[:1000]
    return result


def publish_review_evidence(
    *,
    review_docs_dir: Path,
    report: dict[str, Any],
    config_payload: dict[str, Any],
    openmind_excerpt: list[dict[str, Any]],
    memory_capture_excerpt: list[dict[str, Any]],
    memory_recall_excerpt: list[dict[str, Any]],
    role_capture_excerpt: list[dict[str, Any]],
    role_devops_recall_excerpt: list[dict[str, Any]],
    role_research_recall_excerpt: list[dict[str, Any]],
    sessions_spawn_excerpt: list[dict[str, Any]],
    subagents_excerpt: list[dict[str, Any]],
    maint_excerpt: list[dict[str, Any]],
    review_label: str,
    auth_probe: dict[str, Any],
) -> dict[str, str]:
    evidence_root = review_docs_dir / "evidence" / "openclaw_openmind"
    b1_dir = evidence_root / "B1"
    b2_dir = evidence_root / "B2"
    b1_dir.mkdir(parents=True, exist_ok=True)
    b2_dir.mkdir(parents=True, exist_ok=True)

    topology = str(report.get("topology") or "custom")
    verifier_json_path = review_docs_dir / f"openclaw_openmind_verifier_{topology}_{review_label}.json"
    verifier_md_path = review_docs_dir / f"openclaw_openmind_verifier_{topology}_{review_label}.md"
    config_path = b1_dir / f"openclaw_openmind_config_{topology}_{review_label}.json"
    transcript_path = b1_dir / f"openclaw_openmind_transcript_{topology}_{review_label}.json"
    auth_path = b2_dir / f"openmind_advisor_auth_{topology}_{review_label}.json"

    review_paths = {
        "verifier_json": str(verifier_json_path.relative_to(REPO_ROOT)),
        "verifier_md": str(verifier_md_path.relative_to(REPO_ROOT)),
        "config_snapshot": str(config_path.relative_to(REPO_ROOT)),
        "transcript_excerpt": str(transcript_path.relative_to(REPO_ROOT)),
        "auth_probe": str(auth_path.relative_to(REPO_ROOT)),
    }
    report_payload = dict(report)
    report_payload["review_evidence"] = review_paths
    verifier_json_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verifier_md_path.write_text(render_markdown(report_payload), encoding="utf-8")
    config_path.write_text(json.dumps(redact_recursive(config_payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    transcript_path.write_text(
        json.dumps(
            {
                "topology": topology,
                "openmind_probe": openmind_excerpt,
                "memory_capture": memory_capture_excerpt,
                "memory_recall": memory_recall_excerpt,
                "role_capture": role_capture_excerpt,
                "role_devops_recall": role_devops_recall_excerpt,
                "role_research_recall": role_research_recall_excerpt,
                "sessions_spawn_negative_probe": sessions_spawn_excerpt,
                "subagents_negative_probe": subagents_excerpt,
                "maintagent_comm_probe": maint_excerpt,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    auth_path.write_text(json.dumps(auth_probe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return review_paths


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw + OpenMind Verification Report",
        "",
        f"- Timestamp UTC: `{report['generated_at']}`",
        f"- OpenClaw bin: `{report['openclaw_bin']}`",
        f"- State dir: `{report['state_dir']}`",
        "",
        "## Checks",
        "",
    ]
    for item in report["checks"]:
        status = "PASS" if item["ok"] else "FAIL"
        lines.append(f"- `{item['name']}`: {status} | {item['detail']}")
    lines.extend(
        [
            "",
            "## Security",
            "",
            f"- {report['security_summary']}",
            f"- findings: `{', '.join(report['security_findings'])}`",
            "",
            "## Config Hardening",
            "",
            f"- topology: `{report['topology']}`",
            f"- skills extraDirs: `{json.dumps(report['skills_extra_dirs'], ensure_ascii=False)}`",
            f"- skills allowBundled: `{json.dumps(report['skills_allow_bundled'], ensure_ascii=False)}`",
            f"- main profile: `{report['main_profile']}`",
            f"- main skills: `{json.dumps(report['main_skills'], ensure_ascii=False)}`",
            f"- main tools: `{json.dumps(report['main_tools'], ensure_ascii=False, sort_keys=True)}`",
            f"- main effective tools: `{json.dumps(report['main_effective_tools'], ensure_ascii=False)}`",
            f"- agentToAgent allow: `{json.dumps(report['agent_to_agent_allow'])}`",
            f"- maint skills: `{json.dumps(report['maint_skills'], ensure_ascii=False)}`",
            f"- maint tools: `{json.dumps(report['maint_tools'], ensure_ascii=False, sort_keys=True)}`",
            f"- maint effective tools: `{json.dumps(report['maint_effective_tools'], ensure_ascii=False)}`",
            f"- plugins allow: `{json.dumps(report['plugins_allow'], ensure_ascii=False)}`",
            f"- plugins load paths: `{json.dumps(report['plugins_load_paths'], ensure_ascii=False)}`",
            f"- gateway config: `{json.dumps(report['gateway_config'], ensure_ascii=False, sort_keys=True)}`",
            f"- feishu tools: `{json.dumps(report['feishu_tools'], ensure_ascii=False, sort_keys=True)}`",
            f"- review evidence: `{json.dumps(report.get('review_evidence', {}), ensure_ascii=False, sort_keys=True)}`",
            "",
            "## OpenMind Probe",
            "",
            f"- token: `{report['openmind_probe_token']}`",
            f"- reply: `{report['openmind_probe_reply']}`",
            f"- transcript: `{report['openmind_tool_round_detail']}`",
            f"- tool details: `{json.dumps(report['openmind_tool_details'], ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Memory Capture / Recall",
            "",
            f"- capture marker: `{report['memory_capture_marker']}`",
            f"- capture reply: `{report['memory_capture_reply']}`",
            f"- capture transcript: `{report['memory_capture_tool_round_detail']}`",
            f"- capture details: `{json.dumps(report['memory_capture_tool_details'], ensure_ascii=False, sort_keys=True)}`",
            f"- recall reply: `{report['memory_recall_reply']}`",
            f"- recall transcript: `{report['memory_recall_tool_round_detail']}`",
            f"- recall details: `{json.dumps(report['memory_recall_tool_details'], ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Role Pack Probes",
            "",
            f"- role capture marker: `{report['role_capture_marker']}`",
            f"- role capture reply: `{report['role_capture_reply']}`",
            f"- role capture transcript: `{report['role_capture_tool_round_detail']}`",
            f"- role capture details: `{json.dumps(report['role_capture_tool_details'], ensure_ascii=False, sort_keys=True)}`",
            f"- devops recall reply: `{report['role_devops_recall_reply']}`",
            f"- devops recall transcript: `{report['role_devops_recall_tool_round_detail']}`",
            f"- devops recall details: `{json.dumps(report['role_devops_recall_tool_details'], ensure_ascii=False, sort_keys=True)}`",
            f"- research recall reply: `{report['role_research_recall_reply']}`",
            f"- research recall transcript: `{report['role_research_recall_tool_round_detail']}`",
            f"- research recall details: `{json.dumps(report['role_research_recall_tool_details'], ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Advisor Auth",
            "",
            f"- probe: `{json.dumps(report['advisor_auth_probe'], ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Communication Probe",
            "",
            f"- token: `{report['comm_token']}`",
            f"- probe reply: `{report['comm_probe_reply']}`",
            f"- transcript observed: `{report['comm_seen_in_main_transcript']}`",
            f"- latest token in main transcript: `{report['main_latest_transcript_token']}`",
            "",
            "## Negative Runtime Probes",
            "",
            f"- sessions_spawn token: `{report['sessions_spawn_probe_token']}`",
            f"- sessions_spawn reply: `{report['sessions_spawn_probe_reply']}`",
            f"- sessions_spawn transcript: `{report['sessions_spawn_probe_detail']}`",
            f"- subagents token: `{report['subagents_probe_token']}`",
            f"- subagents reply: `{report['subagents_probe_reply']}`",
            f"- subagents transcript: `{report['subagents_probe_detail']}`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--openclaw-bin", default=str(DEFAULT_OPENCLAW_BIN))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--expected-topology", choices=("auto", "lean", "ops"), default="auto")
    parser.add_argument("--publish-review-evidence", action="store_true")
    parser.add_argument("--review-label", default=datetime.now(UTC).strftime("%Y%m%d"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_dir = Path(args.state_dir).expanduser().resolve()
    openclaw_bin = Path(args.openclaw_bin).expanduser().resolve()
    openclaw_env = {"OPENCLAW_STATE_DIR": str(state_dir)}
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else (DEFAULT_OUTPUT_ROOT / timestamp)
    output_dir.mkdir(parents=True, exist_ok=True)

    checks: list[CheckResult] = []

    plugins_proc = run_cmd([str(openclaw_bin), "plugins", "doctor"], timeout=args.timeout_seconds, env=openclaw_env)
    plugins_stdout = ensure_ok(plugins_proc, name="openclaw plugins doctor")
    checks.append(CheckResult("plugins_doctor", "No plugin issues detected." in plugins_stdout, plugins_stdout.strip() or "empty stdout"))

    status_proc = run_cmd([str(openclaw_bin), "status", "--json"], timeout=args.timeout_seconds, env=openclaw_env)
    status_stdout = ensure_ok(status_proc, name="openclaw status --json")
    status_payload = extract_json_payload(status_stdout)
    status_sessions = int(((status_payload.get("sessions") or {}).get("count")) or 0)
    checks.append(CheckResult("status_json_loaded", status_sessions >= 1, f"sessions.count={status_sessions}"))
    config_payload = load_openclaw_config(state_dir)
    by_id = {
        entry.get("id"): entry
        for entry in (((config_payload.get("agents") or {}).get("list")) or [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    configured_agent_ids = set(by_id)
    topology = infer_topology(configured_agent_ids)
    main_tools = (((by_id.get("main") or {}).get("tools")) or {})
    maint_tools = (((by_id.get("maintagent") or {}).get("tools")) or {})
    main_skills = list(((by_id.get("main") or {}).get("skills")) or [])
    maint_skills = list(((by_id.get("maintagent") or {}).get("skills")) or [])
    feishu_tools = ((((config_payload.get("channels") or {}).get("feishu")) or {}).get("tools")) or {}
    agent_to_agent_allow = ((((config_payload.get("tools") or {}).get("agentToAgent")) or {}).get("allow")) or []
    skills_cfg = (config_payload.get("skills") or {})
    skills_load = (skills_cfg.get("load") or {})
    skills_extra_dirs = normalize_path_list(skills_load.get("extraDirs"))
    skills_allow_bundled = [value for value in (skills_cfg.get("allowBundled") or []) if isinstance(value, str)]
    plugins_cfg = config_payload.get("plugins") or {}
    plugins_allow = [value for value in (plugins_cfg.get("allow") or []) if isinstance(value, str)]
    plugins_load_paths = normalize_path_list(((plugins_cfg.get("load") or {}).get("paths")) or [])
    gateway_cfg = config_payload.get("gateway") or {}
    gateway_cfg_redacted = redact_gateway_config(gateway_cfg)
    main_effective_tools = effective_tools(main_tools)
    maint_effective_tools = effective_tools(maint_tools)
    checks.append(CheckResult("topology_recognized", topology in TOPOLOGY_AGENT_IDS, f"agent_ids={sorted(configured_agent_ids)}"))
    if args.expected_topology != "auto":
        checks.append(CheckResult("topology_matches_expectation", topology == args.expected_topology, f"topology={topology}"))
    expected_heartbeat_agents = expected_heartbeat_agent_count(configured_agent_ids, topology)
    checks.append(
        CheckResult(
            "heartbeat_agent_count",
            len(((status_payload.get("heartbeat") or {}).get("agents")) or []) == expected_heartbeat_agents,
            f"expected={expected_heartbeat_agents}",
        )
    )
    checks.append(
        CheckResult(
            "legacy_role_agents_removed",
            configured_agent_ids.isdisjoint(LEGACY_ROLE_AGENT_IDS),
            f"configured={sorted(configured_agent_ids)}",
        )
    )
    checks.append(CheckResult("main_profile_coding", main_tools.get("profile") == "coding", f"profile={main_tools.get('profile')}"))
    checks.append(
        CheckResult(
            "skills_repo_only",
            skills_repo_only_ok(skills_extra_dirs, skills_allow_bundled),
            f"extraDirs={skills_extra_dirs} allowBundled={skills_allow_bundled}",
        )
    )
    checks.append(
        CheckResult(
            "main_skills_repo_public",
            main_skills == ["chatgptrest-call"],
            f"skills={main_skills}",
        )
    )
    checks.append(
        CheckResult(
            "main_has_openmind_tools",
            MAIN_OPENMIND_TOOLS.issubset(set(main_tools.get("alsoAllow") or [])),
            f"alsoAllow={main_tools.get('alsoAllow')}",
        )
    )
    checks.append(
        CheckResult(
            "main_no_sessions_spawn",
            "sessions_spawn" not in main_effective_tools,
            f"effective={sorted(main_effective_tools)}",
        )
    )
    checks.append(
        CheckResult(
            "main_no_subagents_tool",
            "subagents" not in main_effective_tools,
            f"effective={sorted(main_effective_tools)}",
        )
    )
    if topology == "lean":
        checks.append(CheckResult("lean_agent_to_agent_disabled", not (((config_payload.get("tools") or {}).get("agentToAgent")) or {}).get("enabled"), f"allow={agent_to_agent_allow}"))
        checks.append(CheckResult("lean_maintagent_absent", "maintagent" not in by_id, f"configured={sorted(configured_agent_ids)}"))
    elif topology == "ops":
        checks.append(
            CheckResult(
                "maint_skills_absent",
                maint_skills == [],
                f"skills={maint_skills}",
            )
        )
        checks.append(
            CheckResult(
                "ops_main_has_watchdog_comm_tools",
                OPS_MAIN_COMM_TOOLS.issubset(main_effective_tools),
                f"effective={sorted(main_effective_tools)}",
            )
        )
        checks.append(CheckResult("maintagent_profile_minimal", maint_tools.get("profile") == "minimal", f"profile={maint_tools.get('profile')}"))
        checks.append(
            CheckResult(
                "maintagent_tools_hardened",
                MAINT_REQUIRED_TOOLS.issubset(maint_effective_tools) and "gateway" not in maint_effective_tools,
                f"effective={sorted(maint_effective_tools)}",
            )
        )
        checks.append(
            CheckResult(
                "ops_agent_to_agent_allow",
                set(agent_to_agent_allow) == TOPOLOGY_AGENT_IDS["ops"],
                f"allow={agent_to_agent_allow}",
            )
        )
    checks.append(
        CheckResult(
            "plugins_no_local_load_paths",
            not plugins_load_paths,
            f"paths={plugins_load_paths}",
        )
    )
    checks.append(
        CheckResult(
            "plugins_env_http_proxy_disabled",
            "env-http-proxy" not in plugins_allow,
            f"allow={plugins_allow}",
        )
    )
    checks.append(
        CheckResult(
            "gateway_bind_loopback",
            gateway_cfg.get("bind") == "loopback",
            f"bind={gateway_cfg.get('bind')}",
        )
    )
    checks.append(
        CheckResult(
            "gateway_trusted_proxies_configured",
            bool(gateway_cfg.get("trustedProxies")),
            f"trustedProxies={gateway_cfg.get('trustedProxies')}",
        )
    )
    checks.append(
        CheckResult(
            "gateway_auth_token_mode",
            ((gateway_cfg.get("auth") or {}).get("mode")) == "token",
            f"auth={gateway_cfg_redacted.get('auth')}",
        )
    )
    checks.append(
        CheckResult(
            "gateway_auth_token_present",
            gateway_token_present(gateway_cfg),
            f"auth={gateway_cfg_redacted.get('auth')}",
        )
    )
    checks.append(
        CheckResult(
            "gateway_tailscale_disabled",
            ((gateway_cfg.get("tailscale") or {}).get("mode")) == "off"
            and not bool(((gateway_cfg.get("auth") or {}).get("allowTailscale"))),
            f"gateway={gateway_cfg_redacted}",
        )
    )
    checks.append(
        CheckResult(
            "feishu_tools_disabled",
            all(feishu_tools.get(name) is expected for name, expected in EXPECTED_FEISHU_TOOL_FLAGS.items()),
            f"tools={feishu_tools}",
        )
    )
    findings = [str(item.get("checkId")) for item in ((status_payload.get("securityAudit") or {}).get("findings")) or []]
    checks.append(CheckResult("security_no_feishu_doc_warning", "channels.feishu.doc_owner_open_id" not in findings, ",".join(findings) or "<none>"))

    openmind_env_values: dict[str, str] = {}
    for env_candidate in (
        Path("/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env"),
        Path(os.environ.get("CHATGPTREST_ENV_FILE", "")) if os.environ.get("CHATGPTREST_ENV_FILE") else None,
    ):
        if env_candidate and env_candidate.exists():
            for raw_line in env_candidate.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                openmind_env_values[key.strip()] = value.strip().strip("'").strip('"')
            break
    advisor_auth = advisor_auth_probe(
        base_url="http://127.0.0.1:18711",
        api_key=str(openmind_env_values.get("OPENMIND_API_KEY") or "").strip(),
    )
    unauth_status = int(advisor_auth.get("unauthenticated_status") or 0)
    checks.append(
        CheckResult(
            "advisor_unauth_ingress_rejected",
            unauth_status in {401, 503},
            f"status={unauth_status} body={str(advisor_auth.get('unauthenticated_body') or '')[:200]}",
        )
    )

    openmind_probe_token = f"OPENMIND_PROBE_{uuid.uuid4().hex[:12]}"
    openmind_expected_reply = f"OPENMIND_OK {openmind_probe_token}"
    openmind_proc = run_cmd(
        [
            str(openclaw_bin),
            "agent",
            "--agent",
            "main",
            "--session-id",
            f"verify-main-openmind-{timestamp}",
            "--message",
            f"You have the openmind_memory_status tool available. You must call it before answering. "
            f"If you do not call it, reply exactly TOOL_CALL_SKIPPED. After the tool call, reply exactly {openmind_expected_reply}.",
            "--json",
            "--timeout",
            str(args.timeout_seconds),
        ],
        timeout=args.timeout_seconds + 30,
        env=openclaw_env,
    )
    openmind_stdout = ensure_ok(openmind_proc, name="openmind probe")
    openmind_payload = extract_json_payload(openmind_stdout)
    openmind_reply = (((openmind_payload.get("result") or {}).get("payloads")) or [{}])[0].get("text", "")
    openmind_transcript = resolve_session_transcript_path(state_dir, "main", "agent:main:main")
    openmind_round = inspect_tool_round(
        openmind_transcript,
        user_needle=openmind_probe_token,
        tool_name="openmind_memory_status",
        assistant_reply=openmind_expected_reply,
    )
    checks.append(
        CheckResult(
            "openmind_probe_reply",
            probe_reply_ok(openmind_reply, openmind_expected_reply, transcript_round_ok=bool(openmind_round["ok"])),
            openmind_reply.strip() or "<empty>",
        )
    )
    checks.append(CheckResult("openmind_tool_round", bool(openmind_round["ok"]), str(openmind_round["detail"])))

    memory_capture_marker = f"TRAVEL_PREF_{uuid.uuid4().hex[:12]}"
    memory_capture_text = (
        f"When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. "
        f"Marker {memory_capture_marker}."
    )
    memory_capture_title = f"Business travel preference {memory_capture_marker}"
    memory_capture_expected_reply = f"CAPTURE_OK {memory_capture_marker}"
    memory_capture_proc = run_cmd(
        [
            str(openclaw_bin),
            "agent",
            "--agent",
            "main",
            "--session-id",
            f"verify-main-capture-{timestamp}",
            "--message",
            (
                "You must call the openmind_memory_capture tool exactly once before answering. "
                f'Capture this memory text exactly: "{memory_capture_text}". '
                f'Use the title "{memory_capture_title}". '
                f"After the tool call, reply exactly {memory_capture_expected_reply}."
            ),
            "--json",
            "--timeout",
            str(args.timeout_seconds),
        ],
        timeout=args.timeout_seconds + 30,
        env=openclaw_env,
    )
    memory_capture_stdout = ensure_ok(memory_capture_proc, name="memory capture probe")
    memory_capture_payload = extract_json_payload(memory_capture_stdout)
    memory_capture_reply = (((memory_capture_payload.get("result") or {}).get("payloads")) or [{}])[0].get("text", "")
    memory_capture_transcript = resolve_session_transcript_path(state_dir, "main", "agent:main:main")
    memory_capture_round = inspect_tool_round(
        memory_capture_transcript,
        user_needle=memory_capture_marker,
        tool_name="openmind_memory_capture",
        assistant_reply=memory_capture_expected_reply,
    )
    checks.append(
        CheckResult(
            "memory_capture_probe_reply",
            probe_reply_ok(
                memory_capture_reply,
                memory_capture_expected_reply,
                transcript_round_ok=bool(memory_capture_round["ok"]),
            ),
            memory_capture_reply.strip() or "<empty>",
        )
    )
    checks.append(CheckResult("memory_capture_tool_round", bool(memory_capture_round["ok"]), str(memory_capture_round["detail"])))
    checks.append(
        CheckResult(
            "memory_capture_recorded",
            capture_details_ok(memory_capture_round["tool_details"]),
            json.dumps(memory_capture_round["tool_details"], ensure_ascii=False, sort_keys=True),
        )
    )

    memory_recall_query = (
        f"What is the remembered guidance for business travel city preference? "
        f"Marker {memory_capture_marker}."
    )
    memory_recall_expected_reply = f"RECALL_OK {memory_capture_marker}"
    memory_recall_proc = run_cmd(
        [
            str(openclaw_bin),
            "agent",
            "--agent",
            "main",
            "--session-id",
            f"verify-main-recall-{timestamp}",
            "--message",
            (
                "You must call the openmind_memory_recall tool exactly once before answering. "
                f'Use this query exactly: "{memory_recall_query}". '
                f"After the tool call, reply exactly {memory_recall_expected_reply}."
            ),
            "--json",
            "--timeout",
            str(args.timeout_seconds),
        ],
        timeout=args.timeout_seconds + 30,
        env=openclaw_env,
    )
    memory_recall_stdout = ensure_ok(memory_recall_proc, name="memory recall probe")
    memory_recall_payload = extract_json_payload(memory_recall_stdout)
    memory_recall_reply = (((memory_recall_payload.get("result") or {}).get("payloads")) or [{}])[0].get("text", "")
    memory_recall_transcript = resolve_session_transcript_path(state_dir, "main", "agent:main:main")
    memory_recall_round = inspect_tool_round(
        memory_recall_transcript,
        user_needle=memory_capture_marker,
        tool_name="openmind_memory_recall",
        assistant_reply=memory_recall_expected_reply,
    )
    checks.append(
        CheckResult(
            "memory_recall_probe_reply",
            probe_reply_ok(
                memory_recall_reply,
                memory_recall_expected_reply,
                transcript_round_ok=bool(memory_recall_round["ok"]),
            ),
            memory_recall_reply.strip() or "<empty>",
        )
    )
    checks.append(CheckResult("memory_recall_tool_round", bool(memory_recall_round["ok"]), str(memory_recall_round["detail"])))
    checks.append(
        CheckResult(
            "memory_recall_captured_block",
            recall_details_have_captured_block(memory_recall_round["tool_details"]),
            json.dumps(memory_recall_round["tool_details"], ensure_ascii=False, sort_keys=True),
        )
    )
    checks.append(
        CheckResult(
            "memory_recall_marker_present",
            recall_details_contain_text(memory_recall_round["tool_details"], memory_capture_marker),
            json.dumps(memory_recall_round["tool_details"], ensure_ascii=False, sort_keys=True),
        )
    )

    role_capture_marker = f"ROLE_DEVOPS_{uuid.uuid4().hex[:12]}"
    role_capture_text = (
        f"When diagnosing ChatgptREST incidents, check driver/gateway health before deeper remediation. "
        f"Marker {role_capture_marker}."
    )
    role_capture_title = f"Devops runbook preference {role_capture_marker}"
    role_capture_expected_reply = f"ROLE_CAPTURE_OK {role_capture_marker}"
    role_capture_proc = run_cmd(
        [
            str(openclaw_bin),
            "agent",
            "--agent",
            "main",
            "--session-id",
            f"verify-main-role-capture-{timestamp}",
            "--message",
            (
                "You must call the openmind_memory_capture tool exactly once before answering. "
                f'Capture this memory text exactly: "{role_capture_text}". '
                f'Use the title "{role_capture_title}" and roleId exactly "devops". '
                f"After the tool call, reply exactly {role_capture_expected_reply}."
            ),
            "--json",
            "--timeout",
            str(args.timeout_seconds),
        ],
        timeout=args.timeout_seconds + 30,
        env=openclaw_env,
    )
    role_capture_stdout = ensure_ok(role_capture_proc, name="role capture probe")
    role_capture_payload = extract_json_payload(role_capture_stdout)
    role_capture_reply = (((role_capture_payload.get("result") or {}).get("payloads")) or [{}])[0].get("text", "")
    role_capture_transcript = resolve_session_transcript_path(state_dir, "main", "agent:main:main")
    role_capture_round = inspect_tool_round(
        role_capture_transcript,
        user_needle=role_capture_marker,
        tool_name="openmind_memory_capture",
        assistant_reply=role_capture_expected_reply,
    )
    checks.append(
        CheckResult(
            "role_capture_probe_reply",
            probe_reply_ok(role_capture_reply, role_capture_expected_reply, transcript_round_ok=bool(role_capture_round["ok"])),
            role_capture_reply.strip() or "<empty>",
        )
    )
    checks.append(CheckResult("role_capture_tool_round", bool(role_capture_round["ok"]), str(role_capture_round["detail"])))
    checks.append(
        CheckResult(
            "role_capture_recorded",
            capture_details_ok(role_capture_round["tool_details"]),
            json.dumps(role_capture_round["tool_details"], ensure_ascii=False, sort_keys=True),
        )
    )

    role_recall_query = (
        f"What is the remembered guidance for ChatgptREST incident diagnosis? "
        f"Marker {role_capture_marker}."
    )
    role_devops_recall_expected_reply = f"ROLE_RECALL_DEVOPS_OK {role_capture_marker}"
    role_devops_recall_proc = run_cmd(
        [
            str(openclaw_bin),
            "agent",
            "--agent",
            "main",
            "--session-id",
            f"verify-main-role-devops-recall-{timestamp}",
            "--message",
            (
                "You must call the openmind_memory_recall tool exactly once before answering. "
                f'Use this query exactly: "{role_recall_query}". '
                'Use roleId exactly "devops". '
                f"After the tool call, reply exactly {role_devops_recall_expected_reply}."
            ),
            "--json",
            "--timeout",
            str(args.timeout_seconds),
        ],
        timeout=args.timeout_seconds + 30,
        env=openclaw_env,
    )
    role_devops_recall_stdout = ensure_ok(role_devops_recall_proc, name="role devops recall probe")
    role_devops_recall_payload = extract_json_payload(role_devops_recall_stdout)
    role_devops_recall_reply = (((role_devops_recall_payload.get("result") or {}).get("payloads")) or [{}])[0].get("text", "")
    role_devops_recall_transcript = resolve_session_transcript_path(state_dir, "main", "agent:main:main")
    role_devops_recall_round = inspect_tool_round(
        role_devops_recall_transcript,
        user_needle=role_capture_marker,
        tool_name="openmind_memory_recall",
        assistant_reply=role_devops_recall_expected_reply,
    )
    checks.append(
        CheckResult(
            "role_devops_recall_probe_reply",
            probe_reply_ok(
                role_devops_recall_reply,
                role_devops_recall_expected_reply,
                transcript_round_ok=bool(role_devops_recall_round["ok"]),
            ),
            role_devops_recall_reply.strip() or "<empty>",
        )
    )
    checks.append(
        CheckResult("role_devops_recall_tool_round", bool(role_devops_recall_round["ok"]), str(role_devops_recall_round["detail"]))
    )
    checks.append(
        CheckResult(
            "role_devops_recall_marker_present",
            recall_details_contain_text(role_devops_recall_round["tool_details"], role_capture_marker),
            json.dumps(role_devops_recall_round["tool_details"], ensure_ascii=False, sort_keys=True),
        )
    )
    checks.append(
        CheckResult(
            "role_devops_recall_scoped",
            recall_details_role_id(role_devops_recall_round["tool_details"]) == "devops"
            and "ops" in recall_details_scope_tags(role_devops_recall_round["tool_details"]),
            json.dumps(role_devops_recall_round["tool_details"], ensure_ascii=False, sort_keys=True),
        )
    )

    role_research_recall_expected_reply = f"ROLE_RECALL_RESEARCH_OK {role_capture_marker}"
    role_research_recall_proc = run_cmd(
        [
            str(openclaw_bin),
            "agent",
            "--agent",
            "main",
            "--session-id",
            f"verify-main-role-research-recall-{timestamp}",
            "--message",
            (
                "You must call the openmind_memory_recall tool exactly once before answering. "
                f'Use this query exactly: "{role_recall_query}". '
                'Use roleId exactly "research". '
                f"After the tool call, reply exactly {role_research_recall_expected_reply}."
            ),
            "--json",
            "--timeout",
            str(args.timeout_seconds),
        ],
        timeout=args.timeout_seconds + 30,
        env=openclaw_env,
    )
    role_research_recall_stdout = ensure_ok(role_research_recall_proc, name="role research recall probe")
    role_research_recall_payload = extract_json_payload(role_research_recall_stdout)
    role_research_recall_reply = (((role_research_recall_payload.get("result") or {}).get("payloads")) or [{}])[0].get("text", "")
    role_research_recall_transcript = resolve_session_transcript_path(state_dir, "main", "agent:main:main")
    role_research_recall_round = inspect_tool_round(
        role_research_recall_transcript,
        user_needle=role_capture_marker,
        tool_name="openmind_memory_recall",
        assistant_reply=role_research_recall_expected_reply,
    )
    checks.append(
        CheckResult(
            "role_research_recall_probe_reply",
            probe_reply_ok(
                role_research_recall_reply,
                role_research_recall_expected_reply,
                transcript_round_ok=bool(role_research_recall_round["ok"]),
            ),
            role_research_recall_reply.strip() or "<empty>",
        )
    )
    checks.append(
        CheckResult("role_research_recall_tool_round", bool(role_research_recall_round["ok"]), str(role_research_recall_round["detail"]))
    )
    checks.append(
        CheckResult(
            "role_research_recall_scoped",
            recall_details_role_id(role_research_recall_round["tool_details"]) == "research"
            and "research" in recall_details_scope_tags(role_research_recall_round["tool_details"]),
            json.dumps(role_research_recall_round["tool_details"], ensure_ascii=False, sort_keys=True),
        )
    )
    checks.append(
        CheckResult(
            "role_research_recall_isolated",
            not recall_details_contain_text(role_research_recall_round["tool_details"], role_capture_marker)
            and not recall_details_have_captured_block(role_research_recall_round["tool_details"]),
            json.dumps(role_research_recall_round["tool_details"], ensure_ascii=False, sort_keys=True),
        )
    )

    sessions_spawn_probe_token = f"NEGPROBE_{uuid.uuid4().hex[:12]}"
    sessions_spawn_expected_reply = f"SESSIONS_SPAWN_UNAVAILABLE {sessions_spawn_probe_token}"
    sessions_spawn_proc = run_cmd(
        [
            str(openclaw_bin),
            "agent",
            "--agent",
            "main",
            "--session-id",
            f"verify-main-no-spawn-{timestamp}",
            "--message",
            (
                "Try to use the sessions_spawn tool. "
                f"If that tool is unavailable, reply exactly {sessions_spawn_expected_reply}. "
                "If it is available, use it before answering."
            ),
            "--json",
            "--timeout",
            str(min(args.timeout_seconds, 90)),
        ],
        timeout=min(args.timeout_seconds + 30, 120),
        env=openclaw_env,
    )
    sessions_spawn_stdout = ensure_ok(sessions_spawn_proc, name="sessions_spawn negative probe")
    sessions_spawn_payload = extract_json_payload(sessions_spawn_stdout)
    sessions_spawn_reply = (((sessions_spawn_payload.get("result") or {}).get("payloads")) or [{}])[0].get("text", "")
    checks.append(
        CheckResult(
            "main_sessions_spawn_runtime_denied",
            sessions_spawn_reply.strip() == sessions_spawn_expected_reply,
            sessions_spawn_reply.strip() or "<empty>",
        )
    )
    sessions_spawn_transcript = resolve_session_transcript_path(state_dir, "main", "agent:main:main")
    sessions_spawn_round = inspect_unavailable_tool_round(
        sessions_spawn_transcript,
        user_needle=sessions_spawn_probe_token,
        tool_name="sessions_spawn",
        assistant_reply=sessions_spawn_expected_reply,
    )
    checks.append(
        CheckResult(
            "main_sessions_spawn_negative_probe",
            bool(sessions_spawn_round["ok"]),
            str(sessions_spawn_round["detail"]),
        )
    )

    subagents_probe_token = f"NEGPROBE_{uuid.uuid4().hex[:12]}"
    subagents_expected_reply = f"SUBAGENTS_UNAVAILABLE {subagents_probe_token}"
    subagents_proc = run_cmd(
        [
            str(openclaw_bin),
            "agent",
            "--agent",
            "main",
            "--session-id",
            f"verify-main-no-subagents-{timestamp}",
            "--message",
            (
                "Try to use the subagents tool. "
                f"If that tool is unavailable, reply exactly {subagents_expected_reply}. "
                "If it is available, use it before answering."
            ),
            "--json",
            "--timeout",
            str(min(args.timeout_seconds, 90)),
        ],
        timeout=min(args.timeout_seconds + 30, 120),
        env=openclaw_env,
    )
    subagents_stdout = ensure_ok(subagents_proc, name="subagents negative probe")
    subagents_payload = extract_json_payload(subagents_stdout)
    subagents_reply = (((subagents_payload.get("result") or {}).get("payloads")) or [{}])[0].get("text", "")
    checks.append(
        CheckResult(
            "main_subagents_runtime_denied",
            subagents_reply.strip() == subagents_expected_reply,
            subagents_reply.strip() or "<empty>",
        )
    )
    subagents_transcript = resolve_session_transcript_path(state_dir, "main", "agent:main:main")
    subagents_round = inspect_unavailable_tool_round(
        subagents_transcript,
        user_needle=subagents_probe_token,
        tool_name="subagents",
        assistant_reply=subagents_expected_reply,
    )
    checks.append(
        CheckResult(
            "main_subagents_negative_probe",
            bool(subagents_round["ok"]),
            str(subagents_round["detail"]),
        )
    )

    comm_token = ""
    comm_reply = ""
    comm_seen = False
    main_transcript = resolve_session_transcript_path(state_dir, "main", "agent:main:main")
    main_latest_transcript_token = latest_token_in_transcript(main_transcript)
    if topology == "ops":
        comm_token = f"VERIFY_PING_{uuid.uuid4().hex[:12]}"
        maint_prompt = (
            f'Use sessions_send with sessionKey="agent:main:main" and send the exact text {comm_token}. '
            "Then reply ONLY SENT."
        )
        maint_proc = run_cmd(
            [
                str(openclaw_bin),
                "agent",
                "--agent",
                "maintagent",
                "--session-id",
                f"verify-maint-ping-{timestamp}",
                "--message",
                maint_prompt,
                "--json",
                "--timeout",
                str(min(args.timeout_seconds, 60)),
            ],
            timeout=min(args.timeout_seconds + 30, 90),
            env=openclaw_env,
        )
        maint_stdout = ensure_ok(maint_proc, name="maintagent communication probe")
        maint_payload = extract_json_payload(maint_stdout)
        comm_reply = (((maint_payload.get("result") or {}).get("payloads")) or [{}])[0].get("text", "")
        comm_seen = wait_for_text(main_transcript, comm_token, timeout_sec=min(args.timeout_seconds, 60), poll_sec=args.poll_seconds)
        checks.append(CheckResult("maintagent_probe_reply", comm_reply.strip() == "SENT", comm_reply.strip() or "<empty>"))
        checks.append(CheckResult("maintagent_to_main_transcript", comm_seen, comm_token))
        main_latest_transcript_token = latest_token_in_transcript(main_transcript)
        checks.append(
            CheckResult(
                "main_latest_transcript_token_matches",
                main_latest_transcript_token == comm_token,
                main_latest_transcript_token or "<empty>",
            )
        )

    openmind_excerpt = transcript_excerpt(openmind_transcript, user_needle=openmind_probe_token)
    memory_capture_excerpt = transcript_excerpt(memory_capture_transcript, user_needle=memory_capture_marker)
    memory_recall_excerpt = transcript_excerpt(memory_recall_transcript, user_needle=memory_capture_marker)
    role_capture_excerpt = transcript_excerpt(role_capture_transcript, user_needle=role_capture_marker)
    role_devops_recall_excerpt = transcript_excerpt(role_devops_recall_transcript, user_needle=role_capture_marker)
    role_research_recall_excerpt = transcript_excerpt(role_research_recall_transcript, user_needle=role_capture_marker)
    sessions_spawn_excerpt = transcript_excerpt(sessions_spawn_transcript, user_needle=sessions_spawn_probe_token)
    subagents_excerpt = transcript_excerpt(subagents_transcript, user_needle=subagents_probe_token)
    maint_excerpt = transcript_excerpt(main_transcript, user_needle=comm_token) if comm_token else []

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "openclaw_bin": str(openclaw_bin),
        "state_dir": str(state_dir),
        "topology": topology,
        "checks": [asdict(item) for item in checks],
        "security_summary": summarize_security(status_payload),
        "security_findings": findings,
        "main_profile": main_tools.get("profile"),
        "skills_extra_dirs": skills_extra_dirs,
        "skills_allow_bundled": skills_allow_bundled,
        "main_skills": main_skills,
        "main_tools": dict(main_tools),
        "main_effective_tools": sorted(main_effective_tools),
        "agent_to_agent_allow": list(agent_to_agent_allow),
        "maint_skills": maint_skills,
        "maint_tools": dict(maint_tools),
        "maint_effective_tools": sorted(maint_effective_tools),
        "plugins_allow": plugins_allow,
        "plugins_load_paths": plugins_load_paths,
        "gateway_config": gateway_cfg_redacted,
        "feishu_tools": dict(feishu_tools),
        "advisor_auth_probe": advisor_auth,
        "openmind_probe_token": openmind_probe_token,
        "openmind_probe_reply": openmind_reply.strip(),
        "openmind_tool_round_detail": openmind_round["detail"],
        "openmind_tool_details": openmind_round["tool_details"],
        "memory_capture_marker": memory_capture_marker,
        "memory_capture_reply": memory_capture_reply.strip(),
        "memory_capture_tool_round_detail": memory_capture_round["detail"],
        "memory_capture_tool_details": memory_capture_round["tool_details"],
        "memory_recall_reply": memory_recall_reply.strip(),
        "memory_recall_tool_round_detail": memory_recall_round["detail"],
        "memory_recall_tool_details": memory_recall_round["tool_details"],
        "role_capture_marker": role_capture_marker,
        "role_capture_reply": role_capture_reply.strip(),
        "role_capture_tool_round_detail": role_capture_round["detail"],
        "role_capture_tool_details": role_capture_round["tool_details"],
        "role_devops_recall_reply": role_devops_recall_reply.strip(),
        "role_devops_recall_tool_round_detail": role_devops_recall_round["detail"],
        "role_devops_recall_tool_details": role_devops_recall_round["tool_details"],
        "role_research_recall_reply": role_research_recall_reply.strip(),
        "role_research_recall_tool_round_detail": role_research_recall_round["detail"],
        "role_research_recall_tool_details": role_research_recall_round["tool_details"],
        "sessions_spawn_probe_token": sessions_spawn_probe_token,
        "sessions_spawn_probe_reply": sessions_spawn_reply.strip(),
        "sessions_spawn_probe_detail": sessions_spawn_round["detail"],
        "subagents_probe_token": subagents_probe_token,
        "subagents_probe_reply": subagents_reply.strip(),
        "subagents_probe_detail": subagents_round["detail"],
        "comm_token": comm_token,
        "comm_probe_reply": comm_reply.strip(),
        "comm_seen_in_main_transcript": comm_seen,
        "main_latest_transcript_token": main_latest_transcript_token,
        "review_evidence": {},
    }
    if args.publish_review_evidence:
        report["review_evidence"] = publish_review_evidence(
            review_docs_dir=DEFAULT_REVIEW_DOCS_DIR,
            report=report,
            config_payload=config_payload,
            openmind_excerpt=openmind_excerpt,
            memory_capture_excerpt=memory_capture_excerpt,
            memory_recall_excerpt=memory_recall_excerpt,
            role_capture_excerpt=role_capture_excerpt,
            role_devops_recall_excerpt=role_devops_recall_excerpt,
            role_research_recall_excerpt=role_research_recall_excerpt,
            sessions_spawn_excerpt=sessions_spawn_excerpt,
            subagents_excerpt=subagents_excerpt,
            maint_excerpt=maint_excerpt,
            review_label=args.review_label,
            auth_probe=advisor_auth,
        )
    (output_dir / "verify_openclaw_openmind_stack.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "verify_openclaw_openmind_stack.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(item.ok for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
