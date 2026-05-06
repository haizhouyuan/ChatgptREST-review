import pytest
import asyncio
import tempfile
import sqlite3
import sys
import types
from pathlib import Path

from chatgptrest.kernel.cc_sessiond import (
    SessionRegistry,
    SessionState,
    EventLog,
    EventType,
    JobScheduler,
    BudgetTracker,
    CCSessionClient,
    CcExecutorBackend,
    SDKBackend,
    ArtifactManager,
    PromptPackagingError,
)
from chatgptrest.kernel.cc_executor import CcResult


def _write_task_packet(base_dir: Path, name: str = "task_packet_v1.md") -> Path:
    path = base_dir / name
    path.write_text("# Task Packet\n\nFollow the referenced implementation steps.\n")
    return path


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


class TestSessionRegistry:
    def test_create_session(self, temp_db):
        registry = SessionRegistry(temp_db)
        record = registry.create("Fix the bug", {"allowed_tools": ["Read"]})
        
        assert record.session_id is not None
        assert record.prompt == "Fix the bug"
        assert record.state == SessionState.PENDING
        
        retrieved = registry.get(record.session_id)
        assert retrieved.session_id == record.session_id
        assert retrieved.prompt == "Fix the bug"
        
        registry.close()

    def test_update_state(self, temp_db):
        registry = SessionRegistry(temp_db)
        record = registry.create("Test prompt", {})
        
        registry.update_state(
            record.session_id,
            SessionState.COMPLETED,
            result={"output": "done"},
            total_cost=0.05,
        )
        
        updated = registry.get(record.session_id)
        assert updated.state == SessionState.COMPLETED
        assert updated.result == {"output": "done"}
        assert updated.total_cost == 0.05
        
        registry.close()

    def test_list_sessions(self, temp_db):
        registry = SessionRegistry(temp_db)
        
        registry.create("Prompt 1", {})
        registry.create("Prompt 2", {})
        
        sessions = registry.list()
        assert len(sessions) == 2
        
        sessions = registry.list(state=SessionState.PENDING)
        assert len(sessions) == 2
        
        registry.close()

    def test_migrate_legacy_schema(self, temp_db):
        conn = sqlite3.connect(temp_db)
        conn.execute("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                prompt TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                options TEXT,
                result TEXT,
                error TEXT,
                total_cost REAL,
                total_tokens INTEGER
            )
        """)
        conn.commit()
        conn.close()

        registry = SessionRegistry(temp_db)
        record = registry.create("Legacy prompt", {})

        migrated = registry.get(record.session_id)
        assert migrated is not None
        assert migrated.parent_session_id is None
        assert migrated.backend_run_id is None

        registry.close()


class TestEventLog:
    def test_emit_and_query(self, temp_db):
        event_db = temp_db.with_suffix(".events.db")
        event_log = EventLog(event_db)
        
        event_log.emit("session-1", EventType.STARTED, {"data": "test"})
        event_log.emit("session-1", EventType.TOOL_CALL, {"tool": "Read"})
        
        events = event_log.query("session-1")
        assert len(events) == 2
        assert events[0].event_type == EventType.STARTED
        assert events[1].event_type == EventType.TOOL_CALL
        
        event_log.close()

    def test_get_latest_id(self, temp_db):
        event_db = temp_db.with_suffix(".events.db")
        event_log = EventLog(event_db)
        
        event_log.emit("session-1", EventType.STARTED, {})
        event_log.emit("session-1", EventType.STARTED, {})
        
        latest_id = event_log.get_latest_id("session-1")
        assert latest_id == 2
        
        event_log.close()


class TestArtifactManager:
    def test_append_event_serializes_objects(self, tmp_path: Path):
        artifacts = ArtifactManager(base_dir=tmp_path)

        class _FakeBlock:
            def __init__(self):
                self.text = "hello"

        class _FakeMessage:
            def __init__(self):
                self.kind = "system"
                self.content = [_FakeBlock()]

        artifacts.append_event(
            "session-1",
            {
                "type": "message",
                "message": _FakeMessage(),
            },
        )

        events = artifacts.get_events("session-1")
        assert events[0]["type"] == "message"
        assert events[0]["message"]["kind"] == "system"
        assert events[0]["message"]["content"][0]["text"] == "hello"


class TestBudgetTracker:
    @pytest.mark.asyncio
    async def test_check_budget(self):
        tracker = BudgetTracker(budget_per_hour=10.0, budget_total=100.0)
        
        assert await tracker.check_budget() is True
        
        await tracker.record_cost(5.0)
        
        snapshot = tracker.get_snapshot()
        assert snapshot["hourly_spent"] == 5.0
        assert snapshot["remaining_hourly"] == 5.0
        
        await tracker.record_cost(6.0)
        assert await tracker.check_budget() is False
        
        tracker.close()

    @pytest.mark.asyncio
    async def test_budget_exceeded(self):
        tracker = BudgetTracker(budget_per_hour=10.0, budget_total=1.0)
        
        await tracker.record_cost(1.5)
        
        # Total budget exceeded
        assert await tracker.check_budget() is False
        
        tracker.close()


class TestJobScheduler:
    @pytest.mark.asyncio
    async def test_submit_and_run(self):
        scheduler = JobScheduler(max_concurrent=2)
        
        results = []
        
        async def executor(session_id, prompt, options):
            results.append(session_id)
        
        await scheduler.submit("job-1", "prompt 1", {})
        await scheduler.submit("job-2", "prompt 2", {})
        
        # Run one job
        job_id = await scheduler.run_next(executor)
        assert job_id == "job-1"
        
        # Simulate job completion
        async with scheduler._lock:
            scheduler.running.discard("job-1")
        
        # Run next
        job_id = await scheduler.run_next(executor)
        assert job_id == "job-2"

    @pytest.mark.asyncio
    async def test_cancel(self):
        scheduler = JobScheduler(max_concurrent=2)
        
        await scheduler.submit("job-1", "prompt 1", {})
        
        cancelled = await scheduler.cancel("job-1")
        assert cancelled is True
        
        cancelled = await scheduler.cancel("nonexistent")
        assert cancelled is False

    def test_get_status(self):
        scheduler = JobScheduler(max_concurrent=3, budget_per_hour=10.0)
        
        status = scheduler.get_status()
        assert status["max_concurrent"] == 3
        assert status["running_count"] == 0


class TestCCSessionClient:
    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.mark.asyncio
    async def test_create_session(self, temp_db):
        client = CCSessionClient(
            db_path=temp_db,
            minimax_api_key="test-key",
        )
        task_packet = _write_task_packet(temp_db.parent)
        
        session_id = await client.create_session(
            prompt=str(task_packet),
            options={"allowed_tools": ["Read", "Edit"]},
        )
        
        assert session_id is not None
        
        record = client.get_session(session_id)
        assert record.prompt == str(task_packet)
        assert record.state == SessionState.PENDING
        assert record.options["prompt_doc_path"] == str(task_packet)
        
        client.close()

    @pytest.mark.asyncio
    async def test_create_session_rejects_free_text_prompt(self, temp_db):
        client = CCSessionClient(
            db_path=temp_db,
            minimax_api_key="test-key",
        )

        large_doc = "\n".join(
            [
                "# Spec A",
                "## Mission",
                "- one",
                "- two",
                "- three",
                "- four",
                "- five",
                "- six",
                "- seven",
                "- eight",
                "- nine",
                "- ten",
                "- eleven",
                "- twelve",
                "1. first",
                "2. second",
                "3. third",
                "4. fourth",
                "5. fifth",
                "6. sixth",
                "```text",
                "body",
                "```",
                "```text",
                "body",
                "```",
                "/vol1/1000/projects/ChatgptREST/docs/a.md",
                "/vol1/1000/projects/ChatgptREST/docs/b.md",
                "x" * 9000,
            ]
        )

        with pytest.raises(PromptPackagingError, match="must be only one Markdown task-packet path"):
            await client.create_session(prompt=large_doc, options={})

        client.close()

    @pytest.mark.asyncio
    async def test_create_session_rejects_non_versioned_markdown_path(self, temp_db):
        client = CCSessionClient(
            db_path=temp_db,
            minimax_api_key="test-key",
        )
        invalid_packet = temp_db.parent / "task_packet.md"
        invalid_packet.write_text("# Task Packet\n")

        with pytest.raises(PromptPackagingError, match="versioned Markdown task packet"):
            await client.create_session(prompt=str(invalid_packet), options={})

        client.close()

    @pytest.mark.asyncio
    async def test_create_session_allows_path_only_prompt(self, temp_db):
        client = CCSessionClient(
            db_path=temp_db,
            minimax_api_key="test-key",
        )
        task_packet = _write_task_packet(temp_db.parent)

        session_id = await client.create_session(prompt=str(task_packet), options={})
        record = client.get_session(session_id)
        assert record is not None
        assert record.prompt == str(task_packet)

        client.close()

    @pytest.mark.asyncio
    async def test_create_session_auto_starts_processor_and_completes(self, temp_db):
        class _FakeBackend:
            backend_name = "fake"

            async def create_run(self, session_id, prompt, options):
                yield {
                    "type": "completed",
                    "backend": "fake",
                    "backend_run_id": f"run-{session_id}",
                    "result": {
                        "subtype": "success",
                        "output_text": "done",
                        "total_cost_usd": 0.01,
                        "total_tokens": 5,
                    },
                }

        client = CCSessionClient(
            db_path=temp_db,
            minimax_api_key="test-key",
        )
        client._backend = _FakeBackend()
        task_packet = _write_task_packet(temp_db.parent)

        session_id = await client.create_session(prompt=str(task_packet), options={})
        result = await client.wait(session_id, timeout=3)
        status = client.get_scheduler_status()

        assert result["output_text"] == "done"
        assert client.get_session(session_id).state == SessionState.COMPLETED
        assert status["processor_running"] is True

        await client.stop()
        client.close()

    @pytest.mark.asyncio
    async def test_start_recovers_pending_session_from_registry(self, temp_db):
        class _FakeBackend:
            backend_name = "fake"

            async def create_run(self, session_id, prompt, options):
                yield {
                    "type": "completed",
                    "backend": "fake",
                    "backend_run_id": f"run-{session_id}",
                    "result": {
                        "subtype": "success",
                        "output_text": "recovered",
                        "total_cost_usd": 0.02,
                        "total_tokens": 6,
                    },
                }

        client = CCSessionClient(
            db_path=temp_db,
            minimax_api_key="test-key",
        )
        client._backend = _FakeBackend()
        task_packet = _write_task_packet(temp_db.parent)
        prompt_doc_path = client._validate_prompt_packaging(str(task_packet), {})
        options = client._normalized_prompt_options(prompt_doc_path, {})

        record = client.registry.create(
            client._prompt_record_value(prompt_doc_path),
            options,
        )
        client.artifacts.write_request(
            record.session_id,
            client._prompt_request_value(prompt_doc_path),
            options,
        )
        client.artifacts.write_status(record.session_id, "pending")

        await client.start()
        result = await client.wait(record.session_id, timeout=3)

        assert result["output_text"] == "recovered"
        assert client.get_session(record.session_id).state == SessionState.COMPLETED

        await client.stop()
        client.close()

    def test_get_events(self, temp_db):
        client = CCSessionClient(
            db_path=temp_db,
            minimax_api_key="test-key",
        )
        
        # Manually emit some events
        client.event_log.emit("test-session", EventType.STARTED, {})
        
        events = client.get_events("test-session")
        assert len(events) == 1
        assert events[0]["event_type"] == "started"
        
        client.close()

    @pytest.mark.asyncio
    async def test_list_sessions(self, temp_db):
        client = CCSessionClient(
            db_path=temp_db,
            minimax_api_key="test-key",
        )
        task_packet_1 = _write_task_packet(temp_db.parent, "task_packet_v1.md")
        task_packet_2 = _write_task_packet(temp_db.parent, "task_packet_v2.md")
        
        await client.create_session(str(task_packet_1), {})
        await client.create_session(str(task_packet_2), {})
        
        sessions = client.list_sessions()
        assert len(sessions) >= 2
        
        client.close()

    @pytest.mark.asyncio
    async def test_failed_backend_event_marks_session_failed(self, temp_db):
        client = CCSessionClient(
            db_path=temp_db,
            minimax_api_key="test-key",
        )
        task_packet = _write_task_packet(temp_db.parent)

        session_id = await client.create_session(str(task_packet), {})
        await client._handle_backend_event(
            session_id,
            {
                "type": "completed",
                "backend": "cc_executor",
                "backend_run_id": "run-1",
                "result": {"subtype": "failed", "error": "boom"},
            },
        )

        record = client.get_session(session_id)
        assert record.state == SessionState.FAILED
        assert record.error == "boom"
        assert client.artifacts.get_error(session_id)["error"] == "boom"

        client.close()


class TestCcExecutorBackend:
    @pytest.mark.asyncio
    async def test_create_run_normalizes_cc_result(self):
        class _FakeExecutor:
            async def dispatch_headless(self, task):
                return CcResult(
                    ok=True,
                    agent="headless",
                    task_type=task.task_type,
                    output="done",
                    elapsed_seconds=0.1,
                    quality_score=0.9,
                    session_id="claude-session-1",
                    cost_usd=0.12,
                    input_tokens=7,
                    output_tokens=5,
                    num_turns=2,
                )

        backend = CcExecutorBackend(_FakeExecutor())
        events = [event async for event in backend.create_run("session-1", "hello", {})]

        assert events[0]["backend_run_id"] == "claude-session-1"
        assert events[0]["result"]["output_text"] == "done"
        assert events[0]["result"]["total_cost_usd"] == 0.12
        assert events[0]["result"]["total_tokens"] == 12
        assert events[0]["result"]["turns"] == 2

    @pytest.mark.asyncio
    async def test_continue_run_uses_resume_session_id(self):
        captured = {}

        class _FakeExecutor:
            async def dispatch_headless(self, task):
                captured["task"] = task
                return CcResult(
                    ok=True,
                    agent="headless",
                    task_type=task.task_type,
                    output="continued",
                    elapsed_seconds=0.1,
                    session_id="claude-session-2",
                )

        backend = CcExecutorBackend(_FakeExecutor())
        events = [
            event
            async for event in backend.continue_run(
                "session-2", "claude-session-1", "follow up", {}
            )
        ]

        task = captured["task"]
        assert task.stateless is False
        assert task.session_id == "claude-session-1"
        assert events[0]["backend_run_id"] == "claude-session-2"


class TestSDKBackend:
    @pytest.mark.asyncio
    async def test_sdk_backend_uses_official_sdk_module(self, monkeypatch):
        calls = {}

        class _FakeClaudeCodeOptions:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class _FakeTextBlock:
            def __init__(self, text):
                self.text = text

        class _FakeAssistantMessage:
            def __init__(self, content):
                self.content = content

        class _FakeResultMessage:
            def __init__(self):
                self.is_error = False
                self.session_id = "sdk-session-1"
                self.total_cost_usd = 0.23
                self.usage = {"input_tokens": 11, "output_tokens": 13}
                self.num_turns = 3
                self.duration_ms = 1200
                self.duration_api_ms = 900
                self.result = "sdk output"

        async def _fake_query(*, prompt, options):
            calls["prompt"] = prompt
            calls["options"] = options
            yield _FakeAssistantMessage([_FakeTextBlock("thinking")])
            yield _FakeResultMessage()

        fake_module = types.SimpleNamespace(
            query=_fake_query,
            ClaudeCodeOptions=_FakeClaudeCodeOptions,
            ResultMessage=_FakeResultMessage,
        )
        monkeypatch.setitem(sys.modules, "claude_code_sdk", fake_module)

        backend = SDKBackend(minimax_api_key="mini-key")
        events = [event async for event in backend.create_run("session-1", "hello sdk", {})]

        assert calls["prompt"] == "hello sdk"
        assert calls["options"].kwargs["env"]["ANTHROPIC_API_KEY"] == "mini-key"
        assert calls["options"].kwargs["permission_mode"] == "bypassPermissions"
        assert events[-1]["backend_run_id"] == "sdk-session-1"
        assert events[-1]["result"]["total_tokens"] == 24

    @pytest.mark.asyncio
    async def test_sdk_backend_continue_sets_resume(self, monkeypatch):
        calls = {}

        class _FakeClaudeCodeOptions:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class _FakeResultMessage:
            def __init__(self):
                self.is_error = False
                self.session_id = "sdk-session-2"
                self.total_cost_usd = 0.0
                self.usage = {}
                self.num_turns = 1
                self.duration_ms = 1
                self.duration_api_ms = 1
                self.result = "ok"

        async def _fake_query(*, prompt, options):
            calls["options"] = options
            yield _FakeResultMessage()

        fake_module = types.SimpleNamespace(
            query=_fake_query,
            ClaudeCodeOptions=_FakeClaudeCodeOptions,
            ResultMessage=_FakeResultMessage,
        )
        monkeypatch.setitem(sys.modules, "claude_code_sdk", fake_module)

        backend = SDKBackend(minimax_api_key="mini-key")
        events = [
            event
            async for event in backend.continue_run(
                "session-2", "sdk-parent", "resume this", {}
            )
        ]

        assert calls["options"].kwargs["resume"] == "sdk-parent"
        assert calls["options"].kwargs["continue_conversation"] is True
        assert events[-1]["backend_run_id"] == "sdk-session-2"
