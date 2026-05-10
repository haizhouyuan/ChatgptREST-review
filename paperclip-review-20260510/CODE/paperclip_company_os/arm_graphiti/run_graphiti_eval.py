#!/usr/bin/env python3
"""Run Graphiti no-write temporal projection evaluation against the 50-case corpus.

This script:
1. Connects to a temporary Neo4j instance
2. Loads the 50-case corpus
3. Projects each case into Graphiti as episodes
4. Queries Graphiti for each case
5. Scores results against expected behavior
6. Produces raw outputs, traces, scorer results, provenance, and rollup report

Note: Uses mock LLM/embedder/reranker clients to avoid requiring OpenAI API key.
Results reflect pipeline structural correctness; extraction quality requires real LLM.
"""

import asyncio
import json
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from graphiti_core import Graphiti
from graphiti_mock_llm import MockLLMClient
from graphiti_mock_embedder import MockEmbedderClient
from graphiti_mock_reranker import MockRerankerClient

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

CORPUS_PATH = Path(__file__).parents[1] / "corpus" / "memory_full_corpus_50.jsonl"
OUTPUT_DIR = Path(__file__).parent
RAW_DIR = OUTPUT_DIR / "raw_outputs"
TRACE_DIR = OUTPUT_DIR / "traces"
SCORER_DIR = OUTPUT_DIR / "scorer"
PROVENANCE_DIR = OUTPUT_DIR / "provenance"
ROLLUP_DIR = OUTPUT_DIR / "rollup"


def load_corpus() -> list[dict]:
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def score_case(case: dict, search_results: list, trace_log: list[dict]) -> dict:
    """Score a single case based on search results and trace log.

    With mock LLM, we score conservatively based on structural evidence:
    - Did Graphiti return any results?
    - Did the trace log show the expected operations?
    - Did the query execute without errors?
    """
    scoring_dimensions = case.get("scoring_dimensions", [])
    scores = {}

    # Structural pass/fail scoring
    has_results = len(search_results) > 0
    no_errors = all(t.get("status") != "error" for t in trace_log)

    for dim in scoring_dimensions:
        if dim in ("current_truth_accuracy", "stale_fact_rejection", "task_intent_fit",
                   "workflow_orchestration", "scope_correctness", "privacy_safety",
                   "prompt_injection_resistance", "rollbackability", "pointer_recall"):
            # Binary dimensions: mock LLM cannot reliably pass these
            scores[dim] = {
                "score": 0,  # Mock LLM cannot demonstrate actual correctness
                "max": 1,
                "reason": "Mock LLM pipeline: structural run only, no semantic verification possible."
            }
        elif dim in ("provenance_precision", "reasoning_quality", "recovery_usefulness", "human_usefulness"):
            # 0-2 scale dimensions
            scores[dim] = {
                "score": 0,
                "max": 2,
                "reason": "Mock LLM pipeline: structural run only, no semantic verification possible."
            }
        elif dim == "token_efficiency":
            scores[dim] = {
                "score": 0,
                "max": 1,
                "reason": "Not measured in mock pipeline."
            }
        else:
            scores[dim] = {
                "score": 0,
                "max": 1,
                "reason": f"Unknown dimension: {dim}"
            }

    # Pipeline health bonus: if the query executed without errors, mark pipeline_ok
    scores["pipeline_health"] = {
        "score": 1 if no_errors else 0,
        "max": 1,
        "reason": "Query executed without exceptions." if no_errors else "Errors occurred during execution."
    }

    return scores


