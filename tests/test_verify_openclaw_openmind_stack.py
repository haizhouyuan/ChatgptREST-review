from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "ops" / "verify_openclaw_openmind_stack.py"
_SPEC = importlib.util.spec_from_file_location("verify_openclaw_openmind_stack", _MODULE_PATH)
assert _SPEC and _SPEC.loader
verify = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = verify
_SPEC.loader.exec_module(verify)


def test_resolve_session_transcript_path(tmp_path: Path) -> None:
    state_dir = tmp_path / ".openclaw"
    sessions_dir = state_dir / "agents" / "main" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "sessions.json").write_text(
        json.dumps({"agent:main:main": {"sessionId": "abc-123"}}),
        encoding="utf-8",
    )

    resolved = verify.resolve_session_transcript_path(state_dir, "main", "agent:main:main")

    assert resolved == sessions_dir / "abc-123.jsonl"


def test_resolve_session_transcript_path_prefers_session_file(tmp_path: Path) -> None:
    state_dir = tmp_path / ".openclaw"
    sessions_dir = state_dir / "agents" / "main" / "sessions"
    sessions_dir.mkdir(parents=True)
    transcript = sessions_dir / "actual-session.jsonl"
    transcript.write_text("", encoding="utf-8")
    (sessions_dir / "sessions.json").write_text(
        json.dumps(
            {
                "agent:main:main": {
                    "sessionId": "alias-session-id",
                    "sessionFile": str(transcript),
                }
            }
        ),
        encoding="utf-8",
    )

    resolved = verify.resolve_session_transcript_path(state_dir, "main", "agent:main:main")

    assert resolved == transcript


def test_wait_for_text_detects_marker(tmp_path: Path) -> None:
    transcript = tmp_path / "main.jsonl"
    transcript.write_text('{"message":"VERIFY_PING_123"}\n', encoding="utf-8")

    assert verify.wait_for_text(transcript, "VERIFY_PING_123", timeout_sec=1, poll_sec=0.01) is True
    assert verify.wait_for_text(transcript, "MISSING_TOKEN", timeout_sec=0, poll_sec=0.01) is False


def test_latest_token_in_transcript_returns_last_match(tmp_path: Path) -> None:
    transcript = tmp_path / "main.jsonl"
    transcript.write_text(
        "VERIFY_PING_old\nsomething else\nVERIFY_PING_newer\n",
        encoding="utf-8",
    )

    assert verify.latest_token_in_transcript(transcript) == "VERIFY_PING_newer"


