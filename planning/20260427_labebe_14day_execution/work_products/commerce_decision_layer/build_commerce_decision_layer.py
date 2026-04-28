#!/usr/bin/env python3
"""Build Commerce Decision Layer artifacts from local Labebe evidence.

This script is intentionally conservative: it only uses fields present in the
local independent-site scrape and media manifest. Anything not in those sources
is marked unknown, blocked, or needs review.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
SAMPLE_DIR = ROOT.parent / "sample_dossiers"


SAMPLE_SLUGS = [
    "pink-unicorn-plush-rocker",
    "cream-wooden-play-kitchen-set-with-storage",
    "foldable-learning-tower-montessori-kitchen-tower-log-color",
    "children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art",
    "kids-toy-storage-organizer-bookshelf-with-bins",
    "natural-wood-montessori-shelf-with-storage-boxes",
    "wooden-mud-kitchen-outdoor-play-kitchen-with-planter-box-sink",
    "activity-cube-baby-push-walker",
]


ROLE_OVERRIDES = {
    "pink-unicorn-plush-rocker": {
        "role": "Giftable hero SKU",
        "shopper_mission": "First birthday / nursery gift",
        "why": "Highest review-count signal in the current DTC scrape and strong visual/emotional recognition.",
        "primary_page": "Hero, gift guide, rocker PDP",
        "wow_angle": "Gift finder and nursery moment, not generic toy grid.",
        "risk": "Avoid fake parent quotes, unverified safety or age claims, and invented ratings.",
    },
    "cream-wooden-play-kitchen-set-with-storage": {
        "role": "Pretend-play commerce anchor",
        "shopper_mission": "Kitchen role-play / holiday gift",
        "why": "Recognizable category, review signal, and usable catalog asset; maps well to video, PDP modules, and bundles.",
        "primary_page": "Pretend Play collection, PDP, content modules",
        "wow_angle": "Tiny chef world with add-on play food and room scene merchandising.",
        "risk": "Do not imply materials, dimensions, or certifications unless PDP evidence is captured.",
    },
    "foldable-learning-tower-montessori-kitchen-tower-log-color": {
        "role": "Utility furniture / product-innovation test SKU",
        "shopper_mission": "Kitchen helper / independence routine",
        "why": "High strategic value for VOC-to-concept and PDP education, despite missing review count.",
        "primary_page": "Learning Tower PDP, VOC-to-concept demo, kitchen routine guide",
        "wow_angle": "Fit, foldability, cleaning, stability and human-review claim gate.",
        "risk": "Review count is unknown; safety wording must be conservative.",
    },
    "children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art": {
        "role": "High-ticket study/art room SKU",
        "shopper_mission": "Study corner / art corner upgrade",
        "why": "High price and strong review-count signal; also stress-tests slug normalization and gallery joins.",
        "primary_page": "Study room collection, PDP, room builder",
        "wow_angle": "From playroom to study-corner transformation.",
        "risk": "Slug has CSV/PDP mismatch; join by product URL, not raw slug.",
    },
    "kids-toy-storage-organizer-bookshelf-with-bins": {
        "role": "Playroom reset conversion SKU",
        "shopper_mission": "Toy chaos / storage solution",
        "why": "Directly supports room-transformation merchandising and bundle logic.",
        "primary_page": "Playroom Reset collection, home Quick Finder, bundles",
        "wow_angle": "Before/after playroom organization and toy rotation.",
        "risk": "Do not claim Montessori unless sourced; describe as low-access storage only when evidence supports it.",
    },
    "natural-wood-montessori-shelf-with-storage-boxes": {
        "role": "Montessori-at-home anchor",
        "shopper_mission": "Toy rotation / independent access",
        "why": "Clear fit for education-oriented navigation and product comparison.",
        "primary_page": "Montessori at Home collection, room builder",
        "wow_angle": "Calm shelf system with visible routines and cross-sells.",
        "risk": "Montessori language must be positioned as style/routine unless product claims are verified.",
    },
    "wooden-mud-kitchen-outdoor-play-kitchen-with-planter-box-sink": {
        "role": "Outdoor sensory / content SKU",
        "shopper_mission": "Backyard pretend play / sensory exploration",
        "why": "Best candidate for motion-first scenes and outdoor seasonal campaign, even with low review signal.",
        "primary_page": "Outdoor play collection, video/story modules",
        "wow_angle": "Water, planter, mud-kitchen play scene; strong video potential.",
        "risk": "Low review signal; avoid over-presenting as bestseller.",
    },
    "activity-cube-baby-push-walker": {
        "role": "New-in developmental play candidate",
        "shopper_mission": "Early walker / baby milestone",
        "why": "Covers baby milestone path and new-in category; useful for age-based navigation.",
        "primary_page": "Shop by Age, baby milestone guide",
        "wow_angle": "6-18m journey from activity cube to push walker.",
        "risk": "Collection is new-in; reviews unknown in scrape; must not claim proven demand.",
    },
}


PERMITTED_CLAIMS_BY_SOURCE = {
    "price": "Allowed if shown with scrape date and source URL.",
    "review_count": "Allowed only when numeric in listing capture; otherwise hide or mark unknown.",
    "discount": "Allowed only as listing-captured/implied pricing signal, not long-term promotion.",
    "new_hot_badge": "Allowed as merchandising tag on scrape date; not demand proof.",
    "gallery_count": "Allowed as internal asset-readiness signal.",
    "category": "Allowed from collection_listing.",
}


BLOCKED_CLAIMS = [
    "rating stars",
    "customer quotes",
    "Amazon sales volume",
    "Amazon rank",
    "certifications",
    "safety test passed",
    "age suitability beyond source evidence",
    "materials and finish claims",
    "manufacturing origin",
    "award / press mentions",
    "proven market demand",
    "production-ready CAD",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def money(value: str) -> str:
    if value == "":
        return "unknown"
    return f"${float(value):.2f}"


def review(value: str) -> str:
    return f"{int(value)} reviews" if value.strip() else "unknown"


def build_media_index(media_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    index: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in media_rows:
        filename = row["filename"]
        if not filename:
            continue
        stem = filename.rsplit(".", 1)[0]
        index[stem].append(row)
    return index


def sample_record(row: dict[str, str], media_index: dict[str, list[dict[str, str]]]) -> dict[str, object]:
    slug = row["slug_csv"]
    role = ROLE_OVERRIDES[slug]
    catalog_assets = media_index.get(slug, [])
    dtc_ready = [r for r in catalog_assets if r["source_category"] in {"dtc_build_copy", "official_catalog", "website_pack"}]
    video_count = sum(1 for r in catalog_assets if r["media_type"] == "video")
    return {
        "slug": slug,
        "name": row["name_clean"],
        "category": row["collection_listing"],
        "price": money(row["current_price_usd"]),
        "original_price": money(row["original_price_usd"]),
        "review_count": review(row["reviews_count_listing"]),
        "gallery_count": row["gallery_files_on_disk"],
        "product_url": row["product_url"],
        "role": role["role"],
        "shopper_mission": role["shopper_mission"],
        "why_selected": role["why"],
        "primary_page": role["primary_page"],
        "wow_angle": role["wow_angle"],
        "known_risk": role["risk"],
        "dtc_ready_assets": len(dtc_ready),
        "video_assets": video_count,
    }


def readiness_level(sample: dict[str, object]) -> str:
    images = int(sample["gallery_count"] or 0)
    if images >= 10 and sample["review_count"] != "unknown":
        return "A: prototype-ready"
    if images >= 7:
        return "B: usable with claim review"
    return "C: needs enrichment"


def asset_recommendation(sample: dict[str, object]) -> str:
    slug = sample["slug"]
    if slug == "pink-unicorn-plush-rocker":
        return "Use for hero/gift modules; create synthetic lifestyle only with label."
    if "kitchen" in slug:
        return "Use catalog/gallery plus storyboarded short video; avoid claiming real footage unless verified."
    if "tower" in slug:
        return "Use for PDP education and concept exploration; needs dimension/safety evidence."
    if "storage" in slug or "shelf" in slug:
        return "Use for room-builder and before/after mockups; generated room scenes must be labelled."
    if "walker" in slug:
        return "Use for age navigation and milestone card; review/demand evidence missing."
    return "Use as supporting commerce module only."


def dossier_md(sample: dict[str, object]) -> str:
    permitted = "\n".join(f"- {k}: {v}" for k, v in PERMITTED_CLAIMS_BY_SOURCE.items())
    blocked = "\n".join(f"- {claim}" for claim in BLOCKED_CLAIMS)
    return f"""# SKU Dossier — {sample['name']}

