from __future__ import annotations

import csv
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.planning_review_plane import build_snapshot
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.run_planning_review_cycle import run_cycle


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _seed_db(path: Path) -> None:
    db = KnowledgeDB(str(path))
    db.init_schema()
    for doc_id, raw_ref, title in (
        (
            "doc_104_latest",
            "/vol1/1000/projects/planning/机器人代工业务规划/104关节模组代工_过程记录/99_最新产物/可行性研究报告_v0.3.md",
            "机器人代工项目可行性研究报告（v0.3｜可研主文档）",
        ),
        (
            "doc_budget",
            "/vol1/1000/projects/planning/预算/预算概览_v0.1.md",
            "预算概览 v0.1",
        ),
    ):
        db.put_document(Document(doc_id=doc_id, source="planning", project="planning", raw_ref=raw_ref, title=title, meta_json="{}"))
        db.put_episode(
            Episode(
                episode_id=f"ep_{doc_id}",
                doc_id=doc_id,
                episode_type="md_section",
                title=title,
                summary=title,
                start_ref=raw_ref,
                end_ref=raw_ref,
                time_start=1.0,
                time_end=1.0,
            )
        )
        db.put_atom(
            Atom(
                atom_id=f"at_{doc_id}",
                episode_id=f"ep_{doc_id}",
                atom_type="procedure",
                question=title,
                answer="Stable planning deliverable with reusable steps.",
                canonical_question=title,
                quality_auto=0.82,
                value_auto=0.71,
                valid_from=1.0,
            )
        )
    db.commit()
    db.close()


