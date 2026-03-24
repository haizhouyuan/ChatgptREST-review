"""Consult & Recall API — parallel multi-model consultation and KB retrieval.

Endpoints:
  POST /v1/advisor/consult               — submit parallel consultation
  GET  /v1/advisor/consult/{id}          — get consultation results
  POST /v1/advisor/recall                — search KB knowledge (KB + EvoMap)
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from chatgptrest.advisor.scenario_packs import (
    apply_scenario_pack,
    resolve_scenario_pack,
    summarize_scenario_pack,
)
from chatgptrest.advisor.task_intake import (
    TaskIntakeValidationError,
    build_task_intake_spec,
    summarize_task_intake,
)
from chatgptrest.core.openmind_paths import (
    resolve_consult_kb_db_path,
    resolve_evomap_knowledge_read_db_path,
)
from chatgptrest.core.config import AppConfig
from chatgptrest.core.db import connect
from chatgptrest.core.file_path_inputs import coerce_file_path_input
from chatgptrest.core.idempotency import IdempotencyCollision
from chatgptrest.core.job_store import ConversationBusy, create_job, get_job
from chatgptrest.core.state_machine import JobStatus
from chatgptrest.evomap.knowledge.planning_runtime_pack_search import (
    PLANNING_REVIEW_SCOPE,
    search_planning_runtime_pack,
)
from chatgptrest.evomap.knowledge.telemetry import TelemetryRecorder

_LOG = logging.getLogger(__name__)

# ── Model → Job Kind mapping ─────────────────────────────────────

_MODEL_MAP: dict[str, dict[str, Any]] = {
    "chatgpt_pro": {
        "kind": "chatgpt_web.ask",
        "preset": "pro_extended",
        "provider": "chatgpt_web",
    },
    "gemini_deepthink": {
        "kind": "gemini_web.ask",
        "preset": "deep_think",
        "provider": "gemini_web",
    },
    "chatgpt_dr": {
        "kind": "chatgpt_web.ask",
        "preset": "auto",
        "provider": "chatgpt_web",
        "deep_research": True,
    },
    "gemini_dr": {
        "kind": "gemini_web.ask",
        "preset": "pro",
        "provider": "gemini_web",
        "deep_research": True,
    },
    "qwen": {
        "kind": "qwen_web.ask",
        "preset": "deep_thinking",
        "provider": "qwen_web",
    },
}

DEFAULT_MODELS = ["chatgpt_pro", "gemini_deepthink"]
DEEP_RESEARCH_MODELS = ["chatgpt_dr", "gemini_dr"]
ALL_MODELS = ["chatgpt_pro", "gemini_deepthink", "chatgpt_dr", "gemini_dr", "qwen"]

# mode → model list shortcut
_MODE_PRESETS: dict[str, list[str]] = {
    "default": DEFAULT_MODELS,
    "deep_research": DEEP_RESEARCH_MODELS,
    "all": ALL_MODELS,
    "thinking": ["chatgpt_pro", "gemini_deepthink", "qwen"],
}

# ── In-memory consultation store ─────────────────────────────────

_MAX_CONSULTATIONS = 2000
_consultations: dict[str, dict[str, Any]] = {}
_consultations_lock = threading.Lock()

# Same-provider cooldown (seconds) to avoid rate-limit collisions
_PROVIDER_STAGGER_SECONDS: dict[str, float] = {
    "chatgpt_web": 62.0,  # ChatGPT 61s rate limit
    "gemini_web": 5.0,
    "qwen_web": 5.0,
}


def _store_consultation(consultation_id: str, data: dict[str, Any]) -> None:
    with _consultations_lock:
        _consultations[consultation_id] = data
        if len(_consultations) > _MAX_CONSULTATIONS:
            oldest = next(iter(_consultations))
            del _consultations[oldest]


def _get_consultation(consultation_id: str) -> dict[str, Any] | None:
    with _consultations_lock:
        return _consultations.get(consultation_id)


# ── KB Search helper ─────────────────────────────────────────────

def _kb_search(query: str, *, top_k: int = 5, db_path: Path | None = None) -> list[dict[str, Any]]:
    """Search KB using FTS5. Returns list of {id, title, snippet, score}."""
    if not query.strip():
        return []

    # Try importing KBRetriever
    try:
        from chatgptrest.kb.retrieval import KBRetriever
    except ImportError:
        _LOG.debug("kb.retrieval not available, skipping KB search")
        return []

    # Find KB database path
    kb_db = _find_kb_db(db_path)
    if kb_db is None:
        return []

    try:
        retriever = KBRetriever(db_path=str(kb_db))
        results = retriever.search(query, limit=top_k)
        return [
            {
                "artifact_id": r.artifact_id,
                "title": r.title,
                "snippet": r.snippet,
                "score": r.score,
                "content_type": getattr(r, "content_type", ""),
                "quality_score": getattr(r, "quality_score", 0.0),
                "source": "kb",
            }
            for r in results
        ]
    except Exception as exc:
        _LOG.warning("KB search failed: %s", exc)
        return []


# ── EvoMap Knowledge Search helper ───────────────────────────────

def _find_evomap_knowledge_db() -> str | None:
    """Locate a readable EvoMap knowledge database for consult recall."""
    return resolve_evomap_knowledge_read_db_path()


def _evomap_search(query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
    """Search EvoMap knowledge atoms. Returns list of {atom_id, title, snippet, score, ...}.

    Calls the existing retrieval.retrieve() pipeline:
    FTS5 → pre-filter → quality gate → time decay → diversify
    """
    if not query.strip():
        return []

    db_path = _find_evomap_knowledge_db()
    if db_path is None:
        _LOG.debug("EvoMap knowledge DB not found, skipping EvoMap search")
        return []

    try:
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.retrieval import (
            RetrievalSurface,
            runtime_retrieval_config,
            retrieve,
        )

        db = KnowledgeDB(db_path=db_path)
        db.connect()

        config = runtime_retrieval_config(
            surface=RetrievalSurface.USER_HOT_PATH,
            result_limit=top_k,
            min_quality=0.15,
        )

        scored_atoms = retrieve(db, query, config=config)

        results: list[dict[str, Any]] = []
        for sa in scored_atoms:
            atom = sa.atom
            # Skip atoms with low groundedness if scored
            groundedness = getattr(atom, "groundedness", None)
            if groundedness is not None and groundedness < 0.5:
                continue

            results.append({
                "artifact_id": atom.atom_id,
                "title": atom.question[:120] if atom.question else "",
                "snippet": atom.answer[:500] if atom.answer else "",
                "score": round(sa.final_score, 4),
                "content_type": atom.atom_type or "evomap_atom",
                "quality_score": round(sa.quality, 3),
                "source": (
                    "evomap_staged_fallback"
                    if atom.promotion_status == "staged"
                    else "evomap"
                ),
                "evomap_meta": {
                    "relevance": round(sa.relevance, 3),
                    "time_decay": round(sa.time_decay, 3),
                    "stability": atom.stability,
                    "status": atom.status,
                    "promotion_status": atom.promotion_status,
                    "groundedness": groundedness,
                },
            })

        return results
    except Exception as exc:
        _LOG.warning("EvoMap search failed: %s", exc)
        return []


def _record_recall_telemetry(
    query: str,
    kb_hits: list[dict[str, Any]],
    evomap_hits: list[dict[str, Any]],
    elapsed_ms: int = 0,
    session_id: str = "",
    trace_id: str = "",
    run_id: str = "",
    job_id: str = "",
    task_ref: str = "",
    logical_task_id: str = "",
) -> dict[str, Any] | None:
    """Record recall telemetry for mixed KB/EvoMap hits via shared schema."""
    try:
        db_path = _find_evomap_knowledge_db()
        if db_path is None:
            return None

        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.telemetry_contract import compact_identity, extract_identity_fields

        db = KnowledgeDB(db_path=db_path)
        db.connect()
        recorder = TelemetryRecorder(db)
        recorder.init_schema()
        identity = extract_identity_fields(
            {
                "trace_id": trace_id,
                "run_id": run_id,
                "job_id": job_id,
                "task_ref": task_ref,
                "logical_task_id": logical_task_id,
            },
            event_type="advisor.recall",
            trace_id=trace_id,
            session_id=session_id,
            source="advisor_recall",
        )
        all_hits = evomap_hits + kb_hits
        event = recorder.record_search_results(
            query=query,
            hits=all_hits,
            elapsed_ms=elapsed_ms,
            session_id=session_id,
            trace_id=str(identity.get("trace_id") or ""),
            run_id=str(identity.get("run_id") or ""),
            job_id=str(identity.get("job_id") or ""),
            task_ref=str(identity.get("task_ref") or ""),
            logical_task_id=str(identity.get("logical_task_id") or ""),
            identity_confidence=str(identity.get("identity_confidence") or ""),
            domain="recall",
            intent="advisor_recall",
        )
        return {
            "query_id": event.query_id,
            "identity": compact_identity({key: identity.get(key) for key in (
                "trace_id",
                "run_id",
                "job_id",
                "task_ref",
                "logical_task_id",
                "identity_confidence",
                "session_id",
            )}),
        }
    except Exception as exc:
        _LOG.debug("Recall telemetry recording failed (non-fatal): %s", exc)
        return None


def _find_kb_db(db_path: Path | None = None) -> Path | None:
    """Locate a readable KB database file for consult recall."""
    return resolve_consult_kb_db_path(db_path=db_path)


def _build_kb_context(hits: list[dict[str, Any]], *, max_chars: int = 2000) -> str:
    """Build a context string from KB search results."""
    if not hits:
        return ""

    parts: list[str] = []
    total_chars = 0
    for hit in hits:
        title = hit.get("title", "")
        snippet = hit.get("snippet", "")
        entry = f"[{title}] {snippet}" if title else snippet
        if total_chars + len(entry) > max_chars:
            break
        parts.append(entry)
        total_chars += len(entry)

    if not parts:
        return ""

    return "相关知识库参考：\n" + "\n---\n".join(parts)


def _build_planning_context(hits: list[dict[str, Any]], *, max_chars: int = 2000) -> str:
    """Build a context string from explicit planning runtime-pack hits."""
    if not hits:
        return ""

    parts: list[str] = []
    total_chars = 0
    for hit in hits:
        title = hit.get("title", "")
        snippet = hit.get("snippet", "")
        meta = hit.get("planning_pack_meta") if isinstance(hit.get("planning_pack_meta"), dict) else {}
        review_domain = str(meta.get("review_domain") or "")
        source_bucket = str(meta.get("source_bucket") or "")
        prefix = f"[{title}]"
        suffix = "/".join(value for value in [review_domain, source_bucket] if value)
        if suffix:
            prefix += f" ({suffix})"
        entry = f"{prefix} {snippet}".strip()
        if total_chars + len(entry) > max_chars:
            break
        parts.append(entry)
        total_chars += len(entry)

    if not parts:
        return ""

    return "Planning reviewed slice参考：\n" + "\n---\n".join(parts)


def _normalize_source_scope(raw_scope: Any, *, planning_mode: bool = False) -> list[str]:
    if isinstance(raw_scope, str):
        scope = [raw_scope.strip()] if raw_scope.strip() else []
    elif isinstance(raw_scope, list):
        scope = [str(item).strip() for item in raw_scope if str(item).strip()]
    else:
        scope = []
    if planning_mode and PLANNING_REVIEW_SCOPE not in scope:
        scope.append(PLANNING_REVIEW_SCOPE)
    return scope


def _select_consult_models(
    *,
    explicit_models: Any,
    mode: str,
    task_intake_summary: dict[str, Any] | None,
    scenario_pack_summary: dict[str, Any] | None,
) -> list[str]:
    if mode and mode in _MODE_PRESETS:
        return list(_MODE_PRESETS[mode])
    if explicit_models and isinstance(explicit_models, list):
        return list(explicit_models)

    scenario = str((task_intake_summary or {}).get("scenario") or "").strip().lower()
    profile = str((scenario_pack_summary or {}).get("profile") or "").strip().lower()
    route_hint = str((scenario_pack_summary or {}).get("route_hint") or "").strip().lower()

    if profile in {"topic_research", "comparative_research"}:
        return list(DEEP_RESEARCH_MODELS)
    if profile == "research_report":
        return list(DEFAULT_MODELS)
    if scenario == "research" or route_hint == "deep_research":
        return list(DEEP_RESEARCH_MODELS)
    return list(DEFAULT_MODELS)


# ── Router factory ────────────────────────────────────────────────

def make_consult_router(cfg: AppConfig) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/advisor/consult")
    async def advisor_consult(request: Request, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Submit parallel multi-model consultation."""
        question = str(body.get("question") or "").strip()
        if not question:
            raise HTTPException(status_code=400, detail={"error": "question is required"})

        models = body.get("models") or None
        mode = str(body.get("mode") or "").strip().lower()
        raw_task_intake = body.get("task_intake")
        context_payload = dict(body.get("context") or {}) if isinstance(body.get("context"), dict) else {}

        auto_context = bool(body.get("auto_context", True))
        auto_context_top_k = int(body.get("auto_context_top_k") or 3)
        persist_answer = bool(body.get("persist_answer", False))
        source_scope = _normalize_source_scope(
            body.get("source_scope"),
            planning_mode=bool(body.get("planning_mode", False)),
        )
        kb_scope_enabled = not source_scope or "kb" in source_scope
        planning_scope_enabled = PLANNING_REVIEW_SCOPE in source_scope

        # File attachments — forwarded to each model's input_obj
        raw_file_paths = body.get("file_paths")
        file_paths = coerce_file_path_input(raw_file_paths)
        timeout_seconds = int(body.get("timeout_seconds") or 600)
        consultation_id = f"cons-{uuid.uuid4().hex[:16]}"

        try:
            task_intake = build_task_intake_spec(
                ingress_lane="other",
                default_source="rest",
                raw_source=str(body.get("source") or "rest"),
                raw_task_intake=raw_task_intake if isinstance(raw_task_intake, dict) else None,
                question=question,
                goal_hint=str(body.get("goal_hint") or "").strip(),
                intent_hint=str(body.get("intent_hint") or "").strip(),
                trace_id=str(body.get("trace_id") or "").strip(),
                session_id=str(body.get("session_id") or "").strip(),
                user_id=str(body.get("user_id") or "").strip(),
                account_id=str(body.get("account_id") or "").strip(),
                thread_id=str(body.get("thread_id") or "").strip(),
                agent_id=str(body.get("agent_id") or "").strip(),
                role_id=str(body.get("role_id") or "").strip(),
                context=context_payload,
                attachments=file_paths,
                client_name=str(request.headers.get("x-client-name") or "").strip(),
            )
        except TaskIntakeValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "unsupported_task_intake_spec_version",
                    "expected": "task-intake-v2",
                    "message": str(exc),
                },
            ) from exc

        scenario_pack = resolve_scenario_pack(
            task_intake,
            goal_hint=str(body.get("goal_hint") or "").strip(),
            context=context_payload,
        )
        if scenario_pack is not None:
            task_intake = apply_scenario_pack(task_intake, scenario_pack)

        task_intake_summary = summarize_task_intake(task_intake)
        scenario_pack_summary = summarize_scenario_pack(scenario_pack)
        models = _select_consult_models(
            explicit_models=models,
            mode=mode,
            task_intake_summary=task_intake_summary,
            scenario_pack_summary=scenario_pack_summary,
        )

        # Validate models
        invalid = [m for m in models if m not in _MODEL_MAP]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_models",
                    "invalid": invalid,
                    "available": list(_MODEL_MAP.keys()),
                },
            )

        # KB context enrichment
        kb_context = ""
        kb_hits: list[dict[str, Any]] = []
        if auto_context and kb_scope_enabled:
            kb_hits = _kb_search(question, top_k=auto_context_top_k, db_path=Path(cfg.db_path))
            kb_context = _build_kb_context(kb_hits)
        planning_hits: list[dict[str, Any]] = []
        planning_context = ""
        if planning_scope_enabled:
            planning_hits = search_planning_runtime_pack(question, top_k=auto_context_top_k)
            planning_context = _build_planning_context(planning_hits)

        # Build enriched question
        enriched_question = question
        context_blocks = [block for block in [kb_context, planning_context] if block]
        if context_blocks:
            combined_context = "\n\n---\n\n".join(context_blocks)
            enriched_question = f"{combined_context}\n\n---\n\n用户问题：{question}"

        # Submit jobs for each model
        jobs: list[dict[str, Any]] = []
        request_id = (request.headers.get("x-request-id") or "").strip() or f"consult-{consultation_id}"
        client_name = (request.headers.get("x-client-name") or "").strip() or "advisor_consult"

        # Compute not_before offsets to stagger same-provider jobs
        provider_next_at: dict[str, float] = {}
        now_ts = time.time()

        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                for i, model_key in enumerate(models):
                    model_cfg = _MODEL_MAP[model_key]
                    kind = model_cfg["kind"]
                    provider = model_cfg["provider"]
                    idem = f"consult-{consultation_id}-{model_key}"

                    # Stagger same-provider jobs to avoid rate limits
                    not_before_ts = 0.0
                    stagger = _PROVIDER_STAGGER_SECONDS.get(provider, 0.0)
                    if provider in provider_next_at and stagger > 0:
                        not_before_ts = provider_next_at[provider]
                    provider_next_at[provider] = max(
                        provider_next_at.get(provider, now_ts), now_ts
                    ) + stagger

                    input_obj: dict[str, Any] = {"question": enriched_question}
                    if file_paths:
                        input_obj["file_paths"] = list(file_paths)
                    params_obj: dict[str, Any] = {
                        "preset": model_cfg["preset"],
                        "timeout_seconds": timeout_seconds,
                        "max_wait_seconds": timeout_seconds * 3,
                        "answer_format": "markdown",
                    }
                    if model_cfg.get("deep_research"):
                        params_obj["deep_research"] = True
                    if not_before_ts > 0:
                        params_obj["not_before"] = not_before_ts

                    job = create_job(
                        conn,
                        artifacts_dir=cfg.artifacts_dir,
                        idempotency_key=idem,
                        kind=kind,
                        input=input_obj,
                        params=params_obj,
                        max_attempts=max(1, int(cfg.max_attempts)),
                        parent_job_id=None,
                        client={"name": client_name, "consult_model": model_key},
                        requested_by=request_id,
                        allow_queue=False,
                        enforce_conversation_single_flight=False,
                    )

                    staggered = not_before_ts > 0
                    jobs.append({
                        "model": model_key,
                        "provider": provider,
                        "kind": kind,
                        "job_id": str(job.job_id),
                        "status": str(job.status.value),
                        "preset": model_cfg["preset"],
                        "deep_research": bool(model_cfg.get("deep_research")),
                        "staggered": staggered,
                        "not_before": not_before_ts if staggered else None,
                    })
                conn.commit()
            except ConversationBusy as exc:
                conn.rollback()
                # Some jobs may have been created — report partial state
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "conversation_busy",
                        "partial_jobs": jobs,
                        "active_job_id": exc.active_job_id,
                        "retry_after_seconds": max(5, int(cfg.min_prompt_interval_seconds or 30)),
                    },
                ) from exc
            except IdempotencyCollision as exc:
                conn.rollback()
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "idempotency_collision",
                        "partial_jobs": jobs,
                        "reason": str(exc),
                    },
                ) from exc

        # Store consultation
        consultation = {
            "consultation_id": consultation_id,
            "question": question,
            "enriched_question": enriched_question if kb_context else None,
            "models": models,
            "task_intake": task_intake_summary,
            "scenario_pack": scenario_pack_summary,
            "jobs": jobs,
            "auto_context": auto_context,
            "kb_hits_count": len(kb_hits),
            "planning_hits_count": len(planning_hits),
            "source_scope": source_scope,
            "persist_answer": persist_answer,
            "created_at": time.time(),
            "status": "submitted",
        }
        _store_consultation(consultation_id, consultation)

        _LOG.info(
            "consult submitted consultation_id=%s models=%s jobs=%d kb_hits=%d",
            consultation_id,
            models,
            len(jobs),
            len(kb_hits),
        )

        return {
            "ok": True,
            "consultation_id": consultation_id,
            "status": "submitted",
            "models": models,
            "task_intake": task_intake_summary,
            "scenario_pack": scenario_pack_summary,
            "jobs": jobs,
            "kb_context_injected": bool(kb_context),
            "kb_hits_count": len(kb_hits),
            "planning_context_injected": bool(planning_context),
            "planning_hits_count": len(planning_hits),
            "source_scope": source_scope,
            "action_hint": "use GET /v1/advisor/consult/{consultation_id} or chatgptrest_result per job_id",
        }

    @router.get("/v1/advisor/consult/{consultation_id}")
    async def advisor_consult_result(consultation_id: str) -> dict[str, Any]:
        """Get consultation status and results."""
        consultation = _get_consultation(consultation_id)
        if consultation is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "consultation_not_found", "consultation_id": consultation_id},
            )

        # Refresh job statuses
        jobs = list(consultation.get("jobs") or [])
        all_completed = True
        any_error = False

        with connect(cfg.db_path) as conn:
            for job_info in jobs:
                jid = str(job_info.get("job_id") or "")
                if not jid:
                    continue
                child = get_job(conn, job_id=jid)
                if child is not None:
                    status = str(child.status.value)
                    job_info["status"] = status
                    job_info["answer_path"] = str(getattr(child, "answer_path", "") or "").strip() or None
                    if status != "completed":
                        all_completed = False
                    if status in ("error", "canceled", "blocked"):
                        any_error = True
                else:
                    all_completed = False

        # Read answers for completed jobs
        answers: dict[str, str | None] = {}
        for job_info in jobs:
            if job_info.get("status") == "completed" and job_info.get("answer_path"):
                try:
                    p = Path(str(job_info["answer_path"]))
                    if p.exists():
                        text = p.read_text(encoding="utf-8", errors="replace")
                        answers[job_info["model"]] = text[:24000]
                    else:
                        answers[job_info["model"]] = None
                except Exception:
                    answers[job_info["model"]] = None
            elif job_info.get("status") == "completed":
                answers[job_info["model"]] = None

        overall_status = "submitted"
        if all_completed:
            overall_status = "completed"
        elif any_error:
            overall_status = "partial"

        consultation["status"] = overall_status
        consultation["jobs"] = jobs

        out: dict[str, Any] = {
            "ok": True,
            "consultation_id": consultation_id,
            "status": overall_status,
            "question": consultation.get("question"),
            "models": consultation.get("models"),
            "jobs": jobs,
            "answers": answers if answers else None,
            "all_completed": all_completed,
            "created_at": consultation.get("created_at"),
            "action_hint": "answers_ready" if all_completed else "poll_later",
        }

        if all_completed and len(answers) >= 2:
            out["suggested_next"] = (
                "All models returned answers. Use chatgptrest_result(job_id) to read "
                "each answer in full, or synthesize them directly."
            )

        return out

    @router.post("/v1/advisor/recall")
    async def advisor_recall(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Search KB + EvoMap knowledge for accumulated knowledge."""
        query = str(body.get("query") or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail={"error": "query is required"})

        top_k = int(body.get("top_k") or 5)
        top_k = max(1, min(50, top_k))
        source_scope = _normalize_source_scope(
            body.get("source_scope"),
            planning_mode=bool(body.get("planning_mode", False)),
        )
        kb_scope_enabled = not source_scope or "kb" in source_scope
        evomap_scope_enabled = not source_scope or "evomap" in source_scope
        planning_scope_enabled = PLANNING_REVIEW_SCOPE in source_scope

        t0 = time.time()

        # Search both KB and EvoMap in parallel
        kb_hits = _kb_search(query, top_k=top_k, db_path=Path(cfg.db_path)) if kb_scope_enabled else []
        evomap_hits = _evomap_search(query, top_k=top_k) if evomap_scope_enabled else []
        planning_hits = (
            search_planning_runtime_pack(query, top_k=top_k)
            if planning_scope_enabled
            else []
        )

        # Merge and sort by score (descending), limit to top_k
        all_hits = kb_hits + evomap_hits + planning_hits
        all_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
        hits = all_hits[:top_k]

        elapsed_ms = int((time.time() - t0) * 1000)

        # Record telemetry (P3 feedback loop) — fire and forget
        try:
            telemetry = _record_recall_telemetry(
                query,
                kb_hits,
                evomap_hits + planning_hits,
                elapsed_ms=elapsed_ms,
                session_id=str(body.get("session_id") or body.get("session_key") or "").strip(),
                trace_id=str(body.get("trace_id") or "").strip(),
                run_id=str(body.get("run_id") or "").strip(),
                job_id=str(body.get("job_id") or "").strip(),
                task_ref=str(body.get("task_ref") or body.get("task_id") or "").strip(),
                logical_task_id=str(body.get("logical_task_id") or "").strip(),
            )
        except Exception:
            telemetry = None

        query_id = str((telemetry or {}).get("query_id") or "") or None
        query_identity = (telemetry or {}).get("identity") if isinstance(telemetry, dict) else None

        return {
            "ok": True,
            "query": query,
            "query_id": query_id,
            "query_identity": query_identity,
            "hits": hits,
            "total_hits": len(hits),
            "sources": {
                "kb": len(kb_hits),
                "evomap": len(evomap_hits),
                "planning_review_pack": len(planning_hits),
            },
            "source_scope": source_scope,
            "elapsed_ms": elapsed_ms,
        }

    @router.post("/v1/advisor/recall/feedback")
    async def advisor_recall_feedback(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        query_id = str(body.get("query_id") or "").strip()
        if not query_id:
            raise HTTPException(status_code=400, detail={"error": "query_id is required"})

        feedback_type = str(body.get("feedback_type") or "").strip().lower()
        allowed_feedback = {"accepted", "corrected", "followup", "abstained"}
        if feedback_type not in allowed_feedback:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_feedback_type", "allowed": sorted(allowed_feedback)},
            )

        correction_type = str(body.get("correction_type") or "").strip().lower()
        atom_ids = [
            str(item).strip()
            for item in (body.get("atom_ids") or [])
            if str(item).strip()
        ]

        db_path = _find_evomap_knowledge_db()
        if db_path is None:
            raise HTTPException(status_code=503, detail={"error": "evomap_knowledge_db_unavailable"})

        from chatgptrest.evomap.knowledge.db import KnowledgeDB

        db = KnowledgeDB(db_path=db_path)
        conn = db.connect()
        recorder = TelemetryRecorder(db)
        recorder.init_schema()

        exists = conn.execute(
            "SELECT 1 FROM query_events WHERE query_id = ? LIMIT 1",
            (query_id,),
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail={"error": "query_id_not_found", "query_id": query_id})

        if atom_ids:
            recorder.mark_atoms_used(query_id, atom_ids)
        recorder.record_feedback(
            query_id=query_id,
            feedback_type=feedback_type,
            correction_type=correction_type,
            atom_ids=atom_ids,
        )

        return {
            "ok": True,
            "query_id": query_id,
            "feedback_type": feedback_type,
            "correction_type": correction_type,
            "marked_atom_ids": atom_ids,
        }

    return router
