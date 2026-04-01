# 2026-03-15 Maintagent Self-Heal Runtime Rollout v1

## Scope

This rollout finished the live path from maintagent memory -> SRE diagnosis -> guarded runtime self-heal.

Goals:

- make maintagent carry machine/workspace memory and ChatgptREST repo memory into live diagnosis
- stop `repair.autofix` from hanging indefinitely on slow/broken MCP tool calls
- keep polluted `client_issues.latest_job_id` from pointing at internal `sre.*` / `repair.*` jobs
- make repeated lane-triggered runtime fixes reuse an existing downstream repair job instead of failing on idempotency collision
- provide one operator entrypoint to enable guarded self-heal in production

## Code Changes

### 1. Repair runtime hardening

Files:

- `chatgptrest/executors/repair.py`
- `tests/test_repair_autofix_codex_fallback.py`

Changes:

- added `_call_tool_with_hard_timeout()` and moved repair tool calls behind an outer hard timeout
- injected `Maintagent Repo Memory` and `Maintagent Bootstrap Memory` into the primary `repair.autofix` Codex prompt
- verified that repair prompt rendering includes memory metadata and that hard timeouts raise/return instead of hanging forever

Why:

- live job `0eca6ed17ff3401f87dfe098f7f3f810` had previously stalled in `in_progress` after writing `codex/sre_actions.json`
- the root cause was action-stage waiting on MCP/UI calls without a reliable outer deadline

### 2. Shared issue target resolution + backfill

Files:

- `chatgptrest/ops_shared/issue_targets.py`
- `ops/backfill_internal_issue_targets.py`
- `chatgptrest/executors/sre.py`
- `tests/test_issue_targets.py`

Changes:

- added a shared resolver that prefers the last non-internal job referenced by an issue
- added a one-shot backfill tool for fixing `client_issues.latest_job_id`
- updated `sre.fix_request` to use the shared resolver and record `issue_target_resolution` in lane request/report artifacts

Why:

- earlier `issue_evidence_linked` records from `sre.fix_request` had polluted several issues so the “latest job” was the maintagent follow-up itself
- this made subsequent diagnosis slower and less accurate

### 3. Downstream repair/open_pr reuse

Files:

- `chatgptrest/executors/sre.py`
- `tests/test_sre_fix_request.py`

Changes:

- `sre.fix_request` now catches downstream `IdempotencyCollision`
- if the existing job kind matches (`repair.autofix` or `repair.open_pr`), the lane reuses that job instead of failing

Why:

- repeated diagnosis on the same lane/target can legitimately produce the same downstream route but a slightly different payload
- before this fix, the second run could fail even though the first downstream job was already good enough to reuse

### 4. Operator-facing self-heal entrypoint

Files:

- `ops/systemd/enable_maint_self_heal.sh`
- `ops/systemd/install_user_units.sh`
- `ops/systemd/chatgptrest-maint-daemon.service`
- `ops/systemd/chatgptrest.env.example`
- `docs/runbook.md`
- `docs/maint_daemon.md`

Changes:

- added `enable_maint_self_heal.sh`
- the script:
  - calls `enable_auto_autofix.sh`
  - writes `~/.config/systemd/user/chatgptrest-maint-daemon.service.d/30-self-heal.conf`
  - enables maint daemon `--enable-codex-sre-autofix`
  - sets a medium-risk allowlist: `capture_ui,clear_blocked,restart_driver,restart_chrome,switch_gemini_proxy`
  - restarts maint/send/wait/repair workers

Why:

- operators needed a repeatable switch from “diagnose only” to “guarded self-heal” without hand-editing unit files

## Tests

Ran:

- `./.venv/bin/pytest -q tests/test_repair_autofix_codex_fallback.py tests/test_issue_targets.py tests/test_sre_fix_request.py`
- `./.venv/bin/pytest -q tests/test_repair_autofix_codex_fallback.py tests/test_issue_targets.py tests/test_sre_fix_request.py tests/test_maint_bootstrap_memory.py tests/test_codex_runner.py`

Both passed after the final fixes.

## Live Rollout

### Self-heal enablement

Executed:

- `ops/systemd/enable_maint_self_heal.sh`

Observed live state after restart:

- `chatgptrest-maint-daemon.service` running with:
  - `--enable-codex-sre-autofix`
  - `--codex-sre-autofix-allow-actions capture_ui,clear_blocked,restart_driver,restart_chrome,switch_gemini_proxy`
  - `--codex-sre-autofix-max-risk medium`
- worker env includes:
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX=1`
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MAX_RISK=medium`
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MIN_INTERVAL_SECONDS=300`
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_APPLY_ACTIONS=1`

### Issue target backfill

Executed:

- `ops/backfill_internal_issue_targets.py --db state/jobdb.sqlite3`

Observed:

- `iss_9d505a432e1a40d6acb9fb63f29c330d` moved from internal `latest_job_id=e49aeb...` back to original ask job `db1595c5338a49eca3793546f669b6e1`

### Real issue validation

Real issue:

- `iss_9d505a432e1a40d6acb9fb63f29c330d`

Live jobs:

- `fcdb489a711847cc86adb8f71fa295bd` (`sre.fix_request`)
- reused downstream `110cd51b12994a019661ecd05b43695a` (`repair.autofix`)

Observed:

- `sre.fix_request` completed in `runner_mode=heuristic`
- lane request artifact included:
  - `bootstrap_memory.status=loaded`
  - `repo_memory.status=loaded`
  - `issue_target_resolution.resolved_job_id=db1595c5338a49eca3793546f669b6e1`
- downstream runtime repair was reused successfully instead of failing on idempotency collision
- `sre_fix_report.json` recorded `downstream.idempotency_reused=true`

### Live repair hang validation

Historical stuck job:

- `0eca6ed17ff3401f87dfe098f7f3f810`

Observed after rollout:

- job reached `status=completed`
- `repair_autofix_report.json` exists
- `codex.ok=true`
- `capture_ui` no longer wedges the job; it failed fast with `ToolCallError: SSE stream timeout (deadline exceeded).`
- remaining restart actions still respected the send-phase guard and were skipped safely while non-repair send jobs existed

## Outcome

Maintagent is now materially closer to a usable self-healing operator:

- layered memory is present in live SRE lane artifacts
- repo knowledge is injected before diagnosis
- polluted issues can be re-anchored to their original failing jobs
- repeated runtime diagnoses on the same lane reuse good downstream jobs
- `repair.autofix` no longer hangs indefinitely on broken UI/MCP calls
- production enablement is a documented one-command rollout instead of a hand patch

## Remaining Gap

`client_issues.source` can still remain polluted by historic internal follow-up writes because older `issue_reported` events did not preserve the original source. We can re-anchor `latest_job_id` safely today, but perfect `source` restoration requires either:

- storing original source history explicitly in future issue events, or
- a separate migration that infers canonical source from more than the current event payloads.
