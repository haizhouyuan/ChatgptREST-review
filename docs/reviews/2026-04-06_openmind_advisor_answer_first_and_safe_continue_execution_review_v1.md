# 2026-04-06 OpenMind Advisor Answer-First And Safe-Continue Execution Review v1

## Scope

This batch does not widen the planning task plane.

It closes two user-facing bottlenecks identified after the previous planning
review cycle:

1. OpenClaw users were still seeing machine metadata before the actual answer
2. OpenClaw tool-calling still depended too strictly on explicit `taskId`
   forwarding for simple "continue/refine" follow-ups

The implementation stays in the OpenClaw plugin layer:

- `openclaw_extensions/openmind-advisor/index.ts`

The planning backend contract is not widened in this batch.

## Implemented

### 1. `openmind_advisor_ask` is now answer-first

Files:

- `openclaw_extensions/openmind-advisor/index.ts`
- `openclaw_extensions/openmind-advisor/README.md`

What changed:

1. successful ask results now return the answer body first
2. `Route / Session / Run / Job / Next action` are no longer rendered ahead of
   the answer in `content[0].text`
3. machine-readable metadata still remains in `details`

User effect:

- OpenClaw / Feishu users now see the planning result itself first
- plugin-level machine metadata no longer pollutes the first-screen reading
  experience

### 2. fail-close output is now rendered as human guidance

Files:

- `openclaw_extensions/openmind-advisor/index.ts`

What changed:

1. `needs_followup` is no longer surfaced as raw machine wording such as
   `same_session_repair`
2. when `quality_gate.missing_sections` exists, the plugin now converts those
   missing sections into user-facing labels where possible
3. the plugin renders:
   - current result is not yet deliverable
   - what is still missing
   - what the next step should be
   - current draft, when available

User effect:

- fail-close no longer looks like backend jargon
- users can understand what is missing without reading internal JSON fields

### 3. Safe implicit continuation for obvious follow-up asks

Files:

- `openclaw_extensions/openmind-advisor/index.ts`
- `openclaw_extensions/openmind-advisor/README.md`

What changed:

1. if the caller did not pass `taskId`
2. and the question clearly looks like a follow-up (`继续/补充/完善/改写/...`)
3. and runtime-scoped task lookup finds exactly one visible task
4. then the plugin will automatically attach:
   - `taskId`
   - `taskAction=continue`
5. if more than one candidate task exists, the plugin does not guess

User effect:

- OpenClaw now has a safer fallback path for simple continuation asks
- continuation no longer relies only on the upstream tool-caller perfectly
  passing the prior task id every time

## Validation

Targeted tests:

- `./.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py tests/test_openmind_advisor_truth_surface.py tests/test_openclawbot_planning_task_plane_live_completion_gate.py`

What these tests currently prove:

1. the plugin source exposes the new answer-first and safe-continue helpers
2. the README documents the new response shaping and implicit continuation
   behavior
3. existing live completion gate expectations for `openmind_advisor_ask`
   remain green

## Boundary

This batch improves the OpenClaw-facing ingress and egress experience.

It does **not** prove:

1. that OpenClawBot's high-level tool-selection prompt is fully mature
2. that all follow-up asks can be auto-resolved without ambiguity
3. that real planning output quality is now fully solved

The current honest claim is narrower:

> the OpenClaw plugin no longer forces users to read backend metadata first,
> and it now has a safe continuation fallback when the runtime scope contains a
> single obvious planning task.

## Result

- accepted
