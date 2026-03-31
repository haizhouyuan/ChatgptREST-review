"""Tests for chatgptrest/kernel/cc_executor.py

Comprehensive tests for the headless CcExecutor overhaul, including:
- Data types (CcTask, CcResult, AgentProfile)
- CLI argument building
- Stream-JSON parsing
- Headless dispatch (mocked subprocess)
- Multi-turn conversation
- Parallel dispatch
- Agent teams
- Quality evaluation
- Template management
- Hcom fallback
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from chatgptrest.kernel.cc_executor import (
    MAX_CC_AGENTS,
    CcExecutor,
    CcResult,
    CcTask,
    AgentProfile,
)


# ── Test Data Fixtures ──────────────────────────────────────────────

SAMPLE_STREAM_EVENTS = [
    '{"type":"system","subtype":"init","message":"Claude Code v1.0"}',
    '{"type":"assistant","message":{"content":[{"type":"text","text":"I will review the code."}]}}',
    '{"type":"content_block_start","content_block":{"type":"tool_use","name":"Read","input":{"file_path":"main.py"}}}',
    '{"type":"assistant","message":{"content":[{"type":"text","text":"## Review Findings\\n\\n| ID | Severity | File | Issue |\\n|---|---|---|---|\\n| R-001 | Critical | main.py:10 | SQL injection |\\n| R-002 | High | main.py:25 | Missing auth check |"}]}}',
    '{"type":"result","session_id":"abc-123","model":"claude-sonnet-4-6","input_tokens":1500,"output_tokens":800,"cost_usd":0.03,"num_turns":3,"result":"Review complete."}',
]


class TestCcTask:
    """Tests for CcTask dataclass."""

    def test_cctask_default_values(self):
        """Test CcTask with default values."""
        task = CcTask(task_type="code_review", description="Review code")
        assert task.task_type == "code_review"
        assert task.description == "Review code"
        assert task.files == []
        assert task.timeout == 300
        assert task.model == "sonnet"
        assert task.stateless is True
        assert task.max_turns == 25
        assert task.max_budget_usd == 10.0
        assert task.permission_mode == "bypassPermissions"
        assert task.trace_id.startswith("cc_")

    def test_cctask_with_all_values(self):
        """Test CcTask with all fields set."""
        task = CcTask(
            task_type="bug_fix",
            description="Fix login bug",
            files=["auth.py", "models.py"],
            context={"cwd": "/app"},
            timeout=600,
            trace_id="custom-trace",
            model="opus",
            fallback_model="sonnet",
            max_turns=10,
            max_budget_usd=5.0,
            mcp_config="./mcp.json",
            agents_json={"reviewer": {"description": "Code reviewer"}},
            json_schema={"type": "object"},
            system_prompt="Be thorough",
            cwd="/app",
            permission_mode="plan",
            stateless=False,
            session_id="sess-123",
            effort="high",
            allowed_tools=["Read", "Edit", "Bash"],
            add_dirs=["/lib"],
        )
        assert task.trace_id == "custom-trace"
        assert task.model == "opus"
        assert task.fallback_model == "sonnet"
        assert task.session_id == "sess-123"
        assert task.agents_json["reviewer"]["description"] == "Code reviewer"
        assert task.effort == "high"
        assert task.add_dirs == ["/lib"]

    def test_cctask_trace_id_generation(self):
        """Test that trace_id is auto-generated if not provided."""
        t1 = CcTask(task_type="test", description="test")
        t2 = CcTask(task_type="test", description="test")
        assert t1.trace_id != t2.trace_id
        assert t1.trace_id.startswith("cc_")

    def test_cctask_with_empty_description(self):
        """Test CcTask with empty description (edge case)."""
        task = CcTask(task_type="code_review", description="")
        assert task.description == ""

    def test_cctask_with_large_files_list(self):
        """Test CcTask with large files list."""
        files = [f"file_{i}.py" for i in range(100)]
        task = CcTask(task_type="code_review", description="big review", files=files)
        assert len(task.files) == 100


class TestCcResult:
    """Tests for CcResult dataclass."""

    def test_ccresult_success(self):
        """Test CcResult with successful execution."""
        result = CcResult(
            ok=True, agent="headless", task_type="code_review",
            output="## Review\n...", elapsed_seconds=15.5,
            findings_count=3, quality_score=0.8,
            session_id="abc-123", model_used="claude-sonnet-4-6",
            input_tokens=1000, output_tokens=500, cost_usd=0.02,
            num_turns=3, dispatch_mode="headless",
        )
        assert result.ok is True
        assert result.dispatch_mode == "headless"
        assert result.session_id == "abc-123"
        assert result.input_tokens == 1000
        assert result.cost_usd == 0.02

    def test_ccresult_failure(self):
        """Test CcResult with failed execution."""
        result = CcResult(
            ok=False, agent="headless", task_type="bug_fix",
            output="", elapsed_seconds=300,
            error="timeout after 300s", dispatch_mode="headless",
        )
        assert result.ok is False
        assert "timeout" in result.error

    def test_ccresult_defaults(self):
        """Test CcResult with default values."""
        result = CcResult(
            ok=True, agent="test", task_type="test",
            output="test", elapsed_seconds=1.0,
        )
        assert result.dispatch_mode == "headless"
        assert result.session_id == ""
        assert result.input_tokens == 0
        assert result.tools_used == []
        assert result.files_read == []


class TestAgentProfile:
    """Tests for AgentProfile dataclass."""

    def test_agent_profile_defaults(self):
        """Test AgentProfile with default values."""
        profile = AgentProfile(name="test-agent")
        assert profile.name == "test-agent"
        assert profile.capabilities == {}
        assert profile.total_tasks == 0

    def test_agent_profile_with_capabilities(self):
        """Test AgentProfile with capability scores."""
        profile = AgentProfile(
            name="cc4-rhea",
            capabilities={"code_review": 0.85, "bug_fix": 0.72},
            total_tasks=50,
            total_successes=45,
        )
        assert profile.capabilities["code_review"] == 0.85
        assert profile.total_successes / profile.total_tasks == 0.9


class TestCcExecutor:
    """Tests for CcExecutor class."""

    @pytest.fixture
    def executor(self):
        """Create a CcExecutor instance for testing."""
        with patch.object(CcExecutor, "_load_template_stats"):
            return CcExecutor()

    def test_executor_init_defaults(self, executor):
        """Test CcExecutor initialization with defaults."""
        assert executor._templates is not None
        assert "code_review" in executor._templates
        assert "bug_fix" in executor._templates
        assert executor._agent_profiles == {}

    def test_executor_init_with_params(self):
        """Test CcExecutor initialization with custom params."""
        observer = MagicMock()
        with patch.object(CcExecutor, "_load_template_stats"):
            executor = CcExecutor(
                observer=observer,
                hcom_dir="/tmp/test_hcom",
            )
        assert executor._observer is observer
        assert executor._hcom_dir == "/tmp/test_hcom"

    def test_executor_init_no_auto_recovery(self, executor):
        """Test that recovery daemon is not started by default."""
        assert executor._recovery_thread is None

    @patch.object(CcExecutor, "start_recovery_daemon")
    def test_executor_init_with_auto_recovery(self, mock_start):
        """Test that recovery daemon is started when auto_recover=True."""
        with patch.object(CcExecutor, "_load_template_stats"):
            executor = CcExecutor(auto_recover=True, recovery_interval=300)
        mock_start.assert_called_once_with(300)


# ── CLI Argument Builder Tests ──────────────────────────────────────

class TestBuildCliArgs:
    """Tests for _build_cli_args method."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            ex = CcExecutor()
            ex._cc_cli = "claude"
            return ex

    def test_basic_args(self, executor):
        """Test basic CLI argument construction."""
        task = CcTask(task_type="code_review", description="review")
        args = executor._build_cli_args(task, "Review this code")
        assert args[0] == "claude"
        assert args[1] == "-p"
        assert args[2] == "Review this code"
        assert "--output-format" in args
        assert "stream-json" in args

    def test_stateless_mode(self, executor):
        """Test --no-session-persistence is added for stateless tasks."""
        task = CcTask(task_type="test", description="test", stateless=True)
        args = executor._build_cli_args(task, "test")
        assert "--no-session-persistence" in args

    def test_stateful_mode(self, executor):
        """Test stateless=False omits --no-session-persistence."""
        task = CcTask(task_type="test", description="test", stateless=False)
        args = executor._build_cli_args(task, "test")
        assert "--no-session-persistence" not in args

    def test_model_selection(self, executor):
        """Test model and fallback_model args."""
        task = CcTask(
            task_type="test", description="test",
            model="opus", fallback_model="sonnet",
        )
        args = executor._build_cli_args(task, "test")
        model_idx = args.index("--model")
        assert args[model_idx + 1] == "opus"
        fb_idx = args.index("--fallback-model")
        assert args[fb_idx + 1] == "sonnet"

    def test_mcp_config(self, executor):
        """Test MCP config argument."""
        task = CcTask(
            task_type="test", description="test",
            mcp_config="/path/to/mcp.json",
        )
        args = executor._build_cli_args(task, "test")
        mcp_idx = args.index("--mcp-config")
        assert args[mcp_idx + 1] == "/path/to/mcp.json"

    def test_agents_json(self, executor):
        """Test agents JSON and teammate-mode args."""
        agents = {"reviewer": {"description": "Expert reviewer", "model": "sonnet"}}
        task = CcTask(
            task_type="test", description="test",
            agents_json=agents,
        )
        args = executor._build_cli_args(task, "test")
        assert "--agents" in args
        assert "--teammate-mode" in args
        assert "in-process" in args
        # Verify JSON is properly serialized
        agent_idx = args.index("--agents")
        parsed = json.loads(args[agent_idx + 1])
        assert "reviewer" in parsed

    def test_json_schema(self, executor):
        """Test JSON schema argument."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        task = CcTask(
            task_type="test", description="test",
            json_schema=schema,
        )
        args = executor._build_cli_args(task, "test")
        assert "--json-schema" in args
        schema_idx = args.index("--json-schema")
        parsed = json.loads(args[schema_idx + 1])
        assert parsed["type"] == "object"

    def test_system_prompt(self, executor):
        """Test system prompt argument."""
        task = CcTask(
            task_type="test", description="test",
            system_prompt="Always write TypeScript",
        )
        args = executor._build_cli_args(task, "test")
        assert "--append-system-prompt" in args
        sp_idx = args.index("--append-system-prompt")
        assert args[sp_idx + 1] == "Always write TypeScript"

    def test_max_turns_and_budget(self, executor):
        """Test max_turns and max_budget_usd args."""
        task = CcTask(
            task_type="test", description="test",
            max_turns=5, max_budget_usd=2.5,
        )
        args = executor._build_cli_args(task, "test")
        mt_idx = args.index("--max-turns")
        assert args[mt_idx + 1] == "5"
        mb_idx = args.index("--max-budget-usd")
        assert args[mb_idx + 1] == "2.5"

    def test_permission_mode(self, executor):
        """Test permission mode argument."""
        task = CcTask(
            task_type="test", description="test",
            permission_mode="plan",
        )
        args = executor._build_cli_args(task, "test")
        pm_idx = args.index("--permission-mode")
        assert args[pm_idx + 1] == "plan"

    def test_resume_session(self, executor):
        """Test resume session argument."""
        task = CcTask(
            task_type="test", description="test",
            session_id="abc-123",
        )
        args = executor._build_cli_args(task, "test")
        assert "--resume" in args
        r_idx = args.index("--resume")
        assert args[r_idx + 1] == "abc-123"

    def test_effort_level(self, executor):
        """Test effort level argument."""
        task = CcTask(
            task_type="test", description="test",
            effort="high",
        )
        args = executor._build_cli_args(task, "test")
        assert "--effort" in args
        e_idx = args.index("--effort")
        assert args[e_idx + 1] == "high"

    def test_allowed_tools(self, executor):
        """Test allowed tools argument."""
        task = CcTask(
            task_type="test", description="test",
            allowed_tools=["Read", "Edit", "Bash"],
        )
        args = executor._build_cli_args(task, "test")
        assert "--tools" in args
        t_idx = args.index("--tools")
        assert args[t_idx + 1] == "Read,Edit,Bash"

    def test_no_tools(self, executor):
        """Test disabling all tools."""
        task = CcTask(
            task_type="test", description="test",
            allowed_tools=[],
        )
        args = executor._build_cli_args(task, "test")
        t_idx = args.index("--tools")
        assert args[t_idx + 1] == ""

    def test_add_dirs(self, executor):
        """Test add-dir arguments."""
        task = CcTask(
            task_type="test", description="test",
            add_dirs=["/lib", "/ext"],
        )
        args = executor._build_cli_args(task, "test")
        dir_indices = [i for i, a in enumerate(args) if a == "--add-dir"]
        assert len(dir_indices) == 2


# ── Stream-JSON Parser Tests ────────────────────────────────────────

class TestParseStreamEvent:
    """Tests for _parse_stream_event method."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            return CcExecutor()

    def test_parse_assistant_message(self, executor):
        """Test parsing assistant text content."""
        event = {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Here is my review."}],
            },
        }
        result = executor._parse_stream_event(event)
        assert result["type"] == "text"
        assert "review" in result["content"]

    def test_parse_content_block_delta(self, executor):
        """Test parsing streaming text delta."""
        event = {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "partial"},
        }
        result = executor._parse_stream_event(event)
        assert result["type"] == "text"
        assert result["content"] == "partial"

    def test_parse_tool_use(self, executor):
        """Test parsing tool use event."""
        event = {
            "type": "content_block_start",
            "content_block": {
                "type": "tool_use",
                "name": "Read",
                "input": {"file_path": "main.py"},
            },
        }
        result = executor._parse_stream_event(event)
        assert result["type"] == "tool_use"
        assert result["tool"] == "Read"
        assert result["file"] == "main.py"

    def test_parse_result(self, executor):
        """Test parsing final result event."""
        event = {
            "type": "result",
            "session_id": "abc-123",
            "model": "claude-sonnet-4-6",
            "input_tokens": 1500,
            "output_tokens": 800,
            "cost_usd": 0.03,
            "num_turns": 3,
            "result": "Review complete.",
        }
        result = executor._parse_stream_event(event)
        assert result["type"] == "result"
        meta = result["metadata"]
        assert meta["session_id"] == "abc-123"
        assert meta["input_tokens"] == 1500
        assert meta["cost_usd"] == 0.03

    def test_parse_result_fallback(self, executor):
        """Test parsing result from non-typed event with result+session_id."""
        event = {
            "session_id": "xyz",
            "result": "Done",
            "input_tokens_used": 500,
            "output_tokens_used": 200,
        }
        result = executor._parse_stream_event(event)
        assert result["type"] == "result"
        assert result["metadata"]["session_id"] == "xyz"
        assert result["metadata"]["input_tokens"] == 500

    def test_parse_error(self, executor):
        """Test parsing error event."""
        event = {
            "type": "error",
            "error": {"message": "Rate limit exceeded"},
        }
        result = executor._parse_stream_event(event)
        assert result["type"] == "error"
        assert "Rate limit" in result["message"]

    def test_parse_message_boundary(self, executor):
        """Test parsing message_start/stop events."""
        for etype in ("message_start", "message_stop"):
            result = executor._parse_stream_event({"type": etype})
            assert result["type"] == "turn"

    def test_parse_system_init(self, executor):
        """Test parsing system init event."""
        event = {"type": "system", "subtype": "init"}
        result = executor._parse_stream_event(event)
        assert result["type"] == "text"

    def test_parse_unknown(self, executor):
        """Test parsing unknown event type."""
        event = {"type": "some_unknown_type", "data": "foo"}
        result = executor._parse_stream_event(event)
        assert result["type"] == "unknown"


