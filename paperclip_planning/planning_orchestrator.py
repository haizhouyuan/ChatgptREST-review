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
from allocator_mvp import (
    PrivacyTier,
    QualityTier,
    QuotaLedger,
    RouteRequest,
    allocate,
)

VALID_PROVIDERS = {"minimax", "claudekimi", "openai"}

# Map planning task types to allocator task classes
_TASK_CLASS_MAP: dict[str, str] = {
    "strategic_plan": "document_draft",
    "hr_policy": "hr_sensitive",
    "meeting_extraction": "meeting_summary",
    "document_draft": "document_draft",
}

# Default quality per task type
_TASK_QUALITY_MAP: dict[str, QualityTier] = {
    "strategic_plan": QualityTier.HIGH,
    "hr_policy": QualityTier.STANDARD,
    "meeting_extraction": QualityTier.STANDARD,
    "document_draft": QualityTier.STANDARD,
}

# Privacy requirements per task type
_TASK_PRIVACY_MAP: dict[str, PrivacyTier] = {
    "strategic_plan": PrivacyTier.PRIVATE_CLOUD,
    "hr_policy": PrivacyTier.LOCAL,
    "meeting_extraction": PrivacyTier.PRIVATE_CLOUD,
    "document_draft": PrivacyTier.EXTERNAL_CLOUD,
}


class PlanningRequest(BaseModel):
    """Input payload from Paperclip to the Planning Orchestrator."""

    model_config = ConfigDict(extra="ignore")

    request_id: Optional[str] = None
    company_id: Optional[str] = None
    issue_id: Optional[str] = None

    task_type: Literal[
        "strategic_plan", "hr_policy", "meeting_extraction", "document_draft"
    ]
    input_content: str = Field(description="Raw input: text, transcript, or brief")
    output_language: Literal["Chinese", "English"] = "Chinese"

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

    status: Literal["completed", "blocked", "error"]

    result: str = Field(description="Main planning output (markdown)")
    artifacts: dict[str, str] = Field(default_factory=dict)

    runtime_provider: str = ""
    model_name: str = ""
    route_reason_codes: list[str] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)

    duration_seconds: float = 0.0
    generated_at: str = ""

    error_class: Optional[str] = None
    error: Optional[str] = None


# ── Provider endpoint lookup ────────────────────────────────────────────────


def _provider_endpoint(provider: str) -> tuple[str, str, str]:
    """Return (provider_id, default_model, endpoint)."""
    if provider == "minimax":
        return (
            "minimax",
            "MiniMax-M2.7-highspeed",
            os.getenv("MINIMAX_API_HOST", "https://api.minimaxi.com").rstrip("/") + "/v1",
        )
    if provider == "claudekimi":
        return (
            "claudekimi",
            "mimo-v2.5-pro",
            os.getenv("CLAUDEKIMI_ENDPOINT", "http://127.0.0.1:8080/v1"),
        )
    if provider == "openai":
        return ("openai", "gpt-4.1", os.getenv("OPENAI_BASE_URL", ""))
    raise ValueError(f"Unsupported provider: {provider}")


# ── Runtime routing ─────────────────────────────────────────────────────────


def _route_runtime(req: PlanningRequest):
    """Route planning task via the allocator.

    Planning tasks default to minimax (cheap) unless the task is high-stakes
    or the caller explicitly overrides.
    """
    ledger = QuotaLedger()

    alloc_task_class = _TASK_CLASS_MAP.get(req.task_type, "document_draft")
    min_quality = _TASK_QUALITY_MAP.get(req.task_type, QualityTier.STANDARD)
    privacy = _TASK_PRIVACY_MAP.get(req.task_type, PrivacyTier.EXTERNAL_CLOUD)

    route_req = RouteRequest(
        task_class=alloc_task_class,
        privacy_tier_required=privacy,
        min_quality_tier=min_quality,
        needs_tool_calling=False,
        needs_json=True,
        input_tokens_est=8000,
        output_tokens_est=4000,
        can_degrade=True,
        high_stakes=(req.task_type == "strategic_plan"),
    )

    decision = allocate(route_req, ledger=ledger)

    reason_codes = list(decision.reason_codes)
    fallback_chain = list(decision.fallback_chain)

    # Explicit caller override takes priority
    if req.provider_override:
        provider, model, endpoint = _provider_endpoint(req.provider_override)
        reason_codes.append(f"provider_override={req.provider_override}")
        return provider, model, endpoint, reason_codes, fallback_chain

    if decision.blocked:
        # Fallback to minimax (cheapest) if allocator blocks
        provider, model, endpoint = _provider_endpoint("minimax")
        reason_codes.append("allocator_blocked_fallback_minimax")
        return provider, model, endpoint, reason_codes, fallback_chain

    # Use allocator's pick if it's a supported API provider; otherwise
    # fall back to minimax.  The allocator may return local-only providers
    # (gemini_local, ollama_gpu0) that have no HTTP endpoint usable here.
    if decision.provider_id in VALID_PROVIDERS:
        provider, model, endpoint = _provider_endpoint(decision.provider_id)
    else:
        provider, model, endpoint = _provider_endpoint("minimax")
        reason_codes.append(f"allocator_selected_{decision.provider_id}_unsupported_fallback_minimax")
    return provider, model, endpoint, reason_codes, fallback_chain


