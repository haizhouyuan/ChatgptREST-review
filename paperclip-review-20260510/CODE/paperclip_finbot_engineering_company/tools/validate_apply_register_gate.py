#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def validate_gate(root: Path = ROOT) -> dict:
    gate = json.loads((root / "contracts/APPLY_REGISTER_GATE.json").read_text(encoding="utf-8"))
    smoke = root / "artifacts/kimi_smoke/KIMI_SMOKE_RESULT.json"
    blockers = list(gate.get("current_blockers", []))
    if smoke.exists():
        data = json.loads(smoke.read_text(encoding="utf-8"))
        if data.get("status") == "pass":
            blockers = [item for item in blockers if item not in {"KIMI_SMOKE_BLOCKED", "NO_KIMI_SMOKE_RESULT"}]
    allowed = gate.get("apply_allowed") is True and gate.get("register_allowed") is True and not blockers
    return {
        "status": "pass" if allowed else "blocked",
        "apply_allowed": bool(allowed),
        "register_allowed": bool(allowed),
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--expect", choices=["pass", "blocked"], default="blocked")
    args = parser.parse_args()
    result = validate_gate(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == args.expect else 1


if __name__ == "__main__":
    raise SystemExit(main())

