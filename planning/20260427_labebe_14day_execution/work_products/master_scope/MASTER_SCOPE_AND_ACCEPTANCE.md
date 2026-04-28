# Master Scope And Acceptance

Generated: 2026-04-27
Owner: Codex main controller

## User Intent

The user does not want round-by-round approvals. The expected outcome is a
complete, evidence-backed masterplan execution across product research, website
design, AI/Paperclip demo presentation, video/display strategy, QA, and skill /
runtime governance.

The work must keep moving autonomously until the deliverables are complete or a
hard boundary is reached.

## Hard Separation Of Surfaces

| Surface | Purpose | Must Include | Must Not Include |
| --- | --- | --- | --- |
| Labebe DTC website | Replace/improve the consumer independent store. | Product-first commerce, room/age/gift navigation, PDPs, collection flows, cart/bundle UX, mobile and desktop polish. | Paperclip UI, AI workflow, internal claim gate, technical demo language. |
| Paperclip / Boss Gallery | Show decision makers the AI application result and control system. | Demo A-F, result-first assets, Claim Gate, evidence links, walkthrough video. | Consumer shopping confusion or fake production claims. |
| Masterplan / Evidence Pack | Keep strategy, research, backlog, QA and handoffs coherent. | Source registry, product facts, marketplace limits, design decisions, QA evidence, next actions. | Unsupported claims or vague strategy-only writing. |
| Skill / Runtime Governance | Improve long-term agent execution quality. | Skill inventory, usage logging plan, MCP vs CLI vs Skill placement, Browser Harness QA layer, maint updates. | A new uncontrolled platform that distracts from Labebe/Paperclip execution. |

## Full Task Scope

### 1. Product Reality Layer

Goal: know what Labebe actually has before designing around it.

Required outputs:

- current DTC product master;
- all known product categories and counts;
- 6-8 sample dossiers plus path to full-catalog enrichment;
- media/asset inventory;
- blocked/unknown product fields;
- claim permission ledger.

Done means:

- product identity is stable by product URL/slug;
- known bad fields are not used downstream;
- each sample SKU has a dossier with facts, images, risks and next evidence.

### 2. Marketplace / Amazon Layer

Goal: avoid false marketplace claims while building a repeatable path to Amazon
truth.

Required outputs:

- ASIN identity-first workflow;
- sample candidate matrix;
- rejected/unknown candidates;
- source/method comparison;
- next controlled browser capture plan.

Done means:

- no Amazon sales/rank/rating/review claim is used unless identity is verified;
- the method can be delegated safely after sample validation.

### 3. Design Research And Direction Layer

Goal: build a design method, not another generic page.

Required outputs:

- design reference pattern library;
- DTC commerce pattern library;
- rejected direction log;
- mapping from Labebe product reality to design decisions;
- multiple creative directions/concept-board logic before final site polish.

Done means:

- design choices are linked to shopper tasks and product facts;
- previous weak directions are explicitly blocked from returning.

### 4. Labebe Pure DTC Website

Goal: create a credible, high-quality independent-store replacement.

Required outputs:

- implemented website prototype;
- home, collection, shop-by-room, shop-by-age, PDP routes;
- mobile/desktop QA;
- product cards, bundles, room planning, cart/add-to-cart behavior;
- documented design decisions and remaining production gaps.

Done means:

- the site is visually stronger than prior Kimi/prototype attempts;
- it works on mobile and desktop;
- no AI/Paperclip internal demo leaks into the consumer surface;
- unsupported product claims are absent.

### 5. Paperclip / AI Boss Gallery

Goal: show AI business impact separately from the shopping site.

Required outputs:

- internal Boss Gallery;
- Demo A-F surfaces;
- one-SKU-to-channel asset matrix;
- VOC-to-concept framing;
- Claim Gate blocked/allowed claims;
- evidence links and walkthrough plan.

Done means:

- the gallery demonstrates outcome first, then control;
- every impressive output is clearly prototype/claim-gated;
- it does not pollute the DTC website.

### 6. Video / Presentation Layer

Goal: make the result easy to show on phone and desktop.

Required outputs:

- walkthrough plan for DTC website and Boss Gallery;
- screen-recording + generated media strategy;
- storyboard / shot list;
- QA checklist for video readability and transitions;
- final or next-step video artifact depending on available generation/runtime.

Done means:

- a decision maker can understand the site/demo without reading docs;
- video does not overclaim real footage or production readiness.

### 7. Browser Harness / Visual QA Layer

Goal: stop accepting pages/videos that technically load but visually fail.

Required outputs:

- browser harness P0 contract;
- CDP screenshot tooling;
- mobile/desktop overflow and nonblank checks;
- visual review checklist;
- clear boundary: QA/取证 support only, not a new autonomous brain.

Done means:

- future agents can run repeatable screenshot/overflow checks;
- QA artifacts are attached to deliverables.

### 8. Skill / MCP / Runtime Governance

