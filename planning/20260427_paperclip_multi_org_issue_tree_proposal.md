# Paperclip Multi-Org Issue Tree Proposal

Date: 2026-04-27

Status update after regenerated Pro answer `qa/Labebe运营系统设计.md`:

- This document's original 5-org structure is now treated as an exploration snapshot, not the execution plan.
- The active execution plan is reduced to:
  - `Labebe Commercial Studio`;
  - `Paperclip Runtime & Evidence Kernel`;
  - `Multica Archive / Pattern Library` as read-only only.
- `Skill Foundry`, `Browser and Vision Lab`, and broad `AI Runtime Governance` are deferred until the first Labebe sprint produces visible artifacts.
- Browser Harness remains a small QA/evidence support capability inside the runtime/evidence kernel, not a separate platform org.
- The next executable issue list is the 10-issue sequence in `planning/20260427_pro_gemini_advisor_synthesis.md`.

This proposal converts the user's new ideas, the Labebe program, and useful Multica lessons into a Paperclip-managed multi-org task tree.

## 1. Org Structure

### Org 1: Labebe Growth Studio

Purpose:

- Deliver Labebe product intelligence, DTC prototype, public media library, AI Wow Gallery and executive presentation.

Projects:

1. `labebe-product-intelligence`
2. `labebe-public-media-library`
3. `labebe-dtc-prototype`
4. `labebe-ai-wow-boss-gallery`
5. `labebe-executive-presentation`

### Org 2: AI Runtime Governance

Purpose:

- Govern how Codex/Claude/Kimi/MiniMax/scripts/MCP/CLI/browser harnesses are used across projects.

Projects:

1. `runtime-context-and-permission-model`
2. `mcp-cli-skill-architecture`
3. `browser-computer-use-harness`
4. `vision-video-qa-harness`
5. `runtime-topology-and-isolation`
6. `fresh-agent-validation`

### Org 3: Skill Foundry

Purpose:

- Manage skill usage telemetry, skill lifecycle, skill best practices, retirement and updates.

Projects:

1. `skill-usage-telemetry`
2. `skill-curation-agent`
3. `skill-best-practice-research`
4. `skill-retirement-and-history`
5. `minimax-media-skill-hardening`
6. `labebe-amazon-product-intel-skill`

### Org 4: Browser and Vision Lab

Purpose:

- Build and evaluate browser automation, computer-use substitutes, local vision model QA, website UX QA and video QA.

Projects:

1. `chatgptrest-browser-harness-review`
2. `browser-use-opencli-anythingcli-prototype`
3. `local-vision-model-evaluation`
4. `website-ux-visual-review-harness`
5. `video-understanding-qa-harness`

### Org 5: Multica Archive and Migration

Purpose:

- Preserve useful Multica lessons and explicitly archive deprecated/cancelled items.

Projects:

1. `multica-backlog-inventory`
2. `multica-control-plane-lessons`
3. `multica-runtime-guard-migration`
4. `multica-observer-reduction-lessons`
5. `multica-deprecated-issue-archive`

## 2. Initial Issue Set

This is intentionally small. Do not import 117 Multica issues directly.

### Org 1: Labebe Growth Studio

#### LAB-GS-001: Tool and Method Probe

Acceptance:

- compare available ways to extract Labebe PDP, media and Amazon data;
- produce `tool_method_comparison.md`;
- identify no-key/manual/key-required paths;
- no full crawl yet.

#### LAB-GS-002: Product Master v0 and Data QA

Acceptance:

- 46 products uniquely identified;
- dirty title parse report;
- slug/image/PDP join report;
- do-not-use field list.

#### LAB-GS-003: Stratified Sample Dossiers

Acceptance:

- 6-8 SKU dossiers;
- PDP facts;
- source snippets;
- image/video roles;
- unknown fields explicit.

#### LAB-GS-004: Public Media Asset Probe

Acceptance:

- discover and download/sample public brand video/media where possible;
- source URL and capture time logged;
- usage caveats documented.

#### LAB-GS-005: DTC Design Decision Matrix

Acceptance:

- category portfolio map;
- hero candidate matrix;
- navigation decision matrix;
- PDP module strategy;
- bundle map.

#### LAB-GS-006: Pure DTC Prototype Primary + Fallback

Acceptance:

- one primary and one fallback high-fidelity prototype;
- desktop/mobile screenshot QA;
- no AI Studio/Paperclip inside consumer website.

#### LAB-GS-007: AI Wow Boss Gallery A-F

Acceptance:

- Demo A-F result cards/pages;
- Claim Gate and evidence links;
- desktop/mobile/video QA;
- unsupported claim scan.

