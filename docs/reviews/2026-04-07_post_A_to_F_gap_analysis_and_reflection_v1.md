# Post A-F Gap Analysis And Reflection V1

Date: 2026-04-07

## 1. Purpose

This document answers one question:

> After the completed `A-F` rollout, what has the system actually become, how far is that from the intended end-state, and what should be learned before the next stage?

This is not a changelog. It is a judgment document.

## 2. The intended end-state

The desired system shape, as clarified through the review cycle, is:

1. `ChatgptREST` should be **web-first** for mature coding agents.
2. `OpenClaw` should be the **entry-layer project associator and orchestrator**, not the long-term project brain.
3. `OpenMind plugins` should be a **thin bridge**, not a competing intelligence layer.
4. Project truth should be governed by:
   - a human authority anchor
   - project-scoped memory
   - project-scoped knowledge
   - runtime context assembly
5. EvoMap/promotion should be:
   - observable
   - operable
   - safe
   - eventually improvable by harness feedback

In short:

> The target is a layered platform with clear product boundaries, not a growing generic advisor monolith.

## 3. What the A-F rollout actually achieved

### 3.1 Public agent MCP became materially more usable

The largest practical break before the rollout was:

- long-running deep research tasks could complete in lower layers
- but the public agent surface could still leave coding agents with `completed + empty answer`

The `A` line fixed that class of problem.

Practical result:

- `Codex / Claude Code / Antigravity` now have a real completion-contract-aware public surface
- finality semantics became visible at the public layer
- wrappers stopped assuming `last_answer` is the only authoritative answer source

This is a real product-level improvement, not just a refactor.

### 3.2 Project scope became a runtime property instead of a concept

Before `B/C/D/E`, project scoping existed in pockets of the stack but not in the main hot path.

After the rollout:

- EvoMap schema/runtime now carry `scope_project`
- memory/context/retrieval hot path now carries `project_id`
- OpenMind plugins can now propagate `project_id`
- project-specific recall/capture/telemetry now has a real field to hang on

This means the system moved from:

- "project-aware by convention"

to:

- "project-aware by runtime contract"

That is a foundational change.

### 3.3 Authority semantics became explicit

The rollout also clarified a previously unstable area:

- automatic retrieval
- project memory
- EvoMap knowledge
- manual project truth

These were previously easy to discuss but easy to mix up.

The rollout made one critical rule explicit:

> human authority anchor must outrank automatic retrieval

This is one of the highest-value outcomes of the entire cycle, because without this rule every later "smart" layer would drift.

### 3.4 Promotion moved from "diagnosed problem" to "maintainable subsystem"

Before `F`, promotion analysis mainly lived in reviews, audits, and one-off SQL checks.

After `F`:

- there is now a promotion inventory surface
- there is now a planning review maintenance harness
- there is now a refresh-only timer template
- there are now pre/post evidence artifacts

This does **not** mean promotion is solved.

It means:

> promotion is now observable and operable in a repeatable way

That is a large step forward.

## 4. The gap versus the intended end-state

The rollout closed important technical gaps, but it did not fully achieve the intended product shape.

### 4.1 The coding-agent surface is improved, but not yet truly web-first

This is the biggest remaining gap.

What exists now:

- the existing public agent MCP is more correct and much more usable

What was actually intended:

- mature coding agents should primarily see a web/result-first surface
- they should not need to mentally absorb general advisor semantics unless explicitly needed

Current reality:

- the public surface is fixed
- but the product boundary is not yet simplified to match the desired user mental model

So the system is now **correcter**, but not yet **cleaner**.

### 4.2 OpenClaw still has not fully arrived at the intended role

The intended OpenClaw role is:

- project association
- continue/branch/status recognition
- clarification when needed
- tool routing

and explicitly **not**:

- long-term project brain
- full business reasoning layer

The rollout improved the backend path OpenClaw can hand work into, but did not finish the OpenClaw-side behavioral boundary.

That means:

- backend/project plumbing is stronger
- entry behavior is still not fully productized

