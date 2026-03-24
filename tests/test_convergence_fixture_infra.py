from __future__ import annotations

import pytest

from chatgptrest.kernel.memory_manager import MemoryTier


@pytest.mark.asyncio
async def test_mock_llm_connector_records_calls_and_scripted_failure(mock_llm_connector) -> None:
    mock_llm_connector.queue_text("first-response")
    mock_llm_connector.queue_error(TimeoutError("llm timeout"))

    assert await mock_llm_connector("prompt-1", system_msg="sys-1") == "first-response"

    with pytest.raises(TimeoutError, match="llm timeout"):
        await mock_llm_connector("prompt-2")

    assert mock_llm_connector.calls == [
        {"prompt": "prompt-1", "system_msg": "sys-1"},
        {"prompt": "prompt-2", "system_msg": ""},
    ]


def test_memory_manager_fixture_stages_and_reads_identity_scoped_records(memory_manager_fixture) -> None:
    memory_manager_fixture.stage_and_promote(
        target=MemoryTier.EPISODIC,
        category="status_pref",
        key="pref:status-format",
        value={"text": "lead with conclusion"},
        session_id="session-1",
        account_id="acct-1",
        thread_id="thread-1",
    )

    same_scope = memory_manager_fixture.episodic(session_id="session-1")
    other_scope = memory_manager_fixture.episodic(session_id="session-2")

    assert len(same_scope) == 1
    assert same_scope[0].category == "status_pref"
    assert other_scope == []
