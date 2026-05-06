# Convergence Test Program Walkthrough

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Status: complete

This walkthrough records the second implementation tranche for the convergence
validation program. The focus of this revision is startup honesty, readiness
propagation, and an executable validation runner that emits a durable evidence
bundle instead of relying on ad-hoc pytest invocations.

---

## Why This Revision Exists

The earlier branch work already landed:

- reusable convergence fixtures
- probe semantics (`/livez`, `/healthz`, `/readyz`)
- `cc-control` trusted-proxy hardening
- initial Feishu dependency-loss regression coverage

What was still missing was the next layer of validation discipline:

- boot-time router truth recorded as structured state
- readiness refusing to claim success after core router load failure
- an executable convergence runner with bundle output
- tests that prove these behaviors
- at least one real provider completion path and one real degraded-path record

---

## Independent Engineering Judgments Applied

I re-checked the current branch instead of inheriting earlier review claims and
made the following decisions:

1. `create_app()` has critical blast radius, so any startup-honesty change must
   stay metadata-only and must not refactor auth or routing behavior.
2. `readyz` is the right place to reject fake readiness after startup recorded a
   core-router failure.
3. The repo already contains the right curated tests for Wave 0-4 and Wave 7;
   the missing value is a runner that executes them consistently and writes an
   evidence bundle.
4. Real live validation should be recorded honestly rather than normalized into
   a green story. On this host:
   - Qwen is disabled by config
   - Gemini completes
   - ChatGPT can reach `conversation_exported` while final answer closure still
     lags under current wait-worker backlog

---

## Files Added Or Changed

### Production Changes

- `chatgptrest/api/app.py`
- `chatgptrest/api/routes_jobs.py`
- `ops/run_convergence_validation.py`

### Regression Coverage

- `tests/test_api_startup_smoke.py`
- `tests/test_ops_endpoints.py`
- `tests/test_convergence_validation_runner.py`

### Process Record

- `docs/dev_log/2026-03-13_convergence_test_program_todo_v4.md`
- `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v4.md`

---

## What Landed

### 1. Startup Manifest And Route Inventory

`create_app()` now records a startup manifest on `app.state` with:

- per-router load status
- core router load errors
- route inventory
- route count
- a top-level manifest status

This keeps startup truth close to the application object and makes it testable.

### 2. Readiness Rejects Fake Startup Success

`/readyz` now consumes `app.state.startup_manifest` and adds a dedicated
`startup` check. Readiness only returns 200 when all of the following are true:

- DB check is healthy
- driver readiness is healthy
- startup manifest recorded no core router load failure

This closes the previous gap where boot could log a core router failure while
readiness still looked green.

### 3. Executable Convergence Validation Runner

Added `ops/run_convergence_validation.py`.

It does three things:

- captures `startup_manifest.json`
- compiles the critical control-plane modules with `py_compile`
- executes curated validation waves and writes stdout/stderr and a
  machine-readable `summary.json`

The runner supports:

- required waves `wave0` to `wave3`
- optional `wave4`
- optional live wave
- optional fault wave
- optional soak wave

### 4. Startup Honesty Regression Tests

Added tests proving:

- startup manifest is present and contains route inventory
- v3 router load failure is recorded in the manifest
- `/readyz` returns 503 when startup recorded a core router failure

### 5. Runner Bundle Regression Tests

Added tests proving:

- optional waves are included in the execution plan
- `run_validation()` writes the expected evidence bundle
- `main()` returns non-zero when a required wave fails

---

## Validation Performed

### Focused Static Validation

Executed:

```bash
python3 -m py_compile \
  chatgptrest/api/app.py \
  chatgptrest/api/routes_jobs.py \
  chatgptrest/api/routes_advisor_v3.py \
  ops/run_convergence_validation.py
```

Result:

- passed

### Focused Regression For This Tranche

Executed:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_api_startup_smoke.py \
  tests/test_ops_endpoints.py \
  tests/test_convergence_validation_runner.py
```

Result:

- passed

### Runner Evidence Bundle On Current HEAD

Executed:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/run_convergence_validation.py \
  --output-dir artifacts/release_validation/convergence_validation_tranche2_head \
  --include-wave4 \
  --include-fault
```

Bundle:

- `artifacts/release_validation/convergence_validation_tranche2_head/startup_manifest.json`
- `artifacts/release_validation/convergence_validation_tranche2_head/summary.json`
- per-wave stdout/stderr under the same directory

Result summary:

- compile: passed
- `wave0`: passed
- `wave1`: passed
- `wave2`: passed
- `wave3`: passed
- `wave4`: passed
- `wave7`: passed
- `required_ok`: true

### Real Provider Validation

Recorded under:

- `artifacts/release_validation/convergence_validation_live_local/`

Observed results:

- `gemini_web.ask`: completed with answer and conversation URL
- `qwen_web.ask`: rejected with `provider_disabled` on this host
- `chatgpt_web.ask`: prompt sent and `conversation_exported`, but final answer
  closure remained in `wait` during this run

The ChatGPT case is not a fake pass. It is evidence that:

- send path and conversation capture work
- export path works
- final wait closure is still sensitive to current runtime backlog

That is exactly the kind of live truth the validation program is supposed to
surface.

---

## Evidence Worth Calling Out

### Startup Honesty

The runner now makes startup truth durable enough to audit after the fact:

- `startup_manifest.status`
- `startup_manifest.routers`
- `startup_manifest.router_load_errors`
- `startup_manifest.route_inventory`

### Live Runtime Reality

This revision also produced a useful operational signal:

- Gemini path is currently usable end-to-end
- Qwen is host-disabled and should not be counted in expected live coverage on
  this machine
- ChatGPT live completion can stall after export, which points to runtime wait
  closure and queue conditions rather than prompt-send failure

That distinction matters for release adjudication.

---

## What This Revision Does Not Claim

This revision still does **not** claim the entire convergence program is
finished.

Still open beyond this tranche:

- full shadow / canary / long-soak execution
- wider business-flow simulation catalog
- stronger live-wave automation inside the runner itself
- additional recovery drills tied to real service backlog conditions
- product-level convergence work outside the validation program

What it does claim is narrower and real:

- startup honesty is now encoded and test-backed
- readiness consumes startup truth
- the repo now has an executable convergence runner with evidence bundles
- the branch has current-head bundle evidence plus real provider observations

---

## Commit Sequence For This Revision

1. `docs: add convergence execution tranche todo v4`
2. `feat: add convergence startup manifest and validation runner`
3. pending at time of writing: walkthrough, PR refresh, and closeout

---

## PR Handling

This revision continues to update the existing PR rather than opening a second
parallel PR for the same workstream.

Target PR:

- `https://github.com/haizhouyuan/ChatgptREST/pull/160`

Reason:

- keeps the full design-to-implementation history on one branch
- preserves one review thread for the convergence validation program
- lets later tranches extend a single evidence chain instead of splitting the
  narrative across multiple PRs
