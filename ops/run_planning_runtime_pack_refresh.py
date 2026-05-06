#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.evomap.knowledge.planning_review_plane import default_db_path
from chatgptrest.evomap.knowledge.planning_runtime_pack_search import planning_runtime_pack_bundle_status
from ops.audit_planning_runtime_pack_sensitivity import audit_pack
from ops.build_planning_runtime_pack_observability_samples import build_samples
from ops.build_planning_runtime_pack_release_bundle import (
    DEFAULT_OBSERVABILITY_ROOT,
    DEFAULT_SENSITIVITY_ROOT,
    DEFAULT_VALIDATION_ROOT,
    build_release_bundle,
)
from ops.export_planning_reviewed_runtime_pack import DEFAULT_OUTPUT_ROOT, export_runtime_pack
from ops.report_planning_review_state import DEFAULT_REFRESH_ROOT
from ops.run_planning_runtime_pack_offline_validation import run_validation

DEFAULT_RELEASE_BUNDLE_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_runtime_pack_release_bundle"


def _latest_allowlist(refresh_root: Path) -> Path | None:
    if not refresh_root.exists():
        return None
    candidates: list[Path] = []
    for snapshot_dir in refresh_root.iterdir():
        if not snapshot_dir.is_dir():
            continue
        candidates.extend(snapshot_dir.glob("planning_review_decisions_v*_allowlist.tsv"))
        candidates.extend(snapshot_dir.glob("planning_review_decisions_allowlist.tsv"))
    candidates.sort(key=lambda path: str(path))
    return candidates[-1] if candidates else None


def _latest_bundle(output_root: Path) -> Path | None:
    if not output_root.exists():
        return None
    candidates = [path for path in output_root.iterdir() if path.is_dir()]
    candidates.sort(key=lambda path: path.name)
    return candidates[-1] if candidates else None