#### LAB-GS-008: Apply Design and Browser QA Gates To DTC Prototype

Source:

- `planning/20260427_gstack_agencyagents_intake_research.md`

Acceptance:

- run GStack-inspired design review gate on primary and fallback DTC prototypes;
- produce desktop/tablet/mobile screenshots;
- produce design score and AI-slop score;
- run browser QA gate with health score;
- no boss-facing prototype proceeds with missing screenshots, mobile overflow, blank surfaces or untested core navigation.

#### LAB-GS-009: Apply CEO / Wow Gate To AI Boss Gallery

Source:

- `planning/20260427_gstack_agencyagents_intake_research.md`

Acceptance:

- run CEO / wow review before expanding Demo A-F;
- identify the first 30 seconds of the executive demo;
- list the weakest assumption and unsupported claims;
- produce evidence manifest and claim gate report before marking demo ready.

### Org 2: AI Runtime Governance

#### AIR-GOV-001: Runtime Context Matrix

Acceptance:

- compare native Codex/Claude/Kimi vs Paperclip-run child runtimes;
- skill loading and MCP loading differences documented;
- output `runtime_context_matrix.md`.

#### AIR-GOV-002: MCP/CLI/Skill Decision Matrix

Acceptance:

- define decision dimensions;
- classify current high-value MCPs/skills/CLIs;
- recommend keep/convert/wrap/retire.

#### AIR-GOV-003: No-Write Runtime Smoke Proposal

Acceptance:

- migrate Multica LC-NW lessons without reusing cancelled fixtures;
- define fresh no-write target;
- define success evidence.

#### AIR-GOV-004: Permission and Secret Isolation Policy

Acceptance:

- define profiles for local, Paperclip child runtime, browser automation, media generation;
- no secrets in issue artifacts;
- approval gates for write/high-risk actions.

#### AIR-GOV-005: Machine Topology Inventory

Acceptance:

- inspect available machines where possible;
- map Yoga, M9, Home PC, work laptop roles;
- recommend placement for local models, browser automation, Paperclip, media generation and secrets.

#### AIR-GOV-006: GStack Gate Pattern Extraction

Source:

- `planning/20260427_gstack_agencyagents_intake_research.md`

Acceptance:

- extract Paperclip-native gate templates for CEO/wow review, design review, browser QA, runtime policy and ship/checkpoint;
- do not import GStack wholesale;
- document which GStack behaviors are explicitly excluded: telemetry, routing injection, proactive behavior, auto-update and direct control-plane mutation.

#### AIR-GOV-007: Paperclip Issue Closeout Evidence Contract

Source:

- `planning/20260427_gstack_agencyagents_intake_research.md`

Acceptance:

- define `closeout.md`, `checkpoint.md` and `evidence_manifest.json` requirements;
- require every success claim to point to artifact evidence;
- cancelled/superseded work cannot be counted as success;
- next agent can resume from the checkpoint without reading the full conversation.

#### AIR-GOV-008: Runtime Policy Gate For MCP / CLI / Skill / Browser Work

Source:

- `planning/20260427_gstack_agencyagents_intake_research.md`

Acceptance:

- define review dimensions for secret access, filesystem writes, network access, browser cookies/sessions, child-runtime permissions and prompt/skill supply-chain risk;
- isolate browser and ChatGPTREST experiments from production lanes;
- require rollback plan and redaction rule for high-risk runtime changes.

### Org 3: Skill Foundry

#### SKILL-001: Skill Usage Event Schema

Acceptance:

- define minimal event schema;
- include skill name, task type, success/failure, error class, missing context, suggested fix;
- keep logging low-friction.

#### SKILL-002: Skill Curator Agent Contract

Acceptance:

- define curator responsibilities;
- update vs retire vs convert-to-CLI decision rules;
- maint writeback rule;
- fresh-agent validation requirement.

#### SKILL-003: Skill Lifecycle Registry

Acceptance:

- active / experimental / deprecated / archived / replaced-by-CLI / replaced-by-MCP states;
- initial classification method.

#### SKILL-004: Best-Practice Research Packet Template

Acceptance:

- source registry;
- local capability inventory;
- tested recipe;
- validation outputs.

#### SKILL-005: MiniMax Media Skill Hardening

Acceptance:

- inspect current MiniMax skill;
- document audio/video generation paths;
- test only safe no-secret workflows;
- add missing notes after validation.

#### SKILL-006: AgencyAgents Role-Card Pattern Extraction

Source:

- `planning/20260427_gstack_agencyagents_intake_research.md`

Acceptance:

- inspect AgencyAgents as role-card reference only;
- create Paperclip role schema with mission, inputs, outputs, success metrics, evidence, handoff, allowed tools and risk limits;
- do not bulk-install AgencyAgents;
- no unreviewed external prompt files copied into global agent paths.

### Org 4: Browser and Vision Lab

#### BV-001: ChatGPTREST Browser Harness Review

Acceptance:

- map current ChatGPTREST browser automation architecture;
- identify what should become CLI, MCP, skill or service;
- do not change production code.

#### BV-002: Browser-Use / OpenCLI / Anything-CLI Comparison

Acceptance:

- compare architecture and local feasibility;
- identify where these can improve browser/computer-use.

#### BV-003: Local Vision Model QA Probe

Acceptance:

- test current configured vision APIs/models if available;
- evaluate screenshot and video-frame QA quality.

#### BV-004: Website UX Visual QA Protocol

Acceptance:

- define screenshot set;
- define overlap/readability/layout/desktop/mobile checks;
- define human-view review prompt.

#### BV-005: Video QA Protocol

Acceptance:

- define frame extraction/contact sheet pipeline;
- check transitions, pacing, text legibility, scene continuity and visual consistency.

#### BV-006: Browser Architecture Comparison With GStack

Source:

- `planning/20260427_gstack_agencyagents_intake_research.md`

Acceptance:

- compare GStack browser daemon architecture with ChatGPTREST, browser-use, OpenCLI and Anything-CLI;
- evaluate localhost-only binding, bearer token, state-file permissions, cookie handling, ARIA snapshot interaction and screenshot evidence;
- recommend which pieces become CLI/service/skill/Paperclip gate.

### Org 5: Multica Archive and Migration

#### MULTICA-001: Preserve Live Issue Export

Acceptance:

- store exported issue JSON;
- store classification TSV;
- record counts and statuses.

#### MULTICA-002: Migrate Control Plane Lessons

Acceptance:

- summarize observer/proposer, no-write, dry-run, proof ledger, evidence bundle patterns;
- map to AI Runtime Governance projects.

#### MULTICA-003: Archive Cancelled Smoke Fixtures

Acceptance:

- list cancelled LC-NW and red-team fixtures;
- mark as not success evidence.

#### MULTICA-004: Manual Review Packet Lessons

Acceptance:

- sample 5-10 packet-review/fallback issues;
- extract useful review criteria;
- do not migrate all review issues blindly.

## 3. Cross-Org Rules

1. Paperclip issue progress requires artifact evidence, not just comments.
2. No issue may claim production readiness unless implementation and QA prove it.
3. Cancelled Multica issues must never be cited as success evidence.
4. Skill updates require fresh-agent validation before installation as stable.
5. Browser harness experiments must be isolated from production ChatGPTREST lanes.
6. Consumer DTC website must not include internal AI/Paperclip modules.
7. AI Wow Demo must label prototype exploration and block unsupported claims.

## 4. Recommended Phasing

### Phase 1: Inventory and Design

- `LAB-GS-001`
- `AIR-GOV-001`
- `AIR-GOV-002`
- `AIR-GOV-006`
- `AIR-GOV-007`
- `AIR-GOV-008`
- `SKILL-001`
- `SKILL-006`
- `MULTICA-001`
- `BV-001`
- `BV-006`

### Phase 2: Sample and Validation

- `LAB-GS-002`
- `LAB-GS-003`
- `LAB-GS-004`
- `SKILL-002`
- `BV-003`
- `BV-004`
- `BV-005`

### Phase 3: Prototype and Gallery

- `LAB-GS-005`
- `LAB-GS-006`
- `LAB-GS-007`
- `LAB-GS-008`
- `LAB-GS-009`
- `SKILL-005`

### Phase 4: Platform Governance Hardening

- `AIR-GOV-003`
- `AIR-GOV-004`
- `AIR-GOV-005`
- `SKILL-003`
- `SKILL-004`
- `MULTICA-002..004`

## 5. Decision Needed Before Creating In Paperclip

User should approve or adjust:

1. Whether to create all five orgs now, or start with two:
   - Labebe Growth Studio;
   - AI Runtime Governance.

2. Whether Skill Foundry and Browser/Vision Lab should be separate orgs or projects inside AI Runtime Governance.

3. Whether Multica Archive should be a separate org or an archive project.

My recommendation:

```text
Create 3 orgs first:
1. Labebe Growth Studio
2. AI Runtime Governance
3. Multica Archive

Keep Skill Foundry and Browser/Vision Lab as projects under AI Runtime Governance until they become large enough to split.
```
