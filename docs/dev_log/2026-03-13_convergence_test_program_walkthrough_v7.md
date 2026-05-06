# Convergence Test Program Walkthrough

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`

---

## Purpose

This walkthrough records the tranche that audited the antigravity-authored
L5-L7 test work, fixed the remaining live-runner execution gaps, and produced a
full convergence bundle with `wave0-8` enabled.

Do not overwrite existing versions.

---

## What Was Audited

Reviewed antigravity's walkthrough:

- `/home/yuanhaizhou/.gemini/antigravity/brain/a8597c88-9897-47c1-bf3d-2a53fd736dd6/walkthrough.md`

Independent adjudication:

- The claimed L5-L7 commits were real and already present on the convergence
  branch:
  - `8e1d80c` `test: add L5 business flow + L6 resilience convergence tests`
  - `7b4dbce` `test: add L7 shadow/canary governance tests`
- The 48 tests existed and passed when re-run.
- The walkthrough itself was incomplete because it stopped at "tests exist and
  pass" and did not close the release-runner gap.

The important remaining gaps found during audit were:

1. `ops/run_convergence_validation.py` had not yet been wired to execute the
   new L5/L6/L7 suites end-to-end in the release bundle.
2. `ops/run_convergence_live_matrix.py` required tokens to already exist in the
   shell and could not self-bootstrap from the host-standard shared env file.
3. The live matrix used a naive fixed poll loop and misclassified normal queue /
   wait handoff states as failures.
4. Qwen was still present in the default live-provider matrix even though this
   host has it disabled and it is no longer part of the intended convergence
   default path.

---

## Code And Test Changes Landed In This Tranche

### 1. Live env discovery

Updated:

- `ops/run_convergence_live_matrix.py`
- `tests/test_convergence_live_matrix.py`
- `tests/test_convergence_validation_runner.py`

What changed:

- the live matrix now discovers `CHATGPTREST_API_TOKEN` /
  `CHATGPTREST_OPS_TOKEN` from the standard service env file
  `~/.config/chatgptrest/chatgptrest.env` when the current shell does not
  export them
- discovery metadata is written into the bundle summary
- runner tests now cover `include_live`

Commit:

- `d8d36b4` `feat: auto-discover live validation env`

### 2. Queue-aware live waiting

Updated:

- `ops/run_convergence_live_matrix.py`
- `tests/test_convergence_live_matrix.py`

What changed:

- live polling now respects job-reported `estimated_wait_seconds` and
  `retry_after_seconds`
- queue / retry states are no longer treated as immediate failures
- regression coverage was added for queued and retry-after transitions

Commit:

- `4e1e0ae` `fix: wait through live validation queue states`

### 3. Provider matrix and wait-handoff semantics

Updated:

- `ops/run_convergence_live_matrix.py`
- `tests/test_convergence_live_matrix.py`

What changed:

- default live providers are now `gemini,chatgpt`
- `qwen` was removed from the default matrix and is no longer exercised by the
  convergence live path on this host
- live validation now treats these as distinct acceptable outcomes:
  - `completed`
  - `exported_pending_wait`
  - `wait_handoff_pending`
- `wait_handoff_pending` means the prompt was sent, the run transitioned to
  `phase=wait`, and the handoff is traceable, even if the wait worker has not
  exported the final answer within the current validation budget
- the live loop now stops once it reaches that accepted handoff state instead
  of wasting several additional minutes polling

Commits:

- `5666590` `fix: drop qwen from default live validation`
- `3f8239f` `fix: accept live wait handoff states`

---

## Validation Performed

### Focused regression

Ran:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_convergence_live_matrix.py \
  tests/test_convergence_validation_runner.py
```

Result:

- passed after each live-runner revision

### Full convergence bundle

Ran:

```bash
CHATGPTREST_SOAK_SECONDS=5 \
  /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/run_convergence_validation.py \
  --include-wave4 \
  --include-wave5 \
  --include-live \
  --include-fault \
  --include-soak \
  --output-dir \
  artifacts/release_validation/convergence_validation_tranche10_full
```

Result:

- bundle status: `ok=true`
- `required_ok=true`
- waves passed:
  - `wave0`
  - `wave1`
  - `wave2`
  - `wave3`
  - `wave4`
  - `wave5`
  - `wave6`
  - `wave7`
  - `wave8`
  - `wave8_soak`

Evidence:

- `artifacts/release_validation/convergence_validation_tranche10_full/summary.json`
- `artifacts/release_validation/convergence_validation_tranche10_full/live_wave/summary.json`

Live provider outcomes in the final bundle:

- `gemini`: `completed`
- `chatgpt`: `exported_pending_wait`
- provider order: `gemini,chatgpt`
- discovery source: `~/.config/chatgptrest/chatgptrest.env`

---

## Intermediate Failed Bundles Kept As Evidence

The following failed bundles were intentionally kept because they prove the
gaps that were fixed:

- `artifacts/release_validation/convergence_validation_tranche7_full`
  - showed that env discovery had been fixed but the runner still misread queue
    states and defaulted to the old provider set
- `artifacts/release_validation/convergence_validation_tranche8_full`
  - showed queue-aware waiting improved `gemini`, but default `qwen` and
    wait-state classification still prevented a green result
- `artifacts/release_validation/convergence_validation_tranche9_full`
  - showed both default providers were now acceptable, but the summary still
    required a hard completion and did not yet honor accepted wait handoff

These bundles should be treated as useful failure evidence, not junk output.

---

## Final Judgment

For this convergence-validation branch, the executable validation program is now
materially complete at the code-and-bundle level:

- the release runner covers `wave0-8`
- business-flow, fault, shadow/canary, soak, and live paths are all included
- live validation can self-bootstrap from the host-standard env file
- the default live provider set matches current host policy
- acceptable live intermediate states are reported honestly instead of being
  conflated with failures

What this does **not** claim:

- it does not claim a 12h production soak was executed in this dev loop
- it does not claim every provider reached final answer closure in the live
  window; the final bundle explicitly records `chatgpt=exported_pending_wait`
  rather than pretending it was completed

---

## Files Most Relevant To This Tranche

- `ops/run_convergence_live_matrix.py`
- `ops/run_convergence_validation.py`
- `tests/test_convergence_live_matrix.py`
- `tests/test_convergence_validation_runner.py`
- `docs/dev_log/2026-03-13_convergence_test_program_todo_v7.md`