def _load_manifest(bundle_dir: Path | None) -> dict[str, Any] | None:
    if bundle_dir is None:
        return None
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def refresh_runtime_pack(
    *,
    db_path: str | Path,
    refresh_root: Path,
    output_root: Path,
    validation_root: Path,
    sensitivity_root: Path,
    observability_root: Path,
    release_bundle_root: Path,
    require_consistent: bool,
) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    before_pack = _latest_bundle(output_root)
    before_manifest = _load_manifest(before_pack)
    before_ready_bundle = planning_runtime_pack_bundle_status()
    allowlist = _latest_allowlist(refresh_root)
    if allowlist is None or not allowlist.exists():
        raise RuntimeError(f"No allowlist found under {refresh_root}")

    pack_dir = output_root / stamp
    export_result = export_runtime_pack(
        db_path=db_path,
        allowlist_path=allowlist,
        output_dir=pack_dir,
        require_consistent=require_consistent,
    )
    pack_manifest_path = Path(str(export_result["manifest_path"]))
    pack_manifest = _load_json(pack_manifest_path)

    validation_dir = validation_root / stamp
    validation_result = run_validation(
        pack_dir=pack_dir,
        output_dir=validation_dir,
    )
    validation_summary = _load_json(validation_dir / "summary.json")

    sensitivity_dir = sensitivity_root / stamp
    sensitivity_result = audit_pack(
        pack_dir=pack_dir,
        output_dir=sensitivity_dir,
    )
    sensitivity_summary = _load_json(sensitivity_dir / "summary.json")

    observability_dir = observability_root / stamp
    observability_result = build_samples(
        pack_dir=pack_dir,
        output_dir=observability_dir,
    )

    release_bundle_dir = release_bundle_root / stamp
    release_result = build_release_bundle(
        pack_dir=pack_dir,
        validation_dir=validation_dir,
        sensitivity_dir=sensitivity_dir,
        observability_dir=observability_dir,
        output_dir=release_bundle_dir,
    )
    release_manifest = _load_json(release_bundle_dir / "release_bundle_manifest.json")
    ready_bundle_status = planning_runtime_pack_bundle_status()

    after_counts = dict(pack_manifest.get("counts", {}))
    before_counts = dict((before_manifest or {}).get("counts", {}))

    payload = {
        "ok": bool(pack_manifest.get("ok", False)) and bool(validation_result.get("ok", False)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "allowlist_path": str(allowlist),
        "pack_dir": str(pack_dir),
        "release_bundle_dir": str(release_bundle_dir),
        "before_pack": str(before_pack) if before_pack else "",
        "before_ready_bundle": str(before_ready_bundle.get("bundle_dir") or ""),
        "after_ready_bundle": str(ready_bundle_status.get("bundle_dir") or ""),
        "before_counts": before_counts,
        "after_counts": after_counts,
        "delta": {
            "exported_docs": int(after_counts.get("exported_docs", 0)) - int(before_counts.get("exported_docs", 0)),
            "exported_atoms": int(after_counts.get("exported_atoms", 0)) - int(before_counts.get("exported_atoms", 0)),
        },
        "growth_note": (
            "pack grew after post-promotion refresh"
            if int(after_counts.get("exported_atoms", 0)) > int(before_counts.get("exported_atoms", 0))
            else "pack freshness advanced; breadth remained constrained by current reviewed allowlist"
        ),
        "pack_manifest_path": str(pack_manifest_path),
        "pack_manifest": pack_manifest,
        "validation_dir": str(validation_dir),
        "validation_summary": validation_summary,
        "sensitivity_dir": str(sensitivity_dir),
        "sensitivity_summary": sensitivity_summary,
        "observability_dir": str(observability_dir),
        "observability_result": observability_result,
        "release_bundle_manifest_path": str(release_bundle_dir / "release_bundle_manifest.json"),
        "release_bundle_manifest": release_manifest,
        "release_result": release_result,
        "ready_bundle_status": ready_bundle_status,
        "ready_bundle_advanced": str(ready_bundle_status.get("bundle_dir") or "") == str(release_bundle_dir),
    }
    _write_json(pack_dir / "refresh_summary.json", payload)
    (pack_dir / "README.md").write_text(
        "\n".join(
            [
                "# Planning Runtime Pack Refresh",
                "",
                f"- `allowlist_path`: `{allowlist}`",
                f"- `before_pack`: `{before_pack or 'none'}`",
                f"- `pack_dir`: `{pack_dir}`",
                f"- `release_bundle_dir`: `{release_bundle_dir}`",
                f"- `before_ready_bundle`: `{before_ready_bundle.get('bundle_dir') or 'none'}`",
                f"- `after_ready_bundle`: `{ready_bundle_status.get('bundle_dir') or 'none'}`",
                f"- `delta.exported_docs`: `{payload['delta']['exported_docs']}`",
                f"- `delta.exported_atoms`: `{payload['delta']['exported_atoms']}`",
                f"- `validation.ok`: `{validation_summary.get('ok')}`",
                f"- `sensitivity.ok`: `{sensitivity_summary.get('ok')}`",
                f"- `release_bundle.ready_for_explicit_consumption`: `{release_manifest.get('ready_for_explicit_consumption')}`",
                f"- `ready_bundle_advanced`: `{payload['ready_bundle_advanced']}`",
                f"- `growth_note`: `{payload['growth_note']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the reviewed planning runtime pack and record freshness/growth evidence.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--refresh-root", default=str(DEFAULT_REFRESH_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--validation-root", default=str(DEFAULT_VALIDATION_ROOT))
    parser.add_argument("--sensitivity-root", default=str(DEFAULT_SENSITIVITY_ROOT))
    parser.add_argument("--observability-root", default=str(DEFAULT_OBSERVABILITY_ROOT))
    parser.add_argument("--release-bundle-root", default=str(DEFAULT_RELEASE_BUNDLE_ROOT))
    parser.add_argument("--no-require-consistent", action="store_true")
    args = parser.parse_args()
    payload = refresh_runtime_pack(
        db_path=args.db,
        refresh_root=Path(args.refresh_root),
        output_root=Path(args.output_root),
        validation_root=Path(args.validation_root),
        sensitivity_root=Path(args.sensitivity_root),
        observability_root=Path(args.observability_root),
        release_bundle_root=Path(args.release_bundle_root),
        require_consistent=not args.no_require_consistent,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
