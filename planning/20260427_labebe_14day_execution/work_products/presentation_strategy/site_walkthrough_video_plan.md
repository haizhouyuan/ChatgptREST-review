# Labebe DTC Site Walkthrough Video Plan

Generated: 2026-04-27
Owner: Presentation Strategy Worker
Scope: pure Labebe DTC website replacement only

## Purpose

Produce a short, credible walkthrough that sells the Labebe independent-store
redesign as a better consumer commerce experience. This video must not explain
Paperclip, AI workflow, Claim Gate internals, or runtime evidence. Those belong
to the separate Boss Gallery package.

The viewer should understand three things in under 90 seconds:

1. Labebe is no longer presented as a flat product grid.
2. Parents can shop by room, age, gift occasion, play world, and PDP evidence.
3. The prototype is mobile-aware and commerce-led, while remaining claim-safe.

## Current Inputs

| Input | Path / URL | Use |
| --- | --- | --- |
| DTC prototype v2 | `https://yogas2.tail594315.ts.net:10000/` | Primary external review surface while server and Tailscale Funnel are live. |
| Local DTC route map | `work_products/dtc_prototype_v2/route_map.md` | Route coverage and smoke-tested URLs. |
| Design record | `work_products/dtc_prototype_v2/design_decision_record.md` | Narrative spine: Room-first Commerce. |
| Browser QA report | `work_products/dtc_prototype_v2/browser_qa_report.md` | Build, route, screenshot and overflow evidence. |
| Commerce decision layer | `work_products/commerce_decision_layer/` | Shopper missions, claim permissions, PDP module strategy. |
| QA screenshots | `qa/labebe-commerce-v2/` | Evidence and still-frame fallback. |

Known current screenshots:

- `home-design-gift-desktop-v5.png`
- `home-design-room-desktop-v3.png`
- `home-design-play-desktop-v3.png`
- `giftable-rockers-collection-desktop-v1.png`
- `pink-unicorn-pdp-desktop-v1.png`
- `home-design-gift-mobile-v5.png`
- `giftable-rockers-collection-mobile-v1.png`
- `pink-unicorn-pdp-mobile-v1.png`

## Rendered 2026-04-28 Update

The current render is intentionally screenshot-driven rather than AI-generated
motion. It is meant to be reliable boss-facing evidence of the current DTC
prototype, not a speculative brand film.

Outputs:

- Desktop meeting version:
  `paperclip_runtime_duel/outputs/labebe_site_walkthrough/labebe_dtc_site_walkthrough.mp4`
- Mobile vertical cut:
  `paperclip_runtime_duel/outputs/labebe_site_walkthrough/labebe_dtc_site_walkthrough_mobile.mp4`
- Posters:
  `labebe_dtc_site_walkthrough_poster.jpg`,
  `labebe_dtc_site_walkthrough_mobile_poster.jpg`
- Proof strips:
  `labebe_dtc_site_walkthrough_contact_sheet.jpg`,
  `labebe_dtc_site_walkthrough_mobile_contact_sheet.jpg`

Verification:

- Desktop MP4: H.264, 1920x1080, about 66.97 seconds.
- Mobile MP4: H.264, 1080x1920, about 39.97 seconds.
- Both MP4 files returned HTTP 200 through `fnos.dandanbaba.xyz:8778`.

## Deliverables

| Deliverable | Format | Target |
| --- | --- | --- |
| Main walkthrough | 70-90 sec, 16:9, 1920x1080 | Desktop presentation, meeting screen, decision pack. |
| Mobile cutdown | 45-60 sec, 9:16 or 4:5 | Phone viewing and chat sharing. |
| Screenshot proof strip | 5-8 stills | Backup if video playback fails. |
| Poster frame | Single hero frame, not a contact sheet | Should show the DTC homepage product theater. |
| Evidence manifest | Markdown or JSON | Routes, screenshots, console/overflow status, source dates. |

## Hard Boundary

Must include:

- Product-first consumer commerce.
- Room, age, gift, play-world navigation.
- Home, collection, and PDP route movement.
- Mobile and desktop proof.
- Claim-safe copy: prices and review counts only where supported.

Must not include:

- Paperclip UI.
- Boss Gallery.
- AI pipeline diagrams.
- Internal Claim Gate UI.
- Runtime Duel proof.
- Fake reviews, ratings, certifications, awards, Amazon rank, or conversion lift.

## Recommended Story Arc

Working title: `Choose the room. Choose the play.`

