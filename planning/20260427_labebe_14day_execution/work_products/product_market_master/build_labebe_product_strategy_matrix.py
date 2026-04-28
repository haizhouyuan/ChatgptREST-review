#!/usr/bin/env python3
"""Build a product strategy matrix from DTC catalog and marketplace gates."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
LIVE_DIR = BASE / "live_crawl_20260428"

PRODUCT_MASTER = LIVE_DIR / "product_master_live_probe_v1.csv"
IDENTITY_LANES = LIVE_DIR / "amazon_identity_lanes_v1.csv"
CLAIM_GATE = LIVE_DIR / "amazon_claim_gate_v1.csv"


LANE_PRIORITY = {
    "identity_whitelist_candidate": 4,
    "variant_cluster_research": 3,
    "retry_or_provider_required": 2,
    "blocked_negative_example": 1,
}


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def classify_world(slug: str, title: str, probes: str) -> tuple[str, str]:
    text = f"{slug} {title} {probes}".lower()
    flags = {
        "Pretend Play Worlds": any(k in text for k in ["kitchen", "coffee", "grocery", "washer", "dryer", "bakery", "mud", "garden", "potting", "vanity"]),
        "Giftable Rockers": any(k in text for k in ["plush-rocker", "rocking-horse", "rocking-chair", "rocker", "rockers-ride-ons"]),
        "First Steps & Activity": any(k in text for k in ["push-walker", "activity-cube", "busy-board", "activity-wall", "spinner", "easel"]),
        "Playroom Reset": any(k in text for k in ["storage", "organizer", "shelf", "cabinet", "bookshelf", "stool"]),
        "Montessori Home & Study": any(k in text for k in ["learning-tower", "montessori", "desk", "chair", "study"]),
    }
    priority = [
        "Giftable Rockers",
        "First Steps & Activity",
        "Montessori Home & Study",
        "Pretend Play Worlds",
        "Playroom Reset",
    ]
    worlds = [name for name in priority if flags[name]]
    if not worlds:
        worlds = ["Assorted Play"]
    return worlds[0], ";".join(worlds[1:])


def dtc_signal_tier(review_count: object, catalog_scope: str) -> str:
    reviews = pd.to_numeric(pd.Series([review_count]), errors="coerce").iloc[0]
    if pd.isna(reviews):
        reviews = 0
    if catalog_scope == "regional_variant":
        return "regional_variant_do_not_hero"
    if reviews >= 9:
        return "strong_dtc_review_signal"
    if reviews >= 5:
        return "moderate_dtc_review_signal"
    if reviews > 0:
        return "light_dtc_review_signal"
    return "catalog_only_signal"


def marketplace_signal(row: dict[str, object]) -> str:
    lane = clean(row.get("amazon_identity_lane") or row.get("identity_lane"))
    reviews = pd.to_numeric(pd.Series([row.get("amazon_review_count") or row.get("pdp_review_count")]), errors="coerce").iloc[0]
    if pd.isna(reviews):
        reviews = 0
    if lane == "identity_whitelist_candidate":
        if reviews >= 500:
            return "strong_amazon_social_proof"
        if reviews >= 50:
            return "moderate_amazon_social_proof"
        return "light_amazon_social_proof"
    if lane == "variant_cluster_research":
        return "variant_cluster_not_exact"
    if lane == "retry_or_provider_required":
        return "marketplace_retry_required"
    if lane == "blocked_negative_example":
        return "blocked_wrong_match"
    return "no_marketplace_identity_yet"


def website_role(row: dict[str, object]) -> tuple[str, str, str]:
    world = row["primary_world"]
    dtc = row["dtc_signal_tier"]
    mkt = row["marketplace_signal_tier"]
    scope = row["catalog_scope"]
    title = row["title_clean"]

    if scope == "regional_variant":
        return (
            "do_not_hero",
            "Keep regional variants out of main US merchandising until locale/fulfillment is explicit.",
            "regional_scope_review",
        )
    if mkt == "blocked_wrong_match":
        return (
            "dtc_visible_marketplace_blocked",
            "The product can remain in DTC merchandising, but the current Amazon candidate is a known wrong match.",
            "keep_negative_example_and_restart_asin_discovery",
        )
    if mkt == "strong_amazon_social_proof" and world == "Giftable Rockers":
        return (
            "homepage_hero_or_best_seller",
            "Use as proof-rich giftable hero, but keep Amazon proof internal unless approved for public copy.",
            "prepare_pdp_story_and_review_voc_after_authorized_crawl",
        )
    if world == "Giftable Rockers" and mkt in {"moderate_amazon_social_proof", "light_amazon_social_proof"}:
        return (
            "best_seller_grid_and_gift_collection",
            "Build a plush-character collection with birthday/nursery gift framing.",
            "run_claim_gate_then_review_voc_seed_if_whitelisted",
        )
    if world == "Pretend Play Worlds" and "kitchen" in title.lower() and "identity_whitelist_candidate" == clean(row.get("amazon_identity_lane")):
        return (
            "category_anchor_pdp",
            "Use as the main pretend-play kitchen anchor with strong gallery and role-play modules.",
            "verify variant, specs, dimensions, and claims before production PDP copy",
        )
    if world == "First Steps & Activity":
        return (
            "family_collection_not_exact_marketplace_claim",
            "Show this as a real DTC family, but avoid exact Amazon proof until variant gates are resolved.",
            "build variant map and retry/provider identity capture",
        )
    if world == "Montessori Home & Study" and dtc in {"strong_dtc_review_signal", "moderate_dtc_review_signal"}:
        return (
            "navigation_and_room_solution_anchor",
            "Use for Shop by Room, playroom order, study corner, and parent utility narratives.",
            "recrawl PDP specs, dimensions, materials, care, and safety copy",
        )
    if world == "Playroom Reset":
        return (
            "supporting_collection_and_bundle",
            "Use to make the site feel like a room-planning destination rather than a toy grid.",
            "build bundle logic and storage/room fit facts",
        )
    if dtc == "strong_dtc_review_signal":
        return (
            "best_seller_grid",
            "DTC review count makes it useful for credibility, even without marketplace identity.",
            "recrawl PDP details and source claims",
        )
    return (
        "supporting_catalog_item",
        "Keep visible in collection grids; do not overclaim or hero until facts improve.",
        "collect PDP/spec/media facts in next crawl",
    )


def pick_identity_lane(identity: pd.DataFrame) -> dict[str, dict[str, object]]:
    best: dict[str, dict[str, object]] = {}
    for _, row in identity.iterrows():
        sku = clean(row.get("sku_id"))
        lane = clean(row.get("identity_lane"))
        score = LANE_PRIORITY.get(lane, 0)
        prev = best.get(sku)
        prev_score = LANE_PRIORITY.get(clean(prev.get("identity_lane")) if prev else "", 0)
        if prev is None or score > prev_score:
            best[sku] = row.to_dict()
    return best


def claim_summary(claims: pd.DataFrame) -> dict[str, str]:
    if claims.empty:
        return {}
    summaries: dict[str, str] = {}
    for sku, group in claims.groupby("sku_id"):
        counts = group["decision"].value_counts().to_dict()
        parts = [f"{key}:{value}" for key, value in sorted(counts.items())]
        summaries[str(sku)] = ";".join(parts)
    return summaries


def main() -> None:
    products = pd.read_csv(PRODUCT_MASTER)
    identity = pd.read_csv(IDENTITY_LANES)
    claims = pd.read_csv(CLAIM_GATE) if CLAIM_GATE.exists() else pd.DataFrame()
    identity_by_sku = pick_identity_lane(identity)
    claim_by_sku = claim_summary(claims)

    rows: list[dict[str, object]] = []
    for _, product in products.iterrows():
        sku = clean(product.get("sku_id"))
        identity_row = identity_by_sku.get(sku, {})
        primary_world, secondary_worlds = classify_world(
            sku,
            clean(product.get("title_clean")),
            clean(product.get("collection_probes_seen")),
        )
        base = {
            "sku_id": sku,
            "title_clean": clean(product.get("title_clean")),
            "primary_world": primary_world,
            "secondary_worlds": secondary_worlds,
            "catalog_scope": clean(product.get("catalog_scope")),
            "catalog_caveat": clean(product.get("catalog_caveat")),
            "collection_probes_seen": clean(product.get("collection_probes_seen")),
            "product_url": clean(product.get("product_url")),
            "price_current": clean(product.get("price_current")),
            "price_original": clean(product.get("price_original")),
            "dtc_review_count_visible": clean(product.get("review_count_visible")).replace(".0", ""),
            "dtc_signal_tier": dtc_signal_tier(product.get("review_count_visible"), clean(product.get("catalog_scope"))),
            "amazon_identity_lane": clean(identity_row.get("identity_lane")) or "no_marketplace_identity_yet",
            "asin": clean(identity_row.get("asin")),
            "amazon_rating": clean(identity_row.get("pdp_rating")),
            "amazon_review_count": clean(identity_row.get("pdp_review_count")).replace(".0", ""),
            "amazon_sold_by": clean(identity_row.get("sold_by")),
            "amazon_probe_quality": clean(identity_row.get("probe_quality")),
            "claim_gate_summary": claim_by_sku.get(sku, ""),
        }
        base["marketplace_signal_tier"] = marketplace_signal(base)
        role, implication, action = website_role(base)
        base["website_role"] = role
        base["design_implication"] = implication
        base["next_data_action"] = action
        rows.append(base)

    out_csv = LIVE_DIR / "labebe_product_strategy_matrix_v1.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    df = pd.DataFrame(rows)
    world_counts = df["primary_world"].value_counts().to_dict()
    role_counts = df["website_role"].value_counts().to_dict()
    lane_counts = df["amazon_identity_lane"].value_counts().to_dict()
    signal_counts = df["marketplace_signal_tier"].value_counts().to_dict()
    hero = df[
        df["website_role"].isin(["homepage_hero_or_best_seller", "best_seller_grid_and_gift_collection", "category_anchor_pdp"])
    ].copy()
    hero = hero.sort_values(["website_role", "amazon_review_count", "dtc_review_count_visible"], ascending=[True, False, False])

    report = LIVE_DIR / "labebe_product_strategy_matrix_v1.md"
    lines = [
        "# Labebe Product Strategy Matrix v1",
        "",
        "Date: 2026-04-28",
        "",
        "## Scope",
        "",
        "This matrix combines the live Labebe DTC catalog probe, Amazon identity lanes, visual review, PDP facts, and claim gate into a site-design decision layer.",
        "",
        "It is an internal planning artifact. It does not authorize public marketplace claims, safety claims, certification claims, or customer review reuse.",
        "",
        "## Product World Counts",
        "",
    ]
    for key, value in world_counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Website Role Counts", ""])
    for key, value in role_counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Amazon Identity Lane Counts", ""])
    for key, value in lane_counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Marketplace Signal Counts", ""])
    for key, value in signal_counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Current Design Decisions",
            "",
            "- Giftable Rockers are the strongest proof-rich hero category because they combine visual character, DTC reviews, and multiple Amazon identity-whitelist candidates.",
            "- Pretend Play should be anchored by Cream Wooden Play Kitchen, with the black and gray kitchen variants treated carefully as separate DTC variants, not as the same Amazon ASIN.",
            "- First Steps & Activity is a real DTC family, but Amazon evidence is variant-clustered. It can become a shopping world, but not a marketplace-proof story yet.",
            "- Montessori Home & Study and Playroom Reset are important for site architecture and parent utility, but need PDP/spec recrawl before strong claims.",
            "- Regional variants and site-all-only rows should not become homepage heroes until category, locale, and fulfillment are confirmed.",
            "",
            "## Hero / Anchor Candidates",
            "",
            "| SKU | World | Role | DTC reviews | Amazon ASIN | Amazon reviews | Seller | Next action |",
            "|---|---|---|---:|---|---:|---|---|",
        ]
    )
    for _, row in hero.head(16).iterrows():
        lines.append(
            f"| `{row['sku_id']}` | {row['primary_world']} | {row['website_role']} | {row['dtc_review_count_visible'] or ''} | `{row['asin']}` | {row['amazon_review_count'] or ''} | {row['amazon_sold_by'] or ''} | {row['next_data_action']} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- `{out_csv.name}`",
            f"- `{report.name}`",
        ]
    )
    report.write_text("\n".join(lines), encoding="utf-8")
    print({"csv": str(out_csv), "report": str(report), "rows": len(rows)})


if __name__ == "__main__":
    main()
