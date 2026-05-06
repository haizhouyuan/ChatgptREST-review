from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from chatgptrest.evomap.knowledge.planning_review_plane import build_snapshot
from chatgptrest.evomap.knowledge.planning_review_refresh import compare_snapshot_dirs, run_refresh
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from chatgptrest.evomap.knowledge.db import KnowledgeDB


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _seed_db(path: Path) -> None:
    db = KnowledgeDB(str(path))
    db.init_schema()
    doc_defs = [
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
    ]
    for doc_id, raw_ref, title in doc_defs:
        db.put_document(Document(doc_id=doc_id, source="planning", project="planning", raw_ref=raw_ref, title=title, meta_json="{}"))
        db.put_episode(Episode(episode_id=f"ep_{doc_id}", doc_id=doc_id, episode_type="md_section", title=title, summary=title, start_ref=raw_ref, end_ref=raw_ref, time_start=1.0, time_end=1.0))
        db.put_atom(
            Atom(
                atom_id=f"at_{doc_id}",
                episode_id=f"ep_{doc_id}",
                atom_type="procedure",
                question=title,
                answer="Stable planning deliverable.",
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
    seed_rows = {
        "planning_review_plane_seed.tsv": [],
        "planning_service_candidate_seed.tsv": [
            {"title": "机器人代工项目可行性研究报告（v0.3｜可研主文档）", "avg_quality": "0.82", "atoms": "1", "raw_ref": "/vol1/1000/projects/planning/机器人代工业务规划/104关节模组代工_过程记录/99_最新产物/可行性研究报告_v0.3.md"},
            {"title": "预算概览 v0.1", "avg_quality": "0.82", "atoms": "1", "raw_ref": "/vol1/1000/projects/planning/预算/预算概览_v0.1.md"},
        ],
        "planning_archive_only_seed.tsv": [],
    }
    for name, rows in seed_rows.items():
        with (package_dir / name).open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["title", "avg_quality", "atoms", "raw_ref"], delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
    with (lineage_dir / "planning_lineage_family_registry.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["family_id", "domain", "path_scope", "family_kind", "initial_evomap_bucket", "notes"], delimiter="\t")
        writer.writeheader()
        writer.writerows(
            [
                {"family_id": "b104_exec", "domain": "business", "path_scope": "机器人代工业务规划/104关节模组代工_过程记录/", "family_kind": "report", "initial_evomap_bucket": "service_candidate", "notes": "104"},
                {"family_id": "budget_outputs", "domain": "budget", "path_scope": "预算/", "family_kind": "budget", "initial_evomap_bucket": "service_candidate", "notes": "budget"},
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


def _seed_baseline_dir(base: Path, *, db_path: Path, package_dir: Path, lineage_dir: Path) -> Path:
    baseline_dir = base / "baseline"
    build_snapshot(db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir, output_dir=baseline_dir)
    with (baseline_dir / "planning_review_decisions_v2.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["doc_id", "decision", "service_readiness", "note"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "doc_id": "doc_104_latest",
                    "decision": "service_candidate",
                    "service_readiness": "high",
                    "note": "seed baseline decision",
                }
            ]
        )
    (baseline_dir / "planning_review_decisions_v2.summary.json").write_text(
        json.dumps({"reviewed_docs": 1}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return baseline_dir


def test_compare_snapshot_dirs_detects_new_candidate(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    package_dir, lineage_dir = _seed_package_dirs(tmp_path)
    baseline_dir = _seed_baseline_dir(tmp_path, db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir)
    prev_dir = tmp_path / "prev"
    curr_dir = tmp_path / "curr"
    build_snapshot(db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir, output_dir=prev_dir)
    rows = _read_tsv(prev_dir / "bootstrap_active_allow_candidates.tsv")
    rows = [row for row in rows if row["doc_id"] != "doc_budget"]
    with (prev_dir / "bootstrap_active_allow_candidates.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    build_snapshot(db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir, output_dir=curr_dir)
    result = compare_snapshot_dirs(prev_dir, curr_dir, baseline_decision_dir=baseline_dir)
    assert len(result["added_candidates"]) == 1
    assert result["added_candidates"][0]["doc_id"] == "doc_budget"
    assert len(result["review_needed_rows"]) == 1
    assert result["review_needed_rows"][0]["doc_id"] == "doc_budget"
    assert result["decision_source_dir"] == str(baseline_dir)


def test_run_refresh_writes_summary_and_pack(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    package_dir, lineage_dir = _seed_package_dirs(tmp_path)
    baseline_root = tmp_path / "baseline_root"
    baseline_root.mkdir()
    baseline_dir = _seed_baseline_dir(baseline_root, db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir)
    output_root = tmp_path / "refresh_root"
    first = run_refresh(
        db_path=db_path,
        package_dir=package_dir,
        lineage_dir=lineage_dir,
        baseline_root=baseline_root,
        output_root=output_root,
    )
    assert first["summary"]["review_needed_docs"] == 1
    assert first["summary"]["decision_source_dir"] == str(baseline_dir)
    second = run_refresh(
        db_path=db_path,
        package_dir=package_dir,
        lineage_dir=lineage_dir,
        baseline_root=baseline_root,
        output_root=output_root,
    )
    assert Path(second["summary"]["current_snapshot_dir"]).exists()
    assert Path(second["outputs"]["review_needed"]).exists()
    assert Path(second["pack_path"]).exists() or second["pack_path"] == ""
    assert second["summary"]["review_needed_docs"] == 1


def test_compare_snapshot_dirs_prefers_previous_v3_decisions(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    package_dir, lineage_dir = _seed_package_dirs(tmp_path)
    prev_dir = tmp_path / "prev"
    curr_dir = tmp_path / "curr"
    build_snapshot(db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir, output_dir=prev_dir)
    with (prev_dir / "planning_review_decisions_v3.tsv").open("w", encoding="utf-8", newline="") as fh:
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
        writer.writerows(
            [
                {
                    "doc_id": "doc_104_latest",
                    "title": "doc1",
                    "raw_ref": "/doc1.md",
                    "family_id": "f1",
                    "review_domain": "strategy",
                    "source_bucket": "planning_strategy",
                    "avg_quality": "0.8",
                    "final_bucket": "service_candidate",
                    "service_readiness": "high",
                    "reviewers": "[]",
                },
                {
                    "doc_id": "doc_budget",
                    "title": "doc2",
                    "raw_ref": "/doc2.md",
                    "family_id": "f2",
                    "review_domain": "budget",
                    "source_bucket": "planning_budget",
                    "avg_quality": "0.7",
                    "final_bucket": "procedure",
                    "service_readiness": "medium",
                    "reviewers": "[]",
                },
            ]
        )
    build_snapshot(db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir, output_dir=curr_dir)
    result = compare_snapshot_dirs(prev_dir, curr_dir, baseline_decision_dir=None)
    assert result["decision_source_dir"] == str(prev_dir)
    assert result["previous_decisions_count"] == 2
    assert len(result["review_needed_rows"]) == 0


def test_run_refresh_uses_latest_prior_decision_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    package_dir, lineage_dir = _seed_package_dirs(tmp_path)
    baseline_root = tmp_path / "baseline_root"
    _seed_baseline_dir(baseline_root, db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir)
    output_root = tmp_path / "refresh_root"

    first = run_refresh(
        db_path=db_path,
        package_dir=package_dir,
        lineage_dir=lineage_dir,
        baseline_root=baseline_root,
        output_root=output_root,
    )
    first_dir = Path(first["summary"]["current_snapshot_dir"])
    with (first_dir / "planning_review_decisions_v4.tsv").open("w", encoding="utf-8", newline="") as fh:
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
        writer.writerows(
            [
                {
                    "doc_id": "doc_104_latest",
                    "title": "doc1",
                    "raw_ref": "/doc1.md",
                    "family_id": "f1",
                    "review_domain": "strategy",
                    "source_bucket": "planning_strategy",
                    "avg_quality": "0.8",
                    "final_bucket": "service_candidate",
                    "service_readiness": "high",
                    "reviewers": "[]",
                },
                {
                    "doc_id": "doc_budget",
                    "title": "doc2",
                    "raw_ref": "/doc2.md",
                    "family_id": "f2",
                    "review_domain": "budget",
                    "source_bucket": "planning_budget",
                    "avg_quality": "0.7",
                    "final_bucket": "procedure",
                    "service_readiness": "medium",
                    "reviewers": "[]",
                },
            ]
        )

    time.sleep(1.1)
    second = run_refresh(
        db_path=db_path,
        package_dir=package_dir,
        lineage_dir=lineage_dir,
        baseline_root=baseline_root,
        output_root=output_root,
    )
    assert second["summary"]["decision_source_dir"] == str(first_dir)
    assert second["summary"]["review_needed_docs"] == 0
