# AsterREST Broker/Harness Pro Review Request v1

Date: 2026-05-01

## Role

You are acting as a senior architecture reviewer for a browser-automation-based external model access service.

Please give a critical, implementation-oriented review. The goal is not to validate our preferred answer. The goal is to expose wrong assumptions, missing production constraints, and the safest sequencing for a small team / single-operator environment.

## Naming Boundary

This packet is intentionally anonymized.

- `AsterREST` = the current service under review.
- `ModelWeb-A` = a premium web UI model provider used for long reasoning/review tasks.
- `ModelWeb-B` = another web UI model provider used for research/review tasks.
- `TaskFabric` = a local multi-agent orchestration environment where a dedicated broker agent could run.
- `ExternalModelBrokerAgent` = a proposed dedicated agent that submits, monitors, retrieves, and quality-checks external model answers.

Please keep the same anonymized names in your answer.

## Core Question

Should AsterREST evolve from a REST/job queue with deterministic browser scripts into:

```text
External Model Broker
+ Browser Harness
+ Adaptive Recovery
+ TaskFabric-facing ExternalModelBrokerAgent
```

or should it instead move more aggressively toward a free-form browser agent driven by tools like semantic browser automation, visual reasoning, or general browser agents?

## Current Working Position

Our current independent judgment is:

1. Do not throw away the existing AsterREST job kernel.
2. Keep deterministic Playwright/CDP-style automation as the normal path.
3. Add a production Browser Harness: action ledger, replay bundle, structured browser observations, failure classification, and operator handoff.
4. Add Adaptive Recovery only for exception paths:
   - selector failure -> accessibility tree / semantic locator
   - modal/login/challenge page -> classify and pause
   - answer visible but not persisted -> DOM/export/visual reconcile
   - frontend rate limit -> fail closed and do not let an agent click through
5. Add a TaskFabric-facing `ExternalModelBrokerAgent` with a narrow interface:
   - `ask_external_model`
   - `fetch_conversation_url`
   - `status`
   - `result`
6. Do not expose a new public MCP port by default; add broker-level tools to the existing public automation surface.
7. Do not let arbitrary external agents directly attach to AsterREST driver CDP ports; use isolated browser profiles or a controlled harness.
8. Treat semantic browser automation, visual QA, and general browser agents as pluggable adapters to evaluate, not as the default execution engine.

## What We Need From You

Please answer with these sections:

1. Executive Verdict
   - Is the proposed direction right, partially right, or wrong?
   - What should be changed before implementation?

2. Architecture Critique
   - Evaluate the split between Job Kernel, Browser Harness, Adaptive Recovery, and ExternalModelBrokerAgent.
   - Identify where responsibilities are too broad, too narrow, or incorrectly layered.

3. Alternative Architecture
   - If you would choose a different architecture, describe it concretely.
   - Include the northbound API, internal state model, and browser execution model.

4. Tooling Opinion
   - Compare deterministic Playwright/CDP, accessibility snapshots, semantic locator tools, visual QA, and general browser agents.
   - Do not assume any one tool is best. Give decision criteria and a test matrix.

5. Production Failure Modes
   - List likely failure modes: UI drift, session collision, rate limits, stale exports, partial answers, progress stubs, login expiry, browser crash, memory pressure, duplicated jobs, and operator Web session interference.
   - For each, state where it should be detected and how it should recover or fail closed.

6. Observability Requirements
   - Define the minimum action ledger and replay bundle needed to make failures diagnosable.
   - Include what should be captured before/after each browser action.
   - Include privacy/safety concerns.

7. Token and Cost Control
   - Give realistic token/cost-saving strategies.
   - Identify where LLM/VLM calls are justified and where they are dangerous or wasteful.

8. TaskFabric Integration
   - Should `ExternalModelBrokerAgent` be a dedicated TaskFabric role?
   - What should its role card, tool boundaries, and stop conditions be?
   - Which other agents should be forbidden from touching browser automation directly?

9. P0-P4 Implementation Plan
   - Give a staged plan.
   - Separate safe P0 changes from risky or speculative P3/P4 changes.
   - Include acceptance criteria and rollback rules.

10. Hard No-Go Conditions
   - What would make this design unsafe to deploy?

11. Final Recommendation
   - Give the next three concrete engineering tasks we should do first.

## Review Standard

Be critical. Avoid generic advice. If a claim depends on missing evidence, say so. If current external tooling has changed recently and you use current facts, state that explicitly.

