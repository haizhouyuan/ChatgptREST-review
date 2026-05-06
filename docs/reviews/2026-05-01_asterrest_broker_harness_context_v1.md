# AsterREST Broker/Harness Context v1

Date: 2026-05-01

## Background

AsterREST is a local service that lets coding agents submit external web-model tasks through a durable job queue. It already has:

- idempotent job creation
- background workers
- public MCP-style tools
- answer artifacts
- raw conversation export artifacts
- completion/finality contracts
- provider cooldown and rate-limit handling
- basic health probes and maintenance daemon logic
- read-only conversation URL recovery

The main pain point is that browser UI automation is still too brittle and too manual to operate. The user only needs this lane a few times per day, but the maintenance burden is high when browser UI state changes, provider rate limits appear, exports stall, or answers appear in the browser but are not persisted.

## Recent Historical Problems

Recent incidents include:

- frontend rate-limit modal surfaced in the browser while export/retry loops were still active
- backend conversation export 429 was initially treated too much like a successful fallback
- long premium/research answers were visible later in the browser, but the job system had already terminalized as needing follow-up
- a manual protection guard stopped workers and caused new jobs to stay queued
- client wrappers sometimes retried with new keys or submitted duplicate work when the correct action was to wait, reuse, or repair the same job
- a stale public MCP process exposed an old tool list, hiding dedicated conversation recovery tools
- historical ask jobs associated with a conversation URL had a valid raw export, but their rendered answer artifact was not a full conversation transcript

## Current Fixes Already Landed

The system now has:

- dedicated public conversation recovery tools:
  - `automation_conversation_find`
  - `automation_conversation_fetch`
  - `automation_conversation_get`
- validation that fails if those tools are missing from the live public surface
- live smoke proof that a multi-turn human-created conversation can be fetched read-only and rendered into a full Markdown transcript
- skill guidance that full conversation recovery should prefer dedicated conversation-export jobs rather than reusing ask jobs

These improvements help with answer retrieval, but they do not solve the broader browser automation intelligence and observability problem.

## Competing Proposal We Are Reviewing

One candidate proposal says: the current deterministic script approach is a losing battle because web UIs change frequently. It recommends moving toward an agent-driven browser automation runtime:

- task planner
- hybrid executor
- deterministic Playwright path for most steps
- accessibility snapshots for low-cost state checks
- semantic locator tools for selector drift
- visual QA for final validation
- general browser agent fallback for hard UI changes
- action ledger and screenshot timeline
- TaskFabric service exposing a few simple broker tools

The strongest idea in that proposal is using agentic recovery only where deterministic automation fails. The weakest part may be underestimating the existing job kernel and the risk of letting browser agents act freely on a shared browser session.

## Our Current Independent Position

We think the right direction is not to replace AsterREST with a free-form browser agent.

The safer target is:

```text
AsterREST Job Kernel
+ Browser Harness
+ Adaptive Recovery
+ TaskFabric ExternalModelBrokerAgent
```

### Job Kernel

Keep responsibility for:

- idempotency
- queueing
- worker leases
- provider/lane selection truth
- cooldown and rate-limit state
- artifacts
- answer finality contracts
- push/result delivery

### Browser Harness

Add responsibility for:

- browser action ledger
- before/after screenshots when appropriate
- DOM or accessibility snapshots
- current URL and tab identity
- network/console summary
- structured failure class
- recovery action chosen
- replay bundle per job

### Adaptive Recovery

Only trigger on exception paths:

- selector timeout
- unexpected modal
- login/challenge page
- answer visible but export missing
- finality mismatch
- browser crash / target closed
- rate-limit modal

Use the cheapest useful observation first:

1. deterministic selector
2. accessibility tree
3. semantic locator / DOM reasoning
4. screenshot crop
5. visual QA or general browser agent
6. human interrupt

### ExternalModelBrokerAgent

This should be a TaskFabric role that owns the external model lane. Other agents should not manage browser sessions directly. The broker should expose a small business interface:

- submit ask
- fetch conversation URL
- report status
- return result
- attach artifacts and quality evidence

## Important Constraints

- The operator may also be using the same provider Web account manually.
- The system must not interfere with the operator's active browser use.
- Provider frontend rate limits should be treated as stop-the-world for that provider lane.
- Browser automation must be auditable after the fact.
- Recovery should prefer fail-closed behavior over click-through behavior when account/session risk is involved.
- Token costs are acceptable if used only for rare recovery and validation, but not for every browser action.
- The northbound public interface should stay stable; new broker tools should not break current job tools.

## Current Questions

1. Is our proposed architecture too conservative, or is it the correct production posture?
2. Should semantic/agentic browser tools be introduced in P0, or only after ledger/replay and failure classification exist?
3. What is the minimum useful browser action ledger?
4. How should we isolate manual operator sessions from automated sessions?
5. How should TaskFabric delegate to the broker without leaking browser complexity to every agent?
6. What acceptance tests prove that this is safer and more maintainable than the current implementation?