Generated: 2026-04-27
Evidence scope: local Labebe independent-site scrape and local media manifest only.

## Identity

| Field | Value |
| --- | --- |
| Slug | `{sample['slug']}` |
| Category | {sample['category']} |
| Price | {sample['price']} |
| Original price | {sample['original_price']} |
| Listing review count | {sample['review_count']} |
| Gallery files on disk | {sample['gallery_count']} |
| Product URL | {sample['product_url']} |

## Business Role

| Field | Value |
| --- | --- |
| Role | {sample['role']} |
| Shopper mission | {sample['shopper_mission']} |
| Primary page use | {sample['primary_page']} |
| Why selected | {sample['why_selected']} |
| Wow angle | {sample['wow_angle']} |

## Asset Readiness

| Field | Value |
| --- | --- |
| Readiness | {readiness_level(sample)} |
| DTC-ready/catalog assets found | {sample['dtc_ready_assets']} |
| Video assets found | {sample['video_assets']} |
| Recommendation | {asset_recommendation(sample)} |

## Claim Gate

Permitted claim classes:

{permitted}

Blocked until additional evidence:

{blocked}

## Known Risks

{sample['known_risk']}

## Next Evidence Needed

- PDP text extraction for dimensions, materials, age guidance, assembly, care, and warnings.
- Marketplace identity mapping before any Amazon sales/rank/review claim.
- Asset rights decision before using generated or unknown-origin lifestyle images in a public-facing demo.
- Human review of every safety, certification, developmental, and age-related claim.
"""


def main() -> None:
    products = read_csv(INPUTS / "product_master_v0.csv")
    media_rows = read_csv(INPUTS / "downloaded_media_manifest.csv")
    by_slug = {row["slug_csv"]: row for row in products}
    missing = [slug for slug in SAMPLE_SLUGS if slug not in by_slug]
    if missing:
        raise SystemExit(f"Missing sample slugs: {missing}")

    media_index = build_media_index(media_rows)
    samples = [sample_record(by_slug[slug], media_index) for slug in SAMPLE_SLUGS]
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    for sample in samples:
        (SAMPLE_DIR / f"{sample['slug']}.md").write_text(dossier_md(sample), encoding="utf-8")

    write_csv(
        ROOT / "sku_role_matrix.csv",
        samples,
        [
            "slug",
            "name",
            "category",
            "price",
            "review_count",
            "gallery_count",
            "role",
            "shopper_mission",
            "primary_page",
            "wow_angle",
            "known_risk",
        ],
    )

    readiness_rows = []
    for sample in samples:
        readiness_rows.append(
            {
                "slug": sample["slug"],
                "name": sample["name"],
                "readiness_level": readiness_level(sample),
                "gallery_files_on_disk": sample["gallery_count"],
                "dtc_ready_or_catalog_assets_found": sample["dtc_ready_assets"],
                "video_assets_found": sample["video_assets"],
                "safe_use_now": "Internal prototype / evidence-backed modules only",
                "asset_recommendation": asset_recommendation(sample),
            }
        )
    write_csv(
        ROOT / "asset_readiness_matrix.csv",
        readiness_rows,
        [
            "slug",
            "name",
            "readiness_level",
            "gallery_files_on_disk",
            "dtc_ready_or_catalog_assets_found",
            "video_assets_found",
            "safe_use_now",
            "asset_recommendation",
        ],
    )

    claim_rows = []
    for sample in samples:
        claim_rows.extend(
            [
                {
                    "slug": sample["slug"],
                    "claim_type": "price",
                    "status": "allowed_with_scrape_date",
                    "evidence": f"{sample['price']} from local DTC scrape",
                    "display_rule": "Show with source/date in internal docs; public mock can show price only as demo data.",
                },
                {
                    "slug": sample["slug"],
                    "claim_type": "review_count",
                    "status": "allowed_if_numeric" if sample["review_count"] != "unknown" else "hide_or_mark_unknown",
                    "evidence": sample["review_count"],
                    "display_rule": "Do not convert to star rating or customer quote.",
                },
                {
                    "slug": sample["slug"],
                    "claim_type": "safety_certification_materials_age",
                    "status": "blocked_pending_pdp_evidence",
                    "evidence": "Not present in current product_master_v0.",
                    "display_rule": "Use neutral copy; no certification, safety pass, material, or age guarantee.",
                },
                {
                    "slug": sample["slug"],
                    "claim_type": "marketplace_sales_rank_velocity",
                    "status": "blocked_pending_asin_identity",
                    "evidence": "Amazon identity not verified.",
                    "display_rule": "No Amazon volume, rank, bestseller, or proven demand wording.",
                },
            ]
        )
    write_csv(
        ROOT / "claim_permission_matrix.csv",
        claim_rows,
        ["slug", "claim_type", "status", "evidence", "display_rule"],
    )

    hero_rows = []
    for sample in samples:
        score = 0
        if sample["review_count"] != "unknown":
            score += 2
        if int(sample["gallery_count"]) >= 10:
            score += 2
        if "hero" in sample["role"].lower() or "anchor" in sample["role"].lower():
            score += 2
        if "risk" in sample["known_risk"].lower():
            score -= 0
        hero_rows.append(
            {
                "slug": sample["slug"],
                "name": sample["name"],
                "homepage_role": sample["role"],
                "hero_score_0_6": score,
                "best_surface": sample["primary_page"],
                "hero_line": sample["wow_angle"],
                "must_not_say": sample["known_risk"],
            }
        )
    write_csv(
        ROOT / "hero_candidate_matrix.csv",
        hero_rows,
        ["slug", "name", "homepage_role", "hero_score_0_6", "best_surface", "hero_line", "must_not_say"],
    )

    bundle_rows = [
        {
            "bundle_name": "First Birthday Nursery Gift",
            "anchor_slug": "pink-unicorn-plush-rocker",
            "supporting_slugs": "activity-cube-baby-push-walker; natural-wood-montessori-shelf-with-storage-boxes",
            "commerce_logic": "Emotional gift plus early play plus room organization.",
            "evidence_status": "DTC scrape supports product identity; bundle performance unknown.",
        },
        {
            "bundle_name": "Tiny Chef Pretend Play",
            "anchor_slug": "cream-wooden-play-kitchen-set-with-storage",
            "supporting_slugs": "wooden-mud-kitchen-outdoor-play-kitchen-with-planter-box-sink; kids-coffee-shop-grocery-store-playset",
            "commerce_logic": "Indoor kitchen, outdoor sensory play, and pretend shop expansion.",
            "evidence_status": "Some supporting SKUs not in the 8-sample set; verify before prototype module.",
        },
        {
            "bundle_name": "Playroom Reset",
            "anchor_slug": "kids-toy-storage-organizer-bookshelf-with-bins",
            "supporting_slugs": "natural-wood-montessori-shelf-with-storage-boxes; children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art",
            "commerce_logic": "Storage, toy rotation, and study/art corner.",
            "evidence_status": "DTC identity supports concept; no conversion evidence yet.",
        },
        {
            "bundle_name": "Kitchen Helper Routine",
            "anchor_slug": "foldable-learning-tower-montessori-kitchen-tower-log-color",
            "supporting_slugs": "cream-wooden-play-kitchen-set-with-storage; wooden-mud-kitchen-outdoor-play-kitchen-with-planter-box-sink",
            "commerce_logic": "Parent-child routine, pretend cooking, and sensory play path.",
            "evidence_status": "Safety/age/dimension evidence required before PDP claims.",
        },
    ]
    write_csv(
        ROOT / "bundle_and_cross_sell_map.csv",
        bundle_rows,
        ["bundle_name", "anchor_slug", "supporting_slugs", "commerce_logic", "evidence_status"],
    )

    category_counts = Counter(row["collection_listing"] for row in products)
    category_lines = "\n".join(f"- {category}: {count} products" for category, count in sorted(category_counts.items()))
    (ROOT / "category_portfolio_map.md").write_text(
        f"""# Category Portfolio Map