def test_render_markdown_includes_core_fields() -> None:
    report = {
        "generated_at": "2026-03-09T00:00:00+00:00",
        "openclaw_bin": "/usr/bin/openclaw",
        "state_dir": "/tmp/.openclaw",
        "checks": [
            {"name": "plugins_doctor", "ok": True, "detail": "No plugin issues detected."},
            {"name": "maintagent_to_main_transcript", "ok": True, "detail": "VERIFY_PING_abc"},
        ],
        "security_summary": "critical=0 warn=3 info=1",
        "security_findings": ["gateway.trusted_proxies_missing"],
        "topology": "ops",
        "skills_extra_dirs": ["/vol1/1000/projects/ChatgptREST/skills-src"],
        "skills_allow_bundled": [],
        "main_profile": "coding",
        "main_skills": ["chatgptrest-call"],
        "main_tools": {"profile": "coding", "alsoAllow": ["sessions_send", "sessions_list", "sessions_history"], "deny": ["sessions_spawn", "subagents"]},
        "main_effective_tools": ["exec", "openmind_memory_status", "sessions_history", "sessions_list", "sessions_send"],
        "agent_to_agent_allow": ["main", "maintagent", "finbot"],
        "maint_skills": [],
        "maint_tools": {"profile": "minimal", "alsoAllow": ["sessions_send", "sessions_list"]},
        "maint_effective_tools": ["session_status", "sessions_list", "sessions_send"],
        "plugins_allow": ["acpx", "openmind-memory"],
        "plugins_load_paths": [],
        "gateway_config": {"bind": "loopback", "trustedProxies": ["127.0.0.1/32"], "auth": {"mode": "token", "token": "<redacted>"}, "tailscale": {"mode": "off"}},
        "feishu_tools": {"doc": False, "chat": False, "wiki": False, "drive": False, "perm": False, "scopes": False},
        "review_evidence": {"verifier_json": "docs/reviews/openclaw_openmind_verifier_ops_20260309.json"},
        "advisor_auth_probe": {"unauthenticated_status": 401, "authenticated_status": 200},
        "openmind_probe_token": "OPENMIND_PROBE_abc",
        "openmind_probe_reply": "OPENMIND_OK OPENMIND_PROBE_abc",
        "openmind_tool_round_detail": "tool_called=True tool_result=True assistant='OPENMIND_OK OPENMIND_PROBE_abc'",
        "openmind_tool_details": {"ok": True, "memory_ready": True},
        "memory_capture_marker": "TRAVEL_PREF_abc",
        "memory_capture_reply": "CAPTURE_OK TRAVEL_PREF_abc",
        "memory_capture_tool_round_detail": "tool_called=True tool_result=True assistant='CAPTURE_OK TRAVEL_PREF_abc'",
        "memory_capture_tool_details": {"ok": True, "results": [{"ok": True, "record_id": "mem-1", "audit_trail": []}]},
        "memory_recall_reply": "RECALL_OK TRAVEL_PREF_abc",
        "memory_recall_tool_round_detail": "tool_called=True tool_result=True assistant='RECALL_OK TRAVEL_PREF_abc'",
        "memory_recall_tool_details": {
            "ok": True,
            "prompt_prefix": "## Remembered Guidance\nPrefer Hangzhou. Marker TRAVEL_PREF_abc.",
            "context_blocks": [{"source_type": "captured", "text": "Prefer Hangzhou. Marker TRAVEL_PREF_abc."}],
        },
        "role_capture_marker": "ROLE_DEVOPS_abc",
        "role_capture_reply": "ROLE_CAPTURE_OK ROLE_DEVOPS_abc",
        "role_capture_tool_round_detail": "tool_called=True tool_result=True assistant='ROLE_CAPTURE_OK ROLE_DEVOPS_abc'",
        "role_capture_tool_details": {"ok": True, "results": [{"ok": True, "record_id": "mem-role-1", "audit_trail": []}]},
        "role_devops_recall_reply": "ROLE_RECALL_DEVOPS_OK ROLE_DEVOPS_abc",
        "role_devops_recall_tool_round_detail": "tool_called=True tool_result=True assistant='ROLE_RECALL_DEVOPS_OK ROLE_DEVOPS_abc'",
        "role_devops_recall_tool_details": {
            "ok": True,
            "metadata": {"role_id": "devops", "kb_scope_tags": ["ops", "runbook"]},
            "context_blocks": [{"source_type": "captured", "text": "ROLE_DEVOPS_abc"}],
        },
        "role_research_recall_reply": "ROLE_RECALL_RESEARCH_OK ROLE_DEVOPS_abc",
        "role_research_recall_tool_round_detail": "tool_called=True tool_result=True assistant='ROLE_RECALL_RESEARCH_OK ROLE_DEVOPS_abc'",
        "role_research_recall_tool_details": {
            "ok": True,
            "metadata": {"role_id": "research", "kb_scope_tags": ["research", "analysis"]},
            "context_blocks": [{"source_type": "policy", "text": "Use evidence-first reasoning."}],
        },
        "sessions_spawn_probe_token": "NEGPROBE_spawn",
        "sessions_spawn_probe_reply": "SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_spawn",
        "sessions_spawn_probe_detail": "tool_called=False tool_result=False assistant='SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_spawn'",
        "subagents_probe_token": "NEGPROBE_subagents",
        "subagents_probe_reply": "SUBAGENTS_UNAVAILABLE NEGPROBE_subagents",
        "subagents_probe_detail": "tool_called=False tool_result=False assistant='SUBAGENTS_UNAVAILABLE NEGPROBE_subagents'",
        "comm_token": "VERIFY_PING_abc",
        "comm_probe_reply": "SENT",
        "comm_seen_in_main_transcript": True,
        "main_latest_transcript_token": "VERIFY_PING_abc",
    }

    markdown = verify.render_markdown(report)

    assert "# OpenClaw + OpenMind Verification Report" in markdown
    assert "`plugins_doctor`: PASS" in markdown
    assert "OPENMIND_OK OPENMIND_PROBE_abc" in markdown
    assert "`VERIFY_PING_abc`" in markdown
    assert '`["main", "maintagent", "finbot"]`' in markdown
    assert '"sessions_history"' in markdown
    assert '"sessions_spawn"' in markdown
    assert '"doc": false' in markdown
    assert '"wiki": false' in markdown
    assert '`[]`' in markdown
    assert '"bind": "loopback"' in markdown
    assert '"trustedProxies": ["127.0.0.1/32"]' in markdown
    assert "- topology: `ops`" in markdown
    assert "CAPTURE_OK TRAVEL_PREF_abc" in markdown
    assert "RECALL_OK TRAVEL_PREF_abc" in markdown
    assert "ROLE_CAPTURE_OK ROLE_DEVOPS_abc" in markdown
    assert "ROLE_RECALL_DEVOPS_OK ROLE_DEVOPS_abc" in markdown
    assert "ROLE_RECALL_RESEARCH_OK ROLE_DEVOPS_abc" in markdown
    assert "SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_spawn" in markdown
    assert "SUBAGENTS_UNAVAILABLE NEGPROBE_subagents" in markdown
    assert '"unauthenticated_status": 401' in markdown
    assert '"verifier_json": "docs/reviews/openclaw_openmind_verifier_ops_20260309.json"' in markdown


