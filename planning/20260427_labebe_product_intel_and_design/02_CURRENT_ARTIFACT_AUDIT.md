# Current Artifact Audit

Date: 2026-04-27

This audit separates "already produced" from "good enough to drive the next website rebuild." The current problem is not lack of artifacts. The problem is that many artifacts are partial, mixed-scope, or not connected to a reliable product intelligence layer.

## 1. Independent-Site Product Crawl

Relevant files:

- `data/labebe/labebe_products.csv`
- `data/labebe/labebe_products_with_images.csv`
- `data/labebe/all_product_images.json`
- `data/labebe/images/`
- `docs/labebe-scrape-report-2026-04-24.md`
- `scrape_labebe.py`

What exists:

- 46 Labebe independent-site products.
- 46 product image galleries.
- 459 indexed image URLs.
- 460 local downloaded images.
- Collection split: furniture 17, rockers-ride-ons 13, pretend-play 9, activity-educational-toys 6, new-in 1.
- Price range: $33.99 to $179.99 in the local scrape.
- Onsite review-count leaders are identifiable.

What is not good enough:

- Product titles are dirty. Many titles include labels, prices, discounts, review counts, and `labebe` suffixes.
- The scrape is collection/listing-oriented, not PDP-intelligence-oriented.
- Missing fields include dimensions, materials, age guidance, certification claims, assembly/care, warnings, variants, FAQ, structured data, inventory and media roles.
- Product image galleries are not classified as product-only, lifestyle, dimension chart, infographic, close-up, packaging, assembly, or child-use scenes.
- The output cannot yet answer which product should own the homepage hero, which products deserve bundles, or which PDP claims are safe.

Audit judgment:

The independent-site crawl is a strong starting inventory, not a finished product intelligence dataset.

## 2. Amazon Data

Relevant files:

- `fetch_amazon_reviews_apify.py`
- `data/amazon_reviews_US_B087P9SXZQ.csv`
- `data/amazon_reviews_US_B087P9SXZQ.jsonl`

What exists:

- One sample ASIN: `B087P9SXZQ`.
- 13 deduplicated review rows in the current CSV sample.
- Review fields include rating, date, author, body, verified purchase, helpful votes, review URL, marketplace and scrape metadata.
- The script already supports star filters and sorting through an Apify review actor.

What is not good enough:

- There is no SKU-to-ASIN map for the 46 Labebe products.
- There is no Amazon listing extraction for product title, brand, seller, price, coupon, images, A+ content, variations, Prime/FBA, category, BSR or bought-past-month signals.
- There is no product rank or price history.
- There is no competitor ASIN set.
- There is no method comparison across Apify, direct page extraction, Keepa, SP-API or search-discovery paths.
- The single ASIN sample may not map to a current independent-site SKU without verification.

Audit judgment:

Amazon work is a method seed only. It cannot yet support website positioning, product prioritization, or sales-performance claims.

## 3. Website Design Research and Reference Packs

Relevant areas:

- `labebe_design_reference_pack/`
- `research/20260425_design_dtc_research_v2/`
- `research/20260425_website_design_dtc/`
- `pro_requests/20260425_*`
- `pro_requests/20260426_radical_design_brainstorm/`

What exists:

- Same-category references: Lovevery, Lalo, Milton & Goose, Little Partners, Crate & Kids, Pottery Barn Kids, Nestig, Tender Leaf.
- World-class web references: Linear, Raycast, Stripe Atlas, Framer.
- Design-system notes and motion guidelines.
- Multiple Pro review rounds identifying that earlier designs were not strong enough.

What is not good enough:

- Earlier website prototypes mixed three separate surfaces:
  1. pure Labebe DTC replacement site;
  2. AI growth/product-matrix demo;
  3. internal design library/boss demo.
- The newest user boundary is clear: the website should be a pure replacement Labebe consumer site. AI demos belong elsewhere.
- Existing designs often became warm, narrow, centered DTC pages with too little visual authority, weak product hierarchy, and insufficient product-driven structure.
- The reference pack has not yet been re-applied after a complete product/channel intelligence read.
- Existing design options are not different enough. They feel like variations of one safe direction.

Audit judgment:

The design research is useful but not decisive. It must be re-grounded in product intelligence and expanded into genuinely different creative options.

## 4. AI Demo, Paperclip, MiniMax and Video Assets

Relevant areas:

- `paperclip_labebe_demo_package/`
- `paperclip_runtime_duel/`
- `minimax-output/`
- `labebe-ai-design-studio/`
- `pro_requests/20260425_paperclip_labebe_demo_config_review/`

What exists:

- Separate AI demo thinking and Paperclip-related assets.
- MiniMax-oriented discussion and early generated media artifacts.
- Pro review material for AI demo configuration.

What is not good enough:

- These assets should not be injected into the consumer website by default.
- There is no finalized presentation-video pipeline for website design options.
- There is no standard storyboard combining real screen recording, generated lifestyle clips, narration, subtitles, and user-journey simulation.

Audit judgment:

AI demo assets are valuable for a second project. For the website project, they should only support presentation material or concept visuals, not become the site concept itself.

## 5. Key Lessons From Failed Website Iterations

1. Visual polish without product intelligence leads to generic pages.
2. A centered, narrow DTC layout can look tidy but weak at desktop scale.
3. Adding AI Studio modules into the consumer website confuses the job of the site.
4. Fake reviews, unverified claims, or placeholder imagery immediately reduce credibility.
5. "Warm Montessori" is not enough as a design idea. Labebe needs a stronger product-system expression.
6. The next design cycle must begin from product families, purchase intents, room/age/gift paths, Amazon VOC and visual asset readiness.

## 6. Required Reset

Before another implementation:

1. Build product intelligence sample dossiers.
2. Validate Amazon data method with a few SKUs.
3. Produce a complete product/category/current-state summary.
4. Re-ask design questions from product evidence.
5. Create multiple genuinely different design options.
6. Present website options with video/interaction mockups.
7. Keep the pure DTC website separate from AI demo work.
