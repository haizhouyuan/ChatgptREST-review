from __future__ import annotations

import csv
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.planning_review_plane import (
    _has_runtime_grounding_anchors,
    _normalize_service_readiness,
    apply_bootstrap_allowlist,
    build_service_review_pack,
    build_snapshot,
    import_review_plane,
    merge_review_outputs,
    _extract_review_payload,
)
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _seed_db(path: Path) -> None:
    db = KnowledgeDB(str(path))
    db.init_schema()
    doc_defs = [
        (
            "doc_104_latest",
            "planning",
            "planning",
            "/vol1/1000/projects/planning/机器人代工业务规划/104关节模组代工_过程记录/99_最新产物/可行性研究报告_v0.3.md",
            "机器人代工项目可行性研究报告（v0.3｜可研主文档）",
        ),
        (
            "doc_review_pack",
            "planning",
            "planning",
            "/vol1/1000/projects/planning/减速器开发/PEEK摆线齿轮图纸/_review_pack/REQUEST_R1.md",
            "REQUEST_R1",
        ),
        (
            "doc_budget",
            "planning",
            "planning",
            "/vol1/1000/projects/planning/预算/预算概览_v0.1.md",
            "预算概览 v0.1",
        ),
        (
            "doc_controlled",
            "planning",
            "planning",
            "/vol1/1000/projects/planning/人员与绩效/面试/面试题.md",
            "面试题",
        ),
    ]
    for doc_id, source, project, raw_ref, title in doc_defs:
        answer = "This is a stable planning deliverable with reusable operational steps."
        if doc_id == "doc_104_latest":
            answer = "Use /vol1/1000/projects/ChatgptREST/docs/runbook.md as the runtime reference before rollout."
        db.put_document(
            Document(
                doc_id=doc_id,
                source=source,
                project=project,
                raw_ref=raw_ref,
                title=title,
                meta_json="{}",
            )
        )
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
                answer=answer,
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
    for name, rows in {
        "planning_review_plane_seed.tsv": [
            {"title": "REQUEST_R1", "avg_quality": "0.7", "atoms": "1", "raw_ref": "/vol1/1000/projects/planning/减速器开发/PEEK摆线齿轮图纸/_review_pack/REQUEST_R1.md"},
        ],
        "planning_service_candidate_seed.tsv": [
            {"title": "机器人代工项目可行性研究报告（v0.3｜可研主文档）", "avg_quality": "0.82", "atoms": "1", "raw_ref": "/vol1/1000/projects/planning/机器人代工业务规划/104关节模组代工_过程记录/99_最新产物/可行性研究报告_v0.3.md"},
            {"title": "预算概览 v0.1", "avg_quality": "0.82", "atoms": "1", "raw_ref": "/vol1/1000/projects/planning/预算/预算概览_v0.1.md"},
        ],
        "planning_archive_only_seed.tsv": [
            {"title": "REQUEST_R1", "avg_quality": "0.7", "atoms": "1", "raw_ref": "/vol1/1000/projects/planning/减速器开发/PEEK摆线齿轮图纸/_review_pack/REQUEST_R1.md"},
        ],
    }.items():
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
                    "notes": "104 main line",
                },
                {
                    "family_id": "budget_outputs",
                    "domain": "budget",
                    "path_scope": "预算/",
                    "family_kind": "budget",
                    "initial_evomap_bucket": "service_candidate",
                    "notes": "budget line",
                },
                {
                    "family_id": "peek_review",
                    "domain": "reducer",
                    "path_scope": "减速器开发/PEEK摆线齿轮图纸/",
                    "family_kind": "review_pack",
                    "initial_evomap_bucket": "review_plane",
                    "notes": "peek review",
                },
            ]
        )
    with (lineage_dir / "planning_lineage_edges.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["relation_type", "src_family_id", "dst_family_id", "evidence"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "relation_type": "SUPERCEDES_FLOW",
                "src_family_id": "b104_exec",
                "dst_family_id": "budget_outputs",
                "evidence": "budget follows execution",
            }
        )
    with (lineage_dir / "planning_evomap_mapping_candidates.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["family_id", "target_bucket", "rationale"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(
            [
                {"family_id": "b104_exec", "target_bucket": "service_candidate", "rationale": "stable deliverable"},
                {"family_id": "budget_outputs", "target_bucket": "service_candidate", "rationale": "stable deliverable"},
                {"family_id": "peek_review", "target_bucket": "review_plane", "rationale": "review pack"},
            ]
        )
    return package_dir, lineage_dir


