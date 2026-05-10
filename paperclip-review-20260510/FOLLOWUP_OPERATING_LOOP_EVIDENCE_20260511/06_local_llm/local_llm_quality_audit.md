# Local LLM Quality Audit

Generated: 2026-05-11T00:54:00+08:00  
Controller: codex_parent

## Result

HomePC Ollama is reachable and completed multiple 36-row research-only benchmark
runs.

However, this is not a production-route pass:

- Initial run without `think:false` produced many empty responses for Qwen
  models because content went into the `thinking` field.
- Corrected run with `think:false` improved strict JSON results to `22 / 36`.
- JSON-mode run with `num_predict=800` improved strict JSON results to `33 / 36`.
- `3 / 36` rows still require parser/scorer hardening before any automation use.

## Evidence

- Corrected summary:
  `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-11_codex_parent_8h_operating_program/06_local_llm/local_llm_benchmark_summary.json`
- Corrected rows:
  `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-11_codex_parent_8h_operating_program/06_local_llm/local_llm_benchmark_rows.jsonl`
- Prior JSON-mode 220-token run:
  `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-11_codex_parent_8h_operating_program/06_local_llm/local_llm_benchmark_summary_json_mode_220_tokens.json`
  `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-11_codex_parent_8h_operating_program/06_local_llm/local_llm_benchmark_rows_json_mode_220_tokens.jsonl`
- Preserved initial thinking-trap evidence:
  `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-11_codex_parent_8h_operating_program/06_local_llm/local_llm_benchmark_summary_initial_thinking_trap.json`
  `/vol1/1000/projects/toyresearch/docs/paperclip_ops_runs/2026-05-11_codex_parent_8h_operating_program/06_local_llm/local_llm_benchmark_rows_initial_thinking_trap.jsonl`

## Decision

Status: `research_only_continue`.

Allowed next step: improve prompt/scorer/parser around the remaining 3 non-strict
rows and rerun a controlled benchmark.

Forbidden next step: production route mutation, Finbot/Planning/Governance
authority use, memory authority promotion, or autonomous task execution.
