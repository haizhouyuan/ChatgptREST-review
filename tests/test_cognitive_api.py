from __future__ import annotations

import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chatgptrest.api.routes_cognitive as routes_cognitive_mod
from chatgptrest.advisor.runtime import (
    get_advisor_runtime,
    get_advisor_runtime_if_ready,
    reset_advisor_runtime,
)
from chatgptrest.api.app import create_app
from chatgptrest.api.routes_cognitive import make_cognitive_router
from chatgptrest.evomap.knowledge.schema import (
    Atom,
    AtomStatus,
    Document,
    Edge,
    EdgeType,
    Entity,
    Evidence,
    Episode,
    EpisodeType,
    PromotionStatus,
    Stability,
)
from chatgptrest.kernel.memory_manager import (
    MemoryRecord,
    MemorySource,
    MemoryTier,
    SourceType,
)


def _make_router_client(auth_mode: str = "open", api_key: str = "") -> TestClient:
    reset_advisor_runtime()
    # Patch env BEFORE creating router (router reads env at creation time)
    os.environ["OPENMIND_AUTH_MODE"] = auth_mode
    if api_key:
        os.environ["OPENMIND_API_KEY"] = api_key
    else:
        os.environ.pop("OPENMIND_API_KEY", None)
    app = FastAPI()
    app.include_router(make_cognitive_router())
    return TestClient(app, raise_server_exceptions=False)


def _seed_runtime_state(session_id: str = "sess-1") -> None:
    runtime = get_advisor_runtime()

    runtime.memory.stage_and_promote(
        MemoryRecord(
            category="conversation",
            key=f"working:{session_id}:1",
            value={"role": "user", "message": "We are discussing the anhuisubstrate graph and memory design."},
            confidence=0.95,
            source=MemorySource(
                type=SourceType.USER_INPUT.value,
                agent="test",
                session_id=session_id,
            ).to_dict(),
        ),
        MemoryTier.WORKING,
        reason="test seed",
    )
    runtime.memory.stage_and_promote(
        MemoryRecord(
            category="user_profile",
            key="profile:format",
            value={"preference": "回答要结构化，先结论后细节。"},
            confidence=0.95,
            source=MemorySource(
                type=SourceType.USER_INPUT.value,
                agent="test",
                session_id=session_id,
            ).to_dict(),
        ),
        MemoryTier.SEMANTIC,
        reason="test seed",
    )

    runtime.kb_hub.index_document(
        artifact_id="kb-anhui",
        title="Anhui Project Plan",
        content="The anhuisubstrate plan unifies memory, graph, and EvoMap inside the OpenMind cognitive substrate.",
        source_path="/tmp/anhui.md",
        content_type="markdown",
        quality_score=0.9,
        auto_embed=False,
    )

    doc = Document(
        doc_id="doc_anhui",
        source="test",
        project="ChatgptREST",
        raw_ref="test://anhui",
        title="Anhui project graph seed",
        hash="seeded",
    )
    ep = Episode(
        episode_id="ep_anhui",
        doc_id=doc.doc_id,
        episode_type=EpisodeType.CHAT_SINGLE.value,
        title="graph seed",
        summary="seeded graph content",
    )
    atom = Atom(
        atom_id="at_anhui",
        episode_id=ep.episode_id,
        atom_type="decision",
        question="What is the anhuisubstrate architecture focus?",
        answer="The anhuisubstrate focus is to integrate memory, graph, and EvoMap into OpenMind.",
        canonical_question="What is the anhuisubstrate architecture focus",
        status=AtomStatus.SCORED.value,
        stability=Stability.EVERGREEN.value,
        promotion_status=PromotionStatus.ACTIVE.value,
        quality_auto=0.92,
        value_auto=0.88,
        source_quality=0.9,
    )
    atom.compute_hash()
    runtime.evomap_knowledge_db.put_document(doc)
    runtime.evomap_knowledge_db.put_episode(ep)
    runtime.evomap_knowledge_db.put_atom(atom)
    runtime.evomap_knowledge_db.put_evidence(
        Evidence(
            evidence_id="ev_anhui",
            atom_id=atom.atom_id,
            doc_id=doc.doc_id,
            span_ref="test://anhui#1",
            excerpt="anhuisubstrate integrates memory, graph, and EvoMap with explicit provenance.",
            excerpt_hash="seed-evidence",
            evidence_role="supports",
        )
    )
    runtime.evomap_knowledge_db.put_entity(
        Entity(
            entity_id="ent_anhui",
            entity_type="project",
            name="Anhui Substrate",
            normalized_name="anhuisubstrate",
        )
    )
    runtime.evomap_knowledge_db.put_edge(
        Edge(
            from_id="ent_anhui",
            to_id=atom.atom_id,
            edge_type=EdgeType.IMPLEMENTS.value,
            weight=0.9,
            from_kind="entity",
            to_kind="atom",
            meta_json='{"reason":"seeded test edge"}',
        )
    )
    runtime.evomap_knowledge_db.commit()