# ── Headless Dispatch Tests (mocked subprocess) ────────────────────

class TestDispatchHeadless:
    """Tests for dispatch_headless method."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            ex = CcExecutor()
            ex._cc_cli = "claude"
            ex._headless_available = True
            return ex

    def test_dispatch_headless_success(self, executor):
        """Test successful headless dispatch."""
        mock_proc = AsyncMock()
        
        async def mock_stdout():
            for line in SAMPLE_STREAM_EVENTS:
                yield line.encode() + b"\n"
        
        mock_proc.stdout.__aiter__.side_effect = lambda: mock_stdout()
        mock_proc.stderr.read = AsyncMock(return_value=b"")
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.kill = MagicMock()

        async def _run():
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                task = CcTask(
                    task_type="code_review",
                    description="Review auth code",
                    files=["auth.py"],
                    cwd="/tmp",
                )
                return await executor.dispatch_headless(task)

        result = asyncio.run(_run())

        assert result.ok is True
        assert result.dispatch_mode == "headless"
        assert "Review Findings" in result.output or "review" in result.output.lower()

    def test_dispatch_headless_timeout(self, executor):
        """Test headless dispatch timeout."""
        class _TimeoutStream:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise asyncio.TimeoutError

        mock_proc = AsyncMock()
        mock_proc.stdout = _TimeoutStream()
        mock_proc.stderr.read = AsyncMock(return_value=b"")
        mock_proc.wait = AsyncMock(return_value=-9)
        mock_proc.kill = MagicMock()

        async def _run():
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                task = CcTask(
                    task_type="code_review",
                    description="Review",
                    timeout=1,
                )
                return await executor.dispatch_headless(task)

        result = asyncio.run(_run())
        assert isinstance(result, CcResult)

    def test_dispatch_headless_subprocess_error(self, executor):
        """Test headless dispatch with subprocess error."""
        mock_proc = AsyncMock()
        
        async def mock_stdout():
            if False: yield b""
            
        mock_proc.stdout.__aiter__.side_effect = lambda: mock_stdout()
        mock_proc.stderr.read = AsyncMock(return_value=b"Error: auth failed")
        mock_proc.wait = AsyncMock(return_value=1)
        mock_proc.kill = MagicMock()

        async def _run():
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                task = CcTask(task_type="test", description="test", cwd="/tmp")
                return await executor.dispatch_headless(task)

        result = asyncio.run(_run())
        assert result.ok is False
        assert "auth failed" in result.error

    def test_dispatch_headless_with_callback(self, executor):
        """Test progress callback is invoked."""
        events = [
            b'{"type":"assistant","message":{"content":[{"type":"text","text":"hello"}]}}\n',
        ]

        mock_proc = AsyncMock()
        
        async def mock_stdout():
            for event in events:
                yield event
                
        mock_proc.stdout.__aiter__.side_effect = lambda: mock_stdout()
        mock_proc.stderr.read = AsyncMock(return_value=b"")
        mock_proc.wait = AsyncMock(return_value=0)

        progress_events = []
        def on_progress(evt):
            progress_events.append(evt)

        async def _run():
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                task = CcTask(task_type="test", description="test", cwd="/tmp")
                await executor.dispatch_headless(task, progress_callback=on_progress)

        asyncio.run(_run())

        assert len(progress_events) > 0
        assert progress_events[0]["type"] == "text"


# ── Dispatch Conversation Tests ─────────────────────────────────────

class TestDispatchConversation:
    """Tests for dispatch_conversation method."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            ex = CcExecutor()
            ex._headless_available = True
            return ex

    def test_conversation_two_turns(self, executor):
        """Test multi-turn conversation with session continuation."""
        call_count = 0

        async def mock_dispatch(task, template=None, progress_callback=None):
            nonlocal call_count
            call_count += 1
            return CcResult(
                ok=True, agent="headless", task_type=task.task_type,
                output=f"Turn {call_count} response",
                elapsed_seconds=5.0,
                session_id="session-xyz",
                dispatch_mode="headless",
            )

        executor.dispatch_headless = mock_dispatch

        tasks = [
            CcTask(task_type="bug_fix", description="Fix login"),
            CcTask(task_type="bug_fix", description="Now run tests"),
        ]

        results = asyncio.run(executor.dispatch_conversation(tasks))

        assert len(results) == 2
        assert results[0].ok is True
        assert results[1].ok is True
        assert tasks[1].session_id == "session-xyz"
        assert tasks[1].stateless is False


