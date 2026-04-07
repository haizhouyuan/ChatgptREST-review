"""Step 0 smoke runner for OpenClawBot meeting-intake chain.

This module freezes executable evidence for:

1. Smoke A  - Feishu/OpenClawBot transport captures media and writes MediaPaths.
2. Smoke B1 - openmind-advisor bridge contract still builds the expected /v3 payload.
3. Smoke B2 - canonical OpenClaw custom-tools adapter path currently loses runtime _ctx
              and does not project MediaPaths into attachments.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.eval.openclaw_dynamic_replay_gate import (
    DEFAULT_PLUGIN_SOURCE,
    DEFAULT_TYPEBOX_PATH,
    _ReplayCaptureServer,
    _build_contract_capture_check,
    _execute_openclaw_plugin_tool,
    _run_contract_capture_replay,
)


DEFAULT_OPENCLAW_ROOT = Path("/vol1/1000/projects/openclaw")


@dataclass
class MeetingIntakeSmokeCheck:
    name: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "details": dict(self.details),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class MeetingIntakeSmokeReport:
    openclaw_root: str
    plugin_source: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[MeetingIntakeSmokeCheck]
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "openclaw_root": self.openclaw_root,
            "plugin_source": self.plugin_source,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "evidence": self.evidence,
        }


def run_openclawbot_meeting_intake_smoke(
    *,
    plugin_source: Path = DEFAULT_PLUGIN_SOURCE,
    typebox_path: Path = DEFAULT_TYPEBOX_PATH,
    openclaw_root: Path = DEFAULT_OPENCLAW_ROOT,
) -> MeetingIntakeSmokeReport:
    transport = _run_feishu_transport_capture(openclaw_root=openclaw_root)
    contract = _run_contract_capture_replay(plugin_source=plugin_source, typebox_path=typebox_path)
    adapter_files = _run_main_path_adapter_capture(
        plugin_source=plugin_source,
        typebox_path=typebox_path,
        openclaw_root=openclaw_root,
        context={"files": ["/tmp/openclaw-step0-demo.txt"]},
        request_timeout_ms=30000,
    )
    adapter_media = _run_main_path_adapter_capture(
        plugin_source=plugin_source,
        typebox_path=typebox_path,
        openclaw_root=openclaw_root,
        context={
            "MediaPath": "/tmp/meeting.m4a",
            "MediaPaths": ["/tmp/meeting.m4a"],
            "MediaUrl": "/tmp/meeting.m4a",
            "MediaUrls": ["/tmp/meeting.m4a"],
        },
        request_timeout_ms=30000,
    )
    checks = [
        _build_transport_capture_check(transport),
        _build_contract_capture_check(contract),
        _build_main_path_adapter_files_check(adapter_files),
        _build_main_path_adapter_media_projection_check(adapter_media),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return MeetingIntakeSmokeReport(
        openclaw_root=str(openclaw_root),
        plugin_source=str(plugin_source),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
        evidence={
            "transport": transport,
            "bridge_contract": contract,
            "adapter_files": adapter_files,
            "adapter_media": adapter_media,
        },
    )


def render_openclawbot_meeting_intake_smoke_markdown(report: MeetingIntakeSmokeReport) -> str:
    lines = [
        "# OpenClawBot Meeting Intake Smoke Report",
        "",
        f"- openclaw_root: {report.openclaw_root}",
        f"- plugin_source: {report.plugin_source}",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Check | Pass | Key Details | Mismatch |",
        "|---|---:|---|---|",
    ]
    for check in report.checks:
        details = ", ".join(f"{key}={value}" for key, value in check.details.items())
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}" for key, value in check.mismatches.items()
        )
        lines.append(
            "| {name} | {passed} | {details} | {mismatch} |".format(
                name=_escape_pipe(check.name),
                passed="yes" if check.passed else "no",
                details=_escape_pipe(details or "-"),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_openclawbot_meeting_intake_smoke_report(
    report: MeetingIntakeSmokeReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_openclawbot_meeting_intake_smoke_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_transport_capture_check(replay: dict[str, Any]) -> MeetingIntakeSmokeCheck:
    finalized = replay.get("finalized_context") or {}
    dispatched = replay.get("dispatched_context") or {}
    media_paths = list(finalized.get("MediaPaths") or [])
    media_types = list(finalized.get("MediaTypes") or [])
    details = {
        "route_session_key": str(replay.get("route_session_key") or ""),
        "saved_media_count": len(list(replay.get("saved_media") or [])),
        "media_paths_count": len(media_paths),
        "media_types_count": len(media_types),
        "dispatched_session_key": str(dispatched.get("SessionKey") or ""),
        "originating_channel": str(dispatched.get("OriginatingChannel") or ""),
        "body_contains_speaker_prefix": "Alice:" in str(dispatched.get("Body") or ""),
    }
    expectations = {
        "route_session_key": "agent:main:feishu:chat:oc_chat_1",
        "saved_media_count": 1,
        "media_paths_count": 1,
        "media_types_count": 1,
        "dispatched_session_key": "agent:main:feishu:chat:oc_chat_1",
        "originating_channel": "feishu",
        "body_contains_speaker_prefix": True,
    }
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return MeetingIntakeSmokeCheck(
        name="feishu_transport_media_capture",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_main_path_adapter_files_check(replay: dict[str, Any]) -> MeetingIntakeSmokeCheck:
    request = replay.get("captured_request") or {}
    body = request.get("body") or {}
    task_intake = body.get("task_intake") if isinstance(body, dict) else {}
    task_intake = task_intake if isinstance(task_intake, dict) else {}
    available_inputs = task_intake.get("available_inputs") if isinstance(task_intake, dict) else {}
    available_inputs = available_inputs if isinstance(available_inputs, dict) else {}
    details = {
        "request_path": str(request.get("path") or ""),
        "body_session_id": str(body.get("session_id") or ""),
        "body_user_id": str(body.get("user_id") or ""),
        "task_session_id": str(task_intake.get("session_id") or ""),
        "task_account_id": str(task_intake.get("account_id") or ""),
        "task_thread_id": str(task_intake.get("thread_id") or ""),
        "task_agent_id": str(task_intake.get("agent_id") or ""),
        "attachments_count": len(list(task_intake.get("attachments") or [])),
        "available_input_files_count": len(list(available_inputs.get("files") or [])),
    }
    expectations = {
        "request_path": "/v3/agent/turn",
        "body_session_id": "oc-session-key",
        "body_user_id": "acct-1",
        "task_session_id": "oc-session-key",
        "task_account_id": "acct-1",
        "task_thread_id": "oc-thread-id",
        "task_agent_id": "agent-1",
        "attachments_count": 1,
        "available_input_files_count": 1,
    }
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return MeetingIntakeSmokeCheck(
        name="canonical_main_path_runtime_identity_projection",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_main_path_adapter_media_projection_check(replay: dict[str, Any]) -> MeetingIntakeSmokeCheck:
    request = replay.get("captured_request") or {}
    body = request.get("body") or {}
    task_intake = body.get("task_intake") if isinstance(body, dict) else {}
    task_intake = task_intake if isinstance(task_intake, dict) else {}
    available_inputs = task_intake.get("available_inputs") if isinstance(task_intake, dict) else {}
    available_inputs = available_inputs if isinstance(available_inputs, dict) else {}
    details = {
        "request_path": str(request.get("path") or ""),
        "context_media_paths_count": len(list(((body.get("context") or {}) if isinstance(body, dict) else {}).get("MediaPaths") or [])),
        "attachments_count": len(list(task_intake.get("attachments") or [])),
        "available_input_files_count": len(list(available_inputs.get("files") or [])),
    }
    expectations = {
        "request_path": "/v3/agent/turn",
        "context_media_paths_count": 1,
        "attachments_count": 1,
        "available_input_files_count": 1,
    }
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return MeetingIntakeSmokeCheck(
        name="canonical_main_path_media_projection",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _run_feishu_transport_capture(*, openclaw_root: Path) -> dict[str, Any]:
    bot_source = openclaw_root / "extensions" / "feishu" / "src" / "bot.ts"
    if not bot_source.exists():
        raise FileNotFoundError(f"missing OpenClaw Feishu bot source: {bot_source}")
    with tempfile.TemporaryDirectory(prefix="step0_feishu_transport_") as tempdir:
        temp_path = Path(tempdir)
        src_dir = temp_path / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        plugin_sdk_dir = temp_path / "node_modules" / "openclaw"
        plugin_sdk_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bot_source, src_dir / "bot.ts")
        for name, content in _feishu_transport_stub_modules().items():
            if name.startswith("node_modules/"):
                rel_path = Path(name.removeprefix("node_modules/"))
                target = temp_path / "node_modules" / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            else:
                (src_dir / name).write_text(content, encoding="utf-8")
        harness_path = temp_path / "harness.ts"
        harness_path.write_text(_FEISHU_TRANSPORT_HARNESS_TS, encoding="utf-8")
        proc = subprocess.run(
            ["npx", "--yes", "tsx", str(harness_path)],
            cwd=str(temp_path),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=60,
        )
        stdout = str(proc.stdout or "").strip()
        stderr = str(proc.stderr or "").strip()
        if proc.returncode != 0:
            raise RuntimeError(f"Feishu transport harness failed: rc={proc.returncode} stderr={stderr or stdout}")
        return json.loads(stdout) if stdout else {}


def _run_main_path_adapter_capture(
    *,
    plugin_source: Path,
    typebox_path: Path,
    openclaw_root: Path,
    context: dict[str, Any],
    request_timeout_ms: int,
) -> dict[str, Any]:
    if not plugin_source.exists():
        raise FileNotFoundError(f"missing OpenClaw plugin source: {plugin_source}")
    if not typebox_path.exists():
        raise FileNotFoundError(f"missing TypeBox runtime path: {typebox_path}")
    adapter_source = openclaw_root / "src" / "agents" / "pi-tool-definition-adapter.ts"
    tools_source = openclaw_root / "src" / "plugins" / "tools.ts"
    if not adapter_source.exists():
        raise FileNotFoundError(f"missing OpenClaw adapter source: {adapter_source}")
    if not tools_source.exists():
        raise FileNotFoundError(f"missing OpenClaw plugin tools source: {tools_source}")
    fake_response = {
        "status": "needs_followup",
        "session_id": "phase20-main-path-fake",
        "provenance": {"route": "clarify"},
        "next_action": {"type": "await_user_clarification"},
        "answer": "",
    }
    server = _ReplayCaptureServer(fake_response=fake_response)
    try:
        with tempfile.TemporaryDirectory(prefix="step0_main_path_adapter_") as tempdir:
            temp_path = Path(tempdir)
            plugin_dir = temp_path / "plugin"
            shutil.copytree(plugin_source.parent, plugin_dir, dirs_exist_ok=True)
            nm = temp_path / "node_modules" / "@sinclair"
            nm.mkdir(parents=True)
            os.symlink(typebox_path, nm / "typebox")
            harness_path = temp_path / "harness.ts"
            harness_path.write_text(_MAIN_PATH_ADAPTER_HARNESS_TS, encoding="utf-8")
            home_dir = temp_path / "home"
            openclaw_state_dir = home_dir / ".openclaw"
            openclaw_state_dir.mkdir(parents=True, exist_ok=True)
            (openclaw_state_dir / "openclaw.json").write_text("{}", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(home_dir)
            env["OPENCLAW_PLUGIN_CONFIG_JSON"] = json.dumps(
                {
                    "endpoint": {
                        "baseUrl": str(server.base_url).rstrip("/"),
                        "timeoutMs": int(request_timeout_ms),
                        "apiKey": "",
                    }
                },
                ensure_ascii=False,
            )
            env["OPENCLAW_TOOL_PARAMS_JSON"] = json.dumps(
                {
                    "question": "请总结会议录音",
                    "goalHint": "planning",
                    "context": context,
                },
                ensure_ascii=False,
            )
            env["OPENCLAW_RUNTIME_CTX_JSON"] = json.dumps(
                {
                    "sessionKey": "oc-session-key",
                    "sessionId": "oc-thread-id",
                    "threadId": "oc-thread-id",
                    "agentAccountId": "acct-1",
                    "agentId": "agent-1",
                },
                ensure_ascii=False,
            )
            env["OPENCLAW_ROOT"] = str(openclaw_root)
            proc = subprocess.run(
                ["npx", "--yes", "tsx", str(harness_path)],
                cwd=str(temp_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            stdout = str(proc.stdout or "").strip()
            stderr = str(proc.stderr or "").strip()
            if proc.returncode != 0:
                raise RuntimeError(
                    f"OpenClaw main-path adapter harness failed: rc={proc.returncode} stderr={stderr or stdout}"
                )
            payload = json.loads(stdout) if stdout else {}
            payload["captured_request"] = server.wait_for_request()
            return payload
    finally:
        server.close()


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")


def _feishu_transport_stub_modules() -> dict[str, str]:
    return {
        "accounts.js": """
