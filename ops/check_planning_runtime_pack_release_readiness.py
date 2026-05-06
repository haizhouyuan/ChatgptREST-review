#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_reviewed_runtime_pack"
REQUIRED_FILES = ["manifest.json", "docs.tsv", "atoms.tsv", "retrieval_pack.json", "smoke_manifest.json", "README.md"]


def _latest_pack(pack_root: Path) -> Path | None:
    if not pack_root.exists():
        return None
    candidates = sorted([p for p in pack_root.iterdir() if p.is_dir()])
    return candidates[-1] if candidates else None


def check_release_readiness(*, pack_dir: str | Path, max_age_hours: int = 72) -> dict[str, Any]:
    pack = Path(pack_dir)
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    missing_files = [name for name in REQUIRED_FILES if not (pack / name).exists()]
    generated_at = datetime.fromisoformat(manifest["generated_at"])
    age_hours = (datetime.now(timezone.utc) - generated_at).total_seconds() / 3600.0
    checks = {
        "required_files_ok": len(missing_files) == 0,
        "manifest_ok": bool(manifest.get("ok", False)),
        "opt_in_only_ok": bool(manifest["scope"].get("opt_in_only", False)),
        "default_runtime_cutover_disabled_ok": manifest["scope"].get("default_runtime_cutover", True) is False,
        "freshness_ok": age_hours <= float(max_age_hours),
    }
    return {
        "pack_dir": str(pack),
        "max_age_hours": max_age_hours,
        "age_hours": age_hours,
        "missing_files": missing_files,
        "checks": checks,
        "ready": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a planning reviewed runtime pack is release-ready for explicit opt-in use.")
    parser.add_argument("--pack-dir", default="")
    parser.add_argument("--pack-root", default=str(DEFAULT_PACK_ROOT))
    parser.add_argument("--max-age-hours", type=int, default=72)
    args = parser.parse_args()
    pack_dir = Path(args.pack_dir) if args.pack_dir else _latest_pack(Path(args.pack_root))
    if pack_dir is None or not pack_dir.exists():
        raise SystemExit("No planning reviewed runtime pack found. Pass --pack-dir explicitly.")
    print(json.dumps(check_release_readiness(pack_dir=pack_dir, max_age_hours=args.max_age_hours), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
