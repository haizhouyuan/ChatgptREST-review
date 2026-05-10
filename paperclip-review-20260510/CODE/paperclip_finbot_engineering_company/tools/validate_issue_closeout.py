#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


REQUIRED = {
    "issue_id",
    "status",
    "changed_files",
    "artifact_manifest",
    "validation_result",
    "stdout_stderr",
    "diff_or_commit",
    "evidence_path",
}


def validate_closeout(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {"status": "blocked", "reason": "closeout_missing", "path": str(target)}
    data = json.loads(target.read_text(encoding="utf-8"))
    missing = sorted(REQUIRED - set(data))
    if missing:
        return {"status": "blocked", "reason": "missing_required_fields", "missing": missing}
    if data.get("status") not in {"closed", "pass"}:
        return {"status": "blocked", "reason": "status_not_closed", "actual": data.get("status")}
    if not data.get("changed_files") or not data.get("artifact_manifest"):
        return {"status": "blocked", "reason": "plan_only_closeout"}
    if data.get("validation_result", {}).get("status") != "pass":
        return {"status": "blocked", "reason": "validation_not_pass"}
    return {"status": "pass", "issue_id": data["issue_id"], "path": str(target)}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_issue_closeout.py CLOSEOUT_JSON", file=sys.stderr)
        return 2
    result = validate_closeout(argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

