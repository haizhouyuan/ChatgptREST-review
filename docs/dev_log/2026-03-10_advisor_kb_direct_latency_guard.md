# 2026-03-10 Advisor KB Direct Latency Guard

## Why

Live integration testing exposed a production-facing latency failure:

- a simple `/v2/advisor/advise` request with a strong KB hit still spent tens of
  seconds probing dead LLM backends before returning;
- because the API path is synchronous, one slow request could block the single
  worker long enough for unrelated requests to time out behind it.

The root cause was that both `execute_quick_ask()` and `/v2/advisor/ask` treated
KB direct answers as "raw answer first, then always try to naturalize with LLM".
When LLM routing fell through to slow or unreachable providers, the hot path lost
its fast-return property.

## Change

- Added a default-off guard for KB direct synthesis:
  - `chatgptrest/advisor/graph.py`
  - `chatgptrest/api/routes_advisor_v3.py`
- New default behavior:
  - if KB already has a strong answer, return the raw KB answer immediately;
  - only attempt LLM synthesis when `OPENMIND_KB_DIRECT_SYNTHESIS=1`.
- Made `execute_quick_ask()` resolve `_get_llm_fn()` lazily, so the synthesis
  path does not touch slow LLM routing unless synthesis is explicitly enabled.

## Validation

Focused regression:

```bash
./.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py -k 'kb_direct_defaults_to_raw_answer_without_llm_synthesis or kb_direct_can_opt_in_to_llm_synthesis'
./.venv/bin/python -m py_compile chatgptrest/advisor/graph.py chatgptrest/api/routes_advisor_v3.py tests/test_advisor_v3_end_to_end.py
```

New coverage added:

- `/v2/advisor/advise` defaults to raw KB answer without invoking LLM synthesis
- `/v2/advisor/ask` still supports explicit synthesis opt-in

## Follow-up

This change only guards the synchronous KB direct hot path. It does not yet
solve slow long-form routes that are legitimately LLM-heavy; those still need
separate production readiness verification and latency budgeting.
