from __future__ import annotations

import sqlite3
from pathlib import Path

from chatgptrest.evomap.knowledge.review_experiment import (
    build_atom_pack,
    build_family_pack,
    build_noise_pack,
    compare_review_outputs,
    inventory_summary,
    load_review_json,
    write_inventory_artifacts,
    write_review_pack,
)


def _seed_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(
        """
        create table documents (
          doc_id text primary key,
          source text not null default '',
          project text not null default '',
          raw_ref text not null default '',
          title text not null default '',
          created_at real not null default 0,
          updated_at real not null default 0,
          hash text not null default '',
          meta_json text not null default '{}'
        );
        create table episodes (
          episode_id text primary key,
          doc_id text not null default '',
          episode_type text not null default '',
          title text not null default '',
          summary text not null default '',
          start_ref text not null default '',
          end_ref text not null default '',
          time_start real not null default 0,
          time_end real not null default 0,
          turn_count integer not null default 0,
          source_ext text not null default '{}',
          followup_depth integer not null default 0,
          constraint_growth integer not null default 0,
          reversal_count integer not null default 0,
          convergence_score real not null default 0
        );
        create table atoms (
          atom_id text primary key,
          episode_id text not null default '',
          atom_type text not null default 'qa',
          question text not null default '',
          answer text not null default '',
          canonical_question text not null default '',
          alt_questions text not null default '[]',
          constraints text not null default '[]',
          prerequisites text not null default '[]',
          intent text not null default '',
          format text not null default 'plain',
          applicability text not null default '{}',
          stability text not null default 'versioned',
          status text not null default 'candidate',
          valid_from real not null default 0,
          valid_to real not null default 0,
          quality_auto real not null default 0,
          value_auto real not null default 0,
          novelty real not null default 0,
          groundedness real not null default 0,
          confidence real not null default 0,
          reusability real not null default 0,
          scores_json text not null default '{}',
          source_quality real not null default 0,
          hash text not null default '',
          scope_project text not null default '',
          scope_component text not null default '',
          promotion_status text not null default 'staged',
          superseded_by text not null default '',
          chain_id text not null default '',
          chain_rank integer not null default 0,
          is_chain_head integer not null default 0,
          promotion_reason text not null default ''
        );
        create table groundedness_audit (id integer primary key autoincrement, atom_id text);
        create table promotion_audit (id integer primary key autoincrement, atom_id text);
        """
    )
    docs = [
        ("doc1", "maint", "infrastructure", "/x/runbook_v1.md", "Runbook v1"),
        ("doc2", "maint", "infrastructure", "/x/runbook_v2.md", "Runbook v2"),
        ("doc3", "planning", "planning", "/x/_review_pack/answer.md", "answer"),
        ("doc4", "planning", "research", "/x/report.md", "Research Report"),
    ]
    cur.executemany("insert into documents values (?, ?, ?, ?, ?, 0, 0, '', '{}')", docs)
    episodes = [
        ("ep1", "doc1"),
        ("ep2", "doc2"),
        ("ep3", "doc3"),
        ("ep4", "doc4"),
    ]
    cur.executemany(
        "insert into episodes (episode_id, doc_id, episode_type, title, summary, start_ref, end_ref, time_start, time_end, turn_count, source_ext, followup_depth, constraint_growth, reversal_count, convergence_score) values (?, ?, '', '', '', '', '', 0, 0, 0, '{}', 0, 0, 0, 0)",
        episodes,
    )
    atoms = [
        ("a1", "ep1", "procedure", "q1", "a1 text", "How to recover?", "candidate", 0.9, "staged"),
        ("a2", "ep2", "procedure", "q2", "a2 text", "How to recover?", "candidate", 0.8, "staged"),
        ("a3", "ep3", "qa", "q3", "a3 text", "", "draft", 0.7, "staged"),
        ("a4", "ep4", "qa", "q4", "a4 text", "What changed?", "reviewed", 0.85, "staged"),
    ]
    cur.executemany(
        "insert into atoms (atom_id, episode_id, atom_type, question, answer, canonical_question, status, quality_auto, promotion_status) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        atoms,
    )
    conn.commit()
    conn.close()


