# 2026-03-28 Monitor Projection Repair And Maint Daemon Dry Run Walkthrough v1

## Scope

- Repair stale monitor read-plane projections without changing issue state or enabling guardian autofix.
- Validate `maint_daemon/maint_*.jsonl` cleanup design with a real dry-run report.
- Keep `incidents/*`, `.run/*`, `state/*`, and runtime job artifacts out of scope.

## Independent Judgment

- The immediate governance bottleneck was not another policy gap. It was that the read-plane projections had gone stale, so operators could be looking at obsolete monitor views while the canonical DB kept changing.
- The safest fix was a read-only projection refresh path that refreshes:
  - `artifacts/monitor/open_issue_list/latest.*`
  - `artifacts/monitor/openclaw_guardian/latest_report.json`
- The next most valuable step was not apply cleanup. It was a real dry-run against `maint_daemon/maint_*.jsonl` to prove whether the approved budget design is actually achievable.

## Investigation Findings

### 1. Projection files were stale

- Before repair, `open_issue_list/latest.json` and `openclaw_guardian/latest_report.json` had stopped moving after `2026-03-19`.
- Manual `ops/export_issue_views.py` against the live DB still worked, so the canonical issue data path itself was healthy.

### 2. Stale projection had materially wrong operator picture

- The refreshed `artifacts/monitor/open_issue_list/latest.md` now shows:
  - total issues: `95`
  - active issues: `45`
  - recently settled: `50`
- That is materially different from the stale projection that had only `19` active issues.

### 3. Guardian projection needed a no-mutation mode

- A shell-run `ops/openclaw_guardian_run.py --no-autofix --no-notify` could still hit auth-dependent `ops_status` or optional downstream references depending on environment.
- For projection refresh, the right behavior is stricter:
  - no autofix
  - no notify
  - no orch report inclusion
  - produce `latest_report.json` as a read-only snapshot

### 4. Root cause was stopped projection timers, not exporter code rot

- `systemctl --user` showed the relevant projection timers had been inactive since `2026-03-19`.
- After introducing a combined projection refresh timer, it became clear that keeping the old standalone `chatgptrest-issue-views-export.timer` enabled at the same time causes duplicate `export_issue_views.py` runs against the same canonical outputs.
- The safe runtime shape is:
  - keep `chatgptrest-monitor-projection-refresh.timer` enabled
  - disable `chatgptrest-issue-views-export.timer` when the combined refresh path is used

## Changes Made

### Read-only monitor projection refresh

- Added `ops/refresh_monitor_projections.py`
  - sequentially runs `ops/export_issue_views.py`
  - then runs `ops/openclaw_guardian_run.py --projection-only`
- Added guardian `--projection-only`
  - implies `--no-autofix`
  - implies `--no-notify`
  - implies `--no-include-orch-report`
- Added systemd units:
  - `ops/systemd/chatgptrest-monitor-projection-refresh.service`
  - `ops/systemd/chatgptrest-monitor-projection-refresh.timer`
- Installed units with `ops/systemd/install_user_units.sh`
- Enabled the combined projection refresh timer
- Disabled the standalone `chatgptrest-issue-views-export.timer` to avoid duplicate export contention

### maint_daemon JSONL dry-run tool

- Added `ops/maint_daemon_jsonl_cleanup.py`
- The tool is dry-run only:
  - no compression
  - no deletion
  - no migration
- It writes evidence under:
  - `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/<timestamp>/`

## Runtime Validation

### Projection refresh timer state

- `chatgptrest-monitor-projection-refresh.timer`
  - enabled
  - active (waiting)
- `chatgptrest-monitor-projection-refresh.service`
  - last run exited `0/SUCCESS`
- `chatgptrest-issue-views-export.timer`
  - disabled
  - inactive

### Refreshed projection outputs

- `artifacts/monitor/open_issue_list/latest.json`
  - mtime: `2026-03-28 09:31:02 CST`
  - `summary.active_count = 45`
  - `summary.total_issues = 95`
  - `summary.recent_count = 50`
- `artifacts/monitor/openclaw_guardian/latest_report.json`
  - mtime: `2026-03-28 09:31:02 CST`
  - `ops_status.payload.active_open_issues = 45`
  - `orch_report = null`
  - `client_issue_sweep.enabled = false`
  - `client_issue_close_sweep.enabled = false`

## Dry Run Evidence

- Report root:
  - `artifacts/monitor/reports/maint_daemon_jsonl_cleanup/20260328T012710Z`
- `dry_run_plan.md` shows:
  - current: `94.61 GiB`
  - projected: `36.52 GiB`
  - estimated savings: `58.09 GiB`
  - soft budget `15.00 GiB`: `pass=False`
  - hard budget `25.00 GiB`: `pass=False`
- Planned actions:
  - keep raw: `5`
  - would compress: `0`
  - would summarize-only: `31`
- Compression sample:
  - sample population: `summarize_only`
  - sampled files: `6`
  - observed ratio: `0.0967`

## What This Means

- The monitor read plane is live again and reflects the current canonical DB instead of a March 19 snapshot.
- The approved `maint_daemon` budget policy is directionally right, but the current corpus shape means the existing dry-run plan still misses both soft and hard budgets.
- That means the next step should be design revision or stronger scope confirmation before any apply task is approved.

## Guardrails Kept

- No issue statuses were modified by the projection refresh path.
- No guardian autofix or notification path was enabled in the new projection timer.
- No `maint_daemon` files were compressed, deleted, or rewritten.
- No `incidents/*` files were touched.
- No runtime logic under worker/API/MCP surfaces was changed for this slice.

## Recommended Next Step

- Keep this slice closed as:
  - projection repair: done
  - maint_daemon dry-run evidence: done
- Next, revise the `maint_daemon/maint_*.jsonl` execution design using the real dry-run evidence before approving any apply phase.
