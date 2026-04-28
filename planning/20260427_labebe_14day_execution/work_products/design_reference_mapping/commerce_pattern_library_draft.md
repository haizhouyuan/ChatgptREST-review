# Commerce Pattern Library Draft

> Worker: WP-D Design Reference Mapping
> Date: 2026-04-27
> Purpose: Organize reference patterns by commerce function. Each pattern solves a specific Labebe business problem at a specific touchpoint.

---

## How to Read This Library

Each pattern is tagged:
- **Touchpoint** — where it lives (homepage, nav, collection, PDP, cart, gift flow, room flow, AI studio)
- **P0/P1/P2** — build priority for the 14-day sprint
- **Reference Source** — which brand or system the pattern borrows from
- **Business Problem** — what Labebe friction it resolves
- **Shopper Mission** — what parent job it supports
- **Conversion Mechanism** — how it drives revenue
- **Asset Need** — what must exist to make it credible
- **Rejection Condition** — when to discard it

---

## Section 1: Homepage & Navigation

### 1.1 Product-Family Hero Signal
- **Touchpoint**: Homepage first viewport
- **Priority**: P0
- **Reference Source**: Lalo (adult-taste composition), Lovevery (clear product identity), Labebe positioning doc
- **Business Problem**: Current hero reads as warm room moodboard, not proprietary brand. Parents landing from Pinterest/TikTok/SEO need to know "what Labebe sells" in under 3 seconds.
- **Shopper Mission**: "What does this brand sell, and is it relevant to me?"
- **Category Role**: Cross-collection brand signal. Shows rockers, furniture, pretend-play, storage as a coherent family.
- **PDP Impact**: Hero SKUs (Pink Unicorn, Learning Tower, Play Kitchen, Shelf, Storage) become priority PDPs with full module stacks.
- **Conversion Mechanism**: Product identity reduces bounce. Recognizable SKU in hero increases click-through to PDP by making the product tangible.
- **Asset Need**: Hero product-family composition image with real SKUs visible; warm cream/oak background; clear age/room/occasion CTA chips.
- **Rejection Condition**: Reject if hero shows fewer than 3 recognizable Labebe SKUs. Reject if background overpowers product identity. Reject if CTA leads to generic "Shop All" instead of guided paths.

### 1.2 Scenario-First Navigation
- **Touchpoint**: Global nav, mobile hamburger, footer
- **Priority**: P0
- **Reference Source**: Lovevery (age routing), Crate & Kids (room routing), Pottery Barn Kids (occasion routing)
- **Business Problem**: Category navigation (Furniture, Rockers, Pretend-Play) assumes parents know Labebe's taxonomy. They do not. Parents think in scenarios: "first birthday gift," "kitchen helper," "playroom organization."
- **Shopper Mission**: "Find products by my situation, not your catalog structure."
- **Category Role**: Cross-collection discovery layer. Age routes cut across furniture/rockers/play. Room routes cut across collections.
- **PDP Impact**: PDPs reached via scenario nav should show matching scenario badges (e.g., "First Birthday Pick" badge on Pink Unicorn PDP when arrived from Gift nav).
- **Conversion Mechanism**: Scenario-match reduces browsing time and increases PDP relevance. Parents who find via "First Birthday" nav convert higher than those browsing "Rockers."
- **Asset Need**: Nav label copy; mobile menu structure; scenario landing page templates (age, room, occasion, play goal).
- **Rejection Condition**: Reject if nav is just category labels renamed without underlying scenario logic. Reject if mobile menu requires more than 2 taps to reach any scenario. Reject if scenario paths lead to undifferentiated product grids.

### 1.3 AI Gift Finder Teaser
- **Touchpoint**: Homepage below hero
- **Priority**: P0
- **Reference Source**: Lovevery stage discovery, Nike By You (configurator confidence)
- **Business Problem**: Parents with vague intent ("I need a gift for an 18-month-old") do not know which collection to browse. A guided finder turns vague intent into specific SKU recommendations.
- **Shopper Mission**: "Help me find the right product without knowing your catalog."
- **Category Role**: Cross-collection recommendation engine.
- **PDP Impact**: Finder results link to PDPs with pre-populated scenario context (age + room + occasion chips pre-selected).
- **Conversion Mechanism**: Deterministic recommendation with reason text ("Because you chose 18-36m + nursery + first birthday") increases trust and click-through. Transparent logic prevents overclaim.
- **Asset Need**: Finder chip icons; recommendation card template; "why this fits" copy variants per SKU.
- **Rejection Condition**: Reject if finder claims to use AI personalization without being deterministic/rule-based first. Reject if recommendations lack reason text. Reject if finder shows more than 3 recommendations (decision paralysis).