export function resolveFeishuAccount() {
  return {
    accountId: "main",
    configured: true,
    appId: "app-test",
    config: { dmPolicy: "allowlist", allowFrom: ["oc_sender_1"] },
  };
}
""".strip(),
        "client.js": """
export function createFeishuClient() {
  return {
    contact: {
      user: {
        async get() {
          return { data: { user: { name: "Alice" } } };
        },
      },
    },
    im: {
      message: {
        async get() {
          return { code: 0, data: { items: [] } };
        },
      },
    },
  };
}
""".strip(),
        "dynamic-agent.js": """
export async function maybeCreateDynamicAgent(params) {
  return { created: false, updatedCfg: params.cfg };
}
""".strip(),
        "media.js": """
export async function downloadImageFeishu() {
  return { buffer: Buffer.from("image"), contentType: "image/png", fileName: "image.png" };
}
export async function downloadMessageResourceFeishu() {
  return { buffer: Buffer.from("audio"), contentType: "audio/mpeg", fileName: "meeting.m4a" };
}
""".strip(),
        "mention.js": """
export function extractMentionTargets() { return []; }
export function extractMessageBody(text) { return text; }
export function isMentionForwardRequest() { return false; }
""".strip(),
        "policy.js": """
export function resolveFeishuGroupConfig() { return undefined; }
export function resolveFeishuReplyPolicy() { return { requireMention: false }; }
export function resolveFeishuAllowlistMatch() { return { allowed: true }; }
export function isFeishuGroupAllowed() { return true; }
""".strip(),
        "reply-dispatcher.js": """
