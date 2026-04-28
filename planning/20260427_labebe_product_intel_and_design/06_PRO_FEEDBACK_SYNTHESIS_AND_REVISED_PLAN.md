# Pro Feedback Synthesis and Revised Plan

Date: 2026-04-27

Pro job:

- Job id: `c33acc4b812e41cea92f4e317efad589`
- Conversation: https://chatgpt.com/c/69eef06f-4828-83e8-a318-286bd2b51b12
- Full answer: `pro_packet/pro_answer.md`

## 1. My Read

Pro's answer is strong enough. I do not think we need another Pro follow-up before asking the user to裁决. The response did not just repeat the plan; it identified the main missing layer:

> We know we should start from product evidence, but we have not yet defined how product evidence becomes design decisions.

I agree with this. The next version should not only say "crawl more data" and "make more design options." It must create a hard middle layer:

```text
product facts -> portfolio judgment -> design decision matrix -> IA/PDP/homepage choices -> design options
```

Without that layer, the website can still become a nicer warm children's template.

## 2. Pro's Main Critique

### 2.1 Correct Reset, But Not Sharp Enough

Pro agrees with the reset:

- pure Labebe DTC website and AI Demo must be separate;
- product/channel intelligence should come before website redesign;
- existing artifacts must be audited honestly;
- sample-first crawl is correct.

But Pro says the plan is still too process-heavy and not decision-heavy enough.

### 2.2 Missing Decision Model

Current plan lists many fields and many design options, but does not define:

- what evidence selects the hero SKU;
- what evidence decides primary navigation;
- what evidence decides PDP module order;
- what evidence chooses gift-first vs furniture-confidence vs room-builder;
- what evidence disqualifies a visually attractive option.

Required new deliverable:

- `design_decision_matrix.csv`
- `hero_candidate_matrix.csv`
- `navigation_decision_matrix.md`
- `pdp_module_strategy_by_category.md`

### 2.3 Product Intelligence Schema Must Be Expanded

Pro says the current schema is a good skeleton but insufficient.

Add DTC fields:

- product/variant IDs if extractable;
- availability;
- SEO/canonical/JSON-LD;
- breadcrumb and multi-collection membership;
- shipping/return/warranty signals;
- package/product dimensions and weight;
- assembly/care/manuals;
- age min/max and warning labels;
- onsite review text;
- PDP module order;
- payment/trust/CTA state;
- image alt text and image role classification.

Add Amazon fields:

- parent/child ASIN;
- variation theme;
- model/UPC/GTIN if visible;
- brand byline, brand store, seller, ships_from, sold_by, buy box;
- Prime/FBA/delivery/availability;
- current price/list price/coupon;
- rating distribution;
- review velocity;
- media review count;
- Q&A;
- A+ module map;
- product details;
- BSR category path;
- category-level competitor ASINs;
- Amazon content quality score.

Add design scoring fields:

- `demand_signal_score`
- `asset_readiness_score`
- `category_anchor_score`
- `pdp_fact_completeness_score`
- `review_voc_usefulness_score`
- `bundle_potential_score`
- `risk_score`
- `hero_eligibility_reason`
- `hero_disqualification_reason`

### 2.4 Sample Must Be 6-8 Stratified Products

Pro says my 3-5 sample is too biased toward attractive hero candidates. Revised sample should include both pretty products and data-problem products:

1. Pink Unicorn Plush Rocker.
2. Cream or Midnight Play Kitchen.
3. One Learning Tower variant, plus variant-family check.
4. One near-duplicate desk/chair furniture SKU.
5. One low/no-review but important product.
6. Existing Amazon ASIN `B087P9SXZQ`, but only after verifying which Labebe SKU it maps to.
7. One expected no-match Amazon product.
8. One slug/data mismatch sample, especially the `children-s-writing...` / `childrens-writing...` inconsistency.

This is the right correction. The sample must expose dirty data and ASIN matching risk, not just produce pretty dossiers.

### 2.5 Amazon Work Must Be Reordered

Pro says do not start with review scraping. Correct order:

1. ASIN identity and ownership verification.
2. Current listing facts.
3. Demand proxies.
4. Review/VOC, split by marketplace/language/date/star/verified status.
5. Competitor context.
6. Amazon content-gap analysis.

Critical warning:

- The current `B087P9SXZQ` sample has US marketplace metadata but includes Japanese review content.
- Therefore review data must be split by marketplace/language/source before VOC.

### 2.6 Design Options Must Be Architectural, Not Thematic

Pro says the original five options are too likely to become the same page grammar with different labels. It suggests reframing options as real website architectures:

1. **Gift-first Labebe**
   - first birthday, grandparent gift, baby shower, holiday;
   - strong rockers/push walkers/giftables.

2. **Home-fit Furniture Labebe**
   - dimensions, fit, stability, assembly, care, room context;
   - strong learning tower, desk, shelf, storage.

3. **Child-sized Worlds Labebe**
   - pretend kitchen, shop, laundry, garden, bakery, art corner;
   - story worlds and use-scene video.

4. **Playroom Reset Labebe**
   - storage, organization, room bundles, before/after;
   - strong shelf, bins, desk, room sets.

5. **Object-led Product Theater Labebe**
   - bold product-scale, scroll choreography, product-world transitions;
   - must remain pure DTC and cannot show AI Matrix.

I agree. These are better because each implies different IA, PDP logic, asset needs and conversion mechanism.

### 2.7 PDP Becomes Central

Pro explicitly says PDP is more important than homepage. Next design work must prioritize:

- dimensions;
- age;
- materials/safety claims with source;
- assembly/care;
- product differences;
- real images;
- mobile CTA;
- reassurance based on review/VOC;
- bundles/cross-sells.

This changes the implementation mindset: homepage is not the whole website design problem.

