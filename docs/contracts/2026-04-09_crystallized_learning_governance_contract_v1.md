# Crystallized Learning Governance Contract v1

Date: 2026-04-09  
Status: canonical governance contract for packet-projected crystallized learning

## Purpose

This contract defines how interaction-learning preferences may be turned into packet-visible crystals without silently becoming a second authority layer.

The goal is:

- preserve bounded cross-session learning
- keep the authority anchor above all crystals
- make crystal generation, supersession, and shadow observation measurable

## Current source and scope

Current source:

- interaction-learning memory derived from audited `user_correction` writeback

Current scope:

- thread-scoped interaction learning
- packet projection only
- no standalone durable crystal runtime

## Governance posture

Current runtime posture is:

- `projection_mode = shadow`
- crystals are advisory only
- crystals may appear in the wake-up packet and packet receipt
- crystals may not silently override the authority anchor

Shadow mode means:

- crystals are visible and measurable
- wider reuse claims are blocked until observation evidence exists
- medium/high-risk crystal samples remain shadow-only

## Current support threshold

Current threshold:

- `INTERACTION_LEARNING_MIN_SUPPORT = 2`

This threshold remains unchanged in this phase.

Any future threshold change is a product-semantic change and requires explicit sign-off.

## Crystal allowlist

Only these preference dimensions may crystallize:

- `raw_ingress_mode`
- `quality_bar`
- `preferred_executor_family`
- `closure_style`
- `brevity_preference`
- `depth_preference`
- `focus_preference`
- `reply_first_preference`

## Crystal denylist

These dimensions are reserved for higher-priority authority or runtime control and may not crystallize:

- `owner`
- `goal`
- `non_goals`
- `project_ref`
- `project_context`
- `planning_base`
- `frozen_facts`
- `style_rules`
- `authority_docs`
- `current_phase`
- `current_phase_framing`
- `last_reviewed_at`
- `quality_gate`
- `planning_profile`
- `required_sections`

Unknown future preference keys are treated as denied until explicitly added to the allowlist.

## Crystal metadata requirements

Every active crystal must carry:

- `schema_version`
- `crystal_id`
- `source_record_id`
- `source_key`
- `scope`
- `stable_preferences`
- `support_threshold`
- `support`
- `provenance`
- `governance`
- `supersession`
- `invalidation`
- `shadow_observation`
- `precedence_note`

Current receipt contract:

- `applied`
- `projection_mode`
- `support_threshold`
- `stable_preference_keys`
- `superseded_count`
- `denied_preference_count`
- `shadow_required`

## Supersession and invalidation

Current invalidation mode:

- `superseded_by_newer_interaction_learning_record`

Current invalidation SLA:

- `No later than the next thread-scoped interaction-learning load and packet compile after a newer stable winner is persisted.`

Current supersession semantics:

- alternative preference values that still meet the support threshold are reported as superseded candidates
- superseded candidates are queryable through the governance report artifacts

## Operator entrypoint

Canonical report command:

```bash
cd /vol1/1000/projects/ChatgptREST
python3 ops/report_crystallized_learning_governance.py \
  --output-dir artifacts/monitor/crystallized_learning_governance/live/<stamp>
```

Notes:

- live memory may legitimately report `0` crystals if no audited `user_correction` records exist yet
- shadow-mode fixture evidence may be generated separately to validate the governance pipeline before live adoption

## Acceptance evidence

Implementation and focused tests:

- `chatgptrest/advisor/crystallized_learning.py`
- `chatgptrest/cognitive/wakeup_packet.py`
- `ops/report_crystallized_learning_governance.py`
- `tests/test_crystallized_learning.py`
- `tests/test_wakeup_packet.py`
- `tests/test_report_crystallized_learning_governance.py`

Archived evidence:

- live report:
  - `artifacts/monitor/crystallized_learning_governance/live/20260409T054241Z/crystallized_learning_governance_20260409T054241Z.json`
  - `artifacts/monitor/crystallized_learning_governance/live/20260409T054241Z/crystallized_learning_governance_20260409T054241Z.md`
  - `artifacts/monitor/crystallized_learning_governance/live/20260409T054241Z/crystallized_learning_manual_review_20260409T054241Z.md`
- shadow fixture report:
  - `artifacts/monitor/crystallized_learning_governance/fixture/20260409T054241Z/crystallized_learning_governance_20260409T054241Z.json`
  - `artifacts/monitor/crystallized_learning_governance/fixture/20260409T054241Z/crystallized_learning_governance_20260409T054241Z.md`
  - `artifacts/monitor/crystallized_learning_governance/fixture/20260409T054241Z/crystallized_learning_manual_review_20260409T054241Z.md`

## Residual risks

- live interaction-learning volume is currently zero on this host, so shadow evidence still depends on the controlled fixture run
- precedence remains structurally bounded by allow/deny + advisory labeling, but the final language model still resolves advisory text at prompt time
- wider reuse remains blocked until canary evidence exists in later production-readiness phases
