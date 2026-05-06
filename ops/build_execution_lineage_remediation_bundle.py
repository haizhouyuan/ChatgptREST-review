#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from ops.export_execution_activity_review_queue import build_review_queue


EXTENSION_FIELDS = ["lane_id", "role_id", "adapter_id", "profile_id", "executor_kind"]
DECISION_FIELDNAMES = [
    "atom_id",
    "task_ref",
    "trace_id",
    "source",
    "episode_type",
    "lineage_class",
    "extension_count",
    "correlation_group_size",
    "candidate_fill_fields",
    "remediation_action",
    "decision_bucket",
    "canonical_question",
]


def _correlation_key(row: dict[str, Any]) -> str:
    return f"{row.get('task_ref') or ''}::{row.get('trace_id') or ''}"


def _present_extension_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in EXTENSION_FIELDS if str(row.get(field) or "")]


def _lineage_class(extension_count: int) -> str:
    if extension_count <= 0:
        return "minimal_lineage"
    if extension_count >= len(EXTENSION_FIELDS):
        return "rich_execution_identity"
    return "partial_execution_identity"


def _decision_bucket(*, extension_count: int, candidate_fill_fields: list[str]) -> str:
    if extension_count >= len(EXTENSION_FIELDS):
        return "review_ready"
    if candidate_fill_fields:
        return "remediation_candidate"
    return "manual_review_required"


def _remediation_action(*, extension_count: int, candidate_fill_fields: list[str]) -> str:
    if extension_count >= len(EXTENSION_FIELDS):
        return "none"
    if candidate_fill_fields:
        return "correlate_fill_from_group"
    return "hold_sparse_lineage"