Goal: make the wider agent system learn from errors and use the right capability
shape.

Required outputs:

- inventory of relevant skills/backlogs;
- MiniMax video/audio skill placement check;
- skill usage logging/gov loop design;
- MCP vs CLI vs Skill decision rules;
- GStack/AgencyAgents integration judgment;
- maint repo record/update plan and implementation where safe.

Done means:

- a future agent knows when to use MiniMax, Browser Harness, skills, MCP or CLI;
- stale skills/backlogs are either archived or assigned a governance path.

### 9. Final Integration Pack

Goal: make the whole effort resumable and reviewable.

Required outputs:

- executive decision pack;
- artifact index;
- evidence manifests;
- route map and URLs;
- QA screenshots;
- issue ledger;
- final zip package.

Done means:

- after context loss, a new agent can restart from the package without guessing;
- user can open URLs and documents directly.

## Autonomous Execution Rules

- Do not ask the user to choose between options; build the best reasonable
  version and document alternatives.
- Do not start new Pro/Gemini loops unless a concrete deliverable requires
  external critique and enough context can be packaged in one shot.
- Do not treat slow/blocked external review as a stop condition.
- Do not use fake product facts, fake reviews, fake ratings, fake Amazon
  performance or fake certifications.
- Do not delete or revert user/other-agent work.
- Do not make paid/irreversible/account-sensitive actions without explicit user
  instruction; log blocker and continue alternatives.

## Current Completion Status

Updated: 2026-04-28 after continuation execution.

| Layer | Current status | Boundary |
|---|---|---|
| Product Reality Layer | Review-ready plus current live-catalog update. The local source moved from the older 46-product table to a 60-visible-SKU live probe, product worlds/roles were derived, and 8 Labebe PDPs were captured for source text and claim review. | The 333-row PDP claim queue is manual-review-only; it is not approved marketing copy. |
| Marketplace / Amazon Layer | Sample method validated. Expanded search produced 419 candidate rows; 15 ASIN PDP probes were indexed; 7 rows are identity-whitelist candidates after contact-sheet review. The authorized review/VOC runner now has a dry-run plan, the VOC summarizer has a format smoke, and all 60 DTC SKU rows are assigned to marketplace enrichment worker batches. | Full Amazon truth and real review/VOC extraction remain gated by authorized provider/login access and batch execution. No public sales/rating/review claim is approved. |
| Design Research And Direction Layer | Review-ready and product-backed. The DTC design direction is now driven by the product strategy matrix and three pure consumer creative modes: Gift Theater, Room Builder, and Play Worlds. | Do not reopen generic Montessori-layout directions unless new product evidence demands it. |
| Labebe Pure DTC Website | Implemented prototype and currently exposed for external review at `https://yogas2.tail594315.ts.net:10000/`. It has product-first navigation, collection/PDP routes, cart drawer, checkout handoff, mobile/desktop QA, no AI/Paperclip leakage, explicit image source chain, and a 26-row production asset clearance queue. | It is not a production checkout/backend. Production media/legal approval is still required; the queue is a handoff, not approval. The legacy raw DDNS path `http://fnos.dandanbaba.xyz:8790/` may fail through router/DDNS/proxy. |
| Paperclip / AI Boss Gallery | Internal Boss Gallery v0 is implemented separately at `http://fnos.dandanbaba.xyz:8778/boss_gallery_v0/index.html`, with Demo A-F framing, Claim Gate, evidence links, Paperclip issue binding, and walkthrough videos. Demo A-F are bound to existing Paperclip issues LAB-2, LAB-3, LAB-4, LAB-5, LAB-7 and LAB-8; LAB-9 has the shared Boss Gallery index. | Binding is evidence/document binding only; it does not mark issues done or approve external publication. Keep this out of the DTC website. |
| Video / Presentation Layer | DTC desktop/mobile walkthroughs and Boss Gallery desktop/mobile walkthroughs are rendered, served, and contact-sheet checked. | These are demo walkthroughs, not paid-ad-ready launch videos. |
| Browser Harness / Visual QA Layer | Local reusable Browser Harness P0 is executable and now has a localhost service wrapper. It captures screenshots, sidecar metrics, visible text/CTA inventory, horizontal overflow, likely blank state, console/log entries, network failures and route/view matrix reports. Matrix smoke passed 5/5 on DTC and Boss Gallery representative routes; service smoke passed for health/schema/capture. | It must stay a QA/evidence layer, not a new decision brain. It does not manage authenticated sessions or submit external model jobs. |
| Skill / MCP / Runtime Governance | Review-ready docs exist, and maint has recorded Labebe lessons through the asset-chain cleanup commit. | Long-term skill lifecycle telemetry and shared harness integration remain outside the Labebe DTC deliverable. |
| Final Integration Pack | Incremental package is rebuilt and verified with stale-entry scan, `unzip -t`, and SHA-256 sidecar. | Package reflects the current prototype/research state, not production commerce readiness. |
