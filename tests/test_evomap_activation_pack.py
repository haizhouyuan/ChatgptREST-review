from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _seed_atom(
    db: KnowledgeDB,
    *,
    atom_id: str,
    source: str,
    answer: str,
    quality_auto: float = 0.4,
    promotion_status: str = "staged",
    stability: str = "versioned",
) -> None:
    doc = Document(doc_id=f"doc_{atom_id}", source=source, project="ChatgptREST", raw_ref=atom_id)
    ep = Episode(episode_id=f"ep_{atom_id}", doc_id=doc.doc_id, episode_type="runbook", title=atom_id)
    atom = Atom(
        atom_id=atom_id,
        episode_id=ep.episode_id,
        question=f"Q {atom_id}",
        canonical_question=f"Q {atom_id}?",
        answer=answer,
        quality_auto=quality_auto,
        promotion_status=promotion_status,
        stability=stability,
        valid_from=1000.0,
    )
    db.put_document(doc)
    db.put_episode(ep)
    db.put_atom(atom)


def test_select_activation_candidates_filters_source_and_status(tmp_path: Path) -> None:
    db = KnowledgeDB(db_path=str(tmp_path / "activation.db"))
    db.connect()
    db.init_schema()

    marker = tmp_path / "marker.txt"
    marker.write_text("ok", encoding="utf-8")
    _seed_atom(db, atom_id="at_keep", source="agent_activity", answer=f"See {marker}")
    _seed_atom(db, atom_id="at_other_source", source="planning", answer=f"See {marker}")
    _seed_atom(
        db,
        atom_id="at_candidate",
        source="agent_activity",
        answer=f"See {marker}",
        promotion_status="candidate",
    )
    _seed_atom(
        db,
        atom_id="at_superseded",
        source="agent_activity",
        answer=f"See {marker}",
        stability="superseded",
    )
    db.commit()

    module = _load_module(Path("ops/run_evomap_activation_pack.py").resolve(), "test_activation_pack_select")
    candidates = module.select_activation_candidates(
        db,
        sources=["agent_activity"],
        promotion_statuses=("staged",),
        limit=10,
    )

    assert [candidate.atom_id for candidate in candidates] == ["at_keep"]


def test_run_activation_pack_dry_run_does_not_write_scores_or_audits(tmp_path: Path) -> None:
    db = KnowledgeDB(db_path=str(tmp_path / "activation.db"))
    db.connect()
    db.init_schema()

    marker = tmp_path / "marker.txt"
    marker.write_text("ok", encoding="utf-8")
    _seed_atom(db, atom_id="at_one", source="agent_activity", answer=f"See {marker}")
    db.commit()

    module = _load_module(Path("ops/run_evomap_activation_pack.py").resolve(), "test_activation_pack_dry_run")
    summary = module.run_activation_pack(db, sources=["agent_activity"], apply=False)

    assert summary.selected == 1
    assert summary.passed == 1
    assert summary.applied is False

    atom = db.get_atom("at_one")
    assert atom is not None
    assert atom.groundedness == 0.0
    assert db.list_groundedness_audits("at_one") == []


def test_run_activation_pack_apply_writes_groundedness_and_audit(tmp_path: Path) -> None:
    db = KnowledgeDB(db_path=str(tmp_path / "activation.db"))
    db.connect()
    db.init_schema()

    marker = tmp_path / "marker.txt"
    marker.write_text("ok", encoding="utf-8")
    _seed_atom(db, atom_id="at_pass", source="agent_activity", answer=f"See {marker}")
    _seed_atom(
        db,
        atom_id="at_fail",
        source="agent_activity",
        answer="See /vol1/nonexistent/completely/fake/path/config.py",
    )
    db.commit()

    module = _load_module(Path("ops/run_evomap_activation_pack.py").resolve(), "test_activation_pack_apply")
    summary = module.run_activation_pack(db, sources=["agent_activity"], apply=True)

    assert summary.selected == 2
    assert summary.passed == 1
    assert summary.failed == 1
    assert summary.applied is True

    passed_atom = db.get_atom("at_pass")
    failed_atom = db.get_atom("at_fail")
    assert passed_atom is not None and passed_atom.groundedness >= 0.5
    assert failed_atom is not None and failed_atom.groundedness < 0.5
    assert passed_atom.promotion_status == "staged"
    assert failed_atom.promotion_status == "staged"

    passed_audits = db.list_groundedness_audits("at_pass")
    failed_audits = db.list_groundedness_audits("at_fail")
    assert len(passed_audits) == 1
    assert len(failed_audits) == 1
    assert passed_audits[0]["passed"] == 1
    assert failed_audits[0]["passed"] == 0


def test_activation_pack_cli_writes_report(tmp_path: Path) -> None:
    db_path = tmp_path / "activation.db"
    db = KnowledgeDB(db_path=str(db_path))
    db.connect()
    db.init_schema()

    marker = tmp_path / "marker.txt"
    marker.write_text("ok", encoding="utf-8")
    _seed_atom(db, atom_id="at_cli", source="agent_activity", answer=f"See {marker}")
    db.commit()
    db.close()

    module = _load_module(Path("ops/run_evomap_activation_pack.py").resolve(), "test_activation_pack_cli")
    report_path = tmp_path / "report.json"
    argv = [
        "run_evomap_activation_pack.py",
        "--db",
        str(db_path),
        "--source",
        "agent_activity",
        "--report-json",
        str(report_path),
    ]

    old_argv = sys.argv[:]
    try:
        sys.argv = argv
        rc = module.main()
    finally:
        sys.argv = old_argv

    assert rc == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["selected"] == 1
    assert report["passed"] == 1
