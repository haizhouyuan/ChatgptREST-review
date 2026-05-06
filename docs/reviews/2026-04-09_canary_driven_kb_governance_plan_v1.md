# 2026-04-09 Canary-Driven KB Governance Plan v1

## Judgment

The next KB governance wave should not be a broad inventory-first cleanup.

It should be a canary-driven governance loop:

1. observe real misses
2. classify the miss
3. decide whether the gap is:
   - missing source material
   - weak promotion
   - weak ranking
   - entity mismatch
   - packet/context issue
4. apply targeted ingestion / promotion / ranking correction

## Why this is the right order

Current state:

- critical rollout promotion gap is already bounded
- recall benchmark already passes for bridge use cases
- entity-grade recall is still the exposed weakness

So the highest-value KB work now comes from real Feishu canary misses, not from another abstract full-library cleanup campaign.

## Governance loop

### K1. Miss capture

For each canary miss, record:

- raw ask
- expected outcome
- actual outcome
- retrieval posture
- whether the failure was:
  - no-hit
  - bridge-only
  - wrong-entity
  - wrong-project
  - closure failure

### K2. Triage

Each miss should be triaged into one of four actions:

1. targeted re-ingest
2. promotion / active coverage improvement
3. ranking / entity boost
4. no KB action; route or closure issue instead

### K3. Evidence-backed correction

Every KB change should leave:

- before/after retrieval evidence
- live artifact or harness rerun
- explicit statement whether the change improved bridge recall or entity recall

## Explicit anti-patterns

Do not:

- pause canary just to run another full-library cleanup
- claim entity-grade improvement when only bridge recall improved
- promote broad slices without retrieval-surface guards
- erase interaction history when fresh identity is enough for replay hygiene

## Acceptance

This KB governance loop is working when:

- canary miss triage becomes repeatable
- each real miss maps to a bounded KB action or a bounded non-KB action
- entity-grade recall improves on real company-profile asks
- promotion does not regress into critical rollout failure
