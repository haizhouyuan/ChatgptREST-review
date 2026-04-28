# Paperclip Multi-Org Goal Clarification

Date: 2026-04-27

## 0. Why This Exists

The user's latest request is broader than Labebe website work. It introduces a lower-level governance program covering:

- skill usage telemetry and lifecycle;
- MCP vs skill vs CLI architecture;
- browser automation / computer-use harness;
- visual and video QA;
- local model / API capability usage;
- machine topology and isolation;
- Multica historical backlog migration;
- Paperclip multi-org control plane.

This document freezes the target before implementation so the work does not drift.

## 1. Top-Level Objective

Build a Paperclip-managed multi-organization operating system for AI work.

It should support two kinds of output:

1. **Business deliverables**, starting with Labebe:
   - product intelligence;
   - pure DTC website prototype;
   - AI Wow / Boss Gallery;
   - executive presentation assets.

2. **Reusable AI runtime governance**, including:
   - skill lifecycle management;
   - MCP / CLI / skill decision policy;
   - browser automation harness;
   - visual/video QA capability;
   - machine placement and security isolation;
   - backlog migration from Multica.

Paperclip should become the control plane for this whole program:

```text
Paperclip = orgs + agents + issues + evidence + approvals + status + claim/risk gates
Execution = Codex / Claude Code / Kimi Code / MiniMax / scripts / browser harness / local models
```

## 2. Non-Goals

Do not turn this into:

- a generic essay about AI agents;
- a one-off Labebe-only plan;
- a Paperclip technology demo;
- a Multica resurrection;
- a giant unprioritized backlog;
- a full autonomous write system without safety gates;
- a claim that current skills/MCP/browser harness are already production-grade.

## 3. Core Boundary

There are now three related but separate domains:

### Domain A: Labebe Business Program

Purpose:

- deliver the Labebe DTC prototype and AI Wow/Boss Gallery.

Key outputs:

- product intelligence;
- public media asset library;
- pure DTC prototype;
- AI Wow Boss Gallery;
- presentation video.

### Domain B: AI Runtime Governance

Purpose:

- make future AI work more reliable, reusable and observable.

Key outputs:

- skill usage ledger;
- skill maintainer workflow;
- MCP/CLI/skill decision matrix;
- browser/computer-use harness research;
- visual/video QA harness;
- machine topology proposal;
- validation using fresh agents.

### Domain C: Legacy Multica Migration

Purpose:

- mine useful unfinished ideas/issues from Multica, but do not keep using Multica as the control plane.

Key outputs:

- Multica backlog inventory;
- migrated issue map;
- deprecated issue list;
- Paperclip org/project equivalents;
- no-write / read-only lessons preserved.

## 4. Proposed Paperclip Orgs

### Org 1: Labebe Growth Studio

Scope:

- Labebe product intelligence, DTC prototype, media assets, website design and AI Wow demo.

Projects:

- `labebe-product-intelligence`
- `labebe-dtc-prototype`
- `labebe-public-media-library`
- `labebe-ai-wow-boss-gallery`
- `labebe-executive-presentation`

Why separate:

- This is the user-facing business deliverable lane.

### Org 2: AI Runtime Governance

Scope:

- skill lifecycle, MCP/CLI/tooling architecture, browser harness, visual QA, machine topology, runtime validation.

Projects:

- `skill-governance-loop`
- `mcp-cli-skill-architecture`
- `browser-computer-use-harness`
- `vision-video-qa-harness`
- `runtime-topology-and-isolation`
- `fresh-agent-validation`

Why separate:

- This is platform work. It should not block every Labebe deliverable, but it should provide reusable guardrails.

### Org 3: Skill Foundry

Scope:

- create/update/retire skills and record skill usage failures.

Projects:

- `skill-usage-telemetry`
- `skill-curation-agent`
- `skill-best-practice-research`
- `skill-retirement-and-history`
- `minimax-media-skill-hardening`
- `labebe-amazon-product-intel-skill`

Why separate:

- Skill work needs its own governance because it affects all agents and all future projects.

### Org 4: Browser and Vision Lab

Scope:

- automation browser harness and human-view QA for websites/videos.

Projects:

- `chatgptrest-browser-harness-review`
- `browser-use-opencli-anything-cli-prototype`
- `local-vision-model-evaluation`
- `website-ux-visual-review-harness`
- `video-understanding-qa-harness`

Why separate:

- Browser/computer-use capabilities are platform primitives, not Labebe-specific features.

