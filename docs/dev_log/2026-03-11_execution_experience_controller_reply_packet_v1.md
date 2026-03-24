# 2026-03-11 Execution Experience Controller Reply Packet v1

## Why

By this point the execution experience review plane already had:

- controller status surfaces
- cross-cycle progress surfaces
- a machine-readable rollup manifest

What it still lacked was a final manual-send payload that turned those review
surfaces into a stable controller decision/reply packet without enabling
auto-commenting.

## What Changed

Added `ops/build_execution_experience_controller_reply_packet.py`.

The cycle now also writes:

- `controller_reply_packet.json`

It contains:

- `decision`
  - `recommended_action`
  - `reason`
  - `progress_signal`
  - `reply_kind`
  - `manual_send_required`
  - `auto_send_allowed=false`
- `reply.comment_markdown`
  - a ready-to-send manual comment body assembled from the current controller state
- `paths`
  - rollup manifest, update note, review brief, reply draft, and related surface paths
- `constraints`
  - inherited from the action plan

## Boundary

This is still review-plane only:

- no auto-commenting
- no runtime adoption
- no active knowledge promotion
- no live canonical contract change
