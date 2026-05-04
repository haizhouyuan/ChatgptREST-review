"""Paperclip Memory Research Lab Orchestrator.

One Paperclip agent should call this wrapper. The wrapper owns:
- task routing (system_eval / benchmark / comparison / recommendation)
- runtime allocation via the shared allocator
- stub execution (real memory-system adapters to be added later)
- report persistence to ~/.paperclip/memory_reports/

Company purpose (CN): 记忆管理方法研究实验室。对比研究 thought-retriever、Gbrain、
graphiti、mempalace、supermemory 等记忆系统，为记忆管理 agent 提供最佳实践。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Allocator lives in sibling package
sys.path.insert(0, str(Path(__file__).parent.parent / "runtime_allocator"))
from skill_agent import execute_with_fallback

# Known memory systems under study
KNOWN_MEMORY_SYSTEMS = frozenset({
    "thought-retriever",
    "gbrain",
    "graphiti",
    "mempalace",
    "supermemory",
})


# ── Pydantic models ────────────────────────────────────────────────────────


class MemoryResearchRequest(BaseModel):
    """Input payload from Paperclip to the Memory Research Lab orchestrator."""

    model_config = ConfigDict(extra="ignore")

    request_id: Optional[str] = None
    company_id: Optional[str] = None
    issue_id: Optional[str] = None

    task_type: Literal[
        "system_eval",      # evaluate a single memory system
        "benchmark",        # run a standardized benchmark across systems
        "comparison",       # side-by-side comparison of multiple systems
        "recommendation",   # produce a recommendation report
    ] = "comparison"

    memory_systems: list[str] = Field(
        default_factory=lambda: ["thought-retriever", "gbrain", "graphiti", "mempalace", "supermemory"],
        description="Memory system names to evaluate",
    )

    query_context: str = Field(
        default="",
        description="Additional context or research question for the task",
    )

    output_language: Literal["Chinese", "English"] = "Chinese"

    provider_override: Optional[Literal["minimax", "claudekimi", "openai"]] = None
    model_override: Optional[str] = None
    backend_url_override: Optional[str] = None

    debug: bool = False
    save: bool = True


class MemoryResearchResponse(BaseModel):
    """Normalized response returned to Paperclip."""

    schema_version: Literal["paperclip.memory.run.v1"] = "paperclip.memory.run.v1"

    request_id: str
    company_id: Optional[str] = None
    issue_id: Optional[str] = None

    task_type: str
    memory_systems: list[str] = Field(default_factory=list)

    status: Literal[
        "completed",
        "completed_stub",
        "blocked",
        "error",
    ]

    result: str = ""
    runtime_provider: str = ""
    model_name: str = ""
    route_reason_codes: list[str] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)

    duration_seconds: float = 0.0
    generated_at: str

    artifacts: dict[str, str] = Field(default_factory=dict)

    error_class: Optional[str] = None
    error: Optional[str] = None


# ── Runtime routing (via skill_agent) ──────────────────────────────────────

_TASK_CLASS_MAP: dict[str, str] = {
    "system_eval": "memory_indexing",
    "benchmark": "memory_benchmark",
    "comparison": "memory_comparison",
    "recommendation": "memory_recommendation",
    "memory_benchmark": "memory_benchmark",
    "memory_regression_test": "memory_benchmark",
    "memory_index": "memory_indexing",
    "memory_ablation": "memory_comparison",
}


def _build_execute_params(req: MemoryResearchRequest) -> dict:
    """Build kwargs for execute_with_fallback() from memory research request."""
    task_class = _TASK_CLASS_MAP.get(req.task_type, "memory_indexing")

    params: dict = {
        "task_class": task_class,
        "privacy_tier": "external_cloud",
        "min_quality_tier": "high",
        "needs_json": True,
        "input_tokens_est": 8000,
        "output_tokens_est": 4000,
        "can_degrade": False,
        "high_stakes": False,
    }
    if req.provider_override:
        params["provider_override"] = req.provider_override
    if req.model_override:
        params["model_override"] = req.model_override

    return params


# ── Deterministic benchmark utility ─────────────────────────────────────────


def run_deterministic_memory_benchmark(
    task_type: str,
    memory_systems: list[str],
    input_data: dict,
) -> dict[str, Any]:
    """Run deterministic precision/recall benchmark on provided test cases.

    Expects input_data to contain:
      - cases: list of {case_id, expected_ids: [...], retrieved_ids: [...]}
    """
    cases = input_data.get("cases", [])

    if not cases:
        return {
            "summary": f"{task_type}: no test cases provided. Supply cases with expected_ids and retrieved_ids.",
            "metrics": {"avg_precision": 0.0, "avg_recall": 0.0, "case_count": 0},
            "cases": [],
            "status": "no_cases",
            "template_version": "v1",
        }

    results = []
    for case in cases:
        expected = set(case.get("expected_ids", []))
        retrieved = set(case.get("retrieved_ids", []))

        true_positive = len(expected & retrieved)
        precision = true_positive / max(len(retrieved), 1)
        recall = true_positive / max(len(expected), 1)

        results.append({
            "case_id": case.get("case_id"),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "expected_count": len(expected),
            "retrieved_count": len(retrieved),
            "true_positive": true_positive,
        })

    avg_precision = sum(r["precision"] for r in results) / max(len(results), 1)
    avg_recall = sum(r["recall"] for r in results) / max(len(results), 1)

    return {
        "summary": f"{task_type} completed on {len(results)} cases across {len(memory_systems)} systems.",
        "systems": memory_systems,
        "metrics": {
            "avg_precision": round(avg_precision, 4),
            "avg_recall": round(avg_recall, 4),
            "case_count": len(results),
        },
        "cases": results,
        "status": "completed",
        "template_version": "v1",
    }


# ── Save helpers ────────────────────────────────────────────────────────────


def _save_report(
    req: MemoryResearchRequest,
    result_text: str,
    metadata: dict[str, Any],
    output_dir: str | None = None,
) -> tuple[str, str]:
    """Save memory research result to JSON + markdown files."""
    if output_dir is None:
        output_dir = os.path.expanduser("~/.paperclip/memory_reports")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    systems_tag = "_".join(req.memory_systems[:3])  # cap filename length
    base_name = f"{req.task_type}_{systems_tag}_{timestamp}"

    # JSON
    json_path = output_dir / f"{base_name}.json"
    json_data = {
        **metadata,
        "task_type": req.task_type,
        "memory_systems": req.memory_systems,
        "query_context": req.query_context,
        "output_language": req.output_language,
        "generated_at": datetime.now().isoformat(),
    }
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False))

    # Markdown
    md_path = output_dir / f"{base_name}.md"
    md_content = (
        f"# Memory Research Report\n\n"
        f"- Task: {req.task_type}\n"
        f"- Systems: {', '.join(req.memory_systems)}\n"
        f"- Runtime: {metadata.get('runtime_provider', '?')} / {metadata.get('model_name', '?')}\n"
        f"- Duration: {metadata.get('duration_seconds', 0):.1f}s\n"
        f"- Generated: {datetime.now().isoformat()}\n\n"
        f"{result_text}\n"
    )
    md_path.write_text(md_content)

    return str(json_path), str(md_path)


# ── Main entry point ────────────────────────────────────────────────────────


def run_from_paperclip(payload: dict[str, Any]) -> dict[str, Any]:
    """Main entry point for Paperclip custom adapter."""

    req = MemoryResearchRequest(**payload)
    request_id = req.request_id or str(uuid.uuid4())

    # Validate memory system names (warn but don't block unknown systems)
    unknown = [s for s in req.memory_systems if s.lower() not in KNOWN_MEMORY_SYSTEMS]
    reason_codes: list[str] = []
    if unknown:
        reason_codes.append(f"unknown_systems={','.join(unknown)}")

    # Build messages for the LLM
    system_prompt = (
        f"You are a memory research lab analyst. Task type: {req.task_type}. "
        f"Memory systems under evaluation: {', '.join(req.memory_systems)}. "
        f"Output language: {req.output_language}. "
        f"Provide structured, evidence-based analysis."
    )
    user_content = req.query_context or f"Run {req.task_type} on {', '.join(req.memory_systems)}."
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # Execute via skill_agent with fallback
    exec_params = _build_execute_params(req)
    skill_result = execute_with_fallback(
        messages=messages,
        max_tokens=4096,
        **exec_params,
    )

    provider = skill_result.provider_id
    model = skill_result.model_name
    reason_codes.extend(skill_result.reason_codes)
    fallback_chain = list(skill_result.fallback_chain)

    artifacts: dict[str, str] = {}

    if skill_result.success:
        result_text = skill_result.content
        work_duration = skill_result.total_latency_ms / 1000.0
        status = "completed"
        error_class = None
        error = None

        if req.save:
            try:
                json_path, md_path = _save_report(
                    req,
                    result_text,
                    {
                        "request_id": request_id,
                        "company_id": req.company_id,
                        "issue_id": req.issue_id,
                        "runtime_provider": provider,
                        "model_name": model,
                        "duration_seconds": work_duration,
                        "route_reason_codes": reason_codes,
                    },
                )
                artifacts["json"] = json_path
                artifacts["markdown"] = md_path
            except Exception as save_error:
                reason_codes.append(f"save_failed={save_error.__class__.__name__}")
    else:
        result_text = ""
        work_duration = skill_result.total_latency_ms / 1000.0
        status = "error"
        error_class = skill_result.error_class
        error = skill_result.error

    response = MemoryResearchResponse(
        request_id=request_id,
        company_id=req.company_id,
        issue_id=req.issue_id,
        task_type=req.task_type,
        memory_systems=req.memory_systems,
        status=status,
        result=result_text,
        runtime_provider=provider,
        model_name=model,
        route_reason_codes=reason_codes,
        fallback_chain=fallback_chain,
        duration_seconds=work_duration,
        generated_at=datetime.now().isoformat(),
        artifacts=artifacts,
        error_class=error_class,
        error=error,
    )

    return response.model_dump()


# ── CLI entry point ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Paperclip Memory Research Lab Orchestrator")
    parser.add_argument("--payload", help="JSON payload string")
    parser.add_argument("--payload-file", help="Path to JSON payload file")
    parser.add_argument(
        "--task-type",
        default="comparison",
        choices=["system_eval", "benchmark", "comparison", "recommendation"],
    )
    parser.add_argument(
        "--systems",
        default=None,
        help="Comma-separated memory system names (default: all known)",
    )
    parser.add_argument("--query", default="", help="Research query / context")
    parser.add_argument("--language", default="Chinese", choices=["Chinese", "English"])
    parser.add_argument(
        "--provider",
        default=None,
        choices=["minimax", "claudekimi", "openai"],
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-save", action="store_true", help="Skip saving report files")
    args = parser.parse_args()

    if args.payload_file:
        payload = json.loads(Path(args.payload_file).read_text())
    elif args.payload:
        payload = json.loads(args.payload)
    else:
        systems = None
        if args.systems:
            systems = [s.strip() for s in args.systems.split(",") if s.strip()]
        payload = {
            "task_type": args.task_type,
            "memory_systems": systems,
            "query_context": args.query,
            "output_language": args.language,
            "provider_override": args.provider,
            "debug": args.debug,
            "save": not args.no_save,
        }

    response = run_from_paperclip(payload)
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
