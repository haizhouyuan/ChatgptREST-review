#!/usr/bin/env python3
"""Create marketplace listing fact and claim-gate tables from browser probes."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
LIVE_DIR = BASE / "live_crawl_20260428"

ASIN_TO_SKU = {
    "B072LXVM36": {
        "sku_id": "pink-unicorn-plush-rocker",
        "identity_status": "accepted_browser_visual_sample",
    },
    "B0FH1KX7XQ": {
        "sku_id": "cream-wooden-play-kitchen-set-with-storage",
        "identity_status": "accepted_browser_visual_sample",
    },
    "B07MFXJ28Y": {
        "sku_id": "llama-plush-rocker",
        "identity_status": "accepted_browser_visual_sample",
    },
    "B0DSVJB5QH": {
        "sku_id": "fox-plush-rocker",
        "identity_status": "accepted_but_search_mismatch_source",
    },
    "B087P9SXZQ": {
        "sku_id": "doll-stroller-baby-push-walker",
        "identity_status": "candidate_visual_conflict",
    },
}


def clean_int(value: str) -> str:
    match = re.search(r"[\d,]+", str(value or ""))
    return match.group(0).replace(",", "") if match else ""


def clean_float(value: str) -> str:
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return match.group(0) if match else ""


def dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in seq:
        item = re.sub(r"\s+", " ", str(item or "")).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def classify_claim(text: str) -> tuple[str, str, str]:
    lower = text.lower()
    if re.search(r"\b(certified|astm|en-?71|ce)\b|safety standards?", lower):
        return "safety_certification", "blocked_for_dtc_reuse", "Safety/certification claim needs official source and manual review."
    if any(x in lower for x in ["award", "winning"]):
        return "award_design", "blocked_for_dtc_reuse", "Award/design-origin claim needs independent evidence."
    if any(x in lower for x in ["150 lb", "max weight", "capacity"]):
        return "weight_capacity", "manual_review_required", "Capacity claim needs official spec verification."
    if any(x in lower for x in ["safety belt", "protected", "prevent bumps", "prevent", "tipping", "baby skin"]):
        return "safety_general", "manual_review_required", "Safety-oriented seller claim needs official support and softened wording."
    if any(x in lower for x in ["help train", "develop balance", "promote", "strengthens", "healthy growth"]):
        return "development_benefit", "manual_review_required", "Development-benefit claim needs softened language and review."
    if any(x in lower for x in ["solid wood", "mdf", "pp cotton", "material", "fabric"]):
        return "materials", "manual_review_required", "Material claim needs official product/spec source."
    if any(x in lower for x in ["gift", "birthday", "christmas", "holidays"]):
        return "gift_angle", "allowed_as_marketing_angle", "Gift positioning is allowed if not presented as performance proof."
    return "listing_copy", "internal_reference_only", "Seller listing copy is not automatically reusable as DTC truth."


def main() -> None:
    listing_rows = []
    claim_rows = []
    review_gate_rows = []
    generated_at = datetime.now(timezone.utc).isoformat()

    for asin, mapping in ASIN_TO_SKU.items():
        path = LIVE_DIR / f"amazon_{asin}_structured.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        sku_id = mapping["sku_id"]
        identity_status = mapping["identity_status"]
        listing_rows.append(
            {
                "sku_id": sku_id,
                "asin": asin,
                "marketplace": "Amazon US",
                "identity_status": identity_status,
                "amazon_url": data.get("url", f"https://www.amazon.com/dp/{asin}"),
                "title": data.get("title", ""),
                "brand_store_text": data.get("brand_store_text", ""),
                "price": data.get("price", ""),
                "rating": clean_float(data.get("rating_text", "")),
                "review_count": clean_int(data.get("review_count_text", "")),
                "bought_past_month": data.get("bought_past_month", ""),
                "ships_from": data.get("ships_from", ""),
                "sold_by": data.get("sold_by", ""),
                "availability": data.get("availability", ""),
                "breadcrumbs_json": json.dumps(data.get("breadcrumbs", []), ensure_ascii=False),
                "image_count": data.get("image_count", ""),
                "source_json": str(path),
                "source_screenshot": f"/vol1/1000/projects/toyresearch/qa/marketplace_probe/amazon_{asin}_structured.png",
                "observed_at": data.get("captured_at", generated_at),
                "allowed_use": "listing_fact_for_accepted_sample" if identity_status.startswith("accepted") else "candidate_only_do_not_use_for_dtc",
            }
        )

        for idx, bullet in enumerate(dedupe(data.get("bullets", [])), start=1):
            claim_type, decision, reason = classify_claim(bullet)
            claim_rows.append(
                {
                    "claim_id": f"{asin}-bullet-{idx:02d}",
                    "sku_id": sku_id,
                    "asin": asin,
                    "claim_text": bullet,
                    "claim_type": claim_type,
                    "source_surface": "Amazon PDP feature bullets",
                    "identity_status": identity_status,
                    "decision": decision,
                    "reason": reason,
                    "source_json": str(path),
                    "observed_at": data.get("captured_at", generated_at),
                }
            )

        review_path = LIVE_DIR / f"amazon_{asin}_reviews_browser.json"
        if review_path.exists():
            review_data = json.loads(review_path.read_text(encoding="utf-8"))
            if review_data.get("review_count_extracted", 0):
                gate = "browser_reviews_extracted"
                next_action = "Normalize review records, then run VOC pilot."
            elif "Sign in" in str(review_data.get("document_title", "")) or "Sign in or create account" in str(review_data.get("visible_text_sample", "")):
                gate = "blocked_browser_redirected_to_sign_in"
                next_action = "Use Apify/product-data API or controlled logged-in browser profile for reviews."
            else:
                gate = "blocked_no_reviews_extracted"
                next_action = "Inspect screenshot and try authorized review pipeline."
            review_gate_rows.append(
                {
                    "sku_id": sku_id,
                    "asin": asin,
                    "identity_status": identity_status,
                    "review_probe_path": str(review_path),
                    "review_probe_screenshot": f"/vol1/1000/projects/toyresearch/qa/marketplace_probe/amazon_{asin}_reviews_browser.png",
                    "review_count_extracted": review_data.get("review_count_extracted", 0),
                    "gate": gate,
                    "next_action": next_action,
                    "observed_at": review_data.get("captured_at", generated_at),
                }
            )

    listing_path = LIVE_DIR / "amazon_listing_facts_v1.csv"
    claim_path = LIVE_DIR / "amazon_claim_gate_v1.csv"
    review_gate_path = LIVE_DIR / "amazon_review_crawl_gate_v1.csv"

    pd.DataFrame(listing_rows).to_csv(listing_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(claim_rows).to_csv(claim_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(review_gate_rows).to_csv(review_gate_path, index=False, encoding="utf-8-sig")

    summary = {
        "generated_at": generated_at,
        "listing_rows": len(listing_rows),
        "claim_rows": len(claim_rows),
        "review_gate_rows": len(review_gate_rows),
        "outputs": [str(listing_path), str(claim_path), str(review_gate_path)],
    }
    (LIVE_DIR / "marketplace_fact_tables_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
