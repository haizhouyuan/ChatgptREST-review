# V6 Production-Grade Completion Summary V1

Date: 2026-04-08

Program anchor:

- [Refined Next-Stage Full Execution Plan V6](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v6.md)

Completion anchor:

- [Next-Stage Execution TODO Master V19](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v19.md)

## 1. Final judgment

V6 is complete for the target surface the user is about to test:

- public `coding-agent-v1` surface remains production-ready;
- planning knowledge activation is no longer stuck behind a stale March 11 explicit pack;
- a fresh reviewed planning runtime pack and a fresh explicit release bundle are now live;
- planning bulk scoring/promotion has a dedicated live scheduler instead of being conflated with reviewed-pack maintenance;
- KB hybrid runtime facts are frozen against the actual `.venv` service runtime.

This is enough to call the target surface **production-grade usable for the upcoming manual test**.

It is **not** the same as declaring the entire repository globally production-ready.

## 2. What changed in V6

### A. Wrapper surface behavior

V6 carried forward the earlier wrapper hardening:

- broad advisor-only argument sets auto-route to the advisor lane;
- narrow requests still default to `coding-agent-v1`;
- wrapper/planning regression slices are green again.

### B. Planning bulk scoring and promotion

New live runner:

- [run_planning_bulk_groundedness_promotion.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_bulk_groundedness_promotion.py)

New live scheduler:

- [chatgptrest-planning-bulk-promotion.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-bulk-promotion.service)
- [chatgptrest-planning-bulk-promotion.timer](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-bulk-promotion.timer)

Live bounded run already demonstrated:

- planning active: `201 -> 242`
- planning candidate: `25 -> 538`
- staged reduced by `554`

Evidence:

- [planning bulk promotion summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_bulk_groundedness_promotion/20260408T031417Z/summary.json)

### C. Explicit planning runtime pack release chain

The main V6 gap was not raw pack export. It was the explicit release chain.

That chain is now fixed end-to-end:

1. raw reviewed pack export
2. offline validation
3. sensitivity audit
4. observability sample generation
5. explicit release bundle build
6. ready-bundle status verification

Key fix:

- [run_planning_runtime_pack_refresh.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_runtime_pack_refresh.py) now orchestrates the whole release pipeline instead of confusing raw-pack export with explicit-bundle readiness.

Fresh explicit bundle:

- [fresh release bundle manifest](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_runtime_pack_release_bundle/20260408T032206Z/release_bundle_manifest.json)

Fresh raw pack:

- [fresh reviewed runtime pack manifest](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_reviewed_runtime_pack/20260408T032206Z/manifest.json)

Release-chain evidence:

- [refresh summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_reviewed_runtime_pack/20260408T032206Z/refresh_summary.json)
- [offline validation summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_runtime_pack_validation/20260408T032206Z/summary.json)
- [sensitivity summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_runtime_pack_sensitivity_audit/20260408T032206Z/summary.json)

### D. Sensitivity gate resolution

The new pack initially failed sensitivity, but only because three atoms from one internal planning report matched the token `合同`.

After manual review, those atoms were approved for **internal explicit opt-in** because they describe contract/commercial guardrails rather than sensitive contract text or personal data.

Review spec:

- [planning runtime pack sensitivity review spec v1](/vol1/1000/projects/ChatgptREST/ops/data/planning_runtime_pack_sensitivity_review_v1.json)

### E. KB hybrid runtime hardening

Verified against the actual `.venv` runtime used by both API and MCP services:

- `fastembed` importable and working
- vector-enabled hits present
- live counts:
  - `kb_fts=941`
  - `kb_vectors=151`

Evidence:

- [KB hybrid probe summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_hybrid_runtime_probe/20260408T032254Z/summary.json)

## 3. Acceptance status

### Passed

1. Fresh explicit planning bundle is now the default ready bundle.
2. Fresh explicit bundle reports:
   - `ready_for_explicit_consumption=true`
   - `bundle_freshness=fresh`
3. Planning explicit query smoke returns fresh results from the new bundle.
4. MCP `/health` is green and reports primary-path readiness.
5. Both planning timers are installed and active:
   - bulk promotion timer
   - reviewed maintenance timer
6. Targeted regression suite for wrapper + planning plane + planning pack tooling is green.

Acceptance evidence pack:

- [V6 acceptance pack](/vol1/1000/projects/ChatgptREST/artifacts/monitor/v6_production_grade_acceptance/20260408T034324Z)
- [targeted regression output](/vol1/1000/projects/ChatgptREST/artifacts/monitor/v6_targeted_regression/20260408T034425Z/pytest.txt)

### Exact acceptance artifacts

- [planning runtime pack status and query smoke](/vol1/1000/projects/ChatgptREST/artifacts/monitor/v6_production_grade_acceptance/20260408T034324Z/planning_runtime_pack_status.json)
- [MCP health](/vol1/1000/projects/ChatgptREST/artifacts/monitor/v6_production_grade_acceptance/20260408T034324Z/mcp_health.json)
- [planning bulk promotion timer state](/vol1/1000/projects/ChatgptREST/artifacts/monitor/v6_production_grade_acceptance/20260408T034324Z/planning_bulk_promotion_timer_status.txt)
- [planning review maintenance timer state](/vol1/1000/projects/ChatgptREST/artifacts/monitor/v6_production_grade_acceptance/20260408T034324Z/planning_review_maintenance_timer_status.txt)

## 4. Production-grade claim boundary

The claim made here is intentionally narrow:

> The public coding-agent surface plus the planning explicit knowledge surface are now production-grade usable for the user's upcoming manual test.

The claim not made here:

> The entire ChatgptREST repository is globally green and fully re-baselined.

That broader claim is explicitly deferred to a later repo-wide stabilization wave.
