from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chatgptrest.kernel.skill_manager import get_canonical_registry


DEFAULT_TARGETS: dict[str, tuple[Path, ...]] = {
    "codex": (
        Path("/home/yuanhaizhou/.codex/skill-platform"),
        Path("/vol1/1000/home-yuanhaizhou/.codex-shared/skill-platform"),
        Path("/vol1/1000/home-yuanhaizhou/.home-codex-official/.codex/skill-platform"),
        Path("/vol1/1000/home-yuanhaizhou/.codex2/skill-platform"),
    ),
    "claude_code": (
        Path("/home/yuanhaizhou/.claude/skill-platform"),
        Path("/vol1/1000/home-yuanhaizhou/.home-codex-official/.claude/skill-platform"),
    ),
    "antigravity": (
        Path("/home/yuanhaizhou/.gemini/antigravity/skill-platform"),
        Path("/vol1/1000/home-yuanhaizhou/.home-codex-official/.antigravity/skill-platform"),
    ),
}

MANIFEST_NAME = "skill_platform_consumer_manifest_v1.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _override_var(platform: str) -> str:
    return f"CHATGPTREST_{platform.upper()}_SKILL_CONSUMER_TARGETS"


def resolve_target_dirs(platform: str) -> list[Path]:
    override = os.environ.get(_override_var(platform), "").strip()
    if override:
        return [Path(item).expanduser().resolve() for item in override.split(os.pathsep) if item.strip()]
    return [path.expanduser().resolve() for path in DEFAULT_TARGETS.get(platform, ())]


def build_consumer_manifest(*, platform: str, projection: dict[str, Any]) -> dict[str, Any]:
    payload_json = json.dumps(projection, ensure_ascii=False, indent=2)
    return {
        "platform": platform,
        "projection_file": f"{platform}_skill_projection_v1.json",
        "projection_sha256": _sha256(payload_json),
        "registry_id": projection.get("authority", {}).get("registry_id", ""),
        "registry_version": projection.get("authority", {}).get("registry_version", ""),
        "projection_mode": projection.get("adapter", {}).get("projection_mode", ""),
        "exported_at": _now_iso(),
        "skill_count": len(projection.get("skills") or []),
        "bundle_count": len(projection.get("bundles") or []),
    }


def sync_frontend_skill_platform_consumers(*, platforms: list[str] | None = None) -> list[dict[str, Any]]:
    registry = get_canonical_registry()
    selected = platforms or ["codex", "claude_code", "antigravity"]
    results: list[dict[str, Any]] = []
    for platform in selected:
        projection = registry.projection_for_platform(platform)
        projection_json = json.dumps(projection, ensure_ascii=False, indent=2)
        manifest = build_consumer_manifest(platform=platform, projection=projection)
        targets = resolve_target_dirs(platform)
        for target_dir in targets:
            target_dir.mkdir(parents=True, exist_ok=True)
            projection_path = target_dir / f"{platform}_skill_projection_v1.json"
            manifest_path = target_dir / MANIFEST_NAME
            projection_path.write_text(projection_json, encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append(
                {
                    "platform": platform,
                    "target_dir": str(target_dir),
                    "projection_path": str(projection_path),
                    "manifest_path": str(manifest_path),
                    "projection_sha256": manifest["projection_sha256"],
                }
            )
    return results


def inspect_frontend_skill_platform_consumers(*, platforms: list[str] | None = None) -> list[dict[str, Any]]:
    registry = get_canonical_registry()
    selected = platforms or ["codex", "claude_code", "antigravity"]
    rows: list[dict[str, Any]] = []
    for platform in selected:
        projection = registry.projection_for_platform(platform)
        expected_sha = _sha256(json.dumps(projection, ensure_ascii=False, indent=2))
        for target_dir in resolve_target_dirs(platform):
            projection_path = target_dir / f"{platform}_skill_projection_v1.json"
            manifest_path = target_dir / MANIFEST_NAME
            exists = projection_path.exists() and manifest_path.exists()
            actual_sha = ""
            if projection_path.exists():
                actual_sha = _sha256(projection_path.read_text(encoding="utf-8"))
            status = "missing"
            if exists and actual_sha == expected_sha:
                status = "ok"
            elif exists:
                status = "stale"
            rows.append(
                {
                    "platform": platform,
                    "target_dir": str(target_dir),
                    "exists": exists,
                    "status": status,
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "projection_path": str(projection_path),
                    "manifest_path": str(manifest_path),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync or inspect runtime consumer projections for Codex/Claude/Antigravity.")
    sub = parser.add_subparsers(dest="command", required=True)

    sync_cmd = sub.add_parser("sync", help="Write latest platform projections into frontend runtime directories.")
    sync_cmd.add_argument("--platform", action="append", dest="platforms", default=[])

    status_cmd = sub.add_parser("status", help="Inspect runtime consumer projection status.")
    status_cmd.add_argument("--platform", action="append", dest="platforms", default=[])

    args = parser.parse_args()
    if args.command == "sync":
        payload = {"written": sync_frontend_skill_platform_consumers(platforms=args.platforms or None)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    payload = {"consumers": inspect_frontend_skill_platform_consumers(platforms=args.platforms or None)}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
