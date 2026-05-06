#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.evomap.knowledge.planning_review_plane import (
    DEFAULT_LINEAGE_DIR,
    DEFAULT_PACKAGE_DIR,
    default_db_path,
    import_review_plane,
    merge_review_outputs,
    apply_bootstrap_allowlist,
)
from chatgptrest.evomap.knowledge.planning_review_refresh import DEFAULT_BASELINE_ROOT, run_refresh
from ops.compose_planning_review_decisions import compose


REVIEWER_NAMES = ("gemini_no_mcp", "claudeminmax", "codex_auth_only")


def _decision_file(snapshot_dir: Path) -> Path | None:
    for name in (
        "planning_review_decisions_v9.tsv",
        "planning_review_decisions_v8.tsv",
        "planning_review_decisions_v7.tsv",
        "planning_review_decisions_v6.tsv",
        "planning_review_decisions_v5.tsv",
        "planning_review_decisions_v4.tsv",
        "planning_review_decisions_v3.tsv",
        "planning_review_decisions_v2.tsv",
        "planning_review_decisions.tsv",
    ):
        path = snapshot_dir / name
        if path.exists():
            return path
    return None


def _latest_decision_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir() and _decision_file(path)]
    candidates.sort(key=lambda path: path.name)
    return candidates[-1] if candidates else None


def _next_versioned_decision_name(base_path: Path) -> str:
    match = re.search(r"_v(\d+)\.tsv$", base_path.name)
    if not match:
        return "planning_review_decisions_v1.tsv"
    return re.sub(r"_v\d+\.tsv$", f"_v{int(match.group(1)) + 1}.tsv", base_path.name)


def _copy_db_if_requested(source_db: Path, copy_to: Path | None) -> Path:
    if copy_to is None:
        return source_db
    copy_to.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_db, copy_to)
    return copy_to


def _build_reviewer_manifest(snapshot_dir: Path, pack_path: Path) -> dict[str, Any]:
    review_root = snapshot_dir / "review_runs_cycle"
    review_root.mkdir(parents=True, exist_ok=True)
    reviewers: list[dict[str, str]] = []
    for name in REVIEWER_NAMES:
        output_path = review_root / f"{name}.json"
        reviewers.append(
            {
                "reviewer": name,
                "output_path": str(output_path),
                "instruction": (
                    f"Review pack {pack_path} and write JSON to {output_path}. "
                    "Return only review items for docs in the pack."
                ),
            }
        )
    manifest = {
        "pack_path": str(pack_path),
        "review_output_dir": str(review_root),
        "reviewers": reviewers,
    }
    manifest_path = review_root / "reviewer_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"manifest_path": str(manifest_path), "review_output_dir": str(review_root), "reviewers": reviewers}


