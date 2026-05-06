## Summary

This document freezes the implementation plan for ChatgptREST repair/SRE Codex cost control and fallback governance.

Goal:

- keep repair quality acceptable for known runtime incidents
- reduce unnecessary Codex spend
- make fallback behavior explicit instead of accidental
- stop Codex CLI batch runs from drifting onto ambient `OPENAI_*` API-key lanes

This plan is executable. The follow-on implementation must update this document if scope changes.

## Current Facts

Observed on 2026-04-08:

- `repair.autofix` already defaults to `gpt-5.3-codex-spark`; see `chatgptrest/core/repair_jobs.py`.
- `repair.autofix` already has heuristic fast path before Codex, plus heuristic fallback after Codex failure; see `chatgptrest/executors/repair.py`.
- `sre.fix_request` already has heuristic fast path before Codex, but its Codex phase still lacks an explicit default model/reasoning profile and can fail the whole controller job when Codex is unavailable.
- `repair.open_pr` still relies on ambient model selection unless the caller explicitly sets `params.model`; it has no mode-based reasoning policy.
- recent `repair.autofix` jobs were overwhelmingly runtime incidents such as `TargetClosed`, CDP attach failure, and Cloudflare/blocked states; these should be handled by heuristics first, not by stronger models.
- local `codex exec` can still be pushed onto the API-provider path by ambient `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL`, which breaks login-lane assumptions and makes fallback unreliable.

## Target State

Codex use in repair-related flows should be tiered:

1. `L0 heuristic`
   - deterministic runtime classification and guarded action planning
   - no model call

2. `L1 cheap Codex`
   - `gpt-5.3-codex-spark`
   - low or minimal reasoning
   - only for bounded route/action selection

3. `L2 stronger Codex`
   - non-spark Codex family model
   - medium/high reasoning
   - only for code-change proposal lanes where bounded heuristics are not sufficient

4. `L3 manual`
   - if Codex remains unavailable or evidence is too weak, return a structured manual route instead of repeatedly burning tokens

## Lane Policy

### `repair.autofix`

Policy:

- default path remains `heuristic -> spark(low) -> spark(minimal fallback) -> heuristic fallback`
- do not auto-upgrade to a stronger model
- record which execution path was used

Why:

- this lane is mostly runtime repair for known browser/driver/proxy incidents
- stronger models do not materially improve outcomes for `restart_driver` / `capture_ui` / `clear_blocked` style action choice

Default profile:

- primary model: `gpt-5.3-codex-spark`
- primary reasoning: `low`
- secondary fallback model: same model
- secondary fallback reasoning: `minimal`

### `sre.fix_request`

Policy:

- default path becomes `heuristic -> spark(low resume/fresh diagnosis) -> manual fallback on Codex unavailability`
- when the lane resumes and needs a fresh rerun, allow slightly higher reasoning on the fresh rerun only
- do not fail the entire SRE controller job just because Codex is temporarily unavailable

Why:

- this lane is a router/diagnoser, not the execution lane
- it should preserve operator momentum even when Codex auth/provider transport is unhealthy

Default profile:

- default model: `gpt-5.3-codex-spark`
- resume reasoning: `low`
- fresh reasoning: `medium`
- failure fallback: structured `manual` decision with Codex error captured in the report

### `repair.open_pr`

Policy:

- explicit mode-based model and reasoning selection
- no ambient model fallback

Why:

- this lane proposes real diffs and can optionally run tests / push / open PRs
- it needs a stronger profile than runtime autofix, but only for the modes that justify the cost

Default profile:

- `p0`: `gpt-5.3-codex-spark` + `low`
- `p1`: `gpt-5.3-codex` + `medium`
- `p2`: `gpt-5.3-codex` + `high`

These remain overridable by explicit job params.

## Codex Runner Governance

All ChatgptREST Codex CLI batch calls must run through a scrubbed subprocess environment.

Required behavior:

- start from `os.environ.copy()`
- remove ambient `OPENAI_*` and `openai_*` variables by default
- keep Codex login-lane environment intact
- allow explicit opt-out only via a dedicated env knob

Rationale:

- ambient `OPENAI_API_KEY` / `OPENAI_BASE_URL` can silently switch `codex exec` to the wrong provider path
- that breaks both cost assumptions and auth/fallback reliability

## Execution Steps

1. Freeze this plan in repo docs.
2. Add Codex runner env-scrub support and tests.
3. Add explicit SRE model/reasoning defaults and graceful manual fallback on Codex failure.
4. Add explicit `repair.open_pr` mode-based model/reasoning defaults.
5. Improve repair/SRE reports to expose execution path and model profile.
6. Update contract/dev-log docs with the new lane policy.
7. Apply live config defaults for SRE/open_pr where clarity is worth more than ambient behavior.
8. Restart only the affected ChatgptREST user services after code/config changes.
9. Run focused regression tests.
10. Run a minimal live smoke where safe.

## Acceptance Criteria

### Functional

- `repair.autofix` still resolves known runtime incidents without calling a stronger-than-spark model.
- `sre.fix_request` no longer depends on ambient model selection.
- `sre.fix_request` returns a structured `manual` result instead of failing hard when Codex is unavailable.
- `repair.open_pr` no longer depends on ambient model selection and uses mode-based defaults.

### Cost

- no new path upgrades `repair.autofix` above spark by default
- `repair.open_pr` only uses stronger profiles in `p1/p2`
- `sre.fix_request` defaults stay in the cheap tier unless an operator explicitly overrides them

### Fallback

- every repair-related lane has an explicit non-ambient fallback outcome:
  - `repair.autofix`: heuristic fallback
  - `sre.fix_request`: manual route fallback
  - `repair.open_pr`: explicit failure report with chosen model profile recorded

### Reliability

- Codex runner tests prove ambient `OPENAI_*` variables are scrubbed by default
- explicit caller-provided env still merges cleanly with the scrubbed base env

### Documentation

- contract/dev-log docs describe the new lane policy and fallback semantics
- live config changes are recorded in maint or repo-local operational docs

## Verification Plan

- unit tests:
  - `tests/test_codex_runner.py`
  - `tests/test_repair_autofix_codex_fallback.py`
  - `tests/test_sre_fix_request.py`
- targeted verification:
  - inspect generated repair/SRE reports for `execution_path`, `model`, `reasoning_effort`, and Codex failure metadata
  - verify live config no longer leaves worker auto-autofix enabled
  - run a minimal `codex exec` smoke with scrubbed environment assumptions

## Non-Goals

- redesigning the entire ChatgptREST global routing engine
- changing Gemini/OpenClaw provider policy outside the repair/SRE/open_pr scope
- making `repair.autofix` a code-patching lane