# ── Stub planning work ──────────────────────────────────────────────────────


def _run_planning_work(
    task_type: str,
    input_content: str,
    output_language: str,
    provider: str,
    model: str,
    endpoint: str,
    debug: bool,
) -> dict[str, Any]:
    """Execute the actual planning work.

    STUB: returns a structured placeholder. Replace with real pipeline
    (e.g. LLM call, document template, ASR integration) when ready.
    """
    start = datetime.now()

    # Build a prompt hint for each task type
    task_prompts = {
        "strategic_plan": "请根据以下输入内容，生成一份结构化的战略规划方案，包含目标、关键举措、时间线和风险评估。",
        "hr_policy": "请根据以下输入内容，起草一份人力资源政策文档，包含适用范围、具体条款和执行流程。",
        "meeting_extraction": "请根据以下会议录音转录文本，提取会议纪要，包括议题、决议、待办事项和责任人。",
        "document_draft": "请根据以下输入内容，生成一份结构化的文档草稿。",
    }
    system_hint = task_prompts.get(task_type, task_prompts["document_draft"])

    lang_hint = "请用中文输出。" if output_language == "Chinese" else "Please output in English."

    # --- STUB: structured placeholder ---
    stub_result = (
        f"## {task_type.replace('_', ' ').title()} -- Draft Output\n\n"
        f"**Provider:** {provider} / {model}\n"
        f"**Language:** {output_language}\n"
        f"**Input length:** {len(input_content)} chars\n\n"
        f"### Instructions (to be sent to LLM)\n\n"
        f"{system_hint} {lang_hint}\n\n"
        f"### Input Content (excerpt)\n\n"
        f"```\n{input_content[:500]}\n```\n\n"
        f"---\n"
        f"*This is a stub response. Replace `_run_planning_work` with a real "
        f"LLM / pipeline call to produce actual planning output.*\n"
    )

    duration = (datetime.now() - start).total_seconds()

    return {
        "result": stub_result,
        "duration_seconds": duration,
        "status": "completed",
        "error": None,
        "error_class": None,
    }


# ── Report persistence ──────────────────────────────────────────────────────


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
    base_name = f"{task_type}_{timestamp}"

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

    provider, default_model, default_endpoint, reason_codes, fallback_chain = _route_runtime(req)

    model = req.model_override or default_model
    backend_url = default_endpoint or None

    if req.debug:
        print(f"[Planning] Task: {req.task_type}, Provider: {provider}, Model: {model}")
        print(f"[Planning] Backend: {backend_url}")
        print(f"[Planning] Input length: {len(req.input_content)} chars")

    try:
        work_result = _run_planning_work(
            task_type=req.task_type,
            input_content=req.input_content,
            output_language=req.output_language,
            provider=provider,
            model=model,
            endpoint=backend_url,
            debug=req.debug,
        )
    except Exception as e:
        work_result = {
            "result": "",
            "duration_seconds": 0.0,
            "status": "error",
            "error": str(e),
            "error_class": e.__class__.__name__,
        }

    artifacts: dict[str, str] = {}

    if req.save and work_result["status"] == "completed":
        try:
            json_path, md_path = save_result(
                task_type=req.task_type,
                result_text=work_result["result"],
                runtime_provider=provider,
                model_name=model,
                duration_seconds=work_result["duration_seconds"],
            )
            artifacts["json"] = json_path
            artifacts["markdown"] = md_path
        except Exception as save_error:
            reason_codes.append(f"save_failed={save_error.__class__.__name__}")

    status: Literal["completed", "blocked", "error"]
    if work_result["status"] == "completed":
        status = "completed"
    elif work_result.get("error"):
        status = "error"
    else:
        status = "blocked"

    response = PlanningResponse(
        request_id=request_id,
        company_id=req.company_id,
        issue_id=req.issue_id,
        task_type=req.task_type,
        status=status,
        result=work_result.get("result", ""),
        artifacts=artifacts,
        runtime_provider=provider,
        model_name=model,
        route_reason_codes=reason_codes,
        fallback_chain=fallback_chain,
        duration_seconds=work_result.get("duration_seconds", 0.0),
        generated_at=datetime.now().isoformat(),
        error_class=work_result.get("error_class"),
        error=work_result.get("error"),
    )

    return response.model_dump()


# ── CLI entry point ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Paperclip Planning Work Assistant Orchestrator")
    parser.add_argument("--payload", help="JSON payload string")
    parser.add_argument("--payload-file", help="Path to JSON payload file")
    parser.add_argument(
        "--task-type",
        choices=["strategic_plan", "hr_policy", "meeting_extraction", "document_draft"],
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