def test_extract_json_payload_skips_prefix_noise() -> None:
    payload = verify.extract_json_payload(
        "[plugins] feishu: ok\n(node:1) warning\n{\n  \"gateway\": {\"reachable\": true}\n}\n"
    )

    assert payload["gateway"]["reachable"] is True


def test_run_cmd_merges_env(monkeypatch) -> None:
    captured = {}

    def _fake_run(*args, **kwargs):
        captured["env"] = kwargs.get("env")

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr(verify.subprocess, "run", _fake_run)

    verify.run_cmd(["echo", "ok"], env={"OPENCLAW_STATE_DIR": "/tmp/state"})

    assert captured["env"]["OPENCLAW_STATE_DIR"] == "/tmp/state"


def test_inspect_tool_round_detects_openmind_call(tmp_path: Path) -> None:
    transcript = tmp_path / "main.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Call tool OPENMIND_PROBE_abc"}],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "thinking", "thinking": ""},
                                {"type": "toolCall", "name": "openmind_memory_status", "arguments": {}},
                            ],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "toolResult",
                            "toolName": "openmind_memory_status",
                            "details": {"ok": True, "memory_ready": True},
                            "isError": False,
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "OPENMIND_OK OPENMIND_PROBE_abc"}],
                        }
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = verify.inspect_tool_round(
        transcript,
        user_needle="OPENMIND_PROBE_abc",
        tool_name="openmind_memory_status",
        assistant_reply="OPENMIND_OK OPENMIND_PROBE_abc",
    )

    assert result["ok"] is True
    assert result["tool_called"] is True
    assert result["tool_result"] is True
    assert result["tool_details"]["memory_ready"] is True


