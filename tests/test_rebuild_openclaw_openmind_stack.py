from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "rebuild_openclaw_openmind_stack.py"
_SPEC = importlib.util.spec_from_file_location("rebuild_openclaw_openmind_stack", _MODULE_PATH)
assert _SPEC and _SPEC.loader
rebuild = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = rebuild
_SPEC.loader.exec_module(rebuild)


def _sample_config() -> dict:
    return {
        "gateway": {
            "port": 18789,
            "mode": "local",
            "bind": "loopback",
            "auth": {"mode": "token", "token": "test-token"},
        },
        "session": {
            "maintenance": {
                "mode": "enforce",
                "pruneAfter": "7d",
                "maxEntries": 500,
                "rotateBytes": "10mb",
            }
        },
        "tools": {
            "profile": "coding",
            "exec": {"host": "gateway", "security": "full", "ask": "off", "timeoutSec": 1200, "notifyOnExit": True},
        },
        "skills": {
            "allowBundled": ["healthcheck"],
            "load": {"extraDirs": ["/vol1/1000/projects/planning/skills-src"]},
            "install": {"nodeManager": "npm"},
        },
        "messages": {"ackReactionScope": "group-mentions"},
        "channels": {
            "feishu": {
                "enabled": True,
                "dmPolicy": "pairing",
                "groupPolicy": "disabled",
                "accounts": {
                    "main": {
                        "appId": "cli_main",
                        "appSecretFile": "/tmp/feishu-main.secret",
                        "botName": "OpenClaw",
                        "systemPrompt": "old intake prompt",
                        "renderMode": "raw",
                    },
                    "research": {"enabled": True, "appId": "cli_research", "appSecretFile": "/tmp/feishu-research.secret"},
                },
            },
            "dingtalk": {"enabled": True, "clientId": "ding_client", "clientSecret": "ding_secret"},
        },
        "agents": {
            "defaults": {
                "cliBackends": {
                    "codex-cli": {
                        "command": "codex",
                        "args": ["exec"],
                    }
                },
                "memorySearch": {"provider": "openai", "model": "text-embedding-v2"},
                "compaction": {"mode": "safeguard"},
                "thinkingDefault": "high",
                "maxConcurrent": 4,
            }
        },
        "plugins": {
            "allow": [],
            "load": {"paths": ["/tmp/custom-plugin"]},
            "installs": {"dingtalk": {"source": "npm", "spec": "@openclaw-china/dingtalk"}},
        },
    }


def _seed_plugin_snapshot(target_dir: Path, plugin_id: str) -> None:
    source_dir = rebuild.REPO_ROOT / "openclaw_extensions" / plugin_id
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in ("openclaw.plugin.json", "package.json", "index.ts", "README.md"):
        (target_dir / name).write_bytes((source_dir / name).read_bytes())


