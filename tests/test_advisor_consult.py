"""Tests for advisor consult & recall API endpoints."""

from __future__ import annotations

import csv
import json
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, Document, Episode, PromotionStatus, Stability


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _write_planning_bundle(base: Path) -> tuple[Path, Path]:
    bundle = base / "bundle"
    pack = base / "pack"
    bundle.mkdir(parents=True, exist_ok=True)
    pack.mkdir(parents=True, exist_ok=True)
    with (pack / "docs.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
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
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_plan",
                "title": "机器人代工合同与商务底线",
                "raw_ref": "/planning/report.md",
                "family_id": "business_104",
                "review_domain": "business_104",
                "source_bucket": "planning_outputs",
                "document_role": "service_candidate",
                "final_bucket": "service_candidate",
                "service_readiness": "high",
                "is_latest_output": 1,
                "updated_at": 1,
                "updated_at_iso": "2026-03-11T00:00:00+00:00",
                "live_active_atoms": 1,
                "live_candidate_atoms": 0,
            }
        )
    with (pack / "atoms.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
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
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_plan",
                "atom_id": "at_plan",
                "episode_id": "ep_plan",
                "atom_type": "decision",
                "promotion_status": "active",
                "promotion_reason": "planning_bootstrap_review_verified",
                "quality_auto": 0.9,
                "value_auto": 0.6,
                "question": "合同与商务底线怎么设",
                "canonical_question": "合同与商务底线怎么设",
            }
        )
    (pack / "retrieval_pack.json").write_text(
        json.dumps(
            {
                "pack_type": "planning_reviewed_runtime_pack_v1",
                "doc_ids": ["doc_plan"],
                "atom_ids": ["at_plan"],
                "review_domains": ["business_104"],
                "source_buckets": ["planning_outputs"],
                "opt_in_only": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (bundle / "release_bundle_manifest.json").write_text(
        json.dumps(
            {
                "pack_dir": str(pack),
                "ready_for_explicit_consumption": True,
                "scope": {"opt_in_only": True, "default_runtime_cutover": False},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return bundle, pack


def _seed_planning_db(db_path: Path) -> None:
    db = KnowledgeDB(db_path=str(db_path))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc_plan",
            source="planning",
            project="planning",
            raw_ref="/planning/report.md",
            title="机器人代工合同与商务底线",
            meta_json=json.dumps(
                {
                    "planning_review": {
                        "review_domain": "business_104",
                        "source_bucket": "planning_outputs",
                    }
                },
                ensure_ascii=False,
            ),
        )
    )
    db.put_episode(Episode(episode_id="ep_plan", doc_id="doc_plan", episode_type="md_section", title="合同与商务底线"))
    db.put_atom(
        Atom(
            atom_id="at_plan",
            episode_id="ep_plan",
            atom_type="decision",
            question="合同与商务底线怎么设",
            answer="底线应包含付款节点、验收标准和违约退出条件。",
            canonical_question="合同与商务底线怎么设",
            status="reviewed",
            stability=Stability.VERSIONED.value,
            promotion_status=PromotionStatus.ACTIVE.value,
            quality_auto=0.92,
            groundedness=0.9,
        )
    )
    db.commit()


# ── Consult tests ─────────────────────────────────────────────────


def test_consult_requires_question(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post("/v1/advisor/consult", json={"question": ""})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "question is required"


def test_consult_rejects_invalid_models(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/consult",
        json={"question": "test", "models": ["chatgpt_pro", "invalid_model"]},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_models"
    assert "invalid_model" in detail["invalid"]


def test_consult_submits_parallel_jobs(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/consult",
        json={
            "question": "分析这个架构的3个最大风险",
            "models": ["chatgpt_pro", "gemini_deepthink"],
            "auto_context": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["consultation_id"].startswith("cons-")
    assert body["status"] == "submitted"
    assert len(body["jobs"]) == 2
    assert body["jobs"][0]["model"] == "chatgpt_pro"
    assert body["jobs"][1]["model"] == "gemini_deepthink"
    # Each job should have a job_id
    for job in body["jobs"]:
        assert isinstance(job["job_id"], str) and job["job_id"]
        assert job["status"] in ("queued", "in_progress", "cooldown")


def test_consult_with_single_model(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/consult",
        json={
            "question": "什么是量子计算",
            "models": ["qwen"],
            "auto_context": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["model"] == "qwen"


def test_consult_result_not_found(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.get("/v1/advisor/consult/nonexistent-id")
    assert r.status_code == 404


def test_consult_result_returns_status(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    # Submit first
    r1 = client.post(
        "/v1/advisor/consult",
        json={
            "question": "test query",
            "models": ["chatgpt_pro"],
            "auto_context": False,
        },
    )
    assert r1.status_code == 200
    cid = r1.json()["consultation_id"]

    # Retrieve
    r2 = client.get(f"/v1/advisor/consult/{cid}")
    assert r2.status_code == 200
    body = r2.json()
    assert body["consultation_id"] == cid
    assert body["question"] == "test query"
    assert body["status"] in ("submitted", "partial")
    # Jobs should have updated statuses
    assert len(body["jobs"]) == 1


def test_consult_default_models(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/consult",
        json={"question": "test", "auto_context": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["models"] == ["chatgpt_pro", "gemini_deepthink"]


def test_consult_research_defaults_to_deep_research_models(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/consult",
        json={"question": "调研行星滚柱丝杠产业链关键玩家和国产替代进展", "auto_context": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["models"] == ["chatgpt_dr", "gemini_dr"]
    assert body["scenario_pack"]["profile"] == "topic_research"


def test_consult_research_report_defaults_to_report_grade_models(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/consult",
        json={
            "question": "请基于公开资料输出一份行星滚柱丝杠行业研究报告，重点覆盖市场规模、核心厂商、技术路线和风险。",
            "auto_context": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["models"] == ["chatgpt_pro", "gemini_deepthink"]
    assert body["scenario_pack"]["profile"] == "research_report"


def test_consult_rejects_unsupported_task_intake_spec_version(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/consult",
        json={"question": "test", "task_intake": {"spec_version": "task-intake-v1"}},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "unsupported_task_intake_spec_version"


def test_consult_kb_context_flag(env: dict[str, Path]) -> None:
    """When auto_context=True but KB is empty, should still work."""
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/consult",
        json={"question": "test with context", "auto_context": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    # KB is empty in test env, so no context injected
    assert body["kb_context_injected"] is False


# ── Recall tests ──────────────────────────────────────────────────


def test_recall_requires_query(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post("/v1/advisor/recall", json={"query": ""})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "query is required"


def test_recall_returns_structured_response(env: dict[str, Path]) -> None:
    """Recall returns structured response with sources breakdown."""
    app = create_app()
    client = TestClient(app)
    r = client.post("/v1/advisor/recall", json={"query": "anything"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["query_id"] is None or isinstance(body["query_id"], str)
    assert isinstance(body["hits"], list)
    assert isinstance(body["total_hits"], int)
    # Verify sources breakdown is present (P0 dual-source)
    assert "sources" in body
    assert "kb" in body["sources"]
    assert "evomap" in body["sources"]
    assert "elapsed_ms" in body


@patch("chatgptrest.api.routes_consult._evomap_search", return_value=[])
def test_recall_empty_when_no_sources(mock_evomap, env: dict[str, Path]) -> None:
    """When both KB and EvoMap return nothing, recall returns empty."""
    app = create_app()
    client = TestClient(app)
    r = client.post("/v1/advisor/recall", json={"query": "nonexistent_topic_xyz"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["hits"] == []
    assert body["total_hits"] == 0
    assert body["sources"]["kb"] == 0
    assert body["sources"]["evomap"] == 0


def test_recall_respects_top_k(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post("/v1/advisor/recall", json={"query": "test", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    # Verify top_k is respected
    assert len(body["hits"]) <= 3


def test_recall_can_opt_into_planning_review_pack(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bundle, _ = _write_planning_bundle(tmp_path)
    evomap_db = tmp_path / "evomap_knowledge.db"
    _seed_planning_db(evomap_db)
    monkeypatch.setenv("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR", str(bundle))
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(evomap_db))

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/recall",
        json={"query": "合同 商务 底线", "source_scope": ["planning_review"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["sources"]["planning_review_pack"] == 1
    assert body["sources"]["kb"] == 0
    assert body["sources"]["evomap"] == 0
    assert body["source_scope"] == ["planning_review"]
    assert body["hits"][0]["source"] == "planning_review_pack"


def test_recall_does_not_use_planning_review_pack_without_opt_in(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle, _ = _write_planning_bundle(tmp_path)
    evomap_db = tmp_path / "evomap_knowledge.db"
    _seed_planning_db(evomap_db)
    monkeypatch.setenv("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR", str(bundle))
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(evomap_db))

    app = create_app()
    client = TestClient(app)
    r = client.post("/v1/advisor/recall", json={"query": "合同 商务 底线"})
    assert r.status_code == 200
    body = r.json()
    assert body["sources"]["planning_review_pack"] == 0
    assert all(hit["source"] != "planning_review_pack" for hit in body["hits"])


def test_recall_feedback_records_usage_and_feedback(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evomap_db = tmp_path / "evomap_knowledge.db"
    db = KnowledgeDB(db_path=str(evomap_db))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc_feedback",
            source="evomap",
            project="launch",
            raw_ref="/tmp/doc_feedback.md",
            title="Feedback recall document",
        )
    )
    db.put_episode(Episode(episode_id="ep_feedback", doc_id="doc_feedback", episode_type="note", title="Feedback"))
    db.put_atom(
        Atom(
            atom_id="at_feedback",
            episode_id="ep_feedback",
            atom_type="procedure",
            question="How to validate launch readiness?",
            answer="Run the validation suite and inspect the launch gate summary.",
            canonical_question="How to validate launch readiness?",
            status=AtomStatus.SCORED.value,
            stability=Stability.VERSIONED.value,
            promotion_status=PromotionStatus.ACTIVE.value,
            quality_auto=0.95,
            groundedness=0.9,
        )
    )
    db.commit()

    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(evomap_db))

    app = create_app()
    client = TestClient(app)
    recall = client.post(
        "/v1/advisor/recall",
        json={
            "query": "validate launch readiness",
            "session_id": "sess-recall-1",
            "trace_id": "trace-recall-1",
            "run_id": "run-recall-1",
            "job_id": "job-recall-1",
            "task_ref": "issue-200/p0",
            "logical_task_id": "task-200",
        },
    )
    assert recall.status_code == 200
    body = recall.json()
    assert body["ok"] is True
    assert isinstance(body["query_id"], str) and body["query_id"]
    assert body["query_identity"] == {
        "trace_id": "trace-recall-1",
        "run_id": "run-recall-1",
        "job_id": "job-recall-1",
        "task_ref": "issue-200/p0",
        "logical_task_id": "task-200",
        "identity_confidence": "authoritative",
        "session_id": "sess-recall-1",
    }
    assert body["hits"][0]["artifact_id"] == "at_feedback"

    feedback = client.post(
        "/v1/advisor/recall/feedback",
        json={
            "query_id": body["query_id"],
            "feedback_type": "accepted",
            "atom_ids": ["at_feedback"],
        },
    )
    assert feedback.status_code == 200
    feedback_body = feedback.json()
    assert feedback_body["ok"] is True
    assert feedback_body["marked_atom_ids"] == ["at_feedback"]

    with db.connect() as conn:
        query_event = conn.execute(
            """
            SELECT trace_id, run_id, job_id, task_ref, logical_task_id, identity_confidence
            FROM query_events
            WHERE query_id = ?
            """,
            (body["query_id"],),
        ).fetchone()
        used = conn.execute(
            "SELECT used_in_answer FROM retrieval_events WHERE query_id = ? AND atom_id = ?",
            (body["query_id"], "at_feedback"),
        ).fetchone()
        recorded = conn.execute(
            "SELECT feedback_type FROM answer_feedback WHERE query_id = ?",
            (body["query_id"],),
        ).fetchone()

    assert tuple(query_event) == (
        "trace-recall-1",
        "run-recall-1",
        "job-recall-1",
        "issue-200/p0",
        "task-200",
        "authoritative",
    )
    assert used is not None and used[0] == 1
    assert recorded is not None and recorded[0] == "accepted"


def test_consult_can_inject_planning_review_context_without_default_kb_context(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle, _ = _write_planning_bundle(tmp_path)
    evomap_db = tmp_path / "evomap_knowledge.db"
    _seed_planning_db(evomap_db)
    monkeypatch.setenv("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR", str(bundle))
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(evomap_db))

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/consult",
        json={
            "question": "合同 商务 底线",
            "models": ["qwen"],
            "auto_context": False,
            "source_scope": ["planning_review"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["planning_context_injected"] is True
    assert body["planning_hits_count"] == 1
    assert body["kb_context_injected"] is False


def test_consult_does_not_inject_planning_context_without_opt_in(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle, _ = _write_planning_bundle(tmp_path)
    evomap_db = tmp_path / "evomap_knowledge.db"
    _seed_planning_db(evomap_db)
    monkeypatch.setenv("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR", str(bundle))
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(evomap_db))

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/consult",
        json={
            "question": "合同 商务 底线",
            "models": ["qwen"],
            "auto_context": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["planning_context_injected"] is False
    assert body["planning_hits_count"] == 0
