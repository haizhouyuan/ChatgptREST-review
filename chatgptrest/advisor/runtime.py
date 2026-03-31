from __future__ import annotations

import atexit
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from chatgptrest.core.openmind_paths import (
    resolve_evomap_knowledge_runtime_db_path,
    resolve_openmind_event_bus_db_path,
    resolve_openmind_kb_search_db_path,
    resolve_openmind_kb_vector_db_path,
)
from chatgptrest.evomap.paths import resolve_evomap_db_path

logger = logging.getLogger(__name__)


def _env_flag_enabled(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _openmind_kb_search_db_path() -> str:
    return resolve_openmind_kb_search_db_path()


def _openmind_event_bus_db_path() -> str:
    return resolve_openmind_event_bus_db_path()


def _init_scorecard_store(evo_db: str):
    try:
        from chatgptrest.evomap.team_scorecard import TeamScorecardStore

        store = TeamScorecardStore(db_path=evo_db)
        logger.info("TeamScorecardStore initialized (%s)", evo_db)
        return store
    except Exception as exc:
        logger.warning("TeamScorecardStore init failed: %s", exc)
        return None


def _init_team_policy(evo_db: str):
    try:
        from chatgptrest.evomap.team_scorecard import TeamScorecardStore
        from chatgptrest.kernel.team_policy import TeamPolicy

        store = TeamScorecardStore(db_path=evo_db)
        policy = TeamPolicy(scorecard_store=store)
        logger.info("TeamPolicy initialized")
        return policy
    except Exception as exc:
        logger.warning("TeamPolicy init failed: %s", exc)
        return None


def _init_team_control_plane(evo_db: str):
    try:
        from chatgptrest.kernel.team_control_plane import TeamControlPlane

        plane = TeamControlPlane(db_path=evo_db)
        logger.info("TeamControlPlane initialized (%s)", evo_db)
        return plane
    except Exception as exc:
        logger.warning("TeamControlPlane init failed: %s", exc)
        return None


@dataclass
class AdvisorRuntime:
    api: Any
    feishu: Any
    llm: Any
    outbox: Any
    observer: Any
    kb_registry: Any
    graph_app: Any
    advisor_fn: Any
    kb_hub: Any
    memory: Any
    event_bus: Any
    cc_executor: Any
    cc_native: Any
    evomap_knowledge_db: Any
    policy_engine: Any
    circuit_breaker: Any
    kb_scorer: Any
    gate_tuner: Any
    routing_fabric: Any
    writeback_service: Any
    team_control_plane: Any = None
    mcp_bridge: Any = None
    model_router: Any = None
    skill_registry: Any = None
    bundle_resolver: Any = None
    capability_gap_recorder: Any = None
    quarantine_gate: Any = None
    cleanup_callbacks: list[Callable[[], None]] = field(default_factory=list, repr=False)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    @property
    def llm_connector(self) -> Any:
        return self.llm

    @property
    def evomap_observer(self) -> Any:
        return self.observer

    def close(self) -> None:
        callbacks = list(reversed(self.cleanup_callbacks))
        self.cleanup_callbacks.clear()
        for callback in callbacks:
            try:
                callback()
            except Exception as exc:
                logger.warning("Advisor runtime cleanup failed: %s", exc)
        closeables = (
            ("event_bus", self.event_bus),
            ("outbox", self.outbox),
            ("kb_hub", self.kb_hub),
            ("memory", self.memory),
            ("kb_registry", self.kb_registry),
            ("observer", self.observer),
            ("evomap_knowledge_db", self.evomap_knowledge_db),
            ("capability_gap_recorder", getattr(self, "capability_gap_recorder", None)),
            ("team_control_plane", getattr(self, "team_control_plane", None)),
        )
        seen: set[int] = set()
        for name, resource in closeables:
            if resource is None:
                continue
            marker = id(resource)
            if marker in seen:
                continue
            seen.add(marker)
            close_fn = getattr(resource, "close", None)
            if not callable(close_fn):
                continue
            try:
                close_fn()
            except Exception as exc:
                logger.warning("Advisor runtime close(%s) failed: %s", name, exc)


_RUNTIME: AdvisorRuntime | None = None
_INIT_LOCK = threading.Lock()


def is_advisor_runtime_ready() -> bool:
    with _INIT_LOCK:
        return _RUNTIME is not None


def get_advisor_runtime_if_ready() -> AdvisorRuntime | None:
    with _INIT_LOCK:
        return _RUNTIME


def _age_old_atoms(knowledge_db: Any) -> None:
    """Mark old atoms as SUPERSEDED based on TTL rules.

    Rules:
      - Candidate atoms (unscored) older than 90 days → superseded
      - Scored atoms not accessed in 180 days → needs_revalidate
    """
    import time as _t

    conn = knowledge_db.connect()
    now = _t.time()
    candidate_cutoff = now - (90 * 86400)  # 90 days
    scored_cutoff = now - (180 * 86400)    # 180 days

    # Mark old unscored candidates as superseded
    aged = conn.execute(
        "UPDATE atoms SET stability = 'superseded' "
        "WHERE status = 'candidate' AND valid_from > 0 AND valid_from < ? "
        "AND stability != 'superseded'",
        (candidate_cutoff,),
    ).rowcount

    # Mark very old scored atoms as needs_revalidate
    revalidate = conn.execute(
        "UPDATE atoms SET status = 'needs_revalidate' "
        "WHERE status = 'scored' AND valid_from > 0 AND valid_from < ? "
        "AND status != 'needs_revalidate'",
        (scored_cutoff,),
    ).rowcount

    conn.commit()
    if aged or revalidate:
        logger.info(
            "EvoMap atom aging: %d superseded, %d needs_revalidate",
            aged, revalidate,
        )


def _emit_llm_runtime_signal(*, observer: Any, event_bus: Any, signal_type: str, data: dict[str, Any]) -> None:
    trace_id = str(data.get("trace_id") or "")
    payload = dict(data)
    if "trace_id" in payload:
        payload.pop("trace_id", None)
    if event_bus is not None:
        try:
            from chatgptrest.kernel.event_bus import TraceEvent

            event_bus.emit(
                TraceEvent.create(
                    source="llm_connector",
                    event_type=signal_type,
                    trace_id=trace_id,
                    data=payload,
                )
            )
            return
        except Exception as exc:
            logger.debug("runtime LLM EventBus emit failed: %s", exc)

    if observer is None:
        return
    try:
        observer.record_event(
            trace_id=trace_id,
            signal_type=signal_type,
            source="llm_connector",
            domain="llm",
            data=payload,
        )
    except Exception:
        logger.debug("runtime LLM observer emit failed", exc_info=True)


def _invoke_graph_app(*, app: Any, runtime: AdvisorRuntime, payload: dict[str, Any], thread_id: str) -> dict[str, Any]:
    from chatgptrest.advisor.graph import bind_runtime_services

    config = {"configurable": {"thread_id": thread_id}}
    with bind_runtime_services(runtime):
        return app.invoke(payload, config=config)


def get_advisor_runtime() -> AdvisorRuntime:
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME

    with _INIT_LOCK:
        if _RUNTIME is not None:
            return _RUNTIME

        from chatgptrest.advisor.advisor_api import AdvisorAPI
        from chatgptrest.advisor.feishu_handler import FeishuHandler
        from chatgptrest.advisor.graph import build_advisor_graph, configure_services
        from chatgptrest.evomap.observer import EvoMapObserver
        from chatgptrest.kb.hub import KBHub
        from chatgptrest.kb.registry import ArtifactRegistry
        from chatgptrest.kb.writeback_service import KBWritebackService
        from chatgptrest.kernel.cc_executor import CcExecutor
        from chatgptrest.kernel.cc_native import CcNativeExecutor
        from chatgptrest.kernel.effects_outbox import EffectsOutbox
        from chatgptrest.kernel.llm_connector import LLMConfig, LLMConnector
        from chatgptrest.kernel.memory_manager import MemoryManager
        from chatgptrest.kernel.mcp_llm_bridge import McpLlmBridge
        from chatgptrest.kernel.policy_engine import PolicyEngine
        from chatgptrest.kernel.routing import RoutingFabric

        cleanup_callbacks: list[Callable[[], None]] = []
        llm_config = LLMConfig(
            throttle_interval=0.1,
            timeout=60.0,
        )
        qwen_key = os.environ.get("QWEN_API_KEY", "")

        evo_db = resolve_evomap_db_path()
        observer = EvoMapObserver(db_path=evo_db)

        if qwen_key:
            llm = LLMConnector(
                llm_config,
                signal_emitter=lambda signal_type, data: _emit_llm_runtime_signal(
                    observer=observer,
                    event_bus=event_bus,
                    signal_type=signal_type,
                    data=data,
                ),
            )
            logger.info("LLM connector using Coding Plan API + RoutingFabric (QWEN_API_KEY set)")
        else:
            logger.warning(
                "QWEN_API_KEY not set — using KB-only stub. "
                "Set QWEN_API_KEY for real LLM responses."
            )

            def _stub_llm(prompt: str, system_msg: str = "") -> str:
                if "审核" in prompt or "review" in prompt.lower():
                    return "审核通过。内容结构完整，逻辑清晰。\n[通过]"
                if "检查" in prompt or "敏感" in prompt:
                    return "无敏感信息"
                if "分析" in prompt or "评估" in prompt:
                    return (
                        f"[LLM offline — KB-only模式]\n"
                        f"收到请求: {prompt[:100]}...\n"
                        f"建议: 请配置 QWEN_API_KEY 获取完整分析。"
                    )
                return (
                    f"[LLM offline — KB-only模式]\n"
                    f"核心问题: {prompt[:60]}...\n"
                    f"约束条件: 待明确\n"
                    f"利益相关者: 待明确\n"
                    f"需求清晰度: 中"
                )

            llm = LLMConnector.mock(_stub_llm)

        db_path = os.environ.get(
            "OPENMIND_DB_PATH",
            os.path.expanduser("~/.openmind/effects.db"),
        )
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        outbox = EffectsOutbox(db_path=db_path)

        kb_db = os.environ.get(
            "OPENMIND_KB_DB",
            os.path.expanduser("~/.openmind/kb_registry.db"),
        )
        kb_reg = ArtifactRegistry(db_path=kb_db)

        kb_search_db = _openmind_kb_search_db_path()
        kb_vec_db = resolve_openmind_kb_vector_db_path()
        kb_hub = KBHub(db_path=kb_search_db, vec_db_path=kb_vec_db)
        logger.info("KBHub initialized (FTS=%s, vec=%s, docs=%s)", kb_search_db, kb_vec_db, kb_hub.count())

        memory_db = os.environ.get(
            "OPENMIND_MEMORY_DB",
            os.path.expanduser("~/.openmind/memory.db"),
        )
        memory = MemoryManager(db_path=memory_db)
        logger.info("MemoryManager initialized (%s), records=%d", memory_db, memory.count_total())

        from chatgptrest.kernel.event_bus import EventBus

        event_bus_db = _openmind_event_bus_db_path()
        event_bus = EventBus(db_path=event_bus_db)
        logger.info("EventBus initialized (%s)", event_bus_db)

        if qwen_key:
            llm.set_signal_emitter(
                lambda signal_type, data: _emit_llm_runtime_signal(
                    observer=observer,
                    event_bus=event_bus,
                    signal_type=signal_type,
                    data=data,
                )
            )

        policy_engine = PolicyEngine()
        logger.info("PolicyEngine initialized")

        from chatgptrest.evomap.knowledge.db import KnowledgeDB as EvoMapKnowledgeDB

        evomap_knowledge_db = None
        evomap_kdb_path = resolve_evomap_knowledge_runtime_db_path()
        try:
            evomap_knowledge_db = EvoMapKnowledgeDB(db_path=evomap_kdb_path)
            evomap_knowledge_db.connect()
            evomap_knowledge_db.init_schema()
            stats = evomap_knowledge_db.stats()
            logger.info(
                "EvoMap Knowledge DB initialized (%s), atoms=%d docs=%d",
                evomap_kdb_path,
                stats.get("atoms", 0),
                stats.get("documents", 0),
            )
            if _env_flag_enabled("OPENMIND_ENABLE_EVOMAP_STARTUP_RESCORE", default=False):
                try:
                    from chatgptrest.evomap.knowledge.retrieval import rescore_all_atoms

                    rescore_all_atoms(evomap_knowledge_db, batch_size=500)
                    logger.info("EvoMap startup rescore complete")
                except Exception as exc:
                    logger.warning("EvoMap startup rescore failed (non-fatal): %s", exc)
            else:
                logger.info("EvoMap startup rescore disabled")
        except Exception as exc:
            logger.warning("EvoMap Knowledge DB init failed (non-fatal): %s", exc)
            evomap_knowledge_db = None

        if evomap_knowledge_db is not None:
            try:
                from chatgptrest.evomap.activity_ingest import ActivityIngestService

                activity_handlers = ActivityIngestService(
                    db=evomap_knowledge_db,
                    observer=observer,
                ).register_bus_handlers(event_bus)
                for handler in activity_handlers:
                    cleanup_callbacks.append(lambda h=handler: event_bus.unsubscribe(h))
                logger.info("EventBus → ActivityIngestService wired")
            except Exception as exc:
                logger.warning("ActivityIngestService wiring failed (non-fatal): %s", exc)

        feishu_secret = os.environ.get("FEISHU_WEBHOOK_SECRET", "")
        dedup_db = os.environ.get(
            "OPENMIND_DEDUP_DB",
            os.path.expanduser("~/.openmind/dedup.db"),
        )
        os.makedirs(os.path.dirname(dedup_db), exist_ok=True)

        mcp_bridge = McpLlmBridge(timeout=120)
        cc_executor = CcExecutor(observer=observer, event_bus=event_bus)

        try:
            routing_fabric = RoutingFabric.from_config(
                evomap_observer=observer,
                mcp_bridge=mcp_bridge,
                llm_connector=llm,
            )
            if hasattr(llm, "attach_routing_fabric"):
                llm.attach_routing_fabric(routing_fabric)
            if _env_flag_enabled("OPENMIND_ENABLE_ROUTING_WATCHER"):
                routing_fabric.start_watcher()
                cleanup_callbacks.append(routing_fabric.stop_watcher)
                logger.info("RoutingFabric initialized + config watcher started")
            else:
                logger.info("RoutingFabric initialized (config watcher disabled)")
        except Exception as exc:
            logger.warning("RoutingFabric init failed (static API fallback only): %s", exc)
            routing_fabric = None

        cc_native = CcNativeExecutor(
            observer=observer,
            event_bus=event_bus,
            memory=memory,
            routing_fabric=routing_fabric,
            scorecard_store=_init_scorecard_store(evo_db),
            team_policy=_init_team_policy(evo_db),
            team_control_plane=_init_team_control_plane(evo_db),
        )

        writeback_service = KBWritebackService(
            registry=kb_reg,
            hub=kb_hub,
            policy_engine=policy_engine,
        )

        configure_services(
            llm_connector=llm,
            evomap_observer=observer,
            evomap_knowledge_db=evomap_knowledge_db,
            kb_registry=kb_reg,
            kb_hub=kb_hub,
            memory=memory,
            event_bus=event_bus,
            policy_engine=policy_engine,
            cc_executor=cc_executor,
            routing_fabric=routing_fabric,
            writeback_service=writeback_service,
        )

        def _on_artifact_registered(art):
            try:
                from pathlib import Path

                path = Path(art.source_path)
                if path.exists():
                    content = path.read_text(encoding="utf-8", errors="replace")[:20000]
                else:
                    content = art.summary or art.title or ""
                if content and kb_hub:
                    kb_hub.index_document(
                        artifact_id=art.artifact_id,
                        title=art.title or path.stem,
                        content=content,
                        source_path=art.source_path,
                        content_type=art.content_type,
                        quality_score=art.quality_score,
                    )
                    logger.debug("Auto-indexed artifact %s to KBHub", art.artifact_id)
            except Exception as exc:
                logger.warning("Auto-index failed for %s: %s", getattr(art, "artifact_id", "?"), exc)

        kb_reg.subscribe(_on_artifact_registered)
        cleanup_callbacks.append(lambda cb=_on_artifact_registered: kb_reg.unsubscribe(cb))
        logger.info("ArtifactRegistry → KBHub auto-index wired")

        def _event_to_observer(event):
            try:
                if observer:
                    from chatgptrest.evomap.signals import Signal

                    observer.record(Signal.from_trace_event(event))
            except Exception as exc:
                logger.debug("EventBus→Observer failed (non-fatal): %s", exc)

        def _event_to_memory(event):
            try:
                if memory and event.event_type in (
                    "route.selected",
                    "gate.passed",
                    "gate.failed",
                    "dispatch.task_completed",
                    "kb.writeback",
                ):
                    from chatgptrest.kernel.memory_manager import MemoryRecord, MemoryTier

                    memory.stage_and_promote(
                        MemoryRecord(
                            key=f"event:{event.event_type}:{event.trace_id}",
                            value={"event_type": event.event_type, "data": event.data},
                            source={"type": "event_bus", "agent": event.source},
                        ),
                        MemoryTier.META,
                        "event_bus mirror",
                    )
            except Exception as exc:
                logger.debug("EventBus→Memory failed (non-fatal): %s", exc)

        event_bus.subscribe(_event_to_observer)
        event_bus.subscribe(_event_to_memory)
        cleanup_callbacks.append(lambda handler=_event_to_observer: event_bus.unsubscribe(handler))
        cleanup_callbacks.append(lambda handler=_event_to_memory: event_bus.unsubscribe(handler))

        circuit_breaker = None
        kb_scorer = None
        gate_tuner = None
        try:
            from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker
            from chatgptrest.evomap.actuators.gate_tuner import GateAutoTuner
            from chatgptrest.evomap.actuators.kb_scorer import KBScorer

            circuit_breaker = CircuitBreaker(observer=observer)
            kb_scorer = KBScorer(observer=observer)
            gate_tuner = GateAutoTuner(observer=observer)

            circuit_handler = circuit_breaker.on_event
            kb_scorer_handler = kb_scorer.on_event
            gate_tuner_handler = gate_tuner.on_event
            event_bus.subscribe(circuit_handler)
            event_bus.subscribe(kb_scorer_handler)
            event_bus.subscribe(gate_tuner_handler)
            cleanup_callbacks.append(lambda handler=circuit_handler: event_bus.unsubscribe(handler))
            cleanup_callbacks.append(lambda handler=kb_scorer_handler: event_bus.unsubscribe(handler))
            cleanup_callbacks.append(lambda handler=gate_tuner_handler: event_bus.unsubscribe(handler))
            logger.info("EvoMap actuators wired: CircuitBreaker, KBScorer, GateAutoTuner")
        except Exception as exc:
            logger.warning("EvoMap actuator init failed (non-fatal): %s", exc)

        configure_services(
            gate_tuner=gate_tuner,
            circuit_breaker=circuit_breaker,
            kb_scorer=kb_scorer,
        )

        signal_count = observer.count() if hasattr(observer, "count") else "?"
        logger.info("EvoMap pipeline wired: EventBus → Observer (%s signals), EventBus → Memory, Actuators", signal_count)

        from langgraph.checkpoint.sqlite import SqliteSaver

        checkpoint_db = os.environ.get(
            "OPENMIND_CHECKPOINT_DB",
            os.path.expanduser("~/.openmind/checkpoint.db"),
        )
        os.makedirs(os.path.dirname(checkpoint_db), exist_ok=True)
        ckpt_conn: sqlite3.Connection | None = None
        try:
            ckpt_conn = sqlite3.connect(checkpoint_db, check_same_thread=False)
            checkpointer = SqliteSaver(ckpt_conn)
            cleanup_callbacks.append(ckpt_conn.close)
            logger.info("SqliteSaver checkpoint enabled: %s", checkpoint_db)
        except Exception as exc:
            logger.warning("SqliteSaver init failed (continuing without checkpoint): %s", exc)
            checkpointer = None

        graph = build_advisor_graph()
        app = graph.compile(checkpointer=checkpointer)

        if evomap_knowledge_db and _env_flag_enabled("OPENMIND_ENABLE_EVOMAP_EXTRACTORS", default=False):
            stop_event = threading.Event()

            def _run_evomap_pipeline():
                import time

                stop_event.wait(10)
                while not stop_event.is_set():
                    try:
                        logger.info("Starting scheduled EvoMap Knowledge Extraction pipeline...")
                        try:
                            from chatgptrest.evomap.knowledge.extractors.chat_followup import ChatFollowupExtractor

                            ChatFollowupExtractor(evomap_knowledge_db).extract_all()
                            logger.info("EvoMap: ChatFollowupExtractor complete")
                        except Exception as exc:
                            logger.warning("EvoMap ChatFollowupExtractor failed: %s", exc)

                        try:
                            from chatgptrest.evomap.knowledge.extractors.maint_runbook import MaintRunbookExtractor

                            MaintRunbookExtractor(
                                evomap_knowledge_db,
                                maint_dirs=[os.path.expanduser("/vol1/maint")],
                            ).extract_all()
                            logger.info("EvoMap: MaintRunbookExtractor complete")
                        except Exception as exc:
                            logger.warning("EvoMap MaintRunbookExtractor failed: %s", exc)

                        try:
                            from chatgptrest.evomap.knowledge.extractors.note_section import NoteSectionExtractor

                            NoteSectionExtractor(
                                evomap_knowledge_db,
                                source_dirs=[
                                    os.path.expanduser("~/brain"),
                                    os.path.expanduser("/vol1/1000/projects/openmind/docs"),
                                ],
                            ).extract_all()
                            logger.info("EvoMap: NoteSectionExtractor complete")
                        except Exception as exc:
                            logger.warning("EvoMap NoteSectionExtractor failed: %s", exc)

                        try:
                            from chatgptrest.evomap.knowledge.extractors.commit_kd0 import CommitKD0Extractor

                            CommitKD0Extractor(
                                evomap_knowledge_db,
                                repo_paths=[
                                    os.path.expanduser("/vol1/1000/projects/ChatgptREST"),
                                    os.path.expanduser("/vol1/1000/projects/openmind"),
                                    os.path.expanduser("/vol1/1000/projects/openclaw"),
                                ],
                            ).extract_all()
                            logger.info("EvoMap: CommitKD0Extractor complete")
                        except Exception as exc:
                            logger.warning("EvoMap CommitKD0Extractor failed: %s", exc)

                        try:
                            from chatgptrest.evomap.knowledge.graph_builder import GraphBuilder

                            stats = GraphBuilder(evomap_knowledge_db).build_all()
                            logger.info("EvoMap: GraphBuilder complete (%s)", stats)
                        except Exception as exc:
                            logger.warning("EvoMap GraphBuilder failed: %s", exc)

                        # ── Antigravity Conversation Extractor ────────────
                        try:
                            from chatgptrest.evomap.knowledge.extractors.antigravity_extractor import AntigravityExtractor

                            AntigravityExtractor(evomap_knowledge_db).extract_all()
                            logger.info("EvoMap: AntigravityExtractor complete")
                        except Exception as exc:
                            logger.warning("EvoMap AntigravityExtractor failed: %s", exc)

                        # ── Activity Extractor (agent closeout + commit events) ──
                        try:
                            from chatgptrest.evomap.knowledge.extractors.activity_extractor import ActivityExtractor

                            activity_ext = ActivityExtractor(evomap_knowledge_db)
                            activity_result = activity_ext.extract_all()
                            logger.info(
                                "EvoMap: ActivityExtractor complete (atoms=%d, skipped=%d)",
                                getattr(activity_result, "created", 0),
                                getattr(activity_result, "skipped", 0),
                            )
                        except Exception as exc:
                            logger.warning("EvoMap ActivityExtractor failed: %s", exc)

                        # ── Atom Refiner (heuristic mode, LLM optional) ──
                        try:
                            from chatgptrest.evomap.knowledge.atom_refiner import AtomRefiner

                            refiner = AtomRefiner(db=evomap_knowledge_db)
                            ref_result = refiner.refine_all(limit=200)
                            logger.info(
                                "EvoMap: AtomRefiner complete (refined=%d, skipped=%d)",
                                ref_result.refined, ref_result.skipped,
                            )
                        except Exception as exc:
                            logger.warning("EvoMap AtomRefiner failed: %s", exc)

                        # ── P2 Groundedness Checker ──────────────────────
                        try:
                            from chatgptrest.evomap.knowledge.groundedness_checker import run_p2_groundedness

                            ground_result = run_p2_groundedness(evomap_knowledge_db)
                            logger.info(
                                "EvoMap: Groundedness check complete (checked=%d, demoted=%d)",
                                ground_result.get("checked", 0),
                                ground_result.get("demoted", 0),
                            )
                        except Exception as exc:
                            logger.warning("EvoMap groundedness check failed: %s", exc)

                        # ── Atom Aging (mark old unscored atoms) ─────────
                        try:
                            _age_old_atoms(evomap_knowledge_db)
                        except Exception as exc:
                            logger.warning("EvoMap atom aging failed: %s", exc)

                    except Exception as exc:
                        logger.error("EvoMap pipeline loop error: %s", exc)

                    stop_event.wait(4 * 3600)

            thread = threading.Thread(target=_run_evomap_pipeline, daemon=True, name="EvoMapExtractor")
            thread.start()
            logger.info("EvoMap Knowledge Extraction pipeline scheduled (daemon thread)")

            def _stop_evomap():
                logger.info("EvoMap: requesting graceful shutdown...")
                stop_event.set()
                thread.join(timeout=5)

            atexit.register(_stop_evomap)

            def _cleanup_evomap() -> None:
                try:
                    atexit.unregister(_stop_evomap)
                except Exception:
                    pass
                _stop_evomap()

            cleanup_callbacks.append(_cleanup_evomap)
        elif evomap_knowledge_db:
            logger.info("EvoMap Knowledge Extraction pipeline disabled")

        runtime: AdvisorRuntime

        def advisor_fn(state_dict: dict[str, Any]) -> dict[str, Any]:
            payload = dict(state_dict)
            return _invoke_graph_app(
                app=app,
                runtime=runtime,
                payload=payload,
                thread_id=str(payload.get("trace_id", "default")),
            )

        def feishu_advisor_fn(msg: str, trace_id: str = "") -> dict[str, Any]:
            payload = {
                "user_message": msg,
                "trace_id": trace_id,
            }
            return _invoke_graph_app(
                app=app,
                runtime=runtime,
                payload=payload,
                thread_id=trace_id or "feishu-default",
            )

        try:
            from chatgptrest.advisor.feishu_api_client import FeishuApiClient

            feishu_client = FeishuApiClient()
            send_card_fn = feishu_client.send_card
            if feishu_client.enabled:
                logger.info("FeishuApiClient initialized (app_id=%s...)", feishu_client._app_id[:8])
            else:
                logger.warning("FeishuApiClient not configured — bot replies will be disabled")
        except Exception as exc:
            logger.warning("FeishuApiClient unavailable — bot replies disabled: %s", exc)

            def send_card_fn(*args: Any, **kwargs: Any) -> dict[str, Any]:
                return {"status": "disabled", "reason": "feishu_api_client_unavailable"}

        feishu = FeishuHandler(
            advisor_fn=feishu_advisor_fn,
            webhook_secret=feishu_secret,
            dedup_db_path=dedup_db,
            send_card_fn=send_card_fn,
        )

        api = AdvisorAPI(
            advisor_fn=advisor_fn,
            feishu_handler=feishu,
        )

        skill_registry = None
        bundle_resolver = None
        capability_gap_recorder = None
        quarantine_gate = None
        try:
            from chatgptrest.kernel.skill_manager import CanonicalRegistry, BundleResolver
            from chatgptrest.kernel.market_gate import CapabilityGapRecorder, QuarantineGate

            skill_registry = CanonicalRegistry()
            bundle_resolver = BundleResolver(skill_registry)
            capability_gap_recorder = CapabilityGapRecorder()
            quarantine_gate = QuarantineGate(skill_registry)
            logger.info("Capability Registry and Market Gate initialized")
        except Exception as exc:
            logger.warning("Capability Registry / Market Gate init failed (non-fatal): %s", exc)

        runtime = AdvisorRuntime(
            api=api,
            feishu=feishu,
            llm=llm,
            outbox=outbox,
            observer=observer,
            kb_registry=kb_reg,
            graph_app=app,
            advisor_fn=advisor_fn,
            kb_hub=kb_hub,
            memory=memory,
            event_bus=event_bus,
            cc_executor=cc_executor,
            cc_native=cc_native,
            evomap_knowledge_db=evomap_knowledge_db,
            policy_engine=policy_engine,
            circuit_breaker=circuit_breaker,
            kb_scorer=kb_scorer,
            gate_tuner=gate_tuner,
            routing_fabric=routing_fabric,
            writeback_service=writeback_service,
            team_control_plane=getattr(cc_native, "_team_control_plane", None),
            mcp_bridge=mcp_bridge,
            skill_registry=skill_registry,
            bundle_resolver=bundle_resolver,
            capability_gap_recorder=capability_gap_recorder,
            quarantine_gate=quarantine_gate,
            cleanup_callbacks=cleanup_callbacks,
        )
        _RUNTIME = runtime
        logger.info("OpenMind v3 advisor runtime initialized")
        return runtime


def reset_advisor_runtime() -> None:
    from chatgptrest.advisor.graph import reset_services

    global _RUNTIME
    with _INIT_LOCK:
        runtime = _RUNTIME
        _RUNTIME = None
        if runtime is not None:
            runtime.close()
        reset_services()
