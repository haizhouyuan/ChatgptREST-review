"""Paperclip Labebe Orchestrator.

One Paperclip agent should call this wrapper. The wrapper owns:
- task type dispatch
- runtime routing (via allocator_mvp)
- stub work execution (to be replaced with real pipelines)
- result persistence
- terminal failure normalization

Task types:
  product_review_analysis  -- Analyze Amazon/customer reviews for a product
  dtc_copy                 -- Generate DTC marketing copy
  boss_gallery_card        -- Generate Boss Gallery product card content
  commerce_decision        -- Commerce decision layer analysis
  evidence_bundle          -- Assemble claim-safe evidence bundle

Default provider routing:
  minimax    -- copy, formatting, gallery cards (fast, cheap)
  claudekimi -- commerce decisions, evidence bundles (high quality)
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

PAPERCLIP_API = os.getenv("PAPERCLIP_API", "http://127.0.0.1:3100/api")
LABEBE_COMPANY_ID = "9ca70186-256c-49f4-8d87-038a94f32acb"
ISSUE_PREFIX = "LABA"

REPORT_DIR = Path(os.path.expanduser("~/.paperclip/labebe_reports"))

VALID_PROVIDERS = {"minimax", "claudekimi", "openai"}

# ── Task type -> allocator task class mapping ────────────────────────────────

_TASK_CLASS_MAP: dict[str, str] = {
    "product_review_analysis": "labebe_review_analysis",
    "dtc_copy": "dtc_copy",
    "boss_gallery_card": "boss_gallery_card",
    "commerce_decision": "labebe_commerce_decision",
    "evidence_bundle": "labebe_evidence_bundle",
}

_TASK_QUALITY_MAP: dict[str, QualityTier] = {
    "product_review_analysis": QualityTier.HIGH,
    "dtc_copy": QualityTier.STANDARD,
    "boss_gallery_card": QualityTier.STANDARD,
    "commerce_decision": QualityTier.CRITICAL,
    "evidence_bundle": QualityTier.CRITICAL,
}


# ── Pydantic models ─────────────────────────────────────────────────────────


class LabebeRequest(BaseModel):
    """Input payload from Paperclip to the Labebe Orchestrator."""

    model_config = ConfigDict(extra="ignore")

    request_id: Optional[str] = None
    company_id: Optional[str] = None
    issue_id: Optional[str] = None

    task_type: Literal[
        "product_review_analysis",
        "dtc_copy",
        "boss_gallery_card",
        "commerce_decision",
        "evidence_bundle",
    ]

    input_content: str = Field(description="Primary input text or JSON payload")
    product_id: Optional[str] = Field(
        default=None, description="Labebe product SKU or ASIN"
    )

    output_language: Literal["Chinese", "English"] = "Chinese"

    provider_override: Optional[Literal["minimax", "claudekimi", "openai"]] = None
    model_override: Optional[str] = None

    debug: bool = False
    save: bool = True


class LabebeResponse(BaseModel):
    """Normalized response returned to Paperclip."""

    schema_version: Literal["paperclip.labebe.run.v1"] = "paperclip.labebe.run.v1"

    request_id: str
    company_id: Optional[str] = None
    issue_id: Optional[str] = None

    task_type: str
    product_id: Optional[str] = None

    status: Literal[
        "completed",
        "completed_stub",
        "human_review_required",
        "blocked",
        "error",
    ]

    result: str = ""
    result_structured: Optional[dict[str, Any]] = None

    runtime_provider: str
    model_name: str
    route_reason_codes: list[str] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)

    duration_seconds: float = 0.0
    generated_at: str

    artifacts: dict[str, str] = Field(default_factory=dict)

    error_class: Optional[str] = None
    error: Optional[str] = None


# ── Runtime routing (via skill_agent) ──────────────────────────────────────


def _build_execute_params(req: LabebeRequest) -> dict:
    """Build kwargs for execute_with_fallback() from labebe request."""
    task_class = _TASK_CLASS_MAP.get(req.task_type, "labebe_review_analysis")
    min_quality = _TASK_QUALITY_MAP.get(req.task_type, QualityTier.STANDARD)

    params: dict = {
        "task_class": task_class,
        "privacy_tier": "external_cloud",
        "min_quality_tier": min_quality.value if isinstance(min_quality, QualityTier) else min_quality,
        "needs_json": True,
        "input_tokens_est": 4000,
        "output_tokens_est": 2000,
        "can_degrade": req.task_type not in ("commerce_decision", "evidence_bundle"),
        "high_stakes": req.task_type in ("commerce_decision", "evidence_bundle"),
    }
    if req.provider_override:
        params["provider_override"] = req.provider_override
    if req.model_override:
        params["model_override"] = req.model_override

    return params


# ── Stub work functions ─────────────────────────────────────────────────────
# These return structured placeholders. Replace with real pipelines later.


def _stub_product_review_analysis(
    input_content: str,
    product_id: Optional[str],
    output_language: str,
) -> tuple[str, dict]:
    """Stub: analyze product reviews."""
    summary = (
        f"[STUB] Review analysis for product {product_id or 'unknown'}. "
        f"Input length: {len(input_content)} chars. "
        f"Language: {output_language}. "
        "Real implementation will extract sentiment, key themes, "
        "complaint clusters, and competitive positioning from review data."
    )
    structured = {
        "sentiment_score": None,
        "top_themes": [],
        "complaint_clusters": [],
        "recommendation": "stub_pending",
    }
    return summary, structured


def _stub_dtc_copy(
    input_content: str,
    product_id: Optional[str],
    output_language: str,
) -> tuple[str, dict]:
    """Stub: generate DTC marketing copy."""
    summary = (
        f"[STUB] DTC copy for product {product_id or 'unknown'}. "
        f"Input length: {len(input_content)} chars. "
        f"Language: {output_language}. "
        "Real implementation will generate headline, subhead, body copy, "
        "CTA, and SEO metadata for direct-to-consumer channels."
    )
    structured = {
        "headline": None,
        "subhead": None,
        "body_copy": None,
        "cta": None,
        "seo_title": None,
        "seo_description": None,
    }
    return summary, structured


def _stub_boss_gallery_card(
    input_content: str,
    product_id: Optional[str],
    output_language: str,
) -> tuple[str, dict]:
    """Stub: generate Boss Gallery product card."""
    summary = (
        f"[STUB] Boss Gallery card for product {product_id or 'unknown'}. "
        f"Input length: {len(input_content)} chars. "
        f"Language: {output_language}. "
        "Real implementation will produce gallery card JSON with "
        "image slots, feature bullets, price display, and trust badges."
    )
    structured = {
        "card_title": None,
        "feature_bullets": [],
        "price_display": None,
        "trust_badges": [],
        "image_slots": [],
    }
    return summary, structured


def _stub_commerce_decision(
    input_content: str,
    product_id: Optional[str],
    output_language: str,
) -> tuple[str, dict]:
    """Stub: commerce decision layer analysis."""
    summary = (
        f"[STUB] Commerce decision for product {product_id or 'unknown'}. "
        f"Input length: {len(input_content)} chars. "
        f"Language: {output_language}. "
        "Real implementation will analyze pricing elasticity, channel fit, "
        "inventory risk, and margin optimization."
    )
    structured = {
        "decision": None,
        "confidence": None,
        "pricing_recommendation": None,
        "channel_fit_score": None,
        "risk_flags": [],
    }
    return summary, structured


def _stub_evidence_bundle(
    input_content: str,
    product_id: Optional[str],
    output_language: str,
) -> tuple[str, dict]:
    """Stub: assemble claim-safe evidence bundle."""
    summary = (
        f"[STUB] Evidence bundle for product {product_id or 'unknown'}. "
        f"Input length: {len(input_content)} chars. "
        f"Language: {output_language}. "
        "Real implementation will assemble claim-safe evidence with "
        "source attribution, confidence levels, and regulatory flags."
    )
    structured = {
        "claims": [],
        "sources": [],
        "confidence_map": {},
        "regulatory_flags": [],
        "bundle_hash": None,
    }
    return summary, structured


_STUB_DISPATCH = {
    "product_review_analysis": _stub_product_review_analysis,
    "dtc_copy": _stub_dtc_copy,
    "boss_gallery_card": _stub_boss_gallery_card,
    "commerce_decision": _stub_commerce_decision,
    "evidence_bundle": _stub_evidence_bundle,
}


# ── Persistence ─────────────────────────────────────────────────────────────


def save_result(resp: LabebeResponse) -> tuple[str, str]:
    """Save Labebe result to JSON + markdown files."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    product_tag = resp.product_id or "noprod"
    base_name = f"{resp.task_type}_{product_tag}_{timestamp}"

    # JSON
    json_path = REPORT_DIR / f"{base_name}.json"
    json_path.write_text(
        json.dumps(
            resp.model_dump(),
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    # Markdown
    md_path = REPORT_DIR / f"{base_name}.md"
    md_lines = [
        f"# Labebe Task: {resp.task_type}",
        "",
        f"- Product: {resp.product_id or 'N/A'}",
        f"- Runtime: {resp.runtime_provider} / {resp.model_name}",
        f"- Duration: {resp.duration_seconds:.1f}s",
        f"- Status: {resp.status}",
        f"- Generated: {resp.generated_at}",
        "",
        "## Result",
        "",
        resp.result or "(empty)",
        "",
    ]
    if resp.result_structured:
        md_lines += [
            "## Structured Output",
            "",
            "```json",
            json.dumps(resp.result_structured, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    if resp.error:
        md_lines += ["## Error", "", f"```", resp.error, "```", ""]
    md_path.write_text("\n".join(md_lines))

    return str(json_path), str(md_path)


# ── Main entry point ────────────────────────────────────────────────────────


def run_from_paperclip(payload: dict[str, Any]) -> dict[str, Any]:
    """Main entry point for Paperclip custom adapter."""

    req = LabebeRequest(**payload)
    request_id = req.request_id or str(uuid.uuid4())

    # Build messages for the LLM
    system_prompt = (
        f"You are a Labebe product analysis assistant. Task type: {req.task_type}. "
        f"Product: {req.product_id or 'unknown'}. "
        f"Output language: {req.output_language}. "
        f"Provide structured, actionable product analysis output."
    )
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

    result_structured = None

    if skill_result.success:
        result_text = skill_result.content
        duration = skill_result.total_latency_ms / 1000.0

        # Try to parse structured JSON from LLM output
        try:
            result_structured = json.loads(result_text)
            if isinstance(result_structured, dict):
                result_text = result_structured.pop("result", result_text)
        except (json.JSONDecodeError, AttributeError):
            pass

        status = "completed"
        error_class = None
        error = None
    else:
        result_text = ""
        duration = skill_result.total_latency_ms / 1000.0
        status = "error"
        error_class = skill_result.error_class
        error = skill_result.error

    # Build response
    response = LabebeResponse(
        request_id=request_id,
        company_id=req.company_id or LABEBE_COMPANY_ID,
        issue_id=req.issue_id,
        task_type=req.task_type,
        product_id=req.product_id,
        status=status,
        result=result_text,
        result_structured=result_structured,
        runtime_provider=provider,
        model_name=model,
        route_reason_codes=reason_codes,
        fallback_chain=fallback_chain,
        duration_seconds=duration,
        generated_at=datetime.now().isoformat(),
        error_class=error_class,
        error=error,
    )

    # Persist
    if req.save:
        try:
            json_path, md_path = save_result(response)
            response.artifacts["json"] = json_path
            response.artifacts["markdown"] = md_path
        except Exception as save_err:
            reason_codes.append(f"save_failed={save_err.__class__.__name__}")

    return response.model_dump()


# ── CLI entry point ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Paperclip Labebe Orchestrator")
    parser.add_argument("--payload", help="JSON payload string")
    parser.add_argument("--payload-file", help="Path to JSON payload file")
    parser.add_argument(
        "--task-type",
        choices=[
            "product_review_analysis",
            "dtc_copy",
            "boss_gallery_card",
            "commerce_decision",
            "evidence_bundle",
        ],
        help="Task type to run",
    )
    parser.add_argument("--input", dest="input_content", help="Input text content")
    parser.add_argument("--input-file", help="Path to input text file")
    parser.add_argument("--product-id", help="Labebe product SKU or ASIN")
    parser.add_argument(
        "--language",
        default="Chinese",
        choices=["Chinese", "English"],
        help="Output language",
    )
    parser.add_argument(
        "--provider",
        default=None,
        choices=["minimax", "claudekimi", "openai"],
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-save", action="store_true", help="Skip saving results")
    args = parser.parse_args()

    if args.payload_file:
        payload = json.loads(Path(args.payload_file).read_text())
    elif args.payload:
        payload = json.loads(args.payload)
    else:
        if not args.task_type:
            parser.error("--task-type is required when --payload/--payload-file is not used")

        input_content = args.input_content
        if not input_content and args.input_file:
            input_content = Path(args.input_file).read_text()
        if not input_content:
            input_content = ""

        payload = {
            "task_type": args.task_type,
            "input_content": input_content,
            "product_id": args.product_id,
            "output_language": args.language,
            "provider_override": args.provider,
            "debug": args.debug,
            "save": not args.no_save,
        }

    response = run_from_paperclip(payload)
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
