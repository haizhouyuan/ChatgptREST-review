# Labebe Integrated Program Master Plan

Date: 2026-04-27

## 0. Current Decision Record

The user has made four decisions that change the execution plan:

1. **Amazon / external data sources are not pre-provided.**  
   Codex must discover, compare and manually test the highest-quality and highest-efficiency methods. Start from available skills, local scripts, public pages, browser tooling, and any usable no-key or available-key paths. Do not assume Apify, Keepa or SP-API access until verified.

2. **Website first target is a prototype.**  
   Build a high-fidelity prototype before any production Shopify/independent-site implementation.

3. **Do not force a single business goal.**  
   The DTC prototype must support all four goals:
   - gift conversion;
   - furniture / learning tower trust conversion;
   - room / bundle AOV growth;
   - premium brand rebuild.

4. **Video assets are not supplied manually.**  
   Many assets are likely already live on the brand site, social feeds or paid ad surfaces. Codex must crawl/discover/download usable public brand video assets where possible and log source/provenance.

Additional handoff accepted:

- Another Codex completed a Paperclip/Labebe Wow Demo iteration.
- Current demo is result-first, not Paperclip-first.
- Paperclip is backstage control plane and evidence chain.
- Frontstage should show Labebe AI application outcomes.
- Current service: `python3 -m http.server 8778 --bind 0.0.0.0 --directory /vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs`
- Current URLs:
  - `http://yogas2.tail594315.ts.net:8778/labebe_wow/boss_video.html`
  - `http://yogas2.tail594315.ts.net:8778/labebe_wow/index.html`
  - `http://yogas2.tail594315.ts.net:8778/labebe_wow/labebe_ai_application_wow.mp4`

Advisor synthesis update:

- Do not open new Pro/Gemini reviews unless a new explicit decision conflict appears.
- Use Gemini DeepThink mainly for drift prevention and failure-mode discipline.
- Use the regenerated Pro answer in `qa/Labebe运营系统设计.md` as the primary Pro operating-model memo.
- The active 14-day structure is now:
  - `Labebe Commercial Studio`;
  - `Paperclip Runtime & Evidence Kernel`;
  - `Multica Archive / Pattern Library` as read-only only.
- Browser Harness is allowed only as QA/evidence support, not as a new brain, new agent platform or active org.
- The missing middle layer is formally named `Labebe Commerce Decision Layer`.
- No next high-fidelity DTC redesign should start before the Commerce Decision Layer can justify hero, navigation, PDP modules, bundle logic, asset readiness, claim permissions and rejected alternatives.

## 1. Program Boundary

This is now a two-frontstage program with one shared evidence layer.

```text
Shared evidence layer
  Labebe product intelligence
  Amazon / marketplace intelligence
  public brand media asset library
  VOC / claim / evidence ledger
  design decision matrices

Frontstage A: Pure Labebe DTC Prototype
  A consumer website replacement prototype
  No AI Studio, no Paperclip board, no internal Product Matrix
  Goal: better shopping, trust, brand, bundles, mobile/PDP

Frontstage B: Labebe AI Application Wow Demo
  Boss-facing demo of AI business/product outcomes
  Paperclip is backstage governance/evidence
  Goal: show AI can generate product concepts and market assets while blocking unsafe claims
```

Do not merge Frontstage B into Frontstage A. They may share product data and assets, but they are separate experiences.

## 2. Current State

### 2.1 Product / Website Research State

Planning files already created:

- `planning/20260427_labebe_product_intel_and_design/00_MASTER_PLAN.md`
- `planning/20260427_labebe_product_intel_and_design/01_SOURCE_REGISTRY.yaml`
- `planning/20260427_labebe_product_intel_and_design/02_CURRENT_ARTIFACT_AUDIT.md`
- `planning/20260427_labebe_product_intel_and_design/03_SAMPLE_CRAWL_BRIEF.md`
- `planning/20260427_labebe_product_intel_and_design/04_WEBSITE_DESIGN_RESEARCH_BRIEF.md`
- `planning/20260427_labebe_product_intel_and_design/06_PRO_FEEDBACK_SYNTHESIS_AND_REVISED_PLAN.md`