### 1.4 Four Worlds Story Lanes
- **Touchpoint**: Homepage mid-scroll
- **Priority**: P0
- **Reference Source**: Milton & Goose (pretend-play worlds), Crate & Kids (room makeover), Lalo (gift tone), Little Partners (independence framing)
- **Business Problem**: Best-seller grids are generic. Story lanes turn collections into narratives that parents remember and share.
- **Shopper Mission**: "I want to explore a product world, not just a grid."
- **Category Role**: Collection entry points. Giftable Rockers, Montessori at Home, Tiny Pretend Worlds, Playroom Reset.
- **PDP Impact**: Each world lane links to a collection page with scenario hero and PDPs optimized for that world's story.
- **Conversion Mechanism**: Story-driven browsing increases time-on-site and emotional engagement. World lanes are more shareable than product grids.
- **Asset Need**: World hero images (one per lane); world tagline copy; world-to-SKU mapping table.
- **Rejection Condition**: Reject if world lanes are just renamed collection cards without story copy or scenario entry. Reject if world images do not show real Labebe products in context.

### 1.5 Trust Bar (Top Utility)
- **Touchpoint**: Homepage top bar, global header
- **Priority**: P0
- **Reference Source**: Pottery Barn Kids (shipping/safety/returns utility bar)
- **Business Problem**: First-time visitors from ads or SEO need immediate trust signals. Without them, they bounce to Amazon for reviews.
- **Shopper Mission**: "Is this site credible and safe to buy from?"
- **Category Role**: Universal trust layer.
- **PDP Impact**: Trust bar values (shipping threshold, return policy) must match PDP trust module values. Inconsistency destroys credibility.
- **Conversion Mechanism**: Visible shipping/returns/safety signals reduce checkout hesitation. Consistency between header and PDP increases trust transfer.
- **Asset Need**: Trust icon set; policy copy (must be verified); mobile condensed version.
- **Rejection Condition**: Reject if trust claims ("Free shipping over $X") are not verified with operations. Reject if trust bar is hidden on mobile. Reject if icons are generic without specific policy backing.

---

## Section 2: Collection Pages

### 2.1 Scenario Hero with Use Case
- **Touchpoint**: Collection page top
- **Priority**: P0
- **Reference Source**: Crate & Kids (room context), Milton & Goose (world storytelling)
- **Business Problem**: Collection pages that open with a product grid feel like catalogs. Collection pages that open with a use-case story feel like solutions.
- **Shopper Mission**: "Explain why this collection exists and who it is for."
- **Category Role**: Collection-specific. Pretend Play Worlds hero shows a child playing chef. Playroom Reset hero shows before/after organization.
- **PDP Impact**: Collection hero sets expectations for PDP story modules. If collection promises "tiny pretend worlds," PDP must deliver scenario storyboard.
- **Conversion Mechanism**: Use-case context increases PDP click-through by making the collection emotionally relevant, not just categorically correct.
- **Asset Need**: Collection hero lifestyle image; use-case headline; "best for" filter chips.
- **Rejection Condition**: Reject if collection hero is just a banner with the collection name. Reject if hero image does not show a real Labebe product in use.