def test_inspect_tool_round_tolerates_provider_fallback_bridge(tmp_path: Path) -> None:
    transcript = tmp_path / "main.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Call tool OPENMIND_PROBE_bridge"}],
                        }
                    }
                ),
                json.dumps({"message": {"role": "assistant", "content": []}}),
                json.dumps(
                    {
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Continue where you left off. The previous model attempt failed or timed out.",
                                }
                            ],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "thinking", "thinking": ""},
                                {"type": "toolCall", "name": "openmind_memory_status", "arguments": {}},
                            ],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "toolResult",
                            "toolName": "openmind_memory_status",
                            "details": {"ok": True, "memory_ready": True},
                            "isError": False,
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "OPENMIND_OK OPENMIND_PROBE_bridge"}],
                        }
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = verify.inspect_tool_round(
        transcript,
        user_needle="OPENMIND_PROBE_bridge",
        tool_name="openmind_memory_status",
        assistant_reply="OPENMIND_OK OPENMIND_PROBE_bridge",
    )

    assert result["ok"] is True
    assert result["tool_called"] is True
    assert result["tool_result"] is True


def test_inspect_unavailable_tool_round_requires_no_tool_call(tmp_path: Path) -> None:
    transcript = tmp_path / "main.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Try tool NEGPROBE_abc"}],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_abc"}],
                        }
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = verify.inspect_unavailable_tool_round(
        transcript,
        user_needle="NEGPROBE_abc",
        tool_name="sessions_spawn",
        assistant_reply="SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_abc",
    )

    assert result["ok"] is True
    assert result["tool_called"] is False
    assert result["tool_result"] is False
    assert result["assistant_text"] == "SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_abc"


def test_inspect_unavailable_tool_round_tolerates_provider_fallback_bridge(tmp_path: Path) -> None:
    transcript = tmp_path / "main.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Try tool NEGPROBE_bridge"}],
                        }
                    }
                ),
                json.dumps({"message": {"role": "assistant", "content": []}}),
                json.dumps(
                    {
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Continue where you left off. The previous model attempt failed or timed out.",
                                }
                            ],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_bridge"}],
                        }
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = verify.inspect_unavailable_tool_round(
        transcript,
        user_needle="NEGPROBE_bridge",
        tool_name="sessions_spawn",
        assistant_reply="SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_bridge",
    )

    assert result["ok"] is True
    assert result["tool_called"] is False
    assert result["tool_result"] is False


def test_inspect_tool_round_uses_matching_turn_when_marker_repeats(tmp_path: Path) -> None:
    transcript = tmp_path / "main.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps({"message": {"role": "user", "content": [{"type": "text", "text": "capture MARKER_repeat"}]}}),
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "toolCall", "name": "openmind_memory_capture", "arguments": {"text": "MARKER_repeat"}}],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "toolResult",
                            "toolName": "openmind_memory_capture",
                            "details": {"ok": True, "results": [{"ok": True, "record_id": "mem-1", "audit_trail": []}]},
                            "isError": False,
                        }
                    }
                ),
                json.dumps({"message": {"role": "assistant", "content": [{"type": "text", "text": "CAPTURE_OK MARKER_repeat"}]}}),
                json.dumps(
                    {
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "recall MARKER_repeat"}],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "toolCall",
                                    "name": "openmind_memory_recall",
                                    "arguments": {"query": "MARKER_repeat"},
                                }
                            ],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "toolResult",
                            "toolName": "openmind_memory_recall",
                            "details": {"ok": True, "context_blocks": [{"source_type": "captured", "text": "MARKER_repeat"}]},
                            "isError": False,
                        }
                    }
                ),
                json.dumps({"message": {"role": "assistant", "content": [{"type": "text", "text": "RECALL_OK MARKER_repeat"}]}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = verify.inspect_tool_round(
        transcript,
        user_needle="MARKER_repeat",
        tool_name="openmind_memory_capture",
        assistant_reply="CAPTURE_OK MARKER_repeat",
    )

    assert result["ok"] is True
    assert result["tool_called"] is True
    assert result["tool_result"] is True
    assert result["assistant_text"] == "CAPTURE_OK MARKER_repeat"


def test_normalize_assistant_text_strips_reply_wrapper() -> None:
    assert verify.normalize_assistant_text("[[reply_to_current]] OPENMIND_OK TOKEN") == "OPENMIND_OK TOKEN"
    assert verify.normalize_assistant_text("OPENMIND_OK TOKEN") == "OPENMIND_OK TOKEN"


def test_is_provider_fallback_bridge_user_message_detects_exact_bridge() -> None:
    message = {
        "role": "user",
        "content": [{"type": "text", "text": "Continue where you left off. The previous model attempt failed or timed out."}],
    }
    assert verify.is_provider_fallback_bridge_user_message(message) is True


def test_is_provider_fallback_bridge_user_message_detects_bridge_inside_context() -> None:
    message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    "<openmind-context>\nremembered context\n</openmind-context>\n\n"
                    "Continue where you left off. The previous model attempt failed or timed out."
                ),
            }
        ],
    }
    assert verify.is_provider_fallback_bridge_user_message(message) is True


