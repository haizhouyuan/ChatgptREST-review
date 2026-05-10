"""Validator for governance_memory_provider_policy_20260507.md.

Checks that the policy document covers all required gates and providers
defined in the production master plan.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "Policy Summary",
    "Current State",
    "Promotion Ladder",
    "Blocked",
    "Challenger",
    "Authority",
    "Promotion Gates",
    "Demotion Rules",
    "Provider Sequence",
    "Authority Review Workflow",
    "Compliance Audit Trail",
    "Non-Claims",
    "Next Actions",
]

REQUIRED_GATES = [
    "Clean-room no-write projection",
    "Read-path / verbatim adapter",
    "Privacy / export / provenance",
    "Ops / briefing sandbox",
    "Baseline comparison",
    "Blind fresh-agent recovery",
    "Quarantine / rollback",
]

REQUIRED_PROVIDERS = [
    "Graphiti",
    "MemPalace",
    "Supermemory",
    "GBrain",
]

POLICY_PATH = Path(__file__).with_name("governance_memory_provider_policy_20260507.md")


def validate() -> dict:
    if not POLICY_PATH.exists():
        return {"result": "fail", "reason": f"Policy document not found at {POLICY_PATH}"}

    text = POLICY_PATH.read_text(encoding="utf-8")
    errors: list[str] = []

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"Missing section: {section}")

    for gate in REQUIRED_GATES:
        if gate not in text:
            errors.append(f"Missing gate: {gate}")

    for provider in REQUIRED_PROVIDERS:
        if provider not in text:
            errors.append(f"Missing provider: {provider}")

    # Verify all providers are marked blocked
    for provider in REQUIRED_PROVIDERS:
        pattern = rf"\|\s*{re.escape(provider)}\s*\|\s*`blocked`"
        if not re.search(pattern, text):
            errors.append(f"Provider {provider} not explicitly marked `blocked` in table")

    # Verify authority-review workflow exists
    if "No unilateral promotion" not in text:
        errors.append("Missing unilateral-promotion guard clause")

    if errors:
        return {"result": "fail", "errors": errors}

    return {"result": "pass", "checks": len(REQUIRED_SECTIONS) + len(REQUIRED_GATES) + len(REQUIRED_PROVIDERS) + 1}


if __name__ == "__main__":
    result = validate()
    print(result["result"].upper())
    if result["result"] == "fail" and "errors" in result:
        for e in result["errors"]:
            print(f"  - {e}")
        sys.exit(1)
    print(f"Checks passed: {result['checks']}")
    sys.exit(0)
