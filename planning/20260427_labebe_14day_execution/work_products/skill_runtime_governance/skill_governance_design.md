# Skill Governance Design

Created: 2026-04-27

## Purpose

Turn skill usage from ad hoc "agent remembers a trick" behavior into a closed loop:

```text
Use skill -> record what happened -> review failures -> patch or retire skill -> validate with a fresh agent.
```

This is planning and governance for the Labebe/Paperclip masterplan. It does not authorize bulk skill installation, direct MCP mutation, or runtime config edits.

## Two-Layer Model

### Layer 1: Skill Use Log

Every agent that uses a non-trivial skill should leave a small usage note when the result matters to a deliverable.

Recommended local file pattern:

```text
work_products/<lane>/skill_use_log.jsonl
```

Record shape:

```json
{
  "ts": "2026-04-27T00:00:00+08:00",
  "agent": "codex-main-or-worker-name",
  "skill": "minimax-multimodal-toolkit",
  "skill_path": "/absolute/path/to/SKILL.md",
  "task": "generate or plan Labebe walkthrough video",
  "input_artifacts": ["..."],
  "output_artifacts": ["..."],
  "result": "success|partial|blocked|failed",
  "failure_mode": null,
  "next_skill_change": "none|doc_patch|script_patch|retire_candidate"
}
```

### Layer 2: Skill Steward Review

A separate steward reviews usage logs and evidence. The steward should not blindly trust the same agent that created the skill update.

Review cadence:

- after each major deliverable;
- after any repeated failure;
- before a skill is promoted to all Codex/Claude/Kimi/OpenClaw environments;
- before retirement of any live skill.

Review output:

```text
skill_review_report.md
skill_patch_plan.md
fresh_agent_validation_prompt.md
```

## Validation Rule

A skill is not considered "good" because the creator can use it. It must be tested by at least one fresh agent with limited context.

Fresh-agent validation must include:

- minimal task prompt;
- no hidden intended answer;
- exact skill path;
- expected artifacts;
- pass/fail criteria;
- known failure modes the evaluator should discover naturally when possible.

## Skill Change Classes

| Class | Examples | Required Gate |
|---|---|---|
| Documentation patch | clarify host, output directory, quota, forbidden claims | reviewer read + one fresh-agent smoke |
| Script patch | MiniMax wrapper, browser capture utility, media conversion | command smoke + rollback note |
| New skill | Browser Harness, Labebe product crawl, claim gate | skill-creator structure + fresh-agent validation |
| Retire skill | stale Pro prompt builder, obsolete one-off story skill | usage audit + archive path + replacement note |
| Global install | all Codex/Claude/Kimi/OpenClaw environments | maint-side approval, config diff, smoke in each live home |

## What To Record For Drawing / Media Skills

For image/video/audio skills, record:

- prompt;
- source image/video paths;
- model/provider;
- duration/resolution/ratio;
- output path;
- generation cost/quota note if available;
- visible defects;
- whether output is internal only or publishable;
- whether product/child/safety claims require review;
- whether the skill led to repeated artifacts such as wrong aspect ratio, watermark, identity drift, or unrealistic child imagery.

## Labebe-Specific Rules

- Consumer DTC site must not display internal skill usage, claim gate, AI generation, or Paperclip artifacts.
- Boss Gallery may show AI output only as prototype exploration with visible claim status.
- Child-product visuals require stricter review: no unsafe usage, no implied certification, no invented developmental proof.
- MiniMax video and audio should be planned as scarce resources, not fired casually.
- Image generation can be used for internal concept boards, but final DTC product pages should prioritize source-backed Labebe product media.

## Retirement Criteria

Retire or archive a skill when:

- it points at dead endpoints or stale model names;
- it duplicates a stronger maintained skill;
- it requires hidden context to work;
- it encourages unsafe claims or hidden writes;
- it repeatedly produces wrong artifacts after two documented fixes;
- it exists only for a past one-off project with no current user value.

Keep a skill when:

- it wraps a hard-to-remember workflow;
- it prevents repeated operational mistakes;
- it includes deterministic scripts or validation;
- a fresh agent can use it with low context.

## Immediate Application To This Sprint

| Skill Area | Decision |
|---|---|
| MiniMax multimodal | Already present in shared skills. Use for future video/audio generation after quota and deliverable plan. |
| Browser Harness | Add small deterministic scripts and templates locally; do not create a large new platform. |
| GStack QA/design review | Extract method/checklists only. Do not install or run as a live skill stack. |
| AgencyAgents | Treat as role-writing reference only if later needed. Do not bulk import personas. |
| Paperclip skills | Respect Paperclip's existing skill tightening concerns. Verify loaded path before relying on a skill update. |
| Multica skills/backlog | Read-only pattern library. Do not migrate or revive as active control plane. |

## Acceptance

This governance loop is acceptable when:

- each high-impact skill use has a log or evidence note;
- failed media/browser/automation usage produces a patch or retirement decision;
- at least one fresh agent can validate any new or changed reusable skill;
- global config changes are kept out of Labebe sprint unless a concrete blocker requires them.
