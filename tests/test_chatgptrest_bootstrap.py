from __future__ import annotations

from chatgptrest.repo_cognition import bootstrap


def test_generate_bootstrap_packet_includes_validation_and_closeout_paths(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "_get_git_info", lambda: {"head": "abc123", "branch": "main"})
    monkeypatch.setattr(bootstrap, "detect_planes", lambda *args, **kwargs: [{"plane": "public_agent", "confidence": 1.0, "reason": "goal"}])
    monkeypatch.setattr(bootstrap, "_load_canonical_docs", lambda planes: [{"path": "AGENTS.md", "role": "entry", "doc_type": "canonical"}])
    monkeypatch.setattr(
        bootstrap,
        "generate_runtime_snapshot",
        lambda mode: {
            "mode": mode,
            "source": "quick_summary",
            "timestamp": "2026-03-31T12:00:00Z",
            "services": [],
            "databases": [],
            "public_mcp_ingress": None,
            "maintenance_timers": None,
        },
    )
    gitnexus_calls: list[dict[str, str]] = []
    monkeypatch.setattr(
        bootstrap,
        "query_gitnexus",
        lambda query, goal_hint="": gitnexus_calls.append({"query": query, "goal_hint": goal_hint}) or {
            "status": "resolved",
            "symbols": [{"name": "repo_bootstrap"}],
            "processes": [],
            "error": None,
            "manual_command": None,
        },
    )
    monkeypatch.setattr(bootstrap, "search_history", lambda *args, **kwargs: [{"path": "docs/dev_log/example.md", "relevance": 0.8, "snippet": "history"}])
    monkeypatch.setattr(
        bootstrap,
        "compute_change_obligations",
        lambda changed_files: [
            {
                "pattern": "chatgptrest/mcp/",
                "plane": "public_agent",
                "must_update": ["AGENTS.md"],
                "baseline_tests": ["tests/test_agent_mcp.py"],
                "dynamic_test_strategy": "gitnexus_impact",
                "reason": "MCP changes",
                "matched_files": ["chatgptrest/mcp/agent_mcp.py"],
                "missing_updates": ["AGENTS.md"],
            }
        ],
    )
    monkeypatch.setattr(
        bootstrap,
        "validate_obligations",
        lambda obligations: {
            "ok": False,
            "required_docs": ["AGENTS.md"],
            "required_tests": ["tests/test_agent_mcp.py"],
            "missing_docs": [],
            "missing_tests": [],
            "missing_updates": ["AGENTS.md"],
        },
    )
    monkeypatch.setattr(bootstrap, "_load_surface_policy", lambda: {"default_for_coding_agents": "http://127.0.0.1:18712/mcp", "disallowed_default_surfaces": []})
    monkeypatch.setattr(bootstrap, "_load_danger_zones", lambda: [])

    packet = bootstrap.generate_bootstrap_packet(
        task_description="Fix public MCP ingress drift",
        changed_files=["chatgptrest/mcp/agent_mcp.py"],
        goal_hint="public_agent",
        runtime_mode="quick",
    )

    assert packet["schema_version"] == "bootstrap-v1"
    assert packet["change_obligation_validation"]["missing_updates"] == ["AGENTS.md"]
    assert packet["closeout_contract"]["closeout_script_path"] == "scripts/chatgptrest_closeout.py"
    assert packet["closeout_contract"]["doc_obligations_script_path"] == "scripts/check_doc_obligations.py"
    assert gitnexus_calls == [{"query": "Fix public MCP ingress drift public_agent", "goal_hint": "public_agent"}]


def test_generate_bootstrap_packet_uses_changed_file_stems_when_task_is_blank(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "_get_git_info", lambda: {"head": "abc123", "branch": "main"})
    monkeypatch.setattr(bootstrap, "detect_planes", lambda *args, **kwargs: [])
    monkeypatch.setattr(bootstrap, "_load_canonical_docs", lambda planes: [])
    monkeypatch.setattr(
        bootstrap,
        "generate_runtime_snapshot",
        lambda mode: {
            "mode": mode,
            "source": "quick_summary",
            "timestamp": "2026-03-31T12:00:00Z",
            "services": [],
            "databases": [],
            "public_mcp_ingress": None,
            "maintenance_timers": None,
        },
    )
    seen: list[str] = []
    monkeypatch.setattr(
        bootstrap,
        "query_gitnexus",
        lambda query, goal_hint="": seen.append(query) or {
            "status": "resolved",
            "symbols": [],
            "processes": [],
            "error": None,
            "manual_command": None,
        },
    )
    monkeypatch.setattr(bootstrap, "search_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(bootstrap, "compute_change_obligations", lambda changed_files: [])
    monkeypatch.setattr(
        bootstrap,
        "validate_obligations",
        lambda obligations: {
            "ok": True,
            "required_docs": [],
            "required_tests": [],
            "missing_docs": [],
            "missing_tests": [],
            "missing_updates": [],
        },
    )
    monkeypatch.setattr(bootstrap, "_load_surface_policy", lambda: {})
    monkeypatch.setattr(bootstrap, "_load_danger_zones", lambda: [])

    bootstrap.generate_bootstrap_packet(changed_files=["chatgptrest/mcp/agent_mcp.py"])

    assert seen == ["agent_mcp"]
