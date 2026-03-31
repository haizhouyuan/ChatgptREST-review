"""Server-side Prompt Builder — Contract-driven Prompt Assembly.

This module implements server-side prompt assembly driven by task template + contract.

The prompt builder:
- Builds prompts based on task template
- Adapts prompts to specific model/providers
- Injects role/perspective, output rubric, uncertainty handling,
  evidence summary, and formatting contract
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from chatgptrest.advisor.ask_contract import (
    AskContract,
    TaskTemplate,
)
from chatgptrest.advisor.ask_strategist import AskStrategyPlan, build_strategy_plan

logger = logging.getLogger(__name__)


# Task template prompt templates
_TASK_TEMPLATE_PROMPTS: dict[str, dict[str, str]] = {
    TaskTemplate.RESEARCH.value: {
        "system": """You are a research analyst. Your task is to conduct thorough research on the given topic.
Focus on:
- Finding reliable sources and evidence
- Synthesizing information from multiple perspectives
- Identifying knowledge gaps and uncertainties
- Providing actionable insights based on findings""",
        "user_template": """## Research Objective
{objective}

## Decision to Support
{decision_to_support}

## Audience
{audience}

## Constraints
{constraints}

## Available Inputs
{available_inputs}

## Missing Information
{missing_inputs}

## Output Requirements
{output_shape}

Please conduct research and provide a comprehensive answer.""",
    },
    TaskTemplate.DECISION_SUPPORT.value: {
        "system": """You are a decision support analyst. Your task is to help stakeholders make informed decisions.
Focus on:
- Presenting options with pros and cons
- Assessing risks and trade-offs
- Considering multiple perspectives
- Providing clear recommendations with rationale""",
        "user_template": """## Decision Objective
{objective}

## What Decision This Supports
{decision_to_support}

## Audience
{audience}

## Constraints
{constraints}

## Available Inputs
{available_inputs}

## Missing Information
{missing_inputs}

## Output Requirements
{output_shape}

Please analyze the options and provide a recommendation.""",
    },
    TaskTemplate.CODE_REVIEW.value: {
        "system": """You are a code review expert. Your task is to review code and provide constructive feedback.
Focus on:
- Identifying bugs and security issues
- Suggesting improvements for readability and performance
- Evaluating code style and best practices
- Providing actionable feedback""",
        "user_template": """## Review Objective
{objective}

## Decision to Support
{decision_to_support}

## Audience
{audience}

## Constraints
{constraints}

## Available Inputs
{available_inputs}

## Missing Information
{missing_inputs}

## Output Requirements
{output_shape}

Please review the code and provide feedback.""",
    },
    TaskTemplate.IMPLEMENTATION_PLANNING.value: {
        "system": """You are a technical planner. Your task is to create implementation plans.
Focus on:
- Breaking down tasks into manageable steps
- Identifying dependencies and risks
- Estimating effort and timeline
- Defining acceptance criteria""",
        "user_template": """## Implementation Objective
{objective}

## Decision to Support
{decision_to_support}

## Audience
{audience}

## Constraints
{constraints}

## Available Inputs
{available_inputs}

## Missing Information
{missing_inputs}

## Output Requirements
{output_shape}

Please create an implementation plan.""",
    },
    TaskTemplate.REPORT_GENERATION.value: {
        "system": """You are a report writer. Your task is to generate comprehensive reports.
Focus on:
- Organizing information clearly
- Using appropriate structure and formatting
- Including relevant data and analysis
- Providing actionable conclusions""",
        "user_template": """## Report Objective
{objective}

## Decision to Support
{decision_to_support}

## Audience
{audience}

## Constraints
{constraints}

## Available Inputs
{available_inputs}

## Missing Information
{missing_inputs}

## Output Requirements
{output_shape}

Please generate a comprehensive report.""",
    },
    TaskTemplate.IMAGE_GENERATION.value: {
        "system": """You are an image generation prompt engineer. Your task is to create effective prompts for image generation.
Focus on:
- Describing visual elements clearly
- Specifying style, composition, and mood
- Including relevant details for the desired output""",
        "user_template": """## Image Objective
{objective}

## Decision to Support
{decision_to_support}

## Audience
{audience}

## Constraints
{constraints}

## Available Inputs
{available_inputs}

## Missing Information
{missing_inputs}

## Output Requirements
{output_shape}

Please provide an image generation prompt.""",
    },
    TaskTemplate.DUAL_MODEL_CRITIQUE.value: {
        "system": """You are a dual-model critique analyst. Your task is to compare and evaluate responses from multiple models.
Focus on:
- Identifying strengths and weaknesses in each response
- Synthesizing insights from multiple perspectives
- Providing balanced evaluation
- Suggesting improvements""",
        "user_template": """## Critique Objective
{objective}

## Decision to Support
{decision_to_support}

## Audience
{audience}

## Constraints
{constraints}

## Available Inputs
{available_inputs}

## Missing Information
{missing_inputs}

## Output Requirements
{output_shape}