# ── Dispatch Parallel Tests ─────────────────────────────────────────

class TestDispatchParallel:
    """Tests for dispatch_parallel method."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            ex = CcExecutor()
            ex._headless_available = True
            return ex

    def test_parallel_three_tasks(self, executor):
        """Test parallel execution of 3 independent tasks."""
        async def mock_dispatch(task, template=None, progress_callback=None):
            await asyncio.sleep(0.01)  # Simulate work
            return CcResult(
                ok=True, agent="headless", task_type=task.task_type,
                output=f"Result for {task.description}",
                elapsed_seconds=1.0,
                dispatch_mode="headless",
            )

        executor.dispatch_headless = mock_dispatch

        tasks = [
            CcTask(task_type="code_review", description=f"Review file {i}")
            for i in range(3)
        ]

        results = asyncio.run(executor.dispatch_parallel(tasks, max_concurrent=2))

        assert len(results) == 3
        assert all(r.ok for r in results)
        assert all(r.dispatch_mode == "headless" for r in results)


# ── Dispatch Team Tests ─────────────────────────────────────────────

class TestDispatchTeam:
    """Tests for dispatch_team method."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            ex = CcExecutor()
            ex._headless_available = True
            return ex

    def test_dispatch_team_sets_agents(self, executor):
        """Test that dispatch_team correctly sets agents_json on task."""
        captured_task = None

        async def mock_dispatch(task, template=None, progress_callback=None):
            nonlocal captured_task
            captured_task = task
            return CcResult(
                ok=True, agent="headless", task_type=task.task_type,
                output="Team result", elapsed_seconds=5.0,
                dispatch_mode="headless",
            )

        executor.dispatch_headless = mock_dispatch

        team = {
            "reviewer": {
                "description": "Expert code reviewer",
                "prompt": "Focus on correctness",
                "model": "sonnet",
            },
            "security": {
                "description": "Security specialist",
                "prompt": "Find vulnerabilities",
                "model": "haiku",
            },
        }

        task = CcTask(task_type="code_review", description="Team review")
        result = asyncio.run(executor.dispatch_team(task, team=team))

        assert result.ok is True
        assert captured_task.agents_json == team


