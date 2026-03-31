# Launch Hardening Walkthrough v1

**Date**: 2026-03-13
**Branch**: `codex/launch-hardening-20260313`

## Scope

This walkthrough records the final hardening tranche after `v1` adjudication had already identified the remaining launch blockers.

The goal of this tranche was not to propose more architecture. It was to:

1. turn the remaining blocker list into code changes
2. rerun the entire repository regression suite
3. rerun the convergence validation gate on the final branch state
4. only then decide whether the branch is actually launch-ready

## Main Technical Decisions

### 1. Report path: fix the real hazards, not the symptoms

`report_graph.py` was hardened in two ways:

- full-document chunked redact scanning
- outbox-only Google Workspace delivery

This removed the two concrete launch hazards from the report path:

- sensitive content in tail sections bypassing review
- direct side effects bypassing replay-safe delivery machinery

### 2. Retrieval gating had to be caller-specific

The second pass changed my own approach.

The naive change was to make the generic EvoMap `retrieve()` primitive `ACTIVE-only`. That looked attractive on paper, but it broke explicit graph-query paths because the same primitive is shared by:

- launch-critical context injection
- explicit graph inspection endpoints

After re-checking failing tests and the actual call graph, the final decision was:

- keep the generic retrieval primitive broad
- tighten launch-critical callers explicitly

That is why the final code gates `routes_consult` and `context_service`, not the entire library default.

### 3. The feedback loop needed an actual contract, not dead-code primitives

`telemetry.py` already had the right building blocks, but recall was still writing ad-hoc rows.

The final shape is:

- recall emits a shared-schema `query_id`
- clients can send structured feedback back with that `query_id`
- telemetry marks used atoms and stores answer feedback in the same knowledge DB

This is the first branch state where the recall path has a real operational telemetry contract instead of only dormant methods.

### 4. Validation tooling itself needed repair

The convergence runner was giving false failures in a worktree because it escaped the intended virtualenv and picked up a host-global `pytest`.

That mattered because a broken gate cannot be used as launch evidence.

The final fix binds the runner to the same environment as `python_bin`, which is what the release process actually expects.

## Validation Performed

### Repository-wide regression

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q
```

Outcome:

- green on final branch state

### Curated convergence gate

```bash
CHATGPTREST_SOAK_SECONDS=10 \
  /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/run_convergence_validation.py \
  --output-dir artifacts/release_validation/launch_hardening_20260313_full_v2 \
  --include-wave4 \
  --include-wave5 \
  --include-fault \
  --include-soak \
  --include-live
```

Outcome:

- required waves green
- optional waves green
- live runner acceptable
- bounded soak green

## Files Touched In The Final Tranche

- `chatgptrest/api/routes_cognitive.py`
- `chatgptrest/api/routes_consult.py`
- `chatgptrest/cognitive/context_service.py`
- `chatgptrest/evomap/knowledge/retrieval.py`
- `chatgptrest/evomap/knowledge/telemetry.py`
- `ops/run_convergence_validation.py`
- `tests/test_advisor_consult.py`
- `tests/test_cognitive_api.py`
- `tests/test_convergence_validation_runner.py`
- `tests/test_evomap_runtime_contract.py`
- `tests/test_openmind_memory_business_flow.py`

## Final State

This branch ended with:

- repo regression green
- convergence bundle green
- no known remaining code blockers from the `v1` hardening list

The remaining caveats are operational scope items, not red code paths:

- live validation still accepts ChatGPT `wait_handoff_pending` as a valid non-failure state
- soak here is bounded, not a 12h production observation window