def test_build_snapshot_and_review_pack(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    package_dir, lineage_dir = _seed_package_dirs(tmp_path)
    snapshot_dir = tmp_path / "snapshot"
    result = build_snapshot(db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir, output_dir=snapshot_dir)
    assert result["summary"]["planning_docs"] == 4
    roles = {row["doc_id"]: row for row in _read_tsv(snapshot_dir / "document_role.tsv")}
    assert roles["doc_104_latest"]["document_role"] == "service_candidate"
    assert roles["doc_104_latest"]["family_id"] == "b104_exec"
    assert roles["doc_review_pack"]["document_role"] == "archive_only"
    assert roles["doc_controlled"]["document_role"] == "controlled"
    pack = build_service_review_pack(db_path=db_path, snapshot_dir=snapshot_dir)
    assert pack["pack_type"] == "planning_service_candidate_review"
    assert {item["doc_id"] for item in pack["items"]} >= {"doc_104_latest", "doc_budget"}


def test_import_and_apply_bootstrap(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    package_dir, lineage_dir = _seed_package_dirs(tmp_path)
    snapshot_dir = tmp_path / "snapshot"
    build_snapshot(db_path=db_path, package_dir=package_dir, lineage_dir=lineage_dir, output_dir=snapshot_dir)

    review_payload_a = {
        "pack_id": "a",
        "items": [
            {"doc_id": "doc_104_latest", "decision": "service_candidate", "service_readiness": "high", "note": "keep"},
            {"doc_id": "doc_budget", "decision": "procedure", "service_readiness": "medium", "note": "budget template"},
        ],
    }
    review_payload_b = {
        "pack_id": "b",
        "items": [
            {"doc_id": "doc_104_latest", "decision": "service_candidate", "service_readiness": "high", "note": "keep"},
            {"doc_id": "doc_budget", "decision": "procedure", "service_readiness": "medium", "note": "budget template"},
        ],
    }
    p1 = snapshot_dir / "codex.json"
    p2 = snapshot_dir / "gemini.json"
    p1.write_text(json.dumps(review_payload_a, ensure_ascii=False), encoding="utf-8")
    p2.write_text(json.dumps(review_payload_b, ensure_ascii=False), encoding="utf-8")
    merge_review_outputs(snapshot_dir=snapshot_dir, review_json_paths=[p1, p2], output_path=snapshot_dir / "planning_review_decisions.tsv")

    import_summary = import_review_plane(
        db_path=db_path,
        snapshot_dir=snapshot_dir,
        review_decisions_path=snapshot_dir / "planning_review_decisions.tsv",
    )
    assert import_summary["updated_docs"] == 4

    db = KnowledgeDB(str(db_path))
    conn = db.connect()
    meta = json.loads(conn.execute("select meta_json from documents where doc_id='doc_104_latest'").fetchone()[0])
    assert meta["planning_review"]["family_id"] == "b104_exec"
    assert meta["planning_review"]["decision"]["final_bucket"] == "service_candidate"

    bootstrap_summary = apply_bootstrap_allowlist(
        db_path=db_path,
        allowlist_path=snapshot_dir / "bootstrap_active_allowlist.tsv",
        output_dir=snapshot_dir / "bootstrap",
        min_atom_quality=0.5,
        groundedness_threshold=0.5,
    )
    assert bootstrap_summary["candidate_atoms"] >= 2
    assert bootstrap_summary["promoted_atoms"] >= 1
    promoted = conn.execute("select promotion_status from atoms where atom_id='at_doc_104_latest'").fetchone()[0]
    assert promoted == "active"
    assert bootstrap_summary["reconciled_out_atoms"] == 0

    with (snapshot_dir / "bootstrap_active_allowlist_v2.tsv").open("w", encoding="utf-8", newline="") as fh:
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
                "doc_id": "doc_budget",
                "title": "预算概览 v0.1",
                "raw_ref": "/vol1/1000/projects/planning/预算/预算概览_v0.1.md",
                "family_id": "budget_outputs",
                "review_domain": "budget",
                "source_bucket": "planning_budget",
                "avg_quality": "0.820",
                "final_bucket": "procedure",
                "service_readiness": "medium",
                "reviewers": "[]",
            }
        )
    rerun_summary = apply_bootstrap_allowlist(
        db_path=db_path,
        allowlist_path=snapshot_dir / "bootstrap_active_allowlist_v2.tsv",
        output_dir=snapshot_dir / "bootstrap_v2",
        min_atom_quality=0.5,
        groundedness_threshold=0.5,
    )
    demoted = conn.execute("select promotion_status from atoms where atom_id='at_doc_104_latest'").fetchone()[0]
    assert demoted == "staged"
    budget_status = conn.execute("select promotion_status from atoms where atom_id='at_doc_budget'").fetchone()[0]
    assert budget_status == "candidate"
    assert rerun_summary["reconciled_out_atoms"] >= 1


