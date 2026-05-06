## Summary

This tranche fixes `claudeminmax` / `claudegac` result parsing in the planning coding-agent lane.

The real product symptom was misleading failure on formal planning runs: the Claude-family wrapper returned a successful JSON envelope with `structured_output.answer`, but ChatgptREST only read top-level `answer`. As a result, the execution produced usable content yet was projected as an empty-answer failure.

## What Changed

- `chatgptrest/controller/coding_agent_executor.py`
  - Added `_extract_answer_summary()` to normalize both:
    - direct `{answer, summary}`
    - wrapper envelope `{structured_output: {answer, summary}}`
  - Switched `run_coding_agent_executor()` to use normalized extraction instead of reading only top-level keys.
- `tests/test_coding_agent_executor.py`
  - Added regression for Claude wrapper envelope parsing.

## Why

Formal executor preflight showed the issue clearly:

- `codex2` produced top-level `answer` and was marked `ok=true`
- `claudeminmax` and `claudegac` returned successful wrapper JSON with populated `structured_output.answer`
- The runner still wrote `ok=false` because top-level `answer` was empty

That is a parser bug, not a model-quality or authentication problem.

## Verification

- `python3 -m py_compile chatgptrest/controller/coding_agent_executor.py`
- `./.venv/bin/pytest -q tests/test_coding_agent_executor.py tests/test_controller_engine_planning_pack.py tests/test_routes_agent_v3.py`

## Product Impact

After this fix, formally selected Claude-family coding executors are no longer misclassified as empty-answer failures when their wrapper returns the canonical `structured_output` envelope.

This unblocks the next validation step: re-running the formal OpenClaw planning task on an authenticated Claude-family executor and checking whether the result is directly usable through the formal product path.
