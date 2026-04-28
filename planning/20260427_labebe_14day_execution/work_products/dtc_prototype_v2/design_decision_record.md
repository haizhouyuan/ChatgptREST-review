# Labebe DTC Prototype v2.1 — Design Decision Record

Generated: 2026-04-27
Owner: Codex main controller
Implementation path: `labebe-gemini-demo/`

## Decision

The consumer website is now treated as a pure Labebe independent-store
replacement. It does not expose Paperclip, AI Studio, growth workflow, or
internal claim-gate UI to shoppers.

## Design Thesis

The previous iterations failed because they looked like narrow, generic,
centered product grids. This version uses a **Room-first Commerce** model:

- parents enter by room, age, gift occasion, and play scenario;
- the hero behaves like a product theater, not a static catalog banner;
- the catalog is organized into shopper missions and worlds;
- PDPs keep price, room fit, age path, supported review count, bundles, and
  practical objections close to the purchase decision;
- unsupported claims remain out of copy.

## What Changed In Code

| Area | Change |
| --- | --- |
| Homepage | Rebuilt around hero product theater, shopper mission cards, guided finder, room planner, collection worlds, best-seller signal section, and PDP strategy preview. |
| Navigation | Shifted primary nav to Shop by Room, Shop by Age, Gifts, Play Worlds, Storage. |
| Product data | Added the high-ticket writing desk SKU from the local scrape and copied its catalog image into public assets. |
| Mobile | Reworked hero flow to avoid overlap; PDP mobile now shows product image before purchase details. |
| QA tooling | Added CDP screenshot capture script so mobile screenshots use real device metrics instead of misleading Chrome CLI crop behavior. |
| Commerce flow | Added shared cart state, real cart drawer, add-to-cart PDP action, quantity controls, subtotal, and gift pairing. |
| Copy | Replaced internal design-review language with consumer-facing shopping language on the homepage and collection note. |

## Explicit Non-Goals

- No AI demo inside this consumer site.
- No Paperclip workflow inside this consumer site.
- No fake reviews, star ratings, awards, certifications, or marketplace sales claims.
- No full Amazon performance claims until ASIN identity mapping is complete.

## Current Prototype URL

Local/Tailscale candidate while preview server is running:

`http://100.124.54.52:8790/`

Local:

`http://127.0.0.1:8790/`

## Remaining Design Risks

- The site still uses mostly catalog imagery; a final production-quality site
  needs rights-cleared lifestyle/photo/video assets.
- PDP source capture is now complete for the 8-SKU source sample, but extracted
  dimensions, materials, warnings, assembly, and care references remain in a
  manual claim-review queue before public use.
- Cart drawer is implemented as a prototype interaction; checkout remains a
  non-integrated CTA without payment/shipping backend.
- The visual direction is stronger than the rejected beige centered version, but
  still needs another creative pass if the target is "award-level" rather than
  "credible DTC prototype."
