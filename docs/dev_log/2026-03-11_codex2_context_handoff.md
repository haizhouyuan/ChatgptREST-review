# 2026-03-11 Codex2 Context Handoff

You are `codex2`, a secondary Codex pane for `/vol1/1000/projects/ChatgptREST`.

Your job is **not** to redefine architecture or fork the mainline. Your job is to:

- understand the current mainline state
- preserve background context
- be ready to continue from the current boundary without re-deriving history
- avoid conflicting with the primary mainline Codex

## Identity and Boundary

- The **primary controller** is the mainline Codex in the main pane.
- `codex2` is a **context-preserving secondary pane**, not a second controller.
- Do not independently change product direction.
- Do not touch unrelated dirty files or generated artifacts.

## Current Architecture Baseline

The current high-level architecture is intentionally narrow:

- `OpenClaw` is the shell / execution entry layer.
- `OpenMind / ChatgptREST` is the cognition substrate.
- `main` is the only long-lived controller.
- `maintagent` is watchdog-only, not a second controller.
- Role packs are constrained to explicit `devops` / `research`.
- `EvoMap` is governance / review / runtime knowledge infrastructure, not a second brain.

## Current Mainline State

The primary mainline workstream has already pushed the execution telemetry -> EvoMap path to a stable review-maintenance boundary.

Already landed:

- live canonical coverage via:
  - manual `/v2/telemetry/ingest`
  - `controller_lane_wrapper`
  - OpenClaw `openmind-telemetry` plugin
  - archive envelopes (`agent.task.closeout`, `agent.git.commit`)
- execution activity parity between:
  - live runtime ingest
  - archive/review-plane extraction
- execution review maintenance surface:
  - state audit
  - review queue
  - review bundle
  - decision scaffold
  - single maintenance cycle

Mainline stopping point:

- do **not** jump to active experience knowledge
- do **not** change runtime retrieval defaults
- do **not** fold planning review-plane into runtime cutover
- do **not** build a second live canonical event system

## Coordination Issue Mapping

There are two coordination issues:

- `#114`
  - planning import / review-plane -> EvoMap line
  - this line may continue **review-plane maintenance / bootstrap maintenance**
  - it must **not** do runtime retrieval cutover by default

- `#115`
  - multi-agent execution-layer / contract-supply line
  - this line may continue **artifact / fixture / mapping / capability contract supply**
  - it must **not** do runtime adoption / event-standard fork / adapter-registry platform work

## Current Cross-Codex Boundaries

### Planning / `#114`

Accepted boundary:

- allowed:
  - planning review-plane canonical baseline maintenance
  - backlog visibility
  - deterministic priority queue / bundle / scaffold / cycle
  - bootstrap active-set maintenance inside the planning family
- not allowed:
  - runtime retrieval defaults changes
  - planning runtime cutover
  - changing execution telemetry contracts

The planning line has reached a maintenance stopping point:

- reviewed slice audit
- backlog audit
- deterministic priority queue
- portable bundle
- scaffold TSV
- single maintenance cycle

### Execution / `#115`

Accepted boundary:

- allowed:
  - fixture bundles
  - projection/mapping bundles
  - capability matrix
  - degraded examples
  - review-friendly artifact supply
- not allowed:
  - runtime adoption
  - execution platform / orchestrator implementation
  - second live event standard
  - promotion to active knowledge

The execution supply line has already delivered:

- emitter fixture bundle
- projection/mapping bundle
- capability matrix
- degraded example bundle

Mainline already consumes those artifacts as regression inputs.

## Recent Coordination Infrastructure Fix

The issue-reply wake path was just hardened in commit `6984c15`:

- `watch_github_issue_replies.py` now uses:
  - `Escape -> C-u -> send text -> delay -> C-m`
- `poll_coordination_issues.py` now supports:
  - pane wake
  - issue-specific pane mapping

Current intended pane mapping:

- `#114 -> %31`
- `#115 -> %32`

## Current Next-Step Logic

If no new direction is given, treat the current state like this:

1. Mainline execution telemetry work is at a valid stopping point.
2. Planning and execution-side codex lanes are parked at acceptable maintenance / supply boundaries.
3. The next real mainline project should only start when explicitly chosen from one of:
   - lineage remediation
   - review decision automation
   - candidate/review experience extraction
   - another explicitly approved EvoMap/runtime slice

## What Codex2 Should Do Right Now

1. Read this handoff carefully.
2. Summarize the current architecture, issue boundaries, and stopping points in a short note.
3. Do **not** start broad new implementation automatically.
4. Stay ready to continue from this exact boundary when asked.

## Files Worth Knowing

- `docs/dev_log/2026-03-11_issue_reply_wake_submit_delay_and_poller_wake.md`
- `docs/dev_log/2026-03-11_execution_activity_review_cycle.md`
- `docs/dev_log/2026-03-11_planning_review_priority_cycle_v1.md`
- `docs/dev_log/2026-03-11_execution_emitter_capability_matrix_v1.md`
- `ops/poll_coordination_issues.py`
- `ops/watch_github_issue_replies.py`

## Final Rule

Preserve the current architecture. Do not reopen already-settled high-level debates unless new evidence forces it.