def test_extract_review_payload_unwraps_response_wrapper() -> None:
    wrapped = {
        "session_id": "x",
        "response": "```json\n{\"pack_id\":\"p\",\"items\":[{\"doc_id\":\"d1\",\"decision\":\"service_candidate\",\"service_readiness\":\"high\",\"note\":\"ok\"}]}\n```",
    }
    payload = _extract_review_payload(wrapped)
    assert payload["pack_id"] == "p"
    assert payload["items"][0]["doc_id"] == "d1"


def test_extract_review_payload_accepts_top_level_list_and_wrapped_list() -> None:
    direct = _extract_review_payload(
        [{"doc_id": "d1", "decision": "service_candidate", "service_readiness": "high", "note": "ok"}]
    )
    assert direct["items"][0]["doc_id"] == "d1"

    wrapped = {
        "result": "```json\n[{\"doc_id\":\"d2\",\"decision\":\"review_only\",\"service_readiness\":\"medium\",\"note\":\"wrapped\"}]\n```"
    }
    parsed = _extract_review_payload(wrapped)
    assert parsed["items"][0]["doc_id"] == "d2"
    assert parsed["items"][0]["decision"] == "review_only"


def test_normalize_service_readiness_accepts_numeric_scores() -> None:
    assert _normalize_service_readiness(0.9) == "high"
    assert _normalize_service_readiness(0.55) == "medium"
    assert _normalize_service_readiness(0.1) == "low"
    assert _normalize_service_readiness("0.8") == "high"
    assert _normalize_service_readiness("medium") == "medium"


def test_runtime_grounding_anchor_detection() -> None:
    assert _has_runtime_grounding_anchors("Use /vol1/1000/projects/ChatgptREST/docs/runbook.md as reference.")
    assert _has_runtime_grounding_anchors("Check chatgptrest/api/routes_advisor_v3.py before editing.")
    assert _has_runtime_grounding_anchors("Restart chatgptrest-api.service if the API is down.")
    assert not _has_runtime_grounding_anchors("这是一个可复用的业务规划模板，适合后续项目复用。")


