# Next-Stage TODO And Memory Guard V1

Date: 2026-04-07

## Purpose

This document is the compression-safe execution anchor for the next stage.

If context is lost, the next executor should be able to resume from here without re-deriving the whole strategy.

## Current decision

The next stage is a **boundary-consolidation release** centered on four deliverables:

1. `coding-agent-v1` default contract
2. `OpenClaw` entry-policy contract
3. structural authority governance
4. one release-blocking gate pack

Everything else is secondary.

## External review reality to preserve

### ChatGPT Pro

Substantive architecture review succeeded.

Key source:

- [ChatGPT Pro answer artifact](/vol1/1000/projects/ChatgptREST/artifacts/jobs/523894d79c244c87880437a3b4118691/answer.md)

### Gemini

No usable second architecture opinion was obtained.

What must be remembered:

1. the first Gemini pass exposed a real provider bug and that bug was fixed
2. later Gemini runs remained operationally sensitive
3. a controlled `💻 Codex -> 🇯🇵 日本 03 -> restart chrome -> retry -> restore AUTO` loop was executed
4. the final run still did not yield a usable review answer

Key sources:

- [Gemini retry3 summary](/vol1/1000/projects/ChatgptREST/artifacts/reviews/external/20260407_dual_model_next_stage/gemini_deep_think_retry3_summary.json)
- [Gemini repair.check answer](/vol1/1000/projects/ChatgptREST/artifacts/jobs/43f8af18ff99440fa19dfba47cb8a5b9/answer.md)

## Program TODO

### TODO 1: Freeze `coding-agent-v1`

Definition of done:

- narrow default contract exists
- default wrappers/docs/examples use it
- broad advisor semantics are not the default coding-agent story
- finality and answer retrieval are deterministic

### TODO 2: Freeze OpenClaw entry policy

Definition of done:

- `project_id`, `association_source`, and `task_mode` are explicit
- replay fixtures cover deterministic and ambiguous cases
- OpenClaw does not silently regrow project-brain behavior

### TODO 3: Make authority structural

Definition of done:

- authority anchor has schema and governance
- authority is first-class in runtime assembly
- authority cannot be silently outranked
- stale/conflict tooling exists

### TODO 4: Build one gate pack

Definition of done:

- one manifest/runner covers:
  - coding-agent lane
  - OpenClaw entry behavior
  - authority precedence
  - promotion-maintenance safety
- release fails if any invariant regresses

## Non-goals to preserve

Do **not** let the next stage drift into:

- broad promotion throughput work
- generic self-improving automation
- reopening advisor as the default coding-agent product
- another standalone project-context subsystem

## Files that anchor the next decision

- [post A-F reflection](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_post_A_to_F_gap_analysis_and_reflection_v1.md)
- [earlier next-stage plan](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_next_stage_full_platform_realignment_plan_v1.md)
- [dual-model execution findings](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-07_dual_model_external_review_execution_and_findings_v1.md)
- [dual-model synthesis and platform decision](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_dual_model_external_review_synthesis_and_platform_decision_v1.md)
- [refined next-stage full execution plan](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_refined_next_stage_full_execution_plan_v1.md)

## If execution resumes later

Before touching code again:

1. re-read the five files above
2. confirm current public MCP and OpenClaw runtime behavior
3. do **not** assume Gemini review content exists
4. treat ChatGPT Pro review as the substantive external opinion
5. treat Gemini evidence as runtime-operational input, not architecture endorsement

## Final memory guard

The next stage is not about “making everything better.”

It is about making the platform finally **feel right at its two real product edges**:

- mature coding agents
- OpenClaw
