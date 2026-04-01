# 2026-03-12 Issue Dev Controller OpenClaw Loop Walkthrough v1

## Scope

- Continue the Issue Ledger -> GitHub anchor -> task pack work from issue `#138`.
- Add the next orchestration layer so one controller command can:
  - consume an authoritative Issue Ledger issue
  - create a worktree branch
  - dispatch an implementer lane
  - dispatch a detached reviewer lane
  - commit and push branch changes
  - create and merge a PR
  - restart/verify the target service
  - write evidence back to Issue Ledger

## What Landed

### 1. New controller module

- Added `chatgptrest/ops_shared/issue_dev_controller.py`
- Responsibilities:
  - load Issue Ledger issue
  - sync GitHub issue anchor through existing `issue_github_sync`
  - create worktree branch
  - generate controller task pack and role prompts
  - sync / upsert controller lanes into `state/controller_lanes.sqlite3`
  - run implementer / reviewer commands through `ops/controller_lane_wrapper.py`
  - stage + commit + push git changes
  - create / merge PR through a GitHub client abstraction
  - verify health URL and write evidence back to Issue Ledger

### 2. New CLI entrypoint

- Added `ops/run_issue_ledger_openclaw_controller.py`
- This is the operator-facing command for the full lane loop.

### 3. Structured output contracts

- Added `ops/schemas/issue_dev_implementer_output.schema.json`
- Added `ops/schemas/issue_dev_reviewer_output.schema.json`
- These schemas define the JSON that implementer and reviewer lanes must write back.

### 4. Regression coverage

- Added `tests/test_issue_dev_controller.py`
- Coverage:
  - full controller loop over a temporary git repo + bare remote + fake GitHub client + health server
  - merge gate rejection when reviewer does not approve
  - explicit `skip_github_issue_sync=True` in tests so pytest never creates real GitHub issues

### 5. Runbook / env updates

- Updated `docs/runbook.md` with the full OpenClaw controller loop command
- Updated `ops/systemd/chatgptrest.env.example` with command-template env vars

## Validation

### Targeted pytest

Ran:

```bash
./.venv/bin/pytest -q \
  tests/test_issue_github_sync.py \
  tests/test_run_issue_ledger_dev_loop.py \
  tests/test_issue_dev_controller.py \
  tests/test_controller_lane_wrapper.py
```

Result:

- all passed

### Python compile

Ran:

```bash
python3 -m py_compile \
  chatgptrest/ops_shared/issue_github_sync.py \
  chatgptrest/ops_shared/issue_dev_controller.py \
  ops/sync_issue_ledger_to_github.py \
  ops/run_issue_ledger_dev_loop.py \
  ops/run_issue_ledger_openclaw_controller.py
```

Result:

- passed

### Full CLI smoke

Ran a real `ops/run_issue_ledger_openclaw_controller.py` smoke against:

- temporary git repo
- temporary bare remote
- temporary Issue Ledger DB
- temporary controller lane DB + manifest
- fake `gh` binary for GitHub issue / PR create / merge
- real local `systemctl --user start chatgptrest-api.service`
- real local `http://127.0.0.1:18711/healthz`

Final smoke result:

- `ok = true`
- implementer lane returned structured JSON
- reviewer lane returned `decision = approve`
- git commit succeeded
- git push succeeded
- PR create succeeded
- PR merge succeeded
- `chatgptrest-api.service` start command succeeded
- `/healthz` returned `200`
- Issue Ledger status transitioned to `mitigated`

Representative smoke report:

- artifact dir: `/tmp/chatgptrest-controller-smoke-q4LRuQ/artifacts/iss_27b23fb1b2b34c7a883445b6fcf54287/20260312T045935Z`
- merged PR number in fake-gh smoke: `902`

## Why This Shape

- Reused existing lane continuity and wrapper surfaces instead of inventing a second orchestration plane.
- Reused the existing Issue Ledger -> GitHub sync contract so GitHub remains a coordination anchor, not the source of truth.
- Kept implementer / reviewer execution generic via command templates so the same controller can drive:
  - Codex
  - Claude / `claudeminmax`
  - other local runners later

## Current Limits

- The controller does not yet wake remote OpenClaw / hcom agents by itself; it assumes the implementer and reviewer command templates are locally runnable.
- The controller currently performs PR merge itself once reviewer approval is present; it does not yet wait on external CI checks.
- The default command templates are intentionally not hardcoded; operators must set `CHATGPTREST_DEV_LOOP_IMPLEMENTER_CMD_TEMPLATE` and usually `CHATGPTREST_DEV_LOOP_REVIEWER_CMD_TEMPLATE`.

## Next Step

- Add a controller-side launcher that converts the generated role prompts into concrete hcom / OpenClaw dispatches, so local command templates become optional and lane wake-up can be fully remote-driven.
