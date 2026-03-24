# 2026-03-11 Execution Experience Controller Rollup Manifest v1

## Why

After the mainline added:

- `controller_packet.json`
- `controller_action_plan.json`
- `progress_delta.json`
- `controller_update_note.md`

controller had both human-readable and machine-readable surfaces, but there was
still no single machine-readable index for the whole current controller bundle.

## What Changed

Added `ops/build_execution_experience_controller_rollup_manifest.py`.

The cycle now also writes:

- `controller_rollup_manifest.json`

It contains:

- current recommended action and reason
- current `progress_signal`
- availability flags for optional surfaces
- paths for:
  - `controller_packet`
  - `controller_action_plan`
  - `controller_update_note`
  - `progress_delta`
  - `governance_snapshot`
  - `attention_manifest`
  - `review_brief`
  - `review_reply_draft`
- referenced artifacts and constraints copied from the action plan

## Boundary

This stays entirely inside execution experience review-plane governance:

- no runtime adoption
- no active knowledge promotion
- no retrieval-default change
- no live canonical contract change
