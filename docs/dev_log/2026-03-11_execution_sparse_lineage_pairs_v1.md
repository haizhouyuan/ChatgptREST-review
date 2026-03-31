# 2026-03-11 Execution Sparse Lineage Pairs v1

## Goal

Add paired sparse examples for:

- one live bus execution event
- one archive envelope execution event

so review can see how shared lineage still works when fields are missing.

## Artifact files

Artifact root:

- `docs/dev_log/artifacts/execution_emitter_review_bundle_20260311/`

Included sparse pair artifacts:

1. `sparse_live_bus_pair_v1.json`
2. `sparse_archive_envelope_pair_v1.json`
3. `sparse_lineage_pair_expectations_v1.json`

## Pair choice

The pair is intentionally sparse:

- shared anchors: `task_ref`, `trace_id`
- missing from both: `session_id`, `run_id`
- no execution extensions on the live side
- only one execution extension on the archive side

This keeps the examples realistic for degraded or partial producers.

## Why this matters

The previous mapping bundles showed rich cases. This bundle shows the opposite:

- shared execution lineage does not require a full identity tuple
- live and archive shapes can still correlate with only a small common core
- optional execution extensions remain optional even in paired examples

## Review intent

This is meant to reduce over-assumption during mainline review:

- sparse live bus events are normal
- sparse archive envelopes are normal
- correlation should degrade gracefully instead of assuming complete payloads