### Org 5: Multica Archive and Migration

Scope:

- preserve useful Multica historical issues/backlog, migrate lessons, close/deprecate the rest.

Projects:

- `multica-backlog-inventory`
- `multica-control-plane-lessons`
- `multica-runtime-guard-migration`
- `multica-observer-reduction-lessons`
- `multica-deprecated-issue-archive`

Why separate:

- Multica is being retired as a system, but its historical work contains useful issue contracts, runtime guard, permission selftest and observer/reduction lessons.

## 5. User Ideas Mapped To Goals

### 5.1 Skill Usage Logging

User idea:

- Add a skill that lets agents record how they used skills and what errors they hit.

Goal:

- Build a low-friction skill usage ledger.

Outputs:

- `skill_usage_event_schema.md`
- `skill_usage_ledger.jsonl`
- `skill_error_taxonomy.md`
- optional helper script or skill note for agents.

Important constraint:

- Logging must not create excessive context burden or slow down normal tasks.

### 5.2 Skill Governance Agent

User idea:

- A separate agent should govern skills after usage, fixing them so the next agent does not hit the same issue.

Goal:

- Create a Skill Curator / Skill Steward role.

Responsibilities:

- review usage logs;
- cluster repeated failures;
- decide whether to update skill text, add script, add reference, or retire the skill;
- test updated skills with fresh agents;
- write maint record.

### 5.3 Best-Practice Research + Local Capabilities

User idea:

- Deeply research best practices and combine them with local APIs, keys, models and entitlements to create high-quality, efficient skills.

Goal:

- Build evidence-backed best-use skills, not guesswork.

Outputs:

- source registry for each capability area;
- local capability inventory;
- best-practice synthesis;
- tested recipe;
- skill update proposal.

### 5.4 Skill Retirement and Historical Context

User idea:

- Some skills are outdated or historically contextual; they may need retirement.

Goal:

- Manage skills as living assets.

Lifecycle states:

- active;
- experimental;
- deprecated;
- archived;
- replaced-by-CLI;
- replaced-by-MCP;
- project-specific only.

### 5.5 Conversation-History Skill Analysis

User idea:

- Analyze historical conversations to see how skills were used and what problems occurred.

Goal:

- Optional deep audit, not immediate P0.

Reason:

- It could be valuable but is large and noisy.

Proposed approach:

1. Start with forward logging from now on.
2. Audit a small historical sample.
3. Only expand if signal quality is high.

### 5.6 MCP vs Skill vs CLI

User idea:

- Some MCPs may no longer be appropriate; maybe replace with skills or CLIs such as opencli/anything-cli.

Goal:

- Create a tool architecture decision matrix.

Decision dimensions:

- startup overhead;
- context cost;
- auth/security risk;
- latency;
- determinism;
- UI/browser dependence;
- agent portability;
- compatibility with Codex/Claude/Kimi/Paperclip runtimes;
- whether it needs long-running service state.

Output:

- `mcp_cli_skill_decision_matrix.md`
- per-tool recommendation:
  - keep MCP;
  - convert to CLI;
  - wrap with skill;
  - retire;
  - runtime-specific only.

### 5.7 Different Runtime Environments

User idea:

- Codex/Claude/Kimi running under Paperclip or Multica are not the same as native Codex/CC with direct MCP config.

Goal:

- Document runtime-context differences and build config profiles.

Outputs:

- `runtime_context_matrix.md`
- `mcp_profile_policy.md`
- `agent_runtime_profiles.yaml`

Key issue:

- Native Codex/CC loads skills/MCP differently from Paperclip-run Codex/CC as a child runtime.

### 5.8 Browser Harness / Computer Use

User idea:

- ChatGPTREST is essentially browser automation. Maybe opencli/anything-cli/browser-use/local vision models can improve browser/computer-use capability, especially on Windows where Codex app-like GUI ability is absent.

Goal:

- Research and prototype a browser/computer-use harness.

Outputs:

- `browser_harness_architecture_review.md`
- `browser_use_opencli_anythingcli_comparison.md`
- `local_vision_model_browser_qa_probe.md`
- `chatgptrest_browser_harness_upgrade_plan.md`

Important:

- This should be done as platform R&D, not by destabilizing ChatGPTREST production automation.

### 5.9 Machine Topology

User idea:

- Decide which machine should host local models, browser automation, desktop automation, Paperclip, and projects: work laptop, Yoga, Home PC, M9.

