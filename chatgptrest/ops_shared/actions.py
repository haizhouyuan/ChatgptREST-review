"""Action allowlisting, risk gating, and drain guard — shared with repair executor."""

from __future__ import annotations

import re


RISK_RANK = {"low": 0, "medium": 1, "high": 2}


def risk_allows(*, risk: str, max_risk: str) -> bool:
    r = str(risk or "").strip().lower() or "low"
    m = str(max_risk or "").strip().lower() or "low"
    if r not in RISK_RANK:
        r = "low"
    if m not in RISK_RANK:
        m = "low"
    return RISK_RANK[r] <= RISK_RANK[m]


def parse_allow_actions(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list):
        raw = ",".join([str(x or "") for x in value])
    else:
        raw = str(value)
    out: set[str] = set()
    for part in raw.split(","):
        name = re.sub(r"[^a-z0-9_]+", "", part.strip().lower())
        if name:
            out.add(name)
    return out
