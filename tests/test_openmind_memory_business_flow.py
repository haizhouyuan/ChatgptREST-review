from __future__ import annotations

from fastapi.testclient import TestClient

from chatgptrest.advisor.runtime import get_advisor_runtime_if_ready, reset_advisor_runtime
from chatgptrest.api.app import create_app


def test_openmind_memory_business_flow_cross_session_recall(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENMIND_RATE_LIMIT", raising=False)
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("OPENMIND_ENABLE_ROUTING_WATCHER", "0")
    monkeypatch.setenv("OPENMIND_DB_PATH", str(tmp_path / "effects.db"))
    monkeypatch.setenv("OPENMIND_KB_DB", str(tmp_path / "kb_registry.db"))
    monkeypatch.setenv("OPENMIND_KB_SEARCH_DB", str(tmp_path / "kb_search.db"))
    monkeypatch.setenv("OPENMIND_KB_VEC_DB", str(tmp_path / "kb_vectors.db"))
    monkeypatch.setenv("OPENMIND_MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("OPENMIND_EVENTBUS_DB", str(tmp_path / "events.db"))
    monkeypatch.setenv("OPENMIND_DEDUP_DB", str(tmp_path / "dedup.db"))
    monkeypatch.setenv("OPENMIND_EVOMAP_DB", str(tmp_path / "evomap_observer.db"))
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(tmp_path / "evomap_knowledge.db"))
    monkeypatch.setenv("OPENMIND_CHECKPOINT_DB", str(tmp_path / "checkpoint.db"))

    reset_advisor_runtime()
    client = TestClient(create_app(), raise_server_exceptions=False)
    headers = {"X-Api-Key": "secret-key"}

    cold = client.get("/v2/cognitive/health", headers=headers)
    assert cold.status_code == 200
    cold_body = cold.json()
    assert cold_body["ok"] is False
    assert cold_body["status"] == "not_initialized"
    assert cold_body["runtime_ready"] is False
    assert get_advisor_runtime_if_ready() is None

    capture = client.post(
        "/v2/memory/capture",
        headers=headers,
        json={
            "items": [
                {
                    "title": "Status update preference",
                    "content": "When giving me a status update, lead with the conclusion, then blockers, then next actions.",
                    "trace_id": "tr-business-memory-1",
                    "session_key": "sess-origin",
                    "account_id": "acct-business",
                    "agent_id": "main",
                    "source_system": "openclaw",
                    "source_ref": "openclaw://session/sess-origin/manual-capture",
                }
            ]
        },
    )
    assert capture.status_code == 200
    capture_item = capture.json()["results"][0]
    assert capture_item["ok"] is True
    assert capture_item["provenance_quality"] == "partial"
    assert set(capture_item["identity_gaps"]) == {"missing_thread_id"}

    warm = client.get("/v2/cognitive/health", headers=headers)
    assert warm.status_code == 200
    warm_body = warm.json()
    assert warm_body["status"] == "ok"
    assert warm_body["runtime_ready"] is True

    resolve = client.post(
        "/v2/context/resolve",
        headers=headers,
        json={
            "query": "How should status updates be written for me?",
            "session_key": "sess-other",
            "account_id": "acct-business",
            "agent_id": "main",
            "sources": ["memory", "policy"],
        },
    )
    assert resolve.status_code == 200
    body = resolve.json()
    assert body["ok"] is True
    captured_block = next(block for block in body["context_blocks"] if block["source_type"] == "captured")
    assert "lead with the conclusion" in captured_block["text"]
    assert body["metadata"]["identity_scope"] == "partial"
    assert body["metadata"]["captured_memory_scope"] == "account_cross_session"
    assert set(body["metadata"]["identity_gaps"]) == {"missing_thread_id"}

    runtime = get_advisor_runtime_if_ready()
    assert runtime is not None
    audit = runtime.memory.audit_trail(capture_item["record_id"])
    assert [entry["action"] for entry in audit[:2]] == ["stage", "promote"]
    events = runtime.event_bus.query(trace_id="tr-business-memory-1")
    assert any(event.event_type == "memory.capture" for event in events)