### 4.3 The authority anchor now has the right position, but not yet a mature governance model

The rollout settled the semantic question:

- authority anchor is not a throwaway cache
- it is a durable human-governed truth layer

But governance is still immature.

What still needs definition:

- who updates it
- when it must be refreshed
- how stale state is detected
- which statements qualify as frozen facts
- how writing rules evolve without accidental drift

So the system now has the right object, but not yet the full operating discipline around it.

### 4.4 Promotion remains constrained by activation, not by visibility

This is another major gap.

The rollout fixed:

- visibility
- maintenance packaging
- safe refresh entrypoints

It did **not** fix:

- low active coverage
- generic activation throughput
- promotion automation strategy
- harness-driven feedback loops into promotion behavior

So the real state now is:

> promotion has become governable, but not yet high-throughput

### 4.5 Historical boundary drift in ChatgptREST remains only partially addressed

The broad insight that emerged through the review cycle is:

> ChatgptREST originally aimed to strengthen web automation, but gradually accumulated too many overlapping roles.

The A-F rollout reduced critical friction, but it did not finish the larger product-boundary realignment.

That means historical complexity still exists in:

- broad MCP vs public agent MCP
- advisor semantics vs coding-agent needs
- product surfaces vs internal substrate

This is no longer a debugging problem. It is now a product and architecture consolidation problem.

## 5. What we got wrong before this rollout

### 5.1 We overestimated the need for new infrastructure

A key lesson is that the repo was not missing fundamental substrate nearly as badly as it first appeared.

The real missing piece was often:

- not "build a new system"
- but "thread the existing substrate through the hot path correctly"

This matters because it changes how future work should be approached.

The default strategy should now be:

1. inspect existing substrate
2. check whether the field/contract already exists somewhere
3. repair hot-path integration before designing a parallel system

### 5.2 We initially underweighted boundary clarity

Many earlier discussions focused on:

- fields
- files
- retrieval logic
- context packing

But the highest-value insights came from the boundary questions:

- what is ChatgptREST actually for
- what should OpenClaw own
- what should plugins never own
- what should coding agents never need to understand

This means the next stage should be organized more around **product surfaces and role boundaries** than around isolated technical subproblems.

### 5.3 We almost treated project context as a local planning problem

That would have been a mistake.

The deeper realization was:

> project context is not a special-case planning hack; it is a platform scoping problem

That shift was correct and should be preserved.

## 6. The honest current state

The system is now best described as:

> a significantly more coherent platform foundation that still needs one more stage of product-boundary and operations consolidation

It is no longer in the "unclear prototype" state.

It is also not yet in the "cleanly shaped product platform" state.

It has moved into:

> credible platform foundation with unfinished surface consolidation

## 7. What should be learned before the next stage

### 7.1 The next stage should not be another scattered patch cycle

The next stage should be a **single boundary-and-operations consolidation stage**.

Its purpose should be:

- to finish the product shape
- to make the user-facing surfaces match the clarified intent
- to turn authority/promotion from semantics into operating discipline

### 7.2 Success now depends more on simplification than on adding more capability

The next gains will not come primarily from:

- more data structures
- more modes
- more clever injection logic

They will come from:

- fewer ambiguous surfaces
- stronger default paths
- explicit ownership of each layer
- stable operational governance

### 7.3 Harness should now be treated as a first-class discipline, not a side utility

This rollout worked well partly because:

- each batch was committed
- walkthroughs were written
- review packets existed
- live evidence was captured

That should not remain an implementation habit only.

It should become a formal part of platform evolution.

## 8. Bottom-line judgment

If the intended end-state is scored as `100`, this rollout did not deliver `100`.

But it did move the system from something like:

- `~45`: promising but structurally inconsistent

to something closer to:

- `~70`: coherent enough to build the final shape on

That is a substantial gain.

The missing `30` is not mostly more engineering plumbing.

It is:

- product boundary cleanup
- entry-layer behavior cleanup
- authority governance
- promotion operations maturity

That should define the next stage.
