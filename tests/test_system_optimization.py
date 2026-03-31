"""Tests for the system optimization features (2026-03-16).

Tests cover:
1. Skill registry and pre-flight check
2. Deliverable aggregator
3. Preset recommender
4. Standard entry adapter
"""

from __future__ import annotations

import json

import pytest

# ============================================================================
# 1. Skill Registry Tests
# ============================================================================


class TestSkillRegistry:
    """Tests for chatgptrest.advisor.skill_registry."""

    def test_classify_task_type_market_research(self):
        from chatgptrest.advisor.skill_registry import classify_task_type

        card = {"title": "两轮电动车市场调研", "description": "研究中国市场品牌"}
        assert classify_task_type(card) == "market_research"

    def test_classify_task_type_code_review(self):
        from chatgptrest.advisor.skill_registry import classify_task_type

        card = {"title": "Code Review for dispatch module", "description": "审查代码质量"}
        assert classify_task_type(card) == "code_review"

    def test_classify_task_type_investment(self):
        from chatgptrest.advisor.skill_registry import classify_task_type

        card = {"title": "股票投资机会分析", "description": "寻找投资标的"}
        assert classify_task_type(card) == "investment_research"

    def test_classify_task_type_general(self):
        from chatgptrest.advisor.skill_registry import classify_task_type

        card = {"title": "Hello", "description": "Simple question"}
        assert classify_task_type(card) == "general"

    def test_check_skill_readiness_pass(self):
        from chatgptrest.advisor.skill_registry import check_skill_readiness

        card = {"title": "System maintenance", "description": "ops check"}
        result = check_skill_readiness("main", card)
        assert result.passed is True
        assert result.missing_skills == []

    def test_check_skill_readiness_fail_with_suggestion(self):
        from chatgptrest.advisor.skill_registry import check_skill_readiness

        # main agent doesn't have market_research skill
        card = {"title": "两轮电动车市场调研", "description": "研究中国品牌"}
        result = check_skill_readiness("main", card)
        assert result.passed is False
        assert "market_research" in result.missing_skills
        assert result.suggested_agent == "finbot"
        assert "research_core" in result.recommended_bundles
        assert result.status == "unmet_capabilities"

    def test_check_skill_readiness_unknown_agent(self):
        from chatgptrest.advisor.skill_registry import check_skill_readiness

        card = {"title": "Some task"}
        result = check_skill_readiness("nonexistent_agent", card)
        assert result.passed is False
        assert result.status == "unknown_agent"
        assert "not registered" in result.message

    def test_find_best_agent(self):
        from chatgptrest.advisor.skill_registry import find_best_agent

        assert find_best_agent("market_research") == "finbot"
        assert find_best_agent("investment_research") == "finbot"
        assert find_best_agent("code_development") == "main"

    def test_agent_skill_profile(self):
        from chatgptrest.advisor.skill_registry import AgentSkillProfile

        p = AgentSkillProfile(
            agent_id="test", skills={"code_review", "document_writing"}
        )
        assert p.has_skill("code_review")
        assert not p.has_skill("market_research")
        assert p.has_all_skills(["code_review", "document_writing"])
        assert p.missing_skills(["code_review", "market_research"]) == [
            "market_research"
        ]


# ============================================================================
# 2. Preset Recommender Tests
# ============================================================================


class TestPresetRecommender:
    """Tests for chatgptrest.advisor.preset_recommender."""

    def test_recommend_simple_question(self):
        from chatgptrest.advisor.preset_recommender import recommend_preset

        r = recommend_preset("什么是REST API？", prefer_local=True)
        assert r.preset == "local_llm"
        assert r.provider == "local"

    def test_recommend_simple_without_local(self):
        from chatgptrest.advisor.preset_recommender import recommend_preset

        r = recommend_preset("什么是REST API？", prefer_local=False)
        assert r.preset == "auto"

    def test_recommend_complex_analysis(self):
        from chatgptrest.advisor.preset_recommender import recommend_preset

        q = "请系统性地分析评审我们的架构设计方案，对比不同策略的权衡取舍，评估风险"
        r = recommend_preset(q)
        assert r.preset == "pro_extended"
        assert r.provider == "chatgpt"

    def test_recommend_research(self):
        from chatgptrest.advisor.preset_recommender import recommend_preset

        q = "调研中国两轮电动车市场趋势和竞品分析"
        r = recommend_preset(q)
        assert r.preset == "deep_research_chatgpt"

    def test_recommend_research_report_from_scenario_pack(self):
        from chatgptrest.advisor.preset_recommender import recommend_preset

        r = recommend_preset(
            "请输出一份行星滚柱丝杠行业研究报告",
            task_intake={"scenario": "report"},
            scenario_pack={"profile": "research_report", "route_hint": "report"},
        )
        assert r.preset == "pro_extended"

    def test_recommend_topic_research_from_scenario_pack(self):
        from chatgptrest.advisor.preset_recommender import recommend_preset

        r = recommend_preset(
            "调研行星滚柱丝杠产业链关键玩家和国产替代进展",
            task_intake={"scenario": "research"},
            scenario_pack={"profile": "topic_research", "route_hint": "deep_research"},
        )
        assert r.preset == "deep_research_chatgpt"

    def test_recommend_moderate(self):
        from chatgptrest.advisor.preset_recommender import recommend_preset

        q = "帮我分析这段代码的性能问题并给出优化建议" + " 详细说明" * 50
        r = recommend_preset(q)
        assert r.preset in ("thinking_heavy", "pro_extended")

    def test_validate_overkill(self):
        from chatgptrest.advisor.preset_recommender import validate_preset_choice

        r = validate_preset_choice("什么是REST API？", "pro_extended")
        assert not r["ok"]
        assert any("expensive" in w or "更expensive" in w.lower() for w in r["warnings"])

    def test_validate_good_match(self):
        from chatgptrest.advisor.preset_recommender import validate_preset_choice

        q = "请系统性地分析评审架构方案，全面对比策略权衡"
        r = validate_preset_choice(q, "pro_extended")
        assert r["ok"]

    def test_to_dict(self):
        from chatgptrest.advisor.preset_recommender import recommend_preset

        r = recommend_preset("Hello")
        d = r.to_dict()
        assert "preset" in d
        assert "estimated_turnaround_human" in d