def test_apply_bootstrap_allowlist_defers_service_candidate_without_runtime_anchors(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc_generic",
            source="planning",
            project="planning",
            raw_ref="/vol1/1000/projects/planning/generic.md",
            title="generic",
            meta_json="{}",
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_generic",
            doc_id="doc_generic",
            episode_type="md_section",
            title="generic",
            summary="generic",
            start_ref="/vol1/1000/projects/planning/generic.md",
            end_ref="/vol1/1000/projects/planning/generic.md",
            time_start=1.0,
            time_end=1.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_generic",
            episode_id="ep_generic",
            atom_type="procedure",
            question="generic",
            answer="这是一个可复用的业务规划模板，适合后续项目复用。",
            canonical_question="generic",
            quality_auto=0.82,
            value_auto=0.71,
            valid_from=1.0,
        )
    )
    db.commit()
    db.close()

    allowlist = tmp_path / "allowlist.tsv"
    with allowlist.open("w", encoding="utf-8", newline="") as fh:
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
                "doc_id": "doc_generic",
                "title": "generic",
                "raw_ref": "/vol1/1000/projects/planning/generic.md",
                "family_id": "fam_generic",
                "review_domain": "planning",
                "source_bucket": "planning_latest_output",
                "avg_quality": "0.820",
                "final_bucket": "service_candidate",
                "service_readiness": "high",
                "reviewers": "[]",
            }
        )

    output_dir = tmp_path / "bootstrap"
    summary = apply_bootstrap_allowlist(
        db_path=db_path,
        allowlist_path=allowlist,
        output_dir=output_dir,
        min_atom_quality=0.5,
        groundedness_threshold=0.5,
    )

    db = KnowledgeDB(str(db_path))
    conn = db.connect()
    row = conn.execute(
        "select promotion_status, promotion_reason, groundedness from atoms where atom_id = 'at_generic'"
    ).fetchone()
    assert row[0] == "candidate"
    assert row[1] == "planning_bootstrap:service_candidate"
    assert float(row[2] or 0.0) == 0.0
    assert summary["candidate_atoms"] == 1
    assert summary["promoted_atoms"] == 0
    assert summary["deferred_atoms"] == 1
    deferred_rows = _read_tsv(output_dir / "bootstrap_active_deferred.tsv")
    assert deferred_rows == [
        {
            "doc_id": "doc_generic",
            "atom_id": "at_generic",
            "atom_type": "procedure",
            "quality_auto": "0.820",
            "target_bucket": "service_candidate",
            "result": "candidate",
            "reason": "groundedness_unknown_no_runtime_anchors",
            "groundedness": "unknown",
        }
    ]


def test_apply_bootstrap_allowlist_clears_stale_groundedness_on_no_anchor_rerun(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc_generic",
            source="planning",
            project="planning",
            raw_ref="/vol1/1000/projects/planning/generic.md",
            title="generic",
            meta_json="{}",
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_generic",
            doc_id="doc_generic",
            episode_type="md_section",
            title="generic",
            summary="generic",
            start_ref="/vol1/1000/projects/planning/generic.md",
            end_ref="/vol1/1000/projects/planning/generic.md",
            time_start=1.0,
            time_end=1.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_generic",
            episode_id="ep_generic",
            atom_type="procedure",
            question="generic",
            answer="这是一个可复用的业务规划模板，适合后续项目复用。",
            canonical_question="generic",
            quality_auto=0.82,
            promotion_status=PromotionStatus.ACTIVE.value,
            promotion_reason="planning_bootstrap_review_verified",
            groundedness=1.0,
            valid_from=1.0,
        )
    )
    db.commit()
    db.close()

    allowlist = tmp_path / "allowlist.tsv"
    with allowlist.open("w", encoding="utf-8", newline="") as fh:
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
                "doc_id": "doc_generic",
                "title": "generic",
                "raw_ref": "/vol1/1000/projects/planning/generic.md",
                "family_id": "fam_generic",
                "review_domain": "planning",
                "source_bucket": "planning_latest_output",
                "avg_quality": "0.820",
                "final_bucket": "service_candidate",
                "service_readiness": "high",
                "reviewers": "[]",
            }
        )

    output_dir = tmp_path / "bootstrap"
    summary = apply_bootstrap_allowlist(
        db_path=db_path,
        allowlist_path=allowlist,
        output_dir=output_dir,
        min_atom_quality=0.5,
        groundedness_threshold=0.5,
    )

    db = KnowledgeDB(str(db_path))
    conn = db.connect()
    row = conn.execute(
        "select promotion_status, promotion_reason, groundedness from atoms where atom_id = 'at_generic'"
    ).fetchone()
    assert row[0] == "candidate"
    assert row[1] == "planning_bootstrap:service_candidate"
    assert float(row[2] or 0.0) == 0.0
    assert summary["candidate_atoms"] == 1
    assert summary["promoted_atoms"] == 0
    assert summary["deferred_atoms"] == 1
