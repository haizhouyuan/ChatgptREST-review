# Independent Site Growth Research: Labebe as a Sales and Learning Channel

## 1. Core Thesis

The independent site should not be treated as a static catalog. For Labebe it must perform eight commercial jobs:

1. Acquire traffic from SEO, Google Shopping, TikTok/Reels, Pinterest, email, influencers, Amazon cross-channel inserts, and B2B outreach.
2. Orient visitors into the Labebe product world.
3. Guide parents by age, room, occasion, play goal, and trust need.
4. Persuade on PDPs with media, price, fit, dimensions, safety/material facts if verified, assembly/care, FAQ, and reviews or review signals.
5. Convert through clear buy boxes, bundles, cart drawer recommendations, and gift/room sets.
6. Retain with email, gift reminders, product-use education, and follow-up content.
7. Learn from product clicks, questions, review signals, support questions, creative performance, and search terms.
8. Feed AI workflows with structured product truth and channel templates.

AI should improve these jobs. It should not sit beside the site as novelty.

## 2. Funnel Architecture

```text
Traffic source
  -> Landing page / collection / PDP
  -> Guided finder or room/gift route
  -> Product story and PDP evidence
  -> Bundle or cart drawer
  -> Checkout path
  -> Email / retargeting / post-purchase content
  -> VOC and creative-performance learning
  -> next product, content, and asset decisions
```

## 3. Traffic and Landing Strategy

| Source | Visitor Intent | Best Landing Page | AI Role |
|---|---|---|---|
| Google SEO | problem, product, or comparison search | guide page, collection, PDP | generate FAQ drafts from product truth and real support questions |
| Google Shopping | product comparison and price check | PDP | feed title, image, price, structured data, lifestyle image governance |
| TikTok/Reels | visual proof and inspiration | short landing page or PDP with video module | hooks, shot lists, storyboard, caption variants |
| Pinterest | room and gift inspiration | room guide, gift guide, product collection | room images, pin copy, seasonal boards |
| Email/SMS | warm audience | gift guide, bundle, new-in landing | segmented blocks by age/occasion |
| Amazon cross-channel | already product-aware | brand story, bundles, room sets | expand a single Amazon listing into Labebe world |
| B2B/daycare | spec and institutional confidence | classroom or bulk-buy page | structured spec sheet, FAQ, safety review checklist |

## 4. Page System

### Homepage

Jobs:

- establish Labebe as a children's growth-space brand;
- route by age, room, occasion, and story world;
- show high-signal real products;
- expose the AI Growth-Space Engine;
- send visitors to PDP, gift guide, room guide, or AI demo.

### Collection Pages

Jobs:

- explain the use case;
- compare product differences;
- support filters and internal links;
- increase PDP views and add-to-cart;
- support SEO through scenario content and FAQ.

### PDP

Jobs:

- answer whether the product is right for the child, room, budget, occasion, and parent goal;
- reduce uncertainty;
- create cross-sell and content reuse.

Required modules:

- gallery with product and lifestyle images;
- real price and review count where available;
- age, room, occasion, and play-goal badges;
- buy box and add to cart;
- video/storyboard module;
- dimensions and fit;
- materials/safety only when source-backed;
- assembly/care;
- bundle recommendation;
- FAQ;
- product truth drawer;
- channel asset preview in internal demo mode.

Baymard's ecommerce product-page UX research is useful here because it treats PDP experience as a major source of friction, especially when media, specs, reviews, or mobile usability are weak. Shopify's product-page guidance reinforces the same operational basics: product photos, visible CTA, reviews/social proof where real, descriptions, and mobile experience matter.

### Gift Guide

Jobs:

- capture first birthday, baby shower, holiday, and grandparent gift intent;
- organize by age and gift relationship;
- create email/Pinterest/social reuse.

AI role:

- generate gift-guide block drafts from real product data;
- produce channel-specific copy variants;
- label unknown product facts.

### Room Guide / Room Builder

Jobs:

- shift Labebe from "product seller" to "children's room and routine brand";
- increase multi-item basket potential;
- create Pinterest and SEO assets.

AI role:

- turn a room goal into a product set;
- generate scene prompts and before/after storyboards;
- show bundle price from real product data.

IKEA Kreativ and Wayfair Decorify show that AI room design is a recognizable consumer pattern. Labebe should start with a lightweight 2D room set builder using product cutouts and generated/styled room backgrounds, not a costly 3D room unless real assets exist.

### AI Growth Studio

Jobs:

- show decision makers how product data becomes growth assets;
- demonstrate governance and review workflow;
- connect product, content, channel, and feedback loops.

It should not replace the shopping site. It is an executive demo and internal operating surface.

## 5. Product Data and Structured Commerce

The site must maintain a product truth layer:

- slug;
- title;
- price;
- review count;
- product URL;
- image;
- collection;
- age range if supported;
- room tags;
- play tags;
- gift tags;
- data status;
- unknown fields.

Google's Product structured data and Merchant Center product data guidance matter because independent-site growth increasingly depends on machine-readable product facts. The demo should show this direction without outputting unsupported fields.

Recommended implementation:

- `products.ts` remains the product truth seed;
- add `productFacts.ts` or extend current schema with `source`, `lastVerified`, `unknownFields`, and `allowedClaims`;
- add a Product Truth Drawer to PDP and AI Studio;
- add a structured-data preview panel in internal demo mode.

## 6. Conversion System

### Product Card

Must show:

- image;
- title;
- real price;
- review count if available;
- age/room/gift tag;
- View Details;
- Quick Add only for simple choices.

### PDP

Must answer:

- age fit;
- room fit;
- dimensions;
- price and value;
- materials/safety if confirmed;
- assembly and care;
- what it pairs with;
- what scenario it supports;
- what content or channel assets can be built from it.

### Cart Drawer

Should add:

- bundle recommendation;
- gift accessory or complementary SKU;
- "complete the room" recommendation;
- claim-safe reason.

### Finder

Should be deterministic first:

- input: age, room, occasion, play goal;
- output: three SKUs, each with reason and source state;
- no hidden fake personalization;
- upgrade later to real AI once analytics and product facts are reliable.

## 7. AI Operating Model

```text
Product truth
  -> channel templates
  -> AI draft
  -> claim gate
  -> human review
  -> channel preview
  -> publish-ready asset
  -> performance and VOC capture
  -> next content/product decision
```

This is the operating model the board needs to see. The website should visualize it.

## 8. Metrics for the Real Site

Traffic:

- sessions by source;
- SEO landing pages;
- Google Shopping impressions/clicks;
- Pinterest saves/clicks;
- TikTok landing engagement;
- email click-through.

Commerce:

- PDP view rate;
- add-to-cart rate;
- cart-to-checkout rate;
- conversion rate;
- AOV;
- bundle attach rate;
- gift-guide conversion;
- room-guide conversion.

AI operations:

- assets generated per SKU;
- review-ready rate;
- blocked-claim rate;
- approval cycle time;
- asset reuse count;
- top creative angles;
- FAQ/product questions generated from real user behavior.

## 9. Implementation Implication

The next website sprint should not start with "make it prettier." It should start with a stronger commerce/growth architecture:

- product truth schema;
- finder recommendation engine;
- PDP story and trust modules;
- room/gift guide routes;
- one-SKU asset expansion;
- claim gate;
- channel preview simulator;
- boss presentation path.

Then visual polish, generated images, motion, and 3D/AR can sit on top.
