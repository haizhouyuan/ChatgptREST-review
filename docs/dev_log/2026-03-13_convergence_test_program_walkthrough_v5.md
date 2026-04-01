# Convergence Test Program Walkthrough

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Status: complete

This walkthrough records tranche 3 of the convergence validation program.
The focus of this revision is:

- closing duplicate replay at the Feishu WS ingress edge
- turning `wave6` live validation into an executable, repeatable provider matrix
- producing a current-head convergence bundle that includes both deterministic
  and live evidence

---

## Why This Revision Exists

After tranche 2, the branch already had:

- startup manifest and readiness honesty
- a curated convergence runner for `wave0-4` and `wave7`
- real live evidence captured manually

The remaining gap was that two important pieces were still under-implemented:

1. Feishu WS ingress did not protect itself against repeated delivery of the
   same `message_id`.
2. `wave6` live validation still depended on manual commands and operator
   interpretation instead of a scriptable evidence bundle.

This revision closes both gaps.

---

## Independent Engineering Judgments Applied

I made the following implementation calls after re-checking the current branch:

1. The highest-value business-flow hardening left in the repo-local scope was
   duplicate replay on `FeishuWSGateway`. This is a real channel-edge risk and
   has low blast radius.
2. Live validation should not be modeled as a single binary provider pass/fail.
   The runner needs to distinguish at least three outcomes:
   - provider completed
   - provider disabled by host policy
   - provider reached export evidence but final answer closure still lagged
3. The convergence runner must not leak live auth tokens into deterministic
   pytest waves; otherwise `wave0-2` become invalid by construction.
4. Provider order matters under bounded live polling. Gemini should run before
   ChatGPT because it is more likely to finish within the bounded poll window,
   which makes `wave6` less sensitive to ChatGPT queue depth.

---

## Files Added Or Changed

### Channel Hardening

- `chatgptrest/advisor/feishu_ws_gateway.py`
- `tests/test_feishu_ws_gateway.py`

### Live Validation Automation

- `ops/run_convergence_live_matrix.py`
- `ops/run_convergence_validation.py`
- `tests/test_convergence_live_matrix.py`
- `tests/test_convergence_validation_runner.py`

### Process Record

- `docs/dev_log/2026-03-13_convergence_test_program_todo_v5.md`
- `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v5.md`

---

## What Landed

### 1. Feishu WS Duplicate Replay Protection

`FeishuWSGateway` now claims `message_id` through a dedup store before spawning
background processing.

Behavioral result:

- same `message_id` is processed once
- later repeats are logged and skipped
- distinct `message_id`s still flow normally

This converts `SIM-04 duplicate delivery` from a doc-only concern into a real
guardrail on the channel edge.

### 2. Feishu Duplicate-Delivery Regression Coverage

Added tests that prove:

- duplicate `message_id` replay does not trigger a second processing thread
- distinct `message_id`s still dispatch independently

This sits alongside the existing dependency-loss regression and gives the
Feishu WS surface both positive and negative proof.

### 3. Live Provider Matrix Script

Added `ops/run_convergence_live_matrix.py`.

It performs bounded live validation against the real service by:

- submitting provider-backed jobs through `chatgptrestctl`
- polling job state and events for bounded time
- fetching answer evidence when the job completes
- classifying provider outcomes into explicit categories

Current accepted live categories are:

- `completed`
- `provider_disabled`
- `exported_pending_wait`

That lets the branch record honest runtime truth instead of flattening all
provider states into a single “green” claim.

### 4. Runner Environment Isolation

`ops/run_convergence_validation.py` now isolates deterministic waves from live
auth tokens.

Without this, `wave0-2` falsely failed with `401` because the runner inherited
`CHATGPTREST_API_TOKEN` and caused `create_app()` test clients to require auth.

The runner now:

- strips auth tokens from deterministic compile/pytest waves
- preserves auth tokens only for `wave6`
- passes a dedicated output directory into the live matrix script

### 5. Live Wave Included In Current-Head Bundle

The convergence runner now produces a bundle that includes:

- `wave0`
- `wave1`
- `wave2`
- `wave3`
- `wave4`
- `wave6`
- `wave7`

