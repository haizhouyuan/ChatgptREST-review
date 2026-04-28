# Labebe / Paperclip 14-Day High-Standard Implementation Plan

Date: 2026-04-27
Owner: Codex main controller
Status: Draft v1 before final Pro confirmation

## 0. Executive Intent

The goal is not to make another prettier Labebe website screenshot. The goal is to prove that a single-user AI operating system can produce a business-grade Labebe outcome with evidence, judgment, design quality, claim discipline and handoff continuity.

The 14-day sprint has two visible frontstage outputs and one shared backstage layer:

1. **Pure Labebe DTC Website Prototype**
   - Consumer-facing independent-site replacement prototype.
   - No AI Studio.
   - No Paperclip board.
   - No internal product matrix.
   - Must improve shopping clarity, product trust, brand perception, bundles, mobile UX, PDP conversion and room/gift flows.

2. **Labebe AI Application Wow / Boss Gallery**
   - Decision-maker-facing result demo.
   - Shows how AI turns product facts, VOC, images, videos and channel requirements into concepts, scripts, visual directions, marketing assets, claim gates and evidence-backed workflows.
   - Paperclip stays backstage as governance and evidence chain, not the frontstage story.

3. **Shared Evidence + Decision Layer**
   - Product facts.
   - Marketplace/Amazon identity and listing signals.
   - Public brand media assets.
   - VOC and claim ledger.
   - Design references mapped to Labebe business problems.
   - `Labebe Commerce Decision Layer`, the missing bridge from facts to design decisions.

## 1. Non-Negotiable Boundaries

### 1.1 DTC Site Scope

Allowed:

- product discovery;
- homepage;
- collection navigation;
- PDP;
- room/gift paths;
- cart or bundle flow;
- trust modules;
- mobile-first UX;
- visual identity and motion;
- AI-generated placeholder visuals only if clearly marked in internal files and not used as factual claims.

Forbidden:

- AI Studio inside the consumer website;
- Paperclip board inside the consumer website;
- internal product matrix inside the consumer website;
- unsupported reviews, ratings, certifications, material claims, safety claims, market demand claims or development-benefit claims;
- fake founder story, fake awards, fake press, fake manufacturing origin;
- generic children-brand template that could become any toy brand after a logo swap.

### 1.2 Boss Gallery Scope

Allowed:

- result-first AI application demos;
- Demo A-F skeleton if claim-gated;
- 2-3 deeply polished wow demos;
- concept cards;
- asset matrices;
- claim status badges;
- evidence links;
- blocked claims;
- executive walkthrough video.

Forbidden:

- opening with Paperclip workflow instead of Labebe business outcome;
- presenting concepts as production CAD, certified-safe products, real sales demand or approved launch items;
- mixing Boss Gallery with DTC consumer website;
- making video packaging stronger than the underlying evidence and prototype.

### 1.3 Runtime Scope

Allowed:

- minimal issue/evidence contract;
- mandatory/advisory gate templates;
- Browser Harness as QA/evidence support;
- secret/session/cookie safety checks;
- closeout discipline.

Forbidden:

- turning Browser Harness into a new autonomous agent brain;
- making Skill Foundry a first-class org during this sprint;
- importing GStack wholesale;
- bulk-installing AgencyAgents;
- reviving Multica as the control plane;
- blocking Labebe work because full runtime governance is not complete.

## 2. Operating Model

### 2.1 Active Orgs

There are exactly two active orgs during this sprint.

#### Org 1: `Labebe Commercial Studio`

Purpose:

- deliver Labebe product/channel intelligence;
- build the Commerce Decision Layer;
- produce DTC primary/fallback prototypes;
- produce Boss Gallery v0;
- prepare executive decision pack.

Projects:

1. `00_scope_and_source_registry`
2. `01_product_channel_intelligence`
3. `02_public_media_asset_library`
4. `03_commerce_decision_layer`
5. `04_pure_dtc_prototype`
6. `05_ai_boss_gallery`
7. `06_executive_pack`

#### Org 2: `Paperclip Runtime & Evidence Kernel`