def _seed_graph_atom(
    *,
    atom_id: str,
    question: str,
    answer: str,
    promotion_status: str = PromotionStatus.ACTIVE.value,
) -> None:
    runtime = get_advisor_runtime()
    doc = Document(
        doc_id=f"doc_{atom_id}",
        source="test",
        project="ChatgptREST",
        raw_ref=f"test://{atom_id}",
        title=f"seed {atom_id}",
        hash=f"hash_{atom_id}",
    )
    ep = Episode(
        episode_id=f"ep_{atom_id}",
        doc_id=doc.doc_id,
        episode_type=EpisodeType.CHAT_SINGLE.value,
        title=f"episode {atom_id}",
        summary=f"seeded episode for {atom_id}",
    )
    atom = Atom(
        atom_id=atom_id,
        episode_id=ep.episode_id,
        atom_type="decision",
        question=question,
        answer=answer,
        canonical_question=question.rstrip("?"),
        status=AtomStatus.SCORED.value,
        stability=Stability.EVERGREEN.value,
        promotion_status=promotion_status,
        quality_auto=0.96,
        value_auto=0.9,
        source_quality=0.9,
    )
    atom.compute_hash()
    runtime.evomap_knowledge_db.put_document(doc)
    runtime.evomap_knowledge_db.put_episode(ep)
    runtime.evomap_knowledge_db.put_atom(atom)
    runtime.evomap_knowledge_db.put_evidence(
        Evidence(
            evidence_id=f"ev_{atom_id}",
            atom_id=atom.atom_id,
            doc_id=doc.doc_id,
            span_ref=f"test://{atom_id}#1",
            excerpt=answer,
            excerpt_hash=f"evidence_{atom_id}",
            evidence_role="supports",
        )
    )
    runtime.evomap_knowledge_db.commit()


