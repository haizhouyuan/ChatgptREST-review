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

from chatgptrest.evomap.knowledge.planning_review_plane import DEFAULT_LINEAGE_DIR, DEFAULT_PACKAGE_DIR, default_db_path
from chatgptrest.evomap.knowledge.planning_review_refresh import DEFAULT_BASELINE_ROOT
from ops.report_evomap_promotion_inventory import build_promotion_inventory, write_promotion_inventory_artifacts
from ops.report_planning_review_consistency import report_consistency
from ops.report_planning_review_state import DEFAULT_REFRESH_ROOT, report_state
from ops.run_planning_review_cycle import run_cycle


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_state_bundle(*, db_path: str | Path, allowlist_path: Path | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if allowlist_path is None or not allowlist_path.exists():
        return None, None
    state = report_state(db_path=db_path, allowlist_path=allowlist_path)
    consistency = report_consistency(db_path=db_path, allowlist_path=allowlist_path)
    return state, consistency


def _count_delta(before: dict[str, Any], after: dict[str, Any], key: str) -> int:
    return int(after.get("counts", {}).get(key, 0)) - int(before.get("counts", {}).get(key, 0))


def _derive_allowlist_after(cycle_payload: dict[str, Any], refresh_root: Path) -> tuple[Path | None, str]:
    full_output_raw = str(cycle_payload.get("full_output") or "").strip()
    if full_output_raw:
        full_output = Path(full_output_raw)
        derived = full_output.with_name(full_output.stem + "_allowlist.tsv")
        if derived.exists():
            return derived, "cycle_output"
    latest = _latest_allowlist(refresh_root)
    if latest and latest.exists():
        return latest, "latest_refresh_root"
    return None, ""


def run_maintenance(
    *,
    db_path: str | Path,
    package_dir: Path,
    lineage_dir: Path,
    baseline_root: Path,
    refresh_output_root: Path,
    output_root: Path,
    review_json_paths: list[Path],
    base_decisions_path: Path | None,
    apply_db_copy_to: Path | None,
    apply_live: bool,
    min_atom_quality: float,
    groundedness_threshold: float,
    top_n: int = 20,
) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    allowlist_before = _latest_allowlist(refresh_output_root)
    pre_inventory = build_promotion_inventory(db_path=db_path, top_n=top_n)
    pre_artifacts = write_promotion_inventory_artifacts(pre_inventory, run_dir / "pre_inventory", "pre")
    pre_state, pre_consistency = _load_state_bundle(db_path=db_path, allowlist_path=allowlist_before)

    cycle_payload = run_cycle(
        db_path=db_path,
        package_dir=package_dir,
        lineage_dir=lineage_dir,
        baseline_root=baseline_root,
        output_root=refresh_output_root,
        review_json_paths=review_json_paths,
        base_decisions_path=base_decisions_path,
        apply_db_copy_to=apply_db_copy_to,
        apply_live=apply_live,
        min_atom_quality=min_atom_quality,
        groundedness_threshold=groundedness_threshold,
    )

    target_db = Path(str(cycle_payload.get("apply_summary", {}).get("target_db") or db_path))
    allowlist_after, allowlist_after_source = _derive_allowlist_after(cycle_payload, refresh_output_root)
    post_inventory = build_promotion_inventory(db_path=target_db, top_n=top_n)
    post_artifacts = write_promotion_inventory_artifacts(post_inventory, run_dir / "post_inventory", "post")
    post_state, post_consistency = _load_state_bundle(db_path=target_db, allowlist_path=allowlist_after)

    _write_json(run_dir / "cycle_payload.json", cycle_payload)
    if pre_state is not None:
        _write_json(run_dir / "pre_state.json", pre_state)
    if pre_consistency is not None:
        _write_json(run_dir / "pre_consistency.json", pre_consistency)
    if post_state is not None:
        _write_json(run_dir / "post_state.json", post_state)
    if post_consistency is not None:
        _write_json(run_dir / "post_consistency.json", post_consistency)

    checks = {
        "cycle_ok": bool(cycle_payload.get("ok", False)),
        "pre_inventory_loaded": True,
        "post_inventory_loaded": True,
        "allowlist_after_present": (not review_json_paths) or (allowlist_after is not None and allowlist_after.exists()),
        "post_consistency_ok": True if post_consistency is None else bool(post_consistency.get("ok", False)),
    }
    warnings: list[str] = []
    if review_json_paths and not checks["allowlist_after_present"]:
        warnings.append("review_outputs_supplied_but_no_allowlist_after")
    if post_consistency is not None and not post_consistency.get("ok", False):
        warnings.append("post_consistency_not_green")

    summary = {
        "ok": all(checks.values()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": cycle_payload.get("mode", ""),
        "db_path": str(db_path),
        "target_db": str(target_db),
        "run_dir": str(run_dir),
        "refresh_output_root": str(refresh_output_root),
        "allowlist_before": str(allowlist_before) if allowlist_before else "",
        "allowlist_after": str(allowlist_after) if allowlist_after else "",
        "allowlist_after_source": allowlist_after_source,
        "checks": checks,
        "warnings": warnings,
        "promotion_delta": {
            "active": _count_delta(pre_inventory, post_inventory, "active"),
            "candidate": _count_delta(pre_inventory, post_inventory, "candidate"),
            "staged": _count_delta(pre_inventory, post_inventory, "staged"),
        },
        "artifacts": {
            "pre_inventory": [str(path) for path in pre_artifacts],
            "post_inventory": [str(path) for path in post_artifacts],
            "cycle_payload": str(run_dir / "cycle_payload.json"),
            "pre_state": str(run_dir / "pre_state.json") if pre_state is not None else "",
            "pre_consistency": str(run_dir / "pre_consistency.json") if pre_consistency is not None else "",
            "post_state": str(run_dir / "post_state.json") if post_state is not None else "",
            "post_consistency": str(run_dir / "post_consistency.json") if post_consistency is not None else "",
        },
        "pre_inventory_counts": pre_inventory["counts"],
        "post_inventory_counts": post_inventory["counts"],
        "cycle_summary_path": str(cycle_payload.get("cycle_summary_path") or ""),
    }
    _write_json(run_dir / "summary.json", summary)
    readme_lines = [
        "# Planning Review Maintenance Harness",
        "",
        f"- `mode`: `{summary['mode']}`",
        f"- `db_path`: `{summary['db_path']}`",
        f"- `target_db`: `{summary['target_db']}`",
        f"- `allowlist_before`: `{summary['allowlist_before'] or 'none'}`",
        f"- `allowlist_after`: `{summary['allowlist_after'] or 'none'}`",
        f"- `checks_ok`: `{summary['ok']}`",
        f"- `warnings`: `{', '.join(warnings) if warnings else 'none'}`",
        "",
        "## Promotion Delta",
        "",
        f"- `active`: `{summary['promotion_delta']['active']}`",
        f"- `candidate`: `{summary['promotion_delta']['candidate']}`",
        f"- `staged`: `{summary['promotion_delta']['staged']}`",
        "",
        "## Artifacts",
        "",
        f"- `summary.json`: `{run_dir / 'summary.json'}`",
        f"- `cycle_payload.json`: `{run_dir / 'cycle_payload.json'}`",
        f"- `pre_inventory/`: `{run_dir / 'pre_inventory'}`",
        f"- `post_inventory/`: `{run_dir / 'post_inventory'}`",
    ]
    (run_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a planning review maintenance harness with pre/post promotion inventory snapshots.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR))
    parser.add_argument("--lineage-dir", default=str(DEFAULT_LINEAGE_DIR))
    parser.add_argument("--baseline-root", default=str(DEFAULT_BASELINE_ROOT))
    parser.add_argument("--refresh-output-root", default=str(DEFAULT_REFRESH_ROOT))
    parser.add_argument("--output-root", default=str(REPO_ROOT / "artifacts" / "monitor" / "planning_review_maintenance"))
    parser.add_argument("--review-json", action="append", default=[], help="Reviewer JSON outputs. Repeat for multiple files.")
    parser.add_argument("--base-decisions", default="", help="Optional full baseline decision TSV to overlay against.")
    parser.add_argument("--apply-db-copy", default="", help="Optional temp DB copy path to validate import/bootstrap.")
    parser.add_argument("--apply-live", action="store_true", help="Apply directly to --db instead of a temp copy.")
    parser.add_argument("--min-atom-quality", type=float, default=0.58)
    parser.add_argument("--groundedness-threshold", type=float, default=0.6)
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()

    payload = run_maintenance(
        db_path=args.db,
        package_dir=Path(args.package_dir),
        lineage_dir=Path(args.lineage_dir),
        baseline_root=Path(args.baseline_root),
        refresh_output_root=Path(args.refresh_output_root),
        output_root=Path(args.output_root),
        review_json_paths=[Path(path) for path in args.review_json],
        base_decisions_path=Path(args.base_decisions) if args.base_decisions else None,
        apply_db_copy_to=Path(args.apply_db_copy) if args.apply_db_copy else None,
        apply_live=args.apply_live,
        min_atom_quality=args.min_atom_quality,
        groundedness_threshold=args.groundedness_threshold,
        top_n=args.top_n,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