# ── Quality Evaluation Tests ────────────────────────────────────────

class TestQualityEvaluation:
    """Tests for quality evaluation methods."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            return CcExecutor()

    def test_high_quality_review_output(self, executor):
        """Test quality scoring for a well-structured review."""
        output = """
## Code Review Findings

| ID | Severity | File | Line | Issue | Fix |
|----|----------|------|------|-------|-----|
| R-001 | Critical | auth.py | 15 | SQL injection | Use parameterized queries |
| R-002 | High | auth.py | 32 | Missing auth | Add @login_required |
| R-003 | Medium | models.py | 88 | No validation | Add input validation |
| R-004 | Low | utils.py | 5 | Unused import | Remove unused import |

### Summary
Found 4 issues: 1 Critical, 1 High, 1 Medium, 1 Low.
```python
# Suggested fix for R-001
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```
"""
        task = CcTask(task_type="code_review", description="review")
        score = executor._evaluate_quality(output, task)
        assert score >= 0.6  # Should be high quality

    def test_low_quality_output(self, executor):
        """Test quality scoring for a minimal output."""
        output = "Looks good to me."
        task = CcTask(task_type="code_review", description="review")
        score = executor._evaluate_quality(output, task)
        assert score <= 0.3

    def test_count_findings(self, executor):
        """Test finding counter."""
        output = "R-001 Critical, R-002 High, R-003 Medium"
        count = executor._count_findings(output)
        assert count >= 2

    def test_count_files_modified(self, executor):
        """Test file modification counter."""
        output = """
