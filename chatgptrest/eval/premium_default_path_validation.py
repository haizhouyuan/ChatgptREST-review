"""Regression proof that ordinary premium asks stay on default LLM paths."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

from chatgptrest.advisor.ask_contract import normalize_ask_contract
from chatgptrest.advisor.ask_strategist import build_strategy_plan
from chatgptrest.advisor.scenario_packs import apply_scenario_pack, resolve_scenario_pack
from chatgptrest.advisor.task_intake import build_task_intake_spec, task_intake_to_contract_seed
from chatgptrest.controller.engine import ControllerEngine
from chatgptrest.core.db import connect
from chatgptrest.eval.datasets import EvalDataset, EvalItem


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]

_EXPECTED_FIELD_MAP = {
    "expected_profile": "scenario_pack_profile",
    "expected_route": "route",
    "expected_provider": "provider",
    "expected_preset": "preset",
    "expected_kind": "job_kind",
    "expected_execution_kind": "execution_kind",
    "expected_objective_kind": "objective_kind",
    "expected_llm_default_path": "llm_default_path",
}


class _RuntimeState(dict[str, Any]):
    """Compatibility shim for ControllerEngine state."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover - normal attribute lookup parity
            raise AttributeError(name) from exc


@dataclass
class PremiumDefaultPathSnapshot:
    input: str
    goal_hint: str
    scenario_pack_profile: str = ""
    strategy_route_hint: str = ""
    route: str = ""
    provider: str = ""
    preset: str = ""
    job_kind: str = ""
    execution_kind: str = ""
    objective_kind: str = ""
    controller_status: str = ""
    llm_default_path: bool = False
    team_lane: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PremiumDefaultPathValidationResult:
    item_input: str
    passed: bool
    snapshot: PremiumDefaultPathSnapshot
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_input": self.item_input,
            "passed": self.passed,
            "snapshot": self.snapshot.to_dict(),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class PremiumDefaultPathValidationReport:
    dataset_name: str
    num_items: int
    num_passed: int
    num_failed: int
    results: list[PremiumDefaultPathValidationResult]
    scope_boundary: str = (
        "ordinary premium asks stay on public-agent/controller LLM default paths; "
        "not a live provider completion proof"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "num_items": self.num_items,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "results": [item.to_dict() for item in self.results],
            "scope_boundary": self.scope_boundary,
        }