# ============================================================================
# 3. Standard Entry Adapter Tests
# ============================================================================


class TestStandardEntry:
    """Tests for chatgptrest.advisor.standard_entry."""

    def test_normalize_request(self):
        from chatgptrest.advisor.standard_entry import normalize_request

        req = normalize_request(
            "Test question",
            source="codex",
            target_agent="main",
        )
        assert req.source == "codex"
        assert req.target_agent == "main"
        assert req.trace_id  # auto-generated
        assert req.task_intake is not None
        assert req.task_intake.source == "cli"
        assert req.task_intake.objective == "Test question"

    def test_normalize_request_rejects_invalid_task_intake_version(self):
        from chatgptrest.advisor.standard_entry import normalize_request
        from chatgptrest.advisor.task_intake import TaskIntakeValidationError

        with pytest.raises(TaskIntakeValidationError, match="task intake spec_version"):
            normalize_request(
                "Test question",
                source="codex",
                metadata={"task_intake": {"spec_version": "task-intake-v1"}},
            )

    def test_standard_pipeline_simple(self):
        from chatgptrest.advisor.standard_entry import process_codex_request

        result = process_codex_request("解释一下Python的装饰器是什么")
        assert result["ready_to_dispatch"]
        assert "preset_recommendation" in result["steps"]
        assert "skill_check" in result["steps"]
        assert "quality_gate" in result["steps"]

    def test_standard_pipeline_reroutes_agent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))
        import chatgptrest.kernel.market_gate as market_gate

        market_gate.get_capability_gap_recorder.cache_clear()
        from chatgptrest.advisor.standard_entry import process_codex_request

        # Market research sent to 'main' should be rerouted to 'research'
        result = process_codex_request(
            "调研中国两轮电动车市场品牌",
            target_agent="main",
        )
        # The pipeline should detect skill gap and suggest a reroute
        assert result["steps"]["skill_check"]["passed"] is False
        assert result.get("suggested_agent") == "finbot"
        assert "unmet_capabilities" in result["steps"]["skill_check"]
        assert "research_core" in result["recommended_bundles"]
        assert result["fallback_plan"]
        assert result["capability_gap_ids"]

    def test_quality_gate_short_question(self):
        from chatgptrest.advisor.standard_entry import process_codex_request

        result = process_codex_request("hi")
        assert not result["ready_to_dispatch"]
        assert result["steps"]["quality_gate"]["passed"] is False

    def test_process_mcp_request(self):
        from chatgptrest.advisor.standard_entry import process_mcp_request

        result = process_mcp_request("解释一下Python的GIL机制")
        assert result["source"] == "mcp"
        assert result["task_intake_summary"]["source"] == "mcp"
        assert result["ready_to_dispatch"]

    def test_standard_pipeline_emits_selected_skill_signal(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENMIND_EVOMAP_DB", str(tmp_path / "evomap.db"))
        import chatgptrest.kernel.market_gate as market_gate

        market_gate.get_skill_platform_observer.cache_clear()
        from chatgptrest.advisor.standard_entry import process_codex_request

        result = process_codex_request("解释一下Python的装饰器是什么")
        signal_types = [
            signal.signal_type for signal in market_gate.get_skill_platform_observer().by_trace(result["trace_id"])
        ]

        assert result["ready_to_dispatch"] is True
        assert "skill.selected" in signal_types

    def test_pipeline_output_has_dispatch_params(self):
        from chatgptrest.advisor.standard_entry import process_codex_request

        result = process_codex_request("Write a Python function to sort a list")
        assert "dispatch_params" in result
        params = result["dispatch_params"]
        assert params["source"] == "codex"
        assert params["question"]
        assert params["trace_id"]
        assert params["task_intake"]["source"] == "cli"

    def test_standard_pipeline_injects_research_scenario_pack(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))
        import chatgptrest.kernel.market_gate as market_gate

        market_gate.get_capability_gap_recorder.cache_clear()
        from chatgptrest.advisor.standard_entry import process_codex_request

        result = process_codex_request("调研行星滚柱丝杠产业链关键玩家和国产替代进展")

        assert result["steps"]["skill_check"]["passed"] is False
        assert result.get("suggested_agent") == "finbot"
        assert "research_core" in result["recommended_bundles"]
        assert result["fallback_plan"]
        assert result["capability_gap_ids"]
        assert result["scenario_pack"]["profile"] == "topic_research"
        assert result["dispatch_params"]["scenario_pack"]["route_hint"] == "deep_research"

    def test_standard_pipeline_surfaces_market_candidates_for_unmet_capability(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENMIND_SKILL_PLATFORM_DB", str(tmp_path / "skill_platform.db"))

        import chatgptrest.kernel.market_gate as market_gate

        market_gate.get_capability_gap_recorder.cache_clear()
        recorder = market_gate.get_capability_gap_recorder()
        recorder.register_market_candidate(
            skill_id="community-market-scanner",
            source_market="clawhub",
            source_uri="https://example.invalid/community-market-scanner",
            capability_ids=["market_research"],
            summary="candidate for market research gaps",
        )
        from chatgptrest.advisor.standard_entry import process_codex_request

        result = process_codex_request("调研中国两轮电动车市场品牌", target_agent="main")

        assert result["skill_gap"] is True
        assert result["market_candidates"]
        assert result["market_candidates"][0]["skill_id"] == "community-market-scanner"
        assert result["fallback_plan"][-1]["action"] == "review_market_candidates"


# ============================================================================
# 4. Deliverable Aggregator Tests (structural, no DB)
# ============================================================================


class TestDeliverableAggregator:
    """Tests for chatgptrest.governance.deliverable_aggregator."""

    def test_aggregate_no_jobs(self, tmp_path, monkeypatch):
        from chatgptrest.governance.deliverable_aggregator import aggregate_answers

        monkeypatch.setenv("CHATGPTREST_ARTIFACTS_PATH", str(tmp_path))
        result = aggregate_answers([])
        assert result["job_count"] == 0
        assert result["report_path"] is None

    def test_aggregate_real_answers(self, tmp_path, monkeypatch):
        from chatgptrest.governance.deliverable_aggregator import aggregate_answers

        monkeypatch.setenv("CHATGPTREST_ARTIFACTS_PATH", str(tmp_path))

        # Create fake job answers.
        for jid, content in [
            ("job1111111111111111111111111111111", "# Part 1\n\nData about brand A"),
            ("job2222222222222222222222222222222", "# Part 2\n\nData about brand B"),
        ]:
            job_dir = tmp_path / "jobs" / jid
            job_dir.mkdir(parents=True)
            (job_dir / "answer.md").write_text(content)

        result = aggregate_answers(
            ["job1111111111111111111111111111111", "job2222222222222222222222222222222"],
            title="Test Report",
        )
        assert result["job_count"] == 2
        assert result["total_chars"] > 0
        assert result["report_path"] is not None

        # Verify report content.
        from pathlib import Path

        report = Path(result["report_path"]).read_text()
        assert "Test Report" in report
        assert "Part 1" in report
        assert "Part 2" in report
        assert "Table of Contents" in report

    def test_aggregate_missing_answers(self, tmp_path, monkeypatch):
        from chatgptrest.governance.deliverable_aggregator import aggregate_answers

        monkeypatch.setenv("CHATGPTREST_ARTIFACTS_PATH", str(tmp_path))
        result = aggregate_answers(["nonexistent_job_id"])
        assert result["job_count"] == 0

    def test_aggregate_prefers_authoritative_answer_path_from_result(self, tmp_path, monkeypatch):
        from chatgptrest.governance.deliverable_aggregator import aggregate_answers

        monkeypatch.setenv("CHATGPTREST_ARTIFACTS_PATH", str(tmp_path))

        job_id = "job3333333333333333333333333333333"
        job_dir = tmp_path / "jobs" / job_id
        job_dir.mkdir(parents=True)
        (job_dir / "answer.txt").write_text("authoritative text answer", encoding="utf-8")
        (job_dir / "result.json").write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": "completed",
                    "path": f"jobs/{job_id}/answer.txt",
                    "completion_contract": {
                        "answer_state": "final",
                        "authoritative_answer_path": f"jobs/{job_id}/answer.txt",
                        "answer_provenance": {"contract_class": "research"},
                    },
                    "canonical_answer": {
                        "record_version": "v1",
                        "ready": True,
                        "answer_state": "final",
                        "authoritative_answer_path": f"jobs/{job_id}/answer.txt",
                        "answer_provenance": {"contract_class": "research"},
                    },
                }
            ),
            encoding="utf-8",
        )

        result = aggregate_answers([job_id], title="Authoritative Path Report")
        assert result["job_count"] == 1
        assert result["jobs_included"][0]["source"].endswith("answer.txt")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
