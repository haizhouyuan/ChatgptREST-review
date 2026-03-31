# 2026-03-11 Planning Reviewed Runtime Pack Walkthrough v1

## What changed

The planning workstream already had:

- reviewed slice
- allowlist
- bootstrap active set
- maintenance audits

This round turns that reviewed slice into a concrete, runtime-readable **opt-in pack** without changing default runtime behavior.

## Why this matters

Mainline asked for a way to make the reviewed planning slice quickly consumable after a later explicit runtime hook lands.

The exporter solves that by packaging only the reviewed/allowlisted/live subset and writing the constraints directly into the manifest:

- opt-in only
- no default cutover
- no staged-only atoms

So the pack is ready for explicit use later, but the current runtime remains unchanged.