Pro review:

- Job id: `c33acc4b812e41cea92f4e317efad589`
- Conversation: https://chatgpt.com/c/69eef06f-4828-83e8-a318-286bd2b51b12
- Full answer: `planning/20260427_labebe_product_intel_and_design/pro_packet/pro_answer.md`

Key Pro correction:

```text
Do not only crawl more data and make more design options.
Create the hard middle layer:
product facts -> portfolio judgment -> design decision matrix -> IA/PDP/homepage choices -> design options.
```

### 2.2 Existing Labebe Data

Current local independent-site crawl:

- 46 products.
- 46 product galleries.
- 459 indexed image URLs.
- 460 downloaded local images.
- Collections:
  - furniture: 17
  - rockers-ride-ons: 13
  - pretend-play: 9
  - activity-educational-toys: 6
  - new-in: 1

Known gaps:

- dirty titles;
- CSV/image join mismatches;
- missing PDP fields;
- no full product details;
- no media role classification;
- no video asset library;
- no verified SKU-to-ASIN map;
- Amazon sample review data may mix marketplace/language.

### 2.3 Paperclip / Wow Demo State

Verified locally:

- `paperclip_runtime_duel/outputs/labebe_wow/index.html`
- `paperclip_runtime_duel/outputs/labebe_wow/boss_video.html`
- `paperclip_runtime_duel/outputs/labebe_wow/labebe_ai_application_wow.mp4`
- `paperclip_runtime_duel/outputs/labebe_wow/labebe_ai_application_wow_contact_sheet.jpg`
- `paperclip_runtime_duel/tools/render_labebe_wow_video.mjs`

Local HTTP checks passed for:

- `/labebe_wow/index.html`
- `/labebe_wow/boss_video.html`
- `/labebe_wow/labebe_ai_application_wow.mp4`

Latest relevant commit:

- `9b74ee1 Add Labebe AI application wow demo`

Correct interpretation:

- Current `labebe_wow` is usable as a baseline AI application outcome demo.
- It should not become the consumer DTC website.
- Next iteration should become a Boss Gallery with Demo A-F.

## 3. Workstream A: Product Intelligence and Asset Acquisition

### Goal

Build a design-ready, evidence-tagged Labebe product and channel intelligence layer.

This includes:

- official DTC product data;
- PDP details;
- public brand images and videos;
- Amazon ASIN discovery and validation;
- Amazon listing facts and VOC where feasible;
- competitor and content-gap signals;
- product-to-design decision matrices.

### Method

Start with tooling discovery and manual tests, not full crawl.

#### A0. Tool and Skill Discovery

Inspect and test:

- local scripts:
  - `scrape_labebe.py`
  - `fetch_amazon_reviews_apify.py`
- available Codex skills:
  - web extraction;
  - document extraction;
  - MiniMax media;
  - Claude/agent runner;
  - Playwright / Chrome DevTools MCP if available;
  - GitHub / Google Drive only if useful.
- public no-key methods:
  - Labebe HTML / JSON-LD / Shopify-like endpoints if present;
  - sitemap and collection endpoints;
  - browser network logs for media;
  - Amazon public pages and search pages;
  - public ad libraries or social pages when accessible.

Decision output:

- `tool_method_comparison.md`
- `source_access_matrix.csv`
- `method_failures.md`

#### A1. Data Integrity Baseline

Outputs:

- `product_master_v0.csv`
- `current_data_qa.md`
- `slug_image_join_report.csv`
- `dirty_title_parse_report.csv`
- `do_not_use_fields.md`

Gate:

