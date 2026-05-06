# V6 Production-Grade Walkthrough V1

Date: 2026-04-08

## 1. Why this wave was needed

V5 repaired the northbound lane, but the planning knowledge path still had a fatal practical gap:

- bulk planning promotion had started to exist,
- but the explicit planning runtime consumer still pointed at the stale March 11 release bundle.

That meant the system could claim “fresh raw pack export” while the actual explicit consumer still saw old data.

## 2. What was implemented

### Step 1. Planning bulk promotion runner and scheduler

Added:

- [run_planning_bulk_groundedness_promotion.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_bulk_groundedness_promotion.py)
- [chatgptrest-planning-bulk-promotion.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-bulk-promotion.service)
- [chatgptrest-planning-bulk-promotion.timer](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-bulk-promotion.timer)

Result:

- active `201 -> 242`
- candidate `25 -> 538`

### Step 2. KB hybrid runtime facts frozen against live `.venv`

Added:

- [report_kb_hybrid_runtime_probe.py](/vol1/1000/projects/ChatgptREST/ops/report_kb_hybrid_runtime_probe.py)

Result:

- proved service runtime uses `.venv`
- proved vector-enabled hits are live

### Step 3. Fixed runtime-pack release orchestration

The initial V6 gap was in:

- [run_planning_runtime_pack_refresh.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_runtime_pack_refresh.py)

Before fix:

- it exported a raw pack
- then tried to read “counts” from the export return shape instead of the pack manifest
- and confused raw pack output with explicit release-bundle readiness

After fix:

- raw pack export
- validation
- sensitivity audit
- observability generation
- release bundle build
- ready-bundle verification

all happen in one orchestration step.

### Step 4. Cleared the sensitivity blocker

The new pack initially failed sensitivity because three atoms matched the token `合同`.

Manual review showed they were:

- internal planning guardrails
- not raw contract text
- not personal data

So the review spec was updated:

- [planning_runtime_pack_sensitivity_review_v1.json](/vol1/1000/projects/ChatgptREST/ops/data/planning_runtime_pack_sensitivity_review_v1.json)

### Step 5. Fresh explicit bundle confirmed

New default ready bundle:

- [20260408T032206Z release bundle](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_runtime_pack_release_bundle/20260408T032206Z/release_bundle_manifest.json)

This replaced the old March 11 ready bundle as the default explicit-consumption pointer.

## 3. Evidence used to close V6

### Runtime evidence

- [planning runtime pack refresh summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_reviewed_runtime_pack/20260408T032206Z/refresh_summary.json)
- [planning runtime pack status smoke](/vol1/1000/projects/ChatgptREST/artifacts/monitor/v6_production_grade_acceptance/20260408T034324Z/planning_runtime_pack_status.json)
- [KB hybrid runtime probe](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_hybrid_runtime_probe/20260408T032254Z/summary.json)
- [MCP health](/vol1/1000/projects/ChatgptREST/artifacts/monitor/v6_production_grade_acceptance/20260408T034324Z/mcp_health.json)

### Test evidence

- [targeted regression output](/vol1/1000/projects/ChatgptREST/artifacts/monitor/v6_targeted_regression/20260408T034425Z/pytest.txt)

## 4. What V6 deliberately did not do

1. It did not perform broad `scope_project` live backfill.
2. It did not claim whole-repo full-suite green.
3. It did not collapse all knowledge systems into one merged architecture.
4. It did not promote pure-text planning atoms to `active` without grounded runtime anchors.
