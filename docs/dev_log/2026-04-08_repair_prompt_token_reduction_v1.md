## Summary

This change reduces Codex prompt size for `repair.autofix` and `repair.open_pr` without changing the main `maint_daemon` path.

The investigation showed that current `maint_daemon` incidents already route through the controller repair lane with moderate prompt size, while `repair.autofix` was still serializing oversized context into Codex prompts.

## Findings

- `maint_daemon` is no longer the main token sink.
  - Sample incident: `artifacts/monitor/maint_daemon/incidents/20260408_053059Z_51ffa7fe875e/codex/run_meta.json`
  - Observed `prompt_chars=17163`
  - Observed `prompt_estimated_tokens=4290`
- `repair.autofix` was the expensive path.
  - Sample job: `artifacts/jobs/f03689bc645342f8a9ac3885994833fa/codex/prompt.txt`
  - Previous primary prompt size: `81098` chars
  - Previous fallback prompt size: `38004` chars
- The largest contributors in the sampled autofix prompt were:
  - large `AGENTS.md` injection
  - raw `Evidence (JSON)` payload, especially `events_tail`
  - verbose maint memory blocks
- The secondary Codex fallback in `repair.autofix` was enabled by default, which could spend a second Codex turn even when heuristic fallback was sufficient.

## Changes

### `repair.autofix`

- Added `_compact_prompt_value()` and `_compact_repair_evidence_for_prompt()` to shrink prompt-bound evidence before serialization.
- `AGENTS.md` is now omitted by default for autofix prompts.
  - env: `CHATGPTREST_CODEX_AUTOFIX_AGENTS_MAX_CHARS`
  - default: `0`
- Reduced default context caps:
  - `CHATGPTREST_CODEX_AUTOFIX_PLAYBOOK_MAX_CHARS=6000`
  - `CHATGPTREST_CODEX_AUTOFIX_BOOTSTRAP_MAX_CHARS=4000`
  - `CHATGPTREST_CODEX_AUTOFIX_REPO_MEMORY_MAX_CHARS=2000`
  - `CHATGPTREST_CODEX_AUTOFIX_EVENTS_TAIL_MAX_CHARS=8000`
- Reduced serialized evidence cap in `_build_codex_autofix_prompt()` from `120000` to `24000`.
- Reduced serialized evidence cap in `_build_codex_autofix_fallback_prompt()` from `80000` to `12000`.
- Disabled the secondary Codex fallback by default.
  - env: `CHATGPTREST_CODEX_AUTOFIX_ENABLE_MAINT_FALLBACK`
  - new default: `false`
  - heuristic fallback remains available when Codex fails

### `repair.open_pr`

- Reduced default debug text budget.
  - env: `CHATGPTREST_CODEX_OPEN_PR_DEBUG_TEXT_MAX_CHARS`
  - default: `12000`
- Reduced default `AGENTS.md` budget.
  - env: `CHATGPTREST_CODEX_OPEN_PR_AGENTS_MAX_CHARS`
  - default: `4000`
- Added evidence compaction before prompt assembly.
- Reduced serialized evidence cap from `120000` to `30000`.

## Measured Effect

Using the sampled autofix artifact `f03689bc645342f8a9ac3885994833fa` and rebuilding the prompt with the new defaults:

- primary prompt: `81098 -> 11416` chars
- fallback prompt: `38004 -> 3639` chars
- `AGENTS.md` section is absent by default
- compacted evidence payload for the rebuilt prompt: `3207` chars

This is a large reduction in prompt volume while keeping the repair playbook, minimal maint memory, summarized target-job metadata, and bounded recent events.

## Verification

- `pytest -q tests/test_repair_provider_tools.py tests/test_repair_autofix_codex_fallback.py`
  - `17 passed`
- Added regression coverage for:
  - evidence compaction
  - prompt size caps
  - secondary Codex fallback now being opt-in

## Operational Notes

- No code change was made to the `maint_daemon` controller path in this iteration because the sampled prompt volume was already in the acceptable range.
- If future incidents show `maint_daemon` prompt growth again, inspect prompt builders in the SRE controller path before touching the repair lane defaults.