def snapshot_premium_default_path_sample(item: EvalItem) -> PremiumDefaultPathSnapshot:
    meta = dict(item.metadata or {})
    context = dict(meta.get("context") or {})
    raw_task_intake = dict(meta.get("task_intake") or {})
    raw_contract = dict(meta.get("contract") or {})
    attachments = list(meta.get("attachments") or [])
    goal_hint = str(meta.get("goal_hint") or "")
    ingress_lane = str(meta.get("ingress_lane") or "agent_v3")
    default_source = str(meta.get("default_source") or "rest")
    raw_source = str(meta.get("source") or "")
    trace_id = str(meta.get("trace_id") or f"premium-default:{uuid.uuid4().hex[:12]}")
    session_id = str(meta.get("session_id") or f"premium-default-session-{uuid.uuid4().hex[:8]}")
    user_id = str(meta.get("user_id") or "eval-user")

    task_intake = build_task_intake_spec(
        ingress_lane=ingress_lane,
        default_source=default_source,
        raw_source=raw_source,
        raw_task_intake=raw_task_intake,
        raw_contract=raw_contract,
        message=item.input,
        goal_hint=goal_hint,
        trace_id=trace_id,
        session_id=session_id,
        user_id=user_id,
        context=context,
        attachments=attachments,
        client_name=str(meta.get("client_name") or ""),
    )
    scenario_pack = resolve_scenario_pack(task_intake, goal_hint=goal_hint, context=context)
    if scenario_pack is not None:
        task_intake = apply_scenario_pack(task_intake, scenario_pack)
        context["scenario_pack"] = scenario_pack.to_dict()
    context["task_intake"] = task_intake.to_dict()

    contract_seed = task_intake_to_contract_seed(task_intake)
    merged_contract = dict(contract_seed)
    merged_contract.update(raw_contract)
    contract, _ = normalize_ask_contract(
        message=item.input,
        raw_contract=merged_contract,
        goal_hint=goal_hint,
        context=context,
    )
    strategy = build_strategy_plan(
        message=item.input,
        contract=contract,
        goal_hint=goal_hint,
        context=context,
    )
    context["ask_contract"] = contract.to_dict()
    context["ask_strategy"] = strategy.to_dict()

    route_mapping = _default_public_route_mapping()
    with _temporary_controller_env() as temp_state:
        engine = ControllerEngine(
            _RuntimeState(
                cc_native=object(),
                kb_hub=None,
                llm_connector=None,
                evomap_observer=None,
                kb_registry=None,
                memory=None,
                event_bus=None,
                model_router=None,
                mcp_bridge=None,
                cc_executor=None,
                policy_engine=None,
                routing_fabric=None,
                evomap_knowledge_db=None,
                writeback_service=None,
            )
        )
        route_plan = engine._plan_async_route(
            question=item.input,
            trace_id=trace_id,
            intent_hint=_derive_intent_hint(goal_hint=goal_hint),
            session_id=session_id,
            account_id="",
            thread_id="",
            agent_id="",
            role_id="",
            stable_context=context,
        )
        execution_kind = engine._resolve_execution_kind(route_plan=route_plan, stable_context=context)
        objective_plan = engine._build_objective_plan(
            question=item.input,
            route_plan=route_plan,
            intent_hint=_derive_intent_hint(goal_hint=goal_hint),
            stable_context=context,
        )
        result = engine.ask(
            question=item.input,
            trace_id=trace_id,
            intent_hint=_derive_intent_hint(goal_hint=goal_hint),
            role_id="",
            session_id=session_id,
            account_id="",
            thread_id="",
            agent_id="",
            user_id=user_id,
            stable_context=context,
            idempotency_key=f"premium-default:{session_id}",
            request_fingerprint=f"premium-default:{session_id}",
            timeout_seconds=300,
            max_retries=1,
            quality_threshold=0,
            request_metadata={},
            degradation=[],
            route_mapping=route_mapping,
            kb_direct_completion_allowed=lambda _state: False,
            kb_direct_synthesis_enabled=lambda: False,
            sanitize_context_hash="",
        )
        job_kind = _job_kind(temp_state["db_path"], str(result.get("job_id") or ""))

    profile = ""
    if scenario_pack is not None:
        profile = str(scenario_pack.profile or "")
    route = str(result.get("route") or route_plan.get("route") or "")
    provider = str(result.get("provider") or "")
    preset = str(result.get("preset") or "")
    team_lane = execution_kind == "team" or provider == "team_control_plane" or job_kind == "team_child_executor"
    llm_default_path = execution_kind == "job" and provider in {"chatgpt", "gemini", "consult"} and not team_lane

    return PremiumDefaultPathSnapshot(
        input=item.input,
        goal_hint=goal_hint,
        scenario_pack_profile=profile,
        strategy_route_hint=str(strategy.route_hint or ""),
        route=route,
        provider=provider,
        preset=preset,
        job_kind=job_kind,
        execution_kind=str(execution_kind or ""),
        objective_kind=str(objective_plan.get("objective_kind") or ""),
        controller_status=str(result.get("controller_status") or ""),
        llm_default_path=llm_default_path,
        team_lane=team_lane,
    )


def validate_premium_default_path_sample(item: EvalItem) -> PremiumDefaultPathValidationResult:
    snapshot = snapshot_premium_default_path_sample(item)
    expected = {
        key: value
        for key, value in dict(item.metadata or {}).items()
        if key in _EXPECTED_FIELD_MAP
    }
    mismatches: dict[str, dict[str, Any]] = {}
    snapshot_dict = snapshot.to_dict()
    for expected_key, snapshot_key in _EXPECTED_FIELD_MAP.items():
        if expected_key not in expected:
            continue
        actual = snapshot_dict.get(snapshot_key)
        wanted = expected[expected_key]
        if actual != wanted:
            mismatches[expected_key] = {"expected": wanted, "actual": actual}
    return PremiumDefaultPathValidationResult(
        item_input=item.input,
        passed=not mismatches,
        snapshot=snapshot,
        mismatches=mismatches,
    )


