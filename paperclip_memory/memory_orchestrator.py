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
from allocator_mvp import (
    allocate,
    PrivacyTier,
    QualityTier,
    QuotaLedger,
    RouteRequest,
)

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


# ── Runtime routing ─────────────────────────────────────────────────────────


def _provider_endpoint(provider: str) -> tuple[str, str, str]:
    """Return (provider_id, default_model, endpoint)."""
    if provider == "minimax":
        return (
            "minimax",
            "MiniMax-M2.7-highspeed",
            os.getenv("MINIMAX_API_HOST", "https://api.minimaxi.com").rstrip("/") + "/v1",
        )
    if provider == "claudekimi":
        return (
            "claudekimi",
            "mimo-v2.5-pro",
            os.getenv("CLAUDEKIMI_ENDPOINT", "http://127.0.0.1:8080/v1"),
        )
    if provider == "openai":
        return ("openai", "gpt-4.1", os.getenv("OPENAI_BASE_URL", ""))
    raise ValueError(f"Unsupported provider: {provider}")


def _route_runtime(req: MemoryResearchRequest) -> tuple[str, str, str, list[str], list[str]]:
    """Route memory research tasks.

    Research tasks need quality over speed, so default to claudekimi (CRITICAL tier).
    The allocator is called for audit logging but claudekimi is the hard default.
    """
    ledger = QuotaLedger()

    route_req = RouteRequest(
        task_class="memory_indexing",
        privacy_tier_required=PrivacyTier.EXTERNAL_CLOUD,
        min_quality_tier=QualityTier.HIGH,
        needs_tool_calling=True,
        needs_json=True,
        input_tokens_est=8000,
        output_tokens_est=4000,
        can_degrade=False,
        high_stakes=False,
    )

    decision = allocate(route_req, ledger=ledger)

    reason_codes = list(decision.reason_codes)
    fallback_chain = list(decision.fallback_chain)

    # Honor explicit provider override
    if req.provider_override:
        provider, model, endpoint = _provider_endpoint(req.provider_override)
        reason_codes.append(f"provider_override={req.provider_override}")
        return provider, model, endpoint, reason_codes, fallback_chain

    # Default: claudekimi for research quality
    if decision.provider_id != "claudekimi":
        reason_codes.append(
            f"allocator_selected_{decision.provider_id}_but_memory_research_pinned_to_claudekimi"
        )

    provider, model, endpoint = _provider_endpoint("claudekimi")
    return provider, model, endpoint, reason_codes, fallback_chain


# ── Stub execution ──────────────────────────────────────────────────────────


def _run_stub(
    task_type: str,
    memory_systems: list[str],
    query_context: str,
    output_language: str,
    provider: str,
    model: str,
) -> tuple[str, float]:
    """Stub implementation that returns a structured placeholder.

    Returns (result_text, duration_seconds).
    Real adapters (thought-retriever, graphiti, etc.) will replace this later.
    """
    start = datetime.now()

    lang_header = "记忆研究报告" if output_language == "Chinese" else "Memory Research Report"

    if task_type == "system_eval":
        system = memory_systems[0] if memory_systems else "unknown"
        body = (
            f"## {lang_header}: {system} 评估\n\n"
            f"**任务类型**: system_eval\n"
            f"**目标系统**: {system}\n"
            f"**查询上下文**: {query_context or '(未指定)'}\n\n"
            f"### 评估维度\n"
            f"1. 检索精度 (Retrieval Precision)\n"
            f"2. 记忆持久性 (Memory Persistence)\n"
            f"3. 上下文窗口利用率 (Context Window Utilization)\n"
            f"4. 增量更新效率 (Incremental Update Efficiency)\n"
            f"5. 多跳推理能力 (Multi-hop Reasoning)\n\n"
            f"> STUB: 真实评估结果将在 {system} 适配器接入后生成。\n"
        )
    elif task_type == "benchmark":
        body = (
            f"## {lang_header}: 标准基准测试\n\n"
            f"**任务类型**: benchmark\n"
            f"**测试系统**: {', '.join(memory_systems)}\n"
            f"**查询上下文**: {query_context or '(未指定)'}\n\n"
            f"### 基准指标\n"
            f"| 系统 | 召回率 | 精确率 | 延迟(ms) | 成本/千次 |\n"
            f"|------|--------|--------|----------|----------|\n"
        )
        for sys_name in memory_systems:
            body += f"| {sys_name} | -- | -- | -- | -- |\n"
        body += f"\n> STUB: 真实基准数据将在各系统适配器接入后填充。\n"
    elif task_type == "comparison":
        body = (
            f"## {lang_header}: 多系统对比分析\n\n"
            f"**任务类型**: comparison\n"
            f"**对比系统**: {', '.join(memory_systems)}\n"
            f"**查询上下文**: {query_context or '(未指定)'}\n\n"
            f"### 对比维度\n"
            f"- 架构模式 (Architecture Pattern)\n"
            f"- 记忆组织方式 (Memory Organization)\n"
            f"- 检索策略 (Retrieval Strategy)\n"
            f"- 适用场景 (Best-fit Scenarios)\n"
            f"- 局限性 (Limitations)\n\n"
            f"> STUB: 真实对比分析将在各系统适配器接入后生成。\n"
        )
    else:  # recommendation
        body = (
            f"## {lang_header}: 最佳实践推荐\n\n"
            f"**任务类型**: recommendation\n"
            f"**评估范围**: {', '.join(memory_systems)}\n"
            f"**查询上下文**: {query_context or '(未指定)'}\n\n"
            f"### 推荐内容\n"
            f"1. 场景化选型建议\n"
            f"2. 混合架构方案\n"
            f"3. 性能优化策略\n"
            f"4. 成本效益分析\n\n"
            f"> STUB: 真实推荐将在基准数据积累后生成。\n"
        )

    duration = (datetime.now() - start).total_seconds()
    return body, duration


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

    # Route runtime
    provider, default_model, default_endpoint, route_reasons, fallback_chain = _route_runtime(req)
    reason_codes.extend(route_reasons)

    model = req.model_override or default_model

    try:
        result_text, stub_duration = _run_stub(
            task_type=req.task_type,
            memory_systems=req.memory_systems,
            query_context=req.query_context,
            output_language=req.output_language,
            provider=provider,
            model=model,
        )
        status = "completed_stub"
        error_class = None
        error = None
    except Exception as e:
        result_text = ""
        stub_duration = 0.0
        status = "error"
        error_class = e.__class__.__name__
        error = str(e)
        reason_codes.append(f"execution_error={error_class}")

    # Save artifacts
    artifacts: dict[str, str] = {}
    if req.save and status != "error":
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
                    "duration_seconds": stub_duration,
                    "route_reason_codes": reason_codes,
                },
            )
            artifacts["json"] = json_path
            artifacts["markdown"] = md_path
        except Exception as save_error:
            reason_codes.append(f"save_failed={save_error.__class__.__name__}")

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
        duration_seconds=stub_duration,
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