def test_probe_reply_ok_accepts_exact_match() -> None:
    assert verify.probe_reply_ok("OPENMIND_OK TOKEN", "OPENMIND_OK TOKEN") is True


def test_probe_reply_ok_accepts_empty_reply_when_transcript_succeeded() -> None:
    assert verify.probe_reply_ok("", "OPENMIND_OK TOKEN", transcript_round_ok=True) is True


def test_probe_reply_ok_rejects_empty_reply_without_transcript_success() -> None:
    assert verify.probe_reply_ok("", "OPENMIND_OK TOKEN", transcript_round_ok=False) is False


def test_capture_details_ok_requires_record_and_audit() -> None:
    assert verify.capture_details_ok({"results": [{"ok": True, "record_id": "mem-1", "audit_trail": []}]}) is True
    assert verify.capture_details_ok({"results": [{"ok": True, "record_id": "", "audit_trail": []}]}) is False


def test_recall_details_helpers_detect_captured_marker() -> None:
    details = {
        "prompt_prefix": "## Remembered Guidance\nPrefer Hangzhou. Marker TRAVEL_PREF_abc.",
        "context_blocks": [
            {"source_type": "captured", "text": "Prefer Hangzhou. Marker TRAVEL_PREF_abc."},
            {"source_type": "policy", "text": "- use retrieved evidence"},
        ],
    }

    assert verify.recall_details_have_captured_block(details) is True
    assert verify.recall_details_contain_text(details, "TRAVEL_PREF_abc") is True
    assert verify.recall_details_contain_text(details, "missing-marker") is False


def test_recall_details_role_and_scope_helpers() -> None:
    details = {
        "metadata": {"role_id": "devops", "kb_scope_tags": ["ops", "runbook"]},
        "context_blocks": [{"source_type": "captured", "text": "marker"}],
    }

    assert verify.recall_details_role_id(details) == "devops"
    assert verify.recall_details_scope_tags(details) == ["ops", "runbook"]


