# Initial Media Probe — Labebe Public/Local Assets

**Worker:** WP-C Public Media Asset Probe Worker  
**Date:** 2026-04-27  
**Scope:** Discover and classify existing public/local Labebe media assets for DTC prototype and Boss Gallery planning.  
**Caveat:** This document records discovery only. Public capture is **not** legal clearance.

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Total media files discovered | ~560+ |
| Unique product image downloads | 460 |
| Video files | 9 |
| AI-generated video assets | 2 SKU-specific (Wooden Mud Kitchen) |
| Boss Gallery v0 assets | 13 files (7 category heroes + video + screenshots) |
| DTC prototype product images | 16 SKUs |
| Design library hero/room images | 11 |

**Primary source:** labebeclub.com product catalog (Shopify CDN via `media.cdn.ishopastro.com`).  
**Secondary sources:** Kimi-generated design library, MiniMax AI video outputs, Paperclip `labebe_wow` Boss Gallery v0.

---

## 2. Asset Source Map

### 2.1 Official Product Catalog (Scraped)
- **Path:** `data/labebe/images/`
- **Count:** 460 JPGs across 46 products
- **Source URL base:** `https://media.cdn.ishopastro.com/1212922093866627/media/image/`
- **Origin:** labebeclub.com PDP galleries
- **Capture date:** 2026-04-24
- **Method:** Playwright crawl + direct CDN download
- **Quality:** Mixed; some images are white-background product shots, some are lifestyle/room-context.

### 2.2 Kimi Web Upload Website Pack — Reference Images
- **Path:** `kimi_web_upload_website_pack/images/`
- **Count:** 16 files
- **Content:**
  - `00_labebe_product_contact_sheet.jpg` — composite contact sheet of multiple SKUs
  - `01-03_storyboard_*.jpg` — storyboard frames for 3 hero SKUs (mud kitchen, shelf, unicorn rocker)
  - `10-21_ref_*.jpg` — individual product reference images, likely sourced from official catalog
- **Role:** Briefing material for website generation; many are exact duplicates of catalog images.

### 2.3 MiniMax AI Video Demo Assets
- **Path:** `minimax-output/` and `kimi_web_upload_website_pack/07_minimax_demo_assets/`
- **Count:** 7 files (2 JPG first-frames, 2 MP4 videos, 1 cover, 1 MP3 voiceover, 1 contact sheet)
- **SKU:** Wooden Mud Kitchen only
- **Origin:** AI-generated via MiniMax image-to-video + TTS
- **Caveat:** AI-generated; not a real product photo. Must be labeled as synthetic in any consumer-facing use.

### 2.4 Paperclip Boss Gallery v0 (`labebe_wow`)
- **Path:** `paperclip_runtime_duel/outputs/labebe_wow/`
- **Count:** 13 media files
- **Content:**
  - `assets/` — 7 category hero images (bakery, heroHome, learningTower, playKitchen, playroom, rocker, shelf)
  - `labebe_ai_application_wow.mp4` — Boss Gallery walkthrough video
  - Screenshots: `index_desktop.png`, `index_mobile.png`, `boss_video_page_desktop.png`
  - `labebe_ai_application_wow_contact_sheet.jpg` — video frame contact sheet
  - `labebe_ai_application_wow_poster.jpg` — poster/thumbnail
- **Role:** Decision-maker demo material; **not** for DTC consumer site.

### 2.5 Kimi Generated DTC Site Assets
- **Path:** `kimi_generated_site/app/public/videos/` and `kimi_generated_site/app/dist/assets/products/`
- **Count:** 2 videos + 16 product images
- **Videos:**
  - `brand-video.mp4` (5.5 MB) — generic brand sizzle reel
  - `wooden-mud-kitchen-showroom.mp4` (1.3 MB) — same as MiniMax with-voice output
- **Product images:** 16 SKUs selected for the generated site build

### 2.6 Kimi Labebe Design Library
- **Path:** `kimi_labebe_design_library/app/public/`
- **Count:** 32 files
- **Content:**
  - Hero images: `hero-home.jpg`, `hero-montessori.jpg`, `hero-playroom.jpg`, `hero-pretend.jpg`, `hero-rockers.jpg`
  - Product feature shots: `product-learning-tower.jpg`, `product-play-kitchen.jpg`, `product-rocker-unicorn.jpg`
  - Room context: `room-nursery.jpg`, `room-playroom.jpg`
  - Parent moments: `parent-moment-1.jpg`, `parent-moment-2.jpg`
  - AI studio hero: `ai-studio-hero.jpg`
  - Asset matrix SVG: `ai-studio/labebe-asset-matrix.svg`
  - Demo workflow video: `demo-workflow.mp4`
  - 16 product thumbnails in `products/`

---

## 3. Collection / Category Coverage

| Collection | Products | Image Count | Has Hero Asset |
|------------|----------|-------------|----------------|
| furniture | 17 | ~180 | Yes (shelf, learningTower) |
| rockers-ride-ons | 13 | ~110 | Yes (rocker) |
| pretend-play | 9 | ~100 | Yes (playKitchen, bakery) |
| activity-educational-toys | 6 | ~50 | Partial |
| new-in | 1 | ~20 | No |

---

## 4. Gaps and Unknowns

1. **No official brand video from Labebe.** All video is either AI-generated (MiniMax) or generic sizzle.
2. **No founder/team photography.** All people images are stock or AI-generated room contexts.
3. **No packaging/unboxing photography.**
4. **No certification badge artwork.** (CE, ASTM, etc. — do not invent.)
5. **Limited lifestyle/room-context shots.** Most catalog images are white-background or basic studio.
6. **Only 1 SKU has AI video treatment** (Wooden Mud Kitchen). No video for Learning Tower, Pink Unicorn Rocker, etc.
7. **Duplicate file proliferation.** Same catalog images copied into 3–4 directories (design library, generated site, website pack, labebe_wow). See `downloaded_media_manifest_draft.csv` for hash map.

---

## 5. Method Notes

- Discovery was filesystem-only; no outbound crawling performed in this probe.
- Hashes computed with SHA-256 (first 16 chars reported).
- Image dimensions were not extracted; sizes reported in bytes.
- Video duration/frame-rate not analyzed; file sizes noted.
- No EXIF metadata extraction performed.

---

## 6. Limitations

- Did not verify whether CDN URLs are still hot (404 risk for direct linking).
- Did not check robots.txt or terms of service for media reuse permissions.
- Did not probe for hidden or password-protected asset folders.
- Did not inspect `.docx` briefs for embedded media references (only filesystem enumeration).
