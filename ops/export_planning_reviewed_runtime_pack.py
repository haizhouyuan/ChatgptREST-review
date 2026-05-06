#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.evomap.knowledge.planning_review_plane import default_db_path
from ops.report_planning_review_state import DEFAULT_REFRESH_ROOT, _latest_allowlist, report_state


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_reviewed_runtime_pack"

DOC_FIELDS = [
    "doc_id",
    "title",
    "raw_ref",
    "family_id",
    "review_domain",
    "source_bucket",
    "document_role",
    "final_bucket",
    "service_readiness",
    "is_latest_output",
    "updated_at",
    "updated_at_iso",
    "live_active_atoms",
    "live_candidate_atoms",
]

ATOM_FIELDS = [
    "doc_id",
    "atom_id",
    "episode_id",
    "atom_type",
    "promotion_status",
    "promotion_reason",
    "quality_auto",
    "value_auto",
    "question",
    "canonical_question",
]


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _ts_to_iso(value: float) -> str:
    if not value:
        return ""
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()


def export_runtime_pack(
    *,
    db_path: str | Path,
    allowlist_path: str | Path,
    output_dir: str | Path,
    require_consistent: bool = True,
) -> dict[str, Any]:
    allow_rows = _read_tsv(Path(allowlist_path))
    allow_doc_ids = [row["doc_id"] for row in allow_rows]
    state = report_state(db_path=db_path, allowlist_path=Path(allowlist_path))

    if require_consistent and (
        int(state["allowlist_docs_without_live_atoms"]) > 0
        or int(state["stale_live_atoms_outside_allowlist"]) > 0
    ):
        raise RuntimeError(
            "Planning reviewed runtime pack requires clean allowlist/bootstrap alignment. "
            f"See allowlist_docs_without_live_atoms={state['allowlist_docs_without_live_atoms']} "
            f"stale_live_atoms_outside_allowlist={state['stale_live_atoms_outside_allowlist']}"
        )

    conn = _connect(db_path)
    placeholders = ",".join("?" for _ in allow_doc_ids) or "''"
    doc_rows = conn.execute(
        f"""
        SELECT
            d.doc_id,
            d.title,
            d.raw_ref,
            COALESCE(json_extract(d.meta_json, '$.planning_review.family_id'), '') AS family_id,
            COALESCE(json_extract(d.meta_json, '$.planning_review.review_domain'), '') AS review_domain,
            COALESCE(json_extract(d.meta_json, '$.planning_review.source_bucket'), '') AS source_bucket,
            COALESCE(json_extract(d.meta_json, '$.planning_review.document_role'), '') AS document_role,
            COALESCE(json_extract(d.meta_json, '$.planning_review.decision.final_bucket'), '') AS final_bucket,
            COALESCE(json_extract(d.meta_json, '$.planning_review.decision.service_readiness'), '') AS service_readiness,
            COALESCE(json_extract(d.meta_json, '$.planning_review.is_latest_output'), 0) AS is_latest_output,
            d.updated_at,
            SUM(CASE WHEN a.promotion_status = 'active' THEN 1 ELSE 0 END) AS live_active_atoms,
            SUM(CASE WHEN a.promotion_status = 'candidate' THEN 1 ELSE 0 END) AS live_candidate_atoms
        FROM documents d
        JOIN episodes e ON e.doc_id = d.doc_id
        JOIN atoms a ON a.episode_id = e.episode_id
        WHERE d.source = 'planning'
          AND d.doc_id IN ({placeholders})
          AND a.promotion_status IN ('active', 'candidate')
        GROUP BY
            d.doc_id, d.title, d.raw_ref, d.meta_json, d.updated_at
        ORDER BY review_domain, source_bucket, d.doc_id
        """,
        allow_doc_ids,
    ).fetchall()

    atom_rows = conn.execute(
        f"""
        SELECT
            d.doc_id,
            a.atom_id,
            a.episode_id,
            a.atom_type,
            a.promotion_status,
            a.promotion_reason,
            a.quality_auto,
            a.value_auto,
            a.question,
            a.canonical_question
        FROM documents d
        JOIN episodes e ON e.doc_id = d.doc_id
        JOIN atoms a ON a.episode_id = e.episode_id
        WHERE d.source = 'planning'
          AND d.doc_id IN ({placeholders})
          AND a.promotion_status IN ('active', 'candidate')
        ORDER BY d.doc_id, a.atom_id
        """,
        allow_doc_ids,
    ).fetchall()
    conn.close()

    docs = [
        {
            "doc_id": str(row["doc_id"]),
            "title": str(row["title"] or ""),
            "raw_ref": str(row["raw_ref"] or ""),
            "family_id": str(row["family_id"] or ""),
            "review_domain": str(row["review_domain"] or ""),
            "source_bucket": str(row["source_bucket"] or ""),
            "document_role": str(row["document_role"] or ""),
            "final_bucket": str(row["final_bucket"] or ""),
            "service_readiness": str(row["service_readiness"] or ""),
            "is_latest_output": int(row["is_latest_output"] or 0),
            "updated_at": float(row["updated_at"] or 0.0),
            "updated_at_iso": _ts_to_iso(float(row["updated_at"] or 0.0)),
            "live_active_atoms": int(row["live_active_atoms"] or 0),
            "live_candidate_atoms": int(row["live_candidate_atoms"] or 0),
        }
        for row in doc_rows
    ]
    atoms = [
        {
            "doc_id": str(row["doc_id"]),
            "atom_id": str(row["atom_id"]),
            "episode_id": str(row["episode_id"]),
            "atom_type": str(row["atom_type"] or ""),
            "promotion_status": str(row["promotion_status"] or ""),
            "promotion_reason": str(row["promotion_reason"] or ""),
            "quality_auto": float(row["quality_auto"] or 0.0),
            "value_auto": float(row["value_auto"] or 0.0),
            "question": str(row["question"] or ""),
            "canonical_question": str(row["canonical_question"] or ""),
        }
        for row in atom_rows
    ]

    exported_doc_ids = {row["doc_id"] for row in docs}
    exported_atom_doc_ids = {row["doc_id"] for row in atoms}
    review_domains = sorted({row["review_domain"] for row in docs})
    source_buckets = sorted({row["source_bucket"] for row in docs})

    manifest = {
        "pack_type": "planning_reviewed_runtime_pack_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "allowlist_path": str(allowlist_path),
        "scope": {
            "source": "planning",
            "opt_in_only": True,
            "default_runtime_cutover": False,
            "includes_only_allowlist_docs": True,
            "includes_only_active_candidate_atoms": True,
            "excludes_staged_atoms": True,
        },
        "counts": {
            "reviewed_docs_total": int(state["reviewed_docs"]),
            "allowlist_docs_total": int(state["allowlist_docs"]),
            "exported_docs": len(docs),
            "exported_atoms": len(atoms),
            "live_active_atoms": int(state["planning_atom_status"].get("active", 0)),
            "live_candidate_atoms": int(state["planning_atom_status"].get("candidate", 0)),
        },
        "review_domains": review_domains,
        "source_buckets": source_buckets,
        "checks": {
            "allowlist_live_coverage_ok": int(state["allowlist_docs_without_live_atoms"]) == 0,
            "bootstrap_allowlist_alignment_ok": int(state["stale_live_atoms_outside_allowlist"]) == 0,
            "exported_docs_match_allowlist_ok": len(exported_doc_ids) == len(set(allow_doc_ids)),
            "atom_doc_ids_subset_allowlist_ok": exported_atom_doc_ids.issubset(set(allow_doc_ids)),
            "staged_atoms_excluded_ok": all(row["promotion_status"] in {"active", "candidate"} for row in atoms),
        },
        "consumption": {
            "mode": "explicit_opt_in",
            "intended_consumer": "mainline runtime hook",
            "note": "This pack does not change default retrieval. It is a reviewed planning slice prepared for explicit consumption.",
        },
    }
    manifest["ok"] = all(manifest["checks"].values())

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_tsv(out / "docs.tsv", docs, DOC_FIELDS)
    _write_tsv(out / "atoms.tsv", atoms, ATOM_FIELDS)
    (out / "retrieval_pack.json").write_text(
        json.dumps(
            {
                "pack_type": manifest["pack_type"],
                "doc_ids": sorted(exported_doc_ids),
                "atom_ids": [row["atom_id"] for row in atoms],
                "review_domains": review_domains,
                "source_buckets": source_buckets,
                "opt_in_only": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "smoke_manifest.json").write_text(
        json.dumps(
            {
                "pack_type": manifest["pack_type"],
                "sample_titles": [row["title"] for row in docs[:10]],
                "sample_doc_ids": [row["doc_id"] for row in docs[:10]],
                "note": "Use this pack only through explicit runtime hook or offline smoke. Do not wire it into default retrieval.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "README.md").write_text(
        "\n".join(
            [
                "# Planning Reviewed Runtime Pack",
                "",
                "This pack contains only the reviewed planning allowlist and their active/candidate atoms.",
                "",
                "## Boundaries",
                "",
                "- opt-in only",
                "- not a default runtime cutover",
                "- excludes all staged-only planning atoms",
                "- intended for explicit consumption by a future runtime hook",
                "",
                "## Files",
                "",
                "- `manifest.json`",
                "- `docs.tsv`",
                "- `atoms.tsv`",
                "- `retrieval_pack.json`",
                "- `smoke_manifest.json`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "ok": manifest["ok"],
        "output_dir": str(out),
        "manifest_path": str(out / "manifest.json"),
        "exported_docs": len(docs),
        "exported_atoms": len(atoms),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the reviewed planning slice as an opt-in runtime pack.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--allowlist", default="")
    parser.add_argument("--refresh-root", default=str(DEFAULT_REFRESH_ROOT))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--no-require-consistent", action="store_true")
    args = parser.parse_args()

    allowlist_path = Path(args.allowlist) if args.allowlist else _latest_allowlist(Path(args.refresh_root))
    if allowlist_path is None or not allowlist_path.exists():
        raise SystemExit("No allowlist file found. Pass --allowlist explicitly.")

    out = Path(args.output_dir) if args.output_dir else (DEFAULT_OUTPUT_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    print(
        json.dumps(
            export_runtime_pack(
                db_path=args.db,
                allowlist_path=allowlist_path,
                output_dir=out,
                require_consistent=not args.no_require_consistent,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
