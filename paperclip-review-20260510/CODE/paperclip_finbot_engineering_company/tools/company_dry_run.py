#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def build_manifest() -> dict:
    return {
        "company_name": "Paperclip Finbot Engineering Company",
        "mode": "dry_run",
        "apply": False,
        "root": str(ROOT),
        "agents": [
            "Engineering Lead / Product Owner / Risk Guard",
            "Kimi Implementation Lead",
            "Contract & Adapter Engineer",
            "QA / Replay / Evidence Engineer",
        ],
        "external_reviewers": ["Codex Architecture Reviewer"],
        "first_issues": [
            "FINBOT-ENG-000",
            "FINBOT-ENG-001",
            "FINBOT-ENG-002",
            "FINBOT-ENG-003",
            "FINBOT-ENG-004",
            "FINBOT-ENG-005",
        ],
        "paperclip_mutation": "disabled",
        "finbot_execution": "contract_only",
    }


def main() -> int:
    manifest = build_manifest()
    out = ROOT / "artifacts/dry_run/company_seed_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

