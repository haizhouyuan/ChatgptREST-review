#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def load_policy() -> dict:
    return json.loads((ROOT / "contracts/WRITE_SCOPE_POLICY.json").read_text(encoding="utf-8"))


def validate_path(path: str | Path, policy: dict | None = None) -> dict:
    policy = policy or load_policy()
    candidate = Path(path)
    raw = str(candidate)
    if raw.startswith("..") or "/../" in raw:
        return {"status": "blocked", "reason": "relative_escape", "path": raw}
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve(strict=False)
    allowed = [Path(item).resolve(strict=False) for item in policy["allowed_write_roots"]]
    forbidden = [Path(item).resolve(strict=False) for item in policy["forbidden_write_roots"]]
    if not any(resolved == root or root in resolved.parents for root in allowed):
        return {"status": "blocked", "reason": "outside_allowed_write_roots", "path": str(resolved)}
    if any(resolved == root or root in resolved.parents for root in forbidden):
        return {"status": "blocked", "reason": "forbidden_write_root", "path": str(resolved)}
    if candidate.exists() and candidate.is_symlink():
        target = candidate.resolve(strict=True)
        if not any(target == root or root in target.parents for root in allowed):
            return {"status": "blocked", "reason": "symlink_escape", "path": str(candidate), "target": str(target)}
    return {"status": "pass", "path": str(resolved)}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_write_scope.py PATH", file=sys.stderr)
        return 2
    result = validate_path(argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
