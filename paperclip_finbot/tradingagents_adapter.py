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
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class FinbotResult:
    ticker: str
    date: str
    decision: str
    markdown_report: str
    runtime_provider: str
    model_name: str
    duration_seconds: float
    error: Optional[str] = None


def _build_config(
    provider: str = "minimax",
    model: str = None,
    backend_url: str = None,
    output_language: str = "Chinese",
) -> dict:
    """Build TradingAgents config from environment / defaults."""

    # Import here to avoid import errors when TradingAgents is not installed
    sys.path.insert(0, str(Path(__file__).parent.parent / "TradingAgents"))
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()

    if provider == "minimax":
        config["llm_provider"] = "openai"
        config["deep_think_llm"] = model or "MiniMax-M2.7-highspeed"
        config["quick_think_llm"] = model or "MiniMax-M2.7-highspeed"
        config["backend_url"] = backend_url or (
            os.getenv("MINIMAX_API_HOST", "https://api.minimaxi.com") + "/v1"
        )
        os.environ["OPENAI_API_KEY"] = os.getenv("MINIMAX_API_KEY", "")
    elif provider == "claudekimi":
        config["llm_provider"] = "openai"
        config["deep_think_llm"] = model or "mimo-v2.5-pro"
        config["quick_think_llm"] = model or "mimo-v2.5-pro"
        config["backend_url"] = backend_url or os.getenv("CLAUDEKIMI_ENDPOINT", "http://127.0.0.1:8080/v1")
        os.environ["OPENAI_API_KEY"] = os.getenv("CLAUDEKIMI_API_KEY", "")
    elif provider == "openai":
        config["llm_provider"] = "openai"
        config["deep_think_llm"] = model or "gpt-4.1"
        config["quick_think_llm"] = model or "gpt-4.1-mini"
        if backend_url:
            config["backend_url"] = backend_url

    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["checkpoint_enabled"] = False
    config["output_language"] = output_language
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


def run_tradingagents(
    ticker: str,
    date: str,
    provider: str = "minimax",
    model: str = None,
    backend_url: str = None,
    output_language: str = "Chinese",
    debug: bool = False,
) -> FinbotResult:
    """Run the full TradingAgents pipeline for a ticker/date."""

    _unset_proxy()
    start_time = datetime.now()

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "TradingAgents"))
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        config = _build_config(provider, model, backend_url, output_language)

        if debug:
            print(f"[Finbot] Provider: {provider}, Model: {config['deep_think_llm']}")
            print(f"[Finbot] Backend: {config['backend_url']}")
            print(f"[Finbot] Running {ticker} for {date}...")

        ta = TradingAgentsGraph(debug=debug, config=config)
        state, decision = ta.propagate(ticker, date)

        duration = (datetime.now() - start_time).total_seconds()

        # Extract markdown report from state if available
        markdown_report = ""
        if isinstance(state, dict):
            # Try to get the final report from various state keys
            for key in ["portfolio_manager_report", "trader_report", "risk_debate_state"]:
                if key in state and state[key]:
                    val = state[key]
                    if isinstance(val, str):
                        markdown_report += f"## {key}\n{val}\n\n"
                    elif isinstance(val, dict):
                        for subkey, subval in val.items():
                            if isinstance(subval, str) and subval:
                                markdown_report += f"## {key}.{subkey}\n{subval}\n\n"

        return FinbotResult(
            ticker=ticker,
            date=date,
            decision=str(decision),
            markdown_report=markdown_report or str(decision),
            runtime_provider=provider,
            model_name=config["deep_think_llm"],
            duration_seconds=duration,
        )

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        return FinbotResult(
            ticker=ticker,
            date=date,
            decision="ERROR",
            markdown_report="",
            runtime_provider=provider,
            model_name=model or "unknown",
            duration_seconds=duration,
            error=str(e),
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
        "runtime_provider": result.runtime_provider,
        "model_name": result.model_name,
        "duration_seconds": result.duration_seconds,
        "error": result.error,
        "generated_at": datetime.now().isoformat(),
    }, indent=2, ensure_ascii=False))

    # Save markdown report
    md_path = output_dir / f"{base_name}.md"
    md_content = f"# Finbot Analysis: {result.ticker} ({result.date})\n\n"
    md_content += f"- Runtime: {result.runtime_provider} / {result.model_name}\n"
    md_content += f"- Duration: {result.duration_seconds:.1f}s\n"
    md_content += f"- Generated: {datetime.now().isoformat()}\n\n"
    md_content += f"## Decision\n\n{result.decision}\n\n"
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
    args = parser.parse_args()

    result = run_tradingagents(
        ticker=args.ticker,
        date=args.date,
        provider=args.provider,
        model=args.model,
        output_language=args.language,
        debug=args.debug,
    )

    if result.error:
        print(f"ERROR: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== FINBOT DECISION ({result.ticker} @ {result.date}) ===")
    print(result.decision)

    if args.save:
        json_path, md_path = save_result(result)
        print(f"\nSaved to:\n  {json_path}\n  {md_path}")