Purpose:

- keep issues evidence-backed;
- enforce scope, claim, design and closeout gates;
- provide Browser/Visual QA support;
- preserve handoff continuity;
- prevent agent self-reporting from being mistaken for completion.

Projects:

1. `00_issue_evidence_contract`
2. `01_gate_kernel`
3. `02_runtime_policy_thin_gate`
4. `03_visual_browser_qa`
5. `04_agent_delegation_and_handoff`

### 2.2 Read-Only Area

`Multica Archive / Pattern Library`

Rules:

- read-only during this sprint;
- allowed output: concise lessons, failed fixture notes, do-not-count-as-success notes;
- no migration of large historical issue sets;
- no daily control-plane role.

## 3. The Missing Middle Layer

The core artifact is:

```text
Labebe Commerce Decision Layer
```

It translates product facts into website decisions.

### Inputs

- DTC product master and PDP facts;
- category membership;
- product images and video assets;
- Amazon/marketplace ASIN identity and listing facts;
- VOC only after ASIN confidence;
- claim/source evidence;
- design reference pattern research;
- current data gaps and unknowns.

### Outputs

- `category_portfolio_map.md`
- `shopper_mission_map.md`
- `hero_candidate_matrix.csv`
- `sku_role_matrix.csv`
- `navigation_decision_matrix.md`
- `pdp_module_strategy_by_category.md`
- `bundle_and_cross_sell_map.csv`
- `claim_permission_matrix.csv`
- `asset_readiness_matrix.csv`
- `reference_pattern_mapping.md`
- `design_decision_matrix.csv`
- `rejected_direction_log.md`

### Hard Rule

No next high-fidelity DTC redesign starts until the Commerce Decision Layer explains:

- hero SKU choice;
- navigation architecture;
- PDP module order;
- collection logic;
- bundle/cross-sell logic;
- asset readiness;
- claim permissions;
- rejected alternatives.

## 4. Mandatory Gates

| Gate | Trigger | Required Evidence | Pass Standard |
| --- | --- | --- | --- |
| Scope Separation Gate | Before DTC or Boss Gallery implementation | `scope_boundary.md` | DTC has no AI/Paperclip/internal matrix; Boss Gallery is not a consumer site |
| Evidence Integrity Gate | Before product facts enter design decisions | `current_data_qa.md`, `do_not_use_fields.md` | 46 products uniquely identified; dirty fields and joins explicit |
| ASIN Identity Gate | Before Amazon/VOC use | `asin_match_scoring.md` | accepted/probable/candidate/rejected/no-match status per ASIN |
| Claim Gate | Before any copy/demo/PDP/asset claim is shown | `claim_permission_matrix.csv`, `blocked_claims.md` | unsupported claims blocked or downgraded |
| Design Decision Gate | Before high-fidelity DTC prototype | `design_decision_matrix.csv` | hero/nav/PDP/bundle/asset decisions trace to evidence and alternatives |
| Browser / Visual QA Gate | Before user/boss-facing review | `browser_qa_report.md`, `design_review_report.md`, screenshots | HTTP, mobile, console, links, core flow and visual hierarchy have no P0/P1 |
| Closeout Gate | Before issue done | `closeout.md`, `checkpoint.md`, `evidence_manifest.json` | acceptance criteria map to evidence |

## 5. Advisory Gates

- CEO / Wow Review: direction selection, Boss Gallery first 30 seconds, executive pack.
- Full Design Review Scoring: concept boards and prototypes.
- Fresh Agent Review: after primary/fallback prototype.
- Pro Review: only when artifacts are strong enough; this plan currently allows one final confirmation only.
- Skill Curator Review: only after repeated blocking skill failures.

## 6. Explicit Deferrals

Defer until after this sprint:

- full Skill Foundry;
- full Browser and Vision Lab;
- full machine topology program;
- historical conversation skill mining;
- full MCP/CLI/skill decision matrix;
- full Multica migration;
- five complete DTC websites;
- full Amazon review crawl before sample path validation;
- Pro/Gemini review loops.

