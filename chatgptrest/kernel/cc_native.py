"""CcNativeExecutor — Headless executor using Anthropic API + MCP directly.

Replaces the claude CLI subprocess model with a native Python ReAct loop.
Integrates with EvoMap/EventBus/MemoryManager for machine-readable
self-observation and evolution — no human dashboard needed.

Signal flow:
    CcNativeExecutor
        ├── EventBus.emit(dispatch.task_started)
        ├── _run_react_loop
        │   ├── EventBus.emit(llm.call_completed)   per LLM turn
        │   └── EventBus.emit(tool.call_completed)   per MCP tool call
        ├── EvoMapObserver.record(dispatch.task_completed | dispatch.task_failed)
        └── MemoryManager.stage_and_promote(episodic)  task summary
"""

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Callable, Dict

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from chatgptrest.kernel.cc_executor import CcTask, CcResult, _DEFAULT_TEMPLATES

logger = logging.getLogger(__name__)


def _text_preview(value: str | None, limit: int = 1000) -> str:
    raw = str(value or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 3] + "..."


# ── MCP Manager ─────────────────────────────────────────────────────

class McpManager:
    """Manages connections to multiple MCP servers defined in ~/.claude.json."""

    def __init__(self):
        self._exit_stack = AsyncExitStack()
        self.sessions: Dict[str, ClientSession] = {}
        self.tool_to_server: Dict[str, str] = {}
        self.available_tools: list[dict] = []

    async def initialize(self, mcp_config_path: str = None):
        config_path = mcp_config_path or os.path.expanduser("~/.claude.json")
        if not os.path.exists(config_path):
            logger.warning(f"MCP config not found: {config_path}")
            return

        with open(config_path, "r") as f:
            config = json.load(f)

        servers = config.get("mcpServers", {})
        for name, cfg in servers.items():
            try:
                await self._connect_server(name, cfg)
            except Exception as e:
                logger.error(f"Failed to connect MCP server {name}: {e}")

        for name, session in self.sessions.items():
            try:
                tools_response = await session.list_tools()
                for t in tools_response.tools:
                    self.tool_to_server[t.name] = name
                    schema = t.inputSchema
                    if "type" not in schema:
                        schema["type"] = "object"
                    self.available_tools.append({
                        "name": t.name,
                        "description": t.description or "",
                        "input_schema": schema
                    })
            except Exception as e:
                logger.error(f"Failed to list tools for {name}: {e}")

    async def _connect_server(self, name: str, cfg: dict):
        if name == "chatgptrest-mcp" and cfg.get("type") == "http":
            import sys
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            cfg = {
                "type": "stdio",
                "command": sys.executable,
                "args": [os.path.join(repo_root, "chatgptrest_agent_mcp_server.py"), "--transport", "stdio"],
                "env": {}
            }

        if cfg.get("type") == "stdio":
            command = cfg.get("command")
            args = cfg.get("args", [])
            if command in ("npx", "uvx") and "--yes" not in args and "-y" not in args:
                args = ["--yes"] + args
            env = cfg.get("env", {})
            full_env = os.environ.copy()
            full_env.update(env)
            server_params = StdioServerParameters(command=command, args=args, env=full_env)
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
        elif cfg.get("type") == "http":
            url = cfg.get("url")
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                sse_client(url)
            )
        else:
            raise ValueError(f"Unknown MCP server type: {cfg.get('type')}")

        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        self.sessions[name] = session
        logger.info(f"Connected to MCP server: {name}")

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        server_name = self.tool_to_server.get(tool_name)
        if not server_name:
            raise ValueError(f"Tool {tool_name} not found in any MCP server.")
        session = self.sessions[server_name]
        result = await session.call_tool(tool_name, arguments=arguments)
        if not result.content:
            return "Success (no output)"
        output = []
        for c in result.content:
            if c.type == "text":
                output.append(c.text)
            else:
                output.append(f"[{c.type} content]")
        return "\n".join(output)

    async def close(self):
        await self._exit_stack.aclose()


