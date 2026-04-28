# Labebe Product Intelligence and Website Design Prework Plan

Date: 2026-04-27

## 0. Executive Position

Before继续做 Labebe 网站设计，必须先完成两件基础工作：

1. **产品与渠道现状梳理**：从 Labebe 独立站全目录出发，穷尽式搞清楚每个产品是什么、属于什么类别、价格/折扣/评论/图片/卖点/规格/页面结构如何，并补上 Amazon 侧的 ASIN、listing、价格、review、BSR/rank、竞品与销量信号。
2. **产品洞察驱动的网站设计研究**：不是先凭审美做页面，而是基于产品矩阵、销售强弱、渠道表现、用户场景与竞品借鉴，形成多套不同创意方向的网站设计方案，并用视频/录屏/动效模拟来展示设计思路和用户访问场景。

这两个工作是网站重做前置，不是附属资料。否则网站会继续停留在“看起来不错但不知道为什么这样设计”的阶段。

## 1. Goals

### 1.1 Product Intelligence Goals

- 建立 Labebe 全产品主数据表，覆盖独立站 46 个产品以及后续发现的 Amazon 对应 listing。
- 对每个产品形成可追溯档案：独立站事实、Amazon 事实、review/VOC、销量/排名代理信号、图片素材、风险/未知字段。
- 先用 3-5 个样本 SKU 打通方法和字段，再并行跑全量，避免一开始大规模低质量爬取。
- 形成可复用抓取与分析 skill，写回 maint，后续换品牌/类目也能复用。

### 1.2 Website Design Goals

- 从产品真实结构出发，定义 Labebe 应该如何组织网站：按年龄、房间、礼物、玩法、产品线、价格带、强势 SKU、弱势 SKU、Amazon 反馈来设计，而不是套通用儿童家具模板。
- 形成至少 4 套差异明显的网站设计方向，不是同一版换色：
  - 高端儿童成长空间品牌站；
  - 礼物/里程碑导购站；
  - 房间/场景搭配型站；
  - 内容/视频驱动的 DTC 增长站；
  - 可选：更激进的互动产品剧场。
- 每套设计方案都要展示：首页、集合页、PDP、移动端、关键购买路径、视觉基调、动效/视频呈现方式。
- 最终给老板看的不是静态截图，而是“设计方案视频”：录屏模拟用户访问、点击、筛选、进入 PDP、加入购物车、观看动效，并叠加 AI 生成的场景图/视频片段作为概念展示。

## 2. Current State Inventory

### 2.1 已有独立站抓取资产

Source files:

- `data/labebe/labebe_products.csv`
- `data/labebe/labebe_products_with_images.csv`
- `data/labebe/all_product_images.json`
- `data/labebe/images/`
- `docs/labebe-scrape-report-2026-04-24.md`
- `scrape_labebe.py`

Current snapshot:

| Item | Current State |
|---|---|
| Products | 46 |
| Indexed product image galleries | 46 |
| Indexed image URLs | 459 |
| Local downloaded images | 460 |
| Average indexed images / product | 10.0 |
| Collections | furniture 17, rockers-ride-ons 13, pretend-play 9, activity-educational-toys 6, new-in 1 |
| Price range | $33.99 - $179.99 |
| Site review-count leaders | Pink Unicorn Plush Rocker 18; Children’s Writing Desk & Chair 12; Kids Wooden Desk & Chair 11; Midnight Serenity Kitchen 10; Cream Kitchen 9; Montessori Shelf 9 |

What is useful:

- Product universe is already mostly identified.
- Collection distribution and product images are strong enough to support a product-family wall and visual design research.
- Independent-site review counts give weak but useful “onsite signal” ordering.

What is not done well enough:

- `title` fields are dirty; many include promo labels, price and review count inside title text.
- Collection pages are scraped, but PDP details are not fully extracted.
- Missing or incomplete fields: descriptions, bullets, dimensions, materials, age guidance, certifications, package size, assembly/care, variants, inventory, structured data, breadcrumbs, FAQ, media type classification.
- Image gallery is complete but not classified by image role: main product, lifestyle, dimensions, packaging, infographic, room scene, close-up, child-use scene, safety/assembly.
- Existing scrape report says complete, but “complete” only means product list + images complete, not product intelligence complete.

### 2.2 Existing Amazon Assets

Source files:

- `fetch_amazon_reviews_apify.py`
- `data/amazon_reviews_US_B087P9SXZQ.csv`
- `data/amazon_reviews_US_B087P9SXZQ.jsonl`