def test_inventory_and_pack_generation(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.sqlite3"
    _seed_db(db_path)
    summary = inventory_summary(db_path)
    assert summary["counts"]["documents"] == 4
    assert summary["counts"]["atoms"] == 4
    assert any(row["bucket"] == "review_pack" and row["doc_count"] == 1 for row in summary["noise_buckets"])
    assert any(row["title_key"] == "runbook" for row in summary["version_family_candidates"])

    inv_dir = tmp_path / "inventory"
    written = write_inventory_artifacts(summary, inv_dir, "20260310")
    assert len(written) == 4
    assert all(path.exists() for path in written)

    atom_pack = build_atom_pack(
        db_path,
        [{"source": "maint", "count": 2, "min_quality": 0.5}],
        seed=1,
        pack_id="manual_gold_atoms",
    )
    assert len(atom_pack["items"]) == 2

    noise_pack = build_noise_pack(db_path, limit_per_bucket=1, seed=1, pack_id="noise_atoms")
    assert any(item["bucket"] == "review_pack" for item in noise_pack["items"])

    family_pack = build_family_pack(db_path, limit=2, seed=1, pack_id="version_families")
    assert family_pack["items"][0]["member_count"] >= 2

    pack_dir = tmp_path / "packs"
    pack_paths = write_review_pack(atom_pack, pack_dir)
    assert len(pack_paths) == 2
    assert all(path.exists() for path in pack_paths)


def test_compare_review_outputs() -> None:
    gold = {
        "pack_id": "gold",
        "items": [
            {
                "item_id": "doc1::a1",
                "decision": "service_candidate",
                "reason": "high signal",
                "lesson_candidate": True,
                "version_relation": "latest",
            },
            {
                "item_id": "doc2::a2",
                "decision": "reject_noise",
                "reason": "wrapper",
                "lesson_candidate": False,
                "version_relation": "singleton",
            },
        ],
    }
    lane = {
        "pack_id": "lane",
        "items": [
            {
                "item_id": "doc1::a1",
                "decision": "service_candidate",
                "reason": "good",
                "lesson_candidate": True,
                "version_relation": "latest",
            },
            {
                "item_id": "doc2::a2",
                "decision": "review_queue",
                "reason": "not sure",
                "lesson_candidate": False,
                "version_relation": "singleton",
            },
        ],
    }
    result = compare_review_outputs(gold, lane)
    assert result["shared_items"] == 2
    assert result["decision_accuracy"] == 0.5
    assert result["service_candidate_precision"] == 1.0
    assert result["reject_noise_recall"] == 0.0


def test_compare_review_outputs_supports_family_id() -> None:
    gold = {
        "pack_id": "gold_families",
        "items": [
            {
                "family_id": "family::runbook",
                "decision": "review_queue",
                "reason": "family review",
                "lesson_candidate": False,
                "version_relation": "supersedes_prior",
            }
        ],
    }
    lane = {
        "pack_id": "lane_families",
        "items": [
            {
                "family_id": "family::runbook",
                "decision": "review_queue",
                "reason": "same",
                "lesson_candidate": False,
                "version_relation": "supersedes_prior",
            }
        ],
    }
    result = compare_review_outputs(gold, lane)
    assert result["shared_items"] == 1
    assert result["decision_accuracy"] == 1.0


def test_load_review_json_extracts_first_object(tmp_path: Path) -> None:
    path = tmp_path / "raw.txt"
    path.write_text("codex\n{\"pack_id\":\"x\",\"items\":[]}\n", encoding="utf-8")
    assert load_review_json(path)["pack_id"] == "x"