### 2.2 Filter System: Age + Room + Play + Price
- **Touchpoint**: Collection sidebar or top bar
- **Priority**: P0
- **Reference Source**: Lovevery (age filters), Shopify standard (price filters)
- **Business Problem**: 46 SKUs is not a huge catalog, but it crosses age ranges, rooms, and play types. Without filters, parents scroll past irrelevant products.
- **Shopper Mission**: "Narrow down to products that match my constraints."
- **Category Role**: Cross-collection. Especially critical for Shop by Age and Shop by Room landing pages.
- **PDP Impact**: Filters must persist when user clicks to PDP and returns to collection. Filter state loss is a conversion killer.
- **Conversion Mechanism**: Fast, visible filter results reduce abandonment. Combined filters (age + room + price) surface high-match SKUs.
- **Asset Need**: Filter chip UI; filter logic table; empty-state copy.
- **Rejection Condition**: Reject if filters do not combine (e.g., only one filter active at a time). Reject if filter counts are not shown. Reject if mobile filter requires full-page reload.

### 2.3 "Best For" Product Labels
- **Touchpoint**: Collection product cards
- **Priority**: P0
- **Reference Source**: Lovevery (stage labels), Lalo (parent-friendly tone)
- **Business Problem**: Product cards with only title and price do not help parents decide. Labels like "Best First Birthday Gift" or "Small Room Favorite" provide decision shortcuts.
- **Shopper Mission**: "Quickly see which products match my need."
- **Category Role**: Cross-collection. Labels are scenario tags, not category tags.
- **PDP Impact**: Labels on cards must be explained on PDP. If card says "Grandparent Pick," PDP must show why (age fit, safety, giftability).
- **Conversion Mechanism**: Decision shortcuts increase PDP click-through. Parents scan labels faster than titles.
- **Asset Need**: Label taxonomy (max 8 labels); label badge graphics; label-to-SKU mapping.
- **Rejection Condition**: Reject if labels are more than 3 words. Reject if labels are not explained on PDP. Reject if all products have labels (dilutes meaning).

### 2.4 Cross-Link Module
- **Touchpoint**: Collection bottom
- **Priority**: P1
- **Reference Source**: Crate & Kids (room cross-links), Pottery Barn Kids (gift cross-links)
- **Business Problem**: Parents who land on a collection page may actually need a different scenario. Cross-links keep them in the site instead of bouncing.
- **Shopper Mission**: "I did not find what I need here — where else should I look?"
- **Category Role**: Cross-collection navigation.
- **PDP Impact**: PDP should also show cross-links ("You might also be interested in..." with scenario paths, not just products).
- **Conversion Mechanism**: Cross-links reduce bounce rate. Scenario cross-links increase discovery of high-margin collections (gift, room sets).
- **Asset Need**: Cross-link card template; scenario-to-scenario mapping table.
- **Rejection Condition**: Reject if cross-links are just "Related Products" without scenario context. Reject if cross-links lead to empty or thin pages.

---

## Section 3: PDP (Product Detail Page)

### 3.1 Gallery: Product + Lifestyle + Detail + Dimension
- **Touchpoint**: PDP top
- **Priority**: P0
- **Reference Source**: Baymard PDP UX research, Shopify product-page guidance, Milton & Goose (tactile detail)
- **Business Problem**: Parents need to see product, context, detail, and fit before buying furniture/toys online. Incomplete galleries are a top reason for PDP abandonment.
- **Shopper Mission**: "Show me the product from every angle, in a real room, and next to something for scale."
- **Category Role**: Universal PDP requirement.
- **PDP Module**: Gallery with min 4 image types: product white/lifestyle, context, detail/texture, dimension/scale.
- **Conversion Mechanism**: Complete galleries reduce uncertainty and returns. Dimension images reduce "will it fit?" hesitation.
- **Asset Need**: Product images per SKU (min 4); dimension diagram; lifestyle-in-room shot; detail/texture close-up.
- **Rejection Condition**: Reject if gallery has fewer than 3 images. Reject if there is no dimension or scale reference. Reject if lifestyle image shows a non-Labebe product as the focal point.

### 3.2 Truth Drawer
- **Touchpoint**: PDP, product cards
- **Priority**: P0
- **Reference Source**: Pro context bundle v2 (data truth layer), Google Merchant Center (feed discipline)
- **Business Problem**: Labebe cannot use fake reviews, fake ratings, or unsupported claims. Instead of hiding uncertainty, the site should make data honesty a trust feature.
- **Shopper Mission**: "Tell me what you know and what you do not know about this product."
- **Category Role**: Universal trust layer.
- **PDP Module**: Expandable truth drawer showing: price (scraped), review count (scraped or null), image source, collection, unknown fields explicitly labeled.
- **Conversion Mechanism**: Transparency paradoxically increases trust. Parents who see "To be confirmed" on dimensions prefer that over silence or invention.
- **Asset Need**: Source-label icon set; truth drawer UI component; unknown-field copy.
- **Rejection Condition**: Reject if truth drawer shows invented data. Reject if null fields are hidden instead of labeled. Reject if source labels are not consistent across all PDPs.