Please provide a dual-model critique.""",
    },
    TaskTemplate.REPAIR_DIAGNOSIS.value: {
        "system": """You are a diagnostic analyst. Your task is to diagnose and repair issues.
Focus on:
- Identifying root causes
- Analyzing symptoms and patterns
- Proposing solutions
- Verifying fixes""",
        "user_template": """## Diagnosis Objective
{objective}

## Decision to Support
{decision_to_support}

## Audience
{audience}

## Constraints
{constraints}

## Available Inputs
{available_inputs}

## Missing Information
{missing_inputs}

## Output Requirements
{output_shape}

Please diagnose the issue and provide a repair plan.""",
    },
    TaskTemplate.STAKEHOLDER_COMMUNICATION.value: {
        "system": """You are a communications specialist. Your task is to draft communications for stakeholders.
Focus on:
- Adapting tone to the audience
- Being clear and concise
- Addressing stakeholder concerns
- Maintaining professionalism""",
        "user_template": """## Communication Objective
{objective}

## Decision to Support
{decision_to_support}

## Audience
{audience}

## Constraints
{constraints}

## Available Inputs
{available_inputs}

## Missing Information
{missing_inputs}

## Output Requirements
{output_shape}

Please draft the communication.""",
    },
    TaskTemplate.GENERAL.value: {
        "system": """You are a helpful AI assistant. Your task is to provide clear and accurate answers.
Focus on:
- Understanding the user's intent
- Providing accurate and relevant information
- Being clear and concise
- Acknowledging uncertainty when appropriate""",
        "user_template": """## Question
{objective}

## Decision to Support
{decision_to_support}

## Audience
{audience}

## Constraints
{constraints}

## Available Inputs
{available_inputs}

## Missing Information
{missing_inputs}

## Output Requirements
{output_shape}

