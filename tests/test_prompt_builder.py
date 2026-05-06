"""Tests for server-side prompt builder."""

import pytest

from chatgptrest.advisor.prompt_builder import (
    PromptBuildResult,
    build_prompt_from_contract,
    build_prompt_from_strategy,
    enrich_message_with_contract,
)
from chatgptrest.advisor.ask_contract import (
    AskContract,
    TaskTemplate,
    RiskClass,
)
from chatgptrest.advisor.ask_strategist import build_strategy_plan


class TestPromptBuilder:
    """Test prompt builder."""

    def test_build_prompt_research(self):
        """Test building research prompt."""
        contract = AskContract(
            objective="What is AI?",
            decision_to_support="Understanding AI",
            audience="Students",
            output_shape="Explanation",
            task_template=TaskTemplate.RESEARCH.value,
        )

        result = build_prompt_from_contract(contract)

        assert isinstance(result, PromptBuildResult)
        assert result.system_prompt
        assert result.user_prompt
        assert "AI" in result.user_prompt
        assert result.template_used == TaskTemplate.RESEARCH.value

    def test_build_prompt_code_review(self):
        """Test building code review prompt."""
        contract = AskContract(
            objective="Review this code",
            decision_to_support="Code quality decision",
            audience="Developers",
            output_shape="Review report",
            task_template=TaskTemplate.CODE_REVIEW.value,
        )

        result = build_prompt_from_contract(contract)

        assert result.template_used == TaskTemplate.CODE_REVIEW.value
        assert "review" in result.user_prompt.lower()

    def test_build_prompt_report(self):
        """Test building report prompt."""
        contract = AskContract(
            objective="Generate quarterly report",
            decision_to_support="Business decision",
            audience="Executives",
            output_shape="PDF report",
            task_template=TaskTemplate.REPORT_GENERATION.value,
        )

        result = build_prompt_from_contract(contract)

        assert result.template_used == TaskTemplate.REPORT_GENERATION.value

    def test_build_prompt_high_risk(self):
        """Test building prompt for high-risk requests."""
        contract = AskContract(
            objective="Critical decision",
            decision_to_support="Production decision",
            audience="CTO",
            output_shape="Recommendation",
            risk_class=RiskClass.HIGH.value,
        )

        result = build_prompt_from_contract(contract)

        assert "high-stakes" in result.system_prompt.lower() or \
               "high" in result.system_prompt.lower()

    def test_build_prompt_with_constraints(self):
        """Test building prompt with constraints."""
        contract = AskContract(
            objective="Research topic",
            constraints="Must complete within 2 hours",
            output_shape="Summary",
        )

        result = build_prompt_from_contract(contract)

        assert "2 hours" in result.user_prompt

    def test_build_prompt_default_template(self):
        """Test building prompt with default/general template."""
        contract = AskContract(
            objective="Simple question",
            task_template=TaskTemplate.GENERAL.value,
        )

        result = build_prompt_from_contract(contract)

        assert result.template_used == TaskTemplate.GENERAL.value

    def test_model_hints(self):
        """Test model-specific hints."""
        contract = AskContract(objective="Test")

        result_chatgpt = build_prompt_from_contract(contract, model_provider="chatgpt")
        result_gemini = build_prompt_from_contract(contract, model_provider="gemini")

        assert result_chatgpt.model_hints
        assert result_gemini.model_hints

    def test_build_prompt_from_strategy_includes_compiler_metadata(self):
        contract = AskContract(
            objective="Plan premium ingress rollout",
            decision_to_support="Implementation sequencing",
            audience="Platform team",
            output_shape="markdown_plan",
            task_template=TaskTemplate.IMPLEMENTATION_PLANNING.value,
            risk_class=RiskClass.HIGH.value,
            contract_completeness=0.9,
        )
        strategy = build_strategy_plan(
            message=contract.objective,
            contract=contract,
            goal_hint="report",
            context={"files": ["spec.md"]},
        )

        result = build_prompt_from_strategy(strategy, contract, model_provider="chatgpt")

        assert result.output_contract["format"] == "markdown"
        assert result.evidence_requirements["ground_in_attached_files"] is True
        assert result.review_rubric
        assert "Output Contract" in result.user_prompt
        assert result.model_hints["route_hint"] == "funnel"

    def test_build_prompt_from_strategy_uses_scenario_pack_template_override(self):
        contract = AskContract(
            objective="整理本周项目例会纪要",
            decision_to_support="对齐行动项",
            audience="项目组",
            output_shape="meeting_summary",
            task_template=TaskTemplate.IMPLEMENTATION_PLANNING.value,
            risk_class=RiskClass.MEDIUM.value,
            contract_completeness=0.9,
        )
        strategy = build_strategy_plan(
            message=contract.objective,
            contract=contract,
            goal_hint="planning",
            context={
                "scenario_pack": {
                    "scenario": "planning",
                    "profile": "meeting_summary",
                    "route_hint": "report",
                    "prompt_template_override": TaskTemplate.REPORT_GENERATION.value,
                    "watch_policy": {"checkpoint": "delivery_only"},
                    "acceptance": {"required_sections": ["meeting_context", "key_points", "action_items"]},
                    "review_rubric": ["captures meeting context and participants"],
                }
            },
        )

        result = build_prompt_from_strategy(strategy, contract, model_provider="chatgpt")

        assert result.template_used == TaskTemplate.REPORT_GENERATION.value
        assert "Scenario Pack" in result.user_prompt
        assert result.provider_hints["planning_profile"] == "meeting_summary"

    def test_build_prompt_from_strategy_explicitly_prioritizes_authority_anchor(self):
        contract = AskContract(
            objective="收紧项目口径",
            available_inputs=(
                "Authority anchor (highest priority; prefer this over retrieved context when they conflict):\n"
                "- Project ref: shortmobility\n"
                "- Frozen facts: 金彭量级不能冻结为已确认事实"
            ),
            task_template=TaskTemplate.REPORT_GENERATION.value,
        )
        strategy = build_strategy_plan(
            message=contract.objective,
            contract=contract,
            goal_hint="planning",
            context={},
        )

        result = build_prompt_from_strategy(strategy, contract, model_provider="chatgpt")

        assert "Apply the authority anchor first." in result.user_prompt
        assert result.user_prompt.index("Apply the authority anchor first.") < result.user_prompt.index("Authority anchor")

    def test_build_prompt_from_strategy_renders_authority_dict_inputs(self):
        contract = AskContract(
            objective="收紧项目口径",
            available_inputs={
                "project_ref": "shortmobility",
                "owner": "yuan",
                "last_reviewed_at": "2026-04-08",
                "current_phase_framing": "0497 仍处于战时管理语境，先收紧口径。",
                "frozen_facts": ["金彭量级不能冻结为已确认事实"],
                "style_rules": ["去掉不是而是结构"],
                "authority_docs": ["/tmp/0497.md"],
                "project_context": "保持战时管理语境，不放大未冻结事实。",
                "repo_hint": "ChatgptREST",
            },
            task_template=TaskTemplate.REPORT_GENERATION.value,
        )
        strategy = build_strategy_plan(
            message=contract.objective,
            contract=contract,
            goal_hint="planning",
            context={},
        )

        result = build_prompt_from_strategy(strategy, contract, model_provider="chatgpt")

        assert "Apply the authority anchor first." in result.user_prompt
        assert "- Owner: yuan" in result.user_prompt
        assert "- Authority docs: 0497 [local artifact]" in result.user_prompt
        assert "/tmp/0497.md" not in result.user_prompt
        assert "Additional inputs:" in result.user_prompt
        assert "\"repo_hint\": \"ChatgptREST\"" in result.user_prompt

    def test_build_prompt_from_strategy_renders_wakeup_packet_without_duplicate_l0(self):
        contract = AskContract(
            objective="继续推进 beta rollout",
            available_inputs={
                "project_ref": "prj-beta",
                "frozen_facts": ["Pilot stays in controlled rollout."],
                "wake_up_packet": {
                    "schema_version": "openmind-wakeup-packet-v1",
                    "packet_id": "pkt-1",
                    "project_id": "prj-beta",
                    "query": "What should the beta rollout team do next?",
                    "source_precedence": "authority anchor > project memory > EvoMap knowledge > runtime heuristics",
                    "degraded": False,
                    "degraded_sources": [],
                    "layers": [
                        {
                            "layer_id": "L0",
                            "title": "Authority anchor",
                            "summary": "Pilot stays in controlled rollout.",
                            "provenance": [{"type": "authority_anchor", "path": "/tmp/prj-beta/_project_context.md"}],
                        },
                        {
                            "layer_id": "L3",
                            "title": "Runtime handoff / recommended next step",
                            "summary": "Recommended next step: confirm finance sign-off",
                            "provenance": [],
                        },
                    ],
                },
            },
            task_template=TaskTemplate.REPORT_GENERATION.value,
        )
        strategy = build_strategy_plan(
            message=contract.objective,
            contract=contract,
            goal_hint="planning",
            context={},
        )

        result = build_prompt_from_strategy(strategy, contract, model_provider="chatgpt")

        assert "Wake-up packet" in result.user_prompt
        assert "L3 Runtime handoff / recommended next step" in result.user_prompt
        assert "L0 Authority anchor" not in result.user_prompt

    def test_build_prompt_from_strategy_sanitizes_wakeup_packet_local_markdown_links(self):
        contract = AskContract(
            objective="梳理绩效总结材料",
            available_inputs={
                "wake_up_packet": {
                    "schema_version": "openmind-wakeup-packet-v1",
                    "packet_id": "pkt-2",
                    "query": "请基于现有材料梳理绩效总结",
                    "source_precedence": "authority anchor > project memory > EvoMap knowledge > runtime heuristics",
                    "degraded": False,
                    "degraded_sources": [],
                    "layers": [
                        {
                            "layer_id": "L2",
                            "title": "Retrieved project knowledge / entity context",
                            "summary": "Knowledge Evidence: [q1_perf_review](/vol1/1000/projects/planning/q1_perf_review.md)",
                            "provenance": [
                                {"type": "kb_hit", "path": "/vol1/1000/projects/planning/q1_perf_review.md"}
                            ],
                        }
                    ],
                }
            },
            task_template=TaskTemplate.IMPLEMENTATION_PLANNING.value,
        )
        strategy = build_strategy_plan(
            message=contract.objective,
            contract=contract,
            goal_hint="planning",
            context={},
        )

        result = build_prompt_from_strategy(strategy, contract, model_provider="chatgpt")

        assert "q1_perf_review [local artifact]" in result.user_prompt
        assert "/vol1/1000/projects/planning/q1_perf_review.md" not in result.user_prompt

    def test_build_prompt_from_strategy_renders_local_material_preflight_summary(self):
        contract = AskContract(
            objective="梳理Q1绩效总结",
            available_inputs={
                "files": ["个人绩效/2026Q1/素材/2025年度绩效考核表-袁海州1.xlsx"],
                "local_material_preflight_summary": (
                    "已检查 1 个本地材料路径。\n"
                    "- 2025年度绩效考核表-袁海州1.xlsx: sheets=绩效考核表; "
                    "preview=绩效考核表 表头: 2025年度绩效考核表（袁海州）"
                ),
            },
            task_template=TaskTemplate.REPORT_GENERATION.value,
        )
        strategy = build_strategy_plan(
            message=contract.objective,
            contract=contract,
            goal_hint="planning",
            context={},
        )

        result = build_prompt_from_strategy(strategy, contract, model_provider="chatgpt")

        assert "Files:" in result.user_prompt
        assert "2025年度绩效考核表-袁海州1 [local artifact]" in result.user_prompt
        assert "Host local material preflight:" in result.user_prompt
        assert "已检查 1 个本地材料路径" in result.user_prompt


class TestEnrichMessage:
    """Test message enrichment with contract."""

    def test_enrich_message(self):
        """Test enriching message with contract context."""
        contract = AskContract(
            objective="What is Python?",
            decision_to_support="Learning decision",
            audience="Beginners",
        )

        # Note: enrich_message_with_contract takes message as first arg
        enriched = enrich_message_with_contract(
            message="What is Python?",
            contract=contract,
            model_provider="chatgpt",
        )

        assert enriched
        assert "What is Python?" in enriched