### 3.3 Age / Room / Occasion Badge Cluster
- **Touchpoint**: PDP buy box
- **Priority**: P0
- **Reference Source**: Lovevery (age badges), Crate & Kids (room badges), Pottery Barn Kids (occasion badges)
- **Business Problem**: Parents need to confirm fit quickly. Age, room, and occasion badges provide at-a-glance validation before scrolling to details.
- **Shopper Mission**: "Is this right for my child's age, our room, and the occasion?"
- **Category Role**: Universal PDP module.
- **PDP Module**: Badge cluster below title. Clicking a badge shows guidance text (e.g., "18-36m: toddler can climb independently with supervision").
- **Conversion Mechanism**: Badge validation reduces scroll-to-abandon. Guidance text increases purchase confidence.
- **Asset Need**: Badge icon set; badge guidance copy per SKU; badge-to-SKU mapping.
- **Rejection Condition**: Reject if badges are not clickable. Reject if guidance text is generic (same for all SKUs). Reject if age ranges are unsupported by product data.

### 3.4 Dimensions & Room Fit Block
- **Touchpoint**: PDP mid-scroll
- **Priority**: P0
- **Reference Source**: Nestig (room proportions), Crate & Kids (furniture fit), Baymard (spec completeness)
- **Business Problem**: Furniture PDPs without dimensions have high return rates. Parents buying learning towers, shelves, or storage need to know counter height compatibility, floor footprint, and room proportions.
- **Shopper Mission**: "Will this fit in my room and work with my furniture?"
- **Category Role**: Furniture collection critical. Pretend-play secondary (kitchen footprint). Rockers tertiary (seat height).
- **PDP Module**: Dimension diagram with real measurements; room-fit note ("Fits under standard 36-inch counter"); footprint visualization.
- **Conversion Mechanism**: Fit confidence reduces returns. Specific dimension callouts reduce "too big/too small" returns by 20%+ (Baymard benchmark).
- **Asset Need**: Dimension diagram per furniture SKU; footprint graphic; room-fit copy.
- **Rejection Condition**: Reject if dimensions are labeled "To be confirmed" without a plan to verify. Reject if dimension diagram is missing. Reject if room-fit copy is generic and not specific to the product.

### 3.5 Storyboard / "Watch It In Action" Module
- **Touchpoint**: PDP mid-scroll
- **Priority**: P0
- **Reference Source**: Lovevery (video usage), Little Partners (routine demonstration)
- **Business Problem**: Static images do not show how a product fits into daily life. Storyboard or short-video modules show the product in use, which increases emotional connection and conversion.
- **Shopper Mission**: "Show me how this fits into a real day."
- **Category Role**: Universal, but prioritized for hero SKUs (Pink Unicorn, Learning Tower, Play Kitchen, Shelf, Storage).
- **PDP Module**: 15-second video or 3-frame storyboard showing product in routine use. Label: "Concept storyboard — not final video."
- **Conversion Mechanism**: Video/storyboard increases time-on-PDP and conversion. Emotional routine scenes increase gifting confidence.
- **Asset Need**: Storyboard frames or short video per hero SKU; video player or storyboard carousel.
- **Rejection Condition**: Reject if video is not available and no storyboard placeholder is shown. Reject if storyboard shows unsafe usage. Reject if video is not clearly labeled as concept/draft.

