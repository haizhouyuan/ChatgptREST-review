"""TradingAgents adapter for Paperclip Finbot Orchestrator.

Wraps TradingAgentsGraph.propagate() into a callable that:
1. Builds config from environment
2. Runs the full LangGraph pipeline (analysts -> debate -> risk -> decision)
3. Returns structured JSON + markdown report

Usage:
    from paperclip_finbot.tradingagents_adapter import run_tradingagents
    result = run_tradingagents(ticker="AAPL", date="2026-05-01")
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── Quality gate constants and helpers ────────────────────────────────────────

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)

REFUSAL_MARKERS = [
    "i can't",
    "i cannot",
    "i'm not a financial advisor",
    "not a financial advisor",
    "i need to step back",
    "我无法满足",
    "我不是持证金融顾问",
    "不能提供投资建议",
    "无法继续",
    "prompt injection",
]

VALID_DECISIONS = {
    "BUY",
    "SELL",
    "HOLD",
    "NO_TRADE_DATA_UNAVAILABLE",
    "HUMAN_REVIEW_REQUIRED",
}


def strip_think_blocks(text: str | None) -> str:
    """Remove <think>...</think> draft blocks from LLM output."""
    if not text:
        return ""
    return THINK_BLOCK_RE.sub("", text).strip()


def has_think_block(text: str | None) -> bool:
    """Check if text contains <think> blocks."""
    return bool(text and THINK_BLOCK_RE.search(text))


def contains_refusal(text: str | None) -> bool:
    """Detect LLM refusal patterns in output."""
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def normalize_decision(raw: str | None) -> tuple[str, list[str]]:
    """Normalize final trade decision to valid enum. Returns (decision, flags)."""
    flags: list[str] = []
    text = (raw or "").strip()

    if contains_refusal(text):
        return "HOLD / HUMAN_REVIEW_REQUIRED", ["final_decision_refusal"]

    upper = text.upper()

    if "NO_TRADE_DATA_UNAVAILABLE" in upper:
        return "NO_TRADE_DATA_UNAVAILABLE", flags

    if "HUMAN_REVIEW" in upper:
        return "HOLD / HUMAN_REVIEW_REQUIRED", flags

    for token in ["BUY", "SELL", "HOLD"]:
        if token in upper:
            return token, flags

    flags.append("decision_parse_failed")
    return "HOLD / HUMAN_REVIEW_REQUIRED", flags


@dataclass
class FinbotResult:
    ticker: str
    date: str
    decision: str
    markdown_report: str
    runtime_provider: str
    model_name: str
    duration_seconds: float
    status: str = "completed"
    retry_allowed: bool = False
    selected_analysts: Optional[list[str]] = None
    data_mode: str = "live"
    state: Optional[dict] = None
    quality_flags: list[str] = field(default_factory=list)
    error: Optional[str] = None
    error_class: Optional[str] = None


def _build_config(
    provider: str = "minimax",
    model: str = None,
    backend_url: str = None,
    output_language: str = "Chinese",
    max_recur_limit: int = 40,
    resolve_pending_returns: bool = False,
    data_mode: str = "live",
    risk_mode: str = "framework",
) -> dict:
    """Build TradingAgents config from environment / defaults."""

    sys.path.insert(0, str(Path(__file__).parent.parent / "TradingAgents"))
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()

    if provider == "minimax":
        config["llm_provider"] = "openai"
        config["deep_think_llm"] = model or "MiniMax-M2.7-highspeed"
        config["quick_think_llm"] = model or "MiniMax-M2.7-highspeed"
        config["backend_url"] = backend_url or (
            os.getenv("MINIMAX_API_HOST", "https://api.minimaxi.com").rstrip("/") + "/v1"
        )
        os.environ["OPENAI_API_KEY"] = os.getenv("MINIMAX_API_KEY", "")

    elif provider == "claudekimi":
        config["llm_provider"] = "openai"
        config["deep_think_llm"] = model or "mimo-v2.5-pro"
        config["quick_think_llm"] = model or "mimo-v2.5-pro"
        config["backend_url"] = backend_url or os.getenv(
            "CLAUDEKIMI_ENDPOINT",
            "http://127.0.0.1:8080/v1",
        )
        os.environ["OPENAI_API_KEY"] = os.getenv("CLAUDEKIMI_API_KEY", "")

    elif provider == "openai":
        config["llm_provider"] = "openai"
        config["deep_think_llm"] = model or "gpt-4.1"
        config["quick_think_llm"] = model or "gpt-4.1-mini"
        if backend_url:
            config["backend_url"] = backend_url

    else:
        raise ValueError(f"Unsupported Finbot provider: {provider}")

    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1

    # Don't let 429 retry loops burn tokens through 100 layers of recursion.
    config["max_recur_limit"] = max_recur_limit

    # During Yahoo 429 incidents, don't resolve pending returns at run start.
    config["resolve_pending_returns"] = resolve_pending_returns

    # For dataflow/tool layer to read.
    config["data_mode"] = data_mode

    config["checkpoint_enabled"] = False
    config["output_language"] = output_language
    config["risk_mode"] = risk_mode

    config["data_vendors"] = {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    }

    return config


def _unset_proxy():
    """Remove proxy env vars to prevent yfinance/network issues."""
    for var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        os.environ.pop(var, None)


def _render_state_markdown(state, decision: str) -> tuple[str, list[str]]:
    """Render the TradingAgents final state into a stable markdown report.

    Returns (markdown_text, quality_flags).
    """
    quality_flags: list[str] = []

    if not isinstance(state, dict):
        return str(decision), quality_flags

    sections = []

    ordered_keys = [
        ("market_report", "Market Analyst"),
        ("sentiment_report", "Sentiment / Social Analyst"),
        ("news_report", "News Analyst"),
        ("fundamentals_report", "Fundamentals Analyst"),
        ("investment_plan", "Investment Plan"),
        ("trader_investment_plan", "Trader Investment Plan"),
        ("final_trade_decision", "Final Trade Decision"),
    ]

    for key, title in ordered_keys:
        val = state.get(key)
        if isinstance(val, str) and val.strip():
            if has_think_block(val):
                quality_flags.append(f"chain_of_thought_leak_in_{key}")
            cleaned = strip_think_blocks(val)
            if cleaned:
                sections.append(f"## {title}\n\n{cleaned}")

    debate = state.get("investment_debate_state")
    if isinstance(debate, dict):
        for subkey in ["bull_history", "bear_history", "judge_decision"]:
            val = debate.get(subkey)
            if isinstance(val, str) and val.strip():
                if has_think_block(val):
                    quality_flags.append(f"chain_of_thought_leak_in_debate_{subkey}")
                cleaned = strip_think_blocks(val)
                if cleaned:
                    sections.append(f"## Investment Debate: {subkey}\n\n{cleaned}")

    risk = state.get("risk_debate_state")
    if isinstance(risk, dict):
        for subkey in [
            "aggressive_history",
            "conservative_history",
            "neutral_history",
            "judge_decision",
        ]:
            val = risk.get(subkey)
            if isinstance(val, str) and val.strip():
                if has_think_block(val):
                    quality_flags.append(f"chain_of_thought_leak_in_risk_{subkey}")
                if contains_refusal(val):
                    quality_flags.append(f"refusal_in_risk_{subkey}")
                cleaned = strip_think_blocks(val)
                if cleaned:
                    sections.append(f"## Risk Debate: {subkey}\n\n{cleaned}")

    sections.append(f"## Processed Decision\n\n{decision}")

    return "\n\n".join(sections), quality_flags


def run_tradingagents(
    ticker: str,
    date: str,
    provider: str = "minimax",
    model: str = None,
    backend_url: str = None,
    output_language: str = "Chinese",
    debug: bool = False,
    selected_analysts: Optional[list[str]] = None,
    max_recur_limit: int = 40,
    resolve_pending_returns: bool = False,
    data_mode: str = "live",
    risk_mode: str = "framework",
) -> FinbotResult:
    """Run the full TradingAgents pipeline for a ticker/date."""

    _unset_proxy()
    start_time = datetime.now()

    selected_analysts = selected_analysts or ["market"]

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "TradingAgents"))
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        config = _build_config(
            provider=provider,
            model=model,
            backend_url=backend_url,
            output_language=output_language,
            max_recur_limit=max_recur_limit,
            resolve_pending_returns=resolve_pending_returns,
            data_mode=data_mode,
            risk_mode=risk_mode,
        )

        if debug:
            print(f"[Finbot] Provider: {provider}, Model: {config['deep_think_llm']}")
            print(f"[Finbot] Backend: {config['backend_url']}")
            print(f"[Finbot] Analysts: {selected_analysts}")
            print(f"[Finbot] Data mode: {data_mode}")
            print(f"[Finbot] Running {ticker} for {date}...")

        ta = TradingAgentsGraph(
            selected_analysts=selected_analysts,
            debug=debug,
            config=config,
        )
        state, decision = ta.propagate(ticker, date)

        duration = (datetime.now() - start_time).total_seconds()

        markdown_report, render_flags = _render_state_markdown(state, decision)

        # Normalize the final decision through quality gates
        raw_final = state.get("final_trade_decision") if isinstance(state, dict) else str(decision)
        processed_decision, decision_flags = normalize_decision(raw_final)

        # Check for refusal in the raw decision text
        if contains_refusal(str(decision)):
            decision_flags.append("raw_decision_refusal")

        quality_flags = render_flags + decision_flags

        # Determine status based on quality flags
        status = "completed"
        if any("refusal" in f for f in quality_flags):
            status = "human_review_required"
        elif "decision_parse_failed" in quality_flags:
            status = "human_review_required"

        return FinbotResult(
            ticker=ticker,
            date=date,
            decision=processed_decision,
            markdown_report=markdown_report,
            runtime_provider=provider,
            model_name=config["deep_think_llm"],
            duration_seconds=duration,
            status=status,
            retry_allowed=False,
            selected_analysts=selected_analysts,
            data_mode=data_mode,
            state=state if isinstance(state, dict) else None,
            quality_flags=quality_flags,
        )

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        error_class = e.__class__.__name__
        err = str(e)

        # GraphRecursionError / tool loop should be terminal for this run.
        if "GraphRecursionError" in error_class or "recursion" in err.lower():
            return FinbotResult(
                ticker=ticker,
                date=date,
                decision="HOLD / HUMAN_REVIEW_REQUIRED",
                markdown_report=(
                    "## Terminal Runtime Guard\n\n"
                    "TradingAgents hit a graph recursion/tool retry limit. "
                    "This run is marked terminal and should not be retried automatically.\n\n"
                    "Decision: HOLD / HUMAN_REVIEW_REQUIRED"
                ),
                runtime_provider=provider,
                model_name=model or "unknown",
                duration_seconds=duration,
                status="human_review_required",
                retry_allowed=False,
                selected_analysts=selected_analysts,
                data_mode=data_mode,
                error=err,
                error_class=error_class,
            )

        return FinbotResult(
            ticker=ticker,
            date=date,
            decision="ERROR",
            markdown_report="",
            runtime_provider=provider,
            model_name=model or "unknown",
            duration_seconds=duration,
            status="error",
            retry_allowed=False,
            selected_analysts=selected_analysts,
            data_mode=data_mode,
            error=err,
            error_class=error_class,
        )


def save_result(result: FinbotResult, output_dir: str = None):
    """Save Finbot result to JSON + markdown files."""
    if output_dir is None:
        output_dir = os.path.expanduser("~/.paperclip/finbot_reports")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{result.ticker}_{result.date}_{timestamp}"

    # Save JSON
    json_path = output_dir / f"{base_name}.json"
    json_path.write_text(json.dumps({
        "ticker": result.ticker,
        "date": result.date,
        "decision": result.decision,
        "status": result.status,
        "retry_allowed": result.retry_allowed,
        "runtime_provider": result.runtime_provider,
        "model_name": result.model_name,
        "duration_seconds": result.duration_seconds,
        "selected_analysts": result.selected_analysts,
        "data_mode": result.data_mode,
        "quality_flags": result.quality_flags,
        "error": result.error,
        "error_class": result.error_class,
        "generated_at": datetime.now().isoformat(),
    }, indent=2, ensure_ascii=False))

    # Save markdown report
    md_path = output_dir / f"{base_name}.md"
    md_content = f"# Finbot Analysis: {result.ticker} ({result.date})\n\n"
    md_content += f"- Runtime: {result.runtime_provider} / {result.model_name}\n"
    md_content += f"- Duration: {result.duration_seconds:.1f}s\n"
    md_content += f"- Status: {result.status}\n"
    md_content += f"- Analysts: {', '.join(result.selected_analysts or [])}\n"
    md_content += f"- Data mode: {result.data_mode}\n"
    md_content += f"- Generated: {datetime.now().isoformat()}\n"
    if result.quality_flags:
        md_content += f"- Quality flags: {', '.join(result.quality_flags)}\n"
    md_content += f"\n## Decision\n\n{result.decision}\n\n"
    if result.markdown_report:
        md_content += f"## Full Report\n\n{result.markdown_report}\n"
    if result.error:
        md_content += f"\n## Error\n\n```\n{result.error}\n```\n"
    md_path.write_text(md_content)

    return str(json_path), str(md_path)


# ── CLI entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run TradingAgents via Paperclip adapter")
    parser.add_argument("ticker", help="Stock ticker symbol (e.g., AAPL)")
    parser.add_argument("--date", default="2026-05-01", help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--provider", default="minimax", choices=["minimax", "claudekimi", "openai"])
    parser.add_argument("--model", default=None, help="Override model name")
    parser.add_argument("--language", default="Chinese", help="Output language")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--save", action="store_true", help="Save result to files")
    parser.add_argument(
        "--analysts",
        default="market",
        help="Comma-separated analysts: market,news,social,fundamentals",
    )
    parser.add_argument("--max-recur-limit", type=int, default=40)
    parser.add_argument(
        "--data-mode",
        default="market_only",
        choices=["live", "market_only", "offline"],
    )
    args = parser.parse_args()

    selected_analysts = [x.strip() for x in args.analysts.split(",") if x.strip()]

    result = run_tradingagents(
        ticker=args.ticker,
        date=args.date,
        provider=args.provider,
        model=args.model,
        output_language=args.language,
        debug=args.debug,
        selected_analysts=selected_analysts,
        max_recur_limit=args.max_recur_limit,
        data_mode=args.data_mode,
    )

    if result.error:
        print(f"ERROR: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== FINBOT DECISION ({result.ticker} @ {result.date}) ===")
    print(result.decision)

    if args.save:
        json_path, md_path = save_result(result)
        print(f"\nSaved to:\n  {json_path}\n  {md_path}")