Current snapshot:

| Item | Current State |
|---|---|
| Covered ASINs | 1 |
| Sample ASIN | `B087P9SXZQ` |
| Sample rows after dedupe | 13 |
| Rating distribution | 5-star 7; 4-star 2; 3-star 1; 2-star 1; 1-star 2 |
| Script capability | Apify review scrape by ASIN, marketplace, star filter, sort |

What is useful:

- Review extraction method exists and normalizes review text, rating, date, author, verified purchase, helpful votes.
- The sample demonstrates VOC fields that can feed product diagnosis and marketing messaging.

What is not done well enough:

- No mapping from Labebe independent-site SKUs to Amazon ASINs.
- No Amazon listing scrape for title, price, coupon, rating, review count, images, A+ content, brand store, seller, Prime/FBA, variations.
- No Best Seller Rank / sales-rank history / category rank.
- No “bought in past month” or other public demand signal captured where available.
- No competitor ASIN set per Labebe category.
- No methodology for resolving duplicate listings, resellers, unavailable products, old ASINs, or Labebe-like non-official listings.
- No cost/rate-limit/accuracy comparison between Apify, SP-API, Keepa, SERP scraping, and direct page extraction.

### 2.3 Existing Website and Design Assets

Source areas:

- `labebe-gemini-demo/`
- `kimi_labebe_design_library/`
- `labebe_design_reference_pack/`
- `research/20260425_design_dtc_research_v2/`
- `research/20260425_website_design_dtc/`
- `pro_requests/20260425_*`
- `pro_requests/20260426_radical_design_brainstorm/`
- `qa/`

What is useful:

- Multiple Pro review rounds have clarified the difference between:
  - pure Labebe DTC website;
  - AI Product Matrix / Boss Demo.
- Design reference pack already maps Lovevery, Lalo, Milton & Goose, Little Partners, Crate & Kids, Pottery Barn Kids, Nestig, Tender Leaf, Linear, Raycast, Stripe Atlas, Framer.
- Current site prototype has real products, routes, product data seed, PDP, cart drawer, and mobile QA screenshots.

What is not done well enough:

- Earlier designs mixed consumer website, AI Studio, design library, and boss demo into one surface.
- Several iterations became “warm DTC template” rather than a product-insight-driven Labebe site.
- Later radical AI concepts are valuable for separate AI Demo, but should not be inserted into the consumer website by default.
- Existing design work was not preceded by a complete product/channel intelligence map, so category hierarchy, hero SKU selection, and shopping paths were partly intuitive.

### 2.4 Existing AI / Video / Demo Assets

Source areas:

- `minimax-output/`
- `paperclip_labebe_demo_package/`
- `paperclip_runtime_duel/`
- `labebe-ai-design-studio/`

Current state:

- MiniMax prompt and one Wooden Mud Kitchen first-frame image exist.
- Paperclip / boss demo assets exist, but they belong to separate AI Demo workstream.
- No finalized video presentation pipeline for website design options.

Gaps:

- No reusable “design presentation video” script.
- No standard way to combine:
  - website screen recording;
  - click/scroll/hover scenes;
  - generated product lifestyle images;
  - MiniMax/Gemini video clips;
  - narration/audio;
  - subtitles;
  - before/after comparison.

## 3. Product Intelligence Workstream

### 3.1 Source Strategy

Use a tiered source plan.

| Tier | Source | Usage |
|---|---|---|
| T1 | Labebe official independent site | Product master, brand-owned facts, images, PDP copy, price shown on site |
| T1 | Amazon official listing pages / Brand Store if accessible | Amazon title, listing copy, rating, review count, public rank/coupon/offer signals |
| T1/T2 | Amazon SP-API if credentials are available | Catalog item lookup, pricing/offers; seller-only constraints apply |
| T2 | Keepa / Keepa-derived rank data | BSR history, buy box, price/rank history; treat as external analytics source |
| T2 | Apify Amazon actors | Efficient structured extraction for listing/reviews/rank if actor output passes sample QA |
| T2 | Google / Amazon search result pages | ASIN discovery and competitor discovery; not final evidence without verification |
| T3 | Review text and community/manual observations | VOC and hypotheses; must preserve quote provenance |

Known external method notes:

- Amazon Product Pricing API can retrieve pricing and offer information, but is seller-oriented and credential-gated.
- Amazon Catalog Items v2022-04-01 includes catalog summaries and has release notes around sales-rank-related browse classification/display group fields, but access and returned data depend on SP-API authorization.
- Apify has specialized Amazon product/review/rank actors that accept ASINs or product URLs and return structured price, review, rank and image fields; actor quality must be validated per sample before full use.
- Keepa-style data is attractive for BSR and price/rank history, but must be treated as an external analytics source with documented limitations.

### 3.2 Target Product Intelligence Schema

Minimum product-level fields:

| Group | Fields |
|---|---|
| Identity | `labebe_slug`, `canonical_title`, `raw_title`, `collection`, `product_url`, `status`, `last_seen_at` |
| Pricing | `site_current_price`, `site_compare_at_price`, `site_discount`, `amazon_price`, `coupon`, `currency`, `price_last_seen_at` |
| Onsite demand signal | `site_review_count`, `site_badges`, `site_sort_position_by_collection` |
| Amazon identity | `asin`, `amazon_url`, `amazon_title`, `brand`, `seller`, `fulfilled_by`, `variation_parent_asin`, `variation_attributes` |
| Amazon demand signal | `amazon_rating`, `amazon_review_count`, `bsr_primary_category`, `bsr_primary_rank`, `bsr_subcategory_ranks`, `rank_history_30d/90d` if available, `bought_past_month` if visible |
| Reviews/VOC | `review_count_scraped`, `rating_distribution`, `top_positive_themes`, `top_negative_themes`, `verified_purchase_ratio`, `review_quote_ids` |
| PDP detail | `description`, `bullets`, `dimensions`, `materials`, `age_guidance`, `certifications`, `assembly_care`, `faq`, `warnings`, `unknown_fields` |
| Media | `main_image`, `gallery_count`, `image_roles`, `video_present`, `a_plus_present`, `lifestyle_image_count`, `infographic_count` |
| Design relevance | `hero_candidate_score`, `visual_distinctiveness`, `category_anchor`, `room_scene_potential`, `gift_scene_potential`, `video_story_potential` |
| Evidence | `source_ids`, `confidence`, `notes`, `scrape_method`, `errors` |

### 3.3 Sample-First Method

Do not start with all products. Run a controlled sample first.

Suggested sample SKUs:

1. `pink-unicorn-plush-rocker`  
   Reason: highest onsite review count, strong gift/visual anchor, rocker category.
2. `cream-wooden-play-kitchen-set-with-storage`  
   Reason: pretend-play anchor, strong visual scene and short-video potential.
3. `foldable-learning-tower-montessori-kitchen-tower-log-color`  
   Reason: kitchen participation, parent utility, Amazon/search likely category.
4. `natural-wood-montessori-shelf-with-storage-boxes`  
   Reason: playroom/order story, room-builder relevance.
5. `activity-cube-baby-push-walker` or existing Amazon ASIN sample `B087P9SXZQ`  
   Reason: already has Amazon review sample; can validate Amazon review pipeline.

Sample run objectives:

- Verify ASIN discovery workflow.
- Compare at least three Amazon data extraction methods:
  - direct/manual Amazon page extraction for one ASIN;
  - existing Apify review actor;
  - Apify product/rank actor or Keepa path if available.
- Confirm field coverage and failure rate.
- Produce a sample product dossier for each SKU.
- Write crawler lessons learned before full parallel run.

### 3.4 Method Comparison Matrix

| Method | Best For | Weakness | Decision Gate |
|---|---|---|---|
| Labebe Playwright scrape | Official product universe and images | Current script only list-level; title parsing dirty | Keep; upgrade PDP extraction |
| Amazon direct page scrape | Public visible listing facts, ASIN discovery validation | Anti-bot, changing DOM, rate limits, localization | Use only for sample/manual fallback |
| Apify Amazon reviews actor | Review text/VOC at scale | Cost, actor output variability, incomplete reviews | Already viable for sample; QA required |
| Apify product/rank actors | Product listing, price, BSR/rank, image, review count | Actor-specific reliability/cost | Test on 5 sample ASINs before full run |
| Keepa API/path | Price/rank history and BSR | Requires key/cost; field interpretation limitations | Preferred for rank history if available |
| Amazon SP-API | Catalog/pricing/offers with official API | Credential and seller access constraints | Use if credentials exist; not blocker |
| SERP/search scraping | ASIN discovery and competitor leads | Weak evidence; duplicates/noise | Use only for discovery, then verify |

### 3.5 Full Parallel Run

Parallelization should start only after sample acceptance.

Work partition:

- Batch A: independent-site PDP enrichment for all 46 SKUs.
- Batch B: ASIN discovery and Amazon listing verification.
- Batch C: Amazon review scrape for matched ASINs.
- Batch D: Amazon rank/price/sales proxy scrape.
- Batch E: competitor ASIN discovery by product category.
- Batch F: image role classification and visual asset audit.

Agent strategy:

- Codex owns plan, schema, QA, data merge, Pro packet, maint skill updates.
- `claudeminmax` handles long-running extraction worker tasks after sample method is frozen.
- MiniMax/Gemini video generation is not part of product intelligence crawl; it is a later design-presentation workstream.

## 4. Website Design Research Workstream

### 4.1 Product-Driven Design Inputs

Design decisions must be grounded in the product intelligence outputs:

- Product family breadth: rockers, furniture, pretend play, activity toys, outdoor play, storage.
- Strong SKU anchors: products with review count, high visual distinctiveness, strong Amazon signals.
- Weak or under-explained SKUs: products with low reviews but strong visual/room potential.
- Category-level differences between independent site and Amazon performance.
- VOC patterns: gift satisfaction, assembly issues, stability/safety anxiety, size/space constraints, aesthetics, child engagement, durability, missing parts.
- Media asset readiness: which products already have strong lifestyle images, which need AI-generated scenes or new photography.

### 4.2 Design Research Questions

1. What should Labebe be positioned as after seeing its full product universe?
2. Which product lines deserve first-screen status?
3. Should navigation be primarily by category, age, room, occasion, problem, or story?
4. Which Amazon VOC themes should reshape PDP copy and buying guidance?
5. Which products are best for short-video storytelling?
6. Which design references map to which product lines?
7. What should be deliberately avoided because it looks generic or unsupported?

### 4.3 Design Option Deliverables

Each design option must include:

- one-sentence positioning;
- visual mood;
- homepage structure;
- collection/PDP structure;
- mobile path;
- product families emphasized;
- conversion mechanism;
- required assets;
- risks and why it might fail.

Minimum options:

1. **Growth-Space Home Brand**  
   Labebe as children’s growth-space brand; room/routine/product family design.
2. **Gift and Milestone Commerce**  
   First birthday, baby shower, grandparent gift, holiday gifting; strong product cards and gift finder.
3. **Room Builder / Playroom Reset**  
   Product sets organized by room problems and lifestyle scenes; strong Pinterest/SEO fit.
4. **Pretend Play Editorial Magazine**  
   Kitchens, shops, laundry, outdoor sensory play as story worlds; strong video/content fit.
5. **Product Theater / High-Impact Hero**  
   More daring interaction-focused homepage for decision-maker demo; still consumer-clean.

## 5. Website Design Presentation Video Concept

The presentation should not be a static slide deck only. Use a hybrid video:

1. **Opening: current state problem**
   - Show current Labebe/product grid or current prototype weakness.
   - Narration: “We cannot design the site before understanding the product system.”
2. **Product intelligence wall**
   - Animate 46 products into category clusters.
   - Overlay Amazon/onsite demand signals.
3. **Design strategy fork**
   - Show 4-5 design option cards with different visual directions.
4. **Simulated user journey**
   - Screen recording of website mock:
     - mobile visitor enters from gift intent;
     - selects age/occasion;
     - sees recommended products;
     - opens PDP;
     - watches short video/story module;
     - adds to cart or bundle.
5. **Visual enhancement layer**
   - Use generated lifestyle images or short clips for hero/product scenes.
   - Use MiniMax for video/audio where product story benefits from motion.
6. **Decision close**
   - Show which option is recommended and why.
   - Show which assets need real photography vs AI concept.

Technical approach:

- Use Playwright/Chrome to record deterministic site walkthroughs.
- Use CSS/Framer/GSAP/Rive-style motion for clicks, route transitions, product cards, filters.
- Use MiniMax or Gemini video for product/lifestyle concept clips only where helpful.
- Use image generation for hero scenes or room backgrounds, but keep product facts and claims source-backed.
- Use FFmpeg to assemble:
  - screen recording;
  - generated video clips;
  - voiceover/audio;
  - subtitles;
  - chapter labels.

## 6. Skill / Maint Work

Create or update a reusable skill after sample run:

Suggested skill name:

`labebe-amazon-product-intel`

Scope:

- product master schema;
- Labebe independent-site scrape upgrade notes;
- Amazon ASIN discovery workflow;
- Amazon review/listing/rank extraction options;
- field mapping and confidence rules;
- sample-first gate;
- parallel batch instructions for Claude/Minimax;
- output validation checklist;
- common failures and fixes;
- legal/ethical/source-provenance cautions.

Where to record:

- Skill body in shared skills or project-specific skill location after sample proof.
- Maint log under `/vol1/maint/docs/`.
- Commit after the sample methodology is validated, not before.

Maint notes must include:

- which methods were tested;
- cost/rate/quality observations;
- fields each method reliably returns;
- failure modes;
- recommended default path;
- fallback path;
- forbidden shortcuts.

## 7. Acceptance Criteria

### 7.1 Product Intelligence Acceptance

Sample phase passes only if:

- 3-5 SKU dossiers are produced.
- Each dossier includes independent-site facts, Amazon match status, source IDs, images, review/VOC if available, rank/sales proxy status, unknown fields.
- ASIN match confidence is explicit.
- At least two Amazon extraction methods are compared or a documented reason explains why not.
- Review extraction includes dedupe and quote provenance.
- Method lessons are written before parallelization.

Full phase passes only if:

- All 46 independent-site products are present in master table.
- Every product has either Amazon match, no-match, or needs-manual-review status.
- Every Amazon-matched product has listing facts and at least one demand signal: review count/rating, rank/BSR, bought-past-month, or documented unavailable.
- All extracted claims are source-tagged.
- No design-facing claim depends on unsupported data.

### 7.2 Design Research Acceptance

Passes only if:

- Design options are derived from product/category/customer evidence, not just aesthetics.
- At least 4 different website design concepts are shown.
- Each option includes desktop/mobile, homepage/PDP/collection implications.
- Design references are mapped with borrow/avoid/Labebe translation.
- One recommended direction and one fallback direction are stated.
- Presentation video plan is executable with assets, scenes, and recording steps.

### 7.3 Pro Review Acceptance

Pro review is useful only if:

- Pro receives this full context, not a bare question.
- Pro is asked to critique both product intelligence methodology and design-prework logic.
- Follow-up questions, if any, include the prior Pro answer and current local constraints.
- No new Pro conversation is opened without attaching full context.

## 8. Implementation Plan

### Phase 0: Planning and Pro Review

Outputs:

- This master plan.
- Source registry.
- Current-state gap map.
- Sample task brief for `claudeminmax`.
- Pro review prompt and attachment pack.

Decision gate:

- User裁决 after Pro feedback and my synthesis.

### Phase 1: Product Intelligence Sample

Duration target: 1-2 days after approval.

Steps:

1. Clean current Labebe product CSV into canonical product master.
2. Enrich 3-5 independent-site PDPs.
3. Discover Amazon ASINs for sample SKUs.
4. Run review/listing/rank extraction on sample ASINs.
5. Compare extraction methods.
6. Produce sample dossiers and method lessons.
7. Draft skill notes.

Gate:

- Only parallelize if sample dossier quality is accepted.

### Phase 2: Full Product Intelligence Run

Duration target: 3-5 days depending on Amazon source reliability.

Steps:

1. Parallel independent-site PDP enrichment.
2. Parallel Amazon ASIN discovery and verification.
3. Parallel Amazon reviews/listing/rank extraction.
4. Merge and QA.
5. Category/product performance summary.
6. VOC and design implication summary.
7. Update skill and maint log.

### Phase 3: Design Strategy and Creative Options

Duration target: 2-3 days after initial product intelligence.

Steps:

1. Convert product intelligence into design inputs.
2. Revisit benchmark/reference pack.
3. Brainstorm and select 4-5 design options.
4. Produce static concept boards and key page wireframes.
5. Define video presentation storyboard.
6. Ask Pro for design critique if needed.

### Phase 4: User Decision

Outputs:

- Product intelligence summary.
- Design strategy options.
- Pro feedback synthesis.
- My recommendation and tradeoffs.

User裁决:

- Select final crawl scope, design direction, and presentation/video format.

## 9. Open Questions for Pro / User

1. Should Amazon intelligence prioritize official/low-risk sources even if coverage is lower, or use Apify/Keepa-style sources for speed and breadth?
2. What is the minimum Amazon match confidence required before a product is treated as Labebe-owned rather than reseller/related?
3. Should the first website design recommendation optimize for consumer conversion, boss wow, or balanced DTC credibility?
4. How many design options are enough before implementation: 4, 5, or more?
5. For the presentation video, should it be a polished narrated artifact or a rough interactive walkthrough first?

