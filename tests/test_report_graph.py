"""Tests for Report Graph (T2.3).

Covers:
    - Graph compiles and runs end-to-end
    - purpose_identify extracts purpose/scope/audience
    - evidence_pack returns evidence IDs
    - internal_draft produces sections
    - review produces notes
    - finalize marks complete on review_pass
    - Custom LLM connector injection
"""

import pytest

from chatgptrest.advisor import graph as graph_mod
from chatgptrest.advisor.report_graph import (
    ReportState,
    build_report_graph,
    purpose_identify,
    evidence_pack,
    web_research,
    internal_draft,
    external_draft,
    review,
    redact_gate,
    finalize,
)


@pytest.fixture
def app():
    graph = build_report_graph()
    return graph.compile()


def _safe_llm(prompt, system_msg=""):
    """Mock LLM that passes redact gate (contains '无敏感信息')."""
    if "审核" in prompt or "review" in prompt.lower():
        return "审核通过。\n[通过]"
    if "检查" in prompt or "敏感" in prompt:
        return "无敏感信息"
    return f"[mock] {prompt[:60]}"


# ── Node Unit Tests ───────────────────────────────────────────────

def test_purpose_identify():
    state: ReportState = {"user_message": "安徽项目进展报告", "report_type": "progress"}
    result = purpose_identify(state)
    assert "purpose" in result
    assert "scope" in result
    assert "audience" in result


def test_web_research_uses_pack_min_evidence_threshold() -> None:
    calls: list[str] = []

    def _llm(prompt: str, system_msg: str = "") -> str:
        calls.append(prompt)
        return (
            "1. 官方数据 A：2025 年市场规模达到 100 亿元。\n"
            "2. 官方数据 B：前三家厂商合计份额超过 60%。\n"
            "3. 官方数据 C：国产替代率较去年继续提升。\n"
            "4. 官方数据 D：下游需求主要来自机器人与高端装备。\n"
            "5. 官方数据 E：关键来源仍需持续交叉核验。"
        )

    result = web_research(
        {
            "user_message": "请输出一份行星滚柱丝杠行业研究报告",
            "purpose": "研究报告",
            "evidence_count": 3,
            "evidence_summaries": ["[KB] 现有证据"],
            "llm_connector": _llm,
            "scenario_pack": {
                "profile": "research_report",
                "acceptance": {"min_evidence_items": 4},
                "evidence_required": {
                    "prefer_primary_sources": True,
                    "require_traceable_claims": True,
                },
            },
        }
    )

    assert calls
    assert result["evidence_count"] == 2
    assert "research_report" in calls[0]


def test_evidence_pack_no_hub():
    """Without kb_hub, evidence_pack returns empty."""
    state: ReportState = {"scope": "安徽项目"}
    result = evidence_pack(state)
    assert result["evidence_count"] == 0
    assert result["evidence_ids"] == []


def test_draft_produces_sections():
    state: ReportState = {"purpose": "progress report", "scope": "test", "evidence_count": 5}
    result = internal_draft(state)
    assert "internal_draft_text" in result
    assert len(result["draft_sections"]) >= 3


def test_review_passes():
    state: ReportState = {
        "internal_draft_text": "This is a draft report with evidence.",
        "llm_connector": _safe_llm,
    }
    result = review(state)
    assert result["review_pass"] is True
    assert len(result["review_notes"]) > 0


def test_finalize_complete():
    state: ReportState = {"internal_draft_text": "Final report", "review_pass": True, "redact_pass": True}
    result = finalize(state)
    assert result["final_status"] == "complete"
    assert result["final_text"] == "Final report"


def test_finalize_needs_revision():
    state: ReportState = {"internal_draft_text": "Bad draft", "review_pass": False,
                          "review_notes": ["needs more data"], "redact_pass": True}
    result = finalize(state)
    assert result["final_status"] == "needs_revision"


def test_finalize_redact_blocked():
    state: ReportState = {"internal_draft_text": "Draft", "redact_pass": False,
                          "redact_issues": ["contains PII"]}
    result = finalize(state)
    assert result["final_status"] == "redact_blocked"


def test_redact_gate_no_pii():
    """With safe LLM, redact_gate passes."""
    state: ReportState = {"internal_draft_text": "Safe report content",
                          "llm_connector": _safe_llm}
    result = redact_gate(state)
    assert result["redact_pass"] is True


def test_redact_gate_scans_tail_sections() -> None:
    calls: list[str] = []

    def tail_sensitive_llm(prompt, system_msg=""):
        calls.append(prompt)
        if "APIKEY-TAIL-SECRET" in prompt:
            return "发现 API密钥: APIKEY-TAIL-SECRET"
        return "无敏感信息"

    state: ReportState = {
        "internal_draft_text": ("安全前文。" * 400) + " APIKEY-TAIL-SECRET",
        "llm_connector": tail_sensitive_llm,
    }
    result = redact_gate(state)

    assert result["redact_pass"] is False
    assert any("API密钥" in issue for issue in result["redact_issues"])
    assert len(calls) >= 2


