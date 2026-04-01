"""Agent Teams Dispatch — ProjectCard → Context Package → hcom dispatch.

Uses Effects Outbox for idempotent dispatch:
  - Same trace_id won't dispatch twice
  - Failed dispatches can be retried

Context Package:
  - ProjectCard (from funnel_graph)
  - reasoning_summary (from advisor route_rationale)
  - kb_refs (from evidence_pack)
  - constraints (from funnel understand stage)
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ContextPackage:
    """Context package assembled for Agent Teams dispatch."""
    trace_id: str = ""
    project_card: dict[str, Any] = field(default_factory=dict)
    reasoning_summary: str = ""
    kb_refs: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    priority: str = "P2"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "project_card": self.project_card,
            "reasoning_summary": self.reasoning_summary,
            "kb_refs": self.kb_refs,
            "constraints": self.constraints,
            "priority": self.priority,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class AgentDispatcher:
    """Dispatches Context Packages to Agent Teams via hcom.

    Usage::

        dispatcher = AgentDispatcher(
            outbox=effects_outbox,
            llm_fn=llm_connector,  # for code generation
        )
        dispatcher.dispatch(funnel_result)
    """

    def __init__(
        self,
        *,
        outbox: Any = None,
        hcom_fn: Callable[[ContextPackage], dict] | None = None,
        llm_fn: Callable[[str, str], str] | None = None,
    ) -> None:
        self._outbox = outbox
        self._llm_fn = llm_fn
        self._hcom_fn = hcom_fn or self._execute_project

    def build_context_package(
        self,
        funnel_result: dict[str, Any],
        *,
        trace_id: str = "",
        advisor_rationale: str = "",
    ) -> ContextPackage:
        """Build a ContextPackage from funnel graph output."""
        return ContextPackage(
            trace_id=trace_id or str(uuid.uuid4()),
            project_card=funnel_result.get("project_card", {}),
            reasoning_summary=advisor_rationale or funnel_result.get("recommended_option", ""),
            kb_refs=funnel_result.get("evidence_refs", []),
            constraints=funnel_result.get("constraints", []),
        )

    def dispatch(
        self,
        ctx: ContextPackage,
        *,
        target_agent: str = "main",
        skip_skill_check: bool = False,
    ) -> dict[str, Any]:
        """Dispatch a context package to Agent Teams.

        Performs a skill pre-flight check before dispatch.
        Uses Effects Outbox for idempotency if available.
        """
        selected_skills: list[str] = []
        selected_bundles: list[str] = []
        task_type = "general"
        # --- Skill pre-flight check ---
        if not skip_skill_check:
            from chatgptrest.advisor.skill_registry import check_skill_readiness
            from chatgptrest.kernel.market_gate import (
                emit_skill_execution_signals,
                emit_skill_resolution_signals,
                find_market_candidates_for_unmet,
                get_capability_gap_recorder,
            )
            from chatgptrest.kernel.skill_manager import get_canonical_registry

            skill_result = check_skill_readiness(
                agent_id=target_agent,
                project_card=ctx.project_card,
            )
            task_type = skill_result.task_type
            if not skill_result.passed:
                emit_skill_resolution_signals(
                    trace_id=ctx.trace_id,
                    source="advisor.dispatch",
                    agent_id=target_agent,
                    task_type=skill_result.task_type,
                    platform=skill_result.platform,
                    recommended_skills=skill_result.recommended_skills,
                    recommended_bundles=skill_result.recommended_bundles,
                    unmet_capabilities=skill_result.unmet_capabilities,
                )
                gaps = get_capability_gap_recorder().promote_unmet(
                    trace_id=ctx.trace_id,
                    agent_id=target_agent,
                    task_type=skill_result.task_type,
                    platform=skill_result.platform,
                    unmet_capabilities=skill_result.unmet_capabilities,
                    suggested_agent=skill_result.suggested_agent or "",
                    context={
                        "project_title": str(ctx.project_card.get("title") or ""),
                        "recommended_bundles": list(skill_result.recommended_bundles),
                        "recommended_skills": list(skill_result.recommended_skills),
                    },
                )
                market_candidates = find_market_candidates_for_unmet(skill_result.unmet_capabilities)
                fallback_plan = list(skill_result.fallback_plan)
                if market_candidates:
                    fallback_plan.append(
                        {
                            "action": "review_market_candidates",
                            "reason": "internal_catalog_miss",
                            "candidate_ids": [item["candidate_id"] for item in market_candidates],
                        }
                    )
                logger.warning(
                    "Skill check failed for agent '%s': %s",
                    target_agent,
                    skill_result.message,
                )
                return {
                    "status": "skill_gap",
                    "trace_id": ctx.trace_id,
                    "skill_check": skill_result.to_dict(),
                    "message": skill_result.message,
                    "recommended_skills": list(skill_result.recommended_skills),
                    "recommended_bundles": list(skill_result.recommended_bundles),
                    "unmet_capabilities": list(skill_result.unmet_capabilities),
                    "fallback_plan": fallback_plan,
                    "market_candidates": market_candidates,
                    "capability_gap_ids": [gap.gap_id for gap in gaps],
                }
            registry = get_canonical_registry()
            agent_profile = registry.get_agent_profile(target_agent)
            if agent_profile is not None:
                selected_bundles = list(agent_profile.default_bundles)
                selected_skills = registry.available_skill_ids_for_bundles(
                    agent_profile.default_bundles,
                    platform=skill_result.platform,
                )
            emit_skill_resolution_signals(
                trace_id=ctx.trace_id,
                source="advisor.dispatch",
                agent_id=target_agent,
                task_type=skill_result.task_type,
                platform=skill_result.platform,
                selected_skills=selected_skills,
                selected_bundles=selected_bundles,
            )
            logger.info(
                "Skill check passed for agent '%s' (task_type=%s)",
                target_agent,
                skill_result.task_type,
            )
        effect_key = f"dispatch:{ctx.trace_id}"
        effect_id: str | None = None  # S0-1.1: must init before conditional assignment

        # Check outbox for idempotency
        if self._outbox:
            if self._outbox.is_done("agent_dispatch", effect_key):
                logger.info("Dispatch already done for trace %s", ctx.trace_id)
                return {"status": "already_dispatched", "trace_id": ctx.trace_id}

            # Enqueue the effect
            effect_id = self._outbox.enqueue(
                trace_id=ctx.trace_id,
                effect_type="agent_dispatch",
                effect_key=effect_key,
                payload=ctx.to_dict(),
            )
            if effect_id is None:
                return {"status": "duplicate", "trace_id": ctx.trace_id}

        # Execute dispatch
        try:
            result = self._hcom_fn(ctx)
            if not skip_skill_check:
                from chatgptrest.kernel.market_gate import emit_skill_execution_signals

                emit_skill_execution_signals(
                    trace_id=ctx.trace_id,
                    source="advisor.dispatch",
                    agent_id=target_agent,
                    task_type=task_type,
                    platform="openclaw",
                    selected_skills=selected_skills,
                    selected_bundles=selected_bundles,
                    success=True,
                    extra={"stage": "dispatch"},
                )

            # Mark outbox as done after successful execution (P0 fix)
            if self._outbox and effect_id:
                try:
                    self._outbox.mark_done(effect_id)
                except Exception as oe:
                    logger.warning("Failed to mark outbox done: %s", oe)

            return {
                "status": "dispatched",
                "trace_id": ctx.trace_id,
                "result": result,
            }
        except Exception as e:
            logger.error("Dispatch failed for trace %s: %s", ctx.trace_id, e)
            if not skip_skill_check:
                from chatgptrest.kernel.market_gate import emit_skill_execution_signals

                emit_skill_execution_signals(
                    trace_id=ctx.trace_id,
                    source="advisor.dispatch",
                    agent_id=target_agent,
                    task_type=task_type,
                    platform="openclaw",
                    selected_skills=selected_skills,
                    selected_bundles=selected_bundles,
                    success=False,
                    extra={"stage": "dispatch", "error": str(e)},
                )

            # Mark outbox as failed (P0 fix)
            if self._outbox and effect_id:
                try:
                    self._outbox.mark_failed(effect_id, str(e))
                except Exception as oe:
                    logger.warning("Failed to mark outbox failed: %s", oe)

            return {
                "status": "failed",
                "trace_id": ctx.trace_id,
                "error": str(e),
            }

    def _execute_project(self, ctx: ContextPackage) -> dict:
        """Real project executor: generates project scaffold via LLM.

        Creates:
          1. README.md — project overview, architecture, module list
          2. project_card.json — structured project card
          3. scaffold code — main application file(s)

        Output directory: ~/.openmind/projects/{trace_id}/
        """
        import pathlib, os

        proj_dir = pathlib.Path(os.environ.get(
            "OPENMIND_PROJECTS_PATH", os.path.expanduser("~/.openmind/projects"),
        )) / ctx.trace_id[:12]
        proj_dir.mkdir(parents=True, exist_ok=True)

        card = ctx.project_card
        title = card.get("title", "Untitled")
        plan = card.get("execution_plan", "")
        tasks = card.get("tasks", ctx.project_card.get("tasks", []))

        # 1. Write structured project_card.json
        card_path = proj_dir / "project_card.json"
        card_path.write_text(
            json.dumps({
                "title": title,
                "trace_id": ctx.trace_id,
                "tasks": tasks,
                "constraints": ctx.constraints,
                "priority": ctx.priority,
                "reasoning": ctx.reasoning_summary[:500],
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("ProjectCard written: %s", card_path)

        deliverables = [str(card_path)]
        code_files: list[str] = []

        # 2. Generate README.md via LLM
        if self._llm_fn:
            try:
                readme_prompt = (
                    f"请为以下项目生成一份 README.md:\n\n"
                    f"项目标题: {title}\n"
                    f"执行计划:\n{plan[:800]}\n\n"
                    "README 结构:\n"
                    "# 项目标题\n"
                    "## 项目概述\n"
                    "## 技术架构\n"
                    "## 功能模块\n"
                    "## 安装与运行\n"
                    "## API 文档\n\n"
                    "请用 Markdown 格式直接输出。"
                )
                readme = self._llm_fn(readme_prompt, "你是一个技术文档撰写专家。直接输出 README.md 内容。")
                readme_path = proj_dir / "README.md"
                readme_path.write_text(readme, encoding="utf-8")
                deliverables.append(str(readme_path))
                logger.info("README.md written: %s (%d chars)", readme_path, len(readme))
            except Exception as e:
                logger.warning("README generation failed: %s", e)

            # 3. Generate main application scaffold via LLM
            try:
                code_prompt = (
                    f"请为以下项目生成主应用代码框架:\n\n"
                    f"项目: {title}\n"
                    f"计划:\n{plan[:600]}\n\n"
                    "要求:\n"
                    "- Python FastAPI 后端\n"
                    "- 包含主要数据模型 (Pydantic)\n"
                    "- 包含核心 API 路由\n"
                    "- 包含基本 CRUD 操作\n"
                    "- 可直接运行\n\n"
                    "直接输出完整的 Python 代码 (app.py)。不要解释。"
                )
                code = self._llm_fn(code_prompt, "你是一个 Python 高级开发工程师。直接输出可运行代码。")

                # Extract code from markdown code block if present
                if "```python" in code:
                    code = code.split("```python", 1)[1].split("```", 1)[0]
                elif "```" in code:
                    code = code.split("```", 1)[1].split("```", 1)[0]

                code_path = proj_dir / "app.py"
                code_path.write_text(code.strip(), encoding="utf-8")
                code_files.append(str(code_path))
                deliverables.append(str(code_path))
                logger.info("app.py written: %s (%d chars)", code_path, len(code))
            except Exception as e:
                logger.warning("Code generation failed: %s", e)

        return {
            "session_id": ctx.trace_id[:12],
            "task_count": len(tasks) if isinstance(tasks, list) else 1,
            "project_dir": str(proj_dir),
            "deliverables": deliverables,
            "code_files": code_files,
        }