Generated: 2026-04-27
Source: `inputs/product_master_v0.csv` built from the local Labebe independent-site scrape.

## Current Category Footprint

{category_lines}

## Strategic Reading

Labebe is not only a toy-grid store. The catalog already has four commerce
worlds that should shape the DTC redesign:

| World | Evidence Basis | Design Implication |
| --- | --- | --- |
| Giftable Rockers | 13 rockers/ride-ons in scrape and several visible review counts. | Treat as emotional gift discovery, not commodity product cards. |
| Montessori / Home Furniture | Furniture is the largest category in the 46-product scrape. | Navigation should lead by room, routine and parent job-to-be-done. |
| Pretend Play Worlds | Kitchens, washer/dryer, coffee shop, bakery and mud kitchen products. | Build scene-led collections and video/story modules. |
| Playroom Reset | Storage, shelf, desk and art surfaces. | Show before/after organization logic and cross-sells. |

## Decision

The next DTC prototype should not chase one visual style first. It should first
make these worlds legible, then choose visual language that helps parents decide
what to buy for a child, room and moment.
""",
        encoding="utf-8",
    )

    (ROOT / "sample_selection_rationale.md").write_text(
        "# Sample Selection Rationale\n\n"
        "Generated: 2026-04-27\n\n"
        "These 8 SKUs are selected as the first decision sample. They are not a full catalog crawl, "
        "and they are not claimed to represent Amazon performance. They are the minimum set needed "
        "to design a stronger DTC website from product reality instead of generic aesthetics.\n\n"
        "| SKU | Role | Why It Is In The Sample | Evidence Risk |\n"
        "| --- | --- | --- | --- |\n"
        + "\n".join(
            f"| `{s['slug']}` | {s['role']} | {s['why_selected']} | {s['known_risk']} |" for s in samples
        )
        + "\n\n"
        "Alternate: `midnight-serenity-wooden-play-kitchen-set` has 10 listing reviews and a rich gallery, "
        "so it can replace the Cream Play Kitchen if asset density becomes more important than continuity "
        "with the earlier design discussions.\n\n"
        "Marketplace note: ASIN `B087P9SXZQ` remains an identity-mapping target only. It must not be treated "
        "as a confirmed Labebe SKU until title/image/brand/seller evidence is captured.\n",
        encoding="utf-8",
    )

    (ROOT / "shopper_mission_map.md").write_text(
        """# Shopper Mission Map