- all 46 products uniquely identified;
- no silent image/PDP join loss;
- unknown fields explicit;
- fields not safe for copy/design claims listed.

#### A2. 6-8 SKU Stratified Sample

Revised sample must include:

1. Pink Unicorn Plush Rocker.
2. Cream or Midnight Play Kitchen.
3. One Learning Tower variant plus variant-family check.
4. One near-duplicate desk/chair furniture SKU.
5. One low/no-review but commercially important product.
6. ASIN `B087P9SXZQ`, only after verifying what SKU it maps to.
7. One expected Amazon no-match product.
8. One slug/data mismatch sample.

Outputs:

- `sample_product_dossiers/*.md`
- `pdp_facts_sample.csv`
- `image_role_sample.csv`
- `video_asset_sample.csv`
- `asin_candidates_sample.csv`
- `asin_match_scoring.md`
- `amazon_listing_facts_sample.csv`
- `method_comparison.md`

Gate:

- every factual field has source/provenance;
- every ASIN has confidence state;
- review/VOC split by marketplace/language/date/star/verified status;
- media assets tagged by source and usage safety.

#### A3. Public Video and Ad Asset Acquisition

Targets:

- Labebe product pages;
- homepage and collection pages;
- embedded videos;
- Shopify/CDN media URLs if present;
- TikTok / Meta / Instagram / YouTube / Pinterest public brand surfaces;
- public ad library / creative center surfaces if accessible.

Outputs:

- `brand_video_assets.csv`
- `downloaded_media_manifest.csv`
- `media_source_snapshots/`
- `asset_rights_and_usage_notes.md`
- `video_scene_index.csv`

Rules:

- public capture is evidence/source collection, not legal clearance.
- keep source URL, capture time, file hash, page context.
- do not use videos as proof of claims unless the page text supports the claim.

#### A4. Full Product Intelligence

Run only after sample gates pass.

Outputs:

- `product_master_v1.csv`
- `pdp_facts_full.csv`
- `image_roles_full.csv`
- `brand_video_assets_full.csv`
- `asin_match_full.csv`
- `amazon_listing_facts_full.csv`
- `reviews_voc_full.csv`
- `demand_proxy_full.csv`
- `competitor_asins_by_category.csv`
- `crawl_errors.csv`
- updated `source_cards.tsv`

Gate:

- all design-facing claims source-tagged;
- no Amazon signal used as direct sales proof;
- no unsupported safety/certification/material/developmental claims.

## 4. Workstream B: Pure Labebe DTC Website Prototype

### Goal

Create a high-fidelity prototype for a better Labebe consumer DTC website.

It must serve all four business goals:

1. Gift conversion.
2. Furniture / learning tower trust conversion.
3. Room / bundle AOV growth.
4. Premium brand rebuild.

### Design Principle

The prototype should not be one generic warm site. It should express a product system.

Required evidence-to-design bridge:

- `category_portfolio_map.md`
- `hero_candidate_matrix.csv`
- `navigation_decision_matrix.md`
- `pdp_module_strategy_by_category.md`
- `bundle_and_cross_sell_map.csv`
- `voc_to_pdp_reassurance.md`
- `asset_gap_list.md`
- `design_decision_matrix.csv`

### Prototype Options

Build concept boards and key flows for five architecture-level options:

1. **Gift-first Labebe**
   - birthday, baby shower, grandparent gift, holiday;
   - rockers, push walkers, giftables.

2. **Home-fit Furniture Labebe**
   - dimensions, fit, stability, assembly, cleaning, room context;
   - learning towers, desks, shelves, storage.

3. **Child-sized Worlds Labebe**
   - kitchen, shop, laundry, bakery, garden, art corner;
   - pretend play and story-world merchandising.

4. **Playroom Reset Labebe**
   - before/after, storage, room bundles, calm playroom;
   - shelf, bins, desk, room sets.

