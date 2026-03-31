# 2026-03-08 Behavior Issue Auto Promotion Loop

## Goal

Implement passive issue-ledger registration from observed client behavior, without requiring the client to explicitly call `/v1/issues/report`.

The desired backend loop was:

1. behavior signal
2. incident
3. issue ledger entry
4. automatic `sre.fix_request`
5. quiet-window auto-mitigation

## Design

### Why maint_daemon

The implementation deliberately lives in `maint_daemon`, not the hot request path.

Reason:

- behavior signals are inherently noisy and time-correlated
- promotion needs recent job + event history, not just the current request
- automatic issue filing and repair submission are state-changing actions and should stay in the background ops plane

### New module

- `chatgptrest/ops_shared/behavior_issues.py`

This module adds:

- detector logic over recent `jobs` + `job_events`
- `BehaviorIssueSubsystem`
- incident bundle writing
- issue ledger promotion
- idempotent `sre.fix_request` submission
- quiet-window auto-mitigation for `source=behavior_auto`

### Detectors implemented

1. `completed_short_resubmit`
   - finds human-language prompts where a web ask job completes with a suspiciously short answer
   - then the same client quickly re-asks the same prompt
   - default threshold: 2 occurrences before promotion

2. `needs_followup_loop_exhaustion`
   - finds repeated `needs_followup` chains in the same conversation / parent chain
   - default threshold: chain length >= 3

3. `dr_followup_progression_failure`
   - finds Deep Research parents that end in `needs_followup`
   - then a child follow-up no longer carries DR intent
   - promoted immediately as `P0`

### Closed loop behavior

For a promoted detector candidate, the subsystem now does:

1. create/update a `behavior` incident in `incidents`
2. write an evidence bundle under:
   - `artifacts/monitor/maint_daemon/incidents/<incident_id>/`
3. report/update an issue ledger entry with:
   - `source=behavior_auto`
   - deterministic explicit fingerprint
4. auto-submit one idempotent `sre.fix_request` per incident
5. mark the issue `in_progress`
6. after a quiet window, auto-mark stale `behavior_auto` issues as `mitigated`
   - recurrence will reopen automatically because `report_issue()` already supports reopen-on-mitigated

## Maint Daemon Wiring

### New flags / env support

Added to `ops/maint_daemon.py`:

- `--enable-behavior-issue-detection`
- `--disable-behavior-issue-detection`
- `--behavior-issue-every-seconds`
- `--behavior-issue-lookback-seconds`
- `--behavior-issue-jobs-limit`
- `--behavior-short-answer-chars-max`
- `--behavior-short-resubmit-window-seconds`
- `--behavior-short-resubmit-min-occurrences`
- `--behavior-needs-followup-min-chain`
- `--enable-behavior-auto-sre-fix`
- `--disable-behavior-auto-sre-fix`
- `--behavior-issue-max-promotions-per-tick`
- `--behavior-issue-auto-mitigate-after-hours`
- `--behavior-issue-auto-mitigate-max-per-tick`

Defaults currently ship as enabled for:

- behavior detection
- auto `sre.fix_request`

This is still conservative in practice because:

- only three high-confidence detectors exist
- promotion is deduped by explicit fingerprint
- `sre.fix_request` is idempotent and routes through existing guarded executor policy

### Important runner fix

While wiring the subsystem, a structural bug in `maint_daemon` became visible:

- the same `SubsystemRunner` was used for both pre-DB and post-DB ticks
- DB-dependent subsystems were being “scheduled” during the pre-DB pass with `conn=None`
- that consumed their interval budget and prevented the real post-DB execution

Fix:

- split runner usage into:
  - `_pre_db_subsystem_runner`
  - `_post_db_subsystem_runner`

This keeps `HealthCheckSubsystem` pre-DB and runs DB-dependent subsystems post-DB where they actually have a live connection.

## Tests

### New test file

- `tests/test_behavior_issue_detection.py`

Coverage added:

1. detector coverage for human-language prompts
2. subsystem promotion into incident + issue + `sre.fix_request`
3. quiet-window auto-mitigation
4. `maint_daemon.main()` integration path using natural-language questions

### Regression commands run

Focused behavior / SRE / issue loop:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_behavior_issue_detection.py \
  tests/test_sre_fix_request.py \
  tests/test_issue_ledger_api.py \
  tests/test_maint_daemon_auto_repair_check.py
```

Broader incident / ops regression:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_maint_daemon_incident_upsert.py \
  tests/test_incident_db.py \
  tests/test_ops_endpoints.py
```

## Human-Language Actual Validation

Ran an out-of-pytest one-off script against a temporary DB/artifacts directory.

Human-language prompts used:

1. `请帮我给五岁孩子设计一个乐高主题的周末活动计划。`
2. `请帮我比较一下 Deep Research 和普通搜索的差别。`

Seeded pattern:

- each prompt first produced a suspiciously short completed answer
- then the same client quickly re-submitted the same natural-language question

Then executed:

```bash
PYTHONPATH=. ./.venv/bin/python - <<'PY'
# temp DB setup + seeded human-language jobs + maint_daemon.main(...)
PY
```

Observed result:

- `behavior_auto` issue created
- `behavior` incident created
- `sre.fix_request` queued automatically

Example run result:

```json
{
  "issue": {
    "title": "Behavior detector: repeated short completions trigger human resubmits on gemini_web.ask",
    "status": "in_progress",
    "source": "behavior_auto"
  },
  "incident": {
    "category": "behavior",
    "severity": "P1"
  },
  "fix_job": {
    "kind": "sre.fix_request",
    "status": "queued"
  }
}
```

## Known Limits

1. This is intentionally not a generic “all client behavior becomes an issue” system.
   Only high-confidence server-observable patterns are promoted.

2. Auto-mitigation currently uses a quiet-window rule.
   It does not yet inspect downstream repair outcome semantics in depth.

3. The implementation uses issue ledger / incident / `sre.fix_request` primitives that already existed.
   No schema change was introduced for a separate behavior-events table in this phase.

4. The detector fingerprints are intentionally system-level, not per conversation.
   That keeps the ledger actionable, but it also means samples are aggregated at the provider/kind/detector level.

## Commits

1. `9b2b1be` `feat(maint): detect behavior-driven issues and auto-submit sre fixes`
2. `63c3399` `test(maint): cover behavior-driven issue promotion loop`