def run_premium_default_path_validation(dataset: EvalDataset) -> PremiumDefaultPathValidationReport:
    results = [validate_premium_default_path_sample(item) for item in dataset]
    num_passed = sum(1 for result in results if result.passed)
    return PremiumDefaultPathValidationReport(
        dataset_name=dataset.name,
        num_items=len(results),
        num_passed=num_passed,
        num_failed=len(results) - num_passed,
        results=results,
    )


def render_premium_default_path_report_markdown(report: PremiumDefaultPathValidationReport) -> str:
    lines = [
        f"# Premium Default Path Validation Report — {report.dataset_name}",
        "",
        f"- items: {report.num_items}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        f"- scope_boundary: {report.scope_boundary}",
        "",
        "| Input | Pass | Profile | Route | Provider | Preset | Kind | Exec Kind | Objective Kind | Default LLM Path | Mismatch |",
        "|---|---:|---|---|---|---|---|---|---|---:|---|",
    ]
    for result in report.results:
        snapshot = result.snapshot
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in result.mismatches.items()
        )
        lines.append(
            "| {input} | {passed} | {profile} | {route} | {provider} | {preset} | {kind} | {exec_kind} | {objective_kind} | {llm_path} | {mismatch} |".format(
                input=_escape_pipe(result.item_input),
                passed="yes" if result.passed else "no",
                profile=_escape_pipe(snapshot.scenario_pack_profile or "-"),
                route=_escape_pipe(snapshot.route or "-"),
                provider=_escape_pipe(snapshot.provider or "-"),
                preset=_escape_pipe(snapshot.preset or "-"),
                kind=_escape_pipe(snapshot.job_kind or "-"),
                exec_kind=_escape_pipe(snapshot.execution_kind or "-"),
                objective_kind=_escape_pipe(snapshot.objective_kind or "-"),
                llm_path="yes" if snapshot.llm_default_path else "no",
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_premium_default_path_report(
    report: PremiumDefaultPathValidationReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_premium_default_path_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def _default_public_route_mapping() -> dict[str, dict[str, str]]:
    return {
        "kb_answer": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
        "quick_ask": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
        "clarify": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
        "hybrid": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
        "analysis_heavy": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
        "deep_research": {"provider": "chatgpt", "preset": "deep_research", "kind": "chatgpt_web.ask"},
        "report": {"provider": "chatgpt", "preset": "pro_extended", "kind": "chatgpt_web.ask"},
        "write_report": {"provider": "chatgpt", "preset": "pro_extended", "kind": "chatgpt_web.ask"},
        "funnel": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
        "build_feature": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
        "action": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
    }


@contextmanager
def _temporary_controller_env() -> Iterator[dict[str, Path]]:
    old_db = os.environ.get("CHATGPTREST_DB_PATH")
    old_artifacts = os.environ.get("CHATGPTREST_ARTIFACTS_DIR")
    with tempfile.TemporaryDirectory(prefix="premium-default-path-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "jobdb.sqlite3"
        artifacts_dir = tmp_path / "artifacts"
        os.environ["CHATGPTREST_DB_PATH"] = str(db_path)
        os.environ["CHATGPTREST_ARTIFACTS_DIR"] = str(artifacts_dir)
        try:
            yield {"db_path": db_path, "artifacts_dir": artifacts_dir}
        finally:
            if old_db is None:
                os.environ.pop("CHATGPTREST_DB_PATH", None)
            else:
                os.environ["CHATGPTREST_DB_PATH"] = old_db
            if old_artifacts is None:
                os.environ.pop("CHATGPTREST_ARTIFACTS_DIR", None)
            else:
                os.environ["CHATGPTREST_ARTIFACTS_DIR"] = old_artifacts


def _job_kind(db_path: Path, job_id: str) -> str:
    if not job_id:
        return ""
    with connect(db_path) as conn:
        row = conn.execute("SELECT kind FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        return ""
    return str(row["kind"] or "")


def _derive_intent_hint(*, goal_hint: str) -> str:
    hint = str(goal_hint or "").strip().lower()
    if hint in {"code_review", "research"}:
        return "research"
    if hint == "report":
        return "report"
    if hint == "quick":
        return "quick"
    return ""


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