5. **Object-led Product Theater Labebe**
   - bold product-scale, scroll choreography, product-world transitions;
   - pure DTC only, no AI Matrix.

### Prototype Scope

For each option:

- desktop homepage direction;
- mobile homepage direction;
- collection architecture;
- PDP architecture;
- primary shopper journey;
- hero SKU rationale;
- conversion mechanism;
- asset requirements;
- risk and failure mode.

For implementation:

- implement one primary direction and one fallback as clickable high-fidelity prototype;
- provide a switching bar only for comparing design directions, not as final consumer navigation;
- show mobile and desktop as first-class experiences.

### Hard Reject Conditions

Reject any design that:

- could belong to any children's brand after replacing the logo;
- uses atmosphere instead of product specificity;
- hides PDP facts;
- fails mobile purchase path;
- looks weak on desktop;
- uses fake reviews, fake claims or unsupported certifications;
- puts AI Studio / Paperclip / internal matrix inside consumer website.

## 5. Workstream C: AI Wow Demo / Paperclip Boss Gallery

### Goal

Turn the current result-first `labebe_wow` baseline into a Boss Gallery that demonstrates what AI can do for Labebe beyond a website.

Paperclip remains backstage:

- issue control;
- artifact evidence;
- Claim Gate;
- human review gates;
- audit trail.

Frontstage shows outcomes:

- product opportunity;
- concept;
- design routes;
- safety/DFM preflight;
- market asset matrix;
- blocked claims;
- decision request.

### Current Baseline

Current hero:

- SpaceSmart Foldable Learning Tower.

Current output:

- opportunity signals;
- VOC-to-concept;
- six-channel asset drafts;
- Claim Gate blocks unsupported claims;
- MP4 and interactive page.

### Next Boss Gallery Scope

Build Demo A-F as result cards:

1. **Demo A: Design Opportunity Radar**
   - product/category opportunity signals;
   - evidence labels;
   - opportunity score and uncertainty.

2. **Demo B: VOC → New Product Concept**
   - pain cluster;
   - product requirement;
   - SpaceSmart or another concept card;
   - human review next step.

3. **Demo C: Sketch-to-Concept**
   - rough sketch / product direction to concept routes;
   - selected/rejected reasons;
   - claim boundaries.

4. **Demo D: Custom Toy Kitchen Builder**
   - modular toy kitchen configuration;
   - room fit / bundle logic;
   - not production CAD unless verified.

5. **Demo E: Design Director + DFM/Safety Preflight**
   - stop/go gates;
   - child product risk register;
   - claims blocked before marketing.

6. **Demo F: Concept-to-Market Asset Matrix**
   - PDP;
   - Amazon A+;
   - TikTok/Reels script;
   - Meta carousel;
   - Google image;
   - email/waitlist;
   - each with claim status.

### Boss Gallery Deliverables

- `boss_gallery/index.html`
- `boss_gallery/demo_a_opportunity_radar.html`
- `boss_gallery/demo_b_voc_concept.html`
- `boss_gallery/demo_c_sketch_concept.html`
- `boss_gallery/demo_d_kitchen_builder.html`
- `boss_gallery/demo_e_director_safety_gate.html`
- `boss_gallery/demo_f_asset_matrix.html`
- `boss_gallery/boss_gallery_walkthrough.mp4`
- `boss_gallery/contact_sheet.jpg`
- evidence manifest and claim ledger.

### QA Gate

Every new demo must pass:

- desktop screenshot QA;
- mobile screenshot QA;
- HTTP 200;
- video/contact sheet QA if video is generated;
- evidence chain check;
- forbidden claim scan;
- no unsupported safety/certification/market demand/cost/availability/CAD claim.

## 6. Workstream D: Skills and Maint

### Goal

Do not leave methods as one-off scripts. Convert hard-earned method choices into skills and maint records.

### Required Skills / Notes

