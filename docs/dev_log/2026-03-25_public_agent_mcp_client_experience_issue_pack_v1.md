# 2026-03-25 Public Agent MCP Client Experience Issue Pack v1

## Summary

This note captures a real client-side usage trace of the public advisor-agent MCP surface from a Codex session that was packaging a two-wheeler strategic research packet and sending it to Pro for method review.

The public MCP surface is usable and materially better than direct low-level REST from a coding-agent perspective. The request was accepted, routed correctly, and preserved strong intake metadata.

However, the client experience still has several rough edges that are now visible in real work:

1. `advisor_agent_turn.attachments` is too strict ergonomically.
2. `delivery_mode=sync` silently degrading into deferred/background is not surfaced clearly enough.
3. Long-running advisor sessions still lack a true `wait`/terminal-result retrieval primitive on the public MCP surface.
4. Progress telemetry for long-running report-grade turns is too thin for coding-agent workflows.
5. Public MCP/client schema alignment still needs stronger guarantees as northbound capabilities evolve.

This is **not** a claim that the system is broken. It is a claim that client ergonomics and operability can be improved materially.

## Scope

This issue pack is about:

1. The coding-agent experience of the **public** MCP surface at `http://127.0.0.1:18712/mcp`
2. Real use of:
   - `advisor_agent_turn`
   - `advisor_agent_status`
3. A report-grade Pro review request with one markdown attachment

This issue pack is **not** about:

1. Direct low-level `/v1/jobs` usage
2. Admin/broad MCP
3. The earlier mis-bound built-in connector problem where another Codex session did not hit the correct systemd-managed MCP instance

That earlier connector misbinding was a client binding/configuration problem, not a defect in the public MCP service itself.

## What Worked Well

### 1. The public MCP surface accepted the real task cleanly

After correcting the attachment payload shape, the request was accepted and routed through the intended high-level `report` lane instead of requiring any low-level REST workaround.

### 2. Intake metadata was rich and useful

The returned body exposed:

1. `task_intake`
2. `contract`
3. `scenario_pack`
4. `control_plane`
5. `delivery`
6. `lifecycle`

That is valuable for coding agents, because it makes routing and policy effects inspectable.

### 3. Provenance was good

The status response surfaced:

1. final provider path
2. route
3. job id
4. conversation URL artifact

### 4. Strict evidence grounding was visible

The control plane made it explicit that the turn was grounded in the attached file and expected traceable, report-grade output.

## Real Usage Trace

The client sequence was:

1. Prepared a single-file review packet in the planning repo
2. Called `advisor_agent_turn(...)` with:
   - one attached markdown file
   - `goal_hint=report`
   - `depth=deep`
   - `delivery_mode=sync`
3. Hit one transport/schema validation problem
4. Resubmitted with corrected payload shape
5. Request was accepted and auto-backgrounded
6. Client began polling `advisor_agent_status(...)`

Observed runtime details:

1. Route: `report`
2. Final provider: `chatgpt`
3. Session was accepted and execution started normally
4. A conversation URL artifact appeared while the report was still running

So the issue is not “request failed.” The issue is the ergonomics and observability around getting a long-running answer back as a coding-agent client.

## Client Issues

## Issue A: `attachments` payload ergonomics are too strict

### What happened

The first `advisor_agent_turn` call used:

- `attachments: "/abs/path/file.md"`

The tool rejected it with a validation error that `attachments` must be a list.

### Why this matters

For coding-agent clients, one-file attachment is a very common case. Requiring list-only transport is not inherently wrong, but it is brittle ergonomically, because:

1. The natural single-file representation is a scalar path.
2. The failure happens at the transport layer rather than being normalized automatically.
3. The error is technically correct but not operator-friendly enough.

### Expected behavior

One of these should happen:

1. The MCP surface accepts both `string` and `list[string]` and normalizes to a list.
2. Or the error message explicitly says:
   - `attachments must be a list; try ["..."]`

### Proposed fix

P0 candidate:

1. Accept scalar attachment sugar at the MCP boundary and normalize internally.
2. If that is rejected by policy, return an explicit remediation hint in the validation error.

## Issue B: `sync` → deferred/background transition is not clear enough for clients

### What happened

The client requested:

- `delivery_mode=sync`

The service accepted the turn but returned:

1. `delivery_mode_requested = sync`
2. `delivery_mode_effective = deferred`
3. background watch metadata