Update(auth.py) — Added input validation
Write(test_auth.py) — New test file
Added 15 lines, removed 3 lines
"""
        count = executor._count_files_modified(output)
        assert count >= 2


# ── Headless Capability Detection Tests ─────────────────────────────

class TestCapabilityDetection:
    """Tests for headless capability detection."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            return CcExecutor()

    @patch("subprocess.run")
    def test_headless_available(self, mock_run, executor):
        """Test detection when claude CLI is available."""
        mock_run.return_value = MagicMock(returncode=0)
        executor._headless_available = None  # Reset cache
        assert executor._is_headless_available() is True

    @patch("subprocess.run")
    def test_headless_unavailable(self, mock_run, executor):
        """Test detection when claude CLI is missing."""
        mock_run.side_effect = FileNotFoundError("claude not found")
        executor._headless_available = None
        assert executor._is_headless_available() is False

    @patch("subprocess.run")
    def test_headless_cached(self, mock_run, executor):
        """Test that detection result is cached."""
        executor._headless_available = True
        assert executor._is_headless_available() is True
        mock_run.assert_not_called()


# ── Unified Dispatch Tests ──────────────────────────────────────────

class TestUnifiedDispatch:
    """Tests for unified dispatch() entrypoint."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            return CcExecutor()

    @patch.object(CcExecutor, "_dispatch_headless_sync")
    @patch.object(CcExecutor, "_is_headless_available", return_value=True)
    def test_dispatch_prefers_headless(self, mock_avail, mock_headless, executor):
        """Test that dispatch() prefers headless mode."""
        mock_headless.return_value = CcResult(
            ok=True, agent="headless", task_type="test",
            output="done", elapsed_seconds=5.0,
        )
        task = CcTask(task_type="code_review", description="test")
        result = executor.dispatch(task)
        mock_headless.assert_called_once()

    @patch.object(CcExecutor, "_dispatch_hcom")
    @patch.object(CcExecutor, "_is_headless_available", return_value=False)
    def test_dispatch_falls_back_to_hcom(self, mock_avail, mock_hcom, executor):
        """Test that dispatch() falls back to hcom when CLI unavailable."""
        mock_hcom.return_value = CcResult(
            ok=True, agent="cc4-rhea", task_type="test",
            output="done", elapsed_seconds=10.0,
        )
        task = CcTask(task_type="code_review", description="test")
        result = executor.dispatch(task)
        mock_hcom.assert_called_once()


# ── Template Management Tests ───────────────────────────────────────

class TestCcExecutorSelectTemplate:
    """Tests for template selection and management."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            return CcExecutor()

    def test_select_template_default(self, executor):
        """Test selecting a template for known task type."""
        template = executor._select_template("code_review")
        assert template in executor._templates["code_review"]

    def test_select_template_unknown_type(self, executor):
        """Test selecting template for unknown task type."""
        template = executor._select_template("unknown_type")
        assert template == "v1_default"

    def test_select_template_prefers_high_quality(self, executor):
        """Test that higher quality templates are preferred."""
        executor._templates["code_review"]["v1_structured"]["stats"] = {
            "trials": 10, "avg_quality": 0.9,
        }
        executor._templates["code_review"]["v2_roleplay_cn"]["stats"] = {
            "trials": 10, "avg_quality": 0.4,
        }
        template = executor._select_template("code_review")
        assert template == "v1_structured"


