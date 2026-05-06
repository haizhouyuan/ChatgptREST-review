# 2026-04-07 Dual-Model Next-Stage External Review Packet v1

## Review Goal

Use one `ChatGPT Pro` review and one `Gemini DeepThink` review to answer a single question:

> After the completed `A-F` rollout, what is the best next-stage implementation path to reach the intended final platform shape?

This packet is intentionally for **platform architecture review**, not business-planning review.

## Ground Truth

Treat these as the current ground truth:

1. The `A-F` rollout is complete.
2. `public agent MCP` now projects `completion_contract` and supports a canonical `answer` retrieval path.
3. `project_id` and `scope_project` groundwork now exist through the hot path.
4. `authority anchor > project memory > project knowledge > runtime heuristics` is the intended priority contract.
5. `OpenClaw` should be an entry-layer orchestrator, not the project brain.
6. `OpenMind plugins` should be thin bridges.
7. `ChatgptREST` has grown powerful but still feels broader and thicker than the ideal product boundary.

## What Is Already Achieved

### Coding-agent baseline

- `Codex / Claude Code / Antigravity` no longer get stuck on `completed + empty answer` in the deep-research path.
- `advisor_agent_answer` now provides a formal final-answer retrieval primitive.
- wrapper agent mode follows `answer_state` and canonical answer fetch instead of assuming `last_answer` is the only truth.

### Project-scoped substrate baseline

- `scope_project` groundwork exists in the knowledge layer.
- `project_id` is threaded into the substrate hot path.
- `authority anchor` is now a defined layer instead of an accidental document blob.

### Promotion/maintenance baseline

- promotion inventory exists
- reviewed maintenance harness exists
- the system is now observable enough to inspect promotion health instead of guessing

## Desired Final Shape

The intended final platform shape is:

### 1. Coding-agent surface

For `Codex / Claude Code / Antigravity`, the default surface should feel like:

- submit a web-backed task
- wait
- fetch final answer
- fetch conversation/export/artifact when needed
- cancel when needed

Coding agents should **not** need to understand internal advisor/control-plane internals in routine use.

### 2. OpenClaw entry layer

`OpenClaw` should reliably handle:

- project association
- continue / branch / status determination
- clarification only when needed
- handoff into `OpenMind plugin -> ChatgptREST`

It should **not** try to be the long-term project brain.

### 3. Project truth model

Project truth should remain layered:

1. authority anchor
2. project memory
3. project knowledge
4. runtime context

And the priority contract should stay explicit and durable.

### 4. Promotion / maintenance

Promotion should become:

- observable
- safe
- repeatable
- harness-backed

Not a blind auto-promotion story.

## Current Gap

The current repo is materially better than before, but still has these open gaps:

1. The coding-agent northbound surface is more usable, but not yet as lightweight and web/result-first as desired.
2. `OpenClaw` entry behavior is improved indirectly, but the entry layer is not yet fully completed as a reliable project associator/orchestrator.
3. `authority anchor` exists semantically, but governance rules are not yet fully institutionalized.
4. promotion has maintenance visibility, but not yet a fully restored high-confidence digestion loop.
5. the product boundary between:
   - coding-agent surface
   - OpenClaw plugin/backend surface
   - internal cognition substrate
   is clearer than before, but still not completely “finished”

## Code Scope To Review

The public review repo for this review should contain a curated subset of the main ChatgptREST trunk, not the full private source tree.

The selected public review branch should focus on:

- `chatgptrest/`
- `chatgpt_web_mcp/`
- `openclaw_extensions/`
- `ops/`
- `skills-src/`
- `docs/`
- `.agents/`

Root files:

- `README.md`
- `pyproject.toml`

Deliberately excluded from the public review branch:

- runtime state
- artifacts
- secrets
- env files
- caches
- local-only dirty files unrelated to the mainline plan
- unrelated business-planning source materials

## Additional Attached Context

Besides the curated public review branch, the review should also use attached markdown packets that summarize:

1. post `A-F` reflection
2. next-stage full platform realignment plan
3. sanitized cross-repo context for:
   - `OpenClaw main workspace`
   - project authority-anchor pattern
   - review/upload/privacy constraints

These attachments exist to avoid forcing the model to infer platform intent from code alone.

## Questions For Review

Please answer these questions directly and concretely.

### Q1. Highest-leverage next move

If the goal is to reach the intended final shape with the fewest wrong turns, what is the single highest-leverage next-stage implementation move?

### Q2. Full-plan realism

Is the current “full platform realignment” plan still too broad, or is it the right level of ambition now that `A-F` is complete?

If it is too broad, identify the smallest **full** plan that still reaches the desired shape rather than falling back into patchwork.

### Q3. Boundary mistakes still remaining

Which architectural boundary is still most at risk of drifting again?

Examples:

- coding-agent surface vs advisor/control-plane surface
- OpenClaw entry vs project brain
- authority anchor vs dynamic recall
- promotion maintenance vs automatic evolution claims

### Q4. Acceptance design

What should the acceptance gates be for the next stage so that “it feels better” is not the only measure?

Be explicit about:

- user-visible acceptance
- runtime/contract acceptance
- governance acceptance
- harness/eval acceptance

## Response Format

Return:

1. findings first, ordered by severity/importance
2. architecture verdict
3. recommended next-stage implementation path
4. acceptance gates
5. explicit disagreement with the current plan, if any

## Important Constraints

1. Do not propose reverting back to a purely ad hoc manual workflow.
2. Do not assume hidden private business documents are available.
3. Do not recommend shifting `Gemini DeepThink` to CLI/API-key substitutes.
4. Do not assume the long-term answer is “make every layer smarter”; boundary quality matters more than adding more reasoning.