# ── End-to-End ────────────────────────────────────────────────────

def test_graph_compiles(app):
    assert app is not None


def test_graph_full_run(app):
    result = app.invoke({
        "user_message": "帮我写个安徽项目进展报告",
        "report_type": "progress",
        "llm_connector": _safe_llm,
    })
    assert result["final_status"] == "complete"
    assert len(result["draft_sections"]) >= 3


def test_graph_with_custom_llm(app):
    """Custom LLM connector is used by nodes."""
    calls = []
    def tracking_llm(prompt, system_msg=""):
        calls.append(prompt)
        if "审核" in prompt or "review" in prompt.lower():
            return f"审核通过\n[通过] Custom response: {len(calls)}"
        if "检查" in prompt or "敏感" in prompt:
            return "无敏感信息"
        return f"Custom response: {len(calls)}"

    result = app.invoke({
        "user_message": "write a report",
        "report_type": "analysis",
        "llm_connector": tracking_llm,
    })
    assert len(calls) >= 2  # at least purpose + draft + review
    assert result["final_status"] == "complete"


def test_finalize_skips_exports_without_delivery_target(monkeypatch):
    calls = {"google": 0, "obsidian": 0}

    class _FakeGoogleWorkspace:
        def __init__(self):
            calls["google"] += 1

    class _FakeObsidianClient:
        def __init__(self):
            calls["obsidian"] += 1

    monkeypatch.setattr("chatgptrest.advisor.report_graph.GoogleWorkspace", _FakeGoogleWorkspace)
    monkeypatch.setattr("chatgptrest.advisor.report_graph.ObsidianClient", _FakeObsidianClient)

    result = finalize(
        {
            "internal_draft_text": "Final report",
            "review_pass": True,
            "redact_pass": True,
            "_delivery_target": "",
        }
    )

    assert result["final_status"] == "complete"
    assert result["final_text"] == "Final report"
    assert calls == {"google": 0, "obsidian": 0}


def test_finalize_google_delivery_queues_outbox_without_direct_side_effects(monkeypatch):
    calls = {"google_init": 0}
    enqueued: list[dict] = []

    class _FakeGoogleWorkspace:
        def __init__(self):
            calls["google_init"] += 1

    class _FakeOutbox:
        def enqueue(self, **payload):
            enqueued.append(payload)
            return "eff_google_delivery"

    monkeypatch.setattr("chatgptrest.advisor.report_graph.GoogleWorkspace", _FakeGoogleWorkspace)
    monkeypatch.setenv("OPENMIND_GMAIL_DESTINATION", "leader@example.com")

    result = finalize(
        {
            "internal_draft_text": "Queued report",
            "review_pass": True,
            "redact_pass": True,
            "_delivery_target": "google_drive",
            "_effects_outbox": _FakeOutbox(),
            "trace_id": "trace-google-123456",
            "purpose": "Launch readiness",
            "audience": "leadership",
            "stationery_type": "executive",
        }
    )

    assert result["final_status"] == "complete"
    assert "云端文档已排队" in result["final_text"]
    assert calls["google_init"] == 0
    assert len(enqueued) == 1
    payload = enqueued[0]
    assert payload["effect_type"] == "workspace_action"
    assert payload["effect_key"] == "workspace_action::trace-google-123456::deliver_report_to_docs"
    assert payload["payload"]["workspace_request"]["payload"]["notify_email"] == "leader@example.com"


def test_finalize_google_delivery_without_outbox_skips_direct_side_effects(monkeypatch):
    calls = {"google_init": 0}

    class _FakeGoogleWorkspace:
        def __init__(self):
            calls["google_init"] += 1

    monkeypatch.setattr("chatgptrest.advisor.report_graph.GoogleWorkspace", _FakeGoogleWorkspace)

    result = finalize(
        {
            "internal_draft_text": "Queued report",
            "review_pass": True,
            "redact_pass": True,
            "_delivery_target": "google_drive",
            "trace_id": "trace-google-654321",
            "purpose": "Launch readiness",
        }
    )

    assert result["final_status"] == "complete"
    assert "effects outbox unavailable" in result["final_text"]
    assert calls["google_init"] == 0