## 3. Revised Execution Plan

### Phase 0: Scope Purge and Data QA Baseline

Outputs:

- `scope_boundary.md`
- `current_data_qa.md`
- `product_master_v0.csv`
- `do_not_use_fields.md`

Gate:

- 46 products uniquely identified.
- CSV slugs, PDP URLs and image galleries join without silent loss.
- Unknown fields explicitly marked.
- AI demo language removed from pure DTC website inputs.

### Phase 1: DTC PDP Sample Enrichment

Sample:

- 6-8 stratified SKUs, not 3-5 attractive SKUs.

Outputs:

- `sample_product_dossiers/*.md`
- `pdp_facts_sample.csv`
- `image_role_sample.csv`
- `pdp_extraction_errors.csv`
- `field_coverage_report.md`

Gate:

- PDP facts, unknowns and source snippets recorded.
- Image roles classified.
- Safety/material/developmental claims are not used without source.

### Phase 2: Amazon Identity and Listing Sample

Outputs:

- `asin_candidates_sample.csv`
- `asin_match_scoring.md`
- `amazon_listing_facts_sample.csv`
- `method_comparison.md`
- `amazon_source_limitations.md`

Gate:

- Accepted/probable/candidate/rejected/no-match statuses.
- Parent/child ASIN and marketplace/language risk handled.
- Default full-run method chosen.

### Phase 3: Full Product and Channel Intelligence

Outputs:

- `product_master_v1.csv`
- `pdp_facts_full.csv`
- `image_roles_full.csv`
- `asin_match_full.csv`
- `amazon_listing_facts_full.csv`
- `reviews_voc_full.csv`
- `demand_proxy_full.csv`
- `competitor_asins_by_category.csv`
- `crawl_errors.csv`
- updated `source_cards.tsv`

Gate:

- All design-facing claims source-tagged.
- Review/VOC not mixed across marketplace/language.
- No Amazon signal used as direct sales proof.

### Phase 4: Insight Synthesis Before Visual Design

Outputs:

- `category_portfolio_map.md`
- `hero_candidate_matrix.csv`
- `navigation_decision_matrix.md`
- `pdp_module_strategy_by_category.md`
- `bundle_and_cross_sell_map.csv`
- `voc_to_pdp_reassurance.md`
- `asset_gap_list.md`

Gate:

- IA, hero strategy and PDP strategy approved before visual mockups.

### Phase 5: Divergent Website Concepts

Options:

1. Gift-first Labebe.
2. Home-fit Furniture Labebe.
3. Child-sized Worlds Labebe.
4. Playroom Reset Labebe.
5. Object-led Product Theater Labebe.

Required for each:

- positioning;
- target shopper;
- IA;
- homepage wire;
- collection wire;
- PDP wire;
- mobile journey;
- hero SKU rationale;
- conversion mechanism;
- required assets;
- risk;
- why it is not generic;
- what evidence supports it.

Gate:

- Select one primary and one fallback. Do not implement five complete sites.

### Phase 6: Prototype and Decision Video

Outputs:

- desktop key screens;
- mobile key screens;
- clickable prototype;
- 60-90s walkthrough for primary direction;
- 30s fallback walkthrough;
- evidence appendix;
- asset procurement list;
- implementation backlog.

Video structure:

1. Current problem.
2. Product intelligence wall.
3. Chosen design strategy.
4. Gift shopper path.
5. Furniture/spec shopper path.
6. Room/bundle shopper path.
7. PDP proof.
8. Mobile proof.
9. Decision and next build scope.

Gate:

- Video cannot be stronger than the prototype itself.
- AI-generated media must be marked as concept.

### Phase 7: Implementation Backlog

Outputs:

- P0 launch scope;
- P1 asset/content scope;
- PDP component spec;
- collection/filter spec;
- mobile sticky buy box spec;
- SEO/schema/Merchant Center tasks;
- analytics event map;
- QA checklist;
- copy-claims approval list;
- photography/video/AI concept asset plan.

Gate:

- P0 must be a real DTC replacement path, not an AI demo.

## 4. Changes I Will Make To The Working Plan

I will treat Pro's critique as accepted unless the user裁决 otherwise:

1. Expand sample from 3-5 to 6-8 stratified SKUs.
2. Add data integrity QA before Amazon work.
3. Add ASIN scoring before review scraping.
4. Add design decision matrix before visual design.
5. Replace old design option names with five architecture-level options.
6. Move PDP strategy ahead of homepage polish.
7. Keep presentation video, but make it a business decision walkthrough, not a cinematic mood film.
8. Keep AI Demo/Paperclip/Product Matrix separate from the pure DTC website.

## 5. Decision Points For User

These are the remaining questions that materially affect execution:

1. Amazon-side sources available:
   - Apify token only?
   - Keepa available?
   - SP-API available?
   - Or start with manual/direct validation first?

2. Real website target:
   - existing Shopify/independent site retrofit?
   - or React/Vite high-fidelity prototype first?

3. Primary business goal for the DTC redesign:
   - gift conversion;
   - furniture/learning-tower trust conversion;
   - room/bundle AOV;
   - brand premium rebuild;
   - or a ranked combination.

4. Product assets available beyond current scrape:
   - real photography;
   - Amazon A+ assets;
   - manuals;
   - packaging photos;
   - UGC;
   - video clips.

## 6. My Recommendation

Proceed with the revised plan up to Phase 4 before any new website implementation.

The most important next executable step is:

```text
Phase 0 + Phase 1 sample
= data QA baseline
+ 6-8 SKU DTC PDP enrichment
+ ASIN candidate discovery only after data integrity is repaired
```

After that, we can safely decide which design architecture is justified. Without that, another visual iteration will likely repeat the same failure in a better-looking form.