Generated: 2026-04-27

## Missions To Design For

| Mission | Parent Question | Primary SKUs | Required UX |
| --- | --- | --- | --- |
| First birthday / nursery gift | What feels special, safe-looking and photo-worthy? | Pink Unicorn Plush Rocker, Activity Cube Baby Push Walker | Gift finder, age chips, nursery scene, gift wrap CTA. |
| Kitchen helper routine | How can my child join daily routines? | Foldable Learning Tower, Cream Play Kitchen | PDP education, fit/safety placeholders, parent-child scenario modules. |
| Pretend-play world | What play setup creates repeatable imaginative scenes? | Cream Play Kitchen, Wooden Mud Kitchen | Scene-led collection, video storyboard, add-on bundles. |
| Playroom reset | How do I make toys organized and accessible? | Toy Storage Organizer, Montessori Shelf, Writing Desk | Before/after, room builder, bundle logic. |
| Study/art corner | How do I upgrade from toddler play to focused activity? | Children’s Writing Desk and Chair Set | Room-by-room navigation, dimension and fit evidence gate. |
| Baby milestone | What supports early movement and exploration? | Activity Cube Baby Push Walker | Shop by age, milestone page, evidence-safe developmental language. |

## Redesign Implication

Homepage and navigation should start from age, room and moment. Product category
names still exist, but they should not be the only discovery path.
""",
        encoding="utf-8",
    )

    (ROOT / "navigation_decision_matrix.md").write_text(
        """# Navigation Decision Matrix