def test_build_config_rewrites_bindings_and_plugins(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(rebuild, "DEFAULT_CHATGPTREST_ENV_FILE", tmp_path / "missing.env")
    cfg = rebuild.build_config(_sample_config(), topology="ops")

    assert cfg["bindings"] == [
        {"type": "route", "agentId": "main", "match": {"channel": "dingtalk", "accountId": "default"}},
        {"type": "route", "agentId": "main", "match": {"channel": "feishu", "accountId": "default"}},
    ]
    assert cfg["plugins"]["slots"]["memory"] == "openmind-memory"
    assert cfg["plugins"]["allow"] == sorted(
        [
            "acpx",
            "diffs",
            "dingtalk",
            "feishu",
            "google-gemini-cli-auth",
            "openmind-advisor",
            "openmind-graph",
            "openmind-memory",
            "openmind-telemetry",
        ]
    )
    assert "load" not in cfg["plugins"] or cfg["plugins"]["load"] == {}
    assert cfg["plugins"]["installs"]["dingtalk"]["spec"] == rebuild.PINNED_DINGTALK_SPEC
    assert cfg["plugins"]["installs"]["dingtalk"]["version"] == rebuild.PINNED_DINGTALK_VERSION
    assert cfg["plugins"]["installs"]["dingtalk"]["integrity"] == rebuild.PINNED_DINGTALK_INTEGRITY
    assert cfg["plugins"]["entries"]["openmind-memory"]["enabled"] is True
    assert cfg["plugins"]["entries"]["openmind-memory"]["config"]["endpoint"]["baseUrl"] == "http://127.0.0.1:18711"
    assert "apiKey" not in cfg["plugins"]["entries"]["openmind-memory"]["config"]["endpoint"]
    assert cfg["plugins"]["entries"]["openmind-memory"]["config"]["tokenBudget"] == 4000
    assert cfg["plugins"]["entries"]["openmind-advisor"]["config"]["defaultGoalHint"] == ""
    telemetry_cfg = cfg["plugins"]["entries"]["openmind-telemetry"]["config"]
    assert telemetry_cfg["repoName"] == "ChatgptREST"
    assert telemetry_cfg["repoPath"] == str(rebuild.REPO_ROOT)
    assert telemetry_cfg["taskRefPrefix"] == "openclaw"
    assert telemetry_cfg["defaultProvider"] == "minimax"
    assert telemetry_cfg["defaultModel"] == "MiniMax-M2.5"
    assert telemetry_cfg["executorKind"] == "openclaw.agent"
    assert cfg["plugins"]["entries"]["google-gemini-cli-auth"]["enabled"] is True
    assert cfg["plugins"]["entries"]["acpx"]["enabled"] is True
    assert cfg["plugins"]["entries"]["diffs"]["enabled"] is True
    assert cfg["acp"]["backend"] == "acpx"
    assert cfg["acp"]["allowedAgents"] == ["codex", "gemini", "claude"]
    assert cfg["agents"]["list"][0]["id"] == "main"
    assert cfg["agents"]["list"][0]["default"] is True
    by_id = {agent["id"]: agent for agent in cfg["agents"]["list"]}
    assert set(by_id) == {"main", "maintagent", "finbot"}
    assert by_id["main"]["tools"]["profile"] == "coding"
    assert by_id["main"]["tools"]["alsoAllow"] == list(rebuild.MAIN_OPS_TOOL_ADDITIONS)
    assert by_id["main"]["tools"]["deny"] == list(rebuild.MAIN_TOOL_DENY)
    assert by_id["main"]["skills"] == ["chatgptrest-call"]
    assert "sessions_spawn" not in by_id["main"]["tools"]["alsoAllow"]
    assert "sessions_spawn" in by_id["main"]["tools"]["deny"]
    assert "subagents" in by_id["main"]["tools"]["deny"]
    assert by_id["maintagent"]["tools"]["profile"] == "minimal"
    assert by_id["maintagent"]["tools"]["alsoAllow"] == list(rebuild.MAINT_TOOL_ADDITIONS)
    assert by_id["maintagent"]["tools"]["alsoAllow"] == ["sessions_send", "sessions_list"]
    assert "skills" not in by_id["maintagent"]
    assert "deny" not in by_id["maintagent"]["tools"]
    assert by_id["finbot"]["model"] == rebuild.DEFAULT_MINIMAX_MODEL_REF
    assert by_id["finbot"]["tools"]["profile"] == "coding"
    assert by_id["finbot"]["tools"]["alsoAllow"] == list(rebuild.FINBOT_TOOL_ADDITIONS)
    assert by_id["finbot"]["tools"]["deny"] == list(rebuild.FINBOT_TOOL_DENY)
    assert by_id["finbot"]["sandbox"] == rebuild.AGENT_SANDBOX_OVERRIDES["finbot"]
    assert cfg["agents"]["defaults"]["model"]["primary"] == rebuild.DEFAULT_MINIMAX_MODEL_REF
    assert cfg["agents"]["defaults"]["model"]["fallbacks"] == [
        rebuild.DEFAULT_QWEN_MODEL_REF,
        rebuild.DEFAULT_GEMINI_MODEL_REF,
    ]
    assert cfg["models"]["providers"]["minimax"]["models"][0]["id"] == "MiniMax-M2.5"
    assert cfg["models"]["providers"]["qwen-coding-plan"]["models"][0]["id"] == "qwen3-coder-plus"
    assert cfg["tools"]["profile"] == "coding"
    assert cfg["tools"]["agentToAgent"]["enabled"] is True
    assert cfg["tools"]["agentToAgent"]["allow"] == ["main", "maintagent", "finbot"]
    assert cfg["tools"]["sessions"]["visibility"] == "all"
    assert cfg["tools"]["exec"]["ask"] == "on-miss"
    assert cfg["session"]["agentToAgent"]["maxPingPongTurns"] == 0
    assert cfg["gateway"]["bind"] == "loopback"
    assert cfg["gateway"]["trustedProxies"] == ["127.0.0.1/32", "::1/128"]
    assert cfg["gateway"]["auth"]["mode"] == "token"
    assert cfg["gateway"]["auth"]["token"] == "test-token"
    assert cfg["gateway"]["auth"]["allowTailscale"] is False
    assert cfg["gateway"]["tailscale"]["mode"] == "off"
    assert cfg["gateway"]["tailscale"]["resetOnExit"] is False
    assert cfg["agents"]["defaults"]["sandbox"]["mode"] == "non-main"
    assert cfg["agents"]["defaults"]["sandbox"]["scope"] == "session"
    assert cfg["agents"]["defaults"]["sandbox"]["workspaceAccess"] == "none"
    assert cfg["agents"]["defaults"]["sandbox"]["sessionToolsVisibility"] == "all"
    assert by_id["maintagent"]["sandbox"] == rebuild.AGENT_SANDBOX_OVERRIDES["maintagent"]
    assert "subagents" not in by_id["main"]
    assert "heartbeat" not in cfg["channels"]["defaults"]


def test_build_config_extends_skill_dirs() -> None:
    cfg = rebuild.build_config(_sample_config())
    extra_dirs = cfg["skills"]["load"]["extraDirs"]

    assert extra_dirs == [str((rebuild.REPO_ROOT / "skills-src").resolve())]
    assert cfg["skills"]["allowBundled"] == []


def test_build_config_defaults_to_lean_topology() -> None:
    cfg = rebuild.build_config(_sample_config())
    by_id = {agent["id"]: agent for agent in cfg["agents"]["list"]}

    assert set(by_id) == {"main"}
    assert by_id["main"]["tools"]["profile"] == "coding"
    assert by_id["main"]["tools"]["alsoAllow"] == list(rebuild.MAIN_LEAN_TOOL_ADDITIONS)
    assert by_id["main"]["tools"]["deny"] == list(rebuild.MAIN_LEAN_TOOL_DENY)
    assert "sessions_spawn" in by_id["main"]["tools"]["deny"]
    assert "sessions_send" in by_id["main"]["tools"]["deny"]
    assert "sessions_list" in by_id["main"]["tools"]["deny"]
    assert "sessions_history" in by_id["main"]["tools"]["deny"]
    assert "subagents" in by_id["main"]["tools"]["deny"]
    assert "subagents" not in by_id["main"]
    assert cfg["tools"]["agentToAgent"]["enabled"] is False
    assert cfg["tools"]["agentToAgent"]["allow"] == []


def test_build_gateway_section_generates_token_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENCLAW_GATEWAY_TOKEN", raising=False)

    gateway = rebuild.build_gateway_section({"gateway": {"port": 18789, "mode": "local", "auth": {"mode": "token"}}})

    assert gateway["auth"]["mode"] == "token"
    assert gateway["auth"]["allowTailscale"] is False
    assert gateway["tailscale"]["mode"] == "off"
    assert isinstance(gateway["auth"]["token"], str)
    assert len(gateway["auth"]["token"]) >= 32


def test_build_config_injects_openmind_api_key_from_env_file(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / "chatgptrest.env"
    env_file.write_text("OPENMIND_API_KEY=test-openmind-key\n", encoding="utf-8")
    monkeypatch.setattr(rebuild, "DEFAULT_CHATGPTREST_ENV_FILE", env_file)

    cfg = rebuild.build_config(_sample_config(), topology="ops")

    assert cfg["plugins"]["entries"]["openmind-memory"]["config"]["endpoint"]["apiKey"] == "test-openmind-key"
    assert cfg["plugins"]["entries"]["openmind-advisor"]["config"]["endpoint"]["apiKey"] == "test-openmind-key"


def test_active_agent_specs_switches_main_and_optional_maintagent() -> None:
    lean_specs = rebuild.active_agent_specs("lean")
    ops_specs = rebuild.active_agent_specs("ops")

    assert [spec.agent_id for spec in lean_specs] == ["main"]
    assert lean_specs[0].tool_also_allow == rebuild.MAIN_LEAN_TOOL_ADDITIONS
    assert lean_specs[0].allow_agents == ()
    assert [spec.agent_id for spec in ops_specs] == ["main", "maintagent", "finbot"]
    assert ops_specs[0].tool_also_allow == rebuild.MAIN_OPS_TOOL_ADDITIONS
    assert ops_specs[0].allow_agents == ()


def test_build_config_normalizes_plugin_provenance(monkeypatch, tmp_path: Path) -> None:
    cfg = _sample_config()
    load_symlink_target = tmp_path / "custom-plugin"
    load_symlink_target.mkdir()
    load_symlink = tmp_path / "custom-plugin-link"
    load_symlink.symlink_to(load_symlink_target, target_is_directory=True)
    install_target = tmp_path / "installed-plugin"
    install_target.mkdir()
    install_symlink = tmp_path / "installed-plugin-link"
    install_symlink.symlink_to(install_target, target_is_directory=True)
    cfg["plugins"]["load"] = {"paths": [str(load_symlink)]}
    cfg["plugins"]["installs"] = {
        "openmind-memory": {
            "source": "path",
            "installPath": str(install_symlink),
            "sourcePath": str(install_symlink),
        }
    }
    result = rebuild.build_config(cfg)

    assert "load" not in result["plugins"] or result["plugins"]["load"] == {}
    assert "openmind-memory" not in result["plugins"]["installs"]


def test_build_config_does_not_inherit_arbitrary_plugin_allow_or_load(monkeypatch, tmp_path: Path) -> None:
    cfg = _sample_config()
    cfg["plugins"]["allow"] = ["env-http-proxy", "random-local-plugin"]
    cfg["plugins"]["load"] = {"paths": [str(tmp_path / "random-plugin")]}

    result = rebuild.build_config(cfg)

    assert "random-local-plugin" not in result["plugins"]["allow"]
    assert "load" not in result["plugins"] or result["plugins"]["load"] == {}


def test_normalize_plugin_installs_drops_unknown_keys() -> None:
    normalized = rebuild.normalize_plugin_installs(
        {
            "openmind-memory": {
                "source": "path",
                "sourcePath": "/tmp/source",
                "installPath": "/tmp/install",
                "fingerprint": "stale",
            }
        }
    )

    assert normalized["openmind-memory"]["source"] == "path"
    assert normalized["openmind-memory"]["sourcePath"] == str(Path("/tmp/source").resolve())
    assert normalized["openmind-memory"]["installPath"] == str(Path("/tmp/install").resolve())
    assert "fingerprint" not in normalized["openmind-memory"]


def test_build_config_normalizes_feishu_main_account() -> None:
    cfg = rebuild.build_config(_sample_config(), topology="lean")
    feishu = cfg["channels"]["feishu"]
    main = feishu["accounts"]["default"]
    research = feishu["accounts"]["research"]

    assert main["appId"] == "cli_main"
    assert main["appSecretFile"] == "/tmp/feishu-main.secret"
    assert "systemPrompt" not in main
    assert "renderMode" not in main
    assert feishu["groupPolicy"] == "disabled"
    assert feishu["defaultAccount"] == "default"
    assert feishu["tools"] == {
        "doc": False,
        "chat": False,
        "wiki": False,
        "drive": False,
        "perm": False,
        "scopes": False,
    }
    assert research["enabled"] is False
    assert research["dmPolicy"] == "disabled"
    assert research["groupPolicy"] == "disabled"
    assert "allowFrom" not in research
    assert "groupAllowFrom" not in research


def test_ensure_gateway_openmind_env_dropin_writes_environmentfile(tmp_path: Path) -> None:
    env_file = tmp_path / "chatgptrest.env"
    env_file.write_text("OPENMIND_API_KEY=test-key\nOPENMIND_AUTH_MODE=strict\n", encoding="utf-8")
    dropin_dir = tmp_path / "openclaw-gateway.service.d"

    dropin_path = rebuild.ensure_gateway_openmind_env_dropin(env_file=env_file, dropin_dir=dropin_dir)

    assert dropin_path == dropin_dir / "20-openmind-cognitive.conf"
    assert dropin_path.read_text(encoding="utf-8") == "[Service]\nEnvironmentFile=-" + str(env_file) + "\n"


def test_ensure_gateway_openmind_env_dropin_skips_missing_openmind_keys(tmp_path: Path) -> None:
    env_file = tmp_path / "chatgptrest.env"
    env_file.write_text("CHATGPTREST_PORT=18711\n", encoding="utf-8")

    dropin_path = rebuild.ensure_gateway_openmind_env_dropin(env_file=env_file, dropin_dir=tmp_path / "dropin")

    assert dropin_path is None


def test_build_config_drops_legacy_managed_heartbeat_visibility() -> None:
    sample = _sample_config()
    sample["channels"]["defaults"] = {
        "heartbeat": dict(rebuild.LEGACY_MANAGED_CHANNEL_HEARTBEAT_VISIBILITY),
    }

    cfg = rebuild.build_config(sample)

    assert "heartbeat" not in cfg["channels"]["defaults"]


def test_build_config_preserves_custom_heartbeat_visibility() -> None:
    sample = _sample_config()
    sample["channels"]["defaults"] = {
        "heartbeat": {"showOk": True, "showAlerts": False, "useIndicator": False},
        "extraSetting": "keep-me",
    }

    cfg = rebuild.build_config(sample)

    assert cfg["channels"]["defaults"]["heartbeat"] == {
        "showOk": True,
        "showAlerts": False,
        "useIndicator": False,
    }
    assert cfg["channels"]["defaults"]["extraSetting"] == "keep-me"


def test_build_config_adds_main_and_maint_heartbeats_for_ops() -> None:
    cfg = rebuild.build_config(_sample_config(), topology="ops")
    by_id = {agent["id"]: agent for agent in cfg["agents"]["list"]}

    assert by_id["main"]["heartbeat"]["every"] == "30m"
    assert by_id["maintagent"]["model"] == rebuild.DEFAULT_MINIMAX_MODEL_REF
    assert "sessions_send" in by_id["maintagent"]["heartbeat"]["prompt"]
    assert 'sessionKey="agent:main:main"' in by_id["maintagent"]["heartbeat"]["prompt"]
    assert "read-only" in by_id["maintagent"]["heartbeat"]["prompt"]
    assert "exec, process, or shell" in by_id["maintagent"]["heartbeat"]["prompt"]
    assert "Prefer session status/list over ad-hoc shell probing." in by_id["maintagent"]["heartbeat"]["prompt"]
    assert rebuild.HEARTBEATS["maintagent"].count("18711") == 1
    assert "read-only" in rebuild.HEARTBEATS["maintagent"]
    assert "`sessions_list`" in rebuild.HEARTBEATS["maintagent"]
    assert "openmind_memory_status" not in rebuild.HEARTBEATS["maintagent"]
    assert "role-agent lanes" in rebuild.HEARTBEATS["main"]
    assert 'sessionKey="agent:finbot:main"' in rebuild.HEARTBEATS["main"]
    assert "default execution lane for investment research work" in rebuild.HEARTBEATS["main"]
    assert by_id["finbot"]["heartbeat"]["every"] == "6h"
    assert "dashboard-refresh" in by_id["finbot"]["heartbeat"]["prompt"]
    assert "inbox-list" in by_id["finbot"]["heartbeat"]["prompt"]
    assert str(rebuild.FINBOT_CLI_PATH) in by_id["finbot"]["heartbeat"]["prompt"]
    assert str(rebuild.FINBOT_CLI_PATH) in rebuild.HEARTBEATS["finbot"]
    cron_jobs = rebuild.build_cron_jobs(topology="ops")["jobs"]
    assert cron_jobs == []


def test_normalize_feishu_config_preserves_secret_file_reference(tmp_path: Path) -> None:
    secret_path = tmp_path / "feishu.secret"
    secret_path.write_text("secret-value\n", encoding="utf-8")

    normalized = rebuild.normalize_feishu_config(
        {
            "enabled": True,
            "accounts": {
                "main": {
                    "appId": "cli_main",
                    "appSecretFile": str(secret_path),
                }
            },
        }
    )

    main = normalized["accounts"]["default"]
    assert main["appSecretFile"] == str(secret_path)
    assert "appSecret" not in main


def test_install_openmind_plugins_copies_repo_plugins_into_state_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rebuild, "ensure_plugin_dependencies", lambda *_args, **_kwargs: None)
    (tmp_path / "openclaw.json").write_text(json.dumps({"plugins": {"installs": {}}}), encoding="utf-8")
    rebuild.install_openmind_plugins(tmp_path, openclaw_bin=Path("/tmp/openclaw"))

    installs = json.loads((tmp_path / "openclaw.json").read_text(encoding="utf-8"))["plugins"]["installs"]
    for plugin_id in rebuild.OPENMIND_PLUGIN_IDS:
        install_path = tmp_path / "extensions" / plugin_id
        assert install_path.is_dir()
        assert not install_path.is_symlink()
        assert rebuild.plugin_fingerprint(install_path) == rebuild.plugin_fingerprint(
            rebuild.REPO_ROOT / "openclaw_extensions" / plugin_id
        )
        assert installs[plugin_id]["sourcePath"] == str((rebuild.REPO_ROOT / "openclaw_extensions" / plugin_id).resolve())
        assert installs[plugin_id]["installPath"] == str(install_path)


def test_install_openmind_plugins_skips_matching_linked_installs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rebuild, "ensure_plugin_dependencies", lambda *_args, **_kwargs: None)
    plugin_dir = tmp_path / "extensions" / "openmind-advisor"
    _seed_plugin_snapshot(plugin_dir, "openmind-advisor")
    (tmp_path / "openclaw.json").write_text(
        json.dumps(
            {
                "plugins": {
                    "installs": {
                        "openmind-advisor": {
                            "source": "path",
                            "sourcePath": str(rebuild.REPO_ROOT / "openclaw_extensions" / "openmind-advisor"),
                            "installPath": str(plugin_dir),
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    rebuild.install_openmind_plugins(tmp_path, openclaw_bin=Path("/tmp/openclaw"))

    assert plugin_dir.is_dir()
    assert rebuild.plugin_fingerprint(plugin_dir) == rebuild.plugin_fingerprint(
        rebuild.REPO_ROOT / "openclaw_extensions" / "openmind-advisor"
    )


def test_install_openmind_plugins_adopts_existing_extension_without_reinstall(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rebuild, "ensure_plugin_dependencies", lambda *_args, **_kwargs: None)
    plugin_dir = tmp_path / "extensions" / "openmind-advisor"
    _seed_plugin_snapshot(plugin_dir, "openmind-advisor")
    (tmp_path / "openclaw.json").write_text(
        json.dumps({"plugins": {"installs": {}}}),
        encoding="utf-8",
    )

    rebuild.install_openmind_plugins(tmp_path, openclaw_bin=Path("/tmp/openclaw"))

    assert plugin_dir.is_dir()
    assert rebuild.plugin_fingerprint(plugin_dir) == rebuild.plugin_fingerprint(
        rebuild.REPO_ROOT / "openclaw_extensions" / "openmind-advisor"
    )
    installs = json.loads((tmp_path / "openclaw.json").read_text(encoding="utf-8"))["plugins"]["installs"]
    record = installs["openmind-advisor"]
    assert record["source"] == "path"
    assert record["sourcePath"] == str((rebuild.REPO_ROOT / "openclaw_extensions" / "openmind-advisor").resolve())
    assert record["installPath"] == str(plugin_dir)


def test_install_openmind_plugins_relinks_when_live_extension_drifted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rebuild, "ensure_plugin_dependencies", lambda *_args, **_kwargs: None)
    plugin_dir = tmp_path / "extensions" / "openmind-memory"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "openclaw.plugin.json").write_text(json.dumps({"id": "openmind-memory"}), encoding="utf-8")
    (plugin_dir / "index.ts").write_text("// stale plugin\n", encoding="utf-8")
    (plugin_dir / "package.json").write_text(json.dumps({"name": "openmind-memory"}), encoding="utf-8")
    (plugin_dir / "README.md").write_text("stale\n", encoding="utf-8")
    (tmp_path / "openclaw.json").write_text(
        json.dumps(
            {
                "plugins": {
                    "installs": {
                        "openmind-memory": {
                            "source": "path",
                            "sourcePath": str((rebuild.REPO_ROOT / "openclaw_extensions" / "openmind-memory").resolve()),
                            "installPath": str(plugin_dir),
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    rebuild.install_openmind_plugins(tmp_path, openclaw_bin=Path("/tmp/openclaw"))

    assert plugin_dir.is_dir()
    assert rebuild.plugin_fingerprint(plugin_dir) == rebuild.plugin_fingerprint(
        rebuild.REPO_ROOT / "openclaw_extensions" / "openmind-memory"
    )
    installs = json.loads((tmp_path / "openclaw.json").read_text(encoding="utf-8"))["plugins"]["installs"]
    assert installs["openmind-memory"]["sourcePath"] == str((rebuild.REPO_ROOT / "openclaw_extensions" / "openmind-memory").resolve())


def test_install_openmind_plugins_removes_untracked_stale_extension_before_install(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rebuild, "ensure_plugin_dependencies", lambda *_args, **_kwargs: None)
    plugin_dir = tmp_path / "extensions" / "openmind-advisor"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "openclaw.plugin.json").write_text(json.dumps({"id": "openmind-advisor"}), encoding="utf-8")
    (plugin_dir / "index.ts").write_text("// stale advisor\n", encoding="utf-8")
    (tmp_path / "openclaw.json").write_text(json.dumps({"plugins": {"installs": {}}}), encoding="utf-8")

    rebuild.install_openmind_plugins(tmp_path, openclaw_bin=Path("/tmp/openclaw"))

    assert plugin_dir.is_dir()
    assert rebuild.plugin_fingerprint(plugin_dir) == rebuild.plugin_fingerprint(
        rebuild.REPO_ROOT / "openclaw_extensions" / "openmind-advisor"
    )


def test_ensure_plugin_dependencies_skips_when_typebox_present(tmp_path: Path, monkeypatch) -> None:
    plugin_dir = tmp_path / "openmind-memory"
    pkg = plugin_dir / "node_modules" / "@sinclair" / "typebox" / "package.json"
    pkg.parent.mkdir(parents=True)
    pkg.write_text('{"name":"@sinclair/typebox"}', encoding="utf-8")

    called = False

    def _fake_run(*args, **kwargs):
        nonlocal called
        called = True
        return None

    monkeypatch.setattr(rebuild.subprocess, "run", _fake_run)

    rebuild.ensure_plugin_dependencies(plugin_dir)

    assert called is False


def test_ensure_plugin_dependencies_installs_when_typebox_missing(tmp_path: Path, monkeypatch) -> None:
    plugin_dir = tmp_path / "openmind-memory"
    plugin_dir.mkdir()
    calls = []

    def _fake_run(cmd, cwd, check, capture_output, text):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "capture_output": capture_output, "text": text})
        return None

    monkeypatch.setattr(rebuild.subprocess, "run", _fake_run)

    rebuild.ensure_plugin_dependencies(plugin_dir)

    assert calls == [
        {
            "cmd": ["npm", "install", "--no-audit", "--no-fund", "--omit=dev"],
            "cwd": str(plugin_dir),
            "check": True,
            "capture_output": True,
            "text": True,
        }
    ]


def test_prune_workspace_skill_symlink_escapes(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "main"
    skills_dir = workspace / "skills"
    skills_dir.mkdir(parents=True)
    outside = tmp_path / "outside-skill"
    outside.mkdir()
    inside = workspace / "inside-skill"
    inside.mkdir()
    (skills_dir / "escape").symlink_to(outside, target_is_directory=True)
    (skills_dir / "keep").symlink_to(inside, target_is_directory=True)
    removed = rebuild.prune_workspace_skill_symlink_escapes(
        (
            rebuild.AgentSpec(
                agent_id="main",
                workspace=str(workspace),
                model="openai-codex/gpt-5.4",
            ),
        )
    )

    assert removed == [str(skills_dir / "escape")]
    assert not (skills_dir / "escape").exists()
    assert (skills_dir / "keep").exists()


def test_prune_volatile_artifacts_clears_service_agent_sessions(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    maint_sessions = state_dir / "agents" / "maintagent" / "sessions"
    main_sessions = state_dir / "agents" / "main" / "sessions"
    maint_sessions.mkdir(parents=True)
    main_sessions.mkdir(parents=True)
    (maint_sessions / "sessions.json").write_text("{}", encoding="utf-8")
    (maint_sessions / "abc.jsonl").write_text("{}", encoding="utf-8")
    (main_sessions / "keep.jsonl").write_text("{}", encoding="utf-8")

    removed = rebuild.prune_volatile_artifacts(state_dir)

    assert "agents/maintagent/sessions/sessions.json" in removed
    assert "agents/maintagent/sessions/abc.jsonl" in removed
    assert not (maint_sessions / "sessions.json").exists()
    assert not (maint_sessions / "abc.jsonl").exists()
    assert (main_sessions / "keep.jsonl").exists()


def _make_jwt(claims: dict) -> str:
    header = {"alg": "RS256", "typ": "JWT"}

    def _encode(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        import base64

        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    return f"{_encode(header)}.{_encode(claims)}.sig"


def test_sync_codex_auth_profiles_rewrites_openai_profile(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    target = state_dir / "agents" / "main" / "agent"
    target.mkdir(parents=True)
    (target / "auth-profiles.json").write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": {
                    "openai-codex:default": {
                        "type": "oauth",
                        "provider": "openai-codex",
                        "access": "old-access",
                        "refresh": "old-refresh",
                        "expires": 1,
                        "accountId": "old-account",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    sibling = state_dir / "agents" / "maintagent" / "agent"
    sibling.mkdir(parents=True)
    (sibling / "auth-profiles.json").write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": {
                    "openai-codex:default": {
                        "type": "oauth",
                        "provider": "openai-codex",
                        "access": "sibling-access",
                        "refresh": "sibling-refresh",
                        "expires": 2,
                        "accountId": "sibling-account",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    auth_json = tmp_path / "auth.json"
    auth_json.write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": _make_jwt(
                        {
                            "exp": 1773195672,
                            "https://api.openai.com/auth": {"chatgpt_account_id": "new-account"},
                        }
                    ),
                    "refresh_token": "new-refresh",
                }
            }
        ),
        encoding="utf-8",
    )

    updated = rebuild.sync_codex_auth_profiles(state_dir, auth_json, ["main", "maintagent"])

    assert updated == ["main", "maintagent"]
    profile = json.loads((target / "auth-profiles.json").read_text(encoding="utf-8"))["profiles"]["openai-codex:default"]
    assert profile["refresh"] == "new-refresh"
    assert profile["accountId"] == "new-account"
    assert profile["expires"] == 1773195672000
    sibling_path = sibling / "auth-profiles.json"
    assert sibling_path.is_symlink() is False
    sibling_profile = json.loads(sibling_path.read_text(encoding="utf-8"))["profiles"]["openai-codex:default"]
    assert sibling_profile["refresh"] == "new-refresh"
    assert sibling_profile["accountId"] == "new-account"
    assert sibling_profile["expires"] == 1773195672000


def test_ensure_workspaces_writes_managed_role_files(tmp_path: Path, monkeypatch) -> None:
    patched_agents = (
        rebuild.AgentSpec("main", str(tmp_path / "main"), "openai-codex/gpt-5.4"),
        rebuild.AgentSpec("maintagent", str(tmp_path / "maintagent"), "google-gemini-cli/gemini-2.5-pro"),
        rebuild.AgentSpec("finbot", str(tmp_path / "finbot"), "openai-codex/gpt-5.4"),
    )
    monkeypatch.setattr(
        rebuild,
        "HEARTBEATS",
        {
            "main": "main heartbeat",
            "maintagent": "maint heartbeat\nNever run `ops/openclaw_orch_agent.py --reconcile` during heartbeat.\n",
            "finbot": "finbot heartbeat\nRun `python3 ops/openclaw_finbot.py dashboard-refresh --format json`.\n",
        },
    )

    rebuild.ensure_workspaces(patched_agents)

    main_agents = (tmp_path / "main" / "AGENTS.md").read_text(encoding="utf-8")
    main_role_packs = (tmp_path / "main" / "ROLE_PACKS.md").read_text(encoding="utf-8")
    maint_tools = (tmp_path / "maintagent" / "TOOLS.md").read_text(encoding="utf-8")
    maint_agents = (tmp_path / "maintagent" / "AGENTS.md").read_text(encoding="utf-8")
    maint_role_packs = (tmp_path / "maintagent" / "ROLE_PACKS.md").read_text(encoding="utf-8")
    maint_heartbeat = (tmp_path / "maintagent" / "HEARTBEAT.md").read_text(encoding="utf-8")
    finbot_tools = (tmp_path / "finbot" / "TOOLS.md").read_text(encoding="utf-8")
    finbot_agents = (tmp_path / "finbot" / "AGENTS.md").read_text(encoding="utf-8")
    finbot_role_packs = (tmp_path / "finbot" / "ROLE_PACKS.md").read_text(encoding="utf-8")
    assert "primary human-facing agent" in main_agents
    assert "Use explicit role packs when the task has a business context" in main_agents
    assert "Do not assume `planning`, `research-orch`, or `openclaw-orch` exist." in main_agents
    assert 'sessionKey="agent:finbot:main"' in main_agents
    assert "default execution lane for investment-research work" in main_agents
    assert "Role packs are explicit business-context overlays for `main`." in main_role_packs
    assert "`devops`" in main_role_packs
    assert "`research`" in main_role_packs
    assert "`source.agent` remains the component/emitter identity" in main_role_packs
    assert "do not use `exec`, `process`, or shell probes" in maint_tools
    assert "legacy `chatgptrest-*` orch agents" in maint_tools
    assert "prefer `gateway`, `session_status`, and `openmind_memory_status`" not in maint_agents
    assert "prefer `session_status` and `sessions_list`" in maint_agents
    assert "does not host user-facing role packs" in maint_role_packs
    assert "Never run `ops/openclaw_orch_agent.py --reconcile`" in maint_agents
    assert "Never run `ops/openclaw_orch_agent.py --reconcile` during heartbeat." in maint_heartbeat
    assert "watchlist-scout" in finbot_tools
    assert "theme-radar-scout" in finbot_tools
    assert "theme-batch-run" in finbot_tools
    assert str(rebuild.FINBOT_CLI_PATH) in finbot_tools
    assert "investment research scout" in finbot_agents
    assert str(rebuild.FINBOT_CLI_PATH) in finbot_agents
    assert "theme radar discovery" in finbot_role_packs
    assert "theme batch research" in finbot_role_packs


def test_essential_backup_copies_auth_profiles_and_manifest(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "openclaw.json").write_text("{}", encoding="utf-8")
    (state_dir / "exec-approvals.json").write_text("{}", encoding="utf-8")
    (state_dir / "credentials").mkdir(parents=True)
    (state_dir / "credentials" / "feishu-pairing.json").write_text("{}", encoding="utf-8")
    (state_dir / "devices").mkdir(parents=True)
    (state_dir / "identity").mkdir(parents=True)
    (state_dir / "secrets").mkdir(parents=True)
    (state_dir / "cron").mkdir(parents=True)
    (state_dir / "cron" / "jobs.json").write_text("{}", encoding="utf-8")
    (state_dir / "subagents").mkdir(parents=True)
    (state_dir / "subagents" / "runs.json").write_text("{}", encoding="utf-8")
    (state_dir / "agents" / "main" / "agent").mkdir(parents=True)
    (state_dir / "agents" / "main" / "agent" / "auth-profiles.json").write_text('{"profiles":{}}', encoding="utf-8")

    backup_root = tmp_path / "backup"
    manifest = rebuild.essential_backup(state_dir, backup_root)

    assert (backup_root / "openclaw.json").exists()
    assert (backup_root / "agents" / "main" / "agent" / "auth-profiles.json").exists()
    assert oct((backup_root.stat().st_mode & 0o777)) == "0o700"
    written_manifest = json.loads((backup_root / "manifest.json").read_text(encoding="utf-8"))
    assert written_manifest["state_dir"] == str(state_dir)
    assert manifest["copied"]


def test_prune_unmanaged_agent_dirs_moves_legacy_agents_into_backup(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    (state_dir / "agents" / "main" / "agent").mkdir(parents=True)
    (state_dir / "agents" / "legacy" / "agent").mkdir(parents=True)
    (state_dir / "agents" / "legacy" / "sessions").mkdir(parents=True)
    backup_root = tmp_path / "backup"

    moved = rebuild.prune_unmanaged_agent_dirs(state_dir, backup_root, {"main"})

    assert moved == ["legacy"]
    assert not (state_dir / "agents" / "legacy").exists()
    assert (backup_root / "unmanaged_agents" / "legacy" / "agent").exists()
    assert (state_dir / "agents" / "main").exists()


def test_prune_unmanaged_cron_jobs_filters_legacy_agents(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    jobs_path = state_dir / "cron" / "jobs.json"
    jobs_path.parent.mkdir(parents=True)
    jobs_path.write_text(
        json.dumps(
            {
                "version": 1,
                "jobs": [
                    {"id": "keep-main", "agentId": "main"},
                    {"id": "drop-legacy", "agentId": "legacy"},
                ],
            }
        ),
        encoding="utf-8",
    )

    removed = rebuild.prune_unmanaged_cron_jobs(state_dir, {"main"})

    assert removed == ["drop-legacy"]
    payload = json.loads(jobs_path.read_text(encoding="utf-8"))
    assert payload["jobs"] == [{"id": "keep-main", "agentId": "main"}]


def test_write_managed_cron_jobs_leaves_ops_without_finbot_agentturn_jobs(tmp_path: Path) -> None:
    jobs_path = rebuild.write_managed_cron_jobs(tmp_path, topology="ops")

    payload = json.loads(jobs_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["jobs"] == []


def test_ensure_gateway_token_file_writes_token(tmp_path: Path) -> None:
    token_path = rebuild.ensure_gateway_token_file(
        tmp_path,
        {"auth": {"mode": "token", "token": "abc123"}},
    )

    assert token_path == tmp_path / "gateway.token"
    assert token_path.read_text(encoding="utf-8") == "abc123\n"
