from __future__ import annotations

import asyncio
import threading
import time
import uuid
from typing import Any

from chatgptrest.core.advisor_runs import (
    append_event,
    create_run,
    get_run as get_advisor_run,
    new_run_id,
    update_run,
    upsert_step,
    write_run_json,
)
from chatgptrest.core import artifacts
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect
from chatgptrest.core.idempotency import IdempotencyCollision
from chatgptrest.core import job_store
from chatgptrest.core.prompt_policy import PromptPolicyViolation

from .contracts import ControllerArtifact, ControllerCheckpoint, EffectIntent, StepResult
from . import store


_RUN_STEP_INPUT = "input"
_RUN_STEP_PLAN = "plan"
_RUN_STEP_EXECUTE = "execute"
_RUN_STEP_DELIVER = "deliver"
_RUN_STEP_TEAM = "team_execute"
_RUN_STEP_EFFECT = "effect_intent"


class ControllerEngine:
    """Persist a durable controller view on top of the existing advisor runtime."""

    def __init__(self, runtime_state: dict[str, Any]):
        self._state = runtime_state or {}
        self._cfg = load_config()

    def advise(
        self,
        *,
        message: str,
        trace_id: str,
        request_metadata: dict[str, Any],
        degradation: list[dict[str, Any]],
        role_id: str,
        session_id: str,
        account_id: str,
        thread_id: str,
        agent_id: str,
        user_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        request_id = trace_id or f"advise:{new_run_id()}"
        run_id = self._ensure_run(
            request_id=request_id,
            trace_id=trace_id,
            execution_mode="sync",
            question=message,
            normalized_question=message,
            request_obj={
                "message": message,
                "context": dict(context or {}),
                "request_metadata": dict(request_metadata or {}),
                "degradation": list(degradation or []),
            },
            session_id=session_id,
            account_id=account_id,
            thread_id=thread_id,
            agent_id=agent_id,
            role_id=role_id,
            user_id=user_id,
            intent_hint="",
        )
        self._mark_input_ready(run_id=run_id, question=message, execution_mode="sync")
        api = self._state["api"]
        advise_kwargs: dict[str, Any] = {
            "session_id": session_id,
            "account_id": account_id,
            "thread_id": thread_id,
            "agent_id": agent_id,
            "context": dict(context or {}),
            "role_id": role_id,
            "user_id": user_id,
        }
        task_intake = context.get("task_intake")
        if isinstance(task_intake, dict):
            advise_kwargs["task_intake"] = dict(task_intake)
        scenario_pack = context.get("scenario_pack")
        if isinstance(scenario_pack, dict):
            advise_kwargs["scenario_pack"] = dict(scenario_pack)
            pack_intent = str(scenario_pack.get("intent_top") or "").strip()
            if pack_intent:
                advise_kwargs["intent_top"] = pack_intent
        if trace_id:
            advise_kwargs["trace_id"] = trace_id
        result = api.advise(message, **advise_kwargs)
        selected_route = str(result.get("selected_route") or "")
        plan = {
            "route": selected_route,
            "route_rationale": str(result.get("route_rationale") or ""),
            "intent_top": str(result.get("intent_top") or ""),
            "kb_has_answer": bool(result.get("kb_has_answer", False)),
            "kb_answerability": float(result.get("kb_answerability", 0.0) or 0.0),
            "kb_hit_count": len(list(result.get("kb_top_chunks") or [])),
        }
        delivery = self._build_sync_delivery(result)
        next_action = self._build_sync_next_action(result)
        with connect(self._cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            store.upsert_run(
                conn,
                run_id=run_id,
                trace_id=str(result.get("trace_id") or trace_id or ""),
                request_id=request_id,
                execution_mode="sync",
                controller_status="DELIVERED",
                route=selected_route,
                provider="advisor_graph",
                preset="sync",
                session_id=session_id,
                account_id=account_id,
                thread_id=thread_id,
                agent_id=agent_id,
                role_id=role_id,
                user_id=user_id,
                question=message,
                normalized_question=str(result.get("route_result", {}).get("refined_question") or message),
                request_obj={
                    "message": message,
                    "context": dict(context or {}),
                    "request_metadata": dict(request_metadata or {}),
                    "degradation": list(degradation or []),
                },
                plan_obj=plan,
                delivery_obj=delivery,
                next_action_obj=next_action,
            )
            update_run(
                conn,
                run_id=run_id,
                status="COMPLETED",
                route=selected_route,
                normalized_question=str(result.get("route_result", {}).get("refined_question") or message),
                degraded=False,
            )
            upsert_step(
                conn,
                run_id=run_id,
                step_id=_RUN_STEP_PLAN,
                step_type="planning",
                status="SUCCEEDED",
                input_obj={"message": message},
                output_obj=plan,
            )
            upsert_step(
                conn,
                run_id=run_id,
                step_id=_RUN_STEP_EXECUTE,
                step_type="execution",
                status="SUCCEEDED",
                input_obj={"message": message},
                output_obj={"selected_route": selected_route, "trace_id": str(result.get("trace_id") or trace_id or "")},
            )
            upsert_step(
                conn,
                run_id=run_id,
                step_id=_RUN_STEP_DELIVER,
                step_type="delivery",
                status="SUCCEEDED",
                input_obj={"trace_id": str(result.get("trace_id") or trace_id or "")},
                output_obj=delivery,
            )
            store.upsert_work_item(
                conn,
                run_id=run_id,
                work_id=_RUN_STEP_PLAN,
                title="Understand request and decide route",
                kind="planning",
                status="COMPLETED",
                owner="controller",
                lane="advisor_graph",
                input_obj={"message": message},
                output_obj=plan,
            )
            store.upsert_work_item(
                conn,
                run_id=run_id,
                work_id=_RUN_STEP_EXECUTE,
                title="Execute the selected route",
                kind="execution",
                status="COMPLETED",
                owner="controller",
                lane=selected_route or "advisor_graph",
                input_obj={"message": message},
                output_obj={"route_result": dict(result.get("route_result") or {})},
            )
            store.upsert_work_item(
                conn,
                run_id=run_id,
                work_id=_RUN_STEP_DELIVER,
                title="Produce decision-ready delivery",
                kind="delivery",
                status="COMPLETED",
                owner="controller",
                lane="delivery",
                depends_on=[_RUN_STEP_PLAN, _RUN_STEP_EXECUTE],
                input_obj={"trace_id": str(result.get("trace_id") or trace_id or "")},
                output_obj=delivery,
            )
            for chunk in list(result.get("kb_top_chunks") or [])[:5]:
                artifact_id = str(chunk.get("artifact_id") or "").strip()
                if not artifact_id:
                    continue
                store.upsert_artifact(
                    conn,
                    run_id=run_id,
                    artifact_id=f"kb:{artifact_id}",
                    work_id=_RUN_STEP_DELIVER,
                    kind="kb_ref",
                    title=str(chunk.get("title") or artifact_id),
                    metadata_obj=dict(chunk),
                )
            conversation_url = str(result.get("conversation_url") or "").strip()
            if conversation_url:
                store.upsert_artifact(
                    conn,
                    run_id=run_id,
                    artifact_id="conversation_url",
                    work_id=_RUN_STEP_DELIVER,
                    kind="conversation_url",
                    title="Conversation URL",
                    uri=conversation_url,
                    metadata_obj={"trace_id": str(result.get("trace_id") or trace_id or "")},
                )
            append_event(
                conn,
                run_id=run_id,
                type="controller.delivery.ready",
                payload={
                    "trace_id": str(result.get("trace_id") or trace_id or ""),
                    "route": selected_route,
                    "answer_present": bool(delivery.get("answer")),
                },
            )
            self._write_controller_snapshot(conn, run_id=run_id)
            conn.commit()

        response = dict(result)
        response["run_id"] = run_id
        response["controller_status"] = "DELIVERED"
        response["delivery"] = delivery
        response["next_action"] = next_action
        response["work_items"] = self.get_run_snapshot(run_id=run_id)["work_items"]
        response["checkpoints"] = self.get_run_snapshot(run_id=run_id)["checkpoints"]
        response["artifacts"] = self.get_run_snapshot(run_id=run_id)["artifacts"]
        return response

    def ask(
        self,
        *,
        question: str,
        trace_id: str,
        intent_hint: str,
        role_id: str,
        session_id: str,
        account_id: str,
        thread_id: str,
        agent_id: str,
        user_id: str,
        stable_context: dict[str, Any],
        idempotency_key: str,
        request_fingerprint: str,
        timeout_seconds: int,
        max_retries: int,
        quality_threshold: int,
        request_metadata: dict[str, Any],
        degradation: list[dict[str, Any]],
        route_mapping: dict[str, dict[str, str]],
        kb_direct_completion_allowed: Any,
        kb_direct_synthesis_enabled: Any,
        sanitize_context_hash: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        route_plan = self._plan_async_route(
            question=question,
            trace_id=trace_id,
            intent_hint=intent_hint,
            session_id=session_id,
            account_id=account_id,
            thread_id=thread_id,
            agent_id=agent_id,
            role_id=role_id,
            stable_context=stable_context,
        )
        route = str(route_plan["route"])
        objective_plan = self._build_objective_plan(
            question=question,
            route_plan=route_plan,
            intent_hint=intent_hint,
            stable_context=stable_context,
        )
        route_plan_record = dict(objective_plan)
        run_id = self._ensure_run(
            request_id=idempotency_key,
            trace_id=trace_id,
            execution_mode="async",
            question=question,
            normalized_question=str(route_plan.get("normalized_question") or question),
            request_obj={
                "question": question,
                "context": dict(stable_context or {}),
                "request_metadata": dict(request_metadata or {}),
                "degradation": list(degradation or []),
                "request_fingerprint": request_fingerprint[:32],
            },
            session_id=session_id,
            account_id=account_id,
            thread_id=thread_id,
            agent_id=agent_id,
            role_id=role_id,
            user_id=user_id,
            intent_hint=intent_hint,
        )
        with connect(self._cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            store.upsert_run(
                conn,
                run_id=run_id,
                trace_id=trace_id,
                request_id=idempotency_key,
                execution_mode="async",
                controller_status="PLANNED",
                objective_text=str(objective_plan["objective_text"]),
                objective_kind=str(objective_plan["objective_kind"]),
                success_criteria=list(objective_plan["success_criteria"]),
                constraints=list(objective_plan["constraints"]),
                delivery_target=dict(objective_plan["delivery_target"]),
                current_work_id=_RUN_STEP_PLAN,
                plan_version=int(objective_plan["plan_version"]),
                route=route,
                question=question,
                normalized_question=str(route_plan.get("normalized_question") or question),
                session_id=session_id,
                account_id=account_id,
                thread_id=thread_id,
                agent_id=agent_id,
                role_id=role_id,
                user_id=user_id,
                intent_hint=intent_hint,
                request_obj={
                    "question": question,
                    "context": dict(stable_context or {}),
                    "request_metadata": dict(request_metadata or {}),
                    "degradation": list(degradation or []),
                    "request_fingerprint": request_fingerprint[:32],
                },
                plan_obj=route_plan_record,
            )
            update_run(
                conn,
                run_id=run_id,
                status="PLAN_COMPILED",
                route=route,
                normalized_question=str(route_plan.get("normalized_question") or question),
                degraded=False,
            )
            upsert_step(
                conn,
                run_id=run_id,
                step_id=_RUN_STEP_PLAN,
                step_type="planning",
                status="SUCCEEDED",
                input_obj={"question": question},
                output_obj=route_plan_record,
            )
            store.upsert_work_item(
                conn,
                run_id=run_id,
                work_id=_RUN_STEP_PLAN,
                title="Understand request and decide route",
                kind="planning",
                status="COMPLETED",
                owner="controller",
                lane="routing",
                input_obj={"question": question},
                output_obj=route_plan_record,
            )
            self._write_controller_snapshot(conn, run_id=run_id)
            conn.commit()

        if kb_direct_completion_allowed(route_plan["graph_state"]) and route_plan["kb_chunks"]:
            kb_answer, evidence_refs = self._build_kb_direct_answer(
                question=question,
                kb_chunks=route_plan["kb_chunks"],
                synthesis_enabled=bool(kb_direct_synthesis_enabled()),
            )
            with connect(self._cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                self._persist_step_result(
                    conn,
                    run_id=run_id,
                    work_id=_RUN_STEP_DELIVER,
                    title="Deliver direct KB answer",
                    kind="delivery",
                    owner="controller",
                    lane="kb",
                    step_result=self._make_kb_direct_result(
                        route=route,
                        rationale=str(route_plan["rationale"]) + " -> kb_direct",
                        answer=kb_answer,
                        evidence_refs=evidence_refs,
                    ),
                    depends_on=[_RUN_STEP_PLAN],
                    provider="kb",
                    preset="direct",
                    route=route,
                )
                conn.commit()
            snapshot = self.get_run_snapshot(run_id=run_id)
            return {
                "ok": True,
                "trace_id": trace_id,
                "run_id": run_id,
                "job_id": None,
                "route": route,
                "route_rationale": str(route_plan["rationale"]) + " → KB direct answer",
                "role_id": role_id,
                "provider": "kb",
                "preset": "direct",
                "kb_used": True,
                "kb_hit_count": route_plan["kb_hit_count"],
                "status": "completed",
                "answer": kb_answer,
                "evidence_refs": evidence_refs,
                "conversation_url": None,
                "routing_ms": round(route_plan["routing_ms"], 1),
                "total_ms": round((time.perf_counter() - started) * 1000, 1),
                "request_metadata": request_metadata,
                "degradation": degradation,
                "controller_status": snapshot["run"]["controller_status"],
                "delivery": snapshot["run"]["delivery"],
                "next_action": snapshot["run"]["next_action"],
                "work_items": snapshot["work_items"],
                "checkpoints": snapshot["checkpoints"],
                "artifacts": snapshot["artifacts"],
            }

        execution_kind = self._resolve_execution_kind(route_plan=route_plan, stable_context=stable_context)
        if execution_kind == "effect":
            step_result = self._dispatch_action_as_effect_intent(
                question=question,
                route_plan=route_plan,
                stable_context=stable_context,
                trace_id=trace_id,
                session_id=session_id,
                account_id=account_id,
                thread_id=thread_id,
                agent_id=agent_id,
            )
            with connect(self._cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                self._persist_step_result(
                    conn,
                    run_id=run_id,
                    work_id=_RUN_STEP_EFFECT,
                    title="Plan a typed effect intent for the requested action",
                    kind="effect",
                    owner="controller",
                    lane="action",
                    step_result=step_result,
                    depends_on=[_RUN_STEP_PLAN],
                    route=route,
                )
                conn.commit()
            snapshot = self.get_run_snapshot(run_id=run_id)
            return {
                "ok": True,
                "trace_id": trace_id,
                "run_id": run_id,
                "job_id": None,
                "route": route,
                "route_rationale": route_plan["rationale"],
                "role_id": role_id,
                "provider": "controller",
                "preset": "effect_intent",
                "kb_used": route_plan["kb_used"],
                "kb_hit_count": route_plan["kb_hit_count"],
                "status": "submitted",
                "answer": None,
                "conversation_url": None,
                "routing_ms": round(route_plan["routing_ms"], 1),
                "total_ms": round((time.perf_counter() - started) * 1000, 1),
                "request_metadata": request_metadata,
                "degradation": degradation,
                "controller_status": snapshot["run"]["controller_status"],
                "delivery": snapshot["run"]["delivery"],
                "next_action": snapshot["run"]["next_action"],
                "work_items": snapshot["work_items"],
                "checkpoints": snapshot["checkpoints"],
                "artifacts": snapshot["artifacts"],
            }

        if execution_kind == "team":
            step_result, dispatch_request = self._dispatch_route_to_team(
                run_id=run_id,
                question=question,
                trace_id=trace_id,
                route_plan=route_plan,
                stable_context=stable_context,
                timeout_seconds=timeout_seconds,
                request_metadata=request_metadata,
            )
            with connect(self._cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                self._persist_step_result(
                    conn,
                    run_id=run_id,
                    work_id=_RUN_STEP_TEAM,
                    title="Dispatch route into the team control plane",
                    kind="team_execution",
                    owner="team_executor",
                    lane="team",
                    step_result=step_result,
                    depends_on=[_RUN_STEP_PLAN],
                    route=route,
                )
                conn.commit()
            if dispatch_request is not None:
                self._start_team_dispatch_worker(**dispatch_request)
            snapshot = self.get_run_snapshot(run_id=run_id)
            return {
                "ok": True,
                "trace_id": trace_id,
                "run_id": run_id,
                "job_id": None,
                "route": route,
                "route_rationale": route_plan["rationale"],
                "role_id": role_id,
                "provider": "team_control_plane",
                "preset": "team_child_executor",
                "kb_used": route_plan["kb_used"],
                "kb_hit_count": route_plan["kb_hit_count"],
                "status": "submitted",
                "answer": None,
                "conversation_url": None,
                "routing_ms": round(route_plan["routing_ms"], 1),
                "total_ms": round((time.perf_counter() - started) * 1000, 1),
                "request_metadata": request_metadata,
                "degradation": degradation,
                "controller_status": snapshot["run"]["controller_status"],
                "delivery": snapshot["run"]["delivery"],
                "next_action": snapshot["run"]["next_action"],
                "work_items": snapshot["work_items"],
                "checkpoints": snapshot["checkpoints"],
                "artifacts": snapshot["artifacts"],
            }

        exec_config = dict(route_mapping.get(route, route_mapping["quick_ask"]))
        enriched_question = self._build_enriched_question(question=question, stable_context=stable_context, kb_chunks=route_plan["kb_chunks"])
        input_obj = {
            "question": enriched_question,
            "advisor_request_fingerprint": request_fingerprint[:32],
            "user_id": user_id,
            "session_id": session_id,
            "role_id": role_id,
            "intent_hint": intent_hint,
        }
        file_paths = stable_context.get("files")
        if isinstance(file_paths, list):
            normalized_file_paths = [str(path).strip() for path in file_paths if str(path).strip()]
            if normalized_file_paths:
                input_obj["file_paths"] = normalized_file_paths
        if stable_context:
            input_obj["context_fingerprint"] = (sanitize_context_hash or "")[:32]
        params_obj = {
            "preset": exec_config["preset"],
            "timeout_seconds": timeout_seconds,
            "max_wait_seconds": 1800,
            "min_chars": 200 if route in {"quick_ask", "kb_answer", "clarify", "hybrid"} else 800,
            "answer_format": "markdown",
            "deep_research": (exec_config["preset"] == "deep_research"),
            "max_retries": max_retries,
            "quality_threshold": quality_threshold,
        }
        client_obj = {
            "name": "advisor_ask",
            "route": route,
            "trace_id": trace_id,
            "session_id": session_id,
            "account_id": account_id,
            "thread_id": thread_id,
            "agent_id": agent_id,
            "role_id": role_id,
            "user_id": user_id,
            "intent_hint": intent_hint,
            "request_fingerprint": request_fingerprint[:32],
            "run_id": run_id,
            "objective_text": str(objective_plan["objective_text"]),
            "objective_kind": str(objective_plan["objective_kind"]),
        }
        try:
            with connect(self._cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                job = job_store.create_job(
                    conn,
                    artifacts_dir=self._cfg.artifacts_dir,
                    idempotency_key=idempotency_key,
                    kind=exec_config["kind"],
                    input=input_obj,
                    params=params_obj,
                    max_attempts=self._cfg.max_attempts,
                    parent_job_id=None,
                    client=client_obj,
                )
                store.upsert_run(
                    conn,
                    run_id=run_id,
                    trace_id=trace_id,
                    request_id=idempotency_key,
                    execution_mode="async",
                    controller_status="WAITING_EXTERNAL",
                    current_work_id=_RUN_STEP_EXECUTE,
                    route=route,
                    provider=exec_config["provider"],
                    preset=exec_config["preset"],
                    plan_obj=route_plan_record,
                    delivery_obj={
                        "status": "submitted",
                        "summary": f"Queued execution on {exec_config['provider']} with preset {exec_config['preset']}.",
                        "job_id": str(job.job_id),
                    },
                    next_action_obj={
                        "type": "await_job_completion",
                        "status": "pending",
                        "job_id": str(job.job_id),
                        "provider": exec_config["provider"],
                        "objective_step_id": _RUN_STEP_EXECUTE,
                    },
                )
                update_run(conn, run_id=run_id, status="WAITING_GATES", route=route, final_job_id=str(job.job_id), degraded=False)
                upsert_step(
                    conn,
                    run_id=run_id,
                    step_id=_RUN_STEP_EXECUTE,
                    step_type="execution",
                    status="LEASED",
                    job_id=str(job.job_id),
                    input_obj={"question": enriched_question},
                    output_obj={"provider": exec_config["provider"], "preset": exec_config["preset"]},
                )
                store.upsert_work_item(
                    conn,
                    run_id=run_id,
                    work_id=_RUN_STEP_EXECUTE,
                    title="Dispatch the selected route to an execution lane",
                    kind="execution",
                    status="QUEUED",
                    owner="controller",
                    lane=exec_config["provider"],
                    priority="high",
                    job_id=str(job.job_id),
                    depends_on=[_RUN_STEP_PLAN],
                    input_obj={"question": enriched_question},
                    output_obj={"provider": exec_config["provider"], "preset": exec_config["preset"]},
                )
                append_event(
                    conn,
                    run_id=run_id,
                    type="controller.dispatch.queued",
                    payload={
                        "trace_id": trace_id,
                        "job_id": str(job.job_id),
                        "route": route,
                        "provider": exec_config["provider"],
                        "preset": exec_config["preset"],
                    },
                )
                self._write_controller_snapshot(conn, run_id=run_id)
                conn.commit()
        except IdempotencyCollision:
            raise
        except PromptPolicyViolation:
            raise
        snapshot = self.get_run_snapshot(run_id=run_id)
        return {
            "ok": True,
            "trace_id": trace_id,
            "run_id": run_id,
            "job_id": str(job.job_id),
            "route": route,
            "route_rationale": route_plan["rationale"],
            "role_id": role_id,
            "provider": exec_config["provider"],
            "preset": exec_config["preset"],
            "kb_used": route_plan["kb_used"],
            "kb_hit_count": route_plan["kb_hit_count"],
            "status": "submitted",
            "answer": None,
            "conversation_url": None,
            "routing_ms": round(route_plan["routing_ms"], 1),
            "total_ms": round((time.perf_counter() - started) * 1000, 1),
            "request_metadata": request_metadata,
            "degradation": degradation,
            "controller_status": "WAITING_EXTERNAL",
            "delivery": snapshot["run"]["delivery"],
            "next_action": snapshot["run"]["next_action"],
            "work_items": snapshot["work_items"],
            "checkpoints": snapshot["checkpoints"],
            "artifacts": snapshot["artifacts"],
        }

    def get_run_snapshot(self, *, run_id: str | None = None, trace_id: str | None = None) -> dict[str, Any] | None:
        target_run_id = run_id
        if target_run_id is None and trace_id:
            with connect(self._cfg.db_path) as conn:
                existing = store.get_run_by_trace_id(conn, trace_id=trace_id)
            target_run_id = str(existing["run_id"]) if existing is not None else None
        if target_run_id:
            self._reconcile_external_progress(run_id=target_run_id)
        with connect(self._cfg.db_path) as conn:
            if run_id:
                snapshot = store.snapshot_run(conn, run_id=run_id)
            elif trace_id:
                run = store.get_run_by_trace_id(conn, trace_id=trace_id)
                snapshot = store.snapshot_run(conn, run_id=run["run_id"]) if run is not None else None
            else:
                snapshot = None
            if snapshot is None:
                return None
            advisor_run = get_advisor_run(conn, run_id=snapshot["run"]["run_id"])
            if advisor_run is not None:
                snapshot["advisor_run"] = advisor_run
            return snapshot

    def get_trace_snapshot(self, *, trace_id: str) -> dict[str, Any] | None:
        snapshot = self.get_run_snapshot(trace_id=trace_id)
        if snapshot is None:
            return None
        run = dict(snapshot["run"])
        plan = dict(run.get("plan") or {})
        delivery = dict(run.get("delivery") or {})
        return {
            "trace_id": str(run.get("trace_id") or trace_id),
            "run_id": run["run_id"],
            "status": delivery.get("status") or run.get("controller_status") or "",
            "selected_route": run.get("route") or "",
            "route_rationale": plan.get("route_rationale") or "",
            "intent_top": plan.get("intent_top") or "",
            "answer": delivery.get("answer") or "",
            "conversation_url": delivery.get("conversation_url"),
            "controller_status": run.get("controller_status"),
            "work_items": snapshot["work_items"],
            "checkpoints": snapshot["checkpoints"],
            "artifacts": snapshot["artifacts"],
            "delivery": delivery,
            "next_action": run.get("next_action") or {},
        }

    def _scenario_execution_preference(self, *, stable_context: dict[str, Any]) -> str:
        scenario_pack = stable_context.get("scenario_pack")
        if not isinstance(scenario_pack, dict):
            return ""
        return str(scenario_pack.get("execution_preference") or "").strip().lower()

    def _explicit_team_requested(self, *, route_plan: dict[str, Any], stable_context: dict[str, Any]) -> bool:
        return bool(stable_context.get("team")) or bool(stable_context.get("topology_id")) or str(route_plan.get("executor_lane") or "") == "team"

    def _build_objective_plan(
        self,
        *,
        question: str,
        route_plan: dict[str, Any],
        intent_hint: str,
        stable_context: dict[str, Any],
    ) -> dict[str, Any]:
        route = str(route_plan.get("route") or "quick_ask")
        executor_lane = str(route_plan.get("executor_lane") or "")
        execution_preference = self._scenario_execution_preference(stable_context=stable_context)
        cc = self._state.get("cc_native")
        objective_kind = "answer"
        if route == "action":
            objective_kind = "effect"
        elif route in {"report", "write_report"}:
            objective_kind = "artifact_delivery"
        elif execution_preference == "team" or (cc is not None and self._explicit_team_requested(route_plan=route_plan, stable_context=stable_context)):
            objective_kind = "team_delivery"

        constraints: list[dict[str, Any]] = []
        for key in ("deadline", "repo", "cwd", "audience", "format"):
            value = stable_context.get(key)
            if value:
                constraints.append({"type": key, "value": value})
        if intent_hint:
            constraints.append({"type": "intent_hint", "value": intent_hint})

        success_criteria = [
            {"type": "route_selected", "value": route},
            {"type": "decision_ready_delivery", "value": True},
        ]
        if objective_kind == "effect":
            success_criteria.append({"type": "effect_intent_created", "value": True})
        elif objective_kind == "team_delivery":
            success_criteria.append({"type": "team_child_executor_tracked", "value": True})
        else:
            success_criteria.append({"type": "external_execution_tracked", "value": True})

        steps = [
            {"work_id": _RUN_STEP_INPUT, "kind": "intake", "owner": "controller"},
            {"work_id": _RUN_STEP_PLAN, "kind": "planning", "owner": "controller"},
        ]
        if objective_kind == "effect":
            steps.append({"work_id": _RUN_STEP_EFFECT, "kind": "effect", "owner": "controller"})
        elif objective_kind == "team_delivery":
            steps.append({"work_id": _RUN_STEP_TEAM, "kind": "team_execution", "owner": "team_executor"})
        else:
            steps.append({"work_id": _RUN_STEP_EXECUTE, "kind": "execution", "owner": "controller"})
        steps.append({"work_id": _RUN_STEP_DELIVER, "kind": "delivery", "owner": "controller"})

        route_plan_record = dict(route_plan)
        route_plan_record.pop("graph_state", None)
        return {
            **route_plan_record,
            "objective_text": question,
            "objective_kind": objective_kind,
            "success_criteria": success_criteria,
            "constraints": constraints,
            "delivery_target": {"channel": "api", "mode": "decision_ready"},
            "plan_version": 2,
            "steps": steps,
        }

    def _resolve_execution_kind(self, *, route_plan: dict[str, Any], stable_context: dict[str, Any]) -> str:
        route = str(route_plan.get("route") or "")
        if route == "action":
            return "effect"
        execution_preference = self._scenario_execution_preference(stable_context=stable_context)
        if execution_preference == "job":
            return "job"
        if execution_preference == "team":
            return "team"
        cc = self._state.get("cc_native")
        if cc is not None and self._explicit_team_requested(route_plan=route_plan, stable_context=stable_context):
            return "team"
        return "job"

    def _make_kb_direct_result(
        self,
        *,
        route: str,
        rationale: str,
        answer: str,
        evidence_refs: list[str],
    ) -> StepResult:
        return StepResult(
            work_status="COMPLETED",
            controller_status="DELIVERED",
            summary="Answered directly from the knowledge base.",
            next_action={
                "type": "await_user_followup",
                "status": "optional",
                "reason": "The current request was answered directly from existing knowledge.",
            },
            output={"answer": answer, "evidence_refs": list(evidence_refs)},
            delivery={
                "status": "completed",
                "summary": "Answered directly from the knowledge base.",
                "answer": answer,
                "blockers": [],
                "decisions": [{"type": "route", "value": route, "reason": rationale}],
                "artifacts": list(evidence_refs),
            },
            artifacts=[
                ControllerArtifact(
                    artifact_id=f"kb:{artifact_id}",
                    work_id=_RUN_STEP_DELIVER,
                    kind="kb_ref",
                    title=artifact_id,
                    metadata={"artifact_id": artifact_id},
                )
                for artifact_id in evidence_refs
            ],
        )

    def _dispatch_action_as_effect_intent(
        self,
        *,
        question: str,
        route_plan: dict[str, Any],
        stable_context: dict[str, Any],
        trace_id: str,
        session_id: str,
        account_id: str,
        thread_id: str,
        agent_id: str,
    ) -> StepResult:
        action_result = self._evaluate_action_effect(
            question=question,
            route_plan=route_plan,
            stable_context=stable_context,
            trace_id=trace_id,
            session_id=session_id,
            account_id=account_id,
            thread_id=thread_id,
            agent_id=agent_id,
        )
        payload = dict(action_result.get("route_result") or {})
        status = str(payload.get("status") or "action_planned")
        capabilities = list(payload.get("required_capabilities") or [])
        missing = list(payload.get("missing_capabilities") or [])
        needs_confirmation = bool(payload.get("needs_confirmation", False) or status == "action_planned")
        intent = EffectIntent(
            intent_id=f"eff_{uuid.uuid4().hex[:12]}",
            effect_type=(capabilities[0] if capabilities else "generic_action"),
            payload={
                "question": question,
                "normalized_question": str(route_plan.get("normalized_question") or question),
                "context": dict(stable_context or {}),
            },
            requires_approval=needs_confirmation or bool(payload.get("needs_clarification", False)),
            required_capabilities=capabilities,
            missing_capabilities=missing,
            status=status,
            rationale=str(payload.get("answer") or "")[:280],
        )

        if status == "capability_unknown":
            next_action = {
                "type": "await_user_clarification",
                "status": "blocking",
                "questions": [str(payload.get("answer") or "").strip()],
            }
            checkpoint_title = "Clarify the requested external action"
        elif status == "capability_missing":
            next_action = {
                "type": "await_user_confirmation",
                "status": "blocking",
                "reason": "Required external capabilities are not currently configured.",
            }
            checkpoint_title = "Approve or revise the effect intent despite missing capabilities"
        else:
            next_action = {
                "type": "await_user_confirmation",
                "status": "blocking",
                "effect_intent_id": intent.intent_id,
            }
            checkpoint_title = "Approve the effect intent before execution"

        checkpoint = ControllerCheckpoint(
            checkpoint_id=f"cpi_{uuid.uuid4().hex[:12]}",
            title=checkpoint_title,
            status="NEEDS_HUMAN",
            blocking=True,
            details={"effect_intent": intent.to_dict(), "route_status": status},
        )
        answer = str(payload.get("answer") or "")
        return StepResult(
            work_status="WAITING_HUMAN",
            controller_status="WAITING_HUMAN",
            summary=answer[:240] or "Action request converted into an effect intent.",
            next_action=next_action,
            output={"route_result": payload, "effect_intent": intent.to_dict()},
            delivery={
                "status": "waiting_human",
                "summary": answer[:240] or "Action intent requires user input before execution.",
                "answer": answer,
                "blockers": [checkpoint_title],
                "decisions": [{"type": "route", "value": "action", "reason": str(route_plan.get("rationale") or "")}],
                "artifacts": [intent.intent_id],
            },
            checkpoints=[checkpoint],
            effect_intents=[intent],
            artifacts=[
                ControllerArtifact(
                    artifact_id=intent.intent_id,
                    work_id=_RUN_STEP_EFFECT,
                    kind="effect_intent",
                    title=f"Effect intent: {intent.effect_type}",
                    metadata=intent.to_dict(),
                )
            ],
        )

    def _evaluate_action_effect(
        self,
        *,
        question: str,
        route_plan: dict[str, Any],
        stable_context: dict[str, Any],
        trace_id: str,
        session_id: str,
        account_id: str,
        thread_id: str,
        agent_id: str,
    ) -> dict[str, Any]:
        _ = (trace_id, session_id, account_id, thread_id, agent_id)
        required_capabilities = list(stable_context.get("required_capabilities") or [])
        available_capabilities = list(stable_context.get("available_capabilities") or required_capabilities)
        return {
            "route_result": {
                "status": "action_planned",
                "answer": (
                    "The requested action was converted into an effect intent. "
                    "Confirm the intent before execution."
                ),
                "required_capabilities": required_capabilities,
                "available_capabilities": available_capabilities,
                "needs_confirmation": True,
                "executor": "action",
                "normalized_question": str(route_plan.get("normalized_question") or question),
            },
            "route_status": "action_planned",
        }

    def _dispatch_route_to_team(
        self,
        *,
        run_id: str,
        question: str,
        trace_id: str,
        route_plan: dict[str, Any],
        stable_context: dict[str, Any],
        timeout_seconds: int,
        request_metadata: dict[str, Any],
    ) -> tuple[StepResult, dict[str, Any] | None]:
        cc = self._state.get("cc_native")
        if cc is None:
            return (
                StepResult(
                    work_status="FAILED",
                    controller_status="FAILED",
                    summary="Team execution requested, but cc_native is not initialized.",
                    next_action={"type": "investigate_runtime", "status": "blocking"},
                    output={"error": "cc_native_not_initialized"},
                    delivery={"status": "failed", "summary": "Team execution runtime is unavailable."},
                ),
                None,
            )

        control_plane = getattr(cc, "_team_control_plane", None)
        team_spec = None
        topology = None
        if control_plane is not None:
            try:
                team_spec, topology = control_plane.resolve_team_spec(
                    team=stable_context.get("team"),
                    topology_id=str(stable_context.get("topology_id") or ""),
                    task_type=str(route_plan.get("route") or ""),
                )
            except Exception:
                team_spec = None
                topology = None
        if team_spec is None:
            return (
                StepResult(
                    work_status="WAITING_HUMAN",
                    controller_status="WAITING_HUMAN",
                    summary="No team topology could be resolved for this route.",
                    next_action={"type": "await_team_topology", "status": "blocking"},
                    output={"route": str(route_plan.get("route") or ""), "topology_id": str(stable_context.get("topology_id") or "")},
                    delivery={
                        "status": "waiting_human",
                        "summary": "A team executor is required, but no team topology could be resolved.",
                        "blockers": ["Missing team topology"],
                    },
                    checkpoints=[
                        ControllerCheckpoint(
                            checkpoint_id=f"tcp_{uuid.uuid4().hex[:12]}",
                            title="Provide or resolve a team topology",
                            status="NEEDS_HUMAN",
                            blocking=True,
                            details={"route": str(route_plan.get("route") or ""), "reason": "team_topology_missing"},
                        )
                    ],
                ),
                None,
            )

        from chatgptrest.kernel.cc_executor import CcTask

        task = CcTask(
            task_type=str(route_plan.get("route") or "architecture_review"),
            description=question,
            files=list(stable_context.get("files") or []),
            timeout=int(timeout_seconds),
            model=str(stable_context.get("team_model") or "sonnet"),
            cwd=str(stable_context.get("cwd") or ""),
            context={
                **dict(stable_context or {}),
                "repo": str(stable_context.get("repo") or stable_context.get("cwd") or ""),
                "controller_run_id": run_id,
                "trace_id": trace_id,
                "request_metadata": dict(request_metadata or {}),
            },
            trace_id=trace_id,
        )

        output = {
            "route": str(route_plan.get("route") or ""),
            "team_id": str(getattr(team_spec, "team_id", "") or ""),
            "topology_id": str(getattr(topology, "topology_id", "") or ""),
            "status": "submitted",
        }
        return (
            StepResult(
                work_status="RUNNING",
                controller_status="WAITING_EXTERNAL",
                summary="Team child executor submitted and tracked by the controller.",
                next_action={
                    "type": "await_team_completion",
                    "status": "pending",
                    "team_id": output["team_id"],
                    "topology_id": output["topology_id"],
                },
                output=output,
                delivery={
                    "status": "submitted",
                    "summary": "Submitted to the team child executor.",
                    "team_id": output["team_id"],
                    "topology_id": output["topology_id"],
                },
            ),
            {
                "run_id": run_id,
                "route": str(route_plan.get("route") or ""),
                "task": task,
                "team_spec": team_spec,
            },
        )

    def _start_team_dispatch_worker(self, *, run_id: str, route: str, task: Any, team_spec: Any) -> None:
        worker = threading.Thread(
            target=self._run_team_dispatch,
            kwargs={
                "run_id": run_id,
                "route": route,
                "task": task,
                "team_spec": team_spec,
            },
            daemon=True,
            name=f"controller-team-{run_id[:8]}",
        )
        worker.start()

    def _run_team_dispatch(self, *, run_id: str, route: str, task: Any, team_spec: Any) -> None:
        cc = self._state.get("cc_native")
        if cc is None:
            return
        try:
            result = asyncio.run(cc.dispatch_team(task, team=team_spec))
            step_result = self._project_team_result(route=route, result=result)
        except Exception as exc:
            step_result = StepResult(
                work_status="FAILED",
                controller_status="FAILED",
                summary=f"Team child executor failed: {exc}",
                next_action={"type": "investigate_team_failure", "status": "blocking"},
                output={"error": str(exc)},
                delivery={"status": "failed", "summary": f"Team child executor failed: {exc}"},
            )
        try:
            with connect(self._cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                self._persist_step_result(
                    conn,
                    run_id=run_id,
                    work_id=_RUN_STEP_TEAM,
                    title="Dispatch route into the team control plane",
                    kind="team_execution",
                    owner="team_executor",
                    lane="team",
                    step_result=step_result,
                    depends_on=[_RUN_STEP_PLAN],
                    route=route,
                )
                conn.commit()
        except Exception:
            return

    def _project_team_result(self, *, route: str, result: Any) -> StepResult:
        checkpoints: list[ControllerCheckpoint] = []
        for raw in list(getattr(result, "team_checkpoints", []) or []):
            raw_status = str((raw or {}).get("status") or "pending")
            checkpoint_status = "NEEDS_HUMAN" if raw_status == "pending" else "RESOLVED"
            checkpoints.append(
                ControllerCheckpoint(
                    checkpoint_id=str((raw or {}).get("checkpoint_id") or f"tcp_{uuid.uuid4().hex[:12]}"),
                    title=str((raw or {}).get("summary") or (raw or {}).get("title") or "Team gate"),
                    status=checkpoint_status,
                    blocking=True,
                    details={"team_gate": True, **dict(raw or {})},
                )
            )
        team_digest = str(getattr(result, "team_digest", "") or "")
        artifacts_out = []
        if team_digest:
            artifacts_out.append(
                ControllerArtifact(
                    artifact_id=f"team_digest:{str(getattr(result, 'team_run_id', '') or uuid.uuid4().hex[:8])}",
                    work_id=_RUN_STEP_TEAM,
                    kind="team_digest",
                    title="Team digest",
                    metadata={"team_digest": team_digest},
                )
            )
        team_run_id = str(getattr(result, "team_run_id", "") or "")
        if team_run_id:
            artifacts_out.append(
                ControllerArtifact(
                    artifact_id=f"team_run:{team_run_id}",
                    work_id=_RUN_STEP_TEAM,
                    kind="team_run",
                    title="Team run",
                    metadata={"team_run_id": team_run_id},
                )
            )
        controller_status = "WAITING_HUMAN" if checkpoints else ("DELIVERED" if bool(getattr(result, "ok", False)) else "FAILED")
        work_status = "WAITING_HUMAN" if checkpoints else ("COMPLETED" if bool(getattr(result, "ok", False)) else "FAILED")
        next_action = (
            {
                "type": "await_human_checkpoint",
                "status": "blocking",
                "team_run_id": team_run_id,
                "checkpoint_ids": [cp.checkpoint_id for cp in checkpoints],
            }
            if checkpoints
            else {
                "type": "await_user_followup",
                "status": "optional",
                "team_run_id": team_run_id,
            }
        )
        return StepResult(
            work_status=work_status,
            controller_status=controller_status,
            summary=(team_digest[:240] if team_digest else str(getattr(result, "output", "") or "")[:240]) or f"Team route {route} finished.",
            next_action=next_action,
            output={
                "team_run_id": team_run_id,
                "team_digest": team_digest,
                "role_results": dict(getattr(result, "role_results", {}) or {}),
                "ok": bool(getattr(result, "ok", False)),
            },
            delivery={
                "status": "waiting_human" if checkpoints else ("completed" if bool(getattr(result, "ok", False)) else "failed"),
                "summary": (team_digest[:240] if team_digest else str(getattr(result, "output", "") or "")[:240]) or f"Team route {route} finished.",
                "answer": str(getattr(result, "output", "") or ""),
                "blockers": [cp.title for cp in checkpoints],
                "decisions": [{"type": "route", "value": route, "reason": "team_child_executor"}],
                "artifacts": [artifact.artifact_id for artifact in artifacts_out],
            },
            artifacts=artifacts_out,
            checkpoints=checkpoints,
        )

    def _persist_step_result(
        self,
        conn: Any,
        *,
        run_id: str,
        work_id: str,
        title: str,
        kind: str,
        owner: str,
        lane: str,
        step_result: StepResult,
        depends_on: list[str] | None = None,
        provider: str | None = None,
        preset: str | None = None,
        route: str | None = None,
    ) -> None:
        status_map = {
            "DELIVERED": "COMPLETED",
            "FAILED": "FAILED",
            "CANCELLED": "CANCELLED",
            "WAITING_EXTERNAL": "WAITING_GATES",
            "WAITING_HUMAN": "WAITING_GATES",
            "RUNNING": "RUNNING",
            "PLANNED": "PLAN_COMPILED",
        }
        advisor_status = status_map.get(step_result.controller_status, "RUNNING")
        ended_at = time.time() if step_result.controller_status in {"DELIVERED", "FAILED", "CANCELLED"} else None
        blocked_reason = ""
        if step_result.controller_status == "WAITING_HUMAN":
            blocked_reason = step_result.summary
        store.upsert_run(
            conn,
            run_id=run_id,
            trace_id=None,
            request_id=None,
            execution_mode="async",
            controller_status=step_result.controller_status,
            current_work_id=(None if step_result.controller_status in {"DELIVERED", "FAILED", "CANCELLED"} else work_id),
            blocked_reason=blocked_reason,
            route=route,
            provider=provider,
            preset=preset,
            delivery_obj=step_result.delivery,
            next_action_obj=step_result.next_action,
            ended_at=ended_at,
        )
        update_run(
            conn,
            run_id=run_id,
            status=advisor_status,
            route=route,
            degraded=False,
        )
        job_id = str(step_result.output.get("job_id") or "") or None
        step_status = {
            "COMPLETED": "SUCCEEDED",
            "FAILED": "FAILED",
            "CANCELLED": "CANCELLED",
        }.get(step_result.work_status, "LEASED")
        upsert_step(
            conn,
            run_id=run_id,
            step_id=work_id,
            step_type=kind,
            status=step_status,
            job_id=job_id,
            input_obj={"depends_on": list(depends_on or [])},
            output_obj=step_result.to_dict(),
        )
        store.upsert_work_item(
            conn,
            run_id=run_id,
            work_id=work_id,
            title=title,
            kind=kind,
            status=step_result.work_status,
            owner=owner,
            lane=lane,
            priority="high",
            job_id=job_id,
            depends_on=depends_on or [],
            input_obj={"depends_on": list(depends_on or [])},
            output_obj=step_result.to_dict(),
        )
        for checkpoint in step_result.checkpoints:
            store.upsert_checkpoint(
                conn,
                run_id=run_id,
                checkpoint_id=checkpoint.checkpoint_id,
                title=checkpoint.title,
                status=checkpoint.status,
                blocking=checkpoint.blocking,
                details_obj=checkpoint.details,
            )
        for artifact in step_result.artifacts:
            store.upsert_artifact(
                conn,
                run_id=run_id,
                artifact_id=artifact.artifact_id,
                work_id=artifact.work_id or work_id,
                kind=artifact.kind,
                title=artifact.title,
                path=artifact.path,
                uri=artifact.uri,
                metadata_obj=artifact.metadata,
            )
        for intent in step_result.effect_intents:
            store.upsert_artifact(
                conn,
                run_id=run_id,
                artifact_id=intent.intent_id,
                work_id=work_id,
                kind="effect_intent",
                title=f"Effect intent: {intent.effect_type}",
                metadata_obj=intent.to_dict(),
            )
        append_event(
            conn,
            run_id=run_id,
            type="controller.step.updated",
            payload={
                "work_id": work_id,
                "kind": kind,
                "work_status": step_result.work_status,
                "controller_status": step_result.controller_status,
            },
        )
        self._write_controller_snapshot(conn, run_id=run_id)

    def _reconcile_external_progress(self, *, run_id: str) -> None:
        with connect(self._cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            snapshot = store.snapshot_run(conn, run_id=run_id)
            if snapshot is None:
                conn.commit()
                return
            run = dict(snapshot["run"])
            updated = False
            for work_item in list(snapshot["work_items"]):
                kind = str(work_item.get("kind") or "")
                if work_item.get("job_id") and kind == "execution":
                    updated = self._reconcile_job_work_item(conn, run=run, work_item=work_item) or updated
                elif kind == "team_execution":
                    updated = self._reconcile_team_work_item(conn, run=run, work_item=work_item) or updated
            if updated:
                self._write_controller_snapshot(conn, run_id=run_id)
            conn.commit()

    def _reconcile_job_work_item(self, conn: Any, *, run: dict[str, Any], work_item: dict[str, Any]) -> bool:
        job_id = str(work_item.get("job_id") or "")
        if not job_id:
            return False
        job = job_store.get_job(conn, job_id=job_id)
        if job is None:
            return False
        changed = False
        if job.conversation_url:
            store.upsert_artifact(
                conn,
                run_id=str(run["run_id"]),
                artifact_id=f"conversation:{job_id}",
                work_id=str(work_item["work_id"]),
                kind="conversation_url",
                title="Conversation URL",
                uri=str(job.conversation_url),
                metadata_obj={"job_id": job_id},
            )
            changed = True
        status_value = str(job.status.value)
        if status_value == "completed" and job.answer_path:
            answer = artifacts.read_text_preview(
                artifacts_dir=self._cfg.artifacts_dir,
                path=job.answer_path,
                max_chars=20000,
            )
            step_result = StepResult(
                work_status="COMPLETED",
                controller_status="DELIVERED",
                summary=answer[:240] or "External job completed.",
                next_action={"type": "await_user_followup", "status": "optional"},
                output={
                    **dict(work_item.get("output") or {}),
                    "job_id": job_id,
                    "job_status": status_value,
                    "answer_path": job.answer_path,
                    "conversation_url": job.conversation_url,
                },
                delivery={
                    "status": "completed",
                    "summary": answer[:240] or "External execution finished.",
                    "answer": answer,
                    "blockers": [],
                    "decisions": [{"type": "route", "value": run.get("route") or "", "reason": "job_completed"}],
                    "artifacts": [f"answer:{job_id}"],
                    "conversation_url": job.conversation_url,
                },
                artifacts=[
                    ControllerArtifact(
                        artifact_id=f"answer:{job_id}",
                        work_id=str(work_item["work_id"]),
                        kind="answer",
                        title="Answer artifact",
                        path=str(job.answer_path),
                        metadata={"job_id": job_id, "answer_chars": job.answer_chars},
                    )
                ],
            )
            self._persist_step_result(
                conn,
                run_id=str(run["run_id"]),
                work_id=str(work_item["work_id"]),
                title=str(work_item.get("title") or "Execute route"),
                kind="execution",
                owner=str(work_item.get("owner") or "controller"),
                lane=str(work_item.get("lane") or "external"),
                step_result=step_result,
                depends_on=list(work_item.get("depends_on") or []),
                provider=str(run.get("provider") or ""),
                preset=str(run.get("preset") or ""),
                route=str(run.get("route") or ""),
            )
            return True
        if status_value == "needs_followup":
            retry_after = None
            try:
                if getattr(job, "not_before", None):
                    retry_after = max(0, int(float(job.not_before) - time.time()))
            except Exception:
                retry_after = None
            summary = str(job.last_error or "External job requested same-session repair.")
            step_result = StepResult(
                work_status="WAITING_HUMAN",
                controller_status="WAITING_HUMAN",
                summary=summary,
                next_action={
                    "type": "same_session_repair",
                    "status": "blocking",
                    "job_id": job_id,
                    "error_type": str(job.last_error_type or ""),
                    "retry_after_seconds": retry_after,
                },
                output={
                    **dict(work_item.get("output") or {}),
                    "job_id": job_id,
                    "job_status": status_value,
                    "last_error": str(job.last_error or ""),
                    "last_error_type": str(job.last_error_type or ""),
                    "retry_after_seconds": retry_after,
                    "conversation_url": str(job.conversation_url or ""),
                },
                delivery={
                    "status": "waiting_human",
                    "summary": summary,
                    "blockers": [summary],
                    "conversation_url": str(job.conversation_url or "") or None,
                },
            )
            self._persist_step_result(
                conn,
                run_id=str(run["run_id"]),
                work_id=str(work_item["work_id"]),
                title=str(work_item.get("title") or "Execute route"),
                kind="execution",
                owner=str(work_item.get("owner") or "controller"),
                lane=str(work_item.get("lane") or "external"),
                step_result=step_result,
                depends_on=list(work_item.get("depends_on") or []),
                provider=str(run.get("provider") or ""),
                preset=str(run.get("preset") or ""),
                route=str(run.get("route") or ""),
            )
            return True
        if status_value in {"error", "canceled"}:
            step_result = StepResult(
                work_status="FAILED",
                controller_status="FAILED",
                summary=str(job.last_error or f"External job {status_value}."),
                next_action={"type": "investigate_or_retry", "status": "blocking", "job_id": job_id},
                output={
                    **dict(work_item.get("output") or {}),
                    "job_id": job_id,
                    "job_status": status_value,
                    "last_error": str(job.last_error or ""),
                },
                delivery={
                    "status": "failed",
                    "summary": str(job.last_error or f"External job {status_value}."),
                    "blockers": [str(job.last_error or f"job:{status_value}")],
                },
            )
            self._persist_step_result(
                conn,
                run_id=str(run["run_id"]),
                work_id=str(work_item["work_id"]),
                title=str(work_item.get("title") or "Execute route"),
                kind="execution",
                owner=str(work_item.get("owner") or "controller"),
                lane=str(work_item.get("lane") or "external"),
                step_result=step_result,
                depends_on=list(work_item.get("depends_on") or []),
                provider=str(run.get("provider") or ""),
                preset=str(run.get("preset") or ""),
                route=str(run.get("route") or ""),
            )
            return True
        return changed

    def _reconcile_team_work_item(self, conn: Any, *, run: dict[str, Any], work_item: dict[str, Any]) -> bool:
        output = dict(work_item.get("output") or {})
        team_run_id = str(output.get("team_run_id") or "")
        if not team_run_id:
            return False
        plane = getattr(self._state.get("cc_native"), "_team_control_plane", None)
        if plane is None:
            return False
        team_snapshot = plane.get_run(team_run_id)
        if not team_snapshot:
            return False
        raw_checkpoints = list(team_snapshot.get("checkpoints") or [])
        checkpoints = [
            ControllerCheckpoint(
                checkpoint_id=str(item.get("checkpoint_id") or f"tcp_{uuid.uuid4().hex[:12]}"),
                title=str(item.get("summary") or item.get("checkpoint_id") or "Team gate"),
                status=("NEEDS_HUMAN" if str(item.get("status") or "pending") == "pending" else "RESOLVED"),
                blocking=True,
                details={"team_gate": True, **dict(item)},
            )
            for item in raw_checkpoints
        ]
        controller_status = "WAITING_HUMAN" if any(cp.status == "NEEDS_HUMAN" for cp in checkpoints) else ("DELIVERED" if str(team_snapshot.get("status") or "") == "completed" else None)
        if controller_status is None:
            return False
        step_result = StepResult(
            work_status=("WAITING_HUMAN" if controller_status == "WAITING_HUMAN" else "COMPLETED"),
            controller_status=controller_status,
            summary=str(team_snapshot.get("digest") or "")[:240] or f"Team run {team_run_id} synchronized.",
            next_action=(
                {
                    "type": "await_human_checkpoint",
                    "status": "blocking",
                    "team_run_id": team_run_id,
                    "checkpoint_ids": [cp.checkpoint_id for cp in checkpoints if cp.status == "NEEDS_HUMAN"],
                }
                if controller_status == "WAITING_HUMAN"
                else {"type": "await_user_followup", "status": "optional", "team_run_id": team_run_id}
            ),
            output={**output, "team_digest": str(team_snapshot.get("digest") or "")},
            delivery={
                "status": "waiting_human" if controller_status == "WAITING_HUMAN" else "completed",
                "summary": str(team_snapshot.get("digest") or "")[:240] or f"Team run {team_run_id} synchronized.",
                "answer": str(team_snapshot.get("final_output_preview") or ""),
                "blockers": [cp.title for cp in checkpoints if cp.status == "NEEDS_HUMAN"],
            },
            checkpoints=checkpoints,
            artifacts=[
                ControllerArtifact(
                    artifact_id=f"team_run:{team_run_id}",
                    work_id=str(work_item["work_id"]),
                    kind="team_run",
                    title="Team run",
                    metadata={"team_run_id": team_run_id, "status": str(team_snapshot.get("status") or "")},
                )
            ],
        )
        self._persist_step_result(
            conn,
            run_id=str(run["run_id"]),
            work_id=str(work_item["work_id"]),
            title=str(work_item.get("title") or "Dispatch route into the team control plane"),
            kind="team_execution",
            owner=str(work_item.get("owner") or "team_executor"),
            lane=str(work_item.get("lane") or "team"),
            step_result=step_result,
            depends_on=list(work_item.get("depends_on") or []),
            provider="team_control_plane",
            preset="team_child_executor",
            route=str(run.get("route") or ""),
        )
        return True

    def _ensure_run(
        self,
        *,
        request_id: str,
        trace_id: str,
        execution_mode: str,
        question: str,
        normalized_question: str,
        request_obj: dict[str, Any],
        session_id: str,
        account_id: str,
        thread_id: str,
        agent_id: str,
        role_id: str,
        user_id: str,
        intent_hint: str,
    ) -> str:
        with connect(self._cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = store.get_run_by_request_id(conn, request_id=request_id)
            if existing is None and trace_id:
                existing = store.get_run_by_trace_id(conn, trace_id=trace_id)
            run_id = str(existing["run_id"]) if existing is not None else new_run_id()
            if get_advisor_run(conn, run_id=run_id) is None:
                create_run(
                    conn,
                    run_id=run_id,
                    request_id=request_id,
                    mode=f"controller_{execution_mode}",
                    status="NEW",
                    route=None,
                    raw_question=question,
                    normalized_question=normalized_question,
                    context={"controller": True, "trace_id": trace_id, "intent_hint": intent_hint},
                    quality_threshold=None,
                    crosscheck=False,
                    max_retries=0,
                    orchestrate_job_id=None,
                    final_job_id=None,
                    degraded=False,
                )
                append_event(
                    conn,
                    run_id=run_id,
                    type="run.created",
                    payload={"run_id": run_id, "request_id": request_id, "trace_id": trace_id},
                )
            store.upsert_run(
                conn,
                run_id=run_id,
                trace_id=trace_id,
                request_id=request_id,
                execution_mode=execution_mode,
                controller_status="UNDERSTOOD",
                session_id=session_id,
                account_id=account_id,
                thread_id=thread_id,
                agent_id=agent_id,
                role_id=role_id,
                user_id=user_id,
                intent_hint=intent_hint,
                question=question,
                normalized_question=normalized_question,
                request_obj=request_obj,
            )
            upsert_step(
                conn,
                run_id=run_id,
                step_id=_RUN_STEP_INPUT,
                step_type="intake",
                status="SUCCEEDED",
                input_obj={"question": question},
                output_obj={"trace_id": trace_id, "request_id": request_id},
            )
            store.upsert_work_item(
                conn,
                run_id=run_id,
                work_id=_RUN_STEP_INPUT,
                title="Capture the user request and normalize identity",
                kind="intake",
                status="COMPLETED",
                owner="controller",
                lane="input",
                input_obj={"question": question},
                output_obj={"trace_id": trace_id, "request_id": request_id},
            )
            append_event(
                conn,
                run_id=run_id,
                type="controller.run.understood",
                payload={"trace_id": trace_id, "execution_mode": execution_mode},
            )
            self._write_controller_snapshot(conn, run_id=run_id)
            conn.commit()
        return run_id

    def _mark_input_ready(self, *, run_id: str, question: str, execution_mode: str) -> None:
        with connect(self._cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            store.upsert_run(
                conn,
                run_id=run_id,
                trace_id=None,
                request_id=None,
                execution_mode=execution_mode,
                controller_status="RUNNING",
            )
            update_run(conn, run_id=run_id, status="RUNNING", normalized_question=question, degraded=False)
            self._write_controller_snapshot(conn, run_id=run_id)
            conn.commit()

    def _plan_async_route(
        self,
        *,
        question: str,
        trace_id: str,
        intent_hint: str,
        session_id: str,
        account_id: str,
        thread_id: str,
        agent_id: str,
        role_id: str,
        stable_context: dict[str, Any],
    ) -> dict[str, Any]:
        from chatgptrest.advisor.graph import (
            analyze_intent,
            kb_probe,
            normalize,
            route_decision,
        )

        graph_state: dict[str, Any] = {
            "user_message": question,
            "trace_id": trace_id,
            "session_id": session_id,
            "account_id": account_id,
            "thread_id": thread_id,
            "agent_id": agent_id,
            "task_intake": dict(stable_context.get("task_intake") or {}) if isinstance(stable_context.get("task_intake"), dict) else {},
            "scenario_pack": dict(stable_context.get("scenario_pack") or {}) if isinstance(stable_context.get("scenario_pack"), dict) else {},
            "_runtime": self._state,
        }
        if intent_hint == "research":
            graph_state["intent_top"] = "DO_RESEARCH"
            graph_state["intent_confidence"] = 0.9
        elif intent_hint == "report":
            graph_state["intent_top"] = "WRITE_REPORT"
            graph_state["intent_confidence"] = 0.9
        elif intent_hint == "quick":
            graph_state["intent_top"] = "QUICK_QUESTION"
            graph_state["intent_confidence"] = 0.9

        started = time.perf_counter()
        norm_result = normalize(graph_state)
        graph_state.update(norm_result)
        kb_result = kb_probe(graph_state)
        graph_state.update(kb_result)
        if "intent_top" not in graph_state or not intent_hint:
            intent_result = analyze_intent(graph_state)
            graph_state.update(intent_result)
        route_result = route_decision(graph_state)
        graph_state.update(route_result)
        scenario_pack = graph_state.get("scenario_pack")
        if isinstance(scenario_pack, dict):
            preferred_route = str(scenario_pack.get("route_hint") or "").strip()
            profile = str(scenario_pack.get("profile") or "").strip()
            if preferred_route and preferred_route != str(graph_state.get("selected_route") or ""):
                graph_state["selected_route"] = preferred_route
                rationale = str(graph_state.get("route_rationale") or "").strip()
                suffix = f"ScenarioPack({profile or 'planning'}) override"
                graph_state["route_rationale"] = f"{rationale} -> {suffix}" if rationale else suffix
        return {
            "route": str(graph_state.get("selected_route", "quick_ask")),
            "rationale": str(graph_state.get("route_rationale", "")),
            "executor_lane": str(graph_state.get("executor_lane", "")),
            "intent_top": str(graph_state.get("intent_top", "")),
            "normalized_question": str(graph_state.get("normalized_message") or question),
            "kb_used": bool(graph_state.get("kb_has_answer", False)),
            "kb_answerability": float(graph_state.get("kb_answerability", 0.0) or 0.0),
            "kb_hit_count": len(list(graph_state.get("kb_top_chunks", []))),
            "kb_chunks": list(graph_state.get("kb_top_chunks", [])),
            "routing_ms": (time.perf_counter() - started) * 1000,
            "graph_state": graph_state,
            "role_id": role_id,
        }

    def _build_kb_direct_answer(
        self,
        *,
        question: str,
        kb_chunks: list[dict[str, Any]],
        synthesis_enabled: bool,
    ) -> tuple[str, list[str]]:
        answer_parts: list[str] = []
        evidence_refs: list[str] = []
        for chunk in kb_chunks[:5]:
            title = str(chunk.get("title") or "")
            snippet = str(chunk.get("snippet") or "")
            answer_parts.append(f"[{title}]: {snippet}" if title else snippet)
            artifact_id = str(chunk.get("artifact_id") or "").strip()
            if artifact_id:
                evidence_refs.append(artifact_id)
        kb_answer = "\n\n".join(answer_parts)
        if synthesis_enabled:
            try:
                from chatgptrest.advisor.graph import _get_llm_fn

                llm_fn = _get_llm_fn("default", state={"_runtime": self._state})
                if llm_fn:
                    prompt = (
                        "根据以下知识库内容，简洁准确地回答用户问题。\n\n"
                        f"用户问题：{question}\n\n知识库内容：\n{kb_answer}\n\n"
                        "请直接回答，不要重复问题，不要输出原始文档ID。"
                    )
                    synthesized = llm_fn(prompt, "你是知识助手，根据提供的知识库内容回答问题。")
                    if synthesized and len(str(synthesized).strip()) > 10:
                        kb_answer = str(synthesized)
            except Exception:
                pass
        return kb_answer, evidence_refs

    def _build_enriched_question(
        self,
        *,
        question: str,
        stable_context: dict[str, Any],
        kb_chunks: list[dict[str, Any]],
    ) -> str:
        compiled_prompt = stable_context.get("compiled_prompt")
        if isinstance(compiled_prompt, dict):
            user_prompt = str(compiled_prompt.get("user_prompt") or "").strip()
            if user_prompt:
                return user_prompt
        # Keep the final low-level question clean. Raw KB snippets and stable
        # context stay in controller/runtime state instead of being pasted into
        # the user-visible prompt body, which previously produced noisy live
        # ChatGPT threads like "附加上下文 ---depth: standard".
        return str(question or "")

    def _build_sync_delivery(self, result: dict[str, Any]) -> dict[str, Any]:
        route = str(result.get("selected_route") or "")
        answer = str(result.get("answer") or "")
        conversation_url = str(result.get("conversation_url") or "").strip() or None
        route_result = dict(result.get("route_result") or {})
        blockers = []
        if route == "clarify":
            blockers.extend(list(route_result.get("followups") or []))
        decisions = [
            {
                "type": "route",
                "value": route,
                "reason": str(result.get("route_rationale") or ""),
            }
        ]
        return {
            "status": "completed",
            "summary": answer[:240] if answer else f"Completed route {route}.",
            "answer": answer,
            "blockers": blockers,
            "decisions": decisions,
            "artifacts": [],
            "conversation_url": conversation_url,
            "route_result": route_result,
        }

    def _build_sync_next_action(self, result: dict[str, Any]) -> dict[str, Any]:
        route = str(result.get("selected_route") or "")
        route_result = dict(result.get("route_result") or {})
        if route == "clarify":
            return {
                "type": "await_user_clarification",
                "status": "blocking",
                "questions": list(route_result.get("followups") or []),
            }
        return {
            "type": "await_user_followup",
            "status": "optional",
            "reason": "The current delivery is complete; continue only if the user wants the next step executed.",
        }

    def _write_controller_snapshot(self, conn: Any, *, run_id: str) -> None:
        snapshot = store.snapshot_run(conn, run_id=run_id)
        if snapshot is None:
            return
        write_run_json(
            self._cfg.artifacts_dir,
            run_id=run_id,
            name="controller_snapshot.json",
            payload=snapshot,
        )