export function createFeishuReplyDispatcher() {
  const dispatcher = {
    async sendToolResult() {},
    async sendBlockReply() {},
    async sendFinalReply() {},
    async waitForIdle() {},
    getQueuedCounts() { return { final: 0 }; },
  };
  return {
    dispatcher,
    replyOptions: {},
    markDispatchIdle() {},
  };
}
""".strip(),
        "runtime.js": """
const state = {
  savedMedia: [],
  dispatchedContext: null,
  finalizedContext: null,
  routeSessionKey: null,
  enqueueEvents: [],
};
export function getFeishuRuntime() {
  return {
    media: {
      async detectMime() {
        return "audio/mpeg";
      },
    },
    channel: {
      media: {
        async saveMediaBuffer(_buffer, contentType, _kind, _maxBytes, fileName) {
          const path = `/tmp/${fileName || "meeting.m4a"}`;
          const saved = { path, contentType };
          state.savedMedia.push(saved);
          return saved;
        },
      },
      routing: {
        resolveAgentRoute() {
          state.routeSessionKey = "agent:main:feishu:chat:oc_chat_1";
          return {
            sessionKey: "agent:main:feishu:chat:oc_chat_1",
            accountId: "main",
            agentId: "feishu-intake",
            matchedBy: "default",
          };
        },
      },
      reply: {
        resolveEnvelopeFormatOptions() {
          return {};
        },
        formatAgentEnvelope({ body }) {
          return body;
        },
        finalizeInboundContext(ctx) {
          state.finalizedContext = ctx;
          return ctx;
        },
        async dispatchReplyFromConfig({ ctx }) {
          state.dispatchedContext = ctx;
          return { queuedFinal: false, counts: { final: 0 } };
        },
      },
      text: {
        resolveMarkdownTableMode() {
          return "plain";
        },
        convertMarkdownTables(text) {
          return text;
        },
      },
    },
    system: {
      enqueueSystemEvent(message, options) {
        state.enqueueEvents.push({ message, options });
      },
    },
    __state: state,
  };
}
""".strip(),
        "send.js": """