def run_cycle(
    *,
    db_path: str | Path,
    package_dir: Path,
    lineage_dir: Path,
    baseline_root: Path,
    output_root: Path,
    review_json_paths: list[Path],
    base_decisions_path: Path | None,
    apply_db_copy_to: Path | None,
    apply_live: bool,
    min_atom_quality: float,
    groundedness_threshold: float,
) -> dict[str, Any]:
    refresh_payload = run_refresh(
        db_path=db_path,
        package_dir=package_dir,
        lineage_dir=lineage_dir,
        baseline_root=baseline_root,
        output_root=output_root,
    )
    snapshot_dir = Path(refresh_payload["summary"]["current_snapshot_dir"])
    pack_path = Path(refresh_payload["pack_path"]) if refresh_payload.get("pack_path") else None
    reviewer_manifest: dict[str, Any] | None = None
    if pack_path and pack_path.exists():
        reviewer_manifest = _build_reviewer_manifest(snapshot_dir, pack_path)

    payload: dict[str, Any] = {
        "ok": True,
        "mode": "refresh_only",
        "refresh": refresh_payload,
        "reviewer_manifest": reviewer_manifest or {},
    }

    if not review_json_paths:
        cycle_summary_path = snapshot_dir / "cycle_summary.json"
        cycle_summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        payload["cycle_summary_path"] = str(cycle_summary_path)
        return payload

    missing = [str(path) for path in review_json_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing review outputs: {missing}")

    delta_output = snapshot_dir / "refresh" / "planning_review_decisions_delta_v1.tsv"
    delta_summary = merge_review_outputs(
        snapshot_dir=snapshot_dir,
        review_json_paths=review_json_paths,
        output_path=delta_output,
    )

    if base_decisions_path is None:
        decision_source_dir_raw = str(refresh_payload["summary"].get("decision_source_dir") or "").strip()
        decision_source_dir = Path(decision_source_dir_raw) if decision_source_dir_raw else _latest_decision_dir(baseline_root)
        if decision_source_dir is None:
            raise FileNotFoundError("No baseline decision source dir was found for overlay.")
        base_decisions_path = _decision_file(decision_source_dir)
    if not base_decisions_path or not base_decisions_path.exists():
        raise FileNotFoundError(f"Baseline decisions not found: {base_decisions_path}")

    full_output = snapshot_dir / _next_versioned_decision_name(base_decisions_path)
    compose_summary = compose(base_decisions_path, delta_output, full_output)

    apply_summary: dict[str, Any] | None = None
    mode = "refresh_merge_only"
    if apply_db_copy_to is not None or apply_live:
        target_db = _copy_db_if_requested(Path(db_path), apply_db_copy_to)
        bootstrap_output_dir = snapshot_dir / ("live_apply_cycle" if apply_live else "validation_apply_cycle") / "bootstrap_active"
        import_summary = import_review_plane(
            db_path=target_db,
            snapshot_dir=snapshot_dir,
            review_decisions_path=full_output,
        )
        bootstrap_summary = apply_bootstrap_allowlist(
            db_path=target_db,
            allowlist_path=full_output.with_name(full_output.stem + "_allowlist.tsv"),
            output_dir=bootstrap_output_dir,
            min_atom_quality=min_atom_quality,
            groundedness_threshold=groundedness_threshold,
        )
        apply_summary = {
            "target_db": str(target_db),
            "import_summary": import_summary,
            "bootstrap_summary": bootstrap_summary,
            "mode": "live" if apply_live else "copy",
        }
        mode = "refresh_merge_apply_live" if apply_live else "refresh_merge_apply_copy"

    payload.update(
        {
            "mode": mode,
            "delta_output": str(delta_output),
            "delta_summary": delta_summary,
            "base_decisions_path": str(base_decisions_path),
            "full_output": str(full_output),
            "compose_summary": compose_summary,
            "apply_summary": apply_summary or {},
        }
    )
    cycle_summary_path = snapshot_dir / "cycle_summary.json"
    cycle_summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["cycle_summary_path"] = str(cycle_summary_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one planning review refresh/merge/apply maintenance cycle.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR))
    parser.add_argument("--lineage-dir", default=str(DEFAULT_LINEAGE_DIR))
    parser.add_argument("--baseline-root", default=str(DEFAULT_BASELINE_ROOT))
    parser.add_argument("--output-root", default="artifacts/monitor/planning_review_plane_refresh")
    parser.add_argument("--review-json", action="append", default=[], help="Reviewer JSON outputs. Repeat for multiple files.")
    parser.add_argument("--base-decisions", default="", help="Optional full baseline decision TSV to overlay against.")
    parser.add_argument("--apply-db-copy", default="", help="Optional temp DB copy path to validate import/bootstrap.")
    parser.add_argument("--apply-live", action="store_true", help="Apply directly to --db instead of a temp copy.")
    parser.add_argument("--min-atom-quality", type=float, default=0.58)
    parser.add_argument("--groundedness-threshold", type=float, default=0.6)
    args = parser.parse_args()

    payload = run_cycle(
        db_path=args.db,
        package_dir=Path(args.package_dir),
        lineage_dir=Path(args.lineage_dir),
        baseline_root=Path(args.baseline_root),
        output_root=Path(args.output_root),
        review_json_paths=[Path(path) for path in args.review_json],
        base_decisions_path=Path(args.base_decisions) if args.base_decisions else None,
        apply_db_copy_to=Path(args.apply_db_copy) if args.apply_db_copy else None,
        apply_live=args.apply_live,
        min_atom_quality=args.min_atom_quality,
        groundedness_threshold=args.groundedness_threshold,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