class TestCcExecutorBuildPrompt:
    """Tests for prompt building."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            return CcExecutor()

    def test_build_prompt_with_template(self, executor):
        """Test building prompt from template."""
        task = CcTask(
            task_type="code_review",
            description="Review auth module",
            files=["auth.py", "models.py"],
        )
        prompt = executor._build_prompt(task, "v1_structured")
        assert "auth.py" in prompt
        assert "models.py" in prompt

    def test_build_prompt_falls_back_to_description(self, executor):
        """Test falling back to description when template not found."""
        task = CcTask(
            task_type="code_review",
            description="Custom review task",
        )
        prompt = executor._build_prompt(task, "nonexistent_template")
        assert prompt == "Custom review task"


# ── Agent Selection Tests ───────────────────────────────────────────

class TestCcExecutorSelectAgent:
    """Tests for select_agent method."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            executor = CcExecutor()
        return executor

    @patch("subprocess.run")
    def test_select_agent_no_agents(self, mock_run, executor):
        """Test select_agent when no agents are available."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        agent = executor.select_agent("code_review")
        assert agent == ""

    @patch("subprocess.run")
    def test_select_agent_single_agent(self, mock_run, executor):
        """Test select_agent with a single available agent."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="◉ cc4-rhea now: listening since 10:00\n",
        )
        agent = executor.select_agent("code_review")
        assert agent == "cc4-rhea"

    @patch("subprocess.run")
    def test_select_agent_multiple_agents(self, mock_run, executor):
        """Test select_agent with multiple agents."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "◉ cc4-rhea now: listening since 10:00\n"
                "◉ cc4-silo now: active since 10:05\n"
            ),
        )
        agent = executor.select_agent("code_review")
        assert agent in ("cc4-rhea", "cc4-silo")


# ── Template Evolution Tests ────────────────────────────────────────

class TestTemplateEvolution:
    """Tests for template evolution."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            return CcExecutor()

    def test_evolve_templates_no_data(self, executor):
        """Test evolution with no trial data."""
        changes = executor.evolve_templates()
        # No changes when no data
        assert isinstance(changes, dict)

    def test_evolve_templates_with_data(self, executor):
        """Test evolution with sufficient trial data."""
        executor._templates["code_review"]["v1_structured"]["stats"] = {
            "trials": 10, "avg_quality": 0.9, "total_findings": 50,
        }
        executor._templates["code_review"]["v2_roleplay_cn"]["stats"] = {
            "trials": 10, "avg_quality": 0.3, "total_findings": 5,
        }
        changes = executor.evolve_templates()
        assert "code_review" in changes
        assert changes["code_review"]["promoted"] == "v1_structured"

    def test_template_report(self, executor):
        """Test template report generation."""
        report = executor.get_template_report()
        assert "code_review" in report
        assert "bug_fix" in report
        assert isinstance(report["code_review"], list)


# ── Health Check Tests ──────────────────────────────────────────────

class TestHealthCheck:
    """Tests for check_health method."""

    @pytest.fixture
    def executor(self):
        with patch.object(CcExecutor, "_load_template_stats"):
            ex = CcExecutor()
            ex._headless_available = True
            return ex

    @patch("subprocess.run")
    def test_check_health(self, mock_run, executor):
        """Test check_health returns expected structure."""
        mock_run.return_value = MagicMock(returncode=0, stdout="daemon:    running\n")
        health = executor.check_health()
        assert "headless_available" in health
        assert health["headless_available"] is True
        assert "total_agents" in health
        assert "daemon_running" in health