export async function getMessageFeishu() { return null; }
""".strip(),
        "node_modules/openclaw/plugin-sdk.js": """
export const DEFAULT_GROUP_HISTORY_LIMIT = 20;
export function buildPendingHistoryContextFromMap({ currentMessage }) {
  return currentMessage;
}
export function recordPendingHistoryEntryIfEnabled() {}
export function clearHistoryEntriesIfEnabled() {}
""".strip(),
    }


_FEISHU_TRANSPORT_HARNESS_TS = """
import { handleFeishuMessage } from "./src/bot.ts";
import { getFeishuRuntime } from "./src/runtime.js";

const runtimeCore = getFeishuRuntime();

const cfg = {
  channels: {
    feishu: {
      dmPolicy: "allowlist",
      allowFrom: ["oc_sender_1"],
    },
  },
};

const event = {
  sender: {
    sender_id: {
      open_id: "oc_sender_1",
      user_id: "u_sender_1",
    },
  },
  message: {
    message_id: "om_1",
    chat_id: "oc_chat_1",
    chat_type: "p2p",
    message_type: "file",
    content: JSON.stringify({
      file_key: "file_1",
      file_name: "meeting.m4a",
    }),
  },
};

(async () => {
  await handleFeishuMessage({
    cfg,
    event,
    runtime: {
      log() {},
      error() {},
    },
    accountId: "main",
  });

  console.log(JSON.stringify({
    saved_media: runtimeCore.__state.savedMedia,
    dispatched_context: runtimeCore.__state.dispatchedContext,
    finalized_context: runtimeCore.__state.finalizedContext,
    route_session_key: runtimeCore.__state.routeSessionKey,
    enqueue_events: runtimeCore.__state.enqueueEvents,
  }, null, 2));
})().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
""".strip()


_MAIN_PATH_ADAPTER_HARNESS_TS = """
import path from "node:path";
import { pathToFileURL } from "node:url";

