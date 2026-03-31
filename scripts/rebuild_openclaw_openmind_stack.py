#!/usr/bin/env python3
"""Rebuild local OpenClaw state around latest upstream + OpenMind plugins."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import shlex
import shutil
import subprocess
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chatgptrest.kernel.skill_manager import get_canonical_registry

REPO_ROOT = Path(__file__).resolve().parents[1]
FINBOT_CLI_PATH = (REPO_ROOT / "ops" / "openclaw_finbot.py").resolve()
FINBOT_CLI_CMD = f"python3 {shlex.quote(str(FINBOT_CLI_PATH))}"
STATE_DIR = (Path.home() / ".openclaw").resolve()
DEFAULT_OPENCLAW_BIN = Path(os.environ.get("OPENCLAW_BIN", str(Path.home() / ".local" / "bin" / "openclaw"))).expanduser()
DEFAULT_OPENMIND_BASE_URL = os.environ.get("OPENMIND_BASE_URL", "http://127.0.0.1:18711").rstrip("/")
DEFAULT_CODEX_AUTH_PATH = Path(os.environ.get("CODEX_AUTH_PATH", str(Path.home() / ".codex" / "auth.json"))).expanduser()
DEFAULT_CHATGPTREST_ENV_FILE = Path(os.environ.get("CHATGPTREST_ENV_FILE", f"/home/{os.environ.get('USER', 'yuanhaizhou')}/.config/chatgptrest/chatgptrest.env")).expanduser()
DEFAULT_SYSTEMD_USER_DIR = Path(f"/home/{os.environ.get('USER', 'yuanhaizhou')}/.config/systemd/user").expanduser()
DEFAULT_OPENCLAW_GATEWAY_DROPIN_DIR = DEFAULT_SYSTEMD_USER_DIR / "openclaw-gateway.service.d"
PINNED_DINGTALK_SPEC = os.environ.get("OPENCLAW_DINGTALK_SPEC", "@openclaw-china/dingtalk@2026.3.8-3")
PINNED_DINGTALK_VERSION = os.environ.get("OPENCLAW_DINGTALK_VERSION", "2026.3.8-3")
PINNED_DINGTALK_INTEGRITY = os.environ.get(
    "OPENCLAW_DINGTALK_INTEGRITY",
    "sha512-fq+32sGd0DO+7kOBsmPeTs8iVb0HciTluqIRdoizNd1GSVSVyYx3f4dYpWJaypUvdXzhf4xhOf43QrBZICxS+g==",
)
LEGACY_MANAGED_CHANNEL_HEARTBEAT_VISIBILITY = {
    "showOk": False,
    "showAlerts": False,
    "useIndicator": True,
}
OPENMIND_PLUGIN_IDS = (
    "openmind-advisor",
    "openmind-graph",
    "openmind-memory",
    "openmind-telemetry",
)
DEFAULT_MINIMAX_MODEL_REF = "minimax/MiniMax-M2.5"
DEFAULT_QWEN_MODEL_REF = "qwen-coding-plan/qwen3-coder-plus"
DEFAULT_GEMINI_MODEL_REF = "google-gemini-cli/gemini-2.5-pro"
DEFAULT_TOPOLOGY = os.environ.get("OPENCLAW_OPENMIND_TOPOLOGY", "lean").strip().lower() or "lean"
TOPOLOGY_AGENT_IDS = {
    "lean": ("main",),
    "ops": ("main", "maintagent", "finbot"),
}
VOLATILE_SESSION_AGENT_IDS = ("maintagent",)
MAIN_OPENMIND_TOOLS = (
    "openmind_memory_status",
    "openmind_memory_recall",
    "openmind_memory_capture",
    "openmind_graph_query",
    "openmind_advisor_ask",
)
MAIN_LEAN_TOOL_ADDITIONS = MAIN_OPENMIND_TOOLS
MAIN_OPS_TOOL_ADDITIONS = (
    "sessions_send",
    "sessions_list",
    "sessions_history",
    *MAIN_OPENMIND_TOOLS,
)
MAINT_TOOL_ADDITIONS = (
    "sessions_send",
    "sessions_list",
)
FINBOT_TOOL_ADDITIONS = (
    "sessions_send",
    "sessions_list",
    "sessions_history",
    *MAIN_OPENMIND_TOOLS,
)
AUTOORCH_TOOL_ADDITIONS = FINBOT_TOOL_ADDITIONS
MAIN_TOOL_DENY = (
    "group:automation",
    "group:ui",
    "image",
    "sessions_spawn",
    "subagents",
)
MAIN_LEAN_TOOL_DENY = (
    *MAIN_TOOL_DENY,
    "sessions_send",
    "sessions_list",
    "sessions_history",
)
FINBOT_TOOL_DENY = (
    "group:ui",
    "image",
    "sessions_spawn",
    "subagents",
)
AUTOORCH_TOOL_DENY = FINBOT_TOOL_DENY
DEFAULT_SESSION_MAINTENANCE = {
    "mode": "enforce",
    "pruneAfter": "7d",
    "maxEntries": 500,
    "rotateBytes": "10mb",
}
DEFAULT_SANDBOX = {
    "mode": "non-main",
    "scope": "session",
    "workspaceAccess": "none",
    "sessionToolsVisibility": "all",
}
AGENT_SANDBOX_OVERRIDES = {
    "maintagent": {
        "mode": "all",
        "scope": "agent",
        "workspaceAccess": "none",
    },
    "finbot": {
        "mode": "all",
        "scope": "agent",
        "workspaceAccess": "rw",
    },
}
AGENT_SANDBOX_OVERRIDES["autoorch"] = AGENT_SANDBOX_OVERRIDES["finbot"]
LOCAL_PLUGIN_PROVENANCE_PATHS: dict[str, Path] = {}

@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    workspace: str
    model: str
    tool_profile: str = "coding"
    tool_allow: tuple[str, ...] = ()
    tool_also_allow: tuple[str, ...] = ()
    tool_deny: tuple[str, ...] = ()
    name: str | None = None
    skills: tuple[str, ...] = ()
    skill_bundles: tuple[str, ...] = ()
    allow_agents: tuple[str, ...] = ()
    heartbeat: dict[str, Any] | None = None
    sandbox: dict[str, Any] | None = None


AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        agent_id="main",
        workspace="/vol1/1000/openclaw-workspaces/main",
        model=DEFAULT_MINIMAX_MODEL_REF,
        tool_profile="coding",
        tool_also_allow=MAIN_LEAN_TOOL_ADDITIONS,
        tool_deny=MAIN_LEAN_TOOL_DENY,
        name="Main",
        skill_bundles=("general_core",),
        heartbeat={
            "every": "30m",
            "target": "none",
            "lightContext": True,
            "activeHours": {"start": "08:00", "end": "24:00", "timezone": "Asia/Shanghai"},
        },
    ),
    AgentSpec(
        agent_id="maintagent",
        workspace="/vol1/1000/openclaw-workspaces/maintagent",
        model=DEFAULT_MINIMAX_MODEL_REF,
        name="Maint",
        tool_profile="minimal",
        tool_also_allow=MAINT_TOOL_ADDITIONS,
        skill_bundles=("maint_core",),
        sandbox=AGENT_SANDBOX_OVERRIDES["maintagent"],
        heartbeat={
            "every": "1h",
            "target": "none",
            "lightContext": True,
            "prompt": (
                "Read HEARTBEAT.md if it exists and follow it strictly. "
                "Check OpenClaw gateway health, OpenMind health, and Feishu channel readiness. "
                "Stay read-only; do not use exec, process, or shell commands for routine health checks. "
                "Prefer session status/list over ad-hoc shell probing. "
                "Ignore the legacy chatgptrest-* orch/worker topology in this rebuilt baseline. "
                "Never run ops/openclaw_orch_agent.py --reconcile unless main explicitly asks about that old stack. "
                'If you find an actionable issue, notify `main` via `sessions_send` with `sessionKey="agent:main:main"` and a concise summary. '
                "Otherwise reply HEARTBEAT_OK."
            ),
            "activeHours": {"start": "08:00", "end": "24:00", "timezone": "Asia/Shanghai"},
        },
    ),
    AgentSpec(
        agent_id="finbot",
        workspace="/vol1/1000/openclaw-workspaces/finbot",
        model=DEFAULT_MINIMAX_MODEL_REF,
        name="Finbot",
        tool_profile="coding",
        tool_also_allow=FINBOT_TOOL_ADDITIONS,
        tool_deny=FINBOT_TOOL_DENY,
        skill_bundles=("research_core",),
        sandbox=AGENT_SANDBOX_OVERRIDES["finbot"],
        heartbeat={
            "every": "6h",
            "target": "none",
            "lightContext": True,
            "prompt": (
                "Read HEARTBEAT.md if it exists and follow it strictly. "
                f"Run `{FINBOT_CLI_CMD} dashboard-refresh --format json` to refresh the dashboard control plane. "
                f"Inspect pending inbox items with `{FINBOT_CLI_CMD} inbox-list --format json --limit 10`. "
                "If there is a net-new actionable inbox item, send a concise summary to `main` via `sessions_send` with "
                '`sessionKey="agent:main:main"`. Do not run broad discovery sweeps or theme batch research during heartbeat. '
                "If refresh is clean and nothing new is actionable, reply HEARTBEAT_OK."
            ),
            "activeHours": {"start": "08:00", "end": "24:00", "timezone": "Asia/Shanghai"},
        },
    ),
)

HEARTBEATS = {
    "main": """# Main Heartbeat

