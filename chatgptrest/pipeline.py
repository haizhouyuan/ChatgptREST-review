"""
Automated Pipeline: Feishu Intake → Advisor → Funnel → Dispatch.

This is the real automation bridge. It:
1. Reads REQ_NEW JSON from feishu-intake agent sessions
2. Routes through Advisor (C/K/U/R/I)
3. Runs the full Funnel (9 stages → ProjectCard)
4. Dispatches tasks to Agent Teams via OpenClaw CLI
5. Reports results back to Feishu

Usage:
    # Process a single REQ_NEW JSON
    python -m chatgptrest.pipeline process --req-file /path/to/req.json

    # Watch feishu-intake sessions for new requirements
    python -m chatgptrest.pipeline watch

    # Reprocess all pending requirements
    python -m chatgptrest.pipeline reprocess
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import traceback as tb_module
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .contracts.schemas import (
    AdvisorContext,
    IntentSignals,
    KBProbeResult,
    ProjectCard,
    Route,
    TraceEvent,
    _now_iso,
    _uuid,
)
from .contracts.event_log import EventLogStore
from .advisor import route_request
from .workflows.funnel import FunnelEngine, extract_intent_from_text, classify_request_type
from .workflows import DeepResearchWorkflow
# Phase-2: EvoMapEngine retired — signals now flow through EventBus+Observer
# from .workflows.evomap import EvoMapEngine  # DEPRECATED

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FEISHU_INTAKE_SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "feishu-intake" / "sessions"
PIPELINE_STATE_DIR = Path.home() / ".openclaw" / "workspace-planning" / "pipeline_state"
PROJECT_CARDS_DIR = Path("/vol1/1000/projects/ChatgptREST/docs/project_cards")
OPENCLAW_CMD = "openclaw"
DEFAULT_DB_PATH = Path.home() / ".openclaw" / "workspace-planning" / "pipeline.db"


@dataclass
class PipelineConfig:
    """Pipeline configuration."""
    feishu_sessions_dir: Path = FEISHU_INTAKE_SESSIONS_DIR
    state_dir: Path = PIPELINE_STATE_DIR
    project_cards_dir: Path = PROJECT_CARDS_DIR
    db_path: Path = DEFAULT_DB_PATH
    openclaw_cmd: str = OPENCLAW_CMD
    feishu_account: str = "main"
    feishu_target: str = ""  # Will be auto-detected from session
    auto_dispatch: bool = False  # Safety: don't auto-dispatch until tested


# ---------------------------------------------------------------------------
# REQ_NEW Parser
# ---------------------------------------------------------------------------

@dataclass
class FeishuRequirement:
    """A parsed requirement from feishu-intake."""
    req_id: str = ""
    title: str = ""
    raw_text: str = ""
    goal: str = ""
    priority: str = "P1"
    deadline: str = ""
    acceptance: list[str] = field(default_factory=list)
    owner_hint: str = ""
    blocker: str = "none"
    source_session: str = ""
    feishu_user_id: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_feishu_session(session_path: Path) -> list[FeishuRequirement]:
    """
    Parse a feishu-intake JSONL session file.

    Extracts:
    - User messages (raw voice transcripts)
    - Assistant responses (REQ_NEW JSON when STATUS=READY_FOR_FUNNEL)
    - Conversation metadata (user ID, timestamps)
    """
    reqs: list[FeishuRequirement] = []
    user_messages: list[dict[str, Any]] = []
    session_id = session_path.stem

    with open(session_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = obj.get("message", {})
            role = msg.get("role", "")
            timestamp = obj.get("timestamp", "")

            # Extract text content
            content = msg.get("content", "")
            if isinstance(content, list):
                text = " ".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                )
            else:
                text = str(content)

            if role == "user" and text:
                # Extract Feishu user ID from DM metadata
                feishu_user = ""
                dm_match = re.search(r"DM from (ou_[a-f0-9]+)", text)
                if dm_match:
                    feishu_user = dm_match.group(1)

                # Extract the actual content (after metadata prefix)
                # Format: "System: [timestamp] Feishu[main] DM from ou_xxx: <actual content>"
                content_match = re.search(
                    r"DM from ou_[a-f0-9]+:\s*(.+)",
                    text,
                    re.DOTALL,
                )
                actual_content = content_match.group(1).strip() if content_match else text

                # Remove conversation metadata JSON block
                actual_content = re.sub(
                    r"Conversation info.*?```json.*?```",
                    "",
                    actual_content,
                    flags=re.DOTALL,
                )
                actual_content = actual_content.strip()

                user_messages.append({
                    "text": actual_content,
                    "feishu_user": feishu_user,
                    "timestamp": timestamp,
                    "raw": text,
                })

            elif role == "assistant" and text:
                # Check for REQ_NEW JSON (STATUS=READY_FOR_FUNNEL)
                if "READY_FOR_FUNNEL" in text or "ready_for_funnel" in text:
                    # Try to extract JSON
                    json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
                    if json_match:
                        try:
                            req_json = json.loads(json_match.group())
                            req = FeishuRequirement(
                                req_id=req_json.get("request_id", _uuid()[:12]),
                                title=req_json.get("project_hint", req_json.get("title", "")),
                                goal=req_json.get("goal", ""),
                                priority=req_json.get("priority", "P1"),
                                deadline=req_json.get("deadline", ""),
                                acceptance=req_json.get("acceptance", []),
                                owner_hint=req_json.get("owner_hint", ""),
                                blocker=req_json.get("blocker", "none"),
                                source_session=session_id,
                                timestamp=timestamp,
                            )
                            # Attach latest user message as raw_text
                            if user_messages:
                                req.raw_text = user_messages[-1]["text"]
                                req.feishu_user_id = user_messages[-1].get("feishu_user", "")
                            reqs.append(req)
                        except json.JSONDecodeError:
                            pass

                # Also capture requirements from assistant analysis
                # (when intake summarizes but hasn't received confirmation yet)
                elif "<final>" in text.lower() or "核心目标" in text:
                    # This is an intermediate analysis — associate with user's raw input
                    if user_messages and not any(
                        r.raw_text == user_messages[-1]["text"] for r in reqs
                    ):
                        # Create a requirement from the raw input
                        latest = user_messages[-1]
                        title_match = re.search(r"[一二三1-3]\.\s*\*\*([^*]+)\*\*", text)
                        title = title_match.group(1) if title_match else latest["text"][:50]

                        req = FeishuRequirement(
                            req_id=f"req_{_uuid()[:8]}",
                            title=title,
                            raw_text=latest["text"],
                            feishu_user_id=latest.get("feishu_user", ""),
                            source_session=session_id,
                            timestamp=latest.get("timestamp", ""),
                        )
                        reqs.append(req)

    return reqs


# ---------------------------------------------------------------------------
# Pipeline Engine
# ---------------------------------------------------------------------------

class Pipeline:
    """
    The automated pipeline that processes Feishu requirements end-to-end.

    Flow:
        parse_sessions() → route() → funnel() → save_project_card() → dispatch()
    """

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        self.config.project_cards_dir.mkdir(parents=True, exist_ok=True)

        self.event_log = EventLogStore(str(self.config.db_path))
        self.funnel = FunnelEngine(event_log=self.event_log)
        # Phase-2: EvoMapEngine retired, signals via EventBus+Observer
        self.evomap = None
        self._processed_file = self.config.state_dir / "processed_reqs.json"
        self._processed: OrderedDict = self._load_processed()

    # LRU cache for processed requirements (limited to 1000 entries)
    MAX_PROCESSED_CACHE = 1000

    def _load_processed(self) -> OrderedDict:
        """Load ordered dict of already-processed requirement IDs (LRU bounded)."""
        if self._processed_file.exists():
            try:
                items = json.loads(self._processed_file.read_text())
                od = OrderedDict((k, True) for k in items)
                # Trim to max size (keep newest)
                while len(od) > self.MAX_PROCESSED_CACHE:
                    od.popitem(last=False)
                return od
            except Exception:
                pass
        return OrderedDict()

    def _save_processed(self) -> None:
        """Persist processed requirement IDs."""
        self._processed_file.write_text(json.dumps(list(self._processed.keys()), indent=2))

    def _mark_processed(self, req_id: str) -> None:
        """Mark a requirement as processed, evicting oldest if over limit."""
        self._processed[req_id] = True
        self._processed.move_to_end(req_id)
        while len(self._processed) > self.MAX_PROCESSED_CACHE:
            self._processed.popitem(last=False)
        self._save_processed()

    def scan_sessions(self) -> list[FeishuRequirement]:
        """Scan feishu-intake sessions for new requirements."""
        all_reqs = []
        sessions_dir = self.config.feishu_sessions_dir
        if not sessions_dir.exists():
            logger.warning(f"Sessions dir not found: {sessions_dir}")
            return []

        for session_file in sorted(sessions_dir.glob("*.jsonl")):
            reqs = parse_feishu_session(session_file)
            for req in reqs:
                if req.req_id not in self._processed:
                    all_reqs.append(req)

        return all_reqs

    @staticmethod
    def _make_error_payload(exc: Exception) -> dict[str, Any]:
        """Standardize error payload format."""
        return {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": tb_module.format_exc(),
        }

    def process_requirement(self, req: FeishuRequirement) -> dict[str, Any]:
        """
        Process a single requirement through the full pipeline.

        Returns a result dict with route, project_card, dispatch status, etc.
        """
        trace_id = f"pipeline_{req.req_id}"
        result: dict[str, Any] = {
            "req_id": req.req_id,
            "title": req.title,
            "trace_id": trace_id,
            "timestamp": _now_iso(),
        }

        # Emit step.started BEFORE execution
        self.event_log.append(TraceEvent(
            source="pipeline/process",
            event_type="step.started",
            trace_id=trace_id,
            data={"req_id": req.req_id, "title": req.title},
        ))

        try:
            result = self._execute_pipeline_steps(req, trace_id, result)
        except Exception as exc:
            result["error"] = self._make_error_payload(exc)
            self.event_log.append(TraceEvent(
                source="pipeline/process",
                event_type="step.failed",
                trace_id=trace_id,
                data={"req_id": req.req_id, "error": result["error"]},
            ))

        # Emit step.completed AFTER execution
        self.event_log.append(TraceEvent(
            source="pipeline/process",
            event_type="step.completed",
            trace_id=trace_id,
            data={"req_id": req.req_id, "has_error": "error" in result},
        ))

        # Mark as processed
        self._mark_processed(req.req_id)
        return result

    def _execute_pipeline_steps(
        self, req: FeishuRequirement, trace_id: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute the actual pipeline steps (extracted for error handling)."""

        # Step 1: Intent analysis
        intent = extract_intent_from_text(req.raw_text or req.goal)
        req_type = classify_request_type(req.raw_text or req.goal)

        # Map priority to urgency
        urgency = {"P0": "immediate", "P1": "near-term", "P2": "whenever"}.get(
            req.priority, "whenever"
        )

        # Step 2: Advisor routing
        ctx = route_request(
            req.raw_text[:500] if req.raw_text else req.goal,
            intent=IntentSignals(
                intent_confidence=0.7 if req.raw_text else 0.85,
                multi_intent=len(intent.get("explicit_requests", [])) > 1,
                step_count_est=max(len(intent.get("explicit_requests", [])) * 2, 5),
                verification_need=True,
            ),
            kb_probe=KBProbeResult(answerability=0.15),
            urgency_hint=urgency,
            trace_id=trace_id,
        )

        self.event_log.append(TraceEvent(
            source="pipeline/route",
            event_type="route_selected",
            trace_id=trace_id,
            data={"route": ctx.selected_route, "req_id": req.req_id},
        ))

        result["route"] = ctx.selected_route
        result["scores"] = ctx.scores.to_dict()

        # Step 3: Funnel processing
        funnel_input = req.raw_text or req.goal or req.title
        state = self.funnel.run(funnel_input, trace_id=trace_id)

        result["funnel_stage"] = state.current_stage
        result["rubric"] = state.rubric_history[-1] if state.rubric_history else {}

        # Step 4: Save ProjectCard
        if state.project_card:
            card = state.project_card
            # Enrich with requirement metadata
            card.title = req.title or card.title
            if req.acceptance:
                card.definition_of_done = req.acceptance

            card_path = self.config.project_cards_dir / f"{req.req_id}.json"
            card_path.write_text(
                json.dumps(card.to_dict(), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            result["project_card_path"] = str(card_path)
            result["rubric_total"] = card.rubric_snapshot.total
            result["rubric_gate"] = card.rubric_snapshot.gate
            result["tasks"] = [t.title for t in card.tasks]
            result["risks_count"] = len(card.risks)

        # Step 5: EvoMap signal extraction (Phase-2: retired, handled by EventBus)
        signals_count = 0
        if self.evomap:
            try:
                signals = self.evomap.extract_session_signals(trace_id)
                signals_count = len(signals)
            except Exception:
                pass
        result["signals_count"] = signals_count
        result["trace_events"] = self.event_log.count(trace_id=trace_id)

        return result

    def dispatch_to_agents(
        self,
        result: dict[str, Any],
        req: FeishuRequirement,
    ) -> dict[str, Any]:
        """
        Dispatch a processed requirement to Agent Teams via OpenClaw.

        Uses `openclaw message send` to:
        1. Send ProjectCard summary to the user on Feishu
        2. Create tasks in the orchestrator agent
        """
        dispatch_result = {"dispatched": False, "actions": []}

        if not self.config.auto_dispatch:
            dispatch_result["reason"] = "auto_dispatch disabled (safety)"
            return dispatch_result

        # Send result back to Feishu user
        if req.feishu_user_id:
            summary_text = (
                f"📋 需求已处理: {result.get('title', 'N/A')}\n"
                f"路由: {result.get('route', 'N/A')}\n"
                f"Rubric: {result.get('rubric_total', 0):.0f} "
                f"(Gate {result.get('rubric_gate', 'N/A')})\n"
                f"任务数: {len(result.get('tasks', []))}\n"
                f"风险数: {result.get('risks_count', 0)}\n"
                f"Trace events: {result.get('trace_events', 0)}"
            )

            try:
                cmd = [
                    self.config.openclaw_cmd,
                    "message", "send",
                    "--channel", "feishu",
                    "--account", self.config.feishu_account,
                    "--target", req.feishu_user_id,
                    "--message", summary_text,
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                dispatch_result["feishu_reply"] = {
                    "ok": proc.returncode == 0,
                    "stdout": proc.stdout[:200],
                }
                dispatch_result["actions"].append("feishu_reply_sent")
            except Exception as e:
                dispatch_result["feishu_reply_error"] = str(e)

        dispatch_result["dispatched"] = True
        return dispatch_result

    def run_all(self, dry_run: bool = False) -> list[dict[str, Any]]:
        """
        Scan for new requirements and process them all.

        Args:
            dry_run: If True, only scan and parse, don't process.
        """
        reqs = self.scan_sessions()
        if not reqs:
            logger.info("No new requirements found")
            return []

        logger.info(f"Found {len(reqs)} new requirements")
        results = []

        for req in reqs:
            logger.info(f"Processing: [{req.req_id}] {req.title}")

            if dry_run:
                results.append({
                    "req_id": req.req_id,
                    "title": req.title,
                    "raw_text_preview": (req.raw_text or "")[:200],
                    "dry_run": True,
                })
                continue

            result = self.process_requirement(req)

            # Dispatch if enabled
            if self.config.auto_dispatch:
                dispatch = self.dispatch_to_agents(result, req)
                result["dispatch"] = dispatch

            results.append(result)
            logger.info(
                f"  → route={result.get('route')}, "
                f"rubric={result.get('rubric_total', 0):.0f}, "
                f"tasks={len(result.get('tasks', []))}"
            )

        return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AIOS Pipeline: Feishu → Advisor → Funnel → Dispatch"
    )
    sub = parser.add_subparsers(dest="command")

    # Run all pending
    run_parser = sub.add_parser("run", help="Process all pending requirements")
    run_parser.add_argument("--dry-run", action="store_true",
                           help="Only scan, don't process")
    run_parser.add_argument("--auto-dispatch", action="store_true",
                           help="Auto-dispatch to Agent Teams")
    run_parser.add_argument("--llm", action="store_true",
                           help="Use LLM-powered Funnel stages (real analysis)")

    # Process single file
    proc_parser = sub.add_parser("process", help="Process a single REQ_NEW file")
    proc_parser.add_argument("--req-file", required=True, help="Path to REQ_NEW JSON")
    proc_parser.add_argument("--llm", action="store_true",
                           help="Use LLM-powered Funnel stages (real analysis)")

    # Watch mode
    watch_parser = sub.add_parser("watch", help="Watch for new requirements")
    watch_parser.add_argument("--interval", type=int, default=30,
                             help="Poll interval in seconds")
    watch_parser.add_argument("--llm", action="store_true",
                           help="Use LLM-powered Funnel stages (real analysis)")

    # Status
    sub.add_parser("status", help="Show pipeline status")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = PipelineConfig()

    if args.command == "run":
        config.auto_dispatch = args.auto_dispatch
        pipeline = Pipeline(config)
        if args.llm:
            from .workflows.llm_funnel import upgrade_funnel_with_llm
            upgrade_funnel_with_llm(pipeline.funnel)
            logger.info("LLM-powered Funnel stages enabled")
        results = pipeline.run_all(dry_run=args.dry_run)
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))

    elif args.command == "process":
        req_path = Path(args.req_file)
        req_data = json.loads(req_path.read_text())
        req = FeishuRequirement(
            req_id=req_data.get("request_id", req_path.stem),
            title=req_data.get("title", req_data.get("project_hint", "")),
            goal=req_data.get("goal", req_data.get("objective", "")),
            priority=req_data.get("priority", "P1"),
            deadline=req_data.get("deadline", req_data.get("eta", "")),
            acceptance=req_data.get("acceptance", []),
            raw_text=req_data.get("raw_text", req_data.get("goal", "")),
        )
        pipeline = Pipeline(config)
        if args.llm:
            from .workflows.llm_funnel import upgrade_funnel_with_llm
            upgrade_funnel_with_llm(pipeline.funnel)
            logger.info("LLM-powered Funnel stages enabled")
        result = pipeline.process_requirement(req)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif args.command == "watch":
        config.auto_dispatch = True
        pipeline = Pipeline(config)
        if args.llm:
            from .workflows.llm_funnel import upgrade_funnel_with_llm
            upgrade_funnel_with_llm(pipeline.funnel)
        logger.info(f"Watching {config.feishu_sessions_dir} every {args.interval}s...")
        while True:
            results = pipeline.run_all()
            if results:
                for r in results:
                    logger.info(f"Processed: {r.get('title')} → {r.get('route')}")
            time.sleep(args.interval)

    elif args.command == "status":
        pipeline = Pipeline(config)
        reqs = pipeline.scan_sessions()
        print(f"Pending requirements: {len(reqs)}")
        for req in reqs:
            print(f"  [{req.req_id}] {req.title}")
        print(f"Processed: {len(pipeline._processed)}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
