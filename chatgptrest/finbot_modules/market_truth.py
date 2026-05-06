"""Market truth — fetch real-time market data and ticker inference.

Encapsulates the bridge between finbot and finagent's market data layer.
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ticker inference
# ---------------------------------------------------------------------------

def infer_market_from_ticker(ticker: str) -> str:
    """Best-effort inference of market from ticker format.

    Returns: "CN" | "HK" | "US" | "" (unknown)
    """
    t = ticker.strip().upper()
    # A-share: 6-digit with .SZ/.SH/.BJ suffix, or bare 6 digits starting with 0/3/6
    if re.match(r"^\d{6}\.(SZ|SH|BJ)$", t, re.IGNORECASE):
        return "CN"
    if re.match(r"^[036]\d{5}$", t):
        return "CN"
    # Hong Kong: digits with .HK suffix, or 4-5 digit code
    if re.match(r"^\d{1,5}\.HK$", t, re.IGNORECASE):
        return "HK"
    if re.match(r"^0\d{3,4}$", t):
        return "HK"
    # US: alphabetic ticker (2-5 letters)
    if re.match(r"^[A-Z]{1,5}$", t):
        return "US"
    return ""
