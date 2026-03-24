from __future__ import annotations

import json
import tempfile
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.build_execution_lineage_remediation_bundle import build_bundle


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_lineage_remediation_fixture_bundle_20260311")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_db_path(obj: dict, db_path: Path) -> dict:
    normalized = json.loads(json.dumps(obj, ensure_ascii=False))
    if normalized.get("db_path") == str(db_path):
        normalized["db_path"] = "__FIXTURE_DB__"
    return normalized


def _seed_db_from_fixture(db_path: Path, seed: dict) -> None:
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    document = seed["document"]
    db.put_document(
        Document(
            doc_id=document["doc_id"],
            source=document["source"],
            project=document["project"],
            raw_ref=document["raw_ref"],
            title=document["title"],
        )
    )
    for episode in seed["episodes"]:
        db.put_episode(
            Episode(
                episode_id=episode["episode_id"],
                doc_id=document["doc_id"],
                episode_type=episode["episode_type"],
                title=episode["title"],
                summary=episode["summary"],
                start_ref=episode["start_ref"],
                end_ref=episode["end_ref"],
                time_start=float(episode["time_start"]),
                time_end=float(episode["time_end"]),
            )
        )
    for atom in seed["atoms"]:
        db.put_atom(
            Atom(
                atom_id=atom["atom_id"],
                episode_id=atom["episode_id"],
                atom_type=atom["atom_type"],
                question=atom["question"],
                answer=atom["answer"],
                canonical_question=atom["canonical_question"],
                status=atom["status"],
                promotion_status=atom["promotion_status"],
                promotion_reason=atom["promotion_reason"],
                applicability=json.dumps(atom["applicability"], ensure_ascii=False, sort_keys=True),
                valid_from=float(atom["valid_from"]),
            )
        )
    db.commit()
    db.close()


def test_execution_lineage_remediation_fixture_bundle_matches_expected_outputs() -> None:
    seed = _load_json(FIXTURE_DIR / "fixture_seed_v1.json")
    expected_audit = _load_json(FIXTURE_DIR / "identity_correlation_audit_v1.json")
    expected_manifest = _load_json(FIXTURE_DIR / "lineage_remediation_manifest_v1.json")
    expected_decision = _load_json(FIXTURE_DIR / "review_decision_input_v1.json")
    expected_summary = _load_json(FIXTURE_DIR / "summary_v1.json")
    expected_tsv = (FIXTURE_DIR / "review_decision_input_v1.tsv").read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db_path = root / "evomap.db"
        out = root / "bundle"
        _seed_db_from_fixture(db_path, seed)

        result = build_bundle(db_path=db_path, output_dir=out)
        assert result["ok"] is True

        actual_audit = _normalize_db_path(_load_json(out / "identity_correlation_audit.json"), db_path)
        actual_manifest = _normalize_db_path(_load_json(out / "lineage_remediation_manifest.json"), db_path)
        actual_decision = _normalize_db_path(_load_json(out / "review_decision_input.json"), db_path)
        actual_summary = _normalize_db_path(_load_json(out / "summary.json"), db_path)
        actual_tsv = (out / "review_decision_input.tsv").read_text(encoding="utf-8")

    assert actual_audit == expected_audit
    assert actual_manifest == expected_manifest
    assert actual_decision == expected_decision
    assert actual_summary == expected_summary
    assert actual_tsv == expected_tsv