## 7. First 10 Paperclip Issues

### `PCL-001 Minimal Paperclip Operating Kernel`

Owner role: Paperclip Program Architect.

Acceptance:

- create two active org definitions;
- create project tree;
- define issue evidence contract;
- define evidence manifest schema;
- define mandatory/advisory gates v0.

Evidence:

- `paperclip_org_tree.md`
- `issue_evidence_contract.md`
- `gate_kernel_v0.md`
- `evidence_manifest_schema.json`

Stop condition:

- if the work starts expanding into five active orgs or platform governance, stop and reduce scope.

### `LAB-001 Scope Boundary and Source Registry`

Owner role: Program Strategist / Evidence Steward.

Acceptance:

- define DTC allowed/forbidden scope;
- define Boss Gallery allowed/forbidden scope;
- define shared evidence layer;
- create source registry skeleton.

Evidence:

- `scope_boundary.md`
- `source_registry.yaml`
- `source_cards.tsv`

### `LAB-002 Tool and Source Method Probe`

Owner role: Tooling Research Engineer.

Acceptance:

- test 2-3 Labebe PDP/collection/media extraction paths;
- test 1-2 Amazon sample paths;
- compare no-key/manual/key-required approaches;
- record failures and limitations.

Evidence:

- `tool_method_comparison.md`
- `source_access_matrix.csv`
- `method_failures.md`
- `initial_media_probe.md`

### `LAB-003 Product Master v0 and Data QA`

Owner role: Product Data Analyst.

Acceptance:

- uniquely identify all 46 known DTC products;
- check slug/image/PDP joins;
- parse dirty titles;
- list fields that cannot be used for copy or claim.

Evidence:

- `product_master_v0.csv`
- `current_data_qa.md`
- `slug_image_join_report.csv`
- `dirty_title_parse_report.csv`
- `do_not_use_fields.md`

### `LAB-004 Stratified 6-8 SKU Product Dossiers`

Owner role: Product Intelligence Analyst.

Acceptance:

- select 6-8 sample SKUs;
- include Pink Unicorn, Kitchen, Learning Tower, near-duplicate furniture SKU, low/no-review important SKU, ASIN `B087P9SXZQ` mapping check, expected no-match, and slug/data mismatch where possible;
- create dossiers with facts, unknowns, assets, claim seeds.

Evidence:

- `sample_selection_rationale.md`
- `sample_product_dossiers/*.md`
- `pdp_facts_sample.csv`
- `image_role_sample.csv`
- `claim_seed_ledger.csv`

### `LAB-005 ASIN Identity and Marketplace Listing Sample`

Owner role: Marketplace Intelligence Analyst.

Acceptance:

- create ASIN candidates for sample SKUs;
- score identity confidence;
- extract listing facts where feasible;
- separate marketplace/language/source risks.

Evidence:

- `asin_candidates_sample.csv`
- `asin_match_scoring.md`
- `amazon_listing_facts_sample.csv`
- `amazon_source_limitations.md`

### `LAB-006 Public Media Asset Probe and Scene Index`

Owner role: Media Asset Researcher.

Acceptance:

- discover public brand images/video/ad samples;
- download allowable samples with source and hash;
- classify media roles and scenes;
- document usage caveats.

Evidence:

- `brand_video_assets.csv`
- `downloaded_media_manifest.csv`
- `media_source_snapshots/`
- `video_scene_index.csv`
- `asset_rights_and_usage_notes.md`

### `LAB-007 Commerce Decision Layer v0`

Owner role: Commerce Strategist / UX Architect.

Acceptance:

- map category portfolio roles;
- define shopper missions;
- select hero candidates;
- choose navigation logic;
- define PDP modules by category;
- define bundle map;
- define asset readiness and claim permissions;
- produce design decision matrix and rejected direction log.

Evidence:

- `category_portfolio_map.md`
- `shopper_mission_map.md`
- `hero_candidate_matrix.csv`
- `sku_role_matrix.csv`
- `navigation_decision_matrix.md`
- `pdp_module_strategy_by_category.md`
- `bundle_and_cross_sell_map.csv`
- `asset_readiness_matrix.csv`
- `claim_permission_matrix.csv`
- `design_decision_matrix.csv`
- `rejected_direction_log.md`

### `LAB-008 Pure DTC Primary + Fallback Prototype`

Owner role: UX Designer / Prototype Engineer.

Acceptance:

- create one primary and one fallback high-fidelity clickable prototype;
- include desktop/mobile homepage, collection, PDP and core purchase/bundle flow;
- produce route map and screenshot evidence;
- no AI/Paperclip/internal matrix inside DTC.

Evidence:

- prototype URL/build;
- `route_map.md`;
- desktop/mobile screenshots;
- `design_review_report_dtc.md`;
- `browser_qa_report_dtc.md`.

### `LAB-009 AI Boss Gallery A-F v0 with Claim Gate`

Owner role: AI Demo Producer / Claim Steward.

Acceptance:

- build A-F gallery skeleton based on existing `labebe_wow`;
- polish 2-3 strongest demos;
- each demo has evidence labels, claim status and blocked claims;
- pass browser/mobile QA.

Evidence:

- `boss_gallery/index.html`;
- demo pages;
- `boss_gallery_claim_ledger.csv`;
- `blocked_claims.md`;
- `browser_qa_report_boss_gallery.md`;
- contact sheet/video QA if generated.

## 8. 14-Day Timeline

### Day 1: Minimal Paperclip Kernel + Scope Freeze

Outputs:

- org/project tree;
- `scope_boundary.md`;
- `issue_evidence_contract.md`;
- `gate_kernel_v0.md`;
- `source_registry.yaml`;
- `source_cards.tsv`.

### Day 2: Tool / Source Method Probe

Outputs:

- `tool_method_comparison.md`;
- `source_access_matrix.csv`;
- `method_failures.md`;
- `initial_media_probe.md`.

### Day 3: Product Master v0 + Data QA

Outputs:

- `product_master_v0.csv`;
- `slug_image_join_report.csv`;
- `dirty_title_parse_report.csv`;
- `do_not_use_fields.md`;
- `sample_selection_rationale.md`.

### Day 4: DTC PDP Sample Dossiers

Outputs:

- `sample_product_dossiers/*.md`;
- `pdp_facts_sample.csv`;
- `image_role_sample.csv`;
- `claim_seed_ledger.csv`.

### Day 5: ASIN Identity and Listing Sample

Outputs:

- `asin_candidates_sample.csv`;
- `asin_match_scoring.md`;
- `amazon_listing_facts_sample.csv`;
- `amazon_source_limitations.md`.

### Day 6: Public Media Sample + Design Reference Research

Outputs:

- `brand_video_assets.csv`;
- `downloaded_media_manifest.csv`;
- `video_scene_index.csv`;
- `asset_rights_and_usage_notes.md`;
- `reference_pattern_mapping.md`.

### Day 7: Week 1 Synthesis Wall

Outputs:

- `labebe_evidence_wall_v0.md`;
- `claim_permission_matrix_v0.csv`;
- `asset_gap_list.md`;
- `evidence_integrity_gate_report.md`;
- `week1_go_no_go.md`.

### Day 8: Commerce Decision Layer v0

Outputs:

- all `LAB-007` artifacts.

### Day 9: Five Architecture Concept Boards

Boards:

1. Gift-first Labebe.
2. Home-fit Furniture Labebe.
3. Child-sized Worlds Labebe.
4. Playroom Reset Labebe.
5. Object-led Product Theater Labebe.

Outputs:

- `concept_boards/*.md`;
- `concept_selection_matrix.csv`.

### Day 10: Primary + Fallback Selection

Outputs:

- `ceo_wow_review_dtc_direction.md`;
- `design_decision_gate_report.md`;
- `primary_fallback_decision.md`;
- `dtc_prototype_brief.md`.

### Day 11-12: DTC Prototype + Boss Gallery v0

DTC outputs:

