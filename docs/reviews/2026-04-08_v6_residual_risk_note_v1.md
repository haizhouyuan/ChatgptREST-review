# V6 Residual Risk Note V1

Date: 2026-04-08

Related:

- [V6 Production-Grade Completion Summary V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_v6_production_grade_completion_summary_v1.md)

## 1. What remains intentionally deferred

### R1. Whole-repo full-suite re-baseline

An exploratory full `pytest -q` run was started during V6 and surfaced multiple failures outside the V6 acceptance slice before the run was stopped.

This means:

- V6 acceptance is based on targeted regression slices plus live/runtime evidence;
- V6 does **not** certify the entire repository as globally green.

### R2. Broad `scope_project` live backfill

Still deferred.

Reason:

- the previously identified mismatch families remain unresolved at the policy/governance level;
- V6 did not reopen broad writeback into the live DB.

### R3. Generic promotion-engine scheduling across all knowledge

V6 restored a **planning-specific** bulk promotion lane and kept the reviewed-pack maintenance lane separate.

It did **not** claim that all EvoMap promotion scheduling across all sources/projects is now fully solved.

### R4. Pack breadth is still allowlist-bounded

The explicit planning pack is fresh, but its breadth is still bounded by the current reviewed allowlist.

This is why the new bundle is fresh without growing beyond:

- `exported_docs=116`
- `exported_atoms=258`

### R5. Candidate-heavy planning knowledge remains curated

V6 safely increased candidate coverage, but it did not convert the whole planning substrate into direct `active` retrieval.

That is intentional:

- anchored atoms can move toward `active`
- non-anchored but reviewed-eligible planning atoms stay in curated explicit-pack lanes unless stronger evidence exists

## 2. What is no longer a valid blocker

These older blockers are now closed:

1. jobs answer primary path auth mismatch
2. public MCP missing `/health`
3. stale March 11 explicit planning bundle still being the default ready bundle
4. planning-review maintenance scheduler being confused with bulk promotion scheduling

## 3. Recommendation for manual testing

The user’s next manual test should focus on:

1. public coding-agent flows
2. planning/explicit knowledge flows
3. advisor-backed planning questions that should benefit from the fresh explicit pack

It should **not** be interpreted as a blanket certification of the entire repository test suite.