Generated: 2026-04-27

## Primary Navigation

| Nav Item | Purpose | Included Surfaces | Why |
| --- | --- | --- | --- |
| Shop by Age | Fast parent entry point | 6-18m, 18-36m, 3-5y, 5-8y | Makes product choice legible before browsing. |
| Shop by Room | DTC-specific commerce path | Nursery, Playroom, Kitchen, Study/Art, Backyard | Converts furniture/toy mix into home-space solutions. |
| Gift Finder | Emotional conversion path | First birthday, baby shower, holiday gift, grandparent gift | Uses rocker and milestone products as hooks. |
| Play Worlds | Category storytelling | Rockers, Pretend Play, Montessori at Home, Playroom Reset | Keeps brand worlds visible without generic grid feel. |
| Best Evidence Picks | Trust and merchandising | High review-count, rich-gallery, new-in | Separates supported signals from invented claims. |

## Secondary / Internal

| Item | Rule |
| --- | --- |
| AI / Paperclip demos | Do not place in the DTC consumer website. They belong to Boss Gallery / internal presentation. |
| Design Library | Internal only unless packaged as a design rationale deck. |
| Claim Gate | Invisible to shoppers, explicit in internal docs and Boss Gallery. |
""",
        encoding="utf-8",
    )

    (ROOT / "pdp_module_strategy_by_category.md").write_text(
        """# PDP Module Strategy By Category

