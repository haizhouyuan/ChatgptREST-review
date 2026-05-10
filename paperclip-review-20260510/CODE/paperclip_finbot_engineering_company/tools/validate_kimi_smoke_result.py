#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


def validate(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {"status": "blocked", "reason": "smoke_result_missing", "path": str(target)}
    data = json.loads(target.read_text(encoding="utf-8"))
    required = {
        "issue_id": "FINBOT-ENG-002",
        "status": "pass",
        "runtime": "kimicode",
        "mcp_profile": "none",
        "created_by_native_kimi": True,
        "finbot_execution": False,
        "paperclip_apply": False,
    }
    mismatches = {key: {"expected": value, "actual": data.get(key)} for key, value in required.items() if data.get(key) != value}
    if mismatches:
        return {"status": "blocked", "reason": "field_mismatch", "mismatches": mismatches}
    return {"status": "pass", "path": str(target)}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_kimi_smoke_result.py KIMI_SMOKE_RESULT.json", file=sys.stderr)
        return 2
    result = validate(argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