This behavior is reasonable for long-running jobs, but the client-facing semantics are still too subtle.

### Why this matters

From a coding-agent perspective, the important question is not just “was the request accepted?”, but:

`should I now wait, poll, or consider this turn complete for the moment?`

### Expected behavior

When `sync` is auto-downgraded to background execution, the response should make the handoff more explicit:

1. `accepted_for_background = true`
2. `why_sync_was_not_possible = long_goal_auto_background`
3. `recommended_client_action = poll_status|wait|watch`

### Proposed fix

P0/P1 candidate:

1. Keep the current fields, but add one concise client-action field.
2. Return a more obvious human/machine-readable handoff block.

## Issue C: public MCP still lacks a true wait primitive for advisor sessions

### What happened

Once the report-grade turn was backgrounded, the client only had:

1. `advisor_agent_status`
2. `advisor_agent_cancel`

There is no public advisor-session equivalent of:

1. a blocking `wait`
2. a background wait handle getter
3. a “return terminal answer when ready” helper

### Why this matters

For long-running report/research turns, plain polling is workable but suboptimal:

1. Clients need custom loops.
2. There is no single “done or timeout” primitive.
3. It increases boilerplate and makes different coding agents implement slightly different polling behavior.

### Expected behavior

The public surface should expose one of:

1. `advisor_agent_wait(session_id, timeout_seconds)`
2. or `advisor_agent_watch_get(watch_id)`
3. or a terminal-answer retrieval primitive with long polling semantics

### Proposed fix

P1 candidate:

1. Add a high-level wait helper to the public MCP surface.
2. Make it return:
   - terminal status
   - answer if ready
   - artifacts if ready
   - timeout status if not ready

## Issue D: progress telemetry is still too thin for long report-grade runs

### What happened

Repeated `advisor_agent_status` calls showed:

1. `status=running`
2. route/provider metadata
3. one conversation URL artifact

But the client still could not answer:

1. Is the model drafting, revising, or stuck?
2. Is this still normal latency or an abnormal delay?
3. Is there any partial artifact ready to consume?

### Why this matters

For coding-agent workflows, a binary `running` state is not enough once tasks enter multi-minute report generation.

### Expected behavior

Status should expose a more useful phase model, for example:

1. `accepted`
2. `provider_executing`
3. `draft_received`
4. `quality_gate`
5. `artifact_writeback`
6. `completed`

### Proposed fix

P1 candidate:

1. Extend `next_action` / `lifecycle.phase` with more granular execution phases.
2. Surface partial artifact readiness if available.

## Issue E: public MCP/client schema alignment still needs stronger discipline

### What happened

The broader public-agent northbound surface now supports more advanced concepts such as contract-first fields and `execution_profile`, and docs clearly mention them.

But client-side tool surfaces can lag behind or expose stricter/older shapes than operators expect.

In this run, the concrete observed schema mismatch was the attachment list-only requirement. More broadly, this category remains a real risk whenever public capabilities evolve faster than some client wrappers.

### Why this matters

If public MCP is the single supported coding-agent entry surface, then its transport contract must feel stable and self-explanatory to clients.

### Expected behavior

The service should make schema drift harder by design.

### Proposed fix

P1 candidate:

1. Generate MCP tool schemas and example payloads from one canonical northbound contract source.
2. Ship a compatibility test that exercises common client payload shapes:
   - one attachment
   - multi-attachment
   - contract-first body
   - execution-profile body
   - long-running backgroundable report

## Recommended Service-Side Issue Breakdown

### P0

1. Public MCP attachment ergonomics fix
2. Clearer sync-to-background client handoff semantics

### P1

1. Public advisor wait primitive
2. Richer progress phases for long-running report/research turns
3. Stronger northbound schema alignment and compatibility validation

## What Should Not Be Misdiagnosed

Two things should **not** be misfiled as public MCP defects:

1. Earlier wrong-connector incidents where a Codex session was not actually bound to the authenticated public MCP instance
2. Long report generation itself taking time

The problem here is not “the public MCP failed.” The problem is:

`a real long-running, attachment-backed, report-grade client workflow exposed clear room for better ergonomics and better operator observability.`

## Recommendation

The public advisor-agent MCP surface is already good enough to be the standard coding-agent front door.

The next service-side improvements should focus less on adding more lanes and more on:

1. transport ergonomics
2. long-run operability
3. contract/tooling alignment

That is where the client experience still feels rough in real work.
