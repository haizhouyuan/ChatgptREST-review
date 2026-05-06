## Summary

This follow-up revision corrects the main weakness in `v1`: shrinking the Codex prompt was only a cost stopgap, not the root fix.

The deeper issue is that ChatgptREST still had active automatic paths that route runtime/UI failures into `repair.autofix`, and `repair.autofix` still defaulted to "open Codex first" even for well-known failure signatures that already have deterministic recovery actions.

## Reflection

The `v1` change improved cost but attacked the terminal symptom.

- It reduced per-run token burn.
- It did **not** reduce how often the system decides to invoke Codex.
- It left the core execution policy unchanged for common runtime failures.

That was incomplete because the expensive behavior was not only "prompt too big"; it was also "too many known runtime cases still escalate into a model turn".

## Live Topology Findings

Current live state on YogaS2 shows two automatic recovery surfaces are active:

- worker auto-submit is enabled in `~/.config/chatgptrest/chatgptrest.env`
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX=1`
- maint daemon self-heal is enabled in the user systemd drop-in
  - `chatgptrest-maint-daemon.service.d/30-self-heal.conf`
  - includes `--enable-codex-sre-autofix`

Observed recent job mix from `state/jobdb.sqlite3`:

- `repair.check` by `maint_daemon`: `537` jobs in the last 7 days
- `repair.autofix` by `worker_auto_codex_autofix`: `52` jobs in the last 7 days

This means cost pressure is not just a prompt-formatting problem. It is also a routing-policy problem.

## Root Cause

Before this revision:

- worker auto-submit could create `repair.autofix` directly
- `repair.autofix` always prepared a Codex-first path unless later fallback logic took over
- the existing deterministic planner `_fallback_autofix_actions()` only ran **after** Codex failure

That ordering was backwards for recurring runtime cases such as:

- CDP/browser disconnects
- blocked runtime state
- wait-stage no-progress stalls
- Gemini region/proxy mismatch

These are not "understand the repo" problems first. They are "execute a bounded runtime recovery action set" problems first.

## Changes

### `repair.autofix`

- Added `CHATGPTREST_CODEX_AUTOFIX_ENABLE_HEURISTIC_FAST_PATH` (default `true`).
- Moved deterministic runtime planning ahead of Codex execution.
- If the existing runtime heuristics already produce a valid action plan, executor now:
  - skips Codex entirely
  - skips prompt assembly entirely
  - records `codex.skipped=true`
  - records `codex.skip_reason=heuristic_fast_path_before_codex`
  - records `fallback.reason=heuristic_fast_path_before_codex`
- Codex remains available for ambiguous or non-heuristic cases.

### Scope of the Fix

This revision does **not** yet disable either auto-trigger source.

- worker auto-submit still exists
- maint daemon self-heal still exists

What changed is the expensive part of the execution policy:

- known runtime/UI incidents no longer have to pay a model turn before recovery starts

## Why This Is Closer To Root Fix

This revision changes the escalation order from:

1. create `repair.autofix`
2. call Codex
3. only then fall back to deterministic runtime actions

to:

1. create `repair.autofix`
2. attempt deterministic runtime plan first
3. call Codex only when the heuristic fast path does not cover the case

That is the right ordering for operational incidents.

## Verification

- `pytest -q tests/test_repair_provider_tools.py tests/test_repair_autofix_codex_fallback.py`
  - `18 passed`
- Added regression coverage for:
  - heuristic fast path skipping Codex before prompt generation
  - Codex secondary fallback remaining opt-in
  - explicit opt-out of heuristic fast path in tests that verify Codex prompt/model wiring

## Remaining Work

This is materially better, but still not the final word.

The next systemic step should be reducing duplicate trigger surfaces:

- choose one canonical automatic runtime-repair submitter
- either worker auto-submit or maint daemon self-heal should become the default authority, not both

Until that consolidation is done, the system can still create too many repair jobs even if those jobs are now cheaper and more deterministic.
