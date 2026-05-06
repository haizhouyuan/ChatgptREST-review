# Launch Hardening Adjudication v2

**Date**: 2026-03-13
**Author**: Codex
**Branch**: `codex/launch-hardening-20260313`
**Baseline**: `origin/master` at `3ee6d5fd91f2286d0ad07fb745d54205e71c549f`

## Final Judgment

This branch is now a **launch-ready code candidate** for the current repository baseline.

The decisive difference versus `v1` is that the repo is no longer relying on a curated green subset while hiding repo-level or validation-tool regressions. The current branch now has:

- full repository `pytest -q` green
- convergence validation bundle green with `required_ok=true`
- live provider validation green at the runner contract level
- bounded soak / fault / business-flow waves green

## What Was Actually Broken

### 1. Repo-level regressions were real

At the start of this hardening pass, a clean-worktree full-suite `pytest -q` on top of merged `master` was red.

The broken areas were:

- EvoMap transaction/savepoint handling in executor + sandbox merge-back
- execution review fixture drift
- MCP registry snapshot drift

These are now fixed and no longer reproduce in the final full-suite run.

### 2. Report delivery and redact behavior were not launch-safe

`chatgptrest/advisor/report_graph.py` had two real issues:

- redact scanning only inspected prefixes
- Google Docs / Gmail actions bypassed the retryable effects outbox

Resolution:

- redact scan now covers the full draft via chunked scanning
- Google Workspace delivery is now outbox-only
- missing outbox no longer triggers direct side effects

### 3. Recall telemetry and feedback loop were structurally present but not operational

`chatgptrest/api/routes_consult.py` and `chatgptrest/evomap/knowledge/telemetry.py` had a split-brain problem:

- consult recall wrote ad-hoc telemetry tables inline
- shared `TelemetryRecorder` existed but was not actually the return-path contract
- there was no public feedback write path for recall results

Resolution:

- recall telemetry now goes through the shared `TelemetryRecorder`
- mixed KB/EvoMap results use a dedicated `record_search_results(...)`
- `/v1/advisor/recall` now returns `query_id`
- `/v1/advisor/recall/feedback` now records answer feedback and marks used atoms
- telemetry schema now self-migrates `retrieval_events.source`

### 4. The hot-path retrieval gate needed caller-specific tightening

The tempting but wrong fix was to change the generic EvoMap retrieval primitive to `ACTIVE-only` globally.

Deep re-check showed that this breaks explicit graph-query / inspection paths because `retrieve()` is shared by:

- `/v2/context/resolve` personal graph hot path
- `/v2/graph/query` personal graph inspection path
- `/v1/advisor/recall` EvoMap helper

The correct solution is:

- keep the generic retrieval primitive broad enough for graph inspection
- tighten the **launch-critical hot paths** explicitly at the call site

Implemented:

- `routes_consult._evomap_search(...)` now uses explicit `ACTIVE-only` retrieval config
- `cognitive/context_service.py` now uses explicit `ACTIVE-only` retrieval config for injected graph context
- graph-query / inspection path keeps its broader diagnostic visibility

This is the key architectural adjudication from the second pass: the runtime-serving contract and the inspection/debug contract are not the same thing.

### 5. Cognitive health was dishonest in the cold state

`/v2/cognitive/health` previously returned:

```json
{"ok": true, "status": "not_initialized"}
```

That is contractually misleading.

Resolution:

- cold/uninitialized health now returns `ok=false`, `status=not_initialized`
- auth exemption stays intact
- runtime is still not booted by the probe

### 6. The validation runner itself was not trustworthy in a worktree

`ops/run_convergence_validation.py` was defaulting to a global `pytest` when executed from a detached worktree without a local `.venv`, which produced false-red required waves (`ModuleNotFoundError: fastapi`).

Resolution:

- the runner now prefers the `pytest` sibling of the selected `python_bin`
- this makes worktree execution follow the intended virtualenv instead of falling back to a random host-wide install

## Final Evidence

### Full repository regression

Command:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q
```

Result:

- passed on this branch
- warnings only from upstream `websockets/lark_oapi` deprecations

### Convergence validation bundle

Command:

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

Summary:

- bundle path: `artifacts/release_validation/launch_hardening_20260313_full_v2`
- `ok=true`
- `required_ok=true`
- all required waves `wave0-wave4` green
- optional `wave5-wave8_soak` green

### Live provider validation

See:

- `artifacts/release_validation/launch_hardening_20260313_full_v2/live_wave/summary.json`

Observed:

- `gemini=completed`
- `chatgpt=wait_handoff_pending`
- `unexpected_failures=0`

This is acceptable by the live runner contract because at least one provider fully completed and the ChatGPT path reached a recognized handoff state rather than an unexpected failure state.

## Remaining Non-Code Caveats

These are not code regressions on this branch, but they still matter operationally:

- the convergence runner warns when the current shell lacks exported auth tokens; in this environment live discovery still found the env-file tokens under `~/.config/chatgptrest/chatgptrest.env`
- soak evidence here is bounded (`10s`), not a 12h long-run production soak
- the broader knowledge-promotion roadmap still exists, but it is no longer a blocker for this repo state to pass its current launch gates

## Final Decision

For the current repository standard, this branch is ready to merge as the no-defect launch-hardening tranche.
