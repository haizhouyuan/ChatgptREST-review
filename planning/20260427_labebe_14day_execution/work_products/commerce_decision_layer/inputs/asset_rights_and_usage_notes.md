# Asset Rights and Usage Notes (Draft)

**Worker:** WP-C Public Media Asset Probe Worker  
**Date:** 2026-04-27  
**Status:** Draft — requires legal/brand review before any consumer-facing use.  
**Hard rule:** Public capture ≠ legal clearance.

---

## 1. Asset Classes and Default Rights Posture

| Asset Class | Source | Default Rights | DTC Usable | Boss Gallery Usable | Notes |
|-------------|--------|----------------|------------|---------------------|-------|
| Scraped catalog images | labebeclub.com / Shopify CDN | **Unknown / Unverified** | Conditional | Conditional | Need explicit license or terms-of-service review |
| AI-generated video (MiniMax) | MiniMax API / local pipeline | **Synthetic; no traditional copyright** | Blocked | Usable with claim gate | Must label as AI-generated; cannot imply real product footage |
| AI-generated images (design library heroes) | Unknown AI tool | **Synthetic; provenance unclear** | Blocked | Conditional | Verify generation tool TOS; label synthetic |
| Local composite video (Boss Gallery) | Internal edit | **Internal use only** | Blocked | Usable with claim gate | Contains mixed sources; each component needs its own clearance |
| Screen recordings / workflow demos | Internal tool capture | **Internal use only** | Blocked | Usable with claim gate | May expose internal UI; scrub sensitive data |
| Screenshots (QA) | Local browser capture | **Internal use only** | Blocked | Conditional | No rights issue but not consumer-facing quality |
| Stock/sizzle video (brand-video.mp4) | Unknown origin | **High risk** | Blocked until verified | Blocked until verified | Origin unknown; may contain unlicensed stock footage |

---

## 2. SKU-Specific Asset Notes

### 2.1 Wooden Mud Kitchen (outdoor-mud-kitchen-yellow / wooden-mud-kitchen-outdoor-play-kitchen-with-planter-box-sink)
- **Has AI video:** Yes (MiniMax, 6 sec)
- **Has catalog images:** Yes (7–9 images)
- **Has storyboard:** Yes (`01_storyboard_wooden_mud_kitchen.jpg`)
- **Usage caveat:** AI video shows the product in an outdoor garden context that may not match actual product dimensions or materials. Do not use AI video on PDP without synthetic label.

### 2.2 Foldable Learning Tower (log color / white / gray / unicorn)
- **Has AI video:** No
- **Has catalog images:** Yes (8–9 images per variant)
- **Has hero asset:** Yes (`hero-montessori.jpg`, `learningTower.jpg`)
- **Usage caveat:** Multiple color variants exist; ensure PDP shows the correct variant image.

### 2.3 Pink Unicorn Plush Rocker
- **Has AI video:** No
- **Has catalog images:** Yes (7 images)
- **Has storyboard:** Yes (`03_storyboard_pink_unicorn_rocker.jpg`)
- **Has hero asset:** Yes (`hero-rockers.jpg`, `rocker.jpg`)
- **Usage caveat:** Highlander Cattle and other rocker variants may share visual layout; ensure no variant confusion.

### 2.4 Natural Wood Montessori Shelf
- **Has AI video:** No
- **Has catalog images:** Yes (13 images)
- **Has storyboard:** Yes (`02_storyboard_storage_montessori_shelf.jpg`)
- **Has hero asset:** Yes (`shelf.jpg`)
- **Usage caveat:** Similar SKU "rubber-wood-montessori-shelf" exists; images are distinct but category is close.

### 2.5 Activity Cube Baby Push Walker
- **Has AI video:** No
- **Has catalog images:** Yes (8 images)
- **Has hero asset:** No dedicated hero; appears in contact sheet only
- **Usage caveat:** Low image count relative to complexity; may need lifestyle context shots.

---

## 3. Blocked Claims (Do Not Use)

The following claims must **not** be made using any of the discovered assets unless independently verified:

1. **CE / ASTM / CPSIA certification badges** — No certification artwork discovered. Do not create or display.
2. **"Bestseller" / "Award-winning"** — No evidence of awards or sales rankings in assets.
3. **"As seen on TV / press"** — No press clippings or broadcast footage discovered.
4. **Real child testimonials** — No verified model releases for any children appearing in AI-generated or stock imagery.
5. **Exact material composition** — Catalog images do not prove material claims (e.g., "solid beech wood").
6. **Safety guarantees** — Images and videos are not safety testing evidence.

---

## 4. Allowed Uses (With Conditions)

| Use Case | Required Condition |
|----------|-------------------|
| DTC PDP gallery using scraped catalog images | Verify labebeclub.com TOS or obtain direct license; host on own CDN |
| Boss Gallery showing AI video | Label as "AI-generated prototype"; add claim gate badge |
| Boss Gallery using catalog images | Same as DTC; add source attribution |
| Internal concept boards / storyboards | No restriction; internal use only |
| QA screenshots in review docs | No restriction; internal use only |

---

## 5. Provenance Gaps

The following assets have **unclear origin** and should be treated as highest risk:

- `brand-video.mp4` — No source documentation; unknown music licensing; unknown footage licensing.
- `demo-workflow.mp4` — Contains screen recordings of potentially third-party tools.
- `hero-home.jpg`, `hero-montessori.jpg`, `hero-playroom.jpg`, `hero-pretend.jpg`, `hero-rockers.jpg` — AI-generated but tool/version/prompt unknown.
- `parent-moment-1.jpg`, `parent-moment-2.jpg` — Likely AI-generated; faces of adults/children unverified.
- `room-nursery.jpg`, `room-playroom.jpg` — Likely AI-generated room renders.

---

## 6. Recommended Next Steps

1. **Legal review:** Confirm rights to reuse labebeclub.com catalog images for DTC prototype.
2. **AI labeling policy:** Decide uniform "AI-generated" badge design for all synthetic assets.
3. **CDN migration:** If rights are clear, re-host catalog images on prototype CDN rather than hotlinking Shopify.
4. **Gap fill plan:** Commission or generate hero/lifestyle images for SKUs missing room-context shots.
5. **Video expansion:** Only 1 of 6-8 priority SKUs has AI video. Evaluate cost/benefit of generating more.
