"""CcExecutor — Headless Claude Code execution gateway.

Primary execution mode: `claude -p` subprocess with structured JSON output.
Fallback mode: hcom terminal injection (legacy).

Architecture::

    User/Orchestrator  →  CcExecutor.dispatch()
                              ├── build_cli_args()    — CLI parameter assembly
                              ├── subprocess(claude)  — Headless dispatch
                              ├── stream_parse()      — Realtime JSON parse
                              ├── evaluate_output()   — Quality gate
                              └── emit signals        — EvoMap × Langfuse

    Modes:
      dispatch()              — Single-shot (default, most common)
      dispatch_conversation() — Multi-turn with --continue
      dispatch_parallel()     — Concurrent tasks via asyncio
      dispatch_team()         — Agent teams (--teammate-mode in-process)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

HCOM_DIR = os.environ.get("HCOM_DIR", os.path.expanduser("~/.hcom"))
MAX_CC_AGENTS = int(os.environ.get("MAX_CC_AGENTS", "5"))
CC_CLI = os.environ.get("CC_CLI", "claude")

# ── Prompt Template Registry ────────────────────────────────────────

_DEFAULT_TEMPLATES: dict[str, dict[str, dict]] = {
    "code_review": {
        "v1_structured": {
            "template": (
                "Do a deep code review of: {files}. "
                "Focus on runtime errors, edge cases, thread safety, "
                "missing validation, and logic bugs. "
                "For each finding: ID, Severity (Critical/High/Medium/Low), "
                "File, Line, Issue, Fix Suggestion. Output as markdown table."
            ),
            "stats": {"trials": 0, "avg_quality": 0.0, "total_findings": 0},
        },
        "v2_roleplay_cn": {
            "template": (
                "你是一位资深系统架构师兼安全专家。"
                "深度审查以下文件：{files}。"
                "重点关注：运行时错误、竞态条件、安全漏洞、"
                "资源泄漏、边界条件、API 设计缺陷。"
                "输出格式：ID | 严重度 | 文件:行 | 问题 | 修复建议。"
                "按严重度排序，Critical 在前。"
            ),
            "stats": {"trials": 0, "avg_quality": 0.0, "total_findings": 0},
        },
    },
    "bug_fix": {
        "v1_direct": {
            "template": (
                "Fix the following issue: {description}. "
                "Files involved: {files}. "
                "After fixing, run the relevant tests to verify. "
                "Show the diff and test results."
            ),
            "stats": {"trials": 0, "avg_quality": 0.0, "total_findings": 0},
        },
    },
    "architecture_review": {
        "v1_holistic": {
            "template": (
                "Perform an architecture review of {files}. "
                "Analyze: component coupling, dependency direction, "
                "separation of concerns, error handling strategy, "
                "extensibility, and testability. "
                "Create a mermaid diagram of the dependency graph. "
                "Output findings as: ID | Severity | Component | Issue | Recommendation."
            ),
            "stats": {"trials": 0, "avg_quality": 0.0, "total_findings": 0},
        },
    },
    "test_generation": {
        "v1_comprehensive": {
            "template": (
                "Write comprehensive tests for {files}. "
                "Cover: happy path, edge cases, error conditions, "
                "boundary values, and integration scenarios. "
                "Use pytest. Run the tests and fix any failures."
            ),
            "stats": {"trials": 0, "avg_quality": 0.0, "total_findings": 0},
        },
    },
    "security_audit": {
        "v1_owasp": {
            "template": (
                "Perform a security audit of {files}. "
                "Check against: injection, auth bypass, "
                "sensitive data exposure, SSRF, path traversal, "
                "unsafe deserialization, insecure defaults. "
                "Output: ID | OWASP Category | Severity | File:Line | Issue | Fix."
            ),
            "stats": {"trials": 0, "avg_quality": 0.0, "total_findings": 0},
        },
    },
}


# ── Data Types ──────────────────────────────────────────────────────

@dataclass
class CcTask:
    """A task to dispatch to a CC agent."""
    task_type: str                              # code_review, bug_fix, etc.
    description: str                            # Human-readable description
    files: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    timeout: int = 300                          # Seconds
    trace_id: str = ""
    parent_task_id: str = ""                    # For task decomposition tracking
    # ── Headless-mode fields ──
    model: str = "sonnet"                       # Model alias or full name
    fallback_model: str = ""                    # Fallback when overloaded
    max_turns: int = 25                         # Max agentic turns
    max_budget_usd: float = 10.0                # Max spend per task
    mcp_config: str | None = None               # Path to MCP config JSON
    agents_json: dict | None = None             # Custom agent team definitions
    json_schema: dict | None = None             # Force structured output
    system_prompt: str = ""                     # Appended system prompt
    cwd: str = ""                               # Working directory
    permission_mode: str = "bypassPermissions"  # default / plan / bypassPermissions
    stateless: bool = True                      # --no-session-persistence
    session_id: str = ""                        # Resume specific session
    effort: str = ""                            # low / medium / high
    allowed_tools: list[str] | None = None      # Restrict tools
    add_dirs: list[str] = field(default_factory=list)  # Additional dirs

    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = f"cc_{int(time.time())}_{uuid.uuid4().hex[:8]}"


@dataclass
class CcResult:
    """Result from a CC agent execution."""
    ok: bool
    agent: str
    task_type: str
    output: str
    elapsed_seconds: float
    findings_count: int = 0
    files_modified: int = 0
    template_used: str = ""
    quality_score: float = 0.0
    error: str = ""
    trace_id: str = ""
    # ── Headless-mode fields ──
    session_id: str = ""                        # CC session ID
    model_used: str = ""                        # Actual model used
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    num_turns: int = 0
    structured_output: Any = None               # Parsed JSON if json_schema used
    files_read: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    dispatch_mode: str = "headless"             # headless / hcom
    team_run_id: str = ""                       # Team control plane run id
    team_digest: str = ""                       # Human-readable team digest
    team_checkpoints: list[dict[str, Any]] = field(default_factory=list)
    role_results: dict[str, dict[str, Any]] = field(default_factory=dict)


# ── Agent Capability Profile ────────────────────────────────────────

@dataclass
class AgentProfile:
    """EvoMap-derived capability profile for a CC agent."""
    name: str
    capabilities: dict[str, float] = field(default_factory=dict)
    # per task_type → {success_rate, avg_quality, avg_latency, trials}
    total_tasks: int = 0
    total_successes: int = 0
    last_active: float = 0.0


# ── CcExecutor ──────────────────────────────────────────────────────

class CcExecutor:
    """Unified gateway for CC agent interactions.

    Primary mode: headless (`claude -p`) subprocess with structured JSON.
    Fallback mode: hcom terminal injection (legacy, for when CLI unavailable).

    Manages the full lifecycle:
    1. Prompt construction (template registry)
    2. CLI parameter assembly
    3. Subprocess dispatch (async-capable)
    4. Realtime stream-json parsing
    5. Quality evaluation
    6. Signal emission (EvoMap + Langfuse)
    """

    def __init__(
        self,
        observer: Any = None,
        hcom_dir: str = HCOM_DIR,
        auto_recover: bool = False,
        recovery_interval: int = 300,
        event_bus: Any = None,
    ) -> None:
        self._observer = observer
        self._event_bus = event_bus
        self._hcom_dir = hcom_dir
        self._templates = dict(_DEFAULT_TEMPLATES)
        self._agent_profiles: dict[str, AgentProfile] = {}
        self._load_template_stats()
        self._recovery_thread: threading.Thread | None = None
        self._recovery_stop = threading.Event()
        self._cc_cli = shutil.which(CC_CLI) or CC_CLI
        self._headless_available: bool | None = None  # Lazy-detected

        if auto_recover:
            self.start_recovery_daemon(recovery_interval)

    # ── Public API: Dispatch ──────────────────────────────────────

    def dispatch(
        self,
        task: CcTask,
        agent: str | None = None,
        template: str | None = None,
    ) -> CcResult:
        """Unified dispatch: headless first, hcom fallback.

        Args:
            task: Task to execute.
            agent: Force a specific agent (hcom mode only).
            template: Force a specific template. If None, selects best.

        Returns:
            CcResult with output, quality score, and metadata.
        """
        if template is None:
            template = self._select_template(task.task_type)

        # Prefer headless if claude CLI is available
        if self._is_headless_available():
            return self._dispatch_headless_sync(task, template)

        # Fallback to hcom
        logger.info("CcExecutor: headless unavailable, falling back to hcom")
        return self._dispatch_hcom(task, agent, template)

    async def dispatch_headless(
        self,
        task: CcTask,
        template: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> CcResult:
        """Async headless dispatch via `claude -p` subprocess.

        Args:
            task: Task to execute.
            template: Force a specific template.
            progress_callback: Optional callback for realtime progress updates.
                Called with {"type": "text", "content": "..."} for each chunk.

        Returns:
            CcResult with structured output and full metadata.
        """
        started_at = time.time()
        if template is None:
            template = self._select_template(task.task_type)

        prompt = self._build_prompt(task, template)

        self._emit("task.dispatched", task.trace_id, {
            "dispatch_mode": "headless",
            "task_type": task.task_type,
            "template": template,
            "model": task.model,
            "prompt_length": len(prompt),
            "files": task.files,
            "timeout": task.timeout,
        })

        try:
            result = await self._run_headless(
                task, prompt, progress_callback=progress_callback,
            )
        except Exception as e:
            elapsed = time.time() - started_at
            result = CcResult(
                ok=False, agent="headless", task_type=task.task_type,
                output="", elapsed_seconds=elapsed,
                error=str(e), trace_id=task.trace_id,
                template_used=template, dispatch_mode="headless",
            )

        result.template_used = template
        result.elapsed_seconds = time.time() - started_at

        # Quality evaluation
        if result.ok and result.output:
            result.findings_count = self._count_findings(result.output)
            result.files_modified = self._count_files_modified(result.output)
            result.quality_score = self._evaluate_quality(result.output, task)

        # Emit completion signals
        self._emit_completion(task, result)
        self._update_template_stats(
            task.task_type, template,
            result.quality_score, result.findings_count,
        )
        self._emit_langfuse_trace(task, result)
        self.save_template_stats()

        return result

    async def dispatch_conversation(
        self,
        tasks: list[CcTask],
        progress_callback: Callable[[dict], None] | None = None,
    ) -> list[CcResult]:
        """Execute multi-turn conversation.

        First task creates a new session, subsequent tasks use --continue
        to resume in the same context.

        Args:
            tasks: Ordered list of tasks forming a conversation.
            progress_callback: Optional progress callback.

        Returns:
            List of CcResult, one per task.
        """
        results: list[CcResult] = []
        session_id = ""

        for i, task in enumerate(tasks):
            if i > 0 and session_id:
                # Continue previous session
                task.stateless = False
                task.session_id = session_id

            result = await self.dispatch_headless(
                task, progress_callback=progress_callback,
            )
            results.append(result)

            if result.session_id:
                session_id = result.session_id

            if not result.ok:
                logger.warning(
                    "CcExecutor: conversation turn %d failed: %s",
                    i + 1, result.error,
                )
                break

        return results

    async def dispatch_parallel(
        self,
        tasks: list[CcTask],
        max_concurrent: int = 3,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> list[CcResult]:
        """Execute multiple independent tasks concurrently.

        Args:
            tasks: List of independent tasks.
            max_concurrent: Max concurrent subprocess count.
            progress_callback: Optional progress callback.

        Returns:
            List of CcResult in same order as input tasks.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _run_one(task: CcTask) -> CcResult:
            async with semaphore:
                return await self.dispatch_headless(
                    task, progress_callback=progress_callback,
                )

        return await asyncio.gather(*[_run_one(t) for t in tasks])

    async def dispatch_team(
        self,
        task: CcTask,
        team: "dict | None" = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> CcResult:
        """Execute with agent teams (--teammate-mode in-process).

        Args:
            task: Task to execute.
            team: Agent team definitions. Accepts raw dict (legacy) or
                TeamSpec (validated). If None, uses task.agents_json.
            progress_callback: Optional progress callback.

        Returns:
            CcResult from the lead agent.
        """
        from chatgptrest.kernel.team_types import TeamSpec

        if isinstance(team, TeamSpec):
            task.agents_json = team.to_agents_json()
        elif isinstance(team, dict) and team:
            spec = TeamSpec.from_dict(team)
            task.agents_json = spec.to_agents_json()
        elif team is not None:
            task.agents_json = team
        return await self.dispatch_headless(
            task, progress_callback=progress_callback,
        )

    # ── Sync wrapper ──────────────────────────────────────────────

    def _dispatch_headless_sync(
        self, task: CcTask, template: str,
    ) -> CcResult:
        """Sync wrapper for dispatch_headless."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context — run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self.dispatch_headless(task, template=template),
                )
                return future.result(timeout=task.timeout + 30)
        else:
            return asyncio.run(
                self.dispatch_headless(task, template=template),
            )

    # ── Core Headless Engine ──────────────────────────────────────

    async def _run_headless(
        self,
        task: CcTask,
        prompt: str,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> CcResult:
        """Launch `claude -p` subprocess and parse stream-json output."""
        args = self._build_cli_args(task, prompt)

        logger.info(
            "CcExecutor: headless dispatch [%s] model=%s timeout=%ds",
            task.task_type, task.model, task.timeout,
        )

        cwd = task.cwd or task.context.get("cwd") or "."

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        # Parse stream-json output
        text_chunks: list[str] = []
        metadata: dict[str, Any] = {}
        tools_used: list[str] = []
        files_read: list[str] = []
        num_turns = 0

        try:
            async with asyncio.timeout(task.timeout):
                async for line_bytes in proc.stdout:
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        # Non-JSON line (startup noise, etc.)
                        continue

                    parsed = self._parse_stream_event(event)

                    if parsed["type"] == "text":
                        text_chunks.append(parsed["content"])
                        if progress_callback:
                            try:
                                progress_callback(parsed)
                            except Exception:
                                pass

                    elif parsed["type"] == "tool_use":
                        tool_name = parsed.get("tool", "")
                        if tool_name:
                            tools_used.append(tool_name)
                        if tool_name in ("Read", "Glob", "Grep"):
                            fname = parsed.get("file", "")
                            if fname:
                                files_read.append(fname)
                        if progress_callback:
                            try:
                                progress_callback(parsed)
                            except Exception:
                                pass

                    elif parsed["type"] == "turn":
                        num_turns += 1

                    elif parsed["type"] == "result":
                        metadata = parsed.get("metadata", {})
                        logger.debug("CcExecutor: received terminal 'result' event, breaking loop.")
                        break

                    elif parsed["type"] == "error":
                        raise RuntimeError(parsed.get("message", "unknown error"))

        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return CcResult(
                ok=False, agent="headless", task_type=task.task_type,
                output="\n".join(text_chunks),
                elapsed_seconds=task.timeout,
                error=f"timeout after {task.timeout}s",
                trace_id=task.trace_id, dispatch_mode="headless",
                num_turns=num_turns, tools_used=tools_used,
                files_read=files_read,
            )

        # Force kill the process since stdio MCP servers prevent graceful exit
        try:
            if proc.returncode is None:
                proc.kill()
        except OSError:
            pass

        stderr_data = await proc.stderr.read()
        returncode = await proc.wait()

        output = "\n".join(text_chunks)

        # Ignore returncode == 143 (SIGTERM) or 137 (SIGKILL) since we explicitly kill it
        if returncode not in (0, -9, 137, -15, 143) and not output:
            return CcResult(
                ok=False, agent="headless", task_type=task.task_type,
                output="", elapsed_seconds=0,
                error=stderr_data.decode("utf-8", errors="replace")[:2000],
                trace_id=task.trace_id, dispatch_mode="headless",
            )

        return CcResult(
            ok=True,
            agent="headless",
            task_type=task.task_type,
            output=output,
            elapsed_seconds=0,  # Set by caller
            trace_id=task.trace_id,
            dispatch_mode="headless",
            session_id=metadata.get("session_id", ""),
            model_used=metadata.get("model", task.model),
            input_tokens=metadata.get("input_tokens", 0),
            output_tokens=metadata.get("output_tokens", 0),
            cost_usd=metadata.get("cost_usd", 0.0),
            num_turns=num_turns or metadata.get("num_turns", 0),
            structured_output=metadata.get("structured_output"),
            tools_used=tools_used,
            files_read=files_read,
        )

    def _build_cli_args(self, task: CcTask, prompt: str) -> list[str]:
        """Build the `claude` CLI argument list from task configuration."""
        args = [self._cc_cli, "-p", prompt]
        args += ["--output-format", "stream-json"]
        args += ["--verbose"]

        if task.stateless:
            args += ["--no-session-persistence"]

        if task.session_id:
            args += ["--resume", task.session_id]

        if task.permission_mode:
            args += ["--permission-mode", task.permission_mode]

        if task.model:
            args += ["--model", task.model]

        if task.fallback_model:
            args += ["--fallback-model", task.fallback_model]

        if task.max_turns:
            args += ["--max-turns", str(task.max_turns)]

        if task.max_budget_usd:
            args += ["--max-budget-usd", str(task.max_budget_usd)]

        if task.mcp_config:
            args += ["--mcp-config", task.mcp_config]

        if task.agents_json:
            args += ["--agents", json.dumps(task.agents_json)]
            args += ["--teammate-mode", "in-process"]

        if task.json_schema:
            args += ["--json-schema", json.dumps(task.json_schema)]

        if task.system_prompt:
            args += ["--append-system-prompt", task.system_prompt]

        if task.effort:
            args += ["--effort", task.effort]

        if task.allowed_tools is not None:
            if task.allowed_tools:
                args += ["--tools", ",".join(task.allowed_tools)]
            else:
                args += ["--tools", ""]

        for d in task.add_dirs:
            args += ["--add-dir", d]

        return args

    def _parse_stream_event(self, event: dict) -> dict:
        """Parse a single stream-json event into a normalized format.

        CC stream-json events can have various shapes. This normalizes
        them into: {type, content?, tool?, metadata?}.
        """
        etype = event.get("type", "")

        # ── Text content from assistant message ──
        if etype == "assistant":
            content_blocks = (
                event.get("message", {}).get("content", [])
            )
            text_parts = []
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            return {"type": "text", "content": "\n".join(text_parts)}

        # ── Content block delta (streaming partial) ──
        if etype == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                return {"type": "text", "content": delta.get("text", "")}

        # ── Tool use ──
        if etype == "tool_use" or (
            etype == "content_block_start"
            and event.get("content_block", {}).get("type") == "tool_use"
        ):
            block = event.get("content_block", event)
            return {
                "type": "tool_use",
                "tool": block.get("name", ""),
                "input": block.get("input", {}),
                "file": (block.get("input", {}) or {}).get("file_path", ""),
            }

        # ── Result (final event with metadata) ──
        if etype == "result":
            return {
                "type": "result",
                "metadata": {
                    "session_id": event.get("session_id", ""),
                    "model": event.get("model", ""),
                    "input_tokens": event.get("input_tokens", 0),
                    "output_tokens": event.get("output_tokens", 0),
                    "cost_usd": event.get("cost_usd", 0.0),
                    "num_turns": event.get("num_turns", 0),
                    "structured_output": event.get("result", ""),
                },
            }

        # ── Message start/stop (turn boundary) ──
        if etype in ("message_start", "message_stop"):
            return {"type": "turn"}

        # ── Error ──
        if etype == "error":
            return {
                "type": "error",
                "message": event.get("error", {}).get("message", str(event)),
            }

        # ── System / unknown — try to extract text ──
        if etype == "system":
            subtype = event.get("subtype", "")
            if subtype == "init":
                return {"type": "text", "content": ""}
            return {"type": "text", "content": event.get("message", "")}

        # Fallback: if it has a "result" key, treat as result
        if "result" in event and "session_id" in event:
            return {
                "type": "result",
                "metadata": {
                    "session_id": event.get("session_id", ""),
                    "model": event.get("model", ""),
                    "input_tokens": event.get("input_tokens_used",
                                              event.get("input_tokens", 0)),
                    "output_tokens": event.get("output_tokens_used",
                                               event.get("output_tokens", 0)),
                    "cost_usd": event.get("cost_usd", 0.0),
                    "num_turns": event.get("num_turns", 0),
                    "structured_output": event.get("result", ""),
                },
            }

        return {"type": "unknown", "raw": event}

    # ── Capability Detection ──────────────────────────────────────

    def _is_headless_available(self) -> bool:
        """Check if `claude` CLI is available for headless dispatch."""
        if self._headless_available is not None:
            return self._headless_available

        try:
            result = subprocess.run(
                [self._cc_cli, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            self._headless_available = result.returncode == 0
        except Exception:
            self._headless_available = False

        if self._headless_available:
            logger.info("CcExecutor: headless mode available (claude CLI found)")
        else:
            logger.warning("CcExecutor: headless mode unavailable, will use hcom")

        return self._headless_available

    # ── Legacy hcom Dispatch ──────────────────────────────────────

    def _dispatch_hcom(
        self,
        task: CcTask,
        agent: str | None = None,
        template: str | None = None,
    ) -> CcResult:
        """Legacy dispatch via hcom terminal injection.

        Preserved for environments where `claude` CLI is not installed
        but CC agents are running in tmux panes via hcom.
        """
        started_at = time.time()

        # 1. Select agent
        if agent is None:
            agent = self.select_agent(task.task_type)
        self._emit("agent.selected", task.trace_id, {
            "agent": agent,
            "task_type": task.task_type,
            "selection_method": "explicit" if agent else "evomap",
        })

        # 2. Build prompt from template
        if template is None:
            template = self._select_template(task.task_type)
        prompt = self._build_prompt(task, template)
        self._emit("task.dispatched", task.trace_id, {
            "dispatch_mode": "hcom",
            "agent": agent,
            "task_type": task.task_type,
            "template": template,
            "prompt_length": len(prompt),
            "files": task.files,
            "timeout": task.timeout,
        })

        # 3. Dispatch via hcom
        inject_ok = self._hcom_inject(agent, prompt)
        if not inject_ok:
            result = CcResult(
                ok=False, agent=agent, task_type=task.task_type,
                output="", elapsed_seconds=time.time() - started_at,
                error="hcom inject failed", trace_id=task.trace_id,
                template_used=template, dispatch_mode="hcom",
            )
            self._emit("task.failed", task.trace_id, {
                "agent": agent, "error_type": "inject_failed",
                "elapsed_s": result.elapsed_seconds,
            })
            return result

        # 4. Wait for completion
        output = self._wait_for_completion(agent, task.timeout)
        elapsed = time.time() - started_at

        if not output:
            result = CcResult(
                ok=False, agent=agent, task_type=task.task_type,
                output="", elapsed_seconds=elapsed,
                error="timeout or no output", trace_id=task.trace_id,
                template_used=template, dispatch_mode="hcom",
            )
            return result

        # 5. Evaluate output quality
        findings_count = self._count_findings(output)
        files_modified = self._count_files_modified(output)
        quality = self._evaluate_quality(output, task)

        result = CcResult(
            ok=True, agent=agent, task_type=task.task_type,
            output=output, elapsed_seconds=elapsed,
            findings_count=findings_count,
            files_modified=files_modified,
            template_used=template,
            quality_score=quality,
            trace_id=task.trace_id,
            dispatch_mode="hcom",
        )

        # 6. Complete
        self._emit_completion(task, result)
        self._update_agent_profile(agent, task.task_type, True, quality, elapsed)
        self._update_template_stats(task.task_type, template, quality, findings_count)
        self._emit_langfuse_trace(task, result)
        self.save_template_stats()

        return result

    # ── Agent Selection (EvoMap-driven) ───────────────────────────

    def select_agent(self, task_type: str) -> str:
        """Select the best available CC agent for a task type.

        Selection priority:
        1. EvoMap capability profile (success_rate × avg_quality)
        2. Agent availability (not stalled/zombie)
        3. Round-robin fallback
        """
        available = self._get_available_agents()
        if not available:
            logger.warning("No CC agents available")
            return ""

        # Load profiles from EvoMap
        self._refresh_profiles_from_evomap()

        scored: list[tuple[str, float]] = []
        for agent in available:
            profile = self._agent_profiles.get(agent)
            if profile and task_type in profile.capabilities:
                score = profile.capabilities[task_type]
            elif profile and profile.total_tasks > 0:
                avg = profile.total_successes / max(profile.total_tasks, 1)
                score = avg * 0.7
            else:
                score = 0.5
            scored.append((agent, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0][0]
        logger.info(
            "CcExecutor: selected %s for %s (score %.2f, candidates: %s)",
            best, task_type, scored[0][1],
            [(a, f"{s:.2f}") for a, s in scored],
        )
        return best

    def list_agents(self) -> list[dict[str, Any]]:
        """List all CC agents with status."""
        return self._get_agent_status()

    def check_health(self) -> dict[str, Any]:
        """Check pipeline health: headless availability, daemon, agents."""
        health: dict[str, Any] = {
            "headless_available": self._is_headless_available(),
            "cc_cli": self._cc_cli,
        }

        # Also check hcom layer
        agents = self._get_agent_status()
        zombies = [
            a for a in agents
            if a.get("status") == "listening"
            and a.get("idle_minutes", 0) > 30
        ]
        active = sum(1 for a in agents if a.get("status") != "stopped")
        health.update({
            "daemon_running": self._daemon_running(),
            "total_agents": len(agents),
            "active_agents": active,
            "max_agents": MAX_CC_AGENTS,
            "at_capacity": active >= MAX_CC_AGENTS,
            "zombies": [z["name"] for z in zombies],
            "agents": agents,
        })

        return health

    # ── hcom Subprocess Layer (legacy) ───────────────────────────

    def _hcom_cmd(self, *args: str, timeout: int = 10) -> tuple[bool, str]:
        """Run an hcom command with HCOM_DIR set."""
        env = {**os.environ, "HCOM_DIR": self._hcom_dir}
        cmd = ["hcom", *args]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, env=env,
            )
            return result.returncode == 0, result.stdout
        except subprocess.TimeoutExpired:
            logger.warning("hcom timeout: %s", " ".join(cmd))
            return False, ""
        except Exception as e:
            logger.warning("hcom error: %s — %s", " ".join(cmd), e)
            return False, ""

    def _hcom_inject(self, agent: str, text: str) -> bool:
        """Inject text into a CC agent's PTY via hcom."""
        ok, output = self._hcom_cmd("term", "inject", agent, text, "--enter", timeout=15)
        if ok:
            logger.info("CcExecutor: injected %d chars to %s", len(text), agent)
        else:
            logger.error("CcExecutor: inject failed for %s", agent)
        return ok

    def _wait_for_completion(self, agent: str, timeout: int) -> str:
        """Poll hcom term output until CC finishes or timeout."""
        start = time.time()
        poll_interval = 5
        initial_grace = 10
        last_output = ""
        stable_count = 0

        time.sleep(initial_grace)

        while time.time() - start < timeout:
            ok, output = self._hcom_cmd("term", agent, "--json", timeout=10)
            if not ok:
                time.sleep(poll_interval)
                continue

            try:
                data = json.loads(output)
                lines = data.get("lines", [])
                screen_text = "\n".join(lines) if isinstance(lines, list) else str(lines)
            except (json.JSONDecodeError, TypeError):
                screen_text = output

            if self._is_cc_idle(screen_text):
                return self._extract_cc_output(screen_text)

            if screen_text == last_output:
                stable_count += 1
                if stable_count > 6:
                    self._emit("task.stalled", "", {
                        "agent": agent,
                        "idle_s": stable_count * poll_interval,
                    })
            else:
                stable_count = 0
                last_output = screen_text

            time.sleep(poll_interval)

        logger.warning("CcExecutor: timeout waiting for %s (%ds)", agent, timeout)
        return last_output if last_output else ""

    def _is_cc_idle(self, screen_text: str) -> bool:
        """Detect if CC agent is at an idle prompt."""
        lines = screen_text.strip().split("\n")
        if not lines:
            return False
        tail = "\n".join(lines[-5:])
        patterns = [
            r"⏵⏵\s+bypass permissions",
            r"✻\s+(Brewed|Cooked|Whipped|Sautéing|Grilled)\s+for\s+\d+",
        ]
        has_prompt = bool(re.search(r"^❯\s*$", tail, re.MULTILINE))
        has_completion = any(re.search(p, tail) for p in patterns)
        return has_prompt or has_completion

    def _extract_cc_output(self, screen_text: str) -> str:
        """Extract meaningful output from CC's PTY screen."""
        lines = screen_text.strip().split("\n")
        cleaned = []
        for line in lines:
            m = re.match(r"^\s*\d+:\s?(.*)", line)
            if m:
                cleaned.append(m.group(1))
            else:
                cleaned.append(line)
        return "\n".join(cleaned)

    def _get_available_agents(self) -> list[str]:
        """Get list of available CC agents from hcom list."""
        ok, output = self._hcom_cmd("list")
        if not ok:
            return []
        agents = []
        for line in output.split("\n"):
            m = re.match(r"◉\s+(\S+)\s+now:\s+(listening|active|blocked)", line)
            if m:
                agents.append(m.group(1))
        return agents[:MAX_CC_AGENTS]

    def _get_agent_status(self) -> list[dict[str, Any]]:
        """Get detailed status for all agents."""
        ok, output = self._hcom_cmd("list")
        if not ok:
            return []
        agents = []
        for line in output.split("\n"):
            m = re.match(r"([◉◎○])\s+(\S+)\s+now:\s+(\w+)\s+since\s+(\S+)", line)
            if m:
                agents.append({
                    "name": m.group(2),
                    "status": m.group(3),
                    "since": m.group(4),
                    "indicator": m.group(1),
                })
        return agents

    def _daemon_running(self) -> bool:
        """Check if hcom daemon is running."""
        ok, output = self._hcom_cmd("status")
        return ok and "daemon:    running" in output

    # ── Prompt Construction ─────────────────────────────────────

    def _select_template(self, task_type: str) -> str:
        """Select best-performing template for a task type."""
        templates = self._templates.get(task_type, {})
        if not templates:
            return "v1_default"

        best_name = ""
        best_score = -1.0
        for name, tmpl in templates.items():
            stats = tmpl.get("stats", {})
            trials = stats.get("trials", 0)
            quality = stats.get("avg_quality", 0.0)
            if trials >= 3:
                score = quality
            elif trials > 0:
                score = (quality * trials + 0.5 * 3) / (trials + 3)
            else:
                score = 0.5

            if score > best_score:
                best_score = score
                best_name = name

        return best_name or next(iter(templates))

    def _build_prompt(self, task: CcTask, template_name: str) -> str:
        """Build a prompt from template + task context."""
        templates = self._templates.get(task.task_type, {})
        tmpl_data = templates.get(template_name, {})
        template_str = tmpl_data.get("template", "")

        if not template_str:
            return task.description

        files_str = ", ".join(task.files) if task.files else "all relevant files"
        return template_str.format(
            files=files_str,
            description=task.description,
            **task.context,
        )

    # ── Quality Evaluation ──────────────────────────────────────

    def _evaluate_quality(self, output: str, task: CcTask) -> float:
        """Auto-evaluate CC output quality (0.0–1.0)."""
        score = 0.0

        # Length score (0–0.3)
        chars = len(output.strip())
        if chars > 2000:
            score += 0.3
        elif chars > 500:
            score += 0.2
        elif chars > 100:
            score += 0.1

        # Structure score (0–0.3)
        has_table = bool(re.search(r"\|.*\|.*\|", output))
        has_headers = bool(re.search(r"^#{1,3}\s", output, re.MULTILINE))
        has_code = bool(re.search(r"```", output))
        has_findings = bool(re.search(
            r"(Critical|High|Medium|Low|严重|高|中|低)", output, re.I,
        ))
        structure_count = sum([has_table, has_headers, has_code, has_findings])
        score += min(0.3, structure_count * 0.1)

        # Task-specific scoring (0–0.4)
        if task.task_type == "code_review":
            findings = self._count_findings(output)
            score += min(0.4, findings * 0.05)
        elif task.task_type == "bug_fix":
            has_diff = bool(re.search(r"(\+\+\+|---|>.*<.*)", output))
            has_test = bool(re.search(r"(test|pytest|passed|✓|✅)", output, re.I))
            score += 0.2 if has_diff else 0.0
            score += 0.2 if has_test else 0.0
        elif task.task_type == "test_generation":
            test_count = len(re.findall(r"def test_", output))
            score += min(0.4, test_count * 0.04)
        else:
            score += 0.2 if chars > 1000 else 0.1

        return min(1.0, round(score, 2))

    @staticmethod
    def _count_findings(output: str) -> int:
        """Count review findings in output."""
        patterns = [
            r"[RF]-\d{3}",
            r"\b(Critical|High|Medium|Low)\b",
            r"(严重|高|中等|低)\b",
        ]
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, output, re.I))
        return max(1, count // 2) if count > 0 else 0

    @staticmethod
    def _count_files_modified(output: str) -> int:
        """Count files modified in output."""
        patterns = [
            r"Update\((\S+\.py)\)",
            r"Write\((\S+\.py)\)",
            r"Added \d+ lines?, removed \d+ lines?",
        ]
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, output))
        return count

    # ── Signal Emission ─────────────────────────────────────────

    def _emit(self, signal_type: str, trace_id: str, data: dict) -> None:
        """Emit an EvoMap signal for the cc_pipeline domain.

        Phase-1 fix: prefers EventBus when available, falls back to direct
        observer for backward compatibility.
        """
        # Prefer EventBus path (unified pipeline)
        if self._event_bus:
            try:
                from chatgptrest.kernel.event_bus import TraceEvent
                event = TraceEvent.create(
                    source="cc_executor",
                    event_type=signal_type,
                    trace_id=trace_id or "",
                    data=data,
                )
                self._event_bus.emit(event)
                return
            except Exception as e:
                logger.debug("CcExecutor: EventBus emit failed, fallback to observer: %s", e)

        # Fallback: direct observer (legacy)
        if not self._observer:
            logger.debug("CcExecutor: no observer/event_bus, skipping signal %s", signal_type)
            return
        try:
            self._observer.record_event(
                trace_id=trace_id or "",
                signal_type=signal_type,
                source="cc_executor",
                domain="cc_pipeline",
                data=data,
            )
        except Exception as e:
            logger.debug("CcExecutor: signal emission failed: %s", e)

    def _emit_completion(self, task: CcTask, result: CcResult) -> None:
        """Emit task completion and quality gate signals."""
        self._emit("task.completed", task.trace_id, {
            "dispatch_mode": result.dispatch_mode,
            "agent": result.agent,
            "task_type": task.task_type,
            "elapsed_s": result.elapsed_seconds,
            "findings_count": result.findings_count,
            "files_modified": result.files_modified,
            "output_chars": len(result.output) if result.output else 0,
            "template": result.template_used,
            "model_used": result.model_used,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": result.cost_usd,
            "num_turns": result.num_turns,
        })
        self._emit("gate.review_quality", task.trace_id, {
            "agent": result.agent,
            "task_type": task.task_type,
            "score": result.quality_score,
            "findings_count": result.findings_count,
            "evaluator": "auto",
        })

    # ── Profile Management ──────────────────────────────────────

    def _refresh_profiles_from_evomap(self) -> None:
        """Load/refresh agent profiles from EvoMap signals."""
        if not self._observer:
            return
        try:
            signals = self._observer.query(
                domain="cc_pipeline",
                signal_type="gate.review_quality",
            )
            agg: dict[str, dict[str, list[float]]] = {}
            for sig in signals:
                data = sig.get("data", {})
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except Exception:
                        continue
                agent = data.get("agent", "")
                task_type = data.get("task_type", "")
                quality = data.get("score", 0.0)
                if agent and task_type:
                    agg.setdefault(agent, {}).setdefault(task_type, []).append(quality)

            for agent_name, task_scores in agg.items():
                profile = self._agent_profiles.setdefault(
                    agent_name, AgentProfile(name=agent_name),
                )
                for task_type, scores in task_scores.items():
                    if scores:
                        profile.capabilities[task_type] = sum(scores) / len(scores)
                profile.total_tasks = sum(len(s) for s in task_scores.values())
        except Exception as e:
            logger.debug("CcExecutor: profile refresh failed: %s", e)

    def _update_agent_profile(
        self, agent: str, task_type: str,
        success: bool, quality: float, elapsed: float,
    ) -> None:
        """Update agent profile after task completion."""
        profile = self._agent_profiles.setdefault(
            agent, AgentProfile(name=agent),
        )
        profile.total_tasks += 1
        if success:
            profile.total_successes += 1
        profile.last_active = time.time()

        old = profile.capabilities.get(task_type, 0.5)
        alpha = 0.3
        profile.capabilities[task_type] = old * (1 - alpha) + quality * alpha

    def _update_template_stats(
        self, task_type: str, template: str,
        quality: float, findings: int,
    ) -> None:
        """Update template performance stats."""
        templates = self._templates.get(task_type, {})
        tmpl = templates.get(template, {})
        stats = tmpl.get("stats", {})

        n = stats.get("trials", 0)
        old_q = stats.get("avg_quality", 0.0)
        new_q = (old_q * n + quality) / (n + 1) if n > 0 else quality
        stats["trials"] = n + 1
        stats["avg_quality"] = round(new_q, 3)
        stats["total_findings"] = stats.get("total_findings", 0) + findings
        tmpl["stats"] = stats

    def _load_template_stats(self) -> None:
        """Load template stats from persistent storage."""
        stats_path = Path(self._hcom_dir) / "cc_template_stats.json"
        if stats_path.exists():
            try:
                with open(stats_path) as f:
                    saved = json.load(f)
                for task_type, templates in saved.items():
                    if task_type in self._templates:
                        for tmpl_name, tmpl_stats in templates.items():
                            if tmpl_name in self._templates[task_type]:
                                self._templates[task_type][tmpl_name]["stats"] = tmpl_stats
                logger.info("CcExecutor: loaded template stats from %s", stats_path)
            except Exception as e:
                logger.debug("CcExecutor: template stats load failed: %s", e)

    def save_template_stats(self) -> None:
        """Persist template stats to disk."""
        stats_path = Path(self._hcom_dir) / "cc_template_stats.json"
        try:
            out = {}
            for task_type, templates in self._templates.items():
                out[task_type] = {}
                for tmpl_name, tmpl_data in templates.items():
                    out[task_type][tmpl_name] = tmpl_data.get("stats", {})
            stats_path.parent.mkdir(parents=True, exist_ok=True)
            with open(stats_path, "w") as f:
                json.dump(out, f, indent=2)
        except Exception as e:
            logger.warning("CcExecutor: template stats save failed: %s", e)

    # ── Zombie / Stall Detection ────────────────────────────────

    def detect_zombies(self) -> list[str]:
        """Detect zombie CC agents (listening but unresponsive)."""
        ok, output = self._hcom_cmd("events", "--type", "status", "--last", "50")
        if not ok:
            return []

        agents = self._get_available_agents()
        last_events: dict[str, float] = {}

        for line in output.split("\n"):
            for agent in agents:
                if agent in line:
                    m = re.search(r"(\d+)([smh])\s+ago", line)
                    if m:
                        val, unit = int(m.group(1)), m.group(2)
                        seconds = val * {"s": 1, "m": 60, "h": 3600}.get(unit, 1)
                        if agent not in last_events or seconds < last_events[agent]:
                            last_events[agent] = seconds

        zombies = []
        for agent in agents:
            last = last_events.get(agent, float("inf"))
            if last > 1800:
                zombies.append(agent)
                self._emit("agent.zombie_detected", "", {
                    "agent": agent,
                    "idle_seconds": last,
                })

        return zombies

    def kill_and_restart(self, agent: str, tag: str = "cc") -> bool:
        """Kill a zombie agent and restart a fresh one."""
        current = self._get_available_agents()
        if len(current) > MAX_CC_AGENTS:
            logger.warning(
                "CcExecutor: at capacity (%d/%d), killing %s without restart",
                len(current), MAX_CC_AGENTS, agent,
            )
            self._hcom_cmd("kill", agent, timeout=10)
            return True
        logger.info("CcExecutor: killing zombie %s", agent)
        self._hcom_cmd("kill", agent, timeout=10)
        time.sleep(2)
        ok, _ = self._hcom_cmd(
            "1", "claude", "--tag", tag,
            "--terminal", "tmux",
            "--dangerously-skip-permissions",
            timeout=30,
        )
        if ok:
            self._emit("agent.restarted", "", {
                "old_agent": agent,
                "tag": tag,
            })
        return ok

    # ── Auto-Recovery Daemon ────────────────────────────────────

    def start_recovery_daemon(self, interval: int = 300) -> None:
        """Start background thread for periodic zombie detection + restart."""
        if self._recovery_thread and self._recovery_thread.is_alive():
            return

        def _daemon():
            logger.info("CcExecutor: recovery daemon started (interval=%ds)", interval)
            while not self._recovery_stop.wait(interval):
                try:
                    self._run_recovery_cycle()
                except Exception as e:
                    logger.debug("CcExecutor: recovery cycle error: %s", e)

        self._recovery_thread = threading.Thread(
            target=_daemon, daemon=True, name="cc-recovery",
        )
        self._recovery_thread.start()

    def stop_recovery_daemon(self) -> None:
        """Stop the recovery daemon thread."""
        self._recovery_stop.set()
        if self._recovery_thread:
            self._recovery_thread.join(timeout=5)
            self._recovery_thread = None
        self._recovery_stop.clear()

    def _run_recovery_cycle(self) -> None:
        """One cycle: detect zombies → kill → restart → emit signals."""
        zombies = self.detect_zombies()
        if not zombies:
            return

        logger.warning("CcExecutor: detected %d zombies: %s", len(zombies), zombies)
        for agent in zombies:
            ok = self.kill_and_restart(agent)
            self._emit("recovery.cycle", "", {
                "agent": agent,
                "action": "restarted" if ok else "restart_failed",
            })

    # ── Langfuse CC Pipeline Traces ─────────────────────────────

    def _emit_langfuse_trace(
        self,
        task: "CcTask",
        result: "CcResult",
    ) -> None:
        """Emit a Langfuse trace for a CC pipeline execution."""
        try:
            from chatgptrest.observability import start_request_trace
            trace = start_request_trace(
                name=f"cc_pipeline.{task.task_type}",
                trace_id=task.trace_id,
                tags=["cc_pipeline", task.task_type, result.agent,
                      result.dispatch_mode],
                metadata={
                    "dispatch_mode": result.dispatch_mode,
                    "agent": result.agent,
                    "template": result.template_used,
                    "task_type": task.task_type,
                    "files": task.files,
                    "model": result.model_used or task.model,
                },
            )
            if not trace or not trace.trace_id:
                return

            gen = trace.generation(
                name=f"cc.{result.dispatch_mode}.{result.agent}",
                model=result.model_used or f"claude-code:{result.agent}",
                model_parameters={
                    "template": result.template_used,
                    "timeout": task.timeout,
                    "dispatch_mode": result.dispatch_mode,
                },
                metadata={
                    "task_type": task.task_type,
                    "files": task.files,
                },
            )
            if gen:
                gen.end(
                    output_meta={
                        "quality_score": result.quality_score,
                        "findings_count": result.findings_count,
                        "files_modified": result.files_modified,
                        "output_chars": len(result.output) if result.output else 0,
                        "cost_usd": result.cost_usd,
                        "num_turns": result.num_turns,
                    },
                    status="success" if result.ok else "error",
                    usage={
                        "input": result.input_tokens,
                        "output": result.output_tokens,
                        "total": result.input_tokens + result.output_tokens,
                    },
                    error=result.error or "",
                )

            try:
                from chatgptrest.observability import get_langfuse
                lf = get_langfuse()
                if lf:
                    lf.create_score(
                        trace_id=task.trace_id,
                        name="cc_quality",
                        value=result.quality_score,
                        comment=f"agent={result.agent} mode={result.dispatch_mode} "
                                f"template={result.template_used}",
                    )
            except Exception:
                pass

            trace.end()
        except Exception as e:
            logger.debug("CcExecutor: Langfuse trace failed: %s", e)

    # ── Template Evolution ──────────────────────────────────────

    def evolve_templates(self) -> dict[str, Any]:
        """Auto-promote/demote templates based on accumulated stats."""
        changes = {}
        for task_type, templates in self._templates.items():
            ranked = []
            for name, tmpl in templates.items():
                stats = tmpl.get("stats", {})
                trials = stats.get("trials", 0)
                quality = stats.get("avg_quality", 0.0)
                ranked.append((name, trials, quality))

            ranked.sort(key=lambda x: x[2], reverse=True)

            if len(ranked) >= 2:
                best = ranked[0]
                worst = ranked[-1]

                if best[1] >= 5 and worst[1] >= 5:
                    delta = best[2] - worst[2]
                    if delta > 0.15:
                        changes[task_type] = {
                            "promoted": best[0],
                            "promoted_quality": best[2],
                            "demoted": worst[0],
                            "demoted_quality": worst[2],
                            "delta": round(delta, 3),
                        }

                under_explored = [r for r in ranked if r[1] < 3]
                if under_explored:
                    changes.setdefault(task_type, {})["explore"] = [
                        r[0] for r in under_explored
                    ]

        self._emit("template.evolution", "", {
            "changes": changes,
            "task_types_evaluated": len(self._templates),
        })

        return changes

    def get_template_report(self) -> dict[str, Any]:
        """Get a report of all template performance data."""
        report = {}
        for task_type, templates in self._templates.items():
            entries = []
            for name, tmpl in templates.items():
                stats = tmpl.get("stats", {})
                entries.append({
                    "template": name,
                    "trials": stats.get("trials", 0),
                    "avg_quality": stats.get("avg_quality", 0.0),
                    "total_findings": stats.get("total_findings", 0),
                })
            entries.sort(key=lambda x: x["avg_quality"], reverse=True)
            report[task_type] = entries
        return report
