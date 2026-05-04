"""Paperclip Finbot Orchestrator.

One Paperclip agent should call this wrapper. The wrapper owns:
- data mode selection
- runtime routing
- TradingAgents invocation
- terminal failure normalization
- report persistence

This intentionally does NOT expose every TradingAgents internal analyst as a
separate Paperclip agent. TradingAgents remains the internal LangGraph runtime.
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

try:
    from .tradingagents_adapter import run_tradingagents, save_result
except ImportError:
    from tradingagents_adapter import run_tradingagents, save_result

# Allocator lives in sibling package
sys.path.insert(0, str(Path(__file__).parent.parent / "runtime_allocator"))
from allocator_mvp import (
    allocate,
    PrivacyTier,
    QualityTier,
    QuotaLedger,
    RouteRequest,
)


VALID_TRADINGAGENTS_PROVIDERS = {"minimax", "claudekimi", "openai"}


class PaperclipFinbotRequest(BaseModel):
    """Input payload from Paperclip to the Finbot Orchestrator."""

    model_config = ConfigDict(extra="ignore")

    request_id: Optional[str] = None
    company_id: Optional[str] = None
    issue_id: Optional[str] = None

    ticker: str
    trade_date: str = Field(description="YYYY-MM-DD trade/as-of date")

    output_language: Literal["Chinese", "English"] = "Chinese"

    # live: run normal data tools
    # market_only: use only market analyst; safest during Yahoo 429
    # offline: caller has prepared local/cache data; do not assume live Yahoo
    data_mode: Literal["live", "market_only", "offline"] = "market_only"

    selected_analysts: Optional[
        list[Literal["market", "news", "social", "fundamentals"]]
    ] = None

    # Until allocator quality gating is fixed, Finbot E2E should be hard-pinned
    # to claudekimi unless explicitly overridden.
    provider_override: Optional[Literal["minimax", "claudekimi", "openai"]] = None
    model_override: Optional[str] = None
    backend_url_override: Optional[str] = None

    max_recur_limit: int = 40
    debug: bool = False
    save: bool = True


class PaperclipFinbotResponse(BaseModel):
    """Normalized response returned to Paperclip."""

    schema_version: Literal["paperclip.finbot.run.v1"] = "paperclip.finbot.run.v1"

    request_id: str
    company_id: Optional[str] = None
    issue_id: Optional[str] = None

    ticker: str
    trade_date: str

    status: Literal[
        "completed",
        "completed_no_trade",
        "human_review_required",
        "blocked",
        "error",
    ]

    decision: str
    retry_allowed: bool = False
    requires_human_review: bool = False

    runtime_provider: str
    model_name: str
    route_reason_codes: list[str] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)

    selected_analysts: list[str] = Field(default_factory=list)
    data_mode: str

    duration_seconds: float = 0.0
    generated_at: str

    markdown_report: str = ""
    artifacts: dict[str, str] = Field(default_factory=dict)

    error_class: Optional[str] = None
    error: Optional[str] = None


def _default_selected_analysts(req: PaperclipFinbotRequest) -> list[str]:
    if req.selected_analysts:
        return list(req.selected_analysts)

    if req.data_mode == "market_only":
        return ["market"]

    if req.data_mode == "offline":
        # Offline mode can safely include fundamentals only after local/static
        # fundamental provider is wired. For the first 48h, keep market only.
        return ["market"]

    # Avoid "social" initially because it also relies on get_news in your current
    # tool-node wiring. Add it back after data circuit breakers are stable.
    return ["market", "news", "fundamentals"]


def _provider_endpoint(provider: str) -> tuple[str, str, str]:
    """Return provider, default model, endpoint."""
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


def _route_runtime(req: PaperclipFinbotRequest):
    """Route Finbot E2E.

    Current allocator_mvp.py has a quality-gate bug, so this function still calls
    the allocator for audit but hard-pins E2E to claudekimi unless the caller
    explicitly overrides the provider.
    """
    ledger = QuotaLedger()

    route_req = RouteRequest(
        task_class="finbot_trade_proposal",
        privacy_tier_required=PrivacyTier.EXTERNAL_CLOUD,
        min_quality_tier=QualityTier.CRITICAL,
        needs_tool_calling=True,
        needs_json=True,
        input_tokens_est=14000,
        output_tokens_est=5000,
        can_degrade=False,
        high_stakes=True,
    )

    decision = allocate(route_req, ledger=ledger)

    reason_codes = list(decision.reason_codes)
    fallback_chain = list(decision.fallback_chain)

    if req.provider_override:
        provider, model, endpoint = _provider_endpoint(req.provider_override)
        reason_codes.append(f"provider_override={req.provider_override}")
        return provider, model, endpoint, reason_codes, fallback_chain

    # Safety override until allocator quality tier is fixed.
    if decision.provider_id != "claudekimi":
        provider, model, endpoint = _provider_endpoint("claudekimi")
        reason_codes.append(
            f"allocator_selected_{decision.provider_id}_but_finbot_e2e_hard_pinned_to_claudekimi"
        )
        return provider, model, endpoint, reason_codes, fallback_chain

    provider, model, endpoint = _provider_endpoint("claudekimi")
    return provider, model, endpoint, reason_codes, fallback_chain


def run_from_paperclip(payload: dict[str, Any]) -> dict[str, Any]:
    """Main entry point for Paperclip custom adapter."""

    req = PaperclipFinbotRequest(**payload)
    request_id = req.request_id or str(uuid.uuid4())

    selected_analysts = _default_selected_analysts(req)

    provider, default_model, default_endpoint, reason_codes, fallback_chain = _route_runtime(req)

    model = req.model_override or default_model
    backend_url = req.backend_url_override or default_endpoint or None

    result = run_tradingagents(
        ticker=req.ticker,
        date=req.trade_date,
        provider=provider,
        model=model,
        backend_url=backend_url,
        output_language=req.output_language,
        debug=req.debug,
        selected_analysts=selected_analysts,
        max_recur_limit=req.max_recur_limit,
        resolve_pending_returns=False,
        data_mode=req.data_mode,
    )

    artifacts: dict[str, str] = {}

    if req.save:
        try:
            json_path, md_path = save_result(result)
            artifacts["json"] = json_path
            artifacts["markdown"] = md_path
        except Exception as save_error:
            reason_codes.append(f"save_failed={save_error.__class__.__name__}")

    status: Literal[
        "completed",
        "completed_no_trade",
        "human_review_required",
        "blocked",
        "error",
    ]

    requires_human_review = False

    if result.status == "completed":
        status = "completed"
    elif result.status == "human_review_required":
        status = "human_review_required"
        requires_human_review = True
    elif result.error:
        # Do not ask Paperclip to auto-retry. Failed Finbot runs should become
        # human-reviewable artifacts, not background retry storms.
        status = "human_review_required"
        requires_human_review = True
    else:
        status = "completed_no_trade"

    response = PaperclipFinbotResponse(
        request_id=request_id,
        company_id=req.company_id,
        issue_id=req.issue_id,
        ticker=req.ticker.upper(),
        trade_date=req.trade_date,
        status=status,
        decision=result.decision,
        retry_allowed=False,
        requires_human_review=requires_human_review,
        runtime_provider=result.runtime_provider,
        model_name=result.model_name,
        route_reason_codes=reason_codes,
        fallback_chain=fallback_chain,
        selected_analysts=selected_analysts,
        data_mode=req.data_mode,
        duration_seconds=result.duration_seconds,
        generated_at=datetime.now().isoformat(),
        markdown_report=result.markdown_report,
        artifacts=artifacts,
        error_class=result.error_class,
        error=result.error,
    )

    return response.model_dump()


def main() -> None:
    parser = argparse.ArgumentParser(description="Paperclip Finbot Orchestrator")
    parser.add_argument("--payload", help="JSON payload string")
    parser.add_argument("--payload-file", help="Path to JSON payload file")
    parser.add_argument("--ticker", help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--date", default="2026-05-01", help="Trade date YYYY-MM-DD")
    parser.add_argument(
        "--data-mode",
        default="market_only",
        choices=["live", "market_only", "offline"],
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
        if not args.ticker:
            parser.error("--ticker is required when --payload/--payload-file is not used")
        payload = {
            "ticker": args.ticker,
            "trade_date": args.date,
            "data_mode": args.data_mode,
            "provider_override": args.provider,
            "debug": args.debug,
        }

    response = run_from_paperclip(payload)
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