- primary prototype;
- fallback prototype;
- route map;
- homepage/collection/PDP flows;
- desktop/mobile screenshots.

Boss Gallery outputs:

- A-F gallery skeleton;
- 2-3 polished demos;
- claim ledger;
- blocked claims.

### Day 13: QA and Claim Gate

Outputs:

- `browser_qa_report_dtc.md`;
- `design_review_report_dtc.md`;
- `browser_qa_report_boss_gallery.md`;
- `claim_gate_report_boss_gallery.md`;
- mobile/desktop screenshots;
- contact sheet/video QA where applicable.

### Day 14: Executive Decision Pack

Outputs:

- DTC prototype URL + screenshots;
- Boss Gallery URL + walkthrough;
- `labebe_evidence_wall_v1.md`;
- `design_decision_summary.md`;
- `next_build_scope.md`;
- `executive_pack.md`;
- closeout manifests.

## 9. Parallel Execution Strategy

### 9.1 Main Controller

The main Codex controller owns:

- plan integrity;
- source-of-truth docs;
- Pro confirmation and synthesis;
- final issue sequencing;
- integration of delegated results;
- quality gates;
- user report.

### 9.2 Kimi Code / Claude Code Kimi Delegation Candidates

Delegation begins after Pro confirmation unless a local task is strictly non-conflicting.

Candidate work packages:

1. **Claude Code Kimi / Claude Code: Product Data QA**
   - files owned: `planning/.../product_intel/`, no prototype code edits;
   - task: inspect existing Labebe crawl scripts/data, produce product master v0 and data QA method notes.

2. **Kimi Code: Public Media Probe**
   - files owned: `planning/.../media_assets/`;
   - task: discover likely public media paths, draft media manifest schema, test safe sample extraction.

3. **Claude Code: Amazon Method Probe**
   - files owned: `planning/.../marketplace/`;
   - task: compare no-key/manual/script/API paths, verify ASIN identity workflow on sample products.

4. **Kimi Code: Design Reference Mapping**
   - files owned: `planning/.../design_references/`;
   - task: turn existing design reference pack into business-problem pattern map.

5. **Claude Code or local Codex: Browser / Visual QA Template**
   - files owned: `planning/.../runtime_kernel/qa_templates/`;
   - task: define Browser Harness P0 artifact contract without building a new platform.

### 9.3 Delegation Rules

- Each delegated task must have a disjoint write path.
- Delegates must not call Pro/Gemini.
- Delegates must not change DTC prototype code before `LAB-007` exists.
- Delegates must record evidence and limitations.
- Delegates must produce `handoff.md` and `evidence_manifest.json`.
- Main controller integrates; delegates do not mark sprint-level done.

## 10. Quality Bar

The sprint is successful only if:

- the website decisions are traceable to product/channel/media evidence;
- DTC and Boss Gallery remain separate;
- at least one primary and one fallback DTC prototype exist after gates;
- Boss Gallery shows result-first Labebe AI outcomes, not tool process;
- all risky claims are blocked or downgraded;
- desktop/mobile screenshots exist;
- visual QA explicitly critiques cheap AI-template feel;
- every issue closeout points to artifacts;
- next agent can continue from docs without reading chat history.

The sprint fails if:

- a page opens but design is generic;
- an issue is called done without evidence;
- Pro/Gemini review becomes a loop;
- Browser Harness becomes a new platform;
- Skill Foundry or Multica migration consumes the sprint;
- Amazon review/VOC enters decisions without ASIN confidence;
- DTC site contains internal AI/Paperclip artifacts.

## 11. Pro Confirmation Ask

The Pro confirmation should check:

1. Is the plan still too complex?
2. Are the two active orgs and read-only archive the right structure?
3. Are the first 10 issues correctly ordered?
4. Is the Commerce Decision Layer sufficiently defined?
5. Are the gates too heavy or too light?
6. Does the parallelization strategy protect quality and speed?
7. What should be cut, merged or made stricter before execution?

## 12. Current Plan Status

This is draft v1. It must be revised after the final Pro confirmation answer is received.