- Review pending user follow-ups and background work.
- Use OpenMind tools first when memory, context, or graph awareness matters.
- Treat this as the primary workbench; prefer direct execution, skills, and ACP over resurrecting old role-agent lanes.
- If `maintagent` is enabled, treat it as a watchdog lane rather than a general task worker.
- If `finbot` is enabled, treat it as the default execution lane for investment research work.
- For theme scans, KOL/source sweeps, watchlist refreshes, opportunity discovery, multi-ticker comparisons, and ongoing market tracking, delegate to `finbot` via `sessions_send` with `sessionKey="agent:finbot:main"` instead of doing the work directly in `main`.
- Keep `main` focused on triage, prioritization, synthesis, and user-facing judgment after `finbot` runs.
- Do not replay stale tasks from old sessions.
- If nothing needs attention, reply HEARTBEAT_OK.
""",
    "maintagent": """# Maintenance Heartbeat

- Check OpenClaw gateway health.
- Check OpenMind advisor API health at http://127.0.0.1:18711.
- Stay read-only; do not use `exec`, `process`, or shell commands for routine health checks.
- Prefer `session_status` and `sessions_list` over ad-hoc probing.
- Check that Feishu channel config remains loadable.
- Do not call Feishu doc/wiki tools during heartbeat; stick to gateway/channel health and concise escalation.
- Ignore legacy `chatgptrest-*` orch/worker drift in this rebuilt baseline.
- Never run `ops/openclaw_orch_agent.py --reconcile` during heartbeat.
- If there is an actionable degradation, send a concise note to `main` via `sessions_send` with `sessionKey="agent:main:main"`.
- If everything is healthy, reply HEARTBEAT_OK.
""",
    "finbot": (
        "# Finbot Heartbeat\n\n"
        f"- Refresh the dashboard control-plane projection with `{FINBOT_CLI_CMD} dashboard-refresh --format json`.\n"
        f"- Inspect pending inbox items with `{FINBOT_CLI_CMD} inbox-list --format json --limit 10`.\n"
        '- Escalate only net-new actionable inbox deltas to `main` via `sessions_send` with `sessionKey="agent:main:main"`.\n'
        "- Do not run theme-wide discovery, KOL sweeps, or theme batch research during heartbeat.\n"
        "- Keep the queue quiet; if refresh is healthy and nothing changed materially, reply HEARTBEAT_OK.\n"
    ),
}

WORKSPACE_COMMON_FILES = {
    "USER.md": """# USER.md

- Name: Yuanhaizhou
- Preferred language: 中文优先
- Timezone: Asia/Shanghai
- Working style: 直接、可执行、少废话；期待你先自己查清楚再汇报。
- Primary systems:
  - OpenClaw shell / gateway
  - OpenMind / ChatgptREST cognition backend
  - Feishu / DingTalk channels

## Current intent

- The shell should stay close to upstream OpenClaw.
- OpenMind is the cognition substrate and long-term memory path.
- Keep the shell lean; do not re-grow the old half-finished role-agent topology.
""",
    "SOUL.md": """# SOUL.md

