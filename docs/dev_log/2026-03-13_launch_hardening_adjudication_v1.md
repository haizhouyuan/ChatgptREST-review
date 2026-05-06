# Launch Hardening Adjudication v1

**Date**: 2026-03-13
**Author**: Codex
**Branch**: `codex/launch-hardening-20260313`
**Baseline**: `origin/master` at `3ee6d5fd91f2286d0ad07fb745d54205e71c549f`

## Executive Summary

Current `master` is materially healthier than the pre-merge state because `#164` and `#160` are already in:

- OpenClaw default recall now includes `knowledge + graph`
- `/livez`, startup manifest, `readyz` startup honesty, Feishu dedupe, and `cc-control` IP hardening are merged
- the curated convergence runner can produce a green bounded validation bundle

But this is **not yet a no-defect launch candidate**.

Two separate facts are now true at the same time:

1. The merged convergence gate is green on its own curated bundle.
2. A clean-worktree `pytest -q` on current `origin/master` still fails, and several real launch blockers remain in knowledge governance and security-sensitive report delivery paths.

So the correct conclusion is:

- **Do not launch yet**
- fix the hard blockers below
- rerun full repo regression + convergence gate + live/bounded soak
- only then promote to launch-ready

## Fresh Evidence

### 1. Full-suite pytest on clean master is red

Command:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q
```

Worktree:

```text
/tmp/chatgptrest-launch-hardening-20260313
```

Observed failing tests:

1. `tests/test_evolution_queue.py::TestPlanExecutor::test_execute_rolls_back_partial_changes`
2. `tests/test_execution_experience_review_validation_failure_fixture_bundle.py::test_execution_experience_review_validation_failure_fixture_bundle_complete_required`
3. `tests/test_execution_experience_review_validation_failure_fixture_bundle.py::test_execution_experience_review_validation_failure_fixture_bundle_valid_required`
4. `tests/test_mcp_tool_registry_snapshot.py::test_mcp_tool_registry_snapshot`
5. `tests/test_sandbox.py::TestMergeBack::test_merge_back_sets_staged_status`
6. `tests/test_sandbox.py::TestMergeBack::test_merge_all_new_atoms`

This means current master still has repo-level regressions independent of the curated convergence bundle.

### 2. Real launch blockers still present in code

#### Knowledge retrieval gate

`chatgptrest/evomap/knowledge/retrieval.py` still defaults `allowed_promotion_status` to:

```python
(ACTIVE, STAGED)
```

This is the core of `#129`: unaudited staged atoms are still eligible for retrieval by default.

#### Feedback loop not actually connected

`chatgptrest/evomap/knowledge/telemetry.py` still defines:

- `record_feedback()`
- `mark_atoms_used()`
- gap/frustration analytics

But current consult return path still only writes telemetry rows directly and does not call the feedback methods.

#### Activity ingest still hardcodes staged

`chatgptrest/evomap/activity_ingest.py` still writes `promotion_status=STAGED` for commit and activity atoms.

#### Security-sensitive report path still unsafe

`chatgptrest/advisor/report_graph.py` still:

- scans only `draft[:1000]` / limited prefix in redact flow
- calls `docs_create()` directly
- calls `gmail_send()` directly

This leaves `#149` and `#152` materially open on current master.

#### Telemetry DDL divergence still present

`chatgptrest/api/routes_consult.py` still defines `query_events` / `retrieval_events` inline with a schema that diverges from `chatgptrest/evomap/knowledge/telemetry.py`.

#### Cognitive health latent flaw still present

`chatgptrest/api/routes_cognitive.py` still returns:

```json
{"ok": true, "status": "not_initialized"}
```

when runtime is absent.

### 3. Some open issues are stale, not blockers

These should not drive implementation priority:

- `#148` — stale after `#160`; current `routes_advisor_v3.py` already uses `get_client_ip()`
- `#157` — targeted regression passes on current master

## Problem List and Resolution Direction

### A. Repo-level regression failures

#### A1. EvoMap plan execution rollback is broken

Evidence:

- `tests/test_evolution_queue.py::test_execute_rolls_back_partial_changes`
- error: `sqlite3.OperationalError: no such savepoint`

Likely root cause:

- nested DB helpers commit inside a savepoint-backed operation, invalidating rollback boundaries

Resolution:

- make `PlanExecutor.execute()` own the transaction boundary
- remove or gate inner commits for operations executed under an outer savepoint
- add direct rollback fault-injection tests for update + promote combinations

#### A2. Sandbox merge-back transaction boundary is broken

Evidence:

- `tests/test_sandbox.py::test_merge_back_sets_staged_status`
- `tests/test_sandbox.py::test_merge_all_new_atoms`
- same `no such savepoint` failure

Likely root cause:

- `merge_back()` uses savepoints while lower-level merge helpers or DB wrappers commit

Resolution:

- make sandbox merge atomic at the top level
- prohibit lower layers from committing during merge bundle operations
- add tests for single-atom and multi-atom rollback

#### A3. Execution experience fixture bundle drift

Evidence:

- two failures in `tests/test_execution_experience_review_validation_failure_fixture_bundle.py`

Likely root cause:

- fixture summary no longer matches current output schema/paths

Resolution:

- determine whether code regression or fixture drift
- if behavior is intended, regenerate fixture bundles and snapshot docs
- if behavior is accidental, restore old contract and keep fixtures

#### A4. MCP tool snapshot drift

Evidence:

- `tests/test_mcp_tool_registry_snapshot.py`

Likely root cause:

- tool registry changed without refreshing snapshot

Resolution:

- diff actual tool registry vs snapshot
- keep snapshot only if tool surface is intended
- otherwise revert unintended tool exposure

### B. Launch blockers in knowledge plane

#### B1. Retrieval serves staged atoms by default (`#129`)

Resolution:

- change default retrieval policy to exclude `STAGED`
- likely allow `ACTIVE` and explicitly justified `CANDIDATE` only
- add a host-level config/flag only if temporary compatibility fallback is unavoidable
- add regression proving staged-only atoms do not surface on default hot path

#### B2. Feedback loop is structurally present but not operational (`#128`)

Resolution:

- call `mark_atoms_used()` on actual result-return paths
- introduce explicit feedback write path where results are accepted/corrected/followed-up
- hook frustration/gap metrics into periodic governance action or explicit maintenance command
- prove `answer_feedback` and `used_in_answer` move under real retrieval flows

#### B3. Activity ingest has no automatic path toward trusted retrieval (`#132`)

Resolution:

- stop hardcoding all activity-derived atoms to `STAGED`
- classify higher-signal commit/closeout events into `CANDIDATE` when appropriate
- add a promotion batch/async path for fresh staged atoms that meet governance gates

#### B4. Authority contract is still mixed (`#134`)

Resolution:

- define one authority contract for runtime / consult / cognitive entrypoints
- prevent silent legacy-store growth
- prove entrypoints resolve the same EvoMap authority

### C. Security and side-effect blockers

#### C1. Redact gate scans only prefixes (`#149`)

Resolution:

- scan the full report body
- use chunked scanning if prompt/token limits matter
- make both policy and LLM scan aggregate over all chunks
- add tests with sensitive content only in tail sections

#### C2. Google Docs / Gmail bypass outbox (`#152`)

Resolution:

- move Google Docs create + Gmail send to `EffectsOutbox`
- derive deterministic effect keys from run/report/destination
- make retries replay-safe
- add tests for retry/no-duplicate behavior

#### C3. Attachment contract still not enforced before send (`#116`)

Resolution:

- detect local/repo path references in prompts when `input.file_paths` is missing
- reject or downgrade before provider send
- record structured attachment-contract error semantics
- add request-build and route-level tests

### D. Runtime / contract items that must be consciously closed

#### D1. v1/v2 contract split remains

Current state:

- OpenClaw advisor still submits via `/v2/advisor/ask|advise`
- then optionally polls `/v1/jobs/.../wait` and `/answer`

Resolution:

- for this launch tranche, either:
  - explicitly support this bridge as the published contract, or
  - narrow the launch surface and keep the plugin in a controlled mode

This is not necessarily a code rewrite blocker for this tranche, but it must be an explicit decision, not an accident.

#### D2. Cognitive health latent flaw

Resolution:

- return `ok=false` when runtime is not initialized, or split readiness semantics clearly
- update tests and docs accordingly

#### D3. Provider/runtime scope must match launch scope

User decision already provided:

- Qwen is stopped and should not be part of launch scope

Implication:

- keep Qwen disabled in validation and launch docs
- ensure unsupported Qwen paths fail closed and are not treated as launch blockers

## Proposed Launch-Hardening Execution Plan

### Wave 1. Fix repo-red test baseline first

Target:

- full `pytest -q` returns green on clean master-derived branch

Work items:

1. fix EvoMap plan executor savepoint rollback
2. fix sandbox merge-back savepoint rollback
3. adjudicate execution-experience fixture drift
4. refresh or correct MCP tool registry snapshot

Acceptance:

- all 6 currently failing tests pass
- no new regression appears in the same suite area

### Wave 2. Close security blockers

Target:

- report delivery is replay-safe and full-document redact-gated
- attachment contract is enforced pre-send

Work items:

1. full-document redact gate
2. docs/gmail through outbox with deterministic keys
3. pre-send attachment contract guard
4. add tests for tail-sensitive data, duplicate side effects, and missing attachment manifests

Acceptance:

- `#149`, `#152`, `#116` backed by passing tests

### Wave 3. Close knowledge-plane launch blockers

Target:

- default retrieval only serves governed knowledge
- feedback/usage starts writing to telemetry loop
- activity-derived knowledge has an automatic promotion path

Work items:

1. default retrieval excludes `STAGED`
2. wire `mark_atoms_used()` and feedback writes
3. add promotion job or inline async promotion path
4. unify consult telemetry DDL via the telemetry recorder authority

Acceptance:

- retrieval tests prove staged atoms are hidden by default
- telemetry tables receive query + retrieval + usage/feedback signals
- DDL is single-authority

### Wave 4. Runtime honesty and launch-surface cleanup

Target:

- runtime health semantics are honest
- launch surface is explicit

Work items:

1. fix `/v2/cognitive/health` contract
2. update readiness docs to reflect merged `#160/#164`
3. explicitly remove Qwen from supported launch surface
4. review Gemini path: either keep enabled with passing evidence or fail closed for unstable presets

Acceptance:

- docs and runtime agree on what is supported
- no stale readiness claims remain

### Wave 5. Final launch gate

Required gates:

1. full `pytest -q` green
2. curated convergence bundle green
3. live provider validation green for supported providers
4. bounded soak green
5. one longer soak / canary run recorded for launch evidence

## Decision

Current master is **not ready for a no-defect launch**.

The next branch should focus on:

1. repo-red baseline failures
2. security blockers
3. knowledge governance blockers

Only after those are closed should launch be reconsidered.
