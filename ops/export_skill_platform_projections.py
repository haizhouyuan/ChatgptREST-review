from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgptrest.kernel.skill_manager import get_canonical_registry


def export_skill_platform_projections(
    *,
    out_dir: str | Path,
    platforms: list[str] | None = None,
) -> list[Path]:
    registry = get_canonical_registry()
    output_root = Path(out_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    selected = platforms or sorted(registry.platform_adapters.keys())
    written: list[Path] = []
    for platform in selected:
        payload = registry.projection_for_platform(platform)
        target = output_root / f"{platform}_skill_projection_v1.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Export canonical skill-platform projections for frontend adapters.")
    parser.add_argument("--out-dir", required=True, help="Directory to write per-platform JSON projections into.")
    parser.add_argument(
        "--platform",
        action="append",
        dest="platforms",
        default=[],
        help="Optional platform to export. Repeatable; defaults to all registered platforms.",
    )
    args = parser.parse_args()
    written = export_skill_platform_projections(out_dir=args.out_dir, platforms=args.platforms or None)
    print(json.dumps({"written": [str(path) for path in written]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