def test_context_resolve_returns_memory_graph_policy_and_prompt_prefix() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/context/resolve",
        json={
            "query": "Continue the anhuisubstrate design and focus on graph and memory.",
            "session_key": "sess-1",
            "sources": ["memory", "knowledge", "graph", "policy"],
            "graph_scopes": ["personal"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "Recent Conversation" in body["prompt_prefix"]
    assert "Relevant Knowledge" in body["prompt_prefix"]
    assert "EvoMap Knowledge" in body["prompt_prefix"]
    kinds = {block["kind"] for block in body["context_blocks"]}
    assert {"memory", "knowledge", "graph", "policy"} <= kinds
    assert body["degraded"] is False
    assert body["metadata"]["source_planes"]["memory"] == "runtime_working"
    assert body["metadata"]["source_planes"]["knowledge"] == "kb_working_set"
    assert body["metadata"]["source_planes"]["graph"] == "canonical_knowledge"
    assert body["metadata"]["source_planes"]["policy"] == "runtime_policy"
    retrieval_plan = {item["kind"]: item for item in body["metadata"]["retrieval_plan"]}
    assert retrieval_plan["memory"]["resolved"] is True
    assert retrieval_plan["knowledge"]["resolved"] is True
    assert retrieval_plan["graph"]["resolved"] is True
    assert retrieval_plan["graph"]["plane"] == "canonical_knowledge"
    assert retrieval_plan["policy"]["reason"] == "policy hints were derived from resolved context and route heuristics"


def test_context_resolve_filters_sources_and_marks_repo_graph_degraded() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/context/resolve",
        json={
            "query": "Only use repo graph for anhuisubstrate.",
            "session_key": "sess-1",
            "sources": ["graph"],
            "graph_scopes": ["repo"],
            "repo": "ChatgptREST",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_sources"] == ["graph"]
    assert all(block["kind"] == "graph" for block in body["context_blocks"])
    assert body["degraded"] is True
    assert "repo_graph" in body["degraded_sources"]


def test_graph_query_returns_personal_graph_nodes_edges_and_evidence() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/graph/query",
        json={
            "query": "anhuisubstrate graph",
            "scopes": ["personal_graph"],
            "limit": 10,
            "include_edges": True,
            "include_paths": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    kinds = {node["kind"] for node in body["nodes"]}
    assert {"atom", "episode", "document", "entity"} <= kinds
    assert any(edge["edge_type"] == "implements" for edge in body["edges"])
    assert any(item["kind"] == "evidence" for item in body["evidence"])
    assert "knowledge_db" in body["sources_used"]
    assert body["degraded_sources"] == []


def test_graph_query_marks_repo_graph_degraded_without_adapter() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/graph/query",
        json={
            "query": "anhuisubstrate",
            "scopes": ["repo_graph"],
            "repo": "ChatgptREST",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["nodes"] == []
    assert body["sources_used"] == []
    assert "repo_graph" in body["degraded_sources"]


def test_runtime_retrieval_paths_keep_staged_atoms_out_of_hot_path_but_visible_to_diagnostics() -> None:
    client = _make_router_client()
    _seed_runtime_state()
    _seed_graph_atom(
        atom_id="at_stage_only",
        question="What does stageonlysignal mean for runtime retrieval?",
        answer="stageonlysignal marks staged-only diagnostic guidance for graph investigation.",
        promotion_status=PromotionStatus.STAGED.value,
    )

    context_response = client.post(
        "/v2/context/resolve",
        json={
            "query": "stageonlysignal",
            "session_key": "sess-1",
            "sources": ["knowledge"],
        },
    )

    assert context_response.status_code == 200
    context_body = context_response.json()
    assert context_body["ok"] is True
    assert context_body["metadata"]["promotion_status_counts"] == {}
    assert not any(
        block["source_type"] == "evomap" and "stageonlysignal" in block["text"]
        for block in context_body["context_blocks"]
    )

    graph_response = client.post(
        "/v2/graph/query",
        json={
            "query": "stageonlysignal",
            "scopes": ["personal_graph"],
            "limit": 10,
        },
    )

    assert graph_response.status_code == 200
    graph_body = graph_response.json()
    assert graph_body["ok"] is True
    assert graph_body["metadata"]["promotion_status_counts"] == {"staged": 1}
    assert any(
        node["id"] == "at_stage_only"
        and node["metadata"].get("promotion_status") == PromotionStatus.STAGED.value
        for node in graph_body["nodes"]
        if node["kind"] == "atom"
    )


def test_graph_query_normalizes_structured_repo_graph_payload(tmp_path, monkeypatch) -> None:
    helper = tmp_path / "gitnexus_stub.py"
    helper.write_text(
        """
import json

payload = {
    "processes": [
        {
            "id": "proc_repo_flow",
            "summary": "Resolve graph query -> ranked symbols",
            "priority": 0.91,
            "symbol_count": 2,
            "process_type": "cross_community",
            "step_count": 2,
        }
    ],
    "process_symbols": [
        {
            "id": "Function:chatgptrest/api/routes_cognitive.py:graph_query:1",
            "name": "graph_query",
            "filePath": "chatgptrest/api/routes_cognitive.py",
            "startLine": 1,
            "endLine": 10,
            "module": "Api",
            "process_id": "proc_repo_flow",
            "step_index": 1,
        },
        {
            "id": "Class:chatgptrest/cognitive/graph_service.py:GraphQueryService:1",
            "name": "GraphQueryService",
            "filePath": "chatgptrest/cognitive/graph_service.py",
            "startLine": 1,
            "endLine": 20,
            "module": "Cognitive",
            "process_id": "proc_repo_flow",
            "step_index": 2,
        },
    ],
    "definitions": [
        {
            "id": "File:chatgptrest/cognitive/graph_service.py",
            "name": "graph_service.py",
            "filePath": "chatgptrest/cognitive/graph_service.py",
        }
    ],
}
print(json.dumps(payload))
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENMIND_ENABLE_GITNEXUS_CLI", "1")
    monkeypatch.setenv("OPENMIND_GITNEXUS_QUERY_CMD", f"{sys.executable} {helper}")
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/graph/query",
        json={
            "query": "graph service cognitive substrate",
            "scopes": ["repo_graph"],
            "repo": "ChatgptREST",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert any(node["kind"] == "repo_symbol" for node in body["nodes"])
    assert any(item["kind"] == "repo_graph_process" for item in body["evidence"])
    assert any(path["edge_types"] == ["step_in_process"] for path in body["paths"])
    assert body["degraded_sources"] == []
    assert "gitnexus_cli" in body["sources_used"]


def test_knowledge_ingest_writes_kb_and_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_COGNITIVE_INGEST_DIR", str(tmp_path))
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/knowledge/ingest",
        json={
            "items": [
                {
                    "title": "Anhui execution note",
                    "content": "The anhuisubstrate execution shell should send telemetry into OpenMind and persist graph structure.",
                    "trace_id": "tr-ingest-1",
                    "session_key": "sess-1",
                    "source_system": "openclaw",
                    "source_ref": "openclaw://skill/obsidian",
                    "project_id": "ChatgptREST",
                    "entities": [{"name": "OpenClaw", "entity_type": "platform"}],
                }
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    item = body["results"][0]
    assert item["ok"] is True
    assert item["success"] is True
    assert item["accepted"] is True
    assert item["knowledge_plane"] == "canonical_knowledge"
    assert item["write_path"] == "canonical_projected"
    assert item["file_path"].endswith(".md")
    assert item["graph_refs"]["atom_id"].startswith("at_ingest_")
    assert item["graph_refs"]["trust_level"] == "staged_low_trust"
    assert item["graph_refs"]["scores"]["quality_auto"] <= 0.6
    runtime = get_advisor_runtime()
    assert runtime.kb_hub.search("anhuisubstrate execution shell", top_k=3, auto_embed=False)
    graph_atom = runtime.evomap_knowledge_db.get_atom(item["graph_refs"]["atom_id"])
    assert graph_atom is not None
    assert graph_atom.status == AtomStatus.CANDIDATE.value


def test_memory_capture_dedups_and_emits_audit_evidence() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    payload = {
        "items": [
            {
                "title": "Response preference",
                "content": "Always answer with the decision first and then give structured bullets.",
                "trace_id": "tr-memory-capture-1",
                "session_key": "sess-1",
                "source_ref": "openclaw://session/sess-1/manual-capture",
            }
        ]
    }
    first = client.post("/v2/memory/capture", json=payload)
    second = client.post("/v2/memory/capture", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    first_item = first.json()["results"][0]
    second_item = second.json()["results"][0]
    assert first_item["ok"] is True
    assert first_item["tier"] == "episodic"
    assert first_item["quality_gate"]["allowed"] is True
    assert second_item["ok"] is True
    assert second_item["quality_gate"]["allowed"] is True
    assert second_item["duplicate"] is True
    assert first_item["record_id"] == second_item["record_id"]
    runtime = get_advisor_runtime()
    captured = runtime.memory.get_episodic(category="captured_memory", limit=10)
    assert len(captured) == 1
    audit = runtime.memory.audit_trail(first_item["record_id"])
    assert any(entry["action"] == "update" for entry in audit)
    events = runtime.event_bus.query(trace_id="tr-memory-capture-1")
    assert any(event.event_type == "memory.capture" for event in events)


def test_memory_capture_blocks_sensitive_content_via_server_policy_gate() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/memory/capture",
        json={
            "items": [
                {
                    "title": "Sensitive note",
                    "content": "Reach me at ops@example.com and inspect /vol1/secret/token.txt before continuing.",
                    "trace_id": "tr-memory-capture-blocked",
                    "session_key": "sess-sensitive",
                    "source_ref": "openclaw://session/sess-sensitive/manual-capture",
                }
            ]
        },
    )

    assert response.status_code == 200
    item = response.json()["results"][0]
    assert item["ok"] is False
    assert item["record_id"] == ""
    assert item["message"] == "Blocked by: security"
    assert item["quality_gate"]["allowed"] is False
    assert item["quality_gate"]["blocked_by"] == ["security"]
    runtime = get_advisor_runtime()
    captured = runtime.memory.get_episodic(category="captured_memory", limit=10)
    assert captured == []
    events = runtime.event_bus.query(trace_id="tr-memory-capture-blocked")
    assert any(event.event_type == "memory.capture.blocked" for event in events)


def test_context_resolve_includes_cross_session_captured_memory_block() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    capture = client.post(
        "/v2/memory/capture",
        json={
            "items": [
                {
                    "title": "Writing preference",
                    "content": "When writing status updates, lead with the conclusion and keep the rest in short bullets.",
                    "trace_id": "tr-memory-capture-2",
                    "session_key": "sess-capture",
                    "account_id": "acct-shared",
                    "source_ref": "openclaw://session/sess-capture/agent_end",
                }
            ]
        },
    )
    assert capture.status_code == 200

    response = client.post(
        "/v2/context/resolve",
        json={
            "query": "How should you write status updates for me?",
            "session_key": "sess-other",
            "account_id": "acct-shared",
            "sources": ["memory", "policy"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    captured_block = next(block for block in body["context_blocks"] if block["source_type"] == "captured")
    assert captured_block["title"] == "Remembered Guidance"
    assert "lead with the conclusion" in captured_block["text"]
    assert "## Remembered Guidance" in body["prompt_prefix"]
    assert body["metadata"]["captured_memory_scope"] == "account_cross_session"


def test_memory_capture_persists_across_runtime_reset_with_audit_trail() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    capture = client.post(
        "/v2/memory/capture",
        json={
            "items": [
                {
                    "title": "Audit preference",
                    "content": "Remember that audit findings should be listed by severity before any summary.",
                    "trace_id": "tr-memory-capture-3",
                    "session_key": "sess-origin",
                    "account_id": "acct-persist",
                    "source_ref": "openclaw://session/sess-origin/manual-capture",
                }
            ]
        },
    )
    assert capture.status_code == 200
    record_id = capture.json()["results"][0]["record_id"]

    reset_advisor_runtime()
    client = _make_router_client()

    response = client.post(
        "/v2/context/resolve",
        json={
            "query": "How should audit findings be formatted?",
            "session_key": "sess-fresh",
            "account_id": "acct-persist",
            "sources": ["memory"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    captured_block = next(block for block in body["context_blocks"] if block["source_type"] == "captured")
    assert "listed by severity" in captured_block["text"]

    runtime = get_advisor_runtime()
    audit = runtime.memory.audit_trail(record_id)
    assert [entry["action"] for entry in audit[:2]] == ["stage", "promote"]
    events = runtime.event_bus.query(trace_id="tr-memory-capture-3")
    assert any(event.event_type == "memory.capture" for event in events)


def test_memory_capture_reports_identity_gaps_when_provenance_is_partial() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    capture = client.post(
        "/v2/memory/capture",
        json={
            "items": [
                {
                    "title": "Partial provenance note",
                    "content": "Remember this preference even if the request omitted most identity fields.",
                    "trace_id": "tr-memory-capture-identity",
                }
            ]
        },
    )

    assert capture.status_code == 200
    item = capture.json()["results"][0]
    assert item["ok"] is True
    assert item["provenance_quality"] == "partial"
    assert item["quality_gate"]["allowed"] is True
    assert set(item["identity_gaps"]) == {
        "missing_source_ref",
        "missing_session_key",
        "missing_agent_id",
        "missing_account_id",
        "missing_thread_id",
    }


def test_context_resolve_blocks_anonymous_memory_recall_and_marks_request_degraded() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/context/resolve",
        json={
            "query": "Recall anything useful about my response preferences.",
            "sources": ["memory", "policy"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert "memory_identity_missing" in body["degraded_sources"]
    assert "captured_memory_identity_missing" in body["degraded_sources"]
    assert body["metadata"]["identity_scope"] == "partial"
    assert body["metadata"]["captured_memory_scope"] == "blocked_missing_identity"
    assert not any(block["source_type"] == "captured" for block in body["context_blocks"])
    assert set(body["metadata"]["identity_gaps"]) == {
        "missing_session_key",
        "missing_agent_id",
        "missing_account_id",
        "missing_thread_id",
    }


def test_plugin_style_memory_contract_stays_aligned_with_api_behavior() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    capture = client.post(
        "/v2/memory/capture",
        json={
            "items": [
                {
                    "title": "Plugin style memory",
                    "content": "When sending progress updates, lead with what changed and what remains blocked.",
                    "trace_id": "tr-plugin-style",
                    "session_key": "sess-plugin",
                    "agent_id": "agent-main",
                    "source_system": "openclaw",
                    "source_ref": "openclaw://session/sess-plugin/manual-capture",
                }
            ]
        },
    )
    assert capture.status_code == 200
    capture_item = capture.json()["results"][0]
    assert capture_item["ok"] is True
    assert capture_item["tier"] == "episodic"
    assert capture_item["provenance_quality"] == "partial"
    assert set(capture_item["identity_gaps"]) == {"missing_account_id", "missing_thread_id"}

    response = client.post(
        "/v2/context/resolve",
        json={
            "query": "How should progress updates be written?",
            "session_key": "sess-plugin",
            "agent_id": "agent-main",
            "sources": ["memory", "policy"],
            "graph_scopes": ["personal"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    captured_block = next(block for block in body["context_blocks"] if block["source_type"] == "captured")
    assert "lead with what changed" in captured_block["text"]
    assert "## Remembered Guidance" in body["prompt_prefix"]
    assert body["resolved_sources"] == ["memory", "policy"]
    assert body["metadata"]["identity_scope"] == "partial"
    assert body["metadata"]["captured_memory_scope"] == "session"
    assert set(body["metadata"]["identity_gaps"]) == {"missing_account_id", "missing_thread_id"}


def test_memory_capture_role_id_preserves_component_identity_and_scopes_recall() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    capture = client.post(
        "/v2/memory/capture",
        json={
            "items": [
                {
                    "title": "Devops capture",
                    "content": "Remember the driver incident checklist for devops runs.",
                    "trace_id": "tr-role-devops",
                    "session_key": "sess-role",
                    "account_id": "acct-devops",
                    "agent_id": "agent-main",
                    "role_id": "devops",
                    "source_system": "openclaw",
                    "source_ref": "openclaw://session/sess-role/manual-capture",
                }
            ]
        },
    )
    assert capture.status_code == 200

    runtime = get_advisor_runtime()
    role_hits = runtime.memory.get_episodic(
        category="captured_memory",
        agent_id="agent-main",
        role_id="devops",
        limit=10,
    )
    assert len(role_hits) == 1
    src = role_hits[0].source if isinstance(role_hits[0].source, dict) else {}
    assert src["agent"] == "agent-main"
    assert src["role"] == "devops"

    response = client.post(
        "/v2/context/resolve",
        json={
            "query": "What is the devops driver checklist?",
            "session_key": "sess-fresh",
            "account_id": "acct-devops",
            "agent_id": "agent-main",
            "role_id": "devops",
            "sources": ["memory", "policy"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["role_id"] == "devops"
    captured_block = next(block for block in body["context_blocks"] if block["source_type"] == "captured")
    assert "driver incident checklist" in captured_block["text"]
    assert body["metadata"]["captured_memory_scope"] == "account_cross_session"


def test_context_resolve_cross_session_requires_account_identity() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    capture = client.post(
        "/v2/memory/capture",
        json={
            "items": [
                {
                    "title": "Cross-session account memory",
                    "content": "Remember this only across sessions for the same account.",
                    "trace_id": "tr-account-cross-session",
                    "session_key": "sess-capture",
                    "account_id": "acct-1",
                    "source_ref": "openclaw://session/sess-capture/manual-capture",
                }
            ]
        },
    )
    assert capture.status_code == 200

    blocked = client.post(
        "/v2/context/resolve",
        json={
            "query": "What should be remembered across sessions?",
            "session_key": "sess-other",
            "sources": ["memory", "policy"],
        },
    )
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert not any(block["source_type"] == "captured" for block in blocked_body["context_blocks"])

    allowed = client.post(
        "/v2/context/resolve",
        json={
            "query": "What should be remembered across sessions?",
            "session_key": "sess-other",
            "account_id": "acct-1",
            "sources": ["memory", "policy"],
        },
    )
    assert allowed.status_code == 200
    allowed_body = allowed.json()
    captured_block = next(block for block in allowed_body["context_blocks"] if block["source_type"] == "captured")
    assert "same account" in captured_block["text"]
    assert allowed_body["metadata"]["captured_memory_scope"] == "account_cross_session"


def test_context_resolve_role_kb_hint_prefers_tagged_hits_without_enforcing() -> None:
    client = _make_router_client()
    _seed_runtime_state()
    runtime = get_advisor_runtime()
    runtime.kb_hub.index_document(
        artifact_id="kb-devops-runbook",
        title="Devops Driver Runbook",
        content="Driver MCP runbook guidance for incident recovery and OpenClaw service repair.",
        source_path="/tmp/devops-runbook.md",
        content_type="markdown",
        quality_score=0.92,
        tags=["chatgptrest", "ops", "driver"],
        auto_embed=False,
    )
    runtime.kb_hub.index_document(
        artifact_id="kb-generic-driver",
        title="Generic Driver Notes",
        content="Driver MCP guidance and generic handling notes for assorted systems.",
        source_path="/tmp/generic-driver.md",
        content_type="markdown",
        quality_score=0.92,
        auto_embed=False,
    )

    response = client.post(
        "/v2/context/resolve",
        json={
            "query": "driver mcp guidance",
            "session_key": "sess-role-kb",
            "role_id": "devops",
            "sources": ["knowledge", "policy"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["role_id"] == "devops"
    assert body["metadata"]["kb_scope_mode"] == "hint"
    assert "ops" in body["metadata"]["kb_scope_tags"]
    kb_block = next(block for block in body["context_blocks"] if block["source_type"] == "kb")
    assert kb_block["provenance"][0]["artifact_id"] == "kb-devops-runbook"


def test_duplicate_ingest_preserves_first_evidence(tmp_path, monkeypatch) -> None:
    """Ingesting the same content twice with different source_ref preserves both evidence records."""
    monkeypatch.setenv("OPENMIND_COGNITIVE_INGEST_DIR", str(tmp_path))
    client = _make_router_client()
    _seed_runtime_state()

    shared_payload = {
        "title": "Shared knowledge note",
        "content": "The EvoMap pipeline integrates knowledge extraction, scoring, and retrieval.",
        "session_key": "sess-1",
    }

    # First ingest from source A
    r1 = client.post(
        "/v2/knowledge/ingest",
        json={"items": [{**shared_payload, "trace_id": "tr-first", "source_ref": "source-A"}]},
    )
    assert r1.status_code == 200
    item1 = r1.json()["results"][0]
    assert item1["ok"] is True

    # Second ingest of same content from source B
    r2 = client.post(
        "/v2/knowledge/ingest",
        json={"items": [{**shared_payload, "trace_id": "tr-second", "source_ref": "source-B"}]},
    )
    assert r2.status_code == 200
    item2 = r2.json()["results"][0]
    assert item2["ok"] is True

    # Atom ID should be the same (content-based dedup)
    assert item1["graph_refs"]["atom_id"] == item2["graph_refs"]["atom_id"]

    # Evidence IDs should be DIFFERENT (source-aware)
    assert item1["graph_refs"]["evidence_id"] != item2["graph_refs"]["evidence_id"]

    # Both evidence records should exist in the DB
    runtime = get_advisor_runtime()
    ev_list = runtime.evomap_knowledge_db.list_evidence_for_atom(item1["graph_refs"]["atom_id"])
    ev_ids = {e.evidence_id for e in ev_list}
    assert item1["graph_refs"]["evidence_id"] in ev_ids
    assert item2["graph_refs"]["evidence_id"] in ev_ids
    assert len(ev_ids) >= 2


def test_ingest_skips_graph_mirror_when_policy_mode_blocks_it(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_COGNITIVE_INGEST_DIR", str(tmp_path))
    monkeypatch.setenv("OPENMIND_COGNITIVE_GRAPH_MIRROR_MODE", "blocked")
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/knowledge/ingest",
        json={
            "items": [
                {
                    "title": "No graph growth",
                    "content": "This should write an artifact without mirroring into the repo-local graph DB.",
                    "trace_id": "tr-no-graph-growth",
                    "session_key": "sess-1",
                    "source_ref": "test://no-growth",
                }
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    item = body["results"][0]
    assert item["ok"] is True
    assert item["accepted"] is True
    assert item["success"] is True
    assert item["knowledge_plane"] == "canonical_knowledge"
    assert item["write_path"] == "canonical_policy_blocked"
    assert item["graph_refs"]["status"] == "skipped_policy"
    assert item["graph_refs"]["graph_mode"] == "blocked"
    events = get_advisor_runtime().event_bus.query(trace_id="tr-no-graph-growth")
    kb_events = [event for event in events if event.event_type == "kb.writeback"]
    assert len(kb_events) == 1
    assert kb_events[0].data["graph_mode"] == "blocked"
    assert kb_events[0].data["graph_skipped_policy"] is True


def test_mirror_failure_returns_partial_and_emits_event(tmp_path, monkeypatch) -> None:
    """Graph mirror failure → artifact written, event with graph_failed=True, result partial."""
    monkeypatch.setenv("OPENMIND_COGNITIVE_INGEST_DIR", str(tmp_path))
    client = _make_router_client()
    _seed_runtime_state()

    runtime = get_advisor_runtime()
    original_put = runtime.evomap_knowledge_db.put_document_if_absent

    def _explode(*args, **kwargs):
        raise RuntimeError("simulated graph write failure")

    # Monkey-patch the graph write to fail
    runtime.evomap_knowledge_db.put_document_if_absent = _explode

    response = client.post(
        "/v2/knowledge/ingest",
        json={
            "items": [
                {
                    "title": "Graph failure test",
                    "content": "This should cause a partial failure.",
                    "trace_id": "tr-fail",
                    "session_key": "sess-1",
                    "source_ref": "test://failure",
                }
            ]
        },
    )

    # Restore so other tests aren't affected
    runtime.evomap_knowledge_db.put_document_if_absent = original_put

    assert response.status_code == 200
    body = response.json()
    item = body["results"][0]

    # Artifact was written (accepted=True) but graph failed (ok=False)
    assert item["ok"] is False
    assert item["success"] is False
    assert item["accepted"] is True
    assert item["knowledge_plane"] == "canonical_knowledge"
    assert item["write_path"] == "canonical_partial_failure"
    assert item["file_path"].endswith(".md")

    # Batch-level ok should also be False
    assert body["ok"] is False

    # But message should indicate partial failure
    assert item["message"] == "ingested_partial"

    # graph_refs should contain error details
    assert item["graph_refs"]["status"] == "partial_failure"
    assert "simulated graph write failure" in item["graph_refs"]["error"]

    # Event should have been emitted with graph_failed flag
    events = runtime.event_bus.query(trace_id="tr-fail")
    assert len(events) >= 1
    kb_events = [e for e in events if e.event_type == "kb.writeback"]
    assert len(kb_events) == 1
    assert kb_events[0].data["graph_failed"] is True
    assert "simulated graph write failure" in kb_events[0].data["graph_error"]


def test_graph_query_filters_by_project_id(tmp_path, monkeypatch) -> None:
    """Ingest to project A + B → query with project_id=A → only A results."""
    monkeypatch.setenv("OPENMIND_COGNITIVE_INGEST_DIR", str(tmp_path))
    client = _make_router_client()
    _seed_runtime_state()

    # Ingest item into project A
    r1 = client.post(
        "/v2/knowledge/ingest",
        json={"items": [{
            "title": "Project A knowledge",
            "content": "Alpha subsystem design patterns for architecture.",
            "project_id": "project-alpha",
            "session_key": "sess-1",
        }]},
    )
    assert r1.status_code == 200
    assert r1.json()["results"][0]["ok"] is True

    # Ingest item into project B
    r2 = client.post(
        "/v2/knowledge/ingest",
        json={"items": [{
            "title": "Project B knowledge",
            "content": "Beta subsystem design patterns for architecture.",
            "project_id": "project-beta",
            "session_key": "sess-1",
        }]},
    )
    assert r2.status_code == 200
    assert r2.json()["results"][0]["ok"] is True

    # Query with project_id=project-alpha → should only get A results
    r3 = client.post(
        "/v2/graph/query",
        json={"query": "design patterns architecture", "project_id": "project-alpha"},
    )
    assert r3.status_code == 200
    nodes = r3.json()["nodes"]
    atom_nodes = [n for n in nodes if n["kind"] == "atom"]
    # Should contain project-alpha atom, not project-beta
    titles = [n["title"] for n in atom_nodes]
    assert any("Project A" in t for t in titles), f"Expected Project A in {titles}"
    assert not any("Project B" in t for t in titles), f"Unexpected Project B in {titles}"


def test_graph_query_without_project_returns_all(tmp_path, monkeypatch) -> None:
    """No project_id → returns results from all projects."""
    monkeypatch.setenv("OPENMIND_COGNITIVE_INGEST_DIR", str(tmp_path))
    client = _make_router_client()
    _seed_runtime_state()

    # Ingest items into two different projects
    for project, label in [("proj-x", "X"), ("proj-y", "Y")]:
        client.post(
            "/v2/knowledge/ingest",
            json={"items": [{
                "title": f"Knowledge from {label}",
                "content": f"Unique content about microservices from project {label}.",
                "project_id": project,
                "session_key": "sess-1",
            }]},
        )

    # Query without project_id → should return both
    r = client.post(
        "/v2/graph/query",
        json={"query": "microservices"},
    )
    assert r.status_code == 200
    nodes = r.json()["nodes"]
    atom_nodes = [n for n in nodes if n["kind"] == "atom"]
    titles = [n["title"] for n in atom_nodes]
    assert any("X" in t for t in titles), f"Expected X in {titles}"
    assert any("Y" in t for t in titles), f"Expected Y in {titles}"


def test_telemetry_ingest_records_eventbus_observer_and_memory() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/telemetry/ingest",
        json={
            "trace_id": "tr-telemetry-1",
            "session_key": "sess-1",
            "events": [
                {
                    "type": "tool.completed",
                    "source": "openclaw",
                    "domain": "execution",
                    "data": {"tool": "obsidian_search", "ok": True, "latency_ms": 183},
                },
                {
                    "type": "user.feedback",
                    "source": "openclaw",
                    "domain": "quality",
                    "data": {"rating": "negative", "reason": "missed prior decision"},
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["recorded"] == 2
    runtime = get_advisor_runtime()
    assert len(runtime.event_bus.query(trace_id="tr-telemetry-1")) == 2
    signals = runtime.observer.by_trace("tr-telemetry-1")
    assert len(signals) == 2
    assert all(signal.data.get("session_id") == "sess-1" for signal in signals)
    episodic = runtime.memory.get_episodic(category="execution_feedback", limit=20)
    assert any(rec.category == "execution_feedback" for rec in episodic)


def test_telemetry_ingest_preserves_identity_contract_fields() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/telemetry/ingest",
        json={
            "trace_id": "tr-telemetry-identity",
            "session_key": "sess-identity",
            "events": [
                {
                    "type": "tool.completed",
                    "source": "codex",
                    "domain": "execution",
                    "task_ref": "issue-200/p0",
                    "logical_task_id": "task-200",
                    "job_id": "job-123",
                    "issue_id": "issue-200",
                    "repo_name": "ChatgptREST",
                    "repo_path": "/vol1/1000/projects/ChatgptREST",
                    "repo_branch": "master",
                    "provider": "openai",
                    "model": "gpt-5",
                    "agent_name": "codex",
                    "data": {"tool": "rg", "ok": True},
                }
            ],
        },
    )

    assert response.status_code == 200
    runtime = get_advisor_runtime()
    events = runtime.event_bus.query(trace_id="tr-telemetry-identity")
    assert len(events) == 1
    payload = events[0].data
    assert payload["task_ref"] == "issue-200/p0"
    assert payload["logical_task_id"] == "task-200"
    assert payload["identity_confidence"] == "authoritative"
    assert payload["job_id"] == "job-123"
    assert payload["issue_id"] == "issue-200"
    assert payload["repo_name"] == "ChatgptREST"
    assert payload["provider"] == "openai"
    assert payload["model"] == "gpt-5"


def test_telemetry_ingest_accepts_flat_closeout_event_envelope() -> None:
    client = _make_router_client()

    response = client.post(
        "/v2/telemetry/ingest",
        json={
            "event_type": "agent.task.closeout",
            "session_id": "sess-closeout",
            "source": "codex",
            "domain": "agent",
            "event_id": "evt-closeout-1",
            "repo_name": "ChatgptREST",
            "data": {"status": "completed", "summary": "closeout ok"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["recorded"] == 1


def test_policy_hints_returns_route_quality_gate_and_retrieval_plan() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    response = client.post(
        "/v2/policy/hints",
        json={
            "query": "帮我写一份 anhuisubstrate 的结构化报告，并结合 repo graph 给出风险。",
            "session_key": "sess-1",
            "repo": "ChatgptREST",
            "graph_scopes": ["personal", "repo"],
            "estimated_tokens": 500,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["preferred_route"] == "report"
    assert body["quality_gate"]["allowed"] is True
    assert any("repo_graph" in item or "/v2/graph/query" in item for item in body["retrieval_plan"] + body["hints"])
    assert "repo_graph" in body["degraded_sources"]


def test_policy_hints_includes_execution_summary_from_telemetry() -> None:
    client = _make_router_client()
    _seed_runtime_state()

    telemetry = client.post(
        "/v2/telemetry/ingest",
        json={
            "trace_id": "tr-telemetry-2",
            "session_key": "sess-1",
            "events": [
                {
                    "type": "tool.failed",
                    "source": "openclaw",
                    "domain": "execution",
                    "data": {"tool": "obsidian_search", "error": "timeout"},
                },
                {
                    "type": "user.feedback",
                    "source": "openclaw",
                    "domain": "quality",
                    "data": {"rating": "negative", "reason": "missed prior decision"},
                },
            ],
        },
    )
    assert telemetry.status_code == 200

    response = client.post(
        "/v2/policy/hints",
        json={
            "query": "继续 anhuisubstrate 方案，并注意之前失败的检索路径。",
            "session_key": "sess-1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["execution_summary"]["tool_failures"]["obsidian_search"] == 1
    assert body["execution_summary"]["negative_feedback_count"] == 1
    assert any("obsidian_search" in hint for hint in body["hints"])


def test_cognitive_router_enforces_openmind_api_key() -> None:
    client = _make_router_client(auth_mode="strict", api_key="secret-key")

    r = client.post("/v2/context/resolve", json={"query": "hello"})
    assert r.status_code == 401

    ok = client.post(
        "/v2/context/resolve",
        json={"query": "hello"},
        headers={"X-Api-Key": "secret-key"},
    )
    assert ok.status_code == 200


def test_cognitive_health_is_exempt_from_strict_auth() -> None:
    client = _make_router_client(auth_mode="strict", api_key="secret-key")
    response = client.get("/v2/cognitive/health")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "not_initialized"
    assert response.json()["runtime_ready"] is False
    assert get_advisor_runtime_if_ready() is None


def test_cognitive_health_returns_503_on_runtime_failure(monkeypatch) -> None:
    client = _make_router_client(auth_mode="open")

    def _boom():
        raise RuntimeError("runtime boot failed")

    monkeypatch.setattr(routes_cognitive_mod, "get_advisor_runtime_if_ready", _boom)
    response = client.get("/v2/cognitive/health")

    assert response.status_code == 503
    assert response.json()["ok"] is False


def test_cognitive_router_rate_limits() -> None:
    os.environ["OPENMIND_RATE_LIMIT"] = "1"
    client = _make_router_client(auth_mode="open")

    first = client.post("/v2/context/resolve", json={"query": "hello"})
    second = client.post("/v2/context/resolve", json={"query": "hello again"})

    assert first.status_code == 200
    assert second.status_code == 429


def test_create_app_includes_context_resolve_route() -> None:
    os.environ["OPENMIND_AUTH_MODE"] = "open"
    reset_advisor_runtime()
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post("/v2/context/resolve", json={"query": "hello"})
    assert response.status_code == 200


def test_default_auth_rejects_unauthenticated_writes() -> None:
    """Default strict mode rejects writes when no API key is configured."""
    client = _make_router_client(auth_mode="strict")

    r = client.post("/v2/context/resolve", json={"query": "hello"})
    assert r.status_code == 503
    assert "API key not configured" in r.json()["detail"]

    r2 = client.post("/v2/knowledge/ingest", json={"items": [{"title": "x", "content": "y"}]})
    assert r2.status_code == 503


def test_explicit_open_mode_allows_unauthenticated_writes() -> None:
    """Explicit open mode allows writes without API key."""
    client = _make_router_client(auth_mode="open")
    _seed_runtime_state()

    r = client.post("/v2/context/resolve", json={"query": "hello"})
    assert r.status_code == 200


def test_create_app_scopes_bearer_auth_to_v1_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("OPENMIND_API_KEY", "openmind-key")
    reset_advisor_runtime()

    client = TestClient(create_app(), raise_server_exceptions=False)

    v1 = client.get("/v1/health")
    assert v1.status_code == 401

    v2 = client.post(
        "/v2/policy/hints",
        json={"query": "test"},
        headers={"X-Api-Key": "openmind-key"},
    )
    assert v2.status_code == 200

    v2_missing_key = client.post(
        "/v2/policy/hints",
        json={"query": "test"},
        headers={"Authorization": "Bearer api-token"},
    )
    assert v2_missing_key.status_code == 401
    assert "Invalid or missing API key" in v2_missing_key.json()["detail"]
