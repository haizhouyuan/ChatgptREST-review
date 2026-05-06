# 2026-03-11 Planning Review Consistency Hardening Walkthrough v1

## What I did

I added a narrow maintenance-only consistency layer for the `planning -> EvoMap` workstream.

The new audit script composes the three existing maintenance views:

- reviewed/live state
- backlog shape
- deterministic priority queue

The cycle command now emits this combined view as `consistency_audit.json` and exposes a single `consistency_ok` flag in the cycle summary.

## Why this change

Mainline requested a narrow hardening task inside the existing boundary:

- stay in `planning review-plane / bootstrap maintenance`
- do not enter runtime cutover
- protect consistency across reviewed slice, backlog, allowlist, and live bootstrap atoms

The repo already had the raw ingredients, but there was no single artifact that answered:

- does reviewed + backlog still partition the planning corpus?
- is the allowlist still covered by live active/candidate atoms?
- have any planning bootstrap atoms drifted outside the current allowlist?
- is the priority queue still a deterministic subset of the current backlog?

This patch closes that gap without changing retrieval or promotion semantics.

## Result

The canonical maintenance check is green:

- `consistency_ok = true`
- all seven consistency checks returned `true`

That means the current planning reviewed slice and backlog remain aligned after the prior maintenance work, and the priority cycle now exposes that alignment explicitly.
