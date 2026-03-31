# 2026-03-11 Archive Envelope Applicability Extensions

## Goal

Keep archive-envelope ingest aligned with the execution-extension preservation
work already done for:

- telemetry normalization
- live `activity:*` atoms
- `ActivityExtractor` review-plane atoms

Before this change:

- `ingest_commit_event()` and `ingest_closeout_event()` already preserved
  execution extensions in `episode.source_ext`
- but their atom `applicability` dropped those fields

## Change

Archive-envelope atoms now retain these execution extensions in
`atoms.applicability`:

- `task_ref`
- `trace_id`
- `lane_id`
- `role_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

## Why

Without this, archive/posthoc atoms lagged behind both:

- live canonical `activity:*` atoms
- review-plane `ActivityExtractor` atoms

That meant the same execution run could carry different metadata depending on
which ingest path materialized it.

## Validation

`tests/test_activity_ingest.py` now checks archive commit/closeout envelopes
for extension preservation in both:

- `episodes.source_ext`
- `atoms.applicability`
