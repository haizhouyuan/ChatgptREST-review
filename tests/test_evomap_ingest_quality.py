from __future__ import annotations

from chatgptrest.evomap.knowledge.ingest_quality import (
    classify_atom_ingest_rejections,
    classify_archive_families,
    default_activity_promotion,
)
from chatgptrest.evomap.knowledge.extractors.base import BaseExtractor
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, PromotionStatus
from chatgptrest.evomap.knowledge.schema import Document, Episode


def test_classify_atom_ingest_rejections_flags_generic_heading_and_short_answer() -> None:
    atom = Atom(question="Files", answer="too short", canonical_question="")

    reasons = classify_atom_ingest_rejections(atom)

    assert "generic_heading" in reasons
    assert "short_answer" in reasons


def test_classify_atom_ingest_rejections_flags_path_blacklist() -> None:
    atom = Atom(
        question="/.venv/bin/python should not become a retrievable question",
        answer="Use the managed environment to execute the smoke test from repo root with the managed environment.",
        canonical_question="",
    )

    reasons = classify_atom_ingest_rejections(atom)

    assert reasons == ["path_blacklist"]


def test_classify_archive_families_marks_tool_completed_and_generic_heading() -> None:
    row = {
        "question": "Test Results",
        "canonical_question": "activity: tool.completed",
        "answer": "rg finished successfully",
    }

    families = classify_archive_families(row)

    assert families == ["low_signal_tool_completed", "generic_heading"]


def test_default_activity_promotion_archives_low_signal_tool_completed() -> None:
    promotion_status, promotion_reason = default_activity_promotion("tool.completed")

    assert promotion_status == PromotionStatus.ARCHIVED.value
    assert promotion_reason == "low_signal_activity"


def test_default_activity_promotion_keeps_high_signal_events_staged() -> None:
    promotion_status, promotion_reason = default_activity_promotion("workflow.failed")

    assert promotion_status == PromotionStatus.STAGED.value
    assert promotion_reason == "activity_ingest"


def test_base_extractor_quality_gate_skips_generic_heading_atoms(tmp_path) -> None:
    db = KnowledgeDB(str(tmp_path / "evomap.db"))
    db.init_schema()

    class DummyExtractor(BaseExtractor):
        source_name = "dummy"

        def extract_documents(self):
            yield Document(doc_id="doc_dummy", source="dummy", project="dummy", raw_ref="dummy.md", title="dummy")

        def extract_episodes(self, doc):
            yield Episode(episode_id="ep_dummy", doc_id=doc.doc_id, episode_type="md_section", title="ep")

        def extract_atoms(self, episode):
            yield Atom(atom_id="at_dummy", episode_id=episode.episode_id, question="Files", answer="too short")

    DummyExtractor(db).extract_all()

    assert db.connect().execute("SELECT COUNT(*) FROM atoms").fetchone()[0] == 0
    db.close()
