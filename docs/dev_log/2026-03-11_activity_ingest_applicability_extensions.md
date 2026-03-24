# 2026-03-11 Activity Ingest Applicability Extensions

## Goal

Keep live canonical `activity:*` atoms aligned with:

- telemetry contract extension preservation
- episode `source_ext`
- review-plane `ActivityExtractor` applicability

Before this change, `ingest_activity_event()` preserved execution-layer
extensions only in `episode.source_ext`, but dropped them from atom
`applicability`.

## Change

`ingest_activity_event()` now carries these execution extensions into atom
`applicability` as well:

- `lane_id`
- `role_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

## Why

Without this, live canonical materialization and posthoc review-plane extraction
would diverge:

- review-plane atoms kept execution context
- live `activity:*` atoms lost it

That made routing, debugging, and future candidate/review-first extraction less
consistent than they needed to be.

## Validation

`tests/test_activity_ingest.py::test_activity_event_preserves_execution_extensions`
now asserts the extensions survive in both:

- `episodes.source_ext`
- `atoms.applicability`
