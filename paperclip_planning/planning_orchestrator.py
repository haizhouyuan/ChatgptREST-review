"""Paperclip Planning Work Assistant Orchestrator.

One Paperclip agent should call this wrapper. The wrapper owns:
- task type routing (strategic_plan / hr_policy / meeting_extraction / document_draft)
- runtime selection via allocator
- stub planning work execution (to be replaced with real pipeline)
- report persistence

Company purpose: strategic planning, HR, meeting audio extraction, document generation.
Issue prefix: PLA.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Allocator lives in sibling package
sys.path.insert(0, str(Path(__file__).parent.parent / "runtime_allocator"))
from allocator_mvp import PrivacyTier, QualityTier
from skill_agent import execute_with_fallback

VALID_PROVIDERS = {"minimax", "claudekimi", "openai"}

# Map planning task types to allocator task classes
_TASK_CLASS_MAP: dict[str, str] = {
    "strategy_brief": "document_draft",
    "strategic_plan": "document_draft",
    "hr_policy": "hr_sensitive",
    "hr_sensitive_review": "hr_sensitive",
    "meeting_extraction": "meeting_summary",
    "meeting_summary": "meeting_summary",
    "document_draft": "document_draft",
    "decision_memo": "document_draft",
}

# Default quality per task type
_TASK_QUALITY_MAP: dict[str, QualityTier] = {
    "strategy_brief": QualityTier.HIGH,
    "strategic_plan": QualityTier.HIGH,
    "hr_policy": QualityTier.STANDARD,
    "hr_sensitive_review": QualityTier.STANDARD,
    "meeting_extraction": QualityTier.STANDARD,
    "meeting_summary": QualityTier.STANDARD,
    "document_draft": QualityTier.STANDARD,
    "decision_memo": QualityTier.STANDARD,
}

# Privacy requirements per task type
_TASK_PRIVACY_MAP: dict[str, PrivacyTier] = {
    "strategy_brief": PrivacyTier.PRIVATE_CLOUD,
    "strategic_plan": PrivacyTier.PRIVATE_CLOUD,
    "hr_policy": PrivacyTier.LOCAL,
    "hr_sensitive_review": PrivacyTier.LOCAL,
    "meeting_extraction": PrivacyTier.PRIVATE_CLOUD,
    "meeting_summary": PrivacyTier.PRIVATE_CLOUD,
    "document_draft": PrivacyTier.EXTERNAL_CLOUD,
    "decision_memo": PrivacyTier.PRIVATE_CLOUD,
}

# Sensitive tasks that must NOT use external providers
_SENSITIVE_TASKS = frozenset({"hr_policy", "hr_sensitive_review", "meeting_summary", "meeting_extraction"})

# ── Task-specific system prompts ─────────────────────────────────────────────

_TASK_PROMPTS: dict[str, str] = {
    "strategy_brief": (
        "You are a strategic planning analyst. Produce a structured strategy brief "
        "based on the provided context.\n\n"
        "Output format (JSON):\n"
        "{\n"
        '  "summary": str,\n'
        '  "objectives": [{"objective": str, "priority": "high"|"medium"|"low", "owner": str}],\n'
        '  "constraints": [str],\n'
        '  "timeline": {"phase": str, "duration": str, "deliverables": [str]}],\n'
        '  "risks": [{"risk": str, "impact": "high"|"medium"|"low", "mitigation": str}],\n'
        '  "recommended_next_steps": [str],\n'
        '  "decision_required": str\n'
        "}\n\n"
        "Rules:\n"
        "- Be specific and actionable. Avoid generic advice.\n"
        "- Every objective must have a clear owner.\n"
        "- Every risk must have a concrete mitigation.\n"
        "- Output language: {output_language}."
    ),
    "strategic_plan": (
        "You are a strategic planning lead. Produce a comprehensive strategic plan "
        "based on the provided context.\n\n"
        "Output format (JSON):\n"
        "{\n"
        '  "executive_summary": str,\n'
        '  "vision": str,\n'
        '  "strategic_pillars": [{"pillar": str, "initiatives": [str], "kpis": [str]}],\n'
        '  "resource_requirements": {"headcount": str, "budget": str, "tools": [str]},\n'
        '  "timeline": [{"quarter": str, "milestones": [str]}],\n'
        '  "risks": [{"risk": str, "probability": "high"|"medium"|"low", "impact": "high"|"medium"|"low", "mitigation": str}],\n'
        '  "success_metrics": [str],\n'
        '  "dependencies": [str]\n'
        "}\n\n"
        "Rules:\n"
        "- This is a HIGH-STAKES document. Be thorough and conservative.\n"
        "- Include both leading and lagging indicators in success_metrics.\n"
        "- Resource requirements should be realistic, not aspirational.\n"
        "- Output language: {output_language}."
    ),
    "hr_policy": (
        "You are an HR policy specialist. Draft or review the provided HR policy content.\n\n"
        "IMPORTANT: This is a SENSITIVE task. Output must be reviewed by a human HR owner before use.\n\n"
        "Output format (JSON):\n"
        "{\n"
        '  "policy_title": str,\n'
        '  "summary": str,\n'
        '  "key_provisions": [str],\n'
        '  "compliance_notes": [{"region": str, "requirement": str}],\n'
        '  "escalation_checklist": [str],\n'
        '  "requires_human_review": true,\n'
        '  "reviewer_notes": str\n'
        "}\n\n"
        "Rules:\n"
        "- Do NOT make medical, legal, or financial conclusions.\n"
        "- Flag any content that requires legal review.\n"
        "- All provisions must reference applicable regulations where relevant.\n"
        "- Always set requires_human_review to true.\n"
        "- Output language: {output_language}."
    ),
    "hr_sensitive_review": (
        "You are an HR sensitive content reviewer. Review the provided HR material "
        "for compliance, sensitivity, and risk.\n\n"
        "IMPORTANT: This is a SENSITIVE task. Output must be reviewed by a human HR owner.\n\n"
        "Output format (JSON):\n"
        "{\n"
        '  "review_summary": str,\n'
        '  "risk_items": [{"item": str, "risk_level": "high"|"medium"|"low", "recommendation": str}],\n'
        '  "compliance_flags": [{"flag": str, "regulation": str}],\n'
        '  "sensitivity_notes": [str],\n'
        '  "requires_human_review": true,\n'
        '  "recommended_actions": [str]\n'
        "}\n\n"
        "Rules:\n"
        "- Do NOT make medical, legal, or financial conclusions.\n"
        "- Identify potential discrimination, harassment, or privacy concerns.\n"
        "- Flag any content that could create legal liability.\n"
        "- Always set requires_human_review to true.\n"
        "- Output language: {output_language}."
    ),
    "meeting_extraction": (
        "You are a meeting analyst. Extract structured information from the provided "
        "meeting transcript or notes.\n\n"
        "Output format (JSON):\n"
        "{\n"
        '  "summary": str,\n'
        '  "decisions": [{"decision": str, "owner": str, "deadline": str}],\n'
        '  "action_items": [{"item": str, "assignee": str, "due_date": str, "priority": "high"|"medium"|"low"}],\n'
        '  "risks": [{"risk": str, "raised_by": str}],\n'
        '  "open_questions": [str],\n'
        '  "participants": [str],\n'
        '  "meeting_duration_estimate": str\n'
        "}\n\n"
        "Rules:\n"
        "- Extract only what is explicitly stated. Do not infer decisions not made.\n"
        "- Action items must have an assignee. Use 'unassigned' if not specified.\n"
        "- If the transcript is incomplete or unclear, note it in open_questions.\n"
        "- Output language: {output_language}."
    ),
    "meeting_summary": (
        "You are a meeting summarizer. Produce a concise executive summary "
        "from the provided meeting transcript or notes.\n\n"
        "Output format (JSON):\n"
        "{\n"
        '  "executive_summary": str,\n'
        '  "key_decisions": [str],\n'
        '  "top_action_items": [{"item": str, "owner": str}],\n'
        '  "blockers": [str],\n'
        '  "next_meeting_agenda": [str]\n'
        "}\n\n"
        "Rules:\n"
        "- Executive summary: max 3 sentences.\n"
        "- Key decisions: only decisions that were actually made, not discussed.\n"
        "- Top action items: max 5, most important first.\n"
        "- Output language: {output_language}."
    ),
    "document_draft": (
        "You are a professional document writer. Draft the requested document "
        "based on the provided context.\n\n"
        "Output format (JSON):\n"
        "{\n"
        '  "title": str,\n'
        '  "sections": [{"heading": str, "content": str}],\n'
        '  "summary": str,\n'
        '  "key_points": [str],\n'
        '  "tone": str,\n'
        '  "target_audience": str\n'
        "}\n\n"
        "Rules:\n"
        "- Match the tone to the document type (formal for reports, casual for internal notes).\n"
        "- Sections should be self-contained and logically ordered.\n"
        "- Key points: max 5, suitable for an executive briefing.\n"
        "- Output language: {output_language}."
    ),
    "decision_memo": (
        "You are a decision analyst. Produce a structured decision memo "
        "from the provided context.\n\n"
        "Output format (JSON):\n"
        "{\n"
        '  "decision_point": str,\n'
        '  "options": [{"option": str, "pros": [str], "cons": [str], "risk": "high"|"medium"|"low"}],\n'
        '  "recommendation": str,\n'
        '  "rationale": [str],\n'
        '  "resources_required": str,\n'
        '  "timeline": str,\n'
        '  "stakeholders": [str]\n'
        "}\n\n"
        "Rules:\n"
        "- Present at least 2 options (including 'do nothing').\n"
        "- Recommendation must clearly state which option and why.\n"
        "- Rationale should reference specific evidence from the input.\n"
        "- Output language: {output_language}."
    ),
}


class PlanningRequest(BaseModel):
    """Input payload from Paperclip to the Planning Orchestrator."""

    model_config = ConfigDict(extra="ignore")

    request_id: Optional[str] = None
    company_id: Optional[str] = None
    issue_id: Optional[str] = None

    task_type: Literal[
        "strategy_brief", "strategic_plan", "hr_policy", "hr_sensitive_review",
        "meeting_extraction", "meeting_summary", "document_draft", "decision_memo",
    ]
    input_content: str = Field(description="Raw input: text, transcript, or brief")
    output_language: Literal["Chinese", "English"] = "Chinese"

    # Sensitive tasks (hr_*, meeting_*) ignore allow_external and always use local/private
    allow_external: bool = False

    provider_override: Optional[Literal["minimax", "claudekimi", "openai"]] = None
    model_override: Optional[str] = None

    debug: bool = False
    save: bool = True


class PlanningResponse(BaseModel):
    """Normalized response returned to Paperclip."""

    schema_version: Literal["paperclip.planning.run.v1"] = "paperclip.planning.run.v1"

    request_id: str
    company_id: Optional[str] = None
    issue_id: Optional[str] = None

    task_type: str

    status: Literal["completed", "completed_noop", "human_review_required", "blocked", "error"]

    result: str = Field(description="Main planning output (markdown)")
    artifacts: dict[str, str] = Field(default_factory=dict)
    quality_flags: list[str] = Field(default_factory=list)

    runtime_provider: str = ""
    model_name: str = ""
    route_reason_codes: list[str] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)

    duration_seconds: float = 0.0
    generated_at: str = ""

    error_class: Optional[str] = None
    error: Optional[str] = None


# ── Runtime routing (via skill_agent) ──────────────────────────────────────


def _build_execute_params(req: PlanningRequest) -> dict:
    """Build kwargs for execute_with_fallback() from planning request.

    Handles sensitive task privacy enforcement and provider override logic.
    """
    # Enforce sensitive task privacy — block external providers
    allow_external = req.allow_external
    if req.task_type in _SENSITIVE_TASKS and allow_external:
        allow_external = False

    privacy_tier = _TASK_PRIVACY_MAP.get(req.task_type, PrivacyTier.EXTERNAL_CLOUD)
    min_quality = _TASK_QUALITY_MAP.get(req.task_type, QualityTier.STANDARD)

    # Block external override for sensitive tasks
    provider_override = req.provider_override
    if req.task_type in _SENSITIVE_TASKS and provider_override in ("minimax", "openai"):
        provider_override = None

    params: dict = {
        "task_class": _TASK_CLASS_MAP.get(req.task_type, "document_draft"),
        "privacy_tier": privacy_tier.value if isinstance(privacy_tier, PrivacyTier) else privacy_tier,
        "min_quality_tier": min_quality.value if isinstance(min_quality, QualityTier) else min_quality,
        "needs_json": True,
        "input_tokens_est": 8000,
        "output_tokens_est": 4000,
        "can_degrade": True,
        "high_stakes": req.task_type in ("strategy_brief", "strategic_plan"),
    }
    if provider_override:
        params["provider_override"] = provider_override
    if req.model_override:
        params["model_override"] = req.model_override

    return params


# ── Report persistence ──────────────────────────────────────────────────────


def safe_slug(value: str, max_len: int = 40) -> str:
    """Sanitize a string for safe use in filenames."""
    import re
    safe = re.sub(r"[^\w\-]", "_", value)
    safe = safe.strip("_.")
    safe = safe.replace("..", "_")
    return safe[:max_len]


def save_result(
    task_type: str,
    result_text: str,
    runtime_provider: str,
    model_name: str,
    duration_seconds: float,
    output_dir: Optional[str] = None,
) -> tuple[str, str]:
    """Save planning result to JSON + markdown files."""
    if output_dir is None:
        output_dir = os.path.expanduser("~/.paperclip/planning_reports")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{safe_slug(task_type)}_{timestamp}"

    # JSON metadata
    json_path = output_dir / f"{base_name}.json"
    json_path.write_text(
        json.dumps(
            {
                "task_type": task_type,
                "runtime_provider": runtime_provider,
                "model_name": model_name,
                "duration_seconds": duration_seconds,
                "generated_at": datetime.now().isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    # Markdown report
    md_path = output_dir / f"{base_name}.md"
    md_content = (
        f"# Planning Report: {task_type}\n\n"
        f"- Runtime: {runtime_provider} / {model_name}\n"
        f"- Duration: {duration_seconds:.1f}s\n"
        f"- Generated: {datetime.now().isoformat()}\n\n"
        f"## Result\n\n{result_text}\n"
    )
    md_path.write_text(md_content)

    return str(json_path), str(md_path)


# ── Main entry point ────────────────────────────────────────────────────────


def run_from_paperclip(payload: dict[str, Any]) -> dict[str, Any]:
    """Main entry point for Paperclip custom adapter."""

    req = PlanningRequest(**payload)
    request_id = req.request_id or str(uuid.uuid4())

    quality_flags: list[str] = []
    if req.task_type in _SENSITIVE_TASKS:
        quality_flags.append("sensitive_task_private_only")

    # Build messages for the LLM using task-specific prompt
    system_prompt = _TASK_PROMPTS.get(req.task_type, "")
    system_prompt = system_prompt.format(output_language=req.output_language)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.input_content},
    ]

    # Execute via skill_agent with fallback
    exec_params = _build_execute_params(req)
    skill_result = execute_with_fallback(
        messages=messages,
        max_tokens=4096,
        **exec_params,
    )

    provider = skill_result.provider_id
    model = skill_result.model_name
    reason_codes = list(skill_result.reason_codes)
    fallback_chain = list(skill_result.fallback_chain)

    artifacts: dict[str, str] = {}

    if skill_result.success:
        result_text = skill_result.content
        work_duration = skill_result.total_latency_ms / 1000.0

        if req.save:
            try:
                json_path, md_path = save_result(
                    task_type=req.task_type,
                    result_text=result_text,
                    runtime_provider=provider,
                    model_name=model,
                    duration_seconds=work_duration,
                )
                artifacts["json"] = json_path
                artifacts["markdown"] = md_path
            except Exception as save_error:
                reason_codes.append(f"save_failed={save_error.__class__.__name__}")

        if req.task_type in _SENSITIVE_TASKS:
            status = "human_review_required"
            quality_flags.append("requires_human_review")
        else:
            status = "completed"
        error_class = None
        error = None
    else:
        result_text = ""
        work_duration = skill_result.total_latency_ms / 1000.0
        status = "error"
        error_class = skill_result.error_class
        error = skill_result.error

    response = PlanningResponse(
        request_id=request_id,
        company_id=req.company_id,
        issue_id=req.issue_id,
        task_type=req.task_type,
        status=status,
        result=result_text,
        artifacts=artifacts,
        quality_flags=quality_flags,
        runtime_provider=provider,
        model_name=model,
        route_reason_codes=reason_codes,
        fallback_chain=fallback_chain,
        duration_seconds=work_duration,
        generated_at=datetime.now().isoformat(),
        error_class=error_class,
        error=error,
    )

    return response.model_dump()


# ── CLI entry point ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Paperclip Planning Work Assistant Orchestrator")
    parser.add_argument("--payload", help="JSON payload string")
    parser.add_argument("--payload-file", help="Path to JSON payload file")
    parser.add_argument(
        "--task-type",
        choices=["strategy_brief", "strategic_plan", "hr_policy", "hr_sensitive_review",
                 "meeting_extraction", "meeting_summary", "document_draft", "decision_memo"],
        default="document_draft",
    )
    parser.add_argument("--input", dest="input_content", help="Input content text")
    parser.add_argument("--input-file", help="Path to input content file")
    parser.add_argument(
        "--language",
        default="Chinese",
        choices=["Chinese", "English"],
    )
    parser.add_argument(
        "--provider",
        default=None,
        choices=["minimax", "claudekimi", "openai"],
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.payload_file:
        payload = json.loads(Path(args.payload_file).read_text())
    elif args.payload:
        payload = json.loads(args.payload)
    else:
        input_content = args.input_content
        if not input_content and args.input_file:
            input_content = Path(args.input_file).read_text()
        if not input_content:
            parser.error("--input or --input-file is required when --payload/--payload-file is not used")
        payload = {
            "task_type": args.task_type,
            "input_content": input_content,
            "output_language": args.language,
            "provider_override": args.provider,
            "debug": args.debug,
        }

    response = run_from_paperclip(payload)
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
