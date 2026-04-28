#!/usr/bin/env python3
"""Build identity promotion lanes from human visual review and PDP facts."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
LIVE_DIR = BASE / "live_crawl_20260428"

HUMAN_REVIEW = LIVE_DIR / "amazon_dtc_visual_human_review_v1.csv"
PDP_FACTS = LIVE_DIR / "amazon_pdp_probe_facts_v1.csv"


def clean_value(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def lane_for(row: dict[str, str]) -> tuple[str, str]:
    status = row["human_review_status"]
    if status == "human_confirmed_same_product":
        return "identity_whitelist_candidate", "eligible_after_claim_gate"
    if status in {"human_variant_cluster_probable", "human_variant_cluster_not_exact"}:
        return "variant_cluster_research", "no_exact_sku_claim"
    if status == "human_retry_required":
        return "retry_or_provider_required", "no_review_crawl"
    return "blocked_negative_example", "do_not_use"


def main() -> None:
    human_rows = list(csv.DictReader(HUMAN_REVIEW.open(encoding="utf-8")))
    facts = pd.read_csv(PDP_FACTS).set_index("asin").to_dict("index")
    out_rows: list[dict[str, str]] = []
    seed_rows: list[dict[str, str]] = []

    for review in human_rows:
        asin = review["asin"]
        fact = facts.get(asin, {})
        identity_lane, next_action = lane_for(review)
        row = {
            "sku_id": review["sku_id"],
            "asin": asin,
            "identity_lane": identity_lane,
            "next_action": next_action,
            "human_review_status": review["human_review_status"],
            "promotion_lane": review["promotion_lane"],
            "amazon_url": clean_value(fact.get("amazon_url")),
            "pdp_title": clean_value(fact.get("title")),
            "pdp_price": clean_value(fact.get("price")),
            "pdp_rating": clean_value(fact.get("rating")),
            "pdp_review_count": clean_value(fact.get("review_count")).replace(".0", ""),
            "bought_past_month": clean_value(fact.get("bought_past_month")),
            "sold_by": clean_value(fact.get("sold_by")),
            "ships_from": clean_value(fact.get("ships_from")),
            "probe_quality": clean_value(fact.get("probe_quality")),
            "source_screenshot": clean_value(fact.get("source_screenshot")),
            "claim_gate_required": "yes",
            "review_crawl_allowed_now": "authorized_pipeline_only" if identity_lane == "identity_whitelist_candidate" else "no",
            "public_copy_allowed": "no",
            "note": review["human_note"],
        }
        out_rows.append(row)
        if identity_lane == "identity_whitelist_candidate":
            seed_rows.append(row)

    lanes_csv = LIVE_DIR / "amazon_identity_lanes_v1.csv"
    with lanes_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    seed_csv = LIVE_DIR / "amazon_review_voc_seed_v1.csv"
    with seed_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(seed_rows[0].keys()))
        writer.writeheader()
        writer.writerows(seed_rows)

    counts = pd.Series([row["identity_lane"] for row in out_rows]).value_counts().sort_index().to_dict()
    report = LIVE_DIR / "amazon_identity_lanes_v1.md"
    lines = [
        "# Amazon Identity Lanes v1",
        "",
        "Date: 2026-04-28",
        "",
        "## Scope",
        "",
        "This file turns the machine visual gate plus first human review into execution lanes for review/VOC crawling, variant research, retry, and negative training.",
        "",
        "No row in this table authorizes public DTC copy. Even identity-whitelist candidates still require claim gating and authorized review access.",
        "",
        "## Counts",
        "",
    ]
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Review/VOC Seed",
            "",
            "Use only these seven rows for the next authorized review/VOC crawl pilot:",
            "",
        ]
    )
    for row in seed_rows:
        lines.append(
            f"- `{row['sku_id']}` -> `{row['asin']}` | rating `{row['pdp_rating']}` | reviews `{row['pdp_review_count']}` | sold by `{row['sold_by']}`"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- `{lanes_csv.name}`",
            f"- `{seed_csv.name}`",
        ]
    )
    report.write_text("\n".join(lines), encoding="utf-8")
    print({"lanes": str(lanes_csv), "seed": str(seed_csv), "report": str(report), "counts": counts})


if __name__ == "__main__":
    main()