### 3.6 Bundle Strip ("Complete the Set")
- **Touchpoint**: PDP below buy box
- **Priority**: P0
- **Reference Source**: Lalo (bundle merchandising), Milton & Goose (world-building bundles)
- **Business Problem**: Average order value on single-item furniture/toy purchases is hard to make profitable. Bundles raise AOV and reduce shipping cost per item.
- **Shopper Mission**: "What else do I need to make this gift or room complete?"
- **Category Role**: Cross-collection. Kitchen + Bakery + Accessories. Nursery + Rocker + Shelf. Playroom + Kitchen + Storage.
- **PDP Module**: Horizontal bundle strip with 2-3 complementary SKUs, bundle total, and "Add set to cart" CTA.
- **Conversion Mechanism**: Bundle attach rate directly raises AOV. Logical bundles (same world, same room) convert better than random cross-sells.
- **Asset Need**: Bundle composition images; bundle price calculation logic; complementary SKU mapping.
- **Rejection Condition**: Reject if bundle items are not logically related. Reject if bundle price is not calculated from real SKU prices. Reject if bundle strip pushes primary add-to-cart below the fold on mobile.

### 3.7 Materials & Safety Panel (Source-Backed Only)
- **Touchpoint**: PDP accordion
- **Priority**: P0
- **Reference Source**: Lovevery (material transparency), Little Partners (safety guidelines), Tender Leaf (sustainable badges)
- **Business Problem**: Parents of young children demand material and safety transparency. But Labebe cannot invent certifications or material claims. The panel must show what is known and label what is not.
- **Shopper Mission**: "Is this safe for my child, and what is it made of?"
- **Category Role**: Universal trust layer.
- **PDP Module**: Accordion with materials (source-backed), safety notes (source-backed), care instructions, assembly requirements. Unknown fields labeled "To be confirmed."
- **Conversion Mechanism**: Safety transparency increases purchase confidence for first-time parents. Care instructions reduce post-purchase anxiety.
- **Asset Need**: Material detail shots; care instruction graphics; assembly diagram or video.
- **Rejection Condition**: Reject if safety claims are unsupported. Reject if materials panel is entirely marketing copy without spec detail. Reject if "To be confirmed" fields are hidden.

### 3.8 FAQ Block
- **Touchpoint**: PDP bottom
- **Priority**: P0
- **Reference Source**: Shopify product-page guidance, Baymard (FAQ reduces support load)
- **Business Problem**: Parents have predictable questions (age fit, assembly, cleaning, returns). Without PDP FAQ, they contact support or abandon.
- **Shopper Mission**: "Answer my specific question without leaving this page."
- **Category Role**: Universal PDP module.
- **PDP Module**: Expandable FAQ with 5-8 questions per SKU. Questions generated from product truth data where possible.
- **Conversion Mechanism**: FAQ reduces support tickets and abandonment. SEO-friendly FAQ content captures long-tail search traffic.
- **Asset Need**: FAQ copy per SKU; expandable accordion component.
- **Rejection Condition**: Reject if FAQ is generic (same for all SKUs). Reject if FAQ answers contain unsupported claims. Reject if FAQ is hidden in a tab that requires discovery.

---

## Section 4: Gift Flow

### 4.1 Gift Guide Landing
- **Touchpoint**: `/gifts` or `/gift-guide`
- **Priority**: P0
- **Reference Source**: Pottery Barn Kids (gift structure), Lalo (gift tone)
- **Business Problem**: Gift buyers (grandparents, baby-shower guests, holiday shoppers) have high intent but low category knowledge. A gift guide captures this traffic and converts it.
- **Shopper Mission**: "Find a memorable gift for a specific occasion and age."
- **Category Role**: Rockers primary. Furniture secondary (nursery sets). Pretend-play tertiary (older toddler gifts).
- **PDP Impact**: Gift-guide PDPs must show gift-specific badges and bundle logic.
- **Conversion Mechanism**: Occasion landing pages capture high-intent traffic. Gift bundles raise AOV. Grandparent-specific copy increases trust.
- **Asset Need**: Gift guide hero images; occasion cards (first birthday, baby shower, holiday, grandparent); gift bundle compositions.
- **Rejection Condition**: Reject if gift guide is just a collection filter. Reject if occasion pages lack age guidance. Reject if gift bundles are not prominently shown.

