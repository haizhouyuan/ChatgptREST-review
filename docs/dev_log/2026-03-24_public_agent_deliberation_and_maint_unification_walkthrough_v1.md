# 2026-03-24 Public Agent Deliberation And Maint Unification Walkthrough v1

## Why This Exists

The previous architecture work solved important local problems:

- Public Agent became the canonical northbound surface
- Maint Controller became a canonical maintenance control plane on `sre` lanes
- review-pack/review-repo capabilities remained available
- `/vol1/maint` was cleaned up into a meaningful machine-context repository

But the next step had a real risk of going wrong:

- a new standalone Review Controller could duplicate Public Agent
- `guardian` could remain a third maintenance cognition layer
- deterministic packaging logic could get mixed into LLM-backed flows

This blueprint and plan were written to stop that drift before implementation.

## What Was Decided

### 1. Review Does Not Become A Second Public Brain

Review and debate capabilities should be implemented as a **deliberation plane under Public Agent**, not as a parallel public controller.

That keeps:

- one general northbound task surface
- multiple internal execution modes

instead of multiple competing entry points.

### 2. Maintenance Stays Separate

Maintenance work still needs a separate controller because it has different:

- privileges
- guardrails
- risk model
- takeover semantics

So Maint Controller stays separate.

### 3. `maintagent` Owns Machine Context

The full machine and workspace context in `/vol1/maint` should belong by default to `OpenClaw maintagent`, not every agent.

This keeps the system from over-broadcasting full-machine context everywhere.

### 4. `guardian` Should Disappear

The architecture should converge to:

- `maint_daemon` for deterministic patrol/evidence
- `maintagent` for maintenance cognition/escalation

and not preserve `guardian` as another attention brain.

### 5. Packaging/Validation Must Stay Deterministic

Things like:

- package assembly
- `master_single` checks
- file-count enforcement
- reviewer-channel fail-closed policy

belong in deterministic MCP tools, not in LLM reasoning.

## Why This Is Better

This gives the system:

- one public task brain
- one internal deliberation plane
- one maintenance brain
- one deterministic packaging/gating layer

instead of many overlapping controller-like subsystems.

## What Happens Next

The development plan phases the work so the riskiest architectural cleanup happens first:

1. remove/absorb `guardian`
2. wire `maintagent` to canonical machine context
3. add deterministic work-package tools
4. add `deliberation_start`
5. extend to `dual_review`
6. extend to `red_blue_debate`
7. align wrappers and agent docs

## Bottom Line

The main decision is not “add another controller”.

It is:

- keep **Public Agent** as the single public task surface
- keep **Maint Controller** as the separate maintenance surface
- make **deliberation** an internal Public Agent mode
- make **`maintagent`** the real maintenance brain
- delete **`guardian`** as a competing maintenance cognition layer
