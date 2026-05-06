"""Earnings call transcript provider module.

Provides earnings call transcript fetching with graceful fallback when
provider/API key is unavailable.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from chatgptrest.finbot_modules._helpers import text_value

log = logging.getLogger(__name__)


# Known transcript providers
PROVIDER_ALPHA_VANTAGE = "alpha_vantage"
PROVIDER_FMP = "fmp"
PROVIDER_DISABLED = "disabled"


def _check_available_providers() -> list[str]:
    """Check which transcript providers are available in environment.

    Returns list of available provider names.
    """
    available = []

    if os.environ.get("ALPHA_VANTAGE_API_KEY"):
        available.append(PROVIDER_ALPHA_VANTAGE)

    if os.environ.get("FMP_API_KEY"):
        available.append(PROVIDER_FMP)

    return available


def _fetch_transcript_from_provider(
    provider: str,
    symbol: str,
) -> dict[str, Any]:
    """Fetch transcript from specified provider.

    Args:
        provider: Provider name (alpha_vantage, fmp)
        symbol: Stock ticker symbol

    Returns:
        Transcript data dict or empty result
    """
    if provider == PROVIDER_ALPHA_VANTAGE:
        # Alpha Vantage has earnings calendar but not full transcripts
        # Would need a dedicated transcript service for production
        log.info(f"Alpha Vantage selected for {symbol} - full transcript not available via this provider")
        return {"available": False, "items": []}

    if provider == PROVIDER_FMP:
        # FMP has earnings call transcripts via separate endpoint
        # For now, log that it would be called
        log.info(f"FMP selected for {symbol} - earnings transcript API would be called here")
        return {"available": False, "items": []}

    return {"available": False, "items": []}


def fetch_earnings_transcript(
    symbol: str,
) -> dict[str, Any]:
    """Fetch earnings call transcript with graceful fallback.

    Tries available providers in order, falls back to disabled state
    if no provider is available.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Transcript packet dict with schema:
        {
            "generated_at": float,
            "candidate_id": str,
            "provider": "alpha_vantage|fmp|disabled",
            "available": bool,
            "disabled_reason": str,
            "items": [
                {
                    "source_id": str,
                    "speaker": str,
                    "section": "prepared|qa",
                    "excerpt": str,
                    "stance": "support|weaken|context"
                }
            ]
        }
    """
    ts = time.time()
    available_providers = _check_available_providers()

    # Try each available provider
    for provider in available_providers:
        try:
            result = _fetch_transcript_from_provider(provider, symbol)
            if result.get("available") and result.get("items"):
                return {
                    "generated_at": ts,
                    "candidate_id": symbol,
                    "provider": provider,
                    "available": True,
                    "disabled_reason": "",
                    "items": result.get("items", []),
                }
        except Exception as e:
            log.warning(f"Provider {provider} failed for {symbol}: {e}")
            continue

    # No provider available or all failed - return graceful disabled result
    disabled_reason = ""
    if not available_providers:
        disabled_reason = "No transcript provider API keys configured (ALPHA_VANTAGE_API_KEY, FMP_API_KEY)"
    else:
        disabled_reason = f"Providers {available_providers} available but no transcript data returned"

    log.info(f"Transcript fetch disabled for {symbol}: {disabled_reason}")

    return {
        "generated_at": ts,
        "candidate_id": symbol,
        "provider": PROVIDER_DISABLED,
        "available": False,
        "disabled_reason": disabled_reason,
        "items": [],
    }


def build_transcript_packet(
    *,
    candidate_id: str,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Build transcript packet artifact.

    Args:
        candidate_id: The opportunity/candidate identifier
        symbol: Optional ticker symbol (defaults to candidate_id if looks like ticker)

    Returns:
        Complete transcript packet with provider info and any available excerpts
    """
    # Use candidate_id as symbol if it looks like a ticker
    if not symbol:
        symbol = candidate_id

    # Fetch transcript (with graceful fallback)
    transcript_data = fetch_earnings_transcript(symbol)

    return {
        "generated_at": transcript_data.get("generated_at"),
        "candidate_id": candidate_id,
        "provider": transcript_data.get("provider", PROVIDER_DISABLED),
        "available": transcript_data.get("available", False),
        "disabled_reason": transcript_data.get("disabled_reason", ""),
        "items": transcript_data.get("items", []),
    }