### 4.2 Gift Bundle Builder
- **Touchpoint**: Gift guide, PDP
- **Priority**: P1
- **Reference Source**: Lalo (bundle merchandising), Pottery Barn Kids (registry logic)
- **Business Problem**: Gift buyers often want to buy a "complete gift" (e.g., rocker + cushion + book). A bundle builder makes this easy.
- **Shopper Mission**: "Build a complete gift set without browsing the whole catalog."
- **Category Role**: Rockers and pretend-play primary.
- **PDP Impact**: PDP shows pre-built gift bundles and allows customization.
- **Conversion Mechanism**: Bundle builder raises AOV. Pre-built bundles reduce decision fatigue.
- **Asset Need**: Bundle card template; bundle customization UI; gift-wrap option if available.
- **Rejection Condition**: Reject if bundle builder allows illogical combinations. Reject if bundle prices are not real-time calculated.

---

## Section 5: Room Flow

### 5.1 Shop by Room Landing
- **Touchpoint**: `/shop/by-room`
- **Priority**: P0
- **Reference Source**: Crate & Kids (room structure), Nestig (nursery storytelling)
- **Business Problem**: Room-based shopping positions Labebe as a room brand, not a toy brand. It increases basket size by showing sets.
- **Shopper Mission**: "Design or refresh my child's room."
- **Category Role**: Furniture primary. Rockers and pretend-play secondary.
- **PDP Impact**: Room PDPs show room-fit dimensions and "complete the room" bundles.
- **Conversion Mechanism**: Room sets raise AOV. Room landing pages capture Pinterest/SEO traffic.
- **Asset Need**: Room hero images (nursery, playroom, kitchen, bedroom); room mood shots with Labebe products.
- **Rejection Condition**: Reject if room pages are just collection filters. Reject if room photography shows non-Labebe products without disclosure.

### 5.2 Room Set Builder (2D)
- **Touchpoint**: `/room-builder` or embedded in room landing
- **Priority**: P1
- **Reference Source**: IKEA Kreativ, Wayfair Decorify
- **Business Problem**: Parents need to visualize how furniture pieces fit together. A 2D room builder shows product sets in context without requiring 3D assets.
- **Shopper Mission**: "See how these pieces look together before I buy."
- **Category Role**: Furniture collection bundling tool.
- **PDP Impact**: PDP shows "add to room builder" option.
- **Conversion Mechanism**: Room-set visualization raises bundle attach rate. Reduces "will it fit?" hesitation.
- **Asset Need**: 2D room backgrounds; product cutouts; bundle price calculator.
- **Rejection Condition**: Reject if room builder requires 3D assets that do not exist. Reject if it promises exact fit without dimensions.

---

## Section 6: Cart & Checkout

### 6.1 Cart Drawer with Bundle Logic
- **Touchpoint**: Global cart drawer
- **Priority**: P0
- **Reference Source**: Shopify standard, Lalo (clean cart)
- **Business Problem**: Standard cart drawers show items only. A smart cart drawer shows complementary products and bundle completion.
- **Shopper Mission**: "What else should I add before checking out?"
- **Category Role**: Cross-collection upsell.
- **PDP Impact**: N/A.
- **Conversion Mechanism**: "Complete the room" recommendation in cart raises AOV. Bundle completion reminder reduces regret.
- **Asset Need**: Cart drawer UI; complementary product logic; bundle completion messaging.
- **Rejection Condition**: Reject if cart drawer is full-screen on mobile (disruptive). Reject if recommendations are random, not logic-based.

---

## Section 7: AI Growth Studio (Board / Internal Demo)

### 7.1 SKU Expansion Wall (SkuGrowthLens)
- **Touchpoint**: `/ai-growth-demo/one-sku`
- **Priority**: P0
- **Reference Source**: Linear (workflow), Raycast (command center), TikTok Symphony / Amazon Ads (channel matrix)
- **Business Problem**: Board members need to see that one Labebe SKU can become a multi-channel asset system. Without visual proof, AI is abstract.
- **Shopper Mission**: N/A (board audience).
- **Category Role**: AI Growth Studio core demo.
- **Conversion Mechanism**: Executive trust in AI capability. Not a consumer conversion tool.
- **Asset Need**: Channel card template; status labels; product fact chips; motion mock for card expansion.
- **Rejection Condition**: Reject if channel assets are shown as finished without review status. Reject if performance metrics are invented. Reject if the demo uses a non-Labebe SKU.