def _seed_package_dirs(base: Path) -> tuple[Path, Path]:
    package_dir = base / "package"
    lineage_dir = base / "lineage"
    package_dir.mkdir()
    lineage_dir.mkdir()
    rows_by_file = {
        "planning_review_plane_seed.tsv": [],
        "planning_service_candidate_seed.tsv": [
            {
                "title": "机器人代工项目可行性研究报告（v0.3｜可研主文档）",
                "avg_quality": "0.82",
                "atoms": "1",
                "raw_ref": "/vol1/1000/projects/planning/机器人代工业务规划/104关节模组代工_过程记录/99_最新产物/可行性研究报告_v0.3.md",
            },
            {
                "title": "预算概览 v0.1",
                "avg_quality": "0.82",
                "atoms": "1",
                "raw_ref": "/vol1/1000/projects/planning/预算/预算概览_v0.1.md",
            },
        ],
        "planning_archive_only_seed.tsv": [],
    }
    for name, rows in rows_by_file.items():
        with (package_dir / name).open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["title", "avg_quality", "atoms", "raw_ref"], delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
    with (lineage_dir / "planning_lineage_family_registry.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["family_id", "domain", "path_scope", "family_kind", "initial_evomap_bucket", "notes"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "family_id": "b104_exec",
                    "domain": "business",
                    "path_scope": "机器人代工业务规划/104关节模组代工_过程记录/",
                    "family_kind": "report",
                    "initial_evomap_bucket": "service_candidate",
                    "notes": "104",
                },
                {
                    "family_id": "budget_outputs",
                    "domain": "budget",
                    "path_scope": "预算/",
                    "family_kind": "budget",
                    "initial_evomap_bucket": "service_candidate",
                    "notes": "budget",
                },
            ]
        )
    with (lineage_dir / "planning_lineage_edges.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["relation_type", "src_family_id", "dst_family_id", "evidence"], delimiter="\t")
        writer.writeheader()
    with (lineage_dir / "planning_evomap_mapping_candidates.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["family_id", "target_bucket", "rationale"], delimiter="\t")
        writer.writeheader()
        writer.writerows(
            [
                {"family_id": "b104_exec", "target_bucket": "service_candidate", "rationale": "stable"},
                {"family_id": "budget_outputs", "target_bucket": "service_candidate", "rationale": "stable"},
            ]
        )
    return package_dir, lineage_dir


def _seed_baseline_dir(base_root: Path, *, db_path: Path, package_dir: Path, lineage_dir: Path) -> Path:
    baseline_dir = base_root / "20260311T000000Z"
    baseline_dir.mkdir(parents=True)
    build_snapshot(db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir, output_dir=baseline_dir)
    with (baseline_dir / "planning_review_decisions_v3.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "doc_id",
                "title",
                "raw_ref",
                "family_id",
                "review_domain",
                "source_bucket",
                "avg_quality",
                "final_bucket",
                "service_readiness",
                "reviewers",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_104_latest",
                "title": "机器人代工项目可行性研究报告（v0.3｜可研主文档）",
                "raw_ref": "/vol1/1000/projects/planning/机器人代工业务规划/104关节模组代工_过程记录/99_最新产物/可行性研究报告_v0.3.md",
                "family_id": "b104_exec",
                "review_domain": "business_104",
                "source_bucket": "planning_latest_output",
                "avg_quality": "0.820",
                "final_bucket": "service_candidate",
                "service_readiness": "high",
                "reviewers": "[]",
            }
        )
    return baseline_dir


def test_run_cycle_refresh_only_emits_manifest(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    package_dir, lineage_dir = _seed_package_dirs(tmp_path)
    baseline_root = tmp_path / "baseline_root"
    _seed_baseline_dir(baseline_root, db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir)

    payload = run_cycle(
        db_path=db_path,
        package_dir=package_dir,
        lineage_dir=lineage_dir,
        baseline_root=baseline_root,
        output_root=tmp_path / "refresh_root",
        review_json_paths=[],
        base_decisions_path=None,
        apply_db_copy_to=None,
        apply_live=False,
        min_atom_quality=0.5,
        groundedness_threshold=0.5,
    )

    assert payload["mode"] == "refresh_only"
    assert payload["refresh"]["summary"]["review_needed_docs"] == 1
    manifest = payload["reviewer_manifest"]
    assert Path(manifest["manifest_path"]).exists()
    reviewers = {item["reviewer"] for item in manifest["reviewers"]}
    assert reviewers == {"gemini_no_mcp", "claudeminmax", "codex_auth_only"}


def test_run_cycle_merge_and_apply_copy(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    package_dir, lineage_dir = _seed_package_dirs(tmp_path)
    baseline_root = tmp_path / "baseline_root"
    _seed_baseline_dir(baseline_root, db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir)

    first = run_cycle(
        db_path=db_path,
        package_dir=package_dir,
        lineage_dir=lineage_dir,
        baseline_root=baseline_root,
        output_root=tmp_path / "refresh_root",
        review_json_paths=[],
        base_decisions_path=None,
        apply_db_copy_to=None,
        apply_live=False,
        min_atom_quality=0.5,
        groundedness_threshold=0.5,
    )
    snapshot_dir = Path(first["refresh"]["summary"]["current_snapshot_dir"])
    review_output = snapshot_dir / "review_runs_cycle" / "gemini_no_mcp.json"
    review_output.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "doc_id": "doc_104_latest",
                        "decision": "service_candidate",
                        "service_readiness": "high",
                        "note": "keep active",
                    },
                    {
                        "doc_id": "doc_budget",
                        "decision": "procedure",
                        "service_readiness": "high",
                        "note": "budget template remains reusable",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validation_db = tmp_path / "validation" / "evomap_copy.db"
    second = run_cycle(
        db_path=db_path,
        package_dir=package_dir,
        lineage_dir=lineage_dir,
        baseline_root=baseline_root,
        output_root=tmp_path / "refresh_root",
        review_json_paths=[review_output],
        base_decisions_path=None,
        apply_db_copy_to=validation_db,
        apply_live=False,
        min_atom_quality=0.5,
        groundedness_threshold=0.5,
    )

    assert second["mode"] == "refresh_merge_apply_copy"
    assert Path(second["delta_output"]).exists()
    assert Path(second["full_output"]).exists()
    assert second["compose_summary"]["final_docs"] == 2
    assert Path(second["apply_summary"]["target_db"]).exists()
    allowlist = _read_tsv(Path(second["full_output"]).with_name("planning_review_decisions_v4_allowlist.tsv"))
    assert {row["doc_id"] for row in allowlist} == {"doc_104_latest", "doc_budget"}