Goal:

- Produce a topology and isolation plan.

Dimensions:

- desktop availability;
- GPU/local model capability;
- always-on reliability;
- network/Tailscale access;
- secrets isolation;
- browser profile risk;
- heavy media generation;
- project data storage;
- Windows vs Ubuntu desktop vs headless.

Output:

- `machine_topology_inventory.md`
- `recommended_runtime_placement.md`
- `secret_and_key_isolation_policy.md`

### 5.10 Fresh Agent Validation

User idea:

- The person/agent building a skill has context that a fresh agent does not. Skills should be tested by other agents.

Goal:

- Build validation through fresh agents.

Validation lanes:

- Codex fresh agent;
- Claude Code;
- Kimi Code if available;
- Gemini/Pro review for high-level methods;
- local deterministic tests where possible.

Output:

- `fresh_agent_skill_validation_protocol.md`
- per-skill validation evidence.

### 5.11 Vision / UX / Video QA

User idea:

- Need a way for agents to review websites and videos from a human visual/UX perspective, not just text or high-level summaries.

Goal:

- Build a vision QA harness for:
  - website screenshots;
  - responsive UX;
  - overlap/readability;
  - interaction flow;
  - video transitions;
  - scene continuity;
  - subtitle/caption issues;
  - visual awkwardness;
  - whether it feels premium or amateur.

Outputs:

- `website_visual_qa_protocol.md`
- `video_qa_protocol.md`
- `screenshot_and_contact_sheet_pipeline.md`
- `vision_model_comparison_report.md`

Important:

- Video QA must not only ask "what is the video about?"
- It must inspect frame-level problems, transitions, pacing, text legibility and visual consistency.

## 6. Multica Migration Target

Known from `2026-04-27_multica_chief_completion_summary.md`:

Multica has reached:

```text
bounded observer/proposer
+ packet-only/read-only/design-only execution
+ P3/P4 sidecar reduction candidate
- native no-write worker smoke
- write actuator
- unsupervised state mutation
```

This should be migrated as lessons, not copied as a system.

Useful items to migrate:

- workspace/project/org boundary patterns;
- issue contract templates;
- red-team / fallback review patterns;
- no-write dry-run reporter;
- permission selftest;
- runtime guard;
- observer/reduction architecture;
- proof ledger;
- sidecar knowledge register;
- ability matrix;
- external review packet discipline.

Not to migrate directly:

- Multica as daily control plane;
- issue creation as fake progress;
- unsupervised write autonomy;
- cancelled/obsolete historical smoke tasks;
- stale MCP configs without runtime profile validation.

## 7. Priority Classification

### P0: Needed Before Scaling Paperclip Team

- paperclip org/project/task tree design;
- runtime context matrix;
- MCP/skill/CLI decision matrix draft;
- skill usage event schema;
- visual QA protocol draft;
- Multica backlog inventory and migration classification.

### P1: Needed Before Broad Skill Updates

- fresh agent validation protocol;
- skill lifecycle states;
- best-practice research packets for high-value skills;
- local capability inventory;
- machine topology inventory.

### P2: Valuable But Later

- historical conversation-wide skill usage mining;
- large-scale video understanding benchmark;
- automated skill retirement dashboard;
- cross-runtime automatic MCP profile switching.

## 8. Open Questions To Avoid Ambiguity

These are the only questions that materially affect the next plan:

1. Should Paperclip become the single control plane for this governance program, or should it only manage Labebe/Paperclip demo while platform governance stays in docs/maint?

2. Should the AI Runtime Governance org be created now, or first as a design document and then implemented after Labebe Stage 1 method probe?

3. Which machines are currently available and reachable for inspection: Yoga, M9, Home PC, work laptop?

4. Where is the authoritative list of installed MCP configs across Codex, Claude Code, Kimi Code and Paperclip runtime profiles?

5. How much historical conversation mining is acceptable now: none, small sample, or full archive later?

## 9. Recommended Interpretation

My recommended interpretation is:

```text
Paperclip should manage this as multiple orgs, but implementation should be phased.
Do not block Labebe deliverables on the full platform-governance program.
Start with a design + inventory sprint for the AI Runtime Governance org.
Only install/update skills after fresh-agent validation.
Treat Multica as an archive of lessons and backlog candidates, not as an active dependency.
```

Immediate next action:

```text
Inventory Multica backlog + current skill/MCP/runtime state,
then generate Paperclip org/project/issue tree proposal for user review.
```
