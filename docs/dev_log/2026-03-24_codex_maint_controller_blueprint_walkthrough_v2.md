# 2026-03-24 Codex Maint Controller Blueprint Walkthrough v2

## Why v2 Exists

The `v1` direction was correct, but two implementation ambiguities remained:

1. `taskpack/*` could be misread as a second canonical request/prompt surface inside the lane
2. incident-side `incidents/<id>/codex/*` could be left alive as a second writable Codex evidence tree

`v2` closes both ambiguities before implementation starts.

## What Changed

### 1. `taskpack/*` Is Now Explicitly A Projection

`taskpack/*` is no longer described as a separate canonical file tree.

In `v2`, it is defined as a standardized projection on top of existing lane artifacts:

- `requests/*.json`
- `codex/*.prompt.md`
- `codex/*.decision.json`
- lane manifest fields

Canonical writes remain on the existing lane files.

### 2. Incident-Side Codex Artifacts Are Explicitly Downgraded

`v2` now states that once the controller is implemented:

- `incidents/<id>/codex/*` may only be mirror/evidence copies
- or explicit pointers to lane artifacts

They must not remain an independently writable Codex tree in parallel with lane state.

### 3. The Canonical Ledger Rule Is Stronger

The controller still centers on `sre.fix_request`, but `v2` tightens the rule from:

- "lane state is canonical"

to:

- "lane state is canonical and any derived view or evidence tree must remain secondary"

## Why This Matters

Without these two clarifications, implementation would likely recreate the very state split the blueprint was trying to eliminate.

`v2` removes that ambiguity before code work begins.
