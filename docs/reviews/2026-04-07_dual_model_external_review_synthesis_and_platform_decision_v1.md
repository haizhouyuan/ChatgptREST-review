# Dual-Model External Review Synthesis And Platform Decision V1

Date: 2026-04-07

## Decision summary

After combining:

- the completed `A-F` rollout
- the `ChatGPT Pro` external architecture review
- the failed-but-informative `Gemini Deep Think` runtime review attempts
- the current code and runtime state

my decision is:

> The next stage should be a **boundary-consolidation release**, not another substrate-expansion release.

The single highest-leverage move is:

> Freeze a narrow, explicit, default `coding-agent-v1` northbound contract and make every other change support that contract.

Everything else in the next stage should be subordinate to that.

## Findings first

### 1. The platform is no longer missing core substrate; it is missing a finished product boundary

This is the central conclusion.

After `A-F`, the platform already has:

- completion-contract-aware public agent behavior
- `project_id` threading in core substrate paths
- authority semantics clarified
- promotion maintenance instrumentation

The remaining problem is not “build more underlying machinery.”

The remaining problem is:

> the product surface still does not cleanly match the intended user mental model

This was the strongest correct point from the `ChatGPT Pro` review, and it matches the internal reflection.

### 2. The coding-agent default story is still thicker than it should be

Even after `A-F`, the default public surface still feels advisor-shaped.

That is too heavy for mature coding agents.

For `Codex / Claude Code / Antigravity`, the correct default story should be:

- submit
- wait
- answer
- cancel
- optionally fetch conversation/export/artifacts

Not:

- broad advisor semantics
- implicit workspace/control-plane literacy
- “figure out which fields matter this time”

So the next stage should not start from “improve everything.”

It should start from:

> make the default coding-agent lane feel obviously correct

### 3. The most dangerous future drift remains authority vs dynamic retrieval

This is the highest architectural drift risk.

If the system keeps improving dynamic project-scoped memory/knowledge retrieval without structurally protecting the authority anchor, it will silently drift:

- frozen facts will become suggestions
- style rules will become soft prompts
- global/project memory will quietly outrank human truth

This risk is larger than it looks, because it produces plausible outputs instead of obvious failures.

So the next stage must not merely “document authority priority.”

It must make authority precedence:

- structural
- inspectable
- token-budget protected
- replay-testable

### 4. OpenClaw still needs one more role-boundary correction

The backend is now much better able to accept project-scoped work.

But the `OpenClaw` entry layer still has not fully arrived at its intended role.

Its intended role is:

- associate project
- determine `continue / branch / status / clarify`
- hand off into the backend
- shape the user-facing answer

Its non-role is:

- becoming the project brain
- accumulating hidden business logic
- solving the whole project locally

So the next stage must explicitly freeze OpenClaw’s entry contract, not just improve downstream plumbing.

### 5. Promotion work should stay in the stage, but only as safe operations and release evidence

The external review reinforced something the internal reflection already suggested:

promotion is not the right centerpiece for the next stage.

The next stage should keep:

- inventory
- maintenance harness
- release evidence
- replay safety

But it should not center on:

- generic promotion throughput optimization
- broad self-improvement ambitions
- new automation strategy

Those are later-stage concerns.

## What Gemini changed in the decision

Gemini did not produce a usable architecture review.

But the Gemini execution loop still changed my judgment in an important way.

It proved that:

1. the platform can still lose user-facing reliability because of live web-provider conditions
2. the system still needs to make provider failure states crisp and recoverable
3. “clean product boundary” is not just an architecture preference, it is also an operational necessity

This strengthens the case for a narrow coding-agent contract:

- fewer ambiguous states
- fewer mixed semantics
- clearer release gates
- easier diagnosis when providers drift

So Gemini did not give a second architectural opinion, but it did reinforce the same strategic direction by runtime evidence.

## What I will not do next stage

The next stage should **not** try to do all of the following at once:

- freeze coding-agent contract
- fully productize OpenClaw entry behavior
- harden authority governance
- recover broad promotion throughput
- build generalized self-improving automation

That would repeat the same “broad but blurry” pattern the platform has just spent time correcting.

## Platform decision

The next stage will be executed as one full consolidation program with four integrated deliverables:

1. **coding-agent-v1 default contract**
2. **OpenClaw entry-policy contract**
3. **structural authority governance**
4. **one release-blocking gate pack**

These four together define the desired product shape.

Everything else is either:

- prerequisite support work
- implementation detail
- or explicit out-of-scope follow-on work

## Success definition for the next stage

The next stage will count as successful only if all of the following become true.

### Coding-agent success

- a mature coding agent can complete a long web-backed task through the default lane without needing advisor literacy
- there is no `completed + unclear next step` ambiguity in the default lane
- the default docs/examples teach only the intended path

### OpenClaw success

- project requests do not fall into local ad hoc behavior
- `continue / branch / status / clarify` are explicit and replayable
- project association carries provenance

### Authority success

- authority anchor wins over every lower layer at runtime
- this precedence is visible in context composition
- stale/conflicting authority can be inspected before a release

### Harness success

- one gate pack can fail the release if any of the above invariants regress

## Bottom line

The next stage should be judged by one question:

> After all the work, does the platform finally present the right shape to its two real consumers: mature coding agents and OpenClaw?

If the answer is still “mostly, but with caveats,” then the stage is not complete.