Generated: 2026-04-27

## Universal PDP Modules

- Gallery with evidence-backed product images.
- Price and review count only when captured.
- Add to cart and bundle recommendation.
- Shipping/return placeholder only if source evidence exists.
- Claim-safe FAQ with unknowns hidden or marked as needs confirmation.

## Category-Specific Modules

| Category / World | Modules | Evidence Gate |
| --- | --- | --- |
| Giftable Rockers | Gift occasion, nursery placement, texture/detail gallery, gift wrap CTA. | No fake reviews, no invented ratings, no unsupported age/safety copy. |
| Learning Towers | Kitchen routine, fold/storage, fit/dimension, cleaning, parent checklist. | Dimensions, materials, warnings, age range and safety wording require PDP/source capture. |
| Pretend Play | Scene storyboard, what is included, room fit, add-on play-food/store bundles. | Do not imply included accessories unless source confirms. |
| Playroom Storage / Shelves | Before/after organization, toy rotation, small-space fit, room builder. | Do not overuse Montessori claims beyond supported wording. |
| Study / Art Furniture | Desk setup, storage, chair fit, art/study transition, bundle with easel/storage. | Needs dimensions and weight/age guidance before polished PDP. |
| Baby Milestone Toys | Milestone path, parent-supervised play framing, age navigation. | Developmental and safety claims require human review and source evidence. |
""",
        encoding="utf-8",
    )

    (ROOT / "rejected_direction_log.md").write_text(
        """# Rejected Direction Log

Generated: 2026-04-27

This log exists because prior iterations looked too generic, too narrow, or too
separated from product truth. Rejected directions should not re-enter the project
unless a later evidence review explicitly reverses the decision.