const pluginConfig = JSON.parse(process.env.OPENCLAW_PLUGIN_CONFIG_JSON || "{}");
const toolParams = JSON.parse(process.env.OPENCLAW_TOOL_PARAMS_JSON || "{}");
const runtimeCtx = JSON.parse(process.env.OPENCLAW_RUNTIME_CTX_JSON || "{}");

(async () => {
  const openclawRoot = process.env.OPENCLAW_ROOT;
  if (!openclawRoot) {
    throw new Error("OPENCLAW_ROOT missing");
  }
  const pluginPath = process.env.OPENCLAW_PLUGIN_SOURCE || path.join(process.cwd(), "plugin", "index.ts");
  const toolsPath = pathToFileURL(path.join(openclawRoot, "src", "plugins", "tools.ts")).href;
  const adapterPath = pathToFileURL(path.join(openclawRoot, "src", "agents", "pi-tool-definition-adapter.ts")).href;
  const { resolvePluginTools } = await import(toolsPath);
  const { toToolDefinitions } = await import(adapterPath);
  const tools = resolvePluginTools({
    context: {
      config: {
        plugins: {
          load: { paths: [pluginPath] },
          allow: ["openmind-advisor"],
          entries: {
            "openmind-advisor": {
              enabled: true,
              config: pluginConfig,
            },
          },
        },
      },
      workspaceDir: process.cwd(),
      sessionId: runtimeCtx.sessionId,
      sessionKey: runtimeCtx.sessionKey,
      threadId: runtimeCtx.threadId,
      messageChannel: "feishu",
      agentAccountId: runtimeCtx.agentAccountId,
      agentId: runtimeCtx.agentId,
    },
  });
  const defs = toToolDefinitions(tools);
  const tool = defs.find((entry) => entry.name === "openmind_advisor_ask");
  if (!tool) {
    throw new Error("tool missing: openmind_advisor_ask");
  }
  const result = await tool.execute(
    "phase20-openclaw-main-path",
    toolParams,
    undefined,
    runtimeCtx,
    undefined,
  );
  console.log(JSON.stringify({
    tool_names: defs.map((entry) => entry.name),
    result,
  }, null, 2));
})().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
""".strip()
