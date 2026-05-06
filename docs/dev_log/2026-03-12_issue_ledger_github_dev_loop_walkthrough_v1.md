# 2026-03-12 Issue Ledger GitHub Dev Loop Walkthrough v1

## Scope

Feature issue:

- GitHub issue `#138` `feat(dev-loop): automate issue-ledger -> GitHub -> dev task -> service verification`

This slice turns the existing Issue Ledger into the first step of a development loop instead of leaving it as an internal-only incident register.

## What Landed

### 1. Issue Ledger -> GitHub sync module

Added:

- `chatgptrest/ops_shared/issue_github_sync.py`
- `ops/sync_issue_ledger_to_github.py`

Behavior:

- derive stable GitHub title/body/labels from authoritative Issue Ledger rows
- write back GitHub linkage into `metadata.github_issue`
- emit `issue_github_synced` events into the ledger event stream
- close or reopen/comment on the GitHub side when ledger status changes
- keep `dry-run` side-effect free

### 2. Thin dev-loop runner

Added:

- `ops/run_issue_ledger_dev_loop.py`

Behavior:

- load one ledger issue as the authoritative source
- optionally ensure a GitHub anchor exists
- materialize a dev-loop task pack under `artifacts/dev_loops/<issue_id>/...`
- include current role assignment guidance:
  - controller: `openclaw main + guardian sidecar`
  - implementer: `codex_auth_only`
  - reviewer: `claudeminmax`
- optionally create a git worktree
- optionally run test commands
- optionally run service start commands
- verify a health URL at the end

### 3. Ops wiring

Added:

- `ops/systemd/chatgptrest-issue-github-sync.service`
- `ops/systemd/chatgptrest-issue-github-sync.timer`

Updated:

- `ops/systemd/chatgptrest.env.example`
- `ops/systemd/install_user_units.sh`
- `docs/runbook.md`

The intended shape is:

- keep GitHub interactions out of the worker/API hot path
- run sync as a separate oneshot/timer surface
- keep Issue Ledger authoritative and GitHub coordination-only

## Why This Shape

I did not wire GitHub calls into `worker.py`, `/v1/issues/report`, or the guardian sweep.

Reason:

- GitHub auth/outage should not change the primary incident path
- the repo already treats external coordination as a sidecar concern
- a separate sync runner is easier to audit, retry, disable, and test

## Validation

### Static

```bash
python3 -m py_compile \
  chatgptrest/ops_shared/issue_github_sync.py \
  ops/sync_issue_ledger_to_github.py \
  ops/run_issue_ledger_dev_loop.py
```

### Targeted pytest

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_issue_github_sync.py \
  tests/test_run_issue_ledger_dev_loop.py
```

Result:

- `3` tests passed

### CLI smoke: Issue Ledger -> GitHub sync

Ran against a temporary Issue Ledger DB:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/sync_issue_ledger_to_github.py \
  --db <tmpdb> \
  --repo haizhouyuan/ChatgptREST \
  --report <tmp-report> \
  --force \
  --dry-run
```

Observed result:

- `processed=1`
- `created=1`
- derived labels included `P1`, `bug`, `domain/gemini`, `track/runtime-reliability`, `status/triage`

### CLI smoke: full dev loop

Ran against a temporary Issue Ledger DB plus the live local API service:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/run_issue_ledger_dev_loop.py <issue_id> \
  --db <tmpdb> \
  --repo haizhouyuan/ChatgptREST \
  --artifact-root <tmp-artifacts> \
  --run-test-cmd "/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_issue_github_sync.py tests/test_run_issue_ledger_dev_loop.py" \
  --service-start-cmd "systemctl --user start chatgptrest-api.service" \
  --health-url http://127.0.0.1:18711/healthz \
  --dry-run
```

Observed result:

- GitHub anchor plan generated (`dry_run_create`)
- test command succeeded
- `systemctl --user start chatgptrest-api.service` succeeded
- `/healthz` returned `200`
- task pack and report were written under the generated artifact dir

## Current Limits

- This is not yet a full autonomous multi-agent implementation platform.
- The runner generates role assignments and artifacts, but it does not directly launch Codex/Claude/OpenClaw lanes to write code.
- GitHub Project automation is still blocked separately by missing `project` scopes on the current `gh` token.

## Next Logical Step

If we continue on top of this slice, the next useful move is:

1. add a controller-facing launcher that can hand the generated task pack to the selected implementer/reviewer lanes
2. add PR bootstrap/update helpers on top of the GitHub issue anchor
3. keep reviewer decisions as explicit artifacts instead of burying them in ad hoc comments