- Be direct.
- Do the work before talking about the work.
- Prefer stable automation over one-off manual fixes.
- When you hand work back to `main`, make it short, concrete, and decision-ready.
""",
}


def _workspace_identity(spec: AgentSpec) -> str:
    labels = {
        "main": ("Main", "orchestrator", "calm / decisive"),
        "maintagent": ("Maint", "watchdog", "quiet / risk-aware"),
        "finbot": ("Finbot", "investment research scout", "quiet / methodical"),
    }
    name, creature, vibe = labels[spec.agent_id]
    return (
        "# IDENTITY.md\n\n"
        f"- Name: {name}\n"
        f"- Role: {creature}\n"
        f"- Vibe: {vibe}\n"
        "- Mission: serve the main agent and the user through reliable execution.\n"
    )


def _workspace_tools(spec: AgentSpec) -> str:
    shared = [
        "- OpenClaw CLI: `/home/yuanhaizhou/.local/bin/openclaw`",
        "- OpenMind / ChatgptREST API: `http://127.0.0.1:18711`",
        "- Gateway service: `systemctl --user status openclaw-gateway.service`",
        "- API service: `systemctl --user status chatgptrest-api.service`",
    ]
    role_specific = {
        "main": [
            "- Prefer `openmind_memory_status`, `openmind_memory_recall`, and `openmind_graph_query` before delegating.",
            "- Use explicit role packs for business context: pass `roleId=devops` or `roleId=research` to OpenMind tools instead of inventing extra persistent agents.",
            "- Prefer direct execution, ACP, and skills/workflows over resurrecting old planning/research/runtime role agents.",
            "- If `maintagent` exists in the current topology, use `sessions_send` / `sessions_list` / `sessions_history` for watchdog coordination.",
            '- If `finbot` exists in the current topology, use `sessions_send` with `sessionKey="agent:finbot:main"` for investment research execution.',
            "- Treat `finbot` as the default lane for watchlist scouting, theme radar, KOL/source sweeps, ticker/theme comparisons, and recurring market-monitoring work.",
            "- Keep `main` on triage, prioritization, synthesis, and final user-facing judgment; do not spend main-context tokens on routine investing sweeps when `finbot` can run them.",
            "- Keep OpenClaw close to upstream and push cognition/memory into OpenMind.",
        ],
        "maintagent": [
            "- Use health/readiness checks first; do not touch Feishu doc/wiki tools in heartbeats.",
            "- Stay read-only for routine checks; do not use `exec`, `process`, or shell probes in heartbeats.",
            "- Prefer `session_status` and `sessions_list` for readiness checks.",
            '- Escalate to `main` via `sessions_send` with `sessionKey="agent:main:main"` only when there is an actionable degradation.',
            "- Do not reconcile or resurrect legacy `chatgptrest-*` orch agents unless `main` explicitly requests that old stack.",
        ],
        "finbot": [
            f"- Prefer `{FINBOT_CLI_CMD} dashboard-refresh --format json` for projection refreshes.",
            f"- Prefer `{FINBOT_CLI_CMD} watchlist-scout --format json` for finagent-driven watchlist scouting.",
            f"- Prefer `{FINBOT_CLI_CMD} theme-radar-scout --format json` for new candidate discovery.",
            f"- Prefer `{FINBOT_CLI_CMD} theme-batch-run --format json` for scheduled multi-theme research passes.",
            f"- Use `{FINBOT_CLI_CMD} inbox-list --format json` and `inbox-ack` for queue hygiene.",
            '- Escalate to `main` via `sessions_send` with `sessionKey="agent:main:main"` only for net-new actionable items.',
        ],
    }
    body = "\n".join(shared + role_specific[spec.agent_id])
    return "# TOOLS.md\n\n" + body + "\n"


def _workspace_agents(spec: AgentSpec) -> str:
    blocks = {
        "main": """# AGENTS.md

## Startup

1. Read `SOUL.md`, `USER.md`, `ROLE_PACKS.md`, and today/yesterday memory.
2. Read `HEARTBEAT.md`.
3. Treat this workspace as the primary human-facing agent.

## Operating rules

- Use OpenMind tools first when memory, context, or graph awareness matters.
- Use explicit role packs when the task has a business context:
  - `devops` for ChatgptREST / OpenClaw / infra / driver / ops work
  - `research` for evidence-first analysis work
- Prefer direct execution, ACP, and skills/workflows over persistent role-agent fan-out.
- Do not assume automatic role routing exists; choose the role explicitly when you need it.
- Do not assume `planning`, `research-orch`, or `openclaw-orch` exist.
- If `maintagent` exists in this topology, use it for health/watchdog communication rather than general task delegation.
- If `finbot` exists in this topology, treat it as the default execution lane for investment-research work.
- Delegate to `finbot` via `sessions_send` with `sessionKey="agent:finbot:main"` when the user asks for:
  - theme scans or theme updates
  - watchlist refreshes
  - KOL/source sweeps
  - opportunity discovery
  - multi-ticker / multi-expression comparisons
  - recurring market-monitoring work
- Keep the work in `main` only when the user is asking for:
  - triage or prioritization
  - cross-theme synthesis
  - final judgment / recommendation
  - a quick conceptual answer that does not require running the research lane
- Do not resurrect old half-finished tasks just because they appear in stale transcripts.
""",
        "maintagent": """# AGENTS.md

## Role

- You are the maintenance watchdog for `main`.
- Default mode is read-mostly: probe, summarize, and escalate.
- Only recommend or execute state-changing actions when there is a concrete incident and the path is already approved.
- Stay read-only for routine checks; prefer `session_status` and `sessions_list`.
- Ignore the legacy `chatgptrest-*` orch/worker topology unless `main` explicitly asks about that old stack.
- Never run `ops/openclaw_orch_agent.py --reconcile` as an autonomous fix.

## Handoff

- Send terse health deltas to `main` via `sessions_send` with `sessionKey="agent:main:main"`.
- `HEARTBEAT_OK` is correct when nothing new is actionable.
""",
        "finbot": """# AGENTS.md

## Role

- You are the background investment research scout for `main`.
- Your job is to refresh projections, run scheduled watchlist/theme scans, execute theme batches, and write concise inbox items.
- Prefer deterministic scripts under `""" + str(FINBOT_CLI_PATH) + """` over ad-hoc shell work.
- Do not become a general-purpose research agent during heartbeat or cron turns.

## Handoff

- Inbox is the default handoff path: write files under `artifacts/finbot/inbox/pending/`.
- Only use `sessions_send` to `main` for net-new actionable deltas.
- `HEARTBEAT_OK` is correct when refresh completed and nothing changed materially.
""",
    }
    return blocks[spec.agent_id]


def _workspace_bootstrap(spec: AgentSpec) -> str:
    return (
        "# BOOTSTRAP.md\n\n"
        "This workspace is managed by `scripts/rebuild_openclaw_openmind_stack.py`.\n\n"
        f"- Agent: `{spec.agent_id}`\n"
        f"- Workspace: `{spec.workspace}`\n"
        "- These role files are not a personality sandbox; they are operating instructions for a persistent service agent.\n"
    )


def _workspace_role_packs(spec: AgentSpec) -> str:
    if spec.agent_id != "main":
        if spec.agent_id == "finbot":
            return (
                "# ROLE_PACKS.md\n\n"
                "- This workspace does not host user-facing role packs.\n"
                "- Stay in investment research automation scope: dashboard refresh, watchlist scouting, theme radar discovery, theme batch research, inbox hygiene, and safe escalations.\n"
            )
        return (
            "# ROLE_PACKS.md\n\n"
            "- This workspace does not host user-facing role packs.\n"
            "- Stay in watchdog/readiness scope unless `main` explicitly asks for a different lane.\n"
        )
    return """# ROLE_PACKS.md

Role packs are explicit business-context overlays for `main`. They are not extra persistent agents.

## Available roles

- `devops`
  - Scope: ChatgptREST / OpenClaw / infra / driver / ops
  - Memory namespace: `devops`
  - KB hint tags: `chatgptrest`, `ops`, `infra`, `driver`, `mcp`, `runbook`
- `research`
  - Scope: evidence-first analysis and deep research
  - Memory namespace: `research`
  - KB hint tags: `research`, `finagent`, `education`, `analysis`, `market`

## How to use

- OpenMind memory recall:
  - call `openmind_memory_recall` with `roleId="devops"` or `roleId="research"`
- OpenMind memory capture:
  - call `openmind_memory_capture` with `roleId="devops"` or `roleId="research"`
- OpenMind advisor:
  - call `openmind_advisor_ask` with `roleId="devops"` or `roleId="research"`

## Rules

- Choose the role explicitly; do not assume automatic role routing exists.
- `source.agent` remains the component/emitter identity; `source.role` carries the business role.
- KB role scope is currently hint-first, not a hard deny filter. Missing tags must not silently collapse useful context.
"""


def normalize_topology(topology: str) -> str:
    normalized = topology.strip().lower()
    if normalized not in TOPOLOGY_AGENT_IDS:
        valid = ", ".join(sorted(TOPOLOGY_AGENT_IDS))
        raise ValueError(f"unsupported topology {topology!r}; expected one of: {valid}")
    return normalized


def active_agent_specs(topology: str) -> tuple[AgentSpec, ...]:
    topology_name = normalize_topology(topology)
    selected_ids = TOPOLOGY_AGENT_IDS[topology_name]
    by_id = {spec.agent_id: spec for spec in AGENTS}
    specs: list[AgentSpec] = []
    for agent_id in selected_ids:
        spec = by_id[agent_id]
        if agent_id == "main":
            specs.append(
                replace(
                    spec,
                    tool_profile="coding",
                    tool_also_allow=MAIN_OPS_TOOL_ADDITIONS if topology_name == "ops" else MAIN_LEAN_TOOL_ADDITIONS,
                    tool_deny=MAIN_TOOL_DENY if topology_name == "ops" else MAIN_LEAN_TOOL_DENY,
                    allow_agents=(),
                )
            )
        else:
            specs.append(spec)
    return tuple(specs)


def workspace_files_for(spec: AgentSpec) -> dict[str, str]:
    files = dict(WORKSPACE_COMMON_FILES)
    files["AGENTS.md"] = _workspace_agents(spec)
    files["BOOTSTRAP.md"] = _workspace_bootstrap(spec)
    files["IDENTITY.md"] = _workspace_identity(spec)
    files["ROLE_PACKS.md"] = _workspace_role_packs(spec)
    files["TOOLS.md"] = _workspace_tools(spec)
    heartbeat = HEARTBEATS.get(spec.agent_id)
    if heartbeat:
        files["HEARTBEAT.md"] = heartbeat
    return files


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip("'").strip('"')
    return values


def ensure_gateway_openmind_env_dropin(
    *,
    env_file: Path = DEFAULT_CHATGPTREST_ENV_FILE,
    dropin_dir: Path = DEFAULT_OPENCLAW_GATEWAY_DROPIN_DIR,
) -> Path | None:
    values = read_env_file(env_file)
    if "OPENMIND_API_KEY" not in values and "OPENMIND_AUTH_MODE" not in values:
        return None
    dropin_dir.mkdir(parents=True, exist_ok=True)
    dropin_path = dropin_dir / "20-openmind-cognitive.conf"
    dropin_path.write_text(
        "[Service]\n"
        f"EnvironmentFile=-{env_file}\n",
        encoding="utf-8",
    )
    return dropin_path


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    return True


def essential_backup(state_dir: Path, backup_root: Path) -> dict[str, Any]:
    backup_root.mkdir(parents=True, exist_ok=False)
    os.chmod(backup_root, 0o700)
    copied: list[str] = []
    targets = [
        "openclaw.json",
        "exec-approvals.json",
        "credentials",
        "devices",
        "identity",
        "secrets",
        "cron/jobs.json",
        "cron/jobs.json.bak",
        "subagents/runs.json",
    ]
    for rel in targets:
        src = state_dir / rel
        dst = backup_root / rel
        if copy_if_exists(src, dst):
            copied.append(rel)
    auth_dst_root = backup_root / "agents"
    for auth_path in sorted(state_dir.glob("agents/*/agent/auth-profiles.json")):
        rel = auth_path.relative_to(state_dir)
        copy_if_exists(auth_path, backup_root / rel)
        copied.append(str(rel))
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "state_dir": str(state_dir),
        "copied": copied,
    }
    write_json(backup_root / "manifest.json", manifest)
    return manifest


def prune_unmanaged_agent_dirs(state_dir: Path, backup_root: Path, managed_agent_ids: set[str]) -> list[str]:
    agents_root = state_dir / "agents"
    if not agents_root.is_dir():
        return []
    moved: list[str] = []
    trash_root = backup_root / "unmanaged_agents"
    for agent_dir in sorted(agents_root.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name in managed_agent_ids:
            continue
        destination = trash_root / agent_dir.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(agent_dir), str(destination))
        moved.append(agent_dir.name)
    return moved


def prune_unmanaged_cron_jobs(state_dir: Path, managed_agent_ids: set[str]) -> list[str]:
    jobs_path = state_dir / "cron" / "jobs.json"
    if not jobs_path.is_file():
        return []
    payload = load_json(jobs_path)
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return []
    kept_jobs: list[dict[str, Any]] = []
    removed_ids: list[str] = []
    for job in jobs:
        if not isinstance(job, dict):
            kept_jobs.append(job)
            continue
        agent_id = str(job.get("agentId") or "").strip()
        if agent_id and agent_id not in managed_agent_ids:
            removed_ids.append(str(job.get("id") or agent_id))
            continue
        kept_jobs.append(job)
    if removed_ids:
        payload["jobs"] = kept_jobs
        write_json(jobs_path, payload)
    return removed_ids


def ensure_auth_profiles(state_dir: Path, source_agent_id: str, target_agent_ids: list[str]) -> None:
    source = state_dir / "agents" / source_agent_id / "agent" / "auth-profiles.json"
    if not source.exists():
        raise FileNotFoundError(f"missing source auth store: {source}")
    for agent_id in target_agent_ids:
        target = state_dir / "agents" / agent_id / "agent" / "auth-profiles.json"
        if target.exists():
            continue
        copy_if_exists(source, target)


def _decode_jwt_claims(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return {}


def sync_codex_auth_profiles(state_dir: Path, canonical_auth_path: Path, target_agent_ids: list[str]) -> list[str]:
    if not canonical_auth_path.exists():
        return []
    auth_blob = load_json(canonical_auth_path)
    tokens = auth_blob.get("tokens") or {}
    access = str(tokens.get("access_token") or "").strip()
    refresh = str(tokens.get("refresh_token") or "").strip()
    if not access or not refresh:
        return []
    claims = _decode_jwt_claims(access)
    auth_claims = claims.get("https://api.openai.com/auth") or {}
    account_id = str(auth_claims.get("chatgpt_account_id") or "").strip()
    expires = int(claims.get("exp") or 0) * 1000 if claims.get("exp") else None
    if not target_agent_ids:
        return []
    source_agent_id = "main" if "main" in target_agent_ids else target_agent_ids[0]
    source_path = state_dir / "agents" / source_agent_id / "agent" / "auth-profiles.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"version": 1, "profiles": {}}
    if source_path.exists() and not source_path.is_symlink():
        payload = load_json(source_path)
        payload.setdefault("version", 1)
        payload.setdefault("profiles", {})
    profiles = payload["profiles"]
    current = dict(profiles.get("openai-codex:default") or {})
    profiles["openai-codex:default"] = {
        "type": "oauth",
        "provider": "openai-codex",
        "access": access,
        "refresh": refresh,
        "expires": expires or current.get("expires"),
        "accountId": account_id or current.get("accountId"),
    }
    write_json(source_path, payload)
    updated: list[str] = [source_agent_id]
    for agent_id in list(dict.fromkeys(target_agent_ids)):
        if agent_id == source_agent_id:
            continue
        target = state_dir / "agents" / agent_id / "agent" / "auth-profiles.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            target.unlink()
        shutil.copy2(source_path, target)
        updated.append(agent_id)
    return updated


def ensure_gateway_token_file(state_dir: Path, gateway_cfg: dict[str, Any]) -> Path | None:
    auth_cfg = gateway_cfg.get("auth") or {}
    if str(auth_cfg.get("mode") or "").strip() != "token":
        return None
    token = str(auth_cfg.get("token") or "").strip()
    if not token:
        return None
    token_path = state_dir / "gateway.token"
    token_path.write_text(token + "\n", encoding="utf-8")
    os.chmod(token_path, 0o600)
    return token_path


def plugin_fingerprint(plugin_dir: Path) -> str:
    digest = hashlib.sha256()
    for rel_path in (
        "openclaw.plugin.json",
        "package.json",
        "index.ts",
        "README.md",
    ):
        path = plugin_dir / rel_path
        digest.update(rel_path.encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def upsert_plugin_install_record(
    installs: dict[str, Any],
    *,
    plugin_id: str,
    source_path: Path,
    install_path: Path,
) -> None:
    installs[plugin_id] = {
        "source": "path",
        "sourcePath": str(source_path),
        "installPath": str(install_path),
    }


def sync_plugin_extension(*, source_path: Path, install_path: Path) -> bool:
    install_path.parent.mkdir(parents=True, exist_ok=True)
    if install_path.is_symlink():
        install_path.unlink()
    elif install_path.exists():
        if plugin_fingerprint(install_path) == plugin_fingerprint(source_path):
            return False
        if install_path.is_file():
            install_path.unlink()
        else:
            shutil.rmtree(install_path)
    shutil.copytree(source_path, install_path)
    return True


def ensure_plugin_dependencies(plugin_dir: Path) -> None:
    typebox_pkg = plugin_dir / "node_modules" / "@sinclair" / "typebox" / "package.json"
    if typebox_pkg.is_file():
        return
    subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund", "--omit=dev"],
        cwd=str(plugin_dir),
        check=True,
        capture_output=True,
        text=True,
    )


def install_openmind_plugins(state_dir: Path, *, openclaw_bin: Path) -> None:
    config_path = state_dir / "openclaw.json"
    config = load_json(config_path)
    installs = ((((config.get("plugins") or {}).get("installs")) or {}))
    installs_changed = False
    for plugin_id in OPENMIND_PLUGIN_IDS:
        source_path = (REPO_ROOT / "openclaw_extensions" / plugin_id).resolve()
        record = installs.get(plugin_id) or {}
        recorded_source = Path(str(record.get("sourcePath") or "")).expanduser().resolve() if record.get("sourcePath") else None
        live_install_path = state_dir / "extensions" / plugin_id
        synced = sync_plugin_extension(source_path=source_path, install_path=live_install_path)
        upsert_plugin_install_record(
            installs,
            plugin_id=plugin_id,
            source_path=source_path,
            install_path=live_install_path,
        )
        ensure_plugin_dependencies(live_install_path)
        if synced or recorded_source != source_path or str(record.get("installPath") or "") != str(live_install_path):
            installs_changed = True
    if installs_changed:
        plugins_cfg = dict(config.get("plugins") or {})
        plugins_cfg["installs"] = installs
        config["plugins"] = plugins_cfg
        write_json(config_path, config)


def ensure_workspaces(specs: tuple[AgentSpec, ...]) -> None:
    for spec in specs:
        workspace = Path(spec.workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        for filename, content in workspace_files_for(spec).items():
            (workspace / filename).write_text(content, encoding="utf-8")


def prune_workspace_skill_symlink_escapes(specs: tuple[AgentSpec, ...]) -> list[str]:
    removed: list[str] = []
    for spec in specs:
        skills_dir = Path(spec.workspace) / "skills"
        if not skills_dir.is_dir():
            continue
        workspace_root = Path(spec.workspace).resolve()
        for path in sorted(skills_dir.iterdir()):
            if not path.is_symlink():
                continue
            try:
                target = path.resolve(strict=True)
            except FileNotFoundError:
                path.unlink()
                removed.append(str(path))
                continue
            if target.is_relative_to(workspace_root):
                continue
            path.unlink()
            removed.append(str(path))
    return removed


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _normalize_plugin_path(path_value: Any) -> str | None:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    return str(Path(raw).expanduser().resolve())


def normalize_plugin_load_paths(load_cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(load_cfg)
    paths: list[str] = []
    for raw in load_cfg.get("paths") or []:
        normalized_path = _normalize_plugin_path(raw)
        if normalized_path and normalized_path not in paths:
            paths.append(normalized_path)
    if paths:
        normalized["paths"] = paths
    else:
        normalized.pop("paths", None)
    return normalized


def normalize_plugin_installs(installs_cfg: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for plugin_id, record in installs_cfg.items():
        if not isinstance(record, dict):
            normalized[plugin_id] = record
            continue
        clean = {
            key: value
            for key, value in dict(record).items()
            if key in {"source", "spec", "version", "integrity", "installPath", "sourcePath"}
        }
        for key in ("installPath", "sourcePath"):
            normalized_path = _normalize_plugin_path(clean.get(key))
            if normalized_path:
                clean[key] = normalized_path
        normalized[plugin_id] = clean
    return normalized


def _normalize_feishu_account(account: dict[str, Any], *, default_bot_name: str | None = None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key in (
        "enabled",
        "appId",
        "appSecret",
        "appSecretFile",
        "botName",
        "domain",
        "typingIndicator",
        "resolveSenderNames",
        "connectionMode",
        "verificationToken",
        "dmPolicy",
        "groupPolicy",
        "allowFrom",
        "groupAllowFrom",
        "requireMention",
    ):
        if key in account:
            clean[key] = account[key]
    secret_file = str(clean.get("appSecretFile") or "").strip()
    if secret_file:
        clean["appSecretFile"] = secret_file
        clean.pop("appSecret", None)
    if default_bot_name:
        clean.setdefault("botName", default_bot_name)
    return clean


def normalize_feishu_tools_config(raw: Any) -> dict[str, bool]:
    clean = {
        "doc": False,
        "chat": False,
        "wiki": False,
        "drive": False,
        "perm": False,
        "scopes": False,
    }
    if not isinstance(raw, dict):
        return clean
    for key in tuple(clean.keys()):
        if key in raw:
            clean[key] = bool(raw[key])
    return clean


def normalize_feishu_config(raw: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key in (
        "enabled",
        "streaming",
        "dmPolicy",
        "groupPolicy",
        "defaultAccount",
        "connectionMode",
        "webhookHost",
        "verificationToken",
        "typingIndicator",
        "resolveSenderNames",
        "domain",
        "heartbeat",
    ):
        if key in raw:
            normalized[key] = raw[key]
    normalized["tools"] = normalize_feishu_tools_config(raw.get("tools"))

    accounts = raw.get("accounts") or {}
    normalized_accounts: dict[str, Any] = {}
    default = accounts.get("default")
    if isinstance(default, dict):
        clean_default = _normalize_feishu_account(default, default_bot_name="OpenClaw")
        if clean_default:
            normalized_accounts["default"] = clean_default
    main = accounts.get("main")
    if isinstance(main, dict) and "default" not in normalized_accounts:
        clean_main = _normalize_feishu_account(main, default_bot_name="OpenClaw")
        if clean_main:
            normalized_accounts["default"] = clean_main
    research = accounts.get("research")
    if isinstance(research, dict):
        clean_research = _normalize_feishu_account(research)
        if clean_research:
            # Secondary role-agent channels should not be open human-facing inboxes
            # in the default single-user baseline.
            clean_research["enabled"] = False
            clean_research["dmPolicy"] = "disabled"
            clean_research["groupPolicy"] = "disabled"
            clean_research["requireMention"] = True
            clean_research.pop("allowFrom", None)
            clean_research.pop("groupAllowFrom", None)
            normalized_accounts["research"] = clean_research
    if normalized_accounts:
        normalized["accounts"] = normalized_accounts
    if normalized.get("defaultAccount") not in normalized_accounts:
        normalized.pop("defaultAccount", None)
    if "defaultAccount" not in normalized and len(normalized_accounts) >= 2 and "default" in normalized_accounts:
        normalized["defaultAccount"] = "default"
    return normalized


def normalize_channel_defaults(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(raw)
    heartbeat = normalized.get("heartbeat")
    if not isinstance(heartbeat, dict):
        return normalized

    relevant = {
        key: heartbeat.get(key)
        for key in ("showOk", "showAlerts", "useIndicator")
        if key in heartbeat
    }
    if relevant == LEGACY_MANAGED_CHANNEL_HEARTBEAT_VISIBILITY and set(heartbeat.keys()) <= set(relevant.keys()):
        normalized.pop("heartbeat", None)
    return normalized


def build_models_section() -> dict[str, Any]:
    shared_env = read_env_file(DEFAULT_CHATGPTREST_ENV_FILE)
    qwen_base_url = (
        str(shared_env.get("QWEN_BASE_URL") or "").strip()
        or str(os.environ.get("QWEN_BASE_URL") or "").strip()
        or "https://coding.dashscope.aliyuncs.com/v1"
    )
    minimax_base_url = (
        str(shared_env.get("MINIMAX_ANTHROPIC_BASE_URL") or "").strip()
        or str(os.environ.get("MINIMAX_ANTHROPIC_BASE_URL") or "").strip()
        or "https://api.minimaxi.com/anthropic"
    )
    return {
        "mode": "merge",
        "providers": {
            "minimax": {
                "baseUrl": minimax_base_url,
                "apiKey": "${MINIMAX_API_KEY}",
                "api": "anthropic-messages",
                "models": [
                    {
                        "id": "MiniMax-M2.5",
                        "name": "MiniMax M2.5",
                        "reasoning": True,
                        "input": ["text"],
                        "cost": {"input": 0.3, "output": 1.2, "cacheRead": 0.03, "cacheWrite": 0.12},
                        "contextWindow": 200000,
                        "maxTokens": 8192,
                    }
                ],
            },
            "qwen-coding-plan": {
                "baseUrl": qwen_base_url,
                "apiKey": "${QWEN_API_KEY}",
                "api": "openai-completions",
                "models": [
                    {
                        "id": "qwen3-coder-plus",
                        "name": "Qwen 3 Coder Plus",
                        "reasoning": True,
                        "input": ["text"],
                        "cost": {"input": 0.0, "output": 0.0, "cacheRead": 0.0, "cacheWrite": 0.0},
                        "contextWindow": 262144,
                        "maxTokens": 8192,
                    }
                ],
            },
        },
    }


def build_agents_section(current_cfg: dict[str, Any], *, topology: str) -> dict[str, Any]:
    registry = get_canonical_registry()
    current_defaults = (((current_cfg.get("agents") or {}).get("defaults")) or {})
    active_specs = active_agent_specs(topology)
    defaults = {
        "model": {
            "primary": DEFAULT_MINIMAX_MODEL_REF,
            "fallbacks": [DEFAULT_QWEN_MODEL_REF, DEFAULT_GEMINI_MODEL_REF],
        },
        "models": {
            DEFAULT_MINIMAX_MODEL_REF: {"alias": "minimax"},
            DEFAULT_QWEN_MODEL_REF: {"alias": "qwen"},
            DEFAULT_GEMINI_MODEL_REF: {"alias": "gemini"},
        },
        "userTimezone": "Asia/Shanghai",
        "workspace": "/vol1/1000/openclaw-workspaces/main",
        "cliBackends": current_defaults.get("cliBackends") or {},
        "memorySearch": current_defaults.get("memorySearch") or {},
        "compaction": current_defaults.get("compaction") or {"mode": "safeguard"},
        "thinkingDefault": current_defaults.get("thinkingDefault") or "high",
        "maxConcurrent": current_defaults.get("maxConcurrent") or 4,
        "sandbox": {
            **DEFAULT_SANDBOX,
            **dict(((current_defaults.get("sandbox") or {}))),
            **{
                "mode": DEFAULT_SANDBOX["mode"],
                "scope": DEFAULT_SANDBOX["scope"],
                "workspaceAccess": DEFAULT_SANDBOX["workspaceAccess"],
                "sessionToolsVisibility": DEFAULT_SANDBOX["sessionToolsVisibility"],
            },
        },
        "subagents": {
            "maxConcurrent": 6,
            "thinking": "high",
            "runTimeoutSeconds": 1200,
        },
    }
    list_payload: list[dict[str, Any]] = []
    for spec in active_specs:
        entry: dict[str, Any] = {
            "id": spec.agent_id,
            "workspace": spec.workspace,
            "model": spec.model,
            "tools": {
                "profile": spec.tool_profile,
                **({"allow": list(spec.tool_allow)} if spec.tool_allow else {}),
                **({"alsoAllow": list(spec.tool_also_allow)} if spec.tool_also_allow else {}),
                **({"deny": list(spec.tool_deny)} if spec.tool_deny else {}),
            },
        }
        if spec.name:
            entry["name"] = spec.name
        if spec.agent_id == "main":
            entry["default"] = True
        runtime_skills = list(spec.skills)
        if spec.skill_bundles:
            entry["skillBundles"] = list(spec.skill_bundles)
            for skill_id in registry.available_skill_ids_for_bundles(
                spec.skill_bundles,
                platform="openclaw",
                runtime_local_only=True,
            ):
                if skill_id not in runtime_skills:
                    runtime_skills.append(skill_id)
        if runtime_skills:
            entry["skills"] = runtime_skills
        if spec.allow_agents:
            entry["subagents"] = {"allowAgents": list(spec.allow_agents)}
        if spec.heartbeat:
            entry["heartbeat"] = spec.heartbeat
        if spec.sandbox:
            entry["sandbox"] = dict(spec.sandbox)
        list_payload.append(entry)
    return {"defaults": defaults, "list": list_payload}


def _active_runtime_local_skill_dirs(active_specs: tuple[AgentSpec, ...], registry) -> list[str]:
    """Materialize repo-local skill dirs only when active bundles require them."""

    runtime_local_skill_ids: set[str] = set()
    for spec in active_specs:
        if not spec.skill_bundles:
            continue
        runtime_local_skill_ids.update(
            registry.available_skill_ids_for_bundles(
                spec.skill_bundles,
                platform="openclaw",
                runtime_local_only=True,
            )
        )
    if not runtime_local_skill_ids:
        return []
    return [str((REPO_ROOT / "skills-src").resolve())]


def build_cron_jobs(*, topology: str) -> dict[str, Any]:
    # Background finbot discovery now runs via deterministic systemd timers.
    # Keep OpenClaw cron clean so the gateway no longer depends on an LLM lane
    # for unattended research execution.
    return {"version": 1, "jobs": []}


def write_managed_cron_jobs(state_dir: Path, *, topology: str) -> Path:
    jobs_path = state_dir / "cron" / "jobs.json"
    write_json(jobs_path, build_cron_jobs(topology=topology))
    return jobs_path


def build_plugins_section(current_cfg: dict[str, Any], *, openmind_base_url: str) -> dict[str, Any]:
    current_plugins = current_cfg.get("plugins") or {}
    openmind_env = read_env_file(DEFAULT_CHATGPTREST_ENV_FILE)
    openmind_api_key = str(openmind_env.get("OPENMIND_API_KEY") or "").strip()
    main_model_ref = next((spec.model for spec in AGENTS if spec.agent_id == "main"), "")
    default_provider, _, default_model = main_model_ref.partition("/")
    openmind_endpoint: dict[str, Any] = {"baseUrl": openmind_base_url}
    if openmind_api_key:
        openmind_endpoint["apiKey"] = openmind_api_key
    # The rebuilt baseline must be reproducible from repo-owned defaults instead
    # of inheriting arbitrary plugin load/install state from the current host.
    load = normalize_plugin_load_paths({})
    installs = normalize_plugin_installs({})
    if (((current_cfg.get("channels") or {}).get("dingtalk") or {}).get("enabled", False)):
        dingtalk_install = dict(installs.get("dingtalk") or {})
        dingtalk_install["source"] = "npm"
        dingtalk_install["spec"] = PINNED_DINGTALK_SPEC
        dingtalk_install["version"] = PINNED_DINGTALK_VERSION
        dingtalk_install["integrity"] = PINNED_DINGTALK_INTEGRITY
        installs["dingtalk"] = dingtalk_install
    entries = {
        "feishu": {"enabled": True},
        "dingtalk": {"enabled": bool((((current_cfg.get("channels") or {}).get("dingtalk") or {}).get("enabled", False)))},
        "acpx": {
            "enabled": True,
            "config": {
                "permissionMode": "approve-all",
                "nonInteractivePermissions": "fail",
                "queueOwnerTtlSeconds": 5,
            },
        },
        "diffs": {"enabled": True},
        "google-gemini-cli-auth": {"enabled": True},
        "openmind-advisor": {
            "enabled": True,
            "config": {
                "endpoint": dict(openmind_endpoint),
                "defaultGoalHint": "",
            },
        },
        "openmind-graph": {
            "enabled": True,
            "config": {
                "endpoint": dict(openmind_endpoint),
                "defaultRepo": "ChatgptREST",
                "defaultScopes": ["personal_graph", "repo_graph"],
            },
        },
        "openmind-memory": {
            "enabled": True,
            "config": {
                "endpoint": dict(openmind_endpoint),
                "autoRecall": True,
                "autoCapture": True,
                "graphScopes": ["personal"],
                "domainTags": ["openclaw", "openmind"],
                "cacheTtlSeconds": 180,
                "tokenBudget": 4000,
                "repo": "ChatgptREST",
            },
        },
        "openmind-telemetry": {
            "enabled": True,
            "config": {
                "endpoint": dict(openmind_endpoint),
                "enabled": True,
                "ignoreOwnTools": True,
                "repoName": "ChatgptREST",
                "repoPath": str(REPO_ROOT),
                "taskRefPrefix": "openclaw",
                "defaultProvider": default_provider,
                "defaultModel": default_model,
                "executorKind": "openclaw.agent",
            },
        },
    }
    removed_plugin_ids = {"google-antigravity-auth"}
    allow = sorted(set(entries.keys()) - removed_plugin_ids)
    return {
        "enabled": True,
        "allow": allow,
        "load": load,
        "entries": entries,
        "slots": {"memory": "openmind-memory"},
        "installs": installs,
    }


def build_gateway_section(current_cfg: dict[str, Any]) -> dict[str, Any]:
    current_gateway = current_cfg.get("gateway") or {}
    auth_cfg = current_gateway.get("auth") or {}
    token = (
        str(os.environ.get("OPENCLAW_GATEWAY_TOKEN") or "").strip()
        or str(auth_cfg.get("token") or "").strip()
        or secrets.token_hex(32)
    )
    gateway: dict[str, Any] = {
        "port": int(current_gateway.get("port") or 18789),
        "mode": str(current_gateway.get("mode") or "local"),
        "bind": "loopback",
        "trustedProxies": ["127.0.0.1/32", "::1/128"],
        "controlUi": {
            "allowInsecureAuth": False,
        },
        "auth": {
            "mode": "token",
            "allowTailscale": False,
            "token": token,
        },
        "tailscale": {
            "mode": "off",
            "resetOnExit": False,
        },
    }
    return gateway


def build_bindings(current_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    channels = current_cfg.get("channels") or {}
    bindings: list[dict[str, Any]] = []
    if (channels.get("dingtalk") or {}).get("enabled"):
        bindings.append({"type": "route", "agentId": "main", "match": {"channel": "dingtalk", "accountId": "default"}})
    feishu = normalize_feishu_config(channels.get("feishu") or {})
    accounts = feishu.get("accounts") or {}
    primary_account = str(feishu.get("defaultAccount") or "").strip() or ("default" if "default" in accounts else ("main" if "main" in accounts else ""))
    if primary_account:
        bindings.append({"type": "route", "agentId": "main", "match": {"channel": "feishu", "accountId": primary_account}})
    return bindings


def build_config(
    current_cfg: dict[str, Any],
    *,
    openmind_base_url: str = DEFAULT_OPENMIND_BASE_URL,
    topology: str = DEFAULT_TOPOLOGY,
) -> dict[str, Any]:
    registry = get_canonical_registry()
    topology_name = normalize_topology(topology)
    active_specs = active_agent_specs(topology_name)
    active_agent_ids = [spec.agent_id for spec in active_specs]
    current_channels = current_cfg.get("channels") or {}
    current_tools = current_cfg.get("tools") or {}
    current_skills = current_cfg.get("skills") or {}
    current_browser = current_cfg.get("browser")
    current_messages = current_cfg.get("messages")
    channels = {
        "defaults": normalize_channel_defaults(dict((current_channels.get("defaults") or {}))),
    }
    if current_channels.get("feishu"):
        channels["feishu"] = normalize_feishu_config(current_channels["feishu"])
    if current_channels.get("dingtalk"):
        channels["dingtalk"] = current_channels["dingtalk"]
    load = {"extraDirs": _active_runtime_local_skill_dirs(active_specs, registry)}
    config: dict[str, Any] = {
        "models": build_models_section(),
        "gateway": build_gateway_section(current_cfg),
        "session": {
            "agentToAgent": {"maxPingPongTurns": 0},
            "maintenance": dict(DEFAULT_SESSION_MAINTENANCE),
        },
        "tools": {
            "profile": "coding",
            "agentToAgent": {
                "enabled": topology_name == "ops",
                "allow": active_agent_ids if topology_name == "ops" else [],
            },
            "sessions": {"visibility": "all"},
            "exec": {
                "host": "gateway",
                "security": "full",
                "ask": "on-miss",
                "timeoutSec": 1200,
                "notifyOnExit": True,
            },
        },
        "acp": {
            "enabled": True,
            "dispatch": {"enabled": True},
            "backend": "acpx",
            "defaultAgent": "codex",
            "allowedAgents": ["codex", "gemini", "claude"],
        },
        "skills": {
            "allowBundled": sorted(
                bundle.bundle_id
                for bundle in registry.bundles.values()
                if bundle.supports_platform("openclaw")
            ),
            "load": load,
            "install": current_skills.get("install") or {"nodeManager": "npm"},
        },
        "plugins": build_plugins_section(current_cfg, openmind_base_url=openmind_base_url),
        "channels": channels,
        "bindings": build_bindings(current_cfg),
        "agents": build_agents_section(current_cfg, topology=topology_name),
        "messages": {"ackReactionScope": "group-mentions"},
    }
    if current_browser:
        config["browser"] = current_browser
    return config


def prune_volatile_artifacts(state_dir: Path) -> list[str]:
    removed: list[str] = []
    patterns = [
        "_quarantine",
        "_disabled-extensions",
        "workspace.legacy-*",
        "workspace-planning.legacy-*",
        "openclaw.json.bak*",
    ]
    for pattern in patterns:
        for path in state_dir.glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(str(path.relative_to(state_dir)))
    for path in state_dir.glob("agents/*/sessions/*.jsonl.deleted.*"):
        path.unlink()
        removed.append(str(path.relative_to(state_dir)))
    for path in state_dir.glob("agents/*/sessions/*.lock"):
        path.unlink()
        removed.append(str(path.relative_to(state_dir)))
    for agent_id in VOLATILE_SESSION_AGENT_IDS:
        sessions_dir = state_dir / "agents" / agent_id / "sessions"
        if not sessions_dir.is_dir():
            continue
        for path in sorted(sessions_dir.iterdir()):
            if path.is_file() or path.is_symlink():
                path.unlink()
                removed.append(str(path.relative_to(state_dir)))
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", default=str(STATE_DIR))
    parser.add_argument("--backup-root", default="")
    parser.add_argument("--openclaw-bin", default=str(DEFAULT_OPENCLAW_BIN))
    parser.add_argument("--openmind-base-url", default=DEFAULT_OPENMIND_BASE_URL)
    parser.add_argument("--codex-auth-path", default=str(DEFAULT_CODEX_AUTH_PATH))
    parser.add_argument("--source-auth-agent", default="main")
    parser.add_argument("--topology", choices=sorted(TOPOLOGY_AGENT_IDS), default=DEFAULT_TOPOLOGY)
    parser.add_argument("--prune-volatile", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    topology = normalize_topology(args.topology)
    active_specs = active_agent_specs(topology)
    state_dir = Path(args.state_dir).expanduser().resolve()
    openclaw_bin = Path(args.openclaw_bin).expanduser().resolve()
    current_cfg = load_json(state_dir / "openclaw.json")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_root = Path(args.backup_root).expanduser() if args.backup_root else (state_dir.parent / f"{state_dir.name}.migration-backup-{timestamp}")
    backup_root = backup_root.resolve()

    new_cfg = build_config(current_cfg, openmind_base_url=args.openmind_base_url.rstrip("/"), topology=topology)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "topology": topology,
                    "backup_root": str(backup_root),
                    "openclaw_bin": str(openclaw_bin),
                    "openmind_base_url": args.openmind_base_url.rstrip("/"),
                    "config": new_cfg,
                    "cron_jobs": build_cron_jobs(topology=topology),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    essential_backup(state_dir, backup_root)
    managed_agent_ids = {spec.agent_id for spec in active_specs}
    pruned_agent_dirs = prune_unmanaged_agent_dirs(state_dir, backup_root, managed_agent_ids)
    pruned_cron_jobs = prune_unmanaged_cron_jobs(state_dir, managed_agent_ids)
    ensure_auth_profiles(state_dir, args.source_auth_agent, [spec.agent_id for spec in active_specs])
    synced_auth_agents = sync_codex_auth_profiles(
        state_dir,
        Path(args.codex_auth_path).expanduser().resolve(),
        [spec.agent_id for spec in active_specs if spec.model.startswith("openai-codex/")],
    )
    gateway_env_dropin = ensure_gateway_openmind_env_dropin()
    ensure_workspaces(active_specs)
    removed_workspace_skill_symlinks = prune_workspace_skill_symlink_escapes(active_specs)
    ensure_gateway_token_file(state_dir, new_cfg.get("gateway") or {})
    write_json(state_dir / "openclaw.json", new_cfg)
    cron_jobs_path = write_managed_cron_jobs(state_dir, topology=topology)
    install_openmind_plugins(state_dir, openclaw_bin=openclaw_bin)
    removed = prune_volatile_artifacts(state_dir) if args.prune_volatile else []
    print(
        json.dumps(
            {
                "topology": topology,
                "backup_root": str(backup_root),
                "removed": removed,
                "pruned_agent_dirs": pruned_agent_dirs,
                "pruned_cron_jobs": pruned_cron_jobs,
                "written": str(state_dir / "openclaw.json"),
                "cron_jobs_path": str(cron_jobs_path),
                "synced_codex_auth_agents": synced_auth_agents,
                "gateway_env_dropin": str(gateway_env_dropin) if gateway_env_dropin else "",
                "removed_workspace_skill_symlinks": removed_workspace_skill_symlinks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
