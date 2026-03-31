from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chatgptrest.evomap.knowledge.planning_review_plane import (
    _connect,
    _fetch_top_atom_context,
    build_snapshot,
    default_db_path,
)

DEFAULT_BASELINE_ROOT = Path("/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane")


@dataclass(frozen=True)
class RefreshSummary:
    current_snapshot_dir: str
    previous_snapshot_dir: str
    decision_source_dir: str
    review_needed_docs: int
    role_changed_docs: int
    added_service_candidates: int
    removed_service_candidates: int
    pack_items: int


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def find_previous_snapshot(output_root: Path, current_dir: Path) -> Path | None:
    candidates = [p for p in output_root.iterdir() if p.is_dir() and p != current_dir]
    candidates.sort(key=lambda p: p.name)
    return candidates[-1] if candidates else None


def find_latest_decision_snapshot(snapshot_root: Path, *, exclude: Path | None = None) -> Path | None:
    if not snapshot_root.exists():
        return None
    candidates = [p for p in snapshot_root.iterdir() if p.is_dir() and p != exclude and _decision_file(p)]
    candidates.sort(key=lambda p: p.name)
    return candidates[-1] if candidates else None


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


def compare_snapshot_dirs(
    previous_dir: Path | None,
    current_dir: Path,
    *,
    baseline_decision_dir: Path | None = None,
) -> dict[str, Any]:
    current_roles = {row["doc_id"]: row for row in _read_tsv(current_dir / "document_role.tsv")}
    current_allow = {row["doc_id"]: row for row in _read_tsv(current_dir / "bootstrap_active_allow_candidates.tsv")}
    current_decisions_file = _decision_file(current_dir)
    current_decisions = (
        {row["doc_id"]: row for row in _read_tsv(current_decisions_file)} if current_decisions_file else {}
    )

    previous_roles: dict[str, dict[str, str]] = {}
    previous_allow: dict[str, dict[str, str]] = {}
    previous_decisions: dict[str, dict[str, str]] = {}
    decision_source_dir: Path | None = None
    compare_dir = previous_dir or baseline_decision_dir
    if compare_dir:
        previous_roles = {row["doc_id"]: row for row in _read_tsv(compare_dir / "document_role.tsv")}
        previous_allow = {row["doc_id"]: row for row in _read_tsv(compare_dir / "bootstrap_active_allow_candidates.tsv")}
    if previous_dir:
        previous_decisions_file = _decision_file(previous_dir)
        if previous_decisions_file:
            previous_decisions = {row["doc_id"]: row for row in _read_tsv(previous_decisions_file)}
            decision_source_dir = previous_dir
    if not previous_decisions and baseline_decision_dir:
        baseline_decisions_file = _decision_file(baseline_decision_dir)
        if baseline_decisions_file:
            previous_decisions = {row["doc_id"]: row for row in _read_tsv(baseline_decisions_file)}
            decision_source_dir = baseline_decision_dir

    role_changed_rows: list[dict[str, Any]] = []
    for doc_id, row in current_roles.items():
        prev = previous_roles.get(doc_id)
        if not prev:
            continue
        changed_fields = [
            field
            for field in ("document_role", "source_bucket", "review_domain", "family_id", "is_latest_output")
            if prev.get(field, "") != row.get(field, "")
        ]
        if changed_fields:
            role_changed_rows.append(
                {
                    "doc_id": doc_id,
                    "title": row.get("title", ""),
                    "raw_ref": row.get("raw_ref", ""),
                    "changed_fields": ",".join(changed_fields),
                    "previous_role": prev.get("document_role", ""),
                    "current_role": row.get("document_role", ""),
                }
            )

    added_candidates: list[dict[str, Any]] = []
    removed_candidates: list[dict[str, Any]] = []
    review_needed: list[dict[str, Any]] = []

    for doc_id, row in current_allow.items():
        prev = previous_allow.get(doc_id)
        changed = not prev or any(
            prev.get(field, "") != row.get(field, "")
            for field in ("source_bucket", "review_domain", "family_id", "avg_quality", "is_latest_output")
        )
        if not prev:
            added_candidates.append(
                {
                    "doc_id": doc_id,
                    "title": row.get("title", ""),
                    "raw_ref": row.get("raw_ref", ""),
                    "reason": "new_service_candidate",
                }
            )
        if changed or doc_id not in previous_decisions:
            review_needed.append(
                {
                    "doc_id": doc_id,
                    "title": row.get("title", ""),
                    "raw_ref": row.get("raw_ref", ""),
                    "source_bucket": row.get("source_bucket", ""),
                    "review_domain": row.get("review_domain", ""),
                    "family_id": row.get("family_id", ""),
                    "avg_quality": row.get("avg_quality", ""),
                    "reason": "changed_inputs" if changed else "missing_previous_decision",
                }
            )

    for doc_id, row in previous_allow.items():
        if doc_id not in current_allow:
            removed_candidates.append(
                {
                    "doc_id": doc_id,
                    "title": row.get("title", ""),
                    "raw_ref": row.get("raw_ref", ""),
                    "reason": "removed_from_service_candidate_pool",
                }
            )

    return {
        "previous_snapshot_dir": str(previous_dir) if previous_dir else "",
        "current_snapshot_dir": str(current_dir),
        "decision_source_dir": str(decision_source_dir) if decision_source_dir else "",
        "role_changed_rows": role_changed_rows,
        "added_candidates": added_candidates,
        "removed_candidates": removed_candidates,
        "review_needed_rows": review_needed,
        "current_decisions_count": len(current_decisions),
        "previous_decisions_count": len(previous_decisions),
    }


