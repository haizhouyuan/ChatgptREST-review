from __future__ import annotations

import json
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "openclaw_extensions"
NGINX_OPENMIND_CONF = Path(__file__).resolve().parents[1] / "ops" / "nginx_openmind.conf"
PLUGIN_IDS = [
    "openmind-advisor",
    "openmind-memory",
    "openmind-graph",
    "openmind-telemetry",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_openclaw_plugin_packages_ship_expected_files() -> None:
    for plugin_id in PLUGIN_IDS:
        root = PLUGIN_ROOT / plugin_id
        assert root.is_dir(), f"missing plugin directory: {root}"
        assert (root / "index.ts").is_file()
        assert (root / "package.json").is_file()
        assert (root / "openclaw.plugin.json").is_file()
        assert (root / "README.md").is_file()


def test_openclaw_plugin_manifests_match_package_ids() -> None:
    for plugin_id in PLUGIN_IDS:
        root = PLUGIN_ROOT / plugin_id
        package_json = _load_json(root / "package.json")
        manifest = _load_json(root / "openclaw.plugin.json")

        assert package_json["openclaw"]["extensions"] == ["./index.ts"]
        assert manifest["id"] == plugin_id
        assert manifest["configSchema"]["type"] == "object"
        assert package_json["dependencies"]["@sinclair/typebox"] == "0.34.48"
        if plugin_id == "openmind-memory":
            assert manifest["kind"] == "memory"
            assert manifest["configSchema"]["properties"]["tokenBudget"]["minimum"] == 4000
            assert manifest["configSchema"]["properties"]["defaultRoleId"]["type"] == "string"
        if plugin_id == "openmind-advisor":
            assert manifest["configSchema"]["properties"]["defaultGoalHint"]["type"] == "string"
            assert manifest["configSchema"]["properties"]["defaultRoleId"]["type"] == "string"
        if plugin_id == "openmind-telemetry":
            assert manifest["configSchema"]["properties"]["defaultRoleId"]["type"] == "string"
            assert manifest["configSchema"]["properties"]["repoName"]["type"] == "string"
            assert manifest["configSchema"]["properties"]["repoPath"]["type"] == "string"
            assert manifest["configSchema"]["properties"]["taskRefPrefix"]["type"] == "string"
            assert manifest["configSchema"]["properties"]["defaultProvider"]["type"] == "string"
            assert manifest["configSchema"]["properties"]["defaultModel"]["type"] == "string"
            assert manifest["configSchema"]["properties"]["executorKind"]["type"] == "string"


def test_openmind_plugin_sources_expose_expected_hooks_and_tools() -> None:
    memory_source = (PLUGIN_ROOT / "openmind-memory" / "index.ts").read_text(encoding="utf-8")
    telemetry_source = (PLUGIN_ROOT / "openmind-telemetry" / "index.ts").read_text(encoding="utf-8")
    advisor_source = (PLUGIN_ROOT / "openmind-advisor" / "index.ts").read_text(encoding="utf-8")
    graph_source = (PLUGIN_ROOT / "openmind-graph" / "index.ts").read_text(encoding="utf-8")

    assert "before_agent_start" in memory_source
    assert "agent_end" in memory_source
    assert "openmind_memory_recall" in memory_source
    assert "openmind_memory_capture" in memory_source
    assert "/v2/memory/capture" in memory_source
    assert "/v2/knowledge/ingest" not in memory_source
    assert 'const DEFAULT_RECALL_SOURCES = ["memory", "knowledge", "graph", "policy"] as const;' in memory_source
    assert "buildResolveContextRequest(" in memory_source
    assert "const requestGraph = sources.includes(\"graph\");" in memory_source
    assert "sources: [...sources]" in memory_source
    assert "...(requestGraph ? { graph_scopes: cfg.graphScopes } : {})," in memory_source
    assert 'account_id: params.accountId ?? ""' in memory_source
    assert 'role_id: params.roleId ?? cfg.defaultRoleId ?? ""' in memory_source
    assert 'params.threadId != null && params.threadId !== "" ? String(params.threadId) : params.sessionId ?? ""' in memory_source
    assert "sessionId: ctx?.sessionId" in memory_source
    assert "threadId: ctx?.threadId" in memory_source
    assert "accountId: ctx?.agentAccountId" in memory_source
    assert "roleId: cfg.defaultRoleId" in memory_source
    assert "roleId: Type.Optional(Type.String" in memory_source
    assert "AUTOMATION_PROMPT_PATTERNS" in memory_source
    assert "you must call" in memory_source
    assert "reply exactly" in memory_source
    assert "openmind_memory_(status|recall|capture)" in memory_source
    assert "sessions_(spawn|send|list|history)" in memory_source

    assert "before_agent_start" in telemetry_source
    assert "after_tool_call" in telemetry_source
    assert "message_sent" in telemetry_source
    assert "openmind_telemetry_flush" in telemetry_source
    assert 'type: "team.run.created"' in telemetry_source
    assert 'taskRefPrefix: String(raw.taskRefPrefix ?? "openclaw")' in telemetry_source
    assert 'provider: cfg.defaultProvider' in telemetry_source
    assert 'model: cfg.defaultModel' in telemetry_source
    assert 'executor_kind: cfg.executorKind' in telemetry_source

    assert "openmind_advisor_ask" in advisor_source
    assert "/v3/agent/turn" in advisor_source
    assert "/v2/advisor/ask" not in advisor_source
    assert "/v2/advisor/advise" not in advisor_source
    assert 'defaultGoalHint: String(raw.defaultGoalHint ?? "").trim()' in advisor_source
    assert "createHash" in advisor_source
    assert "agentResultText" in advisor_source
    assert "ctx?.sessionKey" in advisor_source
    assert "ctx?.agentAccountId" in advisor_source
    assert "session_id: runtimeSessionId" in advisor_source
    assert "const userId = runtime.userId;" in advisor_source
    assert 'body.role_id = roleId' in advisor_source
    assert "session_id: String(ctx?.sessionKey ?? \"\").trim()" in advisor_source
    assert "account_id: String(ctx?.agentAccountId ?? \"\").trim()" in advisor_source
    assert "thread_id: String(ctx?.sessionId ?? \"\").trim()" in advisor_source
    assert "agent_id: String(ctx?.agentId ?? \"\").trim()" in advisor_source
    assert 'user_id: userId' in advisor_source
    assert 'createHash("sha256")' in advisor_source
    assert 'return "openclaw:anon"' in advisor_source
    assert "buildUserId(ctx)" in advisor_source
    assert "ctx?.sessionId" in advisor_source
    assert "ctx?.agentAccountId" in advisor_source
    assert "ctx?.sessionKey" in advisor_source
    assert 'defaultRoleId: String(raw.defaultRoleId ?? "").trim()' in advisor_source
    assert "roleId: Type.Optional(Type.String" in advisor_source
    assert "requestJson(" in advisor_source
    assert 'spec_version: "task-intake-v2"' in advisor_source
    assert 'source: "openclaw"' in advisor_source
    assert 'ingress_lane: "agent_v3"' in advisor_source
    assert "buildTaskIntakePayload({" in advisor_source
    assert "extractContextFiles(runtime.mergedContext)" in advisor_source
    assert 'goal === "planning" || goal === "implementation_planning"' in advisor_source
    assert 'return "planning"' in advisor_source
    assert 'case "planning":' in advisor_source
    assert 'payload.scenario = scenario' in advisor_source
    assert 'if (scenario) {' in advisor_source
    assert 'task_intake: taskIntake' in advisor_source
    assert 'body.attachments = files' in advisor_source
    assert '"x-client-name": "openclaw-advisor"' in advisor_source
    assert '"x-client-instance": `openclaw-advisor:${process.pid}`' in advisor_source
    assert '"x-request-id": `openclaw-advisor-${randomUUID()}`' in advisor_source
    assert "agentResultText(payload)" in advisor_source
    assert "waitForCompletion" not in advisor_source
    assert "/v1/jobs/${encodeURIComponent(jobId)}/wait" not in advisor_source
    assert "/v1/jobs/${encodeURIComponent(jobId)}/answer?max_chars=16000&offset=${answerOffset}" not in advisor_source

    assert "openmind_graph_query" in graph_source
    assert "/v2/graph/query" in graph_source


def test_openmind_plugins_default_to_integrated_host_port() -> None:
    advisor_manifest = _load_json(PLUGIN_ROOT / "openmind-advisor" / "openclaw.plugin.json")
    advisor_source = (PLUGIN_ROOT / "openmind-advisor" / "index.ts").read_text(encoding="utf-8")
    memory_source = (PLUGIN_ROOT / "openmind-memory" / "index.ts").read_text(encoding="utf-8")
    graph_source = (PLUGIN_ROOT / "openmind-graph" / "index.ts").read_text(encoding="utf-8")
    telemetry_source = (PLUGIN_ROOT / "openmind-telemetry" / "index.ts").read_text(encoding="utf-8")
    nginx_source = NGINX_OPENMIND_CONF.read_text(encoding="utf-8")

    assert advisor_manifest["uiHints"]["endpoint.baseUrl"]["placeholder"] == "http://127.0.0.1:18711"
    assert advisor_manifest["version"] == "2026.3.12"
    assert advisor_manifest["uiHints"]["defaultGoalHint"]["help"].startswith("Optional default goal hint")
    for source in (advisor_source, memory_source, graph_source, telemetry_source):
        assert "http://127.0.0.1:18711" in source
        assert "http://127.0.0.1:18713" not in source
    assert "127.0.0.1:18711" in nginx_source
    assert "127.0.0.1:18713" not in nginx_source
    assert "OPENMIND_AUTH_MODE=strict" in nginx_source
    assert "X-Api-Key" in nginx_source