def test_execute_report_avoids_serializing_runtime_services(monkeypatch):
    captured: dict[str, object] = {}

    class _DummyReportApp:
        def compile(self):
            return self

        def invoke(self, payload):
            captured.update(payload)
            return {
                "final_status": "complete",
                "final_text": "report body",
                "draft_sections": ["Summary"],
                "review_notes": [],
                "review_pass": True,
                "evidence_count": 1,
            }

    runtime = type(
        "_Runtime",
        (),
        {
            "llm_connector": object(),
            "kb_hub": object(),
            "policy_engine": object(),
            "outbox": object(),
            "memory": None,
            "evomap_observer": None,
            "kb_registry": None,
            "event_bus": None,
            "model_router": None,
            "writeback_service": None,
        },
    )()

    monkeypatch.setattr("chatgptrest.advisor.report_graph.build_report_graph", lambda: _DummyReportApp())
    monkeypatch.setattr(graph_mod, "_kb_writeback_and_record", lambda **_kwargs: {"success": True})

    monkeypatch.setattr(graph_mod, "execute_workspace_effects_for_trace", lambda *_args, **_kwargs: [])

    with graph_mod.bind_runtime_services(runtime):
        result = graph_mod.execute_report(
            {
                "user_message": "请输出周报并发到 Google Drive",
                "trace_id": "trace-report-1",
                "report_type": "analysis",
                "_delivery_target": "google_drive",
            }
        )

    assert result["route_status"] == "complete"
    assert captured["report_type"] == "analysis"
    assert captured["_delivery_target"] == "google_drive"
    assert "llm_connector" not in captured
    assert "kb_hub" not in captured
    assert "_policy_engine" not in captured
    assert "_effects_outbox" not in captured


def test_execute_report_derives_analysis_type_from_research_pack(monkeypatch):
    captured: dict[str, object] = {}

    class _DummyReportApp:
        def compile(self):
            return self

        def invoke(self, payload):
            captured.update(payload)
            return {
                "final_status": "complete",
                "final_text": "report body",
                "draft_sections": ["Summary"],
                "review_notes": [],
                "review_pass": True,
                "evidence_count": 1,
            }

    runtime = type(
        "_Runtime",
        (),
        {
            "llm_connector": object(),
            "kb_hub": object(),
            "policy_engine": object(),
            "outbox": object(),
            "memory": None,
            "evomap_observer": None,
            "kb_registry": None,
            "event_bus": None,
            "model_router": None,
            "writeback_service": None,
        },
    )()

    monkeypatch.setattr("chatgptrest.advisor.report_graph.build_report_graph", lambda: _DummyReportApp())
    monkeypatch.setattr(graph_mod, "_kb_writeback_and_record", lambda **_kwargs: {"success": True})

    with graph_mod.bind_runtime_services(runtime):
        result = graph_mod.execute_report(
            {
                "user_message": "请输出一份行业研究报告",
                "trace_id": "trace-report-research-pack",
                "scenario_pack": {
                    "profile": "research_report",
                    "provider_hints": {"report_type": "analysis"},
                },
            }
        )

    assert result["route_status"] == "complete"
    assert captured["report_type"] == "analysis"
    assert captured["scenario_pack"]["profile"] == "research_report"


def test_finalize_google_delivery_uses_bound_runtime_outbox(monkeypatch):
    queued: dict[str, object] = {}

    class _FakeOutbox:
        def enqueue(self, **kwargs):
            queued.update(kwargs)

    runtime = type("_Runtime", (), {"outbox": _FakeOutbox()})()
    monkeypatch.setattr("chatgptrest.advisor.report_graph.GoogleWorkspace", object())

    with graph_mod.bind_runtime_services(runtime):
        result = finalize(
            {
                "internal_draft_text": "Queued report",
                "review_pass": True,
                "redact_pass": True,
                "_delivery_target": "google_drive",
                "trace_id": "trace-google-runtime",
                "purpose": "Launch readiness",
            }
        )

    assert result["final_status"] == "complete"
    assert queued["effect_type"] == "workspace_action"


def test_execute_report_executes_workspace_effects_and_appends_doc_url(monkeypatch):
    runtime = type(
        "_Runtime",
        (),
        {
            "llm_connector": object(),
            "kb_hub": object(),
            "policy_engine": object(),
            "outbox": object(),
            "memory": None,
            "evomap_observer": None,
            "kb_registry": None,
            "event_bus": None,
            "model_router": None,
            "writeback_service": None,
        },
    )()

    class _DummyReportApp:
        def compile(self):
            return self

        def invoke(self, payload):
            return {
                "final_status": "complete",
                "final_text": "report body",
                "draft_sections": ["Summary"],
                "review_notes": [],
                "review_pass": True,
                "evidence_count": 1,
            }

    monkeypatch.setattr("chatgptrest.advisor.report_graph.build_report_graph", lambda: _DummyReportApp())
    monkeypatch.setattr(graph_mod, "_kb_writeback_and_record", lambda **_kwargs: {"success": True})
    monkeypatch.setattr(
        graph_mod,
        "execute_workspace_effects_for_trace",
        lambda *_args, **_kwargs: [
            {
                "success": True,
                "workspace_result_full": {
                    "ok": True,
                    "action": "deliver_report_to_docs",
                    "status": "completed",
                    "data": {"url": "https://docs.test/doc-1"},
                },
            }
        ],
    )

    with graph_mod.bind_runtime_services(runtime):
        result = graph_mod.execute_report(
            {
                "user_message": "请输出周报并发到 Google Drive",
                "trace_id": "trace-report-ws-1",
                "report_type": "analysis",
                "_delivery_target": "google_drive",
            }
        )

    assert result["route_result"]["workspace_delivery"][0]["success"] is True
    assert "Google Docs 已交付" in result["route_result"]["final_text"]