| Direction | Why Rejected | Replacement |
| --- | --- | --- |
| Warm beige centered mini-page with small content column | Looked like the previous weak iteration; did not feel world-class or commerce-ready. | Full-width, product-led, room/moment navigation with stronger composition. |
| Internal AI Growth Studio inside consumer DTC site | User clarified the website is a pure Labebe replacement site. AI demos belong elsewhere. | Separate Boss Gallery / Paperclip presentation surfaces. |
| Pretty AI image/video collage | Creates wow without trust; can become gimmick. | Product truth + commerce decision layer + labelled synthetic assets. |
| ASICS/running-shoe placeholder logic | Catastrophic brand mismatch. | Labebe-only assets and evidence manifest. |
| Fake reviews/ratings/certifications | Breaks credibility with decision makers and child-product risk. | Review signals and claim permission matrix. |
| Five full website builds before strategy | Wastes effort and compounds mediocre design. | Concept boards and decision matrices first, then primary/fallback prototype. |
| Full Amazon crawl before identity mapping | High risk of false joins and wasted scraping. | ASIN identity workflow, sample-first marketplace probe. |
""",
        encoding="utf-8",
    )

    design_rows = [
        {
            "design_route": "Room-first editorial commerce",
            "business_fit": "Strong",
            "where_it_uses_product_truth": "Shop by Room, playroom reset, kitchen helper, study corner",
            "visual_risk": "Can become bland if product imagery stays too small",
            "prototype_status": "Primary candidate",
        },
        {
            "design_route": "Giftable toy theater",
            "business_fit": "Strong for rockers and baby milestones",
            "where_it_uses_product_truth": "Pink Unicorn, rockers, baby walker, nursery moments",
            "visual_risk": "Can become childish or novelty-only",
            "prototype_status": "Fallback / homepage variant",
        },
        {
            "design_route": "Utility product system",
            "business_fit": "Strong for furniture and storage",
            "where_it_uses_product_truth": "Learning tower, shelf, storage, desk",
            "visual_risk": "May feel too functional and not premium enough",
            "prototype_status": "PDP and room-builder influence",
        },
        {
            "design_route": "AI-visible consumer site",
            "business_fit": "Rejected for DTC surface",
            "where_it_uses_product_truth": "None on consumer site",
            "visual_risk": "Confuses buyer journey and internal demo goals",
            "prototype_status": "Move to Boss Gallery",
        },
    ]
    write_csv(
        ROOT / "design_decision_matrix.csv",
        design_rows,
        ["design_route", "business_fit", "where_it_uses_product_truth", "visual_risk", "prototype_status"],
    )

    manifest = {
        "artifact": "commerce_decision_layer",
        "generated_at": "2026-04-27",
        "source_files": [
            "inputs/product_master_v0.csv",
            "inputs/downloaded_media_manifest.csv",
            "inputs/current_data_qa.md",
            "inputs/reference_pattern_mapping.md",
            "inputs/rejected_generic_patterns.md",
        ],
        "outputs": [
            "sample_selection_rationale.md",
            "category_portfolio_map.md",
            "shopper_mission_map.md",
            "sku_role_matrix.csv",
            "asset_readiness_matrix.csv",
            "claim_permission_matrix.csv",
            "hero_candidate_matrix.csv",
            "bundle_and_cross_sell_map.csv",
            "navigation_decision_matrix.md",
            "pdp_module_strategy_by_category.md",
            "rejected_direction_log.md",
            "design_decision_matrix.csv",
            "../sample_dossiers/*.md",
        ],
        "known_limits": [
            "No new external Amazon crawl was performed in this artifact.",
            "Safety, materials, dimensions, age range, certifications, and marketplace performance remain blocked pending evidence.",
            "Asset rights for scraped/AI-generated images remain usage-gated.",
        ],
    }
    (ROOT / "evidence_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (ROOT / "commerce_decision_layer_handoff.md").write_text(
        """# Commerce Decision Layer Handoff

Generated: 2026-04-27

## What This Layer Decides

- The first 8 SKU sample for prototype and boss-demo planning.
- Which product facts can be used safely.
- Which claims are blocked until more evidence exists.
- Which shopper missions should shape the DTC redesign.
- Which design directions are rejected so they do not keep returning.

## Next Implementation Step

Build DTC concept boards and then one primary prototype route:

1. Homepage with age/room/gift navigation.
2. Collection surfaces for Giftable Rockers, Pretend Play, Montessori at Home, Playroom Reset.
3. PDP templates for Pink Unicorn, Cream Play Kitchen, Learning Tower, Storage/Shelf.
4. Claim-safe data badges and source-aware product modules.
5. Mobile and desktop QA screenshots before any design is considered reviewable.

## Required Guardrails

- No AI/Paperclip workflow inside the consumer website.
- No fake reviews, ratings, certifications, awards, or market-performance claims.
- No full Amazon performance statement until ASIN identity workflow succeeds.
- Generated lifestyle assets must be labelled as prototype/synthetic in internal deliverables.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