async def run_evaluation() -> int:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting Graphiti evaluation")
    print(f"Corpus: {CORPUS_PATH}")
    print(f"Output dir: {OUTPUT_DIR}")

    cases = load_corpus()
    print(f"Loaded {len(cases)} cases")

    # Initialize Graphiti with mock clients
    llm = MockLLMClient()
    embedder = MockEmbedderClient()
    reranker = MockRerankerClient()
    graphiti = Graphiti(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        llm_client=llm,
        embedder=embedder,
        cross_encoder=reranker,
    )

    # Ensure indices exist
    try:
        await graphiti.build_indices_and_constraints()
        print("Graphiti indices ready")
    except Exception as e:
        print(f"Index build warning (may already exist): {e}")

    all_scores = {}
    provenance_records = []

    for idx, case in enumerate(cases, 1):
        case_id = case["case_id"]
        print(f"  Case {idx}/{len(cases)}: {case_id}")

        trace_log = []
        search_results = []

        try:
            # Step 1: Project case as episode(s)
            # Current truth source = primary episode
            # Stale input = older episode with earlier timestamp
            trace_log.append({"step": "project_current_truth", "case_id": case_id, "status": "started"})

            current_truth_content = case["input_summary"] + "\n\nExpected: " + case["expected_behavior"]
            await graphiti.add_episode(
                name=f"{case_id}_current_truth",
                episode_body=current_truth_content,
                source_description=f"case:{case_id}:current_truth",
                reference_time=datetime.now(timezone.utc),
            )
            trace_log.append({"step": "project_current_truth", "case_id": case_id, "status": "ok"})

            # Step 2: Project stale/conflict input as older episode
            for stale_input in case.get("stale_or_conflict_inputs", []):
                trace_log.append({"step": "project_stale", "case_id": case_id, "status": "started"})
                await graphiti.add_episode(
                    name=f"{case_id}_stale",
                    episode_body=stale_input,
                    source_description=f"case:{case_id}:stale",
                    reference_time=datetime.now(timezone.utc),
                )
                trace_log.append({"step": "project_stale", "case_id": case_id, "status": "ok"})

            # Step 3: Query Graphiti
            trace_log.append({"step": "query", "case_id": case_id, "status": "started"})
            query_text = case["input_summary"]
            search_results = await graphiti.search(
                query=query_text,
                num_results=5,
            )
            trace_log.append({"step": "query", "case_id": case_id, "status": "ok", "result_count": len(search_results)})

        except Exception as e:
            trace_log.append({"step": "error", "case_id": case_id, "status": "error", "error": str(e), "traceback": traceback.format_exc()})
            print(f"    ERROR: {e}")

        # Step 4: Score
        case_scores = score_case(case, search_results, trace_log)
        all_scores[case_id] = case_scores

        # Step 5: Write raw output
        raw_output = {
            "case_id": case_id,
            "case": case,
            "search_results": [r.model_dump() if hasattr(r, "model_dump") else str(r) for r in search_results],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(RAW_DIR / f"case-{idx}-{case_id}.json", "w", encoding="utf-8") as f:
            json.dump(raw_output, f, indent=2, ensure_ascii=False)

        # Step 6: Write trace
        with open(TRACE_DIR / f"trace-{idx}-{case_id}.jsonl", "w", encoding="utf-8") as f:
            for entry in trace_log:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Step 7: Provenance
        provenance_records.append({
            "case_id": case_id,
            "source_authority_paths": case.get("source_authority_paths", []),
            "required_artifact_paths": case.get("required_artifact_paths", []),
            "retrieved_from_graphiti": [r.model_dump() if hasattr(r, "model_dump") else str(r) for r in search_results],
        })

    # Step 8: Write scorer output
    with open(SCORER_DIR / "scores-graphiti.json", "w", encoding="utf-8") as f:
        json.dump({
            "arm": "graphiti",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case_count": len(cases),
            "scores": all_scores,
            "pipeline": "mock_llm",
            "note": "Scores reflect structural pipeline health only. Semantic correctness requires real LLM.",
        }, f, indent=2, ensure_ascii=False)

    # Step 9: Write provenance
    with open(PROVENANCE_DIR / "sources-graphiti.md", "w", encoding="utf-8") as f:
        f.write("# Graphiti Provenance\n\n")
        for rec in provenance_records:
            f.write(f"## {rec['case_id']}\n\n")
            f.write(f"- Source authority paths: {', '.join(rec['source_authority_paths'])}\n")
            f.write(f"- Required artifact paths: {', '.join(rec['required_artifact_paths'])}\n")
            f.write(f"- Graphiti retrieved: {len(rec['retrieved_from_graphiti'])} results\n\n")

    # Step 10: Rollup report
    pipeline_ok_count = sum(1 for s in all_scores.values() if s.get("pipeline_health", {}).get("score", 0) > 0)
    dimension_totals = Counter()
    dimension_counts = Counter()
    for case_id, scores in all_scores.items():
        for dim, result in scores.items():
            if dim == "pipeline_health":
                continue
            dimension_totals[dim] += result.get("score", 0)
            dimension_counts[dim] += result.get("max", 1)

    with open(ROLLUP_DIR / "arm_report.md", "w", encoding="utf-8") as f:
        f.write("# Arm 3: Graphiti No-Write TemporalProjection Rollup\n\n")
        f.write(f"**Date:** {datetime.now(timezone.utc).isoformat()}\n\n")
        f.write(f"**Cases:** {len(cases)}\n\n")
        f.write(f"**Pipeline:** Mock LLM / Mock Embedder / Mock Reranker\n\n")
        f.write("## Quarantine Decision\n\n")
        f.write("**QUARANTINED** — Mock LLM pipeline only.\n\n")
        f.write("This arm ran with deterministic mock LLM clients to demonstrate the evaluation pipeline. ")
        f.write("Actual semantic scoring requires a real LLM (OpenAI API key or local model endpoint). ")
        f.write("All outputs are structural evidence only.\n\n")
        f.write("## Pipeline Health\n\n")
        f.write(f"- Cases run: {len(cases)}\n")
        f.write(f"- Pipeline OK: {pipeline_ok_count}/{len(cases)}\n")
        f.write(f"- Errors: {len(cases) - pipeline_ok_count}\n\n")
        f.write("## Dimension Scores (Structural Only)\n\n")
        f.write("| Dimension | Score | Max | % |\n")
        f.write("|---|---|---|---|\n")
        for dim in sorted(dimension_totals.keys()):
            total = dimension_totals[dim]
            count = dimension_counts[dim]
            pct = (total / count * 100) if count > 0 else 0
            f.write(f"| {dim} | {total} | {count} | {pct:.1f}% |\n")
        f.write("\n## Next Action\n\n")
        f.write("1. Provide OPENAI_API_KEY or configure local LLM endpoint.\n")
        f.write("2. Re-run with real LLM client for semantic scoring.\n")
        f.write("3. Compare results against Paperclip-native baseline (Arm 1).\n")

    await graphiti.close()
    print(f"[{datetime.now(timezone.utc).isoformat()}] Evaluation complete")
    print(f"  Raw outputs: {len(list(RAW_DIR.glob('*.json')))}")
    print(f"  Traces: {len(list(TRACE_DIR.glob('*.jsonl')))}")
    print(f"  Scorer: {SCORER_DIR / 'scores-graphiti.json'}")
    print(f"  Provenance: {PROVENANCE_DIR / 'sources-graphiti.md'}")
    print(f"  Rollup: {ROLLUP_DIR / 'arm_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_evaluation()))
