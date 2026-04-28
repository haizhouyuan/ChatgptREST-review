#!/usr/bin/env python3
"""Build consumable outputs from the 2026-04-28 live catalog probe."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
LIVE_DIR = BASE / "live_crawl_20260428"
LIVE_CSV = LIVE_DIR / "labebe_products_live_probe.csv"
OLD_DIFF_CSV = LIVE_DIR / "labebe_old_vs_live_slug_diff.csv"
OLD_MASTER_CSV = BASE.parent / "product_data_qa" / "product_master_v0_draft.csv"
QA_MARKETPLACE_DIR = Path("/vol1/1000/projects/toyresearch/qa/marketplace_probe")
IMAGE_IDENTITY_CSV = LIVE_DIR / "image_identity_sample" / "amazon_dtc_image_identity_sample.csv"

ASIN_IDENTITY_RECORDS = [
    {
        "sku_id": "pink-unicorn-plush-rocker",
        "dtc_title": "Pink Unicorn Plush Rocker",
        "candidate_asin": "B072LXVM36",
        "identity_status": "accepted_browser_visual_sample",
        "match_score": 92,
        "match_reason": "Browser Harness captured Amazon PDP with labebe Store, pink unicorn rocker title, price, rating, review count and bought-past-month signal; contact-sheet review shows same pink unicorn rocker with different scene crop.",
        "blocking_conflicts": "Still timestamp Amazon facts; do not reuse volatile badges or unsupported award/safety claims without separate review.",
        "allowed_use_now": "Use as accepted sample for Amazon listing facts and review-crawl pilot with screenshot/contact-sheet evidence.",
        "next_action": "Run review crawl pilot for this ASIN through an authorized review pipeline, then summarize VOC with source labels.",
        "visual_match_status": "human_accepted_same_product_scene_differs",
        "visual_match_note": "Contact sheet shows the same pink unicorn rocker; Amazon uses a lifestyle child-riding image while DTC local image is product-only.",
    },
    {
        "sku_id": "cream-wooden-play-kitchen-set-with-storage",
        "dtc_title": "Cream Wooden Play Kitchen Set with Storage",
        "candidate_asin": "B0FH1KX7XQ",
        "identity_status": "accepted_browser_visual_sample",
        "match_score": 91,
        "match_reason": "Amazon PDP and DTC image show the same cream wooden play kitchen layout, storage boxes, sink, stove, ice maker, and upper cabinet structure.",
        "blocking_conflicts": "Amazon price is displayed in JPY in the current browser region; use PDP title/rating/review as marketplace evidence, not regional search-page price.",
        "allowed_use_now": "Use as accepted marketplace listing sample after claim gate; do not reuse ASTM/EN71 or safety claims without official source verification.",
        "next_action": "Run claim gate and authorized review/VOC extraction for this ASIN before using marketplace reviews.",
        "visual_match_status": "human_accepted_same_product",
        "visual_match_note": "Browser screenshot and DTC product image show the same cream play kitchen product.",
    },
    {
        "sku_id": "llama-plush-rocker",
        "dtc_title": "Llama Plush Rocker",
        "candidate_asin": "B07MFXJ28Y",
        "identity_status": "accepted_browser_visual_sample",
        "match_score": 88,
        "match_reason": "Amazon PDP is a labebe white llama plush rocker sold by Labebe Store and visually matches the Labebe llama rocker family.",
        "blocking_conflicts": "Amazon listing includes award/origin/safety-oriented claims that require claim-gate review before reuse.",
        "allowed_use_now": "Use as accepted marketplace listing sample and review-crawl candidate; public DTC copy must stay source-gated.",
        "next_action": "Run authorized review/VOC extraction and add image contact sheet in the next batch.",
        "visual_match_status": "human_accepted_same_product_family",
        "visual_match_note": "Amazon screenshot shows the same white llama plush rocker product family.",
    },
    {
        "sku_id": "fox-plush-rocker",
        "dtc_title": "Fox Plush Rocker",
        "candidate_asin": "B0DSVJB5QH",
        "identity_status": "accepted_but_search_mismatch_source",
        "match_score": 82,
        "match_reason": "The ASIN is a labebe Fox Rocking Horse PDP sold by Labebe Store. It was found during a Highlander search, so it is accepted for Fox only, not Highlander.",
        "blocking_conflicts": "Search query mismatch; do not map this ASIN to Highlander Cattle Plush Rocker.",
        "allowed_use_now": "Use as Fox marketplace listing sample only. Treat the originating Highlander search result as a search-candidate false positive.",
        "next_action": "Search Highlander separately and add image contact sheet before any broader rocker-family conclusions.",
        "visual_match_status": "human_accepted_for_fox_only",
        "visual_match_note": "Browser screenshot shows brownish red fox rocker; not the Highlander cattle rocker.",
    },
    {
        "sku_id": "activity-cube-baby-push-walker",
        "dtc_title": "Activity Cube Baby Push Walker",
        "candidate_asin": "B087P9SXZQ",
        "identity_status": "rejected_for_current_dtc_sku",
        "match_score": 38,
        "match_reason": "Both are Labebe push-walker family products, but title/function differs from current Activity Cube Baby Push Walker.",
        "blocking_conflicts": "Likely legacy/orphan marketplace SKU or different walker variant; not safe to map to current DTC activity-cube SKU.",
        "allowed_use_now": "Keep as marketplace orphan sample for review pipeline testing only.",
        "next_action": "Create marketplace_orphan row; search current push-walker variants separately.",
        "visual_match_status": "not_compared_rejected_by_title",
        "visual_match_note": "Amazon title is Doll Stroller / Shopping Cart walker, not Activity Cube Baby Push Walker.",
    },
    {
        "sku_id": "doll-stroller-baby-push-walker",
        "dtc_title": "Doll Stroller Baby Push Walker",
        "candidate_asin": "B087P9SXZQ",
        "identity_status": "candidate_visual_conflict",
        "match_score": 55,
        "match_reason": "Live DTC probe found a Doll Stroller Baby Push Walker and Browser Harness captured a similar Amazon title, but the contact sheet shows a materially different product image/variant.",
        "blocking_conflicts": "Seller is Pretty valley rather than Labebe Store; DTC image and Amazon image conflict; do not attach reviews to DTC SKU.",
        "allowed_use_now": "Use only as marketplace method-test candidate; do not use review/VOC as DTC product evidence.",
        "next_action": "Search additional DTC gallery images and Amazon variations; require visual match before promotion.",
        "visual_match_status": "visual_mismatch_or_different_asset_needs_review",
        "visual_match_note": "Contact sheet shows a different walker/stroller visual; title family is similar but image conflict blocks DTC mapping.",
    },
    {
        "sku_id": "foldable-learning-tower-montessori-kitchen-tower-log-color",
        "dtc_title": "Foldable Learning Tower & Montessori Kitchen Tower (Log Color)",
        "candidate_asin": "",
        "identity_status": "no_match_us_sample",
        "match_score": 0,
        "match_reason": "Search returned weak/no canonical candidate; live DTC also shows multiple log/unicorn/slide/regional variants.",
        "blocking_conflicts": "Variant explosion; US/EU slug differences; no ASIN.",
        "allowed_use_now": "DTC-only design and product facts.",
        "next_action": "Search variant family with image matching; keep each learning-tower color/region separate.",
        "visual_match_status": "",
        "visual_match_note": "",
    },
    {
        "sku_id": "kids-toy-storage-organizer-bookshelf-with-bins",
        "dtc_title": "Kids Toy Storage Organizer & Bookshelf with Bins",
        "candidate_asin": "",
        "identity_status": "no_match_us_sample",
        "match_score": 0,
        "match_reason": "Furniture/storage titles are too generic; must use image and seller evidence.",
        "blocking_conflicts": "No ASIN, possible title ambiguity.",
        "allowed_use_now": "DTC-only design and category architecture.",
        "next_action": "Use image matching plus Amazon search API/provider; avoid review claims.",
        "visual_match_status": "",
        "visual_match_note": "",
    },
]


def classify_scope(row: pd.Series) -> tuple[str, str]:
    slug = str(row["slug"])
    title = str(row["title_clean_probe"])
    collections = str(row.get("collection_probes_seen") or "")

    if "payment" in slug or "shipping-fee" in slug:
        return "non_product", "Payment/order adjustment row; exclude from product design and catalog counts."
    if slug.endswith("-eu") or "(EU)" in title or " EU" in title or slug.endswith("-eu-"):
        return "regional_variant", "EU/regional variant; keep separate from US DTC and Amazon US identity."
    if "all" in collections and collections == "all":
        return "site_all_only", "Observed on all-products page only; needs category placement confirmation."
    return "core_product", "Observed in category probe; usable for DTC fact layer after PDP/spec recrawl."


def build_product_master() -> pd.DataFrame:
    live = pd.read_csv(LIVE_CSV)
    rows = []
    observed_batch = "labebe_live_probe_20260428"
    for _, row in live.iterrows():
        scope, caveat = classify_scope(row)
        price = str(row.get("price_current_probe") or "").replace("$", "").replace(",", "")
        original = str(row.get("price_original_probe") or "").replace("$", "").replace(",", "")
        rows.append(
            {
                "sku_id": row["slug"],
                "canonical_slug": row["slug"],
                "title_clean": row["title_clean_probe"],
                "collection_probe": row["collection_probe"],
                "collection_probes_seen": row.get("collection_probes_seen", ""),
                "product_url": row["product_url"],
                "currency": "USD",
                "price_current": price,
                "price_original": original,
                "discount_listed": row.get("discount_probe", ""),
                "review_count_visible": row.get("reviews_count_probe", ""),
                "primary_image_url_probe": row.get("image_url_probe", ""),
                "catalog_scope": scope,
                "catalog_caveat": caveat,
                "source_domain": "labebeclub.com",
                "observed_at": row["observed_at"],
                "scrape_batch_id": observed_batch,
                "promotion_status": "probe_only_needs_pdp_specs_claim_gate",
            }
        )
    return pd.DataFrame(rows)


def build_old_vs_live_diff() -> pd.DataFrame:
    old = pd.read_csv(OLD_MASTER_CSV)
    live = pd.read_csv(LIVE_CSV)
    old_slugs = set(old["slug_csv"])
    live_slugs = set(live["slug"])
    rows = []
    for slug in sorted(old_slugs | live_slugs):
        old_row = old[old["slug_csv"].eq(slug)].head(1)
        live_row = live[live["slug"].eq(slug)].head(1)
        if slug in old_slugs and slug not in live_slugs:
            status = "old_only_not_seen_live_probe"
        elif slug in live_slugs and slug not in old_slugs:
            status = "new_or_previously_missing_live_probe"
        else:
            status = "seen_in_both"
        rows.append(
            {
                "slug": slug,
                "status": status,
                "old_title": old_row["name_clean"].iloc[0] if len(old_row) else "",
                "live_title": live_row["title_clean_probe"].iloc[0] if len(live_row) else "",
                "old_price": old_row["current_price_usd"].iloc[0] if len(old_row) else "",
                "live_price": live_row["price_current_probe"].iloc[0] if len(live_row) else "",
                "old_reviews": old_row["reviews_count_listing"].iloc[0] if len(old_row) else "",
                "live_reviews": live_row["reviews_count_probe"].iloc[0] if len(live_row) else "",
                "live_collections": live_row["collection_probes_seen"].iloc[0] if len(live_row) else "",
                "live_url": live_row["product_url"].iloc[0]
                if len(live_row)
                else (old_row["product_url"].iloc[0] if len(old_row) else ""),
            }
        )
    diff = pd.DataFrame(rows)
    diff.to_csv(OLD_DIFF_CSV, index=False, encoding="utf-8-sig")

    summary = {
        "old_count": len(old_slugs),
        "live_count": len(live_slugs),
        "intersection_count": len(old_slugs & live_slugs),
        "old_only_count": len(old_slugs - live_slugs),
        "live_only_count": len(live_slugs - old_slugs),
        "diff_csv": str(OLD_DIFF_CSV),
    }
    (LIVE_DIR / "old_vs_live_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return diff


def build_asin_sample() -> pd.DataFrame:
    browser_facts = build_amazon_browser_facts()
    image_status = build_image_identity_status()
    rows = []
    for record in ASIN_IDENTITY_RECORDS:
        asin = record["candidate_asin"]
        row = {
            "sku_id": record["sku_id"],
            "dtc_title": record["dtc_title"],
            "candidate_marketplace": "Amazon US",
            "candidate_asin": asin,
            "candidate_marketplace_url": f"https://www.amazon.com/dp/{asin}" if asin else "",
            "candidate_title_or_source_signal": browser_facts.get(asin, {}).get("amazon_title", "No reliable canonical Amazon US candidate captured in current sample.") if asin else "No reliable canonical Amazon US candidate captured in current sample.",
            "identity_status": record["identity_status"],
            "match_score": record["match_score"],
            "match_reason": record["match_reason"],
            "blocking_conflicts": record["blocking_conflicts"],
            "allowed_use_now": record["allowed_use_now"],
            "next_action": record["next_action"],
            "visual_match_status": record["visual_match_status"] or image_status.get(asin, {}).get("visual_match_status", ""),
            "visual_match_note": record["visual_match_note"] or image_status.get(asin, {}).get("human_review_note", ""),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def build_image_identity_status() -> dict[str, dict[str, str]]:
    if not IMAGE_IDENTITY_CSV.exists():
        return {}
    df = pd.read_csv(IMAGE_IDENTITY_CSV)
    out: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        asin = str(row.get("asin") or "")
        status = str(row.get("visual_match_status") or "")
        note = str(row.get("note") or "")
        if asin == "B072LXVM36":
            note = "Contact sheet shows the same pink unicorn rocker; Amazon uses a lifestyle child-riding image while DTC local image is product-only."
        elif asin == "B087P9SXZQ":
            note = "Contact sheet shows a different walker/stroller visual; title family is similar but image conflict blocks DTC mapping."
        out[asin] = {
            "visual_match_status": status,
            "human_review_note": note,
        }
    return out


def extract_pattern(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.S)
    return match.group(1).strip() if match else ""


def build_amazon_browser_facts() -> dict[str, dict[str, str]]:
    facts: dict[str, dict[str, str]] = {}
    for asin in sorted({record["candidate_asin"] for record in ASIN_IDENTITY_RECORDS if record["candidate_asin"]}):
        structured_path = LIVE_DIR / f"amazon_{asin}_structured.json"
        metrics_path = QA_MARKETPLACE_DIR / f"amazon_{asin}_metrics_wait.json"
        screenshot_path = QA_MARKETPLACE_DIR / f"amazon_{asin}_desktop_wait.png"
        if structured_path.exists():
            try:
                data = json.loads(structured_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
            facts[asin] = {
                "asin": asin,
                "amazon_url": data.get("url", f"https://www.amazon.com/dp/{asin}"),
                "amazon_title": data.get("title", ""),
                "price": data.get("price", ""),
                "rating": data.get("rating_text", "").replace(" out of 5 stars", ""),
                "review_count": str(data.get("review_count_text", "")).strip("()"),
                "bought_past_month": data.get("bought_past_month", ""),
                "sold_by": data.get("sold_by", ""),
                "ships_from": data.get("ships_from", ""),
                "screenshot_path": str(QA_MARKETPLACE_DIR / f"amazon_{asin}_structured.png"),
                "metrics_path": str(structured_path),
                "captured_with": "Amazon structured Browser Harness CDP desktop UA",
            }
            continue
        if not metrics_path.exists():
            continue
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        text = metrics.get("visibleText", "")
        rating = extract_pattern(text, r"(\d\.\d) out of 5 stars")
        review_count = extract_pattern(text, r"out of 5 stars\s+\(?\s*([\d,]+)\)?")
        bought_past_month = extract_pattern(text, r"([\d,]+\+ bought in past month)")
        sold_by = extract_pattern(text, r"Sold by\s+([^\n]+)")
        ships_from = extract_pattern(text, r"Ships from\s+([^\n]+)")
        price = extract_pattern(text, r"(\$\d+\.\d\d)")
        facts[asin] = {
            "asin": asin,
            "amazon_url": metrics.get("url", f"https://www.amazon.com/dp/{asin}"),
            "amazon_title": metrics.get("title", ""),
            "price": price,
            "rating": rating,
            "review_count": review_count,
            "bought_past_month": bought_past_month,
            "sold_by": sold_by,
            "ships_from": ships_from,
            "screenshot_path": str(screenshot_path),
            "metrics_path": str(metrics_path),
            "captured_with": "Browser Harness CDP headless wait 6s",
        }
    return facts


def write_markdown_report(product_master: pd.DataFrame, asin_sample: pd.DataFrame) -> None:
    diff = pd.read_csv(OLD_DIFF_CSV)
    summary = json.loads((LIVE_DIR / "old_vs_live_summary.json").read_text(encoding="utf-8"))
    live_only = diff[diff["status"].eq("new_or_previously_missing_live_probe")]
    old_only = diff[diff["status"].eq("old_only_not_seen_live_probe")]
    core = product_master[product_master["catalog_scope"].eq("core_product")]
    regional = product_master[product_master["catalog_scope"].eq("regional_variant")]
    non_product = product_master[product_master["catalog_scope"].eq("non_product")]
    site_all_only = product_master[product_master["catalog_scope"].eq("site_all_only")]
    browser_facts = pd.DataFrame(build_amazon_browser_facts().values())
    image_identity = pd.read_csv(IMAGE_IDENTITY_CSV) if IMAGE_IDENTITY_CSV.exists() else pd.DataFrame()

    lines = [
        "# Product Fact Execution Update 2026-04-28",
        "",
        "## What Changed",
        "",
        "- A non-destructive live Labebe catalog probe was run against current collection pages.",
        f"- The previous local DTC table had {summary['old_count']} product slugs; the live probe found {summary['live_count']} unique slugs.",
        f"- {summary['intersection_count']} previous slugs were still observed; {summary['live_only_count']} additional slugs appeared in the live probe.",
        f"- {summary['old_only_count']} previous slugs were not observed in this live probe.",
        "- The extra rows include regional EU variants, new baby-push-walker variants, and site-all-only rows needing category confirmation.",
        "",
        "## Catalog Scope Counts",
        "",
        f"- Total live probe rows: {len(product_master)}",
        f"- Core products observed in category probes: {len(core)}",
        f"- Regional variants: {len(regional)}",
        f"- Site all-only rows needing category confirmation: {len(site_all_only)}",
        f"- Non-product rows to exclude: {len(non_product)}",
        "",
        "## Live-Only Rows",
        "",
        live_only[["slug", "live_title", "live_price", "live_collections"]].to_markdown(index=False),
        "",
        "## Amazon / Marketplace Gate 1 Result",
        "",
        "Direct Amazon HTML access via curl returned anti-bot/CloudFront 503, so curl is not the default extraction path.",
        "Browser Harness with headless Chrome and explicit wait states successfully captured canonical Amazon PDP text/screenshots for five ASINs.",
        "The existing Apify review export remains useful for review pipeline testing, but review crawling should still wait for accepted/probable identity.",
        "",
        "### Browser-Captured Amazon Facts",
        "",
        browser_facts[[
            "asin",
            "price",
            "rating",
            "review_count",
            "bought_past_month",
            "sold_by",
            "ships_from",
        ]].to_markdown(index=False) if not browser_facts.empty else "No browser facts captured.",
        "",
        "### Image Identity Triage",
        "",
        image_identity[[
            "sku_id",
            "asin",
            "hash_similarity",
            "color_similarity",
            "visual_match_status",
        ]].to_markdown(index=False) if not image_identity.empty else "No image triage generated.",
        "",
        "Human review of screenshots and contact sheets overrides raw similarity scores where the product is clearly the same but the scene differs. Pink Unicorn, Cream Play Kitchen, Llama Rocker, and Fox Rocker now have accepted sample status. `B087P9SXZQ` remains blocked by visual conflict for DTC push-walker reuse.",
        "",
        asin_sample[[
            "sku_id",
            "candidate_asin",
            "identity_status",
            "match_score",
            "visual_match_status",
            "allowed_use_now",
        ]].to_markdown(index=False),
        "",
        "## Decision",
        "",
        "Gate 1 is passed for DTC catalog recrawl. Marketplace identity now has four accepted Amazon samples, one search-mismatch warning sample, and one visual-conflict sample. This is enough for a controlled review/VOC pilot, not for broad review crawling.",
        "The next efficient path is:",
        "",
        "1. Promote the live Labebe category union as the current DTC catalog probe.",
        "2. Exclude non-product/payment rows from product design.",
        "3. Keep EU/regional variants separate from US DTC and Amazon US matching.",
        "4. Use Browser Harness with wait-state detection as the default ASIN evidence path; keep paid product-data provider as fallback.",
        "5. Product-detail pages are browser-capturable, but direct browser access to `/product-reviews/<ASIN>` redirected to Amazon sign-in in this run.",
        "6. Run review crawlers only through an authorized review pipeline such as Apify/product-data API or a controlled logged-in browser profile, and only for accepted ASINs first.",
        "",
        "## Files",
        "",
        "- `live_labebe_catalog_probe.py`",
        "- `live_crawl_20260428/labebe_products_live_probe.csv`",
        "- `live_crawl_20260428/labebe_old_vs_live_slug_diff.csv`",
        "- `live_crawl_20260428/product_master_live_probe_v1.csv`",
        "- `live_crawl_20260428/amazon_identity_sample_v2.csv`",
        "- `live_crawl_20260428/amazon_browser_identity_facts_v1.csv`",
        "- `live_crawl_20260428/amazon_listing_facts_v1.csv`",
        "- `live_crawl_20260428/amazon_claim_gate_v1.csv`",
        "- `live_crawl_20260428/amazon_review_crawl_gate_v1.csv`",
        "- `live_crawl_20260428/image_identity_sample/amazon_dtc_image_identity_sample.csv`",
        "- `live_crawl_20260428/image_identity_sample/amazon_dtc_image_identity_contact_sheet.jpg`",
        "- `live_crawl_20260428/amazon_B072LXVM36_reviews_browser.json`",
        "- `qa/marketplace_probe/amazon_B072LXVM36_reviews_browser.png`",
        "- `qa/marketplace_probe/amazon_B072LXVM36_desktop_wait.png`",
        "- `qa/marketplace_probe/amazon_B087P9SXZQ_desktop_wait.png`",
    ]
    (LIVE_DIR / "product_fact_execution_update_20260428.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    build_old_vs_live_diff()
    product_master = build_product_master()
    asin_sample = build_asin_sample()
    amazon_browser_facts = pd.DataFrame(build_amazon_browser_facts().values())
    product_master.to_csv(LIVE_DIR / "product_master_live_probe_v1.csv", index=False, encoding="utf-8-sig")
    asin_sample.to_csv(LIVE_DIR / "amazon_identity_sample_v2.csv", index=False, encoding="utf-8-sig")
    amazon_browser_facts.to_csv(LIVE_DIR / "amazon_browser_identity_facts_v1.csv", index=False, encoding="utf-8-sig")
    write_markdown_report(product_master, asin_sample)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": [str(LIVE_CSV), str(OLD_DIFF_CSV), "data/amazon_reviews_US_B087P9SXZQ.csv"],
        "outputs": [
            str(LIVE_DIR / "product_master_live_probe_v1.csv"),
            str(LIVE_DIR / "amazon_identity_sample_v2.csv"),
            str(LIVE_DIR / "amazon_browser_identity_facts_v1.csv"),
            str(LIVE_DIR / "product_fact_execution_update_20260428.md"),
        ],
        "gate_result": "dtc_live_probe_passed_marketplace_identity_sample_partially_passed_not_ready_for_full_review_crawl",
    }
    (LIVE_DIR / "execution_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