1. **Labebe / Amazon Product Intelligence Skill**
   - product master schema;
   - DTC PDP extraction;
   - ASIN discovery and scoring;
   - Amazon public/listing/review/rank method comparison;
   - image/video asset extraction;
   - source/provenance rules;
   - QA and forbidden shortcuts.

2. **MiniMax Media Skill Check**
   - inspect current MiniMax skill coverage;
   - confirm audio/video generation workflow;
   - add missing notes for codingplan key usage only if required and safe;
   - avoid exposing secrets in docs.

3. **AI Wow Demo Skill Notes**
   - result-first boss demo structure;
   - Paperclip as backstage evidence;
   - Claim Gate visualization;
   - video QA and screenshot QA.

### Maint Requirement

After sample methods are validated:

- write method lessons under `/vol1/maint`;
- record tools tested, failures, cost/rate/quality, chosen path and fallback;
- commit maint changes separately.

Do not install or commit unvalidated skills as final.

## 7. Workstream E: Pro Review and QA

### Rule

Ask Pro only with full context packets. No bare questions.

### Review Gates

1. After tool/method sample:
   - ask Pro or local red-team only if method choices remain ambiguous.

2. After Phase 4 design decision matrices:
   - ask Pro to critique IA/PDP/hero/design-option logic.

3. After DTC prototype primary + fallback:
   - ask Pro for strict design review with desktop/mobile screenshots and click path.

4. After Boss Gallery Demo A-F:
   - ask Pro for boss-demo impact review with video/contact sheet/evidence manifest.

### QA Outputs

For every prototype/demo release:

- route map;
- screenshot set;
- mobile screenshots;
- video contact sheet if applicable;
- HTTP 200 checks;
- claim scan;
- evidence manifest;
- known gaps.

## 8. Integrated Execution Order

### Stage 1: Technical Method Probe

Immediate next work.

Tasks:

- discover available tools/skills for browser/PDP/media/Amazon extraction;
- test Labebe product/PDP/media extraction on 2-3 URLs;
- test Amazon ASIN discovery and listing extraction on 1-2 samples;
- test public video/ad discovery paths;
- record method comparison.

Outputs:

- `tool_method_comparison.md`
- `source_access_matrix.csv`
- `initial_media_probe.md`

### Stage 2: Data QA and Stratified Sample

Tasks:

- create product master v0;
- repair title/slug/image joins;
- build 6-8 sample dossiers;
- classify image/video assets for sample;
- produce ASIN match candidates.

Outputs:

- sample dossiers and QA reports.

### Stage 3: Decision Matrices

Tasks:

- category portfolio map;
- hero candidate matrix;
- navigation decision matrix;
- PDP module strategy;
- bundle map;
- asset gap list.

Output:

- evidence-to-design bridge approved before visual work.

### Stage 4: Parallel Frontstage Prototypes

Frontstage A:

- pure DTC website concept boards;
- primary + fallback clickable prototype;
- desktop/mobile paths.

Frontstage B:

- AI Wow Boss Gallery A-F;
- update current `labebe_wow` entry to point to Boss Gallery;
- video walkthrough.

### Stage 5: Pro Review and Revision

Submit two separate packets:

1. DTC prototype review.
2. AI Wow Boss Gallery review.

Do not mix them into one review unless the question is explicitly about the overall executive presentation.

### Stage 6: Final Executive Presentation Pack

Package:

- DTC website prototype URL;
- mobile and desktop screenshots;
- AI Wow Boss Gallery URL;
- 90-second boss video;
- product intelligence one-pager;
- claim/evidence policy;
- next investment decision asks.

## 9. Immediate Next Step

Start Stage 1.

Do not start full crawl yet.
Do not redesign the website yet.
Do not expand AI Wow Gallery yet.

First prove the method:

```text
tools/skills -> 2-3 Labebe PDPs -> media extraction -> Amazon discovery sample -> method comparison
```

Only after this should we launch sample dossiers and design matrices.
