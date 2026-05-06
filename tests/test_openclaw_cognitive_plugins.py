from __future__ import annotations

import json
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "openclaw_extensions"
NGINX_OPENMIND_CONF = Path(__file__).resolve().parents[1] / "ops" / "nginx_openmind.conf"
PLUGIN_IDS = [
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
    assert 'project_id: params.projectId ?? ""' in memory_source
    assert "const sessionProjects = new Map<string, string>();" in memory_source
    assert "function inferProjectIdFromText(text: string): string" in memory_source
    assert "NON_PROJECT_PROJECT_INFERENCE_SUPPRESS_PATTERNS" in memory_source
    assert "function shouldSuppressProjectInference(text: string): boolean" in memory_source
    assert "/袁海州/i" not in memory_source
    assert "/孙群慧/i" not in memory_source
    assert "/蔡总/i" not in memory_source
    assert "if (suppressInference) {" in memory_source
    assert 'projectId: resolveProjectId({' in memory_source
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
    assert "projectId: run.projectId" in telemetry_source
    assert 'project_id: run.projectId' in telemetry_source
    assert "const sessionProjects = new Map<string, string>();" in telemetry_source

    assert "openmind_graph_query" in graph_source
    assert "/v2/graph/query" in graph_source


def test_openmind_plugins_default_to_integrated_host_port() -> None:
    memory_source = (PLUGIN_ROOT / "openmind-memory" / "index.ts").read_text(encoding="utf-8")
    graph_source = (PLUGIN_ROOT / "openmind-graph" / "index.ts").read_text(encoding="utf-8")
    telemetry_source = (PLUGIN_ROOT / "openmind-telemetry" / "index.ts").read_text(encoding="utf-8")
    nginx_source = NGINX_OPENMIND_CONF.read_text(encoding="utf-8")

    for source in (memory_source, graph_source, telemetry_source):
        assert "http://127.0.0.1:18711" in source
        assert "http://127.0.0.1:18713" not in source
    assert "127.0.0.1:18711" in nginx_source
    assert "127.0.0.1:18713" not in nginx_source
    assert "OPENMIND_AUTH_MODE=strict" in nginx_source
    assert "X-Api-Key" in nginx_source


def test_registered_project_context_files_exist() -> None:
    shortmobility = Path("/vol1/1000/projects/planning/两轮车车身业务/_project_context.md")
    prs = Path("/vol1/1000/projects/planning/行星滚柱丝杠/_project_context.md")

    for path in (shortmobility, prs):
        assert path.is_file(), f"missing project context: {path}"
        source = path.read_text(encoding="utf-8")
        assert "authority_docs:" in source
        assert "frozen_facts:" in source
        assert "style_rules:" in source