# ── Native Executor ─────────────────────────────────────────────────

class CcNativeExecutor:
    """Headless executor using Anthropic API and python MCP directly.

    Integrates with EvoMap/EventBus/MemoryManager for machine-driven
    self-observation. No Langfuse needed — all signals stay in-system.
    """

    def __init__(
        self,
        observer: Any = None,
        event_bus: Any = None,
        memory: Any = None,
        routing_fabric: Any = None,
        scorecard_store: Any = None,
        team_policy: Any = None,
        team_control_plane: Any = None,
    ):
        self._observer = observer
        self._event_bus = event_bus
        self._memory = memory
        self._routing_fabric = routing_fabric
        self._scorecard_store = scorecard_store
        self._team_policy = team_policy
        self._team_control_plane = team_control_plane
        self._templates = dict(_DEFAULT_TEMPLATES)

        # Load API keys
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        base_url = (
            os.environ.get("MINIMAX_ANTHROPIC_BASE_URL")
            or os.environ.get("ANTHROPIC_BASE_URL")
        )
        if not api_key:
            api_key = os.environ.get("MINIMAX_API_KEY")

        kwargs = {"api_key": api_key, "timeout": 120.0}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.AsyncAnthropic(**kwargs)

    def _report_routing_outcome(self, provider_id: str, result: "CcResult"):
        """Phase 4: Report execution outcome to RoutingFabric (fail-open)."""
        if not self._routing_fabric:
            return
        try:
            from chatgptrest.kernel.routing.types import ExecutionOutcome
            outcome = ExecutionOutcome(
                provider_id=provider_id,
                task_type=result.task_type,
                success=result.ok,
                latency_ms=int(result.elapsed_seconds * 1000),
                quality_score=result.quality_score if result.ok else 0.0,
                error_type=result.error[:100] if result.error else None,
            )
            self._routing_fabric.report_outcome(outcome)
        except Exception as e:
            logger.debug("CcNativeExecutor: routing outcome report failed: %s", e)

    # ── Template helpers ────────────────────────────────────────

    def _select_template(self, task_type: str) -> str:
        if task_type in self._templates:
            return list(self._templates[task_type].keys())[0]
        return "v1_structured"

    def _build_prompt(self, task: CcTask, template_name: str) -> str:
        try:
            tpl_str = (
                self._templates.get(task.task_type, {})
                .get(template_name, {})
                .get("template", "")
            )
            files_str = ", ".join(task.files) if task.files else "none"
            return tpl_str.format(
                files=files_str,
                description=task.description or "No description provided.",
            )
        except Exception:
            return f"Task: {task.description}\nFiles: {task.files}"

    # ── Signal emission (fail-open) ─────────────────────────────

    def _emit_event(self, event_type: str, trace_id: str, data: dict):
        """Emit a TraceEvent through EventBus. Fail-open."""
        if not self._event_bus:
            return
        try:
            from chatgptrest.kernel.event_bus import TraceEvent
            event = TraceEvent.create(
                source="cc_native",
                event_type=event_type,
                trace_id=trace_id,
                data=data,
            )
            self._event_bus.emit(event)
        except Exception as e:
            logger.debug("CcNativeExecutor: event emission failed: %s", e)

    def _record_signal(self, signal_type: str, trace_id: str, domain: str, data: dict):
        """Record a signal into EvoMap. Fail-open."""
        if not self._observer:
            return
        try:
            from chatgptrest.evomap.signals import Signal
            self._observer.record(Signal(
                trace_id=trace_id,
                signal_type=signal_type,
                source="cc_native",
                domain=domain,
                data=data,
            ))
        except Exception as e:
            logger.debug("CcNativeExecutor: signal record failed: %s", e)

    def _remember_episodic(self, task: CcTask, result: CcResult):
        """Store task summary into MemoryManager episodic layer. Fail-open."""
        if not self._memory:
            return
        try:
            from chatgptrest.kernel.memory_manager import MemoryRecord, MemoryTier
            self._memory.stage_and_promote(
                MemoryRecord(
                    key=f"cc_dispatch:{task.trace_id}",
                    category="cc_dispatch",
                    value={
                        "task_type": task.task_type,
                        "description": task.description[:200],
                        "ok": result.ok,
                        "quality_score": result.quality_score,
                        "model_used": result.model_used,
                        "elapsed_seconds": result.elapsed_seconds,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "num_turns": result.num_turns,
                        "tools_used": result.tools_used[:10] if result.tools_used else [],
                        "error": (result.error or "")[:200],
                        "output_preview": (result.output or "")[:300],
                    },
                    confidence=result.quality_score,
                    source={"type": "tool_result", "agent": "cc_native"},
                ),
                target=MemoryTier.EPISODIC,
                reason=f"cc_dispatch completed: {task.task_type}",
            )
        except Exception as e:
            logger.debug("CcNativeExecutor: memory store failed: %s", e)

    # ── Dispatch entry points ───────────────────────────────────

    async def dispatch_headless(
        self,
        task: CcTask,
        template: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> CcResult:
        started_at = time.time()

        if not task.trace_id:
            task.trace_id = f"native_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        if template is None:
            template = self._select_template(task.task_type)

        prompt = self._build_prompt(task, template)
        if task.system_prompt:
            prompt = task.system_prompt + "\n\n" + prompt

        # Signal: task started
        self._emit_event("dispatch.task_started", task.trace_id, {
            "task_type": task.task_type,
            "model": task.model or "sonnet",
            "files": task.files,
            "description": task.description[:200],
        })

        mcp_manager = McpManager()
        await mcp_manager.initialize(task.mcp_config)

        try:
            result = await self._run_react_loop(
                task=task,
                prompt=prompt,
                template=template,
                mcp_manager=mcp_manager,
                progress_callback=progress_callback,
            )

            completion_data = {
                "task_type": task.task_type,
                "ok": result.ok,
                "quality_score": result.quality_score,
                "elapsed_seconds": result.elapsed_seconds,
                "model_used": result.model_used,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "num_turns": result.num_turns,
                "tools_used": result.tools_used or [],
                "template": template,
            }

            # Signal: task completed
            self._emit_event("dispatch.task_completed", task.trace_id, completion_data)
            self._record_signal("dispatch.task_completed", task.trace_id, "dispatch", completion_data)

            # Memory: store episodic record
            self._remember_episodic(task, result)

            # Phase 4: Report to RoutingFabric
            self._report_routing_outcome(result.model_used or "unknown", result)

            return result
        except Exception as e:
            logger.exception("CcNativeExecutor failed")
            elapsed = time.time() - started_at
            error_result = CcResult(
                ok=False, agent="native", task_type=task.task_type,
                output="", elapsed_seconds=elapsed,
                template_used=template, error=str(e),
                trace_id=task.trace_id, dispatch_mode="native",
            )

            failure_data = {
                "task_type": task.task_type,
                "error": str(e)[:300],
                "elapsed_seconds": elapsed,
            }

            # Signal: task failed
            self._emit_event("dispatch.task_failed", task.trace_id, failure_data)
            self._record_signal("dispatch.task_failed", task.trace_id, "dispatch", failure_data)

            # Phase 4: Report failure to RoutingFabric
            self._report_routing_outcome(task.model or "unknown", error_result)

            return error_result
        finally:
            await mcp_manager.close()

    async def dispatch_conversation(
        self,
        tasks: list[CcTask],
        progress_callback: Callable[[dict], None] | None = None,
    ) -> list[CcResult]:
        results: list[CcResult] = []
        session_id = ""
        for i, task in enumerate(tasks):
            if i > 0 and session_id:
                task.stateless = False
                task.session_id = session_id
            result = await self.dispatch_headless(task, progress_callback=progress_callback)
            results.append(result)
            if result.session_id:
                session_id = result.session_id
            if not result.ok:
                logger.warning("CcNativeExecutor: conversation turn %d failed: %s", i + 1, result.error)
                break
        return results

    async def dispatch_parallel(
        self, tasks: list[CcTask], max_concurrent: int = 3,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> list[CcResult]:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _run_one(task: CcTask) -> CcResult:
            async with semaphore:
                return await self.dispatch_headless(task, progress_callback=progress_callback)

        return await asyncio.gather(*[_run_one(t) for t in tasks])

    async def dispatch_team(
        self, task: CcTask, team: "dict | TeamSpec | None" = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> CcResult:
        from chatgptrest.kernel.team_types import TeamSpec, TeamRunRecord
        team_spec = self._coerce_team_spec(task=task, team=team)
        if team_spec is None or not team_spec.roles:
            return await self.dispatch_headless(task, progress_callback=progress_callback)

        task.agents_json = team_spec.to_agents_json()
        repo = str(task.context.get("repo") or task.cwd or "")
        topology_id = str((team_spec.metadata or {}).get("topology_id", "") or "")

        run_record = TeamRunRecord(
            team_spec=team_spec,
            trace_id=task.trace_id,
            task_type=task.task_type,
            repo=repo,
        )

        if self._team_control_plane:
            try:
                self._team_control_plane.create_run(
                    team_run_id=run_record.team_run_id,
                    team_spec=team_spec,
                    topology_id=topology_id,
                    task=task,
                    repo=repo,
                )
            except Exception as e:
                logger.debug("CcNativeExecutor: team run create failed: %s", e)

        self._emit_event("team.run.created", task.trace_id, {
            "team_run_id": run_record.team_run_id,
            "team_id": team_spec.team_id,
            "roles": [r.name for r in team_spec.roles],
            "task_type": task.task_type,
            "topology_id": topology_id,
        })

        role_results = await self._run_team_roles(
            task=task,
            team_spec=team_spec,
            team_run_id=run_record.team_run_id,
            progress_callback=progress_callback,
        )
        final_result = self._combine_team_results(
            task=task,
            team_spec=team_spec,
            role_results=role_results,
        )

        run_record.completed_at = time.time()
        run_record.result_ok = final_result.ok
        run_record.elapsed_seconds = final_result.elapsed_seconds
        run_record.quality_score = final_result.quality_score
        run_record.total_input_tokens = final_result.input_tokens
        run_record.total_output_tokens = final_result.output_tokens
        run_record.cost_usd = final_result.cost_usd
        run_record.role_outcomes = {
            name: {
                "ok": result.ok,
                "quality_score": result.quality_score,
                "elapsed_seconds": result.elapsed_seconds,
                "error": result.error,
            }
            for name, result in role_results.items()
        }

        checkpoints: list[dict[str, Any]] = []
        if self._team_control_plane:
            try:
                created = self._team_control_plane.finalize_run(
                    team_run_id=run_record.team_run_id,
                    team_spec=team_spec,
                    final_result=final_result,
                    role_outcomes=run_record.role_outcomes,
                )
                checkpoints = [dict(cp.__dict__) for cp in created]
                snapshot = self._team_control_plane.get_run(run_record.team_run_id) or {}
                final_result.team_digest = str(snapshot.get("digest", "") or "")
            except Exception as e:
                logger.debug("CcNativeExecutor: team run finalize failed: %s", e)
        final_result.team_run_id = run_record.team_run_id
        final_result.role_results = run_record.role_outcomes
        final_result.team_checkpoints = checkpoints

        self._record_signal(
            "team.run.completed" if final_result.ok else "team.run.failed",
            task.trace_id, "team", {
                "team_run_id": run_record.team_run_id,
                "team_id": team_spec.team_id,
                "task_type": task.task_type,
                "ok": final_result.ok,
                "quality_score": final_result.quality_score,
                "elapsed_seconds": final_result.elapsed_seconds,
                "checkpoint_count": len(checkpoints),
            },
        )
        self._emit_event(
            "team.output.rejected" if checkpoints else "team.output.accepted",
            task.trace_id,
            {
                "team_run_id": run_record.team_run_id,
                "team_id": team_spec.team_id,
                "checkpoint_count": len(checkpoints),
                "digest": final_result.team_digest,
            },
        )

        if self._scorecard_store:
            try:
                self._scorecard_store.record_outcome(run_record)
            except Exception as e:
                logger.debug("CcNativeExecutor: scorecard update failed: %s", e)

        return final_result

    def _coerce_team_spec(
        self,
        *,
        task: CcTask,
        team: "dict | TeamSpec | None",
    ) -> "TeamSpec | None":
        from chatgptrest.kernel.team_types import TeamSpec

        if isinstance(team, TeamSpec):
            return team
        if isinstance(team, dict) and team:
            return TeamSpec.from_dict(team)
        if task.agents_json:
            return TeamSpec.from_dict(task.agents_json)
        return None

    def _build_role_system_prompt(
        self,
        *,
        task: CcTask,
        role: Any,
        role_outputs: dict[str, CcResult] | None = None,
    ) -> str:
        prompt_parts = [
            f"You are role `{role.name}` in a coordinated team.",
            str(role.description or "").strip(),
            str(role.prompt or "").strip(),
        ]
        if task.system_prompt:
            prompt_parts.append(str(task.system_prompt))
        if role_outputs:
            prompt_parts.append("Upstream team outputs:")
            for role_name, result in role_outputs.items():
                prompt_parts.append(
                    f"[{role_name}] ok={result.ok} quality={result.quality_score:.2f}\n{_text_preview(result.output, 1000)}"
                )
        prompt_parts.append(
            "Return concrete output for your role. If there are unresolved conflicts or approval blockers, say so explicitly."
        )
        return "\n\n".join(p for p in prompt_parts if p)

    def _clone_task_for_role(
        self,
        *,
        task: CcTask,
        role: Any,
        role_outputs: dict[str, CcResult] | None = None,
    ) -> CcTask:
        return CcTask(
            task_type=task.task_type,
            description=task.description,
            files=list(task.files),
            context=dict(task.context),
            timeout=task.timeout,
            trace_id=f"{task.trace_id}:{role.name}",
            parent_task_id=task.parent_task_id,
            model=role.model or task.model,
            fallback_model=task.fallback_model,
            max_turns=task.max_turns,
            max_budget_usd=task.max_budget_usd,
            mcp_config=task.mcp_config,
            agents_json=None,
            json_schema=task.json_schema,
            system_prompt=self._build_role_system_prompt(task=task, role=role, role_outputs=role_outputs),
            cwd=task.cwd,
            permission_mode=task.permission_mode,
            stateless=True,
            session_id="",
            effort=task.effort,
            allowed_tools=list(role.tools) if getattr(role, "tools", None) else task.allowed_tools,
            add_dirs=list(task.add_dirs),
        )

    async def _run_single_role(
        self,
        *,
        task: CcTask,
        role: Any,
        team_run_id: str,
        role_outputs: dict[str, CcResult] | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> CcResult:
        role_task = self._clone_task_for_role(task=task, role=role, role_outputs=role_outputs)
        if self._team_control_plane:
            try:
                self._team_control_plane.mark_role_started(team_run_id, role.name, task_trace_id=role_task.trace_id)
            except Exception as e:
                logger.debug("CcNativeExecutor: role start tracking failed: %s", e)
        self._emit_event("team.role.started", task.trace_id, {
            "team_run_id": team_run_id,
            "role": role.name,
            "trace_id": role_task.trace_id,
        })
        if progress_callback:
            progress_callback({"type": "text", "content": f"\n\n[team role start] {role.name}\n"})
        result = await self.dispatch_headless(role_task, progress_callback=progress_callback)
        if self._team_control_plane:
            try:
                self._team_control_plane.mark_role_completed(team_run_id, role.name, result)
            except Exception as e:
                logger.debug("CcNativeExecutor: role completion tracking failed: %s", e)
        self._emit_event("team.role.completed" if result.ok else "team.role.failed", task.trace_id, {
            "team_run_id": team_run_id,
            "role": role.name,
            "ok": result.ok,
            "quality_score": result.quality_score,
            "elapsed_seconds": result.elapsed_seconds,
            "error": (result.error or "")[:200],
        })
        return result

    async def _run_team_roles(
        self,
        *,
        task: CcTask,
        team_spec: "TeamSpec",
        team_run_id: str,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict[str, CcResult]:
        execution_mode = str((team_spec.metadata or {}).get("execution_mode", "parallel") or "parallel")
        synthesis_role_name = str((team_spec.metadata or {}).get("synthesis_role", "") or "")
        synthesis_role = next((role for role in team_spec.roles if role.name == synthesis_role_name), None)
        fanout_roles = [role for role in team_spec.roles if role.name != synthesis_role_name]
        results: dict[str, CcResult] = {}

        if execution_mode == "sequential":
            for role in fanout_roles:
                results[role.name] = await self._run_single_role(
                    task=task,
                    role=role,
                    team_run_id=team_run_id,
                    role_outputs=dict(results),
                    progress_callback=progress_callback,
                )
        else:
            max_concurrent = int((team_spec.metadata or {}).get("max_concurrent", len(fanout_roles) or 1) or 1)
            max_concurrent = max(1, min(max_concurrent, len(fanout_roles) or 1))
            semaphore = asyncio.Semaphore(max_concurrent)

            async def _run_parallel_role(role: Any) -> CcResult:
                async with semaphore:
                    return await self._run_single_role(
                        task=task,
                        role=role,
                        team_run_id=team_run_id,
                        progress_callback=progress_callback,
                    )

            ordered_results = await asyncio.gather(*[
                _run_parallel_role(role)
                for role in fanout_roles
            ])
            for role, result in zip(fanout_roles, ordered_results):
                results[role.name] = result

        if synthesis_role is not None:
            results[synthesis_role.name] = await self._run_single_role(
                task=task,
                role=synthesis_role,
                team_run_id=team_run_id,
                role_outputs=dict(results),
                progress_callback=progress_callback,
            )

        return results

    def _combine_team_results(
        self,
        *,
        task: CcTask,
        team_spec: "TeamSpec",
        role_results: dict[str, CcResult],
    ) -> CcResult:
        synthesis_role_name = str((team_spec.metadata or {}).get("synthesis_role", "") or "")
        final = role_results.get(synthesis_role_name) if synthesis_role_name else None
        if final is None:
            successful = [result for result in role_results.values() if result.ok]
            final = max(successful, key=lambda item: item.quality_score, default=None)
            if final is None:
                final = max(role_results.values(), key=lambda item: item.elapsed_seconds)
        combined_output = "\n\n".join(
            f"[{role_name}]\n{result.output or result.error}"
            for role_name, result in role_results.items()
            if (result.output or result.error)
        )
        total_elapsed = sum(result.elapsed_seconds for result in role_results.values())
        total_input_tokens = sum(result.input_tokens for result in role_results.values())
        total_output_tokens = sum(result.output_tokens for result in role_results.values())
        total_cost = sum(result.cost_usd for result in role_results.values())
        avg_quality = sum(result.quality_score for result in role_results.values()) / max(len(role_results), 1)
        ok = final.ok and all(result.ok for result in role_results.values() if result is not final)
        output = final.output or combined_output
        if final.output and combined_output and final.output != combined_output:
            output = final.output + "\n\n--- Team role outputs ---\n" + combined_output
        return CcResult(
            ok=ok,
            agent="native-team",
            task_type=task.task_type,
            output=output,
            elapsed_seconds=total_elapsed,
            findings_count=final.findings_count,
            files_modified=final.files_modified,
            template_used=final.template_used,
            quality_score=max(final.quality_score, avg_quality),
            error=final.error,
            trace_id=task.trace_id,
            session_id=final.session_id,
            model_used=final.model_used,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost_usd=total_cost,
            num_turns=sum(result.num_turns for result in role_results.values()),
            structured_output=final.structured_output,
            files_read=sorted({path for result in role_results.values() for path in result.files_read}),
            tools_used=sorted({tool for result in role_results.values() for tool in result.tools_used}),
            dispatch_mode="native-team",
        )

    # ── Core ReAct Loop ─────────────────────────────────────────

    async def _run_react_loop(
        self,
        task: CcTask,
        prompt: str,
        template: str,
        mcp_manager: McpManager,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> CcResult:
        started_at = time.time()
        messages = [{"role": "user", "content": prompt}]
        tools = mcp_manager.available_tools

        if task.allowed_tools:
            tools = [t for t in tools if t["name"] in task.allowed_tools]

        model = task.model or "claude-3-5-sonnet-20241022"
        if model == "sonnet":
            model = "MiniMax-M2.5"

        turns = 0
        total_input_tokens = 0
        total_output_tokens = 0
        files_read = []
        tools_used = []
        final_output = ""

        while turns < task.max_turns:
            turns += 1

            if progress_callback:
                progress_callback({"type": "text", "content": f"\n\n--- Turn {turns} ---\n"})

            llm_start = time.time()
            response = await self.client.messages.create(
                model=model,
                max_tokens=4096,
                messages=messages,
                tools=tools if tools else anthropic.NOT_GIVEN,
            )
            llm_elapsed = time.time() - llm_start

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            # Signal: LLM call completed
            self._emit_event("llm.call_completed", task.trace_id, {
                "model": model,
                "turn": turns,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "latency_seconds": round(llm_elapsed, 2),
            })

            assistant_content = []
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    if progress_callback:
                        progress_callback({"type": "text", "content": block.text})
                    assistant_content.append(block.text)
                elif block.type == "tool_use":
                    tool_calls.append(block)
                    tools_used.append(block.name)
                    if progress_callback:
                        progress_callback({
                            "type": "text",
                            "content": f"\n[Tool Use: {block.name}({json.dumps(block.input)})]\n",
                        })

            messages.append({"role": "assistant", "content": response.content})

            if not tool_calls:
                final_output = "\n".join(assistant_content)
                break

            # Execute tools
            tool_results = []
            for tool_use in tool_calls:
                tool_start = time.time()
                try:
                    res_str = await mcp_manager.call_tool(tool_use.name, tool_use.input)
                    tool_ok = True
                except Exception as e:
                    res_str = f"Error: {e}"
                    tool_ok = False
                tool_elapsed = time.time() - tool_start

                # Signal: tool call completed
                self._emit_event(
                    "tool.call_completed" if tool_ok else "tool.call_failed",
                    task.trace_id,
                    {
                        "tool_name": tool_use.name,
                        "turn": turns,
                        "ok": tool_ok,
                        "latency_seconds": round(tool_elapsed, 2),
                        "output_chars": len(res_str),
                    },
                )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": res_str,
                })

                if progress_callback:
                    out_trunc = res_str[:500] + ("..." if len(res_str) > 500 else "")
                    progress_callback({"type": "text", "content": f"\n[Tool Result]: {out_trunc}\n"})

            messages.append({"role": "user", "content": tool_results})

        elapsed = time.time() - started_at
        return CcResult(
            ok=True,
            agent="native",
            task_type=task.task_type,
            output=final_output,
            elapsed_seconds=elapsed,
            findings_count=0,
            files_modified=0,
            template_used=template,
            quality_score=1.0,
            error="",
            trace_id=task.trace_id,
            session_id="",
            model_used=model,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost_usd=0.0,
            num_turns=turns,
            tools_used=tools_used,
            files_read=files_read,
            dispatch_mode="native",
        )
