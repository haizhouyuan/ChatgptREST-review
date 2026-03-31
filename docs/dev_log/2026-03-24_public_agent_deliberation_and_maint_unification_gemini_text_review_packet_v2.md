# 2026-03-24 Public Agent Deliberation And Maint Unification Gemini Text Review Packet v2

## Task

Review the current `Public Agent deliberation + maintenance unification` direction and the current repo state.

Deliver:

1. findings first, ordered by severity
2. architecture verdict
3. open risks / assumptions
4. recommended changes

Be strict. Do not be agreeable by default.

## Intended Architecture Direction

The proposed architecture says:

1. Public Agent should remain the only general northbound entry for external agents and clients.
2. Deliberation should become an internal advanced reasoning plane under Public Agent, not a parallel public review controller.
3. Maint Controller should remain separate because it has different privileges, action boundaries, and risk model.
4. OpenClaw maintagent should become the maintenance brain that holds canonical machine context from the maint repository.
5. Guardian should be removed, with deterministic sweep and notify absorbed into maint daemon, and judgment and escalation absorbed into maintagent.

The same blueprint also proposes:

- a deliberation tool family with start, status, cancel, and attach
- deterministic work-package tools for prepare, validate, channel compilation, and submit
- formal reasoning modes such as single review, dual review, and red-blue debate

## Current Repo Facts To Evaluate Against

Please judge the architecture against these concrete current facts.

### A. Public Agent MCP is still intentionally minimal

The current public MCP surface is still centered on three minimal tools:

- advisor agent turn
- advisor agent status
- advisor agent cancel

It is not currently exposing a separate deliberation tool family or deterministic work-package family.

### B. Consult and review are still a separate public surface today

Current FastAPI composition still loads a consult router alongside advisor v3 and agent v3.
So review and consult are not yet fully internalized under the agent v3 public facade.

### C. Consult still owns a separate consultation state universe

The current consult router still exposes public consult endpoints and still uses an in-memory consultations map for consultation state.

### D. Agent v3 still bridges consult and dual review through consult semantics

Current agent v3 does not yet have a unified deliberation ledger.
It still maps consult and dual-review style asks into consult defaults and returns a separate consultation identifier.

### E. Guardian is still live and still carries policy and lifecycle behavior

Current topology still includes guardian wake behavior for main.
The guardian runner still does more than simple patrol or notify. It includes behavior around:

- ChatGPT Pro trivial prompt checks
- violation filtering
- system client classification
- guarded repair check guidance
- client issue stale and close sweeps

### F. Maintagent is not yet wired as the real maintenance brain

Current rebuild and OpenClaw configuration still frames maintagent more as a watchdog or read-mostly lane for main, with minimal tool exposure.

### G. The maint repository is already shared into current maintenance paths

The canonical machine-context direction is reasonable, but the repo already shares maint memory into:

- maint daemon Codex prompt bootstrap
- SRE lane prompt bootstrap

So the maint repository is already a shared maintenance substrate, not something uniquely consumed by maintagent in current execution.

### H. Deterministic review and work-package tooling is still CLI/manual and partly fail-open

Current review packaging and review-repo sync tooling exists, but it is not yet a server-enforced deterministic compiler plane.

Current facts:

- the review packer is still a local CLI tool
- public review sync still depends on a sync script
- some workflow validation still warns and asks humans to verify uploads
- Gemini file-count and size checks are not yet fully centralized as a hard server gate

## Review Questions

Please evaluate the following strictly:

1. Is it architecturally correct to keep Public Agent as the only general northbound entry and treat review or deliberation as an internal mode rather than a peer controller?
2. Is Maint Controller correctly kept separate?
3. Is removing guardian directionally right, or premature for the current repo state?
4. Is maintagent currently ready to become the maintenance brain, or is that still aspirational?
5. Is the proposed deterministic work-package plane coherent, or is it currently under-specified relative to the repo state?
6. Are hard channel rules and repo-first versus attachment-first semantics correctly defined, or still too fragmented?
7. Is the rollout order safe?

## Expected Strictness

If the architecture direction is right but the current repo has not actually achieved that unification yet, say that clearly.

If new top-level deliberation or work-package MCP families would contradict the single-entry rule, say that clearly.

If guardian still contains live policy semantics that have not yet been remapped, say that clearly.