def test_transcript_excerpt_returns_round_messages(tmp_path: Path) -> None:
    transcript = tmp_path / "main.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps({"message": {"role": "user", "content": [{"type": "text", "text": "marker-1"}]}}),
                json.dumps({"message": {"role": "assistant", "content": [{"type": "toolCall", "name": "demo_tool", "arguments": {}}]}}),
                json.dumps({"message": {"role": "toolResult", "toolName": "demo_tool", "details": {"ok": True}, "isError": False}}),
                json.dumps({"message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]}}),
                json.dumps({"message": {"role": "user", "content": [{"type": "text", "text": "next-marker"}]}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    excerpt = verify.transcript_excerpt(transcript, user_needle="marker-1")

    assert excerpt[0]["role"] == "user"
    assert excerpt[1]["toolCalls"] == ["demo_tool"]
    assert excerpt[2]["toolName"] == "demo_tool"
    assert excerpt[3]["text"] == "done"


def test_redact_recursive_masks_sensitive_keys() -> None:
    value = {
        "gateway": {"auth": {"token": "abc"}},
        "plugins": {"entries": {"openmind-memory": {"config": {"endpoint": {"apiKey": "secret"}}}}},
        "channels": {"feishu": {"accounts": {"main": {"appSecretFile": "/tmp/secret"}}}},
    }

    redacted = verify.redact_recursive(value)

    assert redacted["gateway"]["auth"]["token"] == "<redacted>"
    assert redacted["plugins"]["entries"]["openmind-memory"]["config"]["endpoint"]["apiKey"] == "<redacted>"
    assert redacted["channels"]["feishu"]["accounts"]["main"]["appSecretFile"] == "<redacted>"


def test_publish_review_evidence_writes_review_safe_bundle(tmp_path: Path) -> None:
    original_repo_root = verify.REPO_ROOT
    verify.REPO_ROOT = tmp_path
    review_docs_dir = tmp_path / "docs" / "reviews"
    report = {
        "topology": "lean",
        "checks": [],
        "review_evidence": {},
        "advisor_auth_probe": {"unauthenticated_status": 401},
        "generated_at": "2026-03-09T00:00:00+00:00",
        "openclaw_bin": "/tmp/openclaw",
        "state_dir": "/tmp/.openclaw",
        "security_summary": "critical=0 warn=0 info=0",
        "security_findings": [],
        "skills_extra_dirs": [],
        "skills_allow_bundled": [],
        "main_profile": "coding",
        "main_skills": ["chatgptrest-call"],
        "main_tools": {"profile": "coding"},
        "main_effective_tools": ["read"],
        "agent_to_agent_allow": [],
        "maint_skills": [],
        "maint_tools": {"profile": "minimal"},
        "maint_effective_tools": ["session_status"],
        "plugins_allow": [],
        "plugins_load_paths": [],
        "gateway_config": {"auth": {"token": "<redacted>"}},
        "feishu_tools": {},
        "openmind_probe_token": "token",
        "openmind_probe_reply": "reply",
        "openmind_tool_round_detail": "detail",
        "openmind_tool_details": {"ok": True},
        "memory_capture_marker": "marker",
        "memory_capture_reply": "capture",
        "memory_capture_tool_round_detail": "capture-detail",
        "memory_capture_tool_details": {"ok": True},
        "memory_recall_reply": "recall",
        "memory_recall_tool_round_detail": "recall-detail",
        "memory_recall_tool_details": {"ok": True},
        "role_capture_marker": "role-marker",
        "role_capture_reply": "role-capture",
        "role_capture_tool_round_detail": "role-capture-detail",
        "role_capture_tool_details": {"ok": True},
        "role_devops_recall_reply": "role-devops-recall",
        "role_devops_recall_tool_round_detail": "role-devops-recall-detail",
        "role_devops_recall_tool_details": {"ok": True},
        "role_research_recall_reply": "role-research-recall",
        "role_research_recall_tool_round_detail": "role-research-recall-detail",
        "role_research_recall_tool_details": {"ok": True},
        "sessions_spawn_probe_token": "neg",
        "sessions_spawn_probe_reply": "neg-reply",
        "sessions_spawn_probe_detail": "neg-detail",
        "subagents_probe_token": "sub",
        "subagents_probe_reply": "sub-reply",
        "subagents_probe_detail": "sub-detail",
        "comm_token": "",
        "comm_probe_reply": "",
        "comm_seen_in_main_transcript": False,
        "main_latest_transcript_token": "",
    }

    try:
        paths = verify.publish_review_evidence(
            review_docs_dir=review_docs_dir,
            report=report,
            config_payload={"gateway": {"auth": {"token": "secret"}}},
            openmind_excerpt=[{"role": "assistant", "text": "OPENMIND_OK"}],
            memory_capture_excerpt=[],
            memory_recall_excerpt=[],
            role_capture_excerpt=[],
            role_devops_recall_excerpt=[],
            role_research_recall_excerpt=[],
            sessions_spawn_excerpt=[],
            subagents_excerpt=[],
            maint_excerpt=[],
            review_label="20260309",
            auth_probe={"unauthenticated_status": 401},
        )
    finally:
        verify.REPO_ROOT = original_repo_root

    assert (tmp_path / paths["verifier_json"]).is_file()
    assert (tmp_path / paths["config_snapshot"]).is_file()
    assert (tmp_path / paths["transcript_excerpt"]).is_file()
    assert (tmp_path / paths["auth_probe"]).is_file()


def test_infer_topology_matches_supported_layouts() -> None:
    assert verify.infer_topology({"main"}) == "lean"
    assert verify.infer_topology({"main", "maintagent", "autoorch"}) == "ops"
    assert verify.infer_topology({"main", "maintagent", "finbot"}) == "ops"
    assert verify.infer_topology({"main", "planning"}) == "custom"


def test_infer_topology_accepts_retired_extras() -> None:
    original = set(verify.RETIRED_AGENT_IDS)
    try:
        verify.RETIRED_AGENT_IDS = {"chatgptrest-orch", "chatgptrest-guardian"}
        assert verify.infer_topology({"main", "maintagent", "chatgptrest-orch"}) == "ops"
        assert verify.infer_topology({"main", "chatgptrest-guardian"}) == "lean"
    finally:
        verify.RETIRED_AGENT_IDS = original


def test_effective_tools_expands_profile_and_respects_deny() -> None:
    tools = verify.effective_tools(
        {
            "profile": "coding",
            "alsoAllow": ["openmind_memory_status", "sessions_send"],
            "deny": ["sessions_spawn", "subagents", "group:automation", "image"],
        }
    )

    assert "exec" in tools
    assert "sessions_send" in tools
    assert "openmind_memory_status" in tools
    assert "sessions_spawn" not in tools
    assert "subagents" not in tools
    assert "cron" not in tools
    assert "image" not in tools


def test_normalize_path_list_resolves_unique_paths(tmp_path: Path) -> None:
    path = tmp_path / "skills"
    path.mkdir()

    normalized = verify.normalize_path_list([str(path), str(path), "", "   "])

    assert normalized == [str(path.resolve())]


def test_is_repo_skill_dir_accepts_repo_owned_checkout(tmp_path: Path) -> None:
    repo_root = tmp_path / "chatgptrest-checkout"
    skill_dir = repo_root / "skills-src" / "chatgptrest-call"
    app_py = repo_root / "chatgptrest" / "api"
    skill_dir.mkdir(parents=True)
    app_py.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (app_py / "app.py").write_text("app = object()\n", encoding="utf-8")

    assert verify.is_repo_skill_dir(str(repo_root / "skills-src")) is True
    assert verify.skills_repo_only_ok([str(repo_root / "skills-src")], []) is True
    assert verify.skills_repo_only_ok([str(repo_root / "skills-src")], ["bundled"]) is False


def test_expected_heartbeat_agent_count_accepts_retired_extras() -> None:
    original_topologies = dict(verify.TOPOLOGY_AGENT_IDS)
    original_retired = set(verify.RETIRED_AGENT_IDS)
    try:
        verify.TOPOLOGY_AGENT_IDS = {"lean": {"main"}, "ops": {"main", "maintagent"}}
        verify.RETIRED_AGENT_IDS = {"chatgptrest-orch", "chatgptrest-guardian"}
        assert verify.expected_heartbeat_agent_count({"main", "maintagent"}, "ops") == 2
        assert verify.expected_heartbeat_agent_count(
            {"main", "maintagent", "chatgptrest-orch", "chatgptrest-guardian"},
            "ops",
        ) == 4
    finally:
        verify.TOPOLOGY_AGENT_IDS = original_topologies
        verify.RETIRED_AGENT_IDS = original_retired


def test_redact_gateway_config_masks_auth_token() -> None:
    gateway = {
        "bind": "loopback",
        "trustedProxies": ["127.0.0.1/32"],
        "auth": {"mode": "token", "allowTailscale": True, "token": "secret-token"},
    }

    redacted = verify.redact_gateway_config(gateway)

    assert redacted["auth"]["token"] == "<redacted>"
    assert gateway["auth"]["token"] == "secret-token"


def test_gateway_token_present_detects_non_empty_token() -> None:
    assert verify.gateway_token_present({"auth": {"mode": "token", "token": "abc"}}) is True
    assert verify.gateway_token_present({"auth": {"mode": "token", "token": ""}}) is False