| Time | Shot | Action | Message |
| --- | --- | --- | --- |
| 0-6s | Desktop homepage first viewport | Slow reveal or scroll-free hold on hero product theater. | Labebe is a room-first wooden play brand, not a flat toy shelf. |
| 6-14s | Desktop navigation | Hover or click `Shop by Room`, `Shop by Age`, `Gifts`. | Discovery starts from parent intent. |
| 14-25s | Collection route | Open `/collections/playroom-reset` or room path. | Collection pages are scenario-led, not generic grids. |
| 25-42s | PDP route | Open `/product/pink-unicorn-plush-rocker`; show image, price, review count, age/room/gift badges. | PDP keeps decision facts near the purchase action. |
| 42-55s | PDP tabs / trust modules | Show details, fit/care, gifting modules if stable. | Practical objections are handled without inventing claims. |
| 55-70s | Mobile home and PDP | Cut to 390px mobile capture; show hero, CTA stack, product image before buy box. | The design works as a phone-first commerce path. |
| 70-85s | Evidence close | Quick still montage of desktop/mobile screenshots and route status, outside the consumer UI. | The prototype has browser evidence and remaining gaps are explicit. |

## Voiceover Draft

Use calm commerce language. Avoid talking about how the page was built.

```text
Labebe should not feel like a flat toy shelf.
This prototype reorganizes the store around the way parents actually shop:
room, age, occasion, and daily routine.

The homepage makes product identity immediate.
Collections start with scenarios, not rows of undifferentiated cards.
The PDP keeps the product image, price, review count, age fit, room fit,
gift framing, and add-to-cart action together.

On mobile, the product comes first and the purchase path stays readable.
This is a consumer DTC replacement direction, separate from the internal AI
demo and still bounded by the claim evidence we have today.
```

## Capture Plan

### Desktop

- Viewport: `1440x1100` for evidence screenshots; `1920x1080` for final video.
- Routes:
  - `/`
  - `/shop/by-room`
  - `/shop/by-age`
  - `/collections/playroom-reset`
  - `/product/pink-unicorn-plush-rocker`
- Capture:
  - smooth scroll at 0.7-0.9 viewport per second;
  - cursor visible only when it clarifies a click;
  - no fast page whip transitions;
  - no browser chrome in the polished edit unless showing route evidence.

### Mobile

- Viewport: `390x844` for video framing; `390x1200` or CDP full-page for QA.
- Mandatory shots:
  - mobile header and nav chips;
  - homepage headline plus primary CTA;
  - product hero card;
  - PDP image before buy box;
  - add-to-cart target visible and readable.
- Safe area:
  - keep captions outside the top 110px and bottom 140px in vertical cut;
  - minimum caption size equivalent to 34-40px at 1080x1920.

## Motion Direction

Motion should demonstrate usability, not decorate the page.

- Use route transitions, scroll, hover states, and tab changes as the main motion.
- Optional edit-layer motion: 250-450ms cross-dissolves and subtle zooms on stills.
- Do not add floating shapes, decorative blobs, animated fake metrics, or generic AI-style kinetic typography.
- Do not imply live checkout if the cart drawer/checkout flow is not implemented.
- Respect `prefers-reduced-motion` for the site; the video edit can use restrained transitions.

## Evidence Package

The final video folder should include:

| Evidence | Required |
| --- | --- |
| Desktop homepage screenshot | yes |
| Mobile homepage screenshot | yes |
| Desktop PDP screenshot | yes |
| Mobile PDP screenshot | yes |
| Collection screenshot | yes |
| Route HTTP status table | yes |
| Horizontal overflow results | yes |
| Console error summary | yes |
| Asset rights caveat | yes |
| Known gaps slide or note | yes |

2026-04-28 status update:

- The prototype cart drawer now has add/update/remove/subtotal behavior and a
  non-dead checkout-review handoff. It still does not implement payment, tax,
  shipping, order placement, or a production checkout backend.
- The 8-SKU PDP source capture is complete, with raw text, screenshots, keyword
  contexts, and a 333-row manual claim-review queue. Claims from that queue are
  not approved until reviewed.
- The DTC desktop and mobile walkthroughs have been rendered and served from
  `paperclip_runtime_duel/outputs/labebe_site_walkthrough/`.
- Catalog/lifestyle asset rights still need brand/legal review before production
  use.
- The prototype is review-ready and demo-ready, not production-complete.

## Production Sequence

1. Restart and smoke the DTC server with the existing SPA static server command
   from `work_products/dtc_prototype_v2/browser_qa_report.md`.
2. Capture desktop screenshots and video clips for all target routes.
3. Capture mobile clips using real device metrics, not only a resized desktop window.
4. Run the visual QA acceptance checklist in `visual_qa_acceptance.md`.
5. Assemble the main 16:9 edit first.
6. Reframe or recapture for mobile; do not crop desktop footage if UI text becomes too small.
7. Export poster frame, proof strip, and evidence manifest.

## Acceptance Gates

Reject the walkthrough if any of these are true:

- Paperclip, AI workflow, or internal Claim Gate appears inside the consumer site story.
- Mobile feels like a cropped desktop recording.
- Text in the video is unreadable on a phone.
- The first viewport does not clearly show Labebe product value.
- The edit uses contact sheets as video cover art.
- Unsupported claims appear in captions, narration, or overlays.
- Any shot shows obvious overlap, clipped CTA text, horizontal scroll, blank content, or broken media.