def build_bundle(*, db_path: str | Path, output_dir: str | Path, limit: int = 1000) -> dict[str, Any]:
    queue = build_review_queue(db_path=db_path, limit=limit)
    rows = list(queue["rows"])
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(_correlation_key(row), []).append(row)

    audit_rows: list[dict[str, Any]] = []
    remediation_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []

    for key, group_rows in sorted(groups.items()):
        extension_union = sorted({field for row in group_rows for field in _present_extension_fields(row)})
        richest_row = max(group_rows, key=lambda row: (len(_present_extension_fields(row)), float(row.get("valid_from") or 0.0), str(row.get("atom_id") or "")))
        richest_fields = _present_extension_fields(richest_row)
        min_extensions = min(len(_present_extension_fields(row)) for row in group_rows)
        max_extensions = max(len(_present_extension_fields(row)) for row in group_rows)
        cluster_status = (
            "no_extension_data"
            if max_extensions == 0
            else "mixed_identity_richness"
            if min_extensions != max_extensions
            else "stable_identity_richness"
        )
        audit_rows.append(
            {
                "correlation_key": key,
                "task_ref": str(group_rows[0].get("task_ref") or ""),
                "trace_id": str(group_rows[0].get("trace_id") or ""),
                "row_count": len(group_rows),
                "sources": sorted({str(row.get("source") or "") for row in group_rows}),
                "episode_types": sorted({str(row.get("episode_type") or "") for row in group_rows}),
                "extension_union": extension_union,
                "min_extension_count": min_extensions,
                "max_extension_count": max_extensions,
                "richest_atom_id": str(richest_row.get("atom_id") or ""),
                "cluster_status": cluster_status,
            }
        )

        for row in group_rows:
            present_fields = _present_extension_fields(row)
            candidate_fill_fields = sorted([field for field in extension_union if field not in present_fields])
            extension_count = len(present_fields)
            lineage_class = _lineage_class(extension_count)
            remediation_action = _remediation_action(
                extension_count=extension_count,
                candidate_fill_fields=candidate_fill_fields,
            )
            decision_bucket = _decision_bucket(
                extension_count=extension_count,
                candidate_fill_fields=candidate_fill_fields,
            )
            remediation_rows.append(
                {
                    "atom_id": str(row.get("atom_id") or ""),
                    "correlation_key": key,
                    "lineage_class": lineage_class,
                    "extension_count": extension_count,
                    "present_extension_fields": present_fields,
                    "candidate_fill_fields": candidate_fill_fields,
                    "remediation_action": remediation_action,
                    "decision_bucket": decision_bucket,
                    "canonical_question": str(row.get("canonical_question") or ""),
                }
            )
            decision_rows.append(
                {
                    "atom_id": str(row.get("atom_id") or ""),
                    "task_ref": str(row.get("task_ref") or ""),
                    "trace_id": str(row.get("trace_id") or ""),
                    "source": str(row.get("source") or ""),
                    "episode_type": str(row.get("episode_type") or ""),
                    "lineage_class": lineage_class,
                    "extension_count": extension_count,
                    "correlation_group_size": len(group_rows),
                    "candidate_fill_fields": ",".join(candidate_fill_fields),
                    "remediation_action": remediation_action,
                    "decision_bucket": decision_bucket,
                    "canonical_question": str(row.get("canonical_question") or ""),
                }
            )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "db_path": str(db_path),
        "selected_atoms": len(rows),
        "correlation_groups": len(audit_rows),
        "groups_with_mixed_identity_richness": sum(1 for row in audit_rows if row["cluster_status"] == "mixed_identity_richness"),
        "rows_review_ready": sum(1 for row in decision_rows if row["decision_bucket"] == "review_ready"),
        "rows_remediation_candidate": sum(1 for row in decision_rows if row["decision_bucket"] == "remediation_candidate"),
        "rows_manual_review_required": sum(1 for row in decision_rows if row["decision_bucket"] == "manual_review_required"),
    }
    (out / "lineage_remediation_manifest.json").write_text(
        json.dumps(
            {
                **manifest,
                "rows": remediation_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "identity_correlation_audit.json").write_text(
        json.dumps(
            {
                "db_path": str(db_path),
                "groups": audit_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "review_decision_input.json").write_text(
        json.dumps(
            {
                "db_path": str(db_path),
                "rows": decision_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    with (out / "review_decision_input.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=DECISION_FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(decision_rows)
    (out / "summary.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    readme_lines = [
        "# Execution Lineage Remediation / Decision Input Bundle",
        "",
        "## Summary",
        "",
        f"- `selected_atoms`: `{manifest['selected_atoms']}`",
        f"- `correlation_groups`: `{manifest['correlation_groups']}`",
        f"- `groups_with_mixed_identity_richness`: `{manifest['groups_with_mixed_identity_richness']}`",
        f"- `rows_review_ready`: `{manifest['rows_review_ready']}`",
        f"- `rows_remediation_candidate`: `{manifest['rows_remediation_candidate']}`",
        f"- `rows_manual_review_required`: `{manifest['rows_manual_review_required']}`",
        "",
        "## Outputs",
        "",
        "- `identity_correlation_audit.json`",
        "- `lineage_remediation_manifest.json`",
        "- `review_decision_input.json`",
        "- `review_decision_input.tsv`",
        "- `summary.json`",
    ]
    (out / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "output_dir": str(out),
        "selected_atoms": len(rows),
        "correlation_groups": len(audit_rows),
        "rows_review_ready": manifest["rows_review_ready"],
        "rows_remediation_candidate": manifest["rows_remediation_candidate"],
        "rows_manual_review_required": manifest["rows_manual_review_required"],
        "files": [
            str(out / "identity_correlation_audit.json"),
            str(out / "lineage_remediation_manifest.json"),
            str(out / "review_decision_input.json"),
            str(out / "review_decision_input.tsv"),
            str(out / "summary.json"),
            str(out / "README.md"),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic lineage remediation and decision-input artifacts from the execution review queue."
    )
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    result = build_bundle(db_path=args.db, output_dir=args.output_dir, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