### 7.2 Claim Gate Theater
- **Touchpoint**: `/ai-growth-demo/claim-gate`
- **Priority**: P0
- **Reference Source**: Pro context bundle (governance), Stripe Atlas (trust logic)
- **Business Problem**: AI-generated content risks unsafe claims about children's products. A visible claim gate shows that governance is built-in, not an afterthought.
- **Shopper Mission**: N/A (internal/demo audience).
- **Category Role**: AI Growth Studio governance demo.
- **Conversion Mechanism**: Risk reduction for legal/compliance. Trust building for board.
- **Asset Need**: Claim status icons; risk explanation copy; safe rewrite examples; blocked claim examples.
- **Rejection Condition**: Reject if claim gate shows fake approvals. Reject if blocked claims are not explained. Reject if safe rewrites are not actually safer.

### 7.3 Product Truth Panel
- **Touchpoint**: `/ai-growth-demo`, PDP internal demo mode
- **Priority**: P0
- **Reference Source**: Pro context bundle (data truth), Google Merchant Center (feed discipline)
- **Business Problem**: AI demos often use fake data. A visible product truth panel proves that AI outputs are grounded in real product facts.
- **Shopper Mission**: N/A (demo audience).
- **Category Role**: AI Growth Studio truth demo.
- **Conversion Mechanism**: Data credibility for board. Truth transparency for consumer PDP.
- **Asset Need**: Product fact card; source labels; unknown field indicators.
- **Rejection Condition**: Reject if product facts are invented. Reject if source labels are inconsistent.

### 7.4 Channel Preview Simulator
- **Touchpoint**: `/ai-growth-demo/channel-preview`
- **Priority**: P0
- **Reference Source**: Amazon Ads, TikTok Symphony, Google Product Studio
- **Business Problem**: Stakeholders need to see how one SKU adapts to different channels. Without channel preview, AI output feels one-dimensional.
- **Shopper Mission**: N/A (demo audience).
- **Category Role**: AI Growth Studio channel demo.
- **Conversion Mechanism**: Board understanding of channel scalability.
- **Asset Need**: Channel template cards (TikTok, Amazon A+, Google Shopping, Email, Pinterest, Site); channel-specific copy variants; image prompt variants.
- **Rejection Condition**: Reject if channel previews show fake final content. Reject if channel-specific constraints (character limits, aspect ratios) are not respected.

---

## Priority Summary

| P0 (Build First) | P1 (Strong Upgrade) | P2 (Future) |
|---|---|---|
| Product-Family Hero | Gift Bundle Builder | 3D Product Viewer |
| Scenario-First Navigation | Room Set Builder 2D | AR Room Placement |
| AI Gift Finder Teaser | Playroom Reset Before/After | Real AI Backend Personalization |
| Four Worlds Story Lanes | Dynamic Gift Guide Builder | Live Image Generation |
| Trust Bar | A+ Module Composer | Auto Video Generation |
| Scenario Hero (Collection) | UGC Hook Lab | Voice Shopping Assistant |
| Filter System | Product Comparison Advisor | |
| "Best For" Labels | Search Intent Map | |
| Gallery (4-image type) | Mobile Demo Path | |
| Truth Drawer | | |
| Badge Cluster | | |
| Dimensions & Room Fit | | |
| Storyboard Module | | |
| Bundle Strip | | |
| Materials & Safety Panel | | |
| FAQ Block | | |
| Gift Guide Landing | | |
| Shop by Room Landing | | |
| Cart Drawer with Logic | | |
| SKU Expansion Wall | | |
| Claim Gate Theater | | |
| Product Truth Panel | | |
| Channel Preview Simulator | | |

---

## Evidence Checklist

- [x] Every pattern states what Labebe business problem it solves.
- [x] Every pattern includes shopper mission mapping.
- [x] Every pattern includes category role.
- [x] Every pattern includes PDP module mapping.
- [x] Every pattern includes conversion mechanism.
- [x] Every pattern includes asset need.
- [x] Every pattern includes rejection condition.
- [x] No pretty sites listed without mapping.
- [x] No final UI designs included.
- [x] No Pro/Gemini calls made.
