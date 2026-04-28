#!/usr/bin/env python3
"""Build the next marketplace enrichment backlog from current Labebe matrices."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIVE_DIR = Path(
    "planning/20260427_labebe_14day_execution/work_products/"
    "product_market_master/live_crawl_20260428"
)
STRATEGY = LIVE_DIR / "labebe_product_strategy_matrix_v1.csv"
SEARCH = LIVE_DIR / "amazon_search_candidate_summary_v1.csv"
IDENTITY = LIVE_DIR / "amazon_identity_lanes_v1.csv"
OUT_CSV = LIVE_DIR / "marketplace_enrichment_backlog_v1.csv"
OUT_JSON = LIVE_DIR / "marketplace_enrichment_worker_batches_v1.json"
OUT_MD = LIVE_DIR / "marketplace_enrichment_batch_plan_v1.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean(value: Any) -> str:
    return str(value or "").strip()


def as_int(value: Any) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except Exception:
        return 0


def search_map(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_sku: dict[str, dict[str, str]] = {}
    for row in rows:
        sku = clean(row.get("sku_id"))
        if not sku:
            continue
        current = by_sku.get(sku)
        if current is None or as_int(row.get("candidate_score")) > as_int(current.get("candidate_score")):
            by_sku[sku] = row
    return by_sku


def identity_map(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(clean(row.get("sku_id")), clean(row.get("asin"))): row for row in rows}


def batch_for(strategy: dict[str, str], search: dict[str, str] | None) -> tuple[str, str, str, str]:
    lane = clean(strategy.get("amazon_identity_lane")) or "no_marketplace_identity_yet"
    catalog_scope = clean(strategy.get("catalog_scope"))
    role = clean(strategy.get("website_role"))
    dtc_reviews = as_int(strategy.get("dtc_review_count_visible"))
    search_status = clean(search.get("search_candidate_status")) if search else ""
    score = as_int(search.get("candidate_score")) if search else 0

    if lane == "identity_whitelist_candidate":
        return (
            "B0_identity_whitelist_review_voc",
            "P0_gate_after_authorized_reviews",
            "Run claim gate and authorized review/VOC extraction only; no more identity discovery needed for this row.",
            "review_voc_runner_then_claim_review",
        )
    if lane == "variant_cluster_research":
        return (
            "B1_variant_cluster_map",
            "P1_high",
            "Build variant map with provider/PDP variation data and image review before exact SKU claims.",
            "provider_variation_api_or_manual_variant_sheet",
        )
    if lane == "retry_or_provider_required":
        return (
            "B2_pdp_retry_provider",
            "P1_high" if role in {"homepage_hero_or_best_seller", "navigation_and_room_solution_anchor", "category_anchor_pdp"} or dtc_reviews >= 5 else "P2_medium",
            "Retry PDP capture or use a product-data provider; current browser capture is weak, blank, or missing social-proof/image detail.",
            "browser_harness_retry_then_provider_fallback",
        )
    if lane == "blocked_negative_example":
        return (
            "B4_negative_training_restart_search",
            "P2_medium" if dtc_reviews >= 5 else "P3_low",
            "Keep as negative training; restart discovery with exclusion terms and do not reuse the blocked ASIN as proof.",
            "search_with_negative_asin_exclusion",
        )
    if catalog_scope == "regional_variant":
        return (
            "B5_regional_scope_review",
            "P3_low",
            "Review locale/fulfillment before any Amazon US identity work; keep out of US proof layer.",
            "regional_locale_review_first",
        )
    if search and search_status.startswith("pdp_queue") and score >= 80:
        return (
            "B3_no_identity_high_signal",
            "P1_high" if dtc_reviews >= 5 or role in {"navigation_and_room_solution_anchor", "category_anchor_pdp"} else "P2_medium",
            "Search found a high-scoring candidate but no accepted identity; run PDP probe and visual gate.",
            "pdp_probe_then_visual_gate",
        )
    return (
        "B3_no_identity_restart_discovery",
        "P1_high" if dtc_reviews >= 9 or role == "navigation_and_room_solution_anchor" else "P2_medium",
        "No accepted marketplace identity yet; restart discovery with exact title, brand, image search, and provider fallback.",
        "exact_title_brand_search_then_provider_fallback",
    )


def public_copy_rule(batch_id: str) -> str:
    if batch_id == "B0_identity_whitelist_review_voc":
        return "no_public_copy_until_claim_review_and_source_approval"
    return "no_public_marketplace_claim"


def main() -> int:
    strategy_rows = read_csv(STRATEGY)
    search_by_sku = search_map(read_csv(SEARCH))
    identities = identity_map(read_csv(IDENTITY))
    backlog: list[dict[str, Any]] = []

    for row in strategy_rows:
        sku = clean(row.get("sku_id"))
        asin = clean(row.get("asin"))
        search = search_by_sku.get(sku)
        identity = identities.get((sku, asin), {}) if asin else {}
        batch_id, priority, next_action, method = batch_for(row, search)
        backlog.append(
            {
                "sku_id": sku,
                "title_clean": clean(row.get("title_clean")),
                "primary_world": clean(row.get("primary_world")),
                "catalog_scope": clean(row.get("catalog_scope")),
                "website_role": clean(row.get("website_role")),
                "dtc_review_count_visible": clean(row.get("dtc_review_count_visible")),
                "amazon_identity_lane": clean(row.get("amazon_identity_lane")) or "no_marketplace_identity_yet",
                "current_asin": asin,
                "amazon_review_count": clean(row.get("amazon_review_count")),
                "amazon_sold_by": clean(row.get("amazon_sold_by")),
                "search_candidate_asin": clean(search.get("asin")) if search else "",
                "search_candidate_status": clean(search.get("search_candidate_status")) if search else "not_in_search_summary",
                "search_candidate_score": clean(search.get("candidate_score")) if search else "",
                "human_review_status": clean(identity.get("human_review_status")),
                "promotion_lane": clean(identity.get("promotion_lane")),
                "batch_id": batch_id,
                "priority": priority,
                "recommended_method": method,
                "next_action": next_action,
                "public_copy_rule": public_copy_rule(batch_id),
                "worker_guardrail": "identity_first_no_search_page_facts_no_fake_reviews_no_public_claims",
            }
        )

    priority_order = {"P0_gate_after_authorized_reviews": 0, "P1_high": 1, "P2_medium": 2, "P3_low": 3}
    backlog.sort(key=lambda r: (priority_order.get(r["priority"], 9), r["batch_id"], -as_int(r["dtc_review_count_visible"]), r["sku_id"]))

    fields = list(backlog[0].keys())
    write_csv(OUT_CSV, backlog, fields)

    batches: dict[str, dict[str, Any]] = {}
    for row in backlog:
        batch = batches.setdefault(
            row["batch_id"],
            {
                "batch_id": row["batch_id"],
                "priority_counts": Counter(),
                "recommended_methods": Counter(),
                "rows": [],
            },
        )
        batch["priority_counts"][row["priority"]] += 1
        batch["recommended_methods"][row["recommended_method"]] += 1
        batch["rows"].append(
            {
                "sku_id": row["sku_id"],
                "asin": row["current_asin"] or row["search_candidate_asin"],
                "priority": row["priority"],
                "method": row["recommended_method"],
                "guardrail": row["worker_guardrail"],
            }
        )

    serializable_batches = []
    for batch_id in sorted(batches):
        batch = batches[batch_id]
        serializable_batches.append(
            {
                "batch_id": batch_id,
                "row_count": len(batch["rows"]),
                "priority_counts": dict(batch["priority_counts"]),
                "recommended_methods": dict(batch["recommended_methods"]),
                "rows": batch["rows"],
            }
        )

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_strategy": str(STRATEGY),
        "input_search_summary": str(SEARCH),
        "input_identity_lanes": str(IDENTITY),
        "backlog_csv": str(OUT_CSV),
        "batch_plan_md": str(OUT_MD),
        "total_rows": len(backlog),
        "batch_counts": dict(Counter(row["batch_id"] for row in backlog)),
        "priority_counts": dict(Counter(row["priority"] for row in backlog)),
        "batches": serializable_batches,
        "forbidden": [
            "do not use search-page price/rating/review counts as facts",
            "do not promote variant clusters as exact SKU proof",
            "do not run review extraction outside identity-whitelist rows",
            "do not use marketplace review text as public copy without claim review",
        ],
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Marketplace Enrichment Batch Plan v1",
        "",
        f"Generated: {summary['created_at']}",
        "",
        "## Purpose",
        "",
        "This file turns the 60-row Labebe product strategy matrix into a worker-ready marketplace enrichment backlog. It does not create new Amazon claims. It tells future workers which rows can be processed in parallel and which gates must stay closed.",
        "",
        "## Summary",
        "",
        f"- Total SKU rows: {len(backlog)}",
        f"- Backlog CSV: `{OUT_CSV.name}`",
        f"- Worker batches JSON: `{OUT_JSON.name}`",
        "",
        "### Batch Counts",
        "",
    ]
    for batch_id, count in sorted(summary["batch_counts"].items()):
        lines.append(f"- `{batch_id}`: {count}")
    lines += ["", "### Priority Counts", ""]
    for priority, count in sorted(summary["priority_counts"].items(), key=lambda item: priority_order.get(item[0], 9)):
        lines.append(f"- `{priority}`: {count}")
    lines += [
        "",
        "## Batch Definitions",
        "",
        "| Batch | Use For | Allowed Next Step | Guardrail |",
        "|---|---|---|---|",
        "| `B0_identity_whitelist_review_voc` | confirmed same-product identity rows | authorized review/VOC runner, then claim review | no public copy until source/claim approval |",
        "| `B1_variant_cluster_map` | related model/variant clusters | provider variation API, child ASIN/variation mapping, image review | no exact SKU claim |",
        "| `B2_pdp_retry_provider` | weak PDP, blank image, missing proof | Browser Harness retry then provider fallback | no review crawl |",
        "| `B3_no_identity_high_signal` | strong search candidate but no accepted identity | PDP probe then visual gate | search facts stay discovery-only |",
        "| `B3_no_identity_restart_discovery` | no accepted identity | exact title/brand search, reverse image/provider fallback | no search-page facts |",
        "| `B4_negative_training_restart_search` | known wrong ASIN mappings | preserve negative example and restart with exclusions | blocked ASIN cannot be reused as proof |",
        "| `B5_regional_scope_review` | EU/regional products | locale/fulfillment review first | keep out of Amazon US proof layer |",
        "",
        "## Top P1 Rows",
        "",
        "| SKU | Batch | Current ASIN | Search ASIN | Method |",
        "|---|---|---|---|---|",
    ]
    for row in [item for item in backlog if item["priority"] == "P1_high"][:25]:
        lines.append(
            f"| `{row['sku_id']}` | `{row['batch_id']}` | `{row['current_asin']}` | "
            f"`{row['search_candidate_asin']}` | {row['recommended_method']} |"
        )
    lines += [
        "",
        "## Stop Rules",
        "",
        "- Search pages are discovery only.",
        "- Marketplace facts remain internal until identity, claim, and source gates pass.",
        "- Review/VOC extraction is allowed only for `B0_identity_whitelist_review_voc` rows after provider credentials are available.",
        "- Regional variants must not be mixed into Amazon US proof.",
        "- Negative examples must stay attached to prevent repeated false-positive matching.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["total_rows", "batch_counts", "priority_counts", "backlog_csv", "batch_plan_md"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