Please provide an answer.""",
    },
}


@dataclass
class PromptBuildResult:
    """Result of prompt building."""
    system_prompt: str
    user_prompt: str
    template_used: str
    model_hints: dict[str, Any] = field(default_factory=dict)
    output_contract: dict[str, Any] = field(default_factory=dict)
    uncertainty_policy: dict[str, Any] = field(default_factory=dict)
    evidence_requirements: dict[str, Any] = field(default_factory=dict)
    review_rubric: list[str] = field(default_factory=list)
    provider_hints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "template_used": self.template_used,
            "model_hints": dict(self.model_hints or {}),
            "output_contract": dict(self.output_contract or {}),
            "uncertainty_policy": dict(self.uncertainty_policy or {}),
            "evidence_requirements": dict(self.evidence_requirements or {}),
            "review_rubric": list(self.review_rubric or []),
            "provider_hints": dict(self.provider_hints or {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptBuildResult":
        return cls(
            system_prompt=str(data.get("system_prompt") or ""),
            user_prompt=str(data.get("user_prompt") or ""),
            template_used=str(data.get("template_used") or TaskTemplate.GENERAL.value),
            model_hints=dict(data.get("model_hints") or {}),
            output_contract=dict(data.get("output_contract") or {}),
            uncertainty_policy=dict(data.get("uncertainty_policy") or {}),
            evidence_requirements=dict(data.get("evidence_requirements") or {}),
            review_rubric=list(data.get("review_rubric") or []),
            provider_hints=dict(data.get("provider_hints") or {}),
        )


def build_prompt_from_contract(
    contract: AskContract,
    model_provider: str = "chatgpt",
    custom_context: Optional[dict[str, Any]] = None,
) -> PromptBuildResult:
    """
    Build a prompt from an ask contract.

    Args:
        contract: The ask contract
        model_provider: The model provider (chatgpt, gemini, etc.)
        custom_context: Additional context for prompt building

    Returns:
        PromptBuildResult with assembled prompts
    """
    strategy_plan = build_strategy_plan(
        message=contract.objective or "",
        contract=contract,
        goal_hint=str((custom_context or {}).get("goal_hint") or ""),
        context=custom_context,
    )
    return build_prompt_from_strategy(
        strategy_plan=strategy_plan,
        contract=contract,
        model_provider=model_provider,
        custom_context=custom_context,
    )


def build_prompt_from_strategy(
    strategy_plan: AskStrategyPlan,
    contract: AskContract,
    model_provider: str = "chatgpt",
    custom_context: Optional[dict[str, Any]] = None,
) -> PromptBuildResult:
    """Build a compiled prompt from strategist output plus ask contract."""
    template = (
        str(strategy_plan.provider_hints.get("prompt_template_override") or "").strip()
        or contract.task_template
        or TaskTemplate.GENERAL.value
    )
    template_prompts = _TASK_TEMPLATE_PROMPTS.get(
        template,
        _TASK_TEMPLATE_PROMPTS[TaskTemplate.GENERAL.value],
    )
    scenario_pack = dict(strategy_plan.provider_hints.get("scenario_pack") or {})

    user_prompt = template_prompts["user_template"].format(
        objective=contract.objective or "Not specified",
        decision_to_support=contract.decision_to_support or "Not specified",
        audience=contract.audience or "General audience",
        constraints=contract.constraints or "No specific constraints",
        available_inputs=contract.available_inputs or "None provided",
        missing_inputs=contract.missing_inputs or "None identified",
        output_shape=contract.output_shape or "Text answer",
    )

    if contract.risk_class:
        risk_note = f"\n\n## Risk Level: {contract.risk_class.upper()}"
        if contract.risk_class == "high":
            risk_note += "\nThis is a high-stakes request. Please be thorough and consider all implications."
        user_prompt += risk_note

    if contract.opportunity_cost:
        user_prompt += f"\n\n## Opportunity Cost Consideration\n{contract.opportunity_cost}"

    system_prompt = _adapt_system_prompt(
        template_prompts["system"],
        model_provider,
        contract.risk_class,
    )
    system_prompt += f"\n\nStrategist route hint: {strategy_plan.route_hint}."
    system_prompt += f"\nModel family target: {strategy_plan.model_family}."

    user_prompt += "\n\n## Output Contract\n"
    user_prompt += _render_json_block(strategy_plan.output_contract)
    user_prompt += "\n\n## Evidence Requirements\n"
    user_prompt += _render_json_block(strategy_plan.evidence_requirements)
    user_prompt += "\n\n## Uncertainty Policy\n"
    user_prompt += _render_json_block(strategy_plan.uncertainty_policy)
    if strategy_plan.review_rubric:
        user_prompt += "\n\n## Review Rubric\n"
        user_prompt += "\n".join(f"- {item}" for item in strategy_plan.review_rubric)
    if scenario_pack:
        user_prompt += "\n\n## Scenario Pack\n"
        user_prompt += _render_json_block(
            {
                "scenario": str(scenario_pack.get("scenario") or ""),
                "profile": str(scenario_pack.get("profile") or ""),
                "watch_policy": dict(scenario_pack.get("watch_policy") or {}),
            }
        )
        profile = str(scenario_pack.get("profile") or "").strip()
        if profile:
            system_prompt += f"\nPlanning deliverable profile: {profile}."

    model_hints = _get_model_hints(model_provider, template)
    model_hints["route_hint"] = strategy_plan.route_hint
    model_hints["model_family"] = strategy_plan.model_family
    if custom_context and custom_context.get("depth"):
        model_hints["depth"] = str(custom_context["depth"])
    provider_hints = {
        **dict(strategy_plan.provider_hints or {}),
        "provider_family": strategy_plan.provider_family,
    }

    logger.info(
        f"Built prompt from strategy: template={template}, "
        f"provider={model_provider}, risk={contract.risk_class}, route_hint={strategy_plan.route_hint}"
    )

    return PromptBuildResult(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_used=template,
        model_hints=model_hints,
        output_contract=dict(strategy_plan.output_contract or {}),
        uncertainty_policy=dict(strategy_plan.uncertainty_policy or {}),
        evidence_requirements=dict(strategy_plan.evidence_requirements or {}),
        review_rubric=list(strategy_plan.review_rubric or []),
        provider_hints=provider_hints,
    )


def _render_json_block(value: dict[str, Any]) -> str:
    return f"```json\n{json.dumps(value, ensure_ascii=False, indent=2)}\n```"


def _get_model_hints(model_provider: str, template: str) -> dict[str, Any]:
    """Get model-specific hints based on provider and template."""
    hints = {}

    if model_provider in {"chatgpt", "gpt"}:
        hints["max_tokens"] = 8192
        hints["temperature"] = 0.7
    elif model_provider in {"gemini", "gemini_pro"}:
        hints["max_output_tokens"] = 8192
        hints["temperature"] = 0.7
    elif model_provider in {"claude", "anthropic"}:
        hints["max_tokens"] = 8192
        hints["temperature"] = 0.7

    return hints


def _adapt_system_prompt(
    base_prompt: str,
    model_provider: str,
    risk_class: str,
) -> str:
    """Adapt system prompt based on model provider and risk class."""
    prompt = base_prompt

    # Add uncertainty handling guidance
    if risk_class == "high":
        prompt += "\n\nIMPORTANT: This is a high-stakes request. "
        prompt += "Be thorough in your analysis and explicitly acknowledge "
        prompt += "any uncertainties or limitations in your answer."

    # Model-specific adaptations
    if model_provider in {"gemini", "gemini_pro"}:
        prompt += "\n\nWhen uncertain, state your uncertainty clearly."

    return prompt


def enrich_message_with_contract(
    message: str,
    contract: AskContract,
    model_provider: str = "chatgpt",
) -> str:
    """
    Enrich a message with contract context for prompt assembly.

    This is a simpler version that prepends contract context to the message
    for cases where full prompt assembly is not needed.

    Args:
        message: Original user message
        contract: Ask contract
        model_provider: Model provider

    Returns:
        Enriched message with contract context
    """
    # Build full prompt
    prompt_result = build_prompt_from_contract(
        contract=contract,
        model_provider=model_provider,
    )

    # Combine system + user prompts
    enriched = f"{prompt_result.system_prompt}\n\n---\n\n{prompt_result.user_prompt}"

    return enriched