This is the first branch revision where live provider validation is part of the
same evidence bundle as the deterministic convergence waves.

---

## Validation Performed

### Feishu WS Regression

Executed:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_feishu_ws_gateway.py
```

Result:

- passed

### Live Matrix Focused Regression

Executed:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_convergence_live_matrix.py \
  tests/test_convergence_validation_runner.py
```

Result:

- passed

### Combined Focused Regression

Executed:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_convergence_validation_runner.py \
  tests/test_convergence_live_matrix.py \
  tests/test_feishu_ws_gateway.py
```

Result:

- passed

### Standalone Live Matrix

Executed:

```bash
CHATGPTREST_API_TOKEN=... \
  /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/run_convergence_live_matrix.py \
  artifacts/release_validation/convergence_live_matrix_head
```

Result:

- overall `ok=true`

Observed provider outcomes:

- Gemini: `completed`
- ChatGPT: `exported_pending_wait`
- Qwen: `provider_disabled`

Evidence:

- `artifacts/release_validation/convergence_live_matrix_head/summary.json`

### Current-Head Convergence Bundle With Live Wave

Executed:

```bash
CHATGPTREST_API_TOKEN=... \
  /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/run_convergence_validation.py \
  --output-dir artifacts/release_validation/convergence_validation_tranche3_head \
  --include-wave4 \
  --include-live \
  --include-fault
```

Bundle:

- `artifacts/release_validation/convergence_validation_tranche3_head/summary.json`
- `artifacts/release_validation/convergence_validation_tranche3_head/live_wave/summary.json`
- per-wave stdout/stderr under the same directory

Result summary:

- compile: passed
- `wave0`: passed
- `wave1`: passed
- `wave2`: passed
- `wave3`: passed
- `wave4`: passed
- `wave6`: passed
- `wave7`: passed
- `required_ok`: true

Live-wave provider summary inside the bundle:

- Gemini: `completed`
- ChatGPT: `exported_pending_wait`
- Qwen: `provider_disabled`

---

## Important Findings

### Feishu WS Needed Real Dedup, Not Just Test Intent

Before this revision, the WS gateway would forward the same `message_id`
repeatedly if the upstream delivered duplicates.

That is exactly the kind of issue a convergence plan is supposed to flush out:
the system might “work” in a happy path and still double-process real user
messages under replay.

### Live Validation Must Carry Degraded Truth Forward

The current host is not a symmetrical provider environment:

- Gemini is available and can complete end-to-end
- Qwen is deliberately disabled on this host
- ChatGPT can reach export evidence while final answer closure still lags in
  some runs

The right validation behavior is to record those distinctions, not erase them.

### Auth Leakage Into Test Waves Was A Real Runner Bug

The first attempt to include `wave6` in the total runner bundle polluted
deterministic pytest waves with auth tokens and turned clean tests into
`401 Unauthorized`.

Fixing that was necessary for the bundle to be trustworthy.

---

## What This Revision Does Not Claim

This revision still does **not** claim the entire convergence program is
finished.

Still open beyond tranche 3:

- longer soak and canary automation
- more business-flow scenarios from the matrix
- more recovery drills tied to real service backlog conditions
- product-level convergence work outside the validation-program scope

What it does claim is concrete:

- Feishu WS duplicate replay is now guarded and tested
- `wave6` live validation is now executable and repeatable
- the current branch has a full-head bundle with `wave0-4`, `wave6`, and
  `wave7` all green

---

## Commit Sequence For This Revision

1. `docs: add convergence execution tranche todo v5`
2. `fix: dedupe repeated feishu ws messages`
3. `feat: automate convergence live provider validation`
4. pending at time of writing: walkthrough, PR refresh, and closeout

---

## PR Handling

This revision continues to update the existing PR rather than opening a second
parallel PR for the same workstream.

Target PR:

- `https://github.com/haizhouyuan/ChatgptREST/pull/160`

Reason:

- keeps tranche 1-3 in one evidence chain
- keeps design, implementation, and runtime evidence in one review surface
- avoids fragmenting the convergence-validation narrative across parallel PRs
