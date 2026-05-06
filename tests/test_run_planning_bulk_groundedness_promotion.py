from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus
from ops.run_planning_bulk_groundedness_promotion import run_bulk_cycle


def _seed_db(db_path: Path, repo_root: Path) -> None:
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    conn = db.connect()

    docs = [
        Document(
            doc_id="doc_active",
            source="planning",
            project="planning",
            raw_ref="/vol1/1000/projects/planning/aios/AIOS_grounded_active.md",
            title="AIOS grounded",
        ),
        Document(
            doc_id="doc_candidate",
            source="planning",
            project="planning",
            raw_ref="/vol1/1000/projects/planning/demo/_review_pack/round1/review_pack.md",
            title="Review pack candidate",
        ),
        Document(
            doc_id="doc_skip",
            source="planning",
            project="planning",
            raw_ref="/vol1/1000/projects/planning/misc/freeform_notes.md",
            title="Misc freeform",
        ),
    ]
    episodes = [
        Episode(episode_id="ep_active", doc_id="doc_active", episode_type="md_section", title="active"),
        Episode(episode_id="ep_candidate", doc_id="doc_candidate", episode_type="md_section", title="candidate"),
        Episode(episode_id="ep_skip", doc_id="doc_skip", episode_type="md_section", title="skip"),
    ]
    atoms = [
        Atom(
            atom_id="at_active",
            episode_id="ep_active",
            question="How do we validate the planning path?",
            answer=f"Use {repo_root / 'docs' / 'runbook.md'} as the tracked planning file.",
            canonical_question="planning grounded active",
            quality_auto=0.82,
            promotion_status=PromotionStatus.STAGED.value,
        ),
        Atom(
            atom_id="at_candidate",
            episode_id="ep_candidate",
            question="What is the review-pack decision?",
            answer="This review-pack summary is text-only and should stay curated before activation.",
            canonical_question="planning curated candidate",
            quality_auto=0.88,
            promotion_status=PromotionStatus.STAGED.value,
        ),
        Atom(
            atom_id="at_skip",
            episode_id="ep_skip",
            question="What is the misc note?",
            answer="Unanchored misc note that should not be promoted by the bulk runner.",
            canonical_question="planning misc skip",
            quality_auto=0.91,
            promotion_status=PromotionStatus.STAGED.value,
        ),
    ]

    for doc in docs:
        conn.execute(
            """
            INSERT INTO documents (doc_id, source, project, raw_ref, title, created_at, updated_at, hash, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (doc.doc_id, doc.source, doc.project, doc.raw_ref, doc.title, doc.created_at, doc.updated_at, "", "{}"),
        )
    for episode in episodes:
        conn.execute(
            """
            INSERT INTO episodes (episode_id, doc_id, episode_type, title, summary, start_ref, end_ref, time_start, time_end, turn_count, source_ext)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                episode.episode_id,
                episode.doc_id,
                episode.episode_type,
                episode.title,
                "",
                "",
                "",
                0.0,
                0.0,
                0,
                "{}",
            ),
        )
    for atom in atoms:
        conn.execute(
            """
            INSERT INTO atoms (
                atom_id, episode_id, atom_type, question, answer, canonical_question,
                quality_auto, groundedness, promotion_status, promotion_reason, valid_from
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                atom.atom_id,
                atom.episode_id,
                atom.atom_type,
                atom.question,
                atom.answer,
                atom.canonical_question,
                atom.quality_auto,
                atom.groundedness,
                atom.promotion_status,
                atom.promotion_reason,
                atom.valid_from,
            ),
        )
    conn.commit()
    conn.close()


def test_run_bulk_cycle_dry_run(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge.db"
    _seed_db(db_path, Path("/vol1/1000/projects/ChatgptREST"))

    summary = run_bulk_cycle(
        db_path=db_path,
        output_root=tmp_path / "artifacts",
        live=False,
        max_atoms=100,
        batch_size=10,
        planning_root=Path("/vol1/1000/projects/planning"),
        project_root=Path("/vol1/1000/projects/ChatgptREST"),
        min_quality_active=0.6,
        min_quality_candidate=0.7,
        groundedness_threshold=0.6,
        candidate_buckets=("planning_review_pack",),
        include_candidate=True,
    )

    assert summary["mode"] == "dry_run"
    assert summary["stats"]["eligible_active"] == 1
    assert summary["stats"]["eligible_candidate"] == 1
    assert summary["delta"]["active"] == 0
    assert summary["delta"]["candidate"] == 0

    with open(summary["artifacts"]["candidate_eligibility"], "r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    assert [row["atom_id"] for row in rows] == ["at_candidate"]


def test_run_bulk_cycle_live_updates_db_and_audits(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge.db"
    _seed_db(db_path, Path("/vol1/1000/projects/ChatgptREST"))

    summary = run_bulk_cycle(
        db_path=db_path,
        output_root=tmp_path / "artifacts",
        live=True,
        max_atoms=100,
        batch_size=2,
        planning_root=Path("/vol1/1000/projects/planning"),
        project_root=Path("/vol1/1000/projects/ChatgptREST"),
        min_quality_active=0.6,
        min_quality_candidate=0.7,
        groundedness_threshold=0.6,
        candidate_buckets=("planning_review_pack",),
        include_candidate=True,
    )

    conn = sqlite3.connect(str(db_path))
    active_status = conn.execute("SELECT promotion_status, groundedness FROM atoms WHERE atom_id = 'at_active'").fetchone()
    candidate_status = conn.execute("SELECT promotion_status FROM atoms WHERE atom_id = 'at_candidate'").fetchone()
    skip_status = conn.execute("SELECT promotion_status FROM atoms WHERE atom_id = 'at_skip'").fetchone()
    grounded_audits = conn.execute("SELECT COUNT(*) FROM groundedness_audit").fetchone()[0]
    promotion_audits = conn.execute("SELECT COUNT(*) FROM promotion_audit").fetchone()[0]
    conn.close()

    assert active_status[0] == PromotionStatus.ACTIVE.value
    assert active_status[1] >= 0.6
    assert candidate_status[0] == PromotionStatus.CANDIDATE.value
    assert skip_status[0] == PromotionStatus.STAGED.value
    assert grounded_audits >= 1
    assert promotion_audits >= 2
    assert summary["delta"]["active"] == 1
    assert summary["delta"]["candidate"] == 1