def write_refresh_outputs(compare_result: dict[str, Any], output_dir: Path) -> dict[str, str]:
    role_changed = compare_result["role_changed_rows"]
    added = compare_result["added_candidates"]
    removed = compare_result["removed_candidates"]
    review_needed = compare_result["review_needed_rows"]

    paths = {
        "role_changed": output_dir / "role_changed.tsv",
        "added_candidates": output_dir / "added_service_candidates.tsv",
        "removed_candidates": output_dir / "removed_service_candidates.tsv",
        "review_needed": output_dir / "review_needed.tsv",
    }
    _write_tsv(
        paths["role_changed"],
        role_changed,
        ["doc_id", "title", "raw_ref", "changed_fields", "previous_role", "current_role"],
    )
    _write_tsv(paths["added_candidates"], added, ["doc_id", "title", "raw_ref", "reason"])
    _write_tsv(paths["removed_candidates"], removed, ["doc_id", "title", "raw_ref", "reason"])
    _write_tsv(
        paths["review_needed"],
        review_needed,
        ["doc_id", "title", "raw_ref", "source_bucket", "review_domain", "family_id", "avg_quality", "reason"],
    )
    return {key: str(path) for key, path in paths.items()}


def build_incremental_review_pack(
    *,
    db_path: str | Path,
    current_snapshot_dir: Path,
    review_needed_rows: list[dict[str, Any]],
    output_path: Path,
    pack_id: str = "planning_incremental_review_pack_v1",
    limit: int = 80,
) -> dict[str, Any]:
    conn = _connect(db_path)
    picked = review_needed_rows[:limit]
    items: list[dict[str, Any]] = []
    for row in picked:
        item = dict(row)
        item["top_atoms"] = _fetch_top_atom_context(conn, row["doc_id"], limit=2)
        items.append(item)
    conn.close()
    pack = {
        "pack_id": pack_id,
        "pack_type": "planning_incremental_service_review",
        "current_snapshot_dir": str(current_snapshot_dir),
        "instructions": {
            "decision_values": [
                "service_candidate",
                "lesson",
                "procedure",
                "correction",
                "review_only",
                "archive_only",
                "controlled",
                "reject_noise",
            ],
            "fields": ["doc_id", "decision", "service_readiness", "note"],
            "rules": [
                "Only review docs listed in this delta pack.",
                "If the document is still reusable and stable, keep service_candidate.",
                "If it became noisy, demote to review_only/archive_only/reject_noise.",
            ],
        },
        "items": items,
    }
    output_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_path.with_name(output_path.stem + "_prompt.txt").write_text(
        "Review this incremental planning pack and return JSON only.\n\n"
        + json.dumps(pack, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return pack


def run_refresh(
    *,
    db_path: str | Path = default_db_path(),
    package_dir: Path,
    lineage_dir: Path,
    output_root: Path,
    baseline_root: Path = DEFAULT_BASELINE_ROOT,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    from datetime import UTC, datetime

    current_dir = output_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    build_snapshot(db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir, output_dir=current_dir)
    previous_dir = find_previous_snapshot(output_root, current_dir)
    previous_decision_dir = find_latest_decision_snapshot(output_root, exclude=current_dir)
    baseline_decision_dir = previous_decision_dir or find_latest_decision_snapshot(baseline_root)
    compare_result = compare_snapshot_dirs(previous_dir, current_dir, baseline_decision_dir=baseline_decision_dir)
    output_paths = write_refresh_outputs(compare_result, current_dir / "refresh")
    pack_items = 0
    pack_path = ""
    if compare_result["review_needed_rows"]:
        pack_path_obj = current_dir / "refresh" / "planning_incremental_review_pack_v1.json"
        pack = build_incremental_review_pack(
            db_path=db_path,
            current_snapshot_dir=current_dir,
            review_needed_rows=compare_result["review_needed_rows"],
            output_path=pack_path_obj,
        )
        pack_items = len(pack["items"])
        pack_path = str(pack_path_obj)
    summary = RefreshSummary(
        current_snapshot_dir=str(current_dir),
        previous_snapshot_dir=str(previous_dir) if previous_dir else "",
        decision_source_dir=compare_result["decision_source_dir"],
        review_needed_docs=len(compare_result["review_needed_rows"]),
        role_changed_docs=len(compare_result["role_changed_rows"]),
        added_service_candidates=len(compare_result["added_candidates"]),
        removed_service_candidates=len(compare_result["removed_candidates"]),
        pack_items=pack_items,
    )
    payload = {
        "ok": True,
        "summary": summary.__dict__,
        "outputs": output_paths,
        "pack_path": pack_path,
    }
    (current_dir / "refresh" / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload
