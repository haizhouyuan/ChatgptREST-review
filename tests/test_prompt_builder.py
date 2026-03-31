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
