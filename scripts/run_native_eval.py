#!/usr/bin/env python3
"""Run CcNativeExecutor evaluation with EvoMap observability.

Usage:
    python scripts/run_native_eval.py --level L1        # Quick: 3 scenarios
    python scripts/run_native_eval.py --level L2        # Medium: 3 scenarios
    python scripts/run_native_eval.py --scenario idempotency_bug_hunt
    python scripts/run_native_eval.py --all             # All 13 scenarios
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatgptrest.kernel.cc_native import CcNativeExecutor
from chatgptrest.kernel.cc_executor import CcTask
from chatgptrest.kernel.cc_eval_runner import (
    ALL_SCENARIOS, SCENARIOS_BY_LEVEL, EvalScenario, score_output,
)
from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.evomap.signals import Signal, SignalType, SignalDomain
from chatgptrest.kernel.event_bus import EventBus
from chatgptrest.kernel.memory_manager import MemoryManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("eval")


def build_infrastructure():
    """Create observer, event_bus, memory instances."""
    evo_db = os.environ.get(
        "OPENMIND_EVOMAP_DB",
        os.path.expanduser("~/.openmind/evomap.db"),
    )
    observer = EvoMapObserver(db_path=evo_db)

    event_bus_db = os.environ.get(
        "OPENMIND_EVENTBUS_DB",
        os.path.expanduser("~/.openmind/events.db"),
    )
    event_bus = EventBus(db_path=event_bus_db)

    memory_db = os.environ.get(
        "OPENMIND_MEMORY_DB",
        os.path.expanduser("~/.openmind/memory.db"),
    )
    memory = MemoryManager(db_path=memory_db)

    return observer, event_bus, memory


async def run_scenario(
    executor: CcNativeExecutor,
    scenario: EvalScenario,
    index: int,
    total: int,
) -> dict:
    """Run a single scenario and return scored result."""
    logger.info(
        "[%d/%d] Running: %s (%s/%s)",
        index, total, scenario.name, scenario.complexity, scenario.task_type,
    )

    task = CcTask(
        task_type=scenario.task_type,
        description=scenario.description,
        files=scenario.files,
        timeout=scenario.timeout,
    )

    started_at = time.time()
    result = await executor.dispatch_headless(task)
    elapsed = time.time() - started_at

    # Score the output
    quality_detail = score_output(
        result.output or "",
        scenario,
        result.elapsed_seconds,
        result.findings_count,
    )

    passed = (
        result.ok
        and quality_detail["total"] >= scenario.expected_min_quality
    )

    entry = {
        "scenario": scenario.name,
        "complexity": scenario.complexity,
        "task_type": scenario.task_type,
        "passed": passed,
        "ok": result.ok,
        "quality_total": quality_detail["total"],
        "quality_detail": quality_detail,
        "elapsed_seconds": round(elapsed, 1),
        "model_used": result.model_used,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "num_turns": result.num_turns,
        "tools_used": result.tools_used or [],
        "trace_id": result.trace_id,
        "error": result.error or "",
        "output_preview": (result.output or "")[:300],
    }

    status = "✅ PASS" if passed else "❌ FAIL"
    logger.info(
        "  %s | quality=%.2f | tokens=%d+%d | turns=%d | %.1fs",
        status, quality_detail["total"],
        result.input_tokens, result.output_tokens,
        result.num_turns, elapsed,
    )

    return entry


async def run_eval(scenarios: list[EvalScenario]):
    """Run all selected scenarios and produce a report."""
    observer, event_bus, memory = build_infrastructure()

    executor = CcNativeExecutor(
        observer=observer,
        event_bus=event_bus,
        memory=memory,
    )

    results = []
    total = len(scenarios)

    for i, scenario in enumerate(scenarios, 1):
        entry = await run_scenario(executor, scenario, i, total)
        results.append(entry)
        # Short pause between scenarios
        if i < total:
            await asyncio.sleep(2)

    # ── Aggregation ─────────────────────────────────────────────

    passed = sum(1 for r in results if r["passed"])
    total_tokens = sum(r["input_tokens"] + r["output_tokens"] for r in results)
    total_time = sum(r["elapsed_seconds"] for r in results)

    summary = {
        "total_scenarios": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / max(total, 1), 2),
        "avg_quality": round(
            sum(r["quality_total"] for r in results) / max(total, 1), 3
        ),
        "total_tokens": total_tokens,
        "total_time_seconds": round(total_time, 1),
        "results": results,
    }

    # ── EvoMap signal count ─────────────────────────────────────

    try:
        signal_stats = observer.aggregate_by_type()
        summary["evomap_signals"] = signal_stats
        logger.info("EvoMap signals recorded: %s", signal_stats)
    except Exception as e:
        logger.warning("EvoMap query failed: %s", e)

    # ── Memory check ────────────────────────────────────────────

    try:
        from chatgptrest.kernel.memory_manager import MemoryTier
        episodic = memory.get_episodic(query="cc_dispatch", limit=100)
        summary["episodic_records"] = len(episodic)
        logger.info("Episodic memory records: %d", len(episodic))
    except Exception as e:
        logger.warning("Memory query failed: %s", e)

    # ── Write report ────────────────────────────────────────────

    report_path = os.path.expanduser("~/.openmind/eval_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    logger.info("="*60)
    logger.info("EVAL COMPLETE: %d/%d passed (%.0f%%)", passed, total, passed/max(total,1)*100)
    logger.info("Avg quality: %.3f | Total tokens: %d | Time: %.0fs",
                summary["avg_quality"], total_tokens, total_time)
    logger.info("Report: %s", report_path)
    logger.info("="*60)

    # Print summary table
    print("\n" + "="*80)
    print(f"{'Scenario':<30} {'Level':<5} {'Status':<8} {'Quality':<10} {'Tokens':<10} {'Time':>6}")
    print("-"*80)
    for r in results:
        status = "✅" if r["passed"] else "❌"
        print(f"{r['scenario']:<30} {r['complexity']:<5} {status:<8} "
              f"{r['quality_total']:<10.3f} "
              f"{r['input_tokens']+r['output_tokens']:<10} "
              f"{r['elapsed_seconds']:>5.1f}s")
    print("="*80)

    return summary


def main():
    parser = argparse.ArgumentParser(description="CcNativeExecutor Eval Runner")
    parser.add_argument("--level", choices=["L1", "L2", "L3", "L4"], help="Run scenarios at this level")
    parser.add_argument("--scenario", help="Run a specific scenario by name")
    parser.add_argument("--all", action="store_true", help="Run all 13 scenarios")
    args = parser.parse_args()

    if args.scenario:
        scenarios = [s for s in ALL_SCENARIOS if s.name == args.scenario]
        if not scenarios:
            print(f"Unknown scenario: {args.scenario}")
            print("Available:", ", ".join(s.name for s in ALL_SCENARIOS))
            sys.exit(1)
    elif args.level:
        scenarios = SCENARIOS_BY_LEVEL.get(args.level, [])
    elif args.all:
        scenarios = ALL_SCENARIOS
    else:
        # Default: L1 (quick smoke test)
        scenarios = SCENARIOS_BY_LEVEL["L1"]
        logger.info("No level specified, defaulting to L1 (3 scenarios)")

    asyncio.run(run_eval(scenarios))


if __name__ == "__main__":
    main()
