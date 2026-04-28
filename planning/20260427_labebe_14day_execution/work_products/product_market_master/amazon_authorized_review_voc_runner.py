#!/usr/bin/env python3
"""Authorized Amazon review/VOC runner for Labebe identity-whitelist ASINs.

Default behavior is dry-run only. The script calls Apify only when both
conditions are true:

- `--execute` is passed;
- `APIFY_TOKEN` or `APIFY_API_TOKEN` is present.

It intentionally accepts only rows already promoted into the
identity-whitelist review/VOC seed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTOR_ID_DEFAULT = "automation-lab/amazon-reviews-scraper"
STAR_FILTERS = ["five_star", "four_star", "three_star", "two_star", "one_star"]
DEFAULT_SEED = Path(
    "planning/20260427_labebe_14day_execution/work_products/"
    "product_market_master/live_crawl_20260428/amazon_review_voc_seed_v1.csv"
)
DEFAULT_OUT_DIR = Path(
    "planning/20260427_labebe_14day_execution/work_products/"
    "product_market_master/live_crawl_20260428/authorized_reviews"
)


def read_seed(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    allowed = []
    for row in rows:
        if row.get("identity_lane") != "identity_whitelist_candidate":
            continue
        if row.get("review_crawl_allowed_now") != "authorized_pipeline_only":
            continue
        if not row.get("asin") or not row.get("sku_id"):
            continue
        allowed.append(row)
    return allowed


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def token_from_env() -> str:
    return os.getenv("APIFY_TOKEN") or os.getenv("APIFY_API_TOKEN") or ""


def plan_rows(
    seed_rows: list[dict[str, str]],
    marketplace: str,
    max_reviews: int,
    sorts: list[str],
    actor_id: str,
) -> list[dict[str, Any]]:
    rows = []
    for row in seed_rows:
        asin = row["asin"]
        rows.append(
            {
                "sku_id": row["sku_id"],
                "asin": asin,
                "marketplace": marketplace,
                "amazon_url": row.get("amazon_url", ""),
                "pdp_rating": row.get("pdp_rating", ""),
                "pdp_review_count": row.get("pdp_review_count", ""),
                "identity_lane": row.get("identity_lane", ""),
                "human_review_status": row.get("human_review_status", ""),
                "review_crawl_allowed_now": row.get("review_crawl_allowed_now", ""),
                "actor_id": actor_id,
                "sorts": " ".join(sorts),
                "star_filters": " ".join(STAR_FILTERS),
                "max_reviews_per_star_filter": min(max_reviews, 100),
                "planned_calls": len(sorts) * len(STAR_FILTERS),
                "output_csv": f"amazon_reviews_{marketplace}_{asin}.csv",
                "output_jsonl": f"amazon_reviews_{marketplace}_{asin}.jsonl",
                "public_copy_allowed": "no",
                "claim_gate": "review_text_internal_only_until_claim_review",
            }
        )
    return rows


def fetch_one_asin(
    *,
    token: str,
    actor_id: str,
    asin: str,
    marketplace: str,
    max_reviews: int,
    sorts: list[str],
) -> list[dict[str, Any]]:
    try:
        from apify_client import ApifyClient  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "apify_client is not installed; install it before --execute, "
            "or run without --execute for dry-run planning"
        ) from exc

    client = ApifyClient(token)
    all_items: list[dict[str, Any]] = []
    for sort in sorts:
        for star_filter in STAR_FILTERS:
            run_input = {
                "asins": [asin],
                "marketplace": marketplace,
                "maxReviewsPerProduct": min(max_reviews, 100),
                "sort": sort,
                "filterByStars": star_filter,
                "maxRequestRetries": 5,
            }
            run = client.actor(actor_id).call(run_input=run_input)
            dataset_id = run["defaultDatasetId"]
            for item in client.dataset(dataset_id).iterate_items():
                item["_source_star_filter"] = star_filter
                item["_source_sort"] = sort
                item["_source_actor_id"] = actor_id
                all_items.append(item)
    return all_items


def normalize_reviews(
    items: list[dict[str, Any]],
    sku_id: str,
    asin: str,
    marketplace: str,
) -> list[dict[str, Any]]:
    fields = [
        "sku_id",
        "asin",
        "productName",
        "productUrl",
        "reviewId",
        "title",
        "body",
        "rating",
        "date",
        "author",
        "authorUrl",
        "isVerifiedPurchase",
        "helpfulVotes",
        "reviewUrl",
        "marketplace",
        "scrapedAt",
        "_source_star_filter",
        "_source_sort",
        "_source_actor_id",
    ]
    seen: set[tuple[str, str, str]] = set()
    rows: list[dict[str, Any]] = []
    for item in items:
        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or "").strip()
        key = (
            asin,
            str(item.get("reviewId") or item.get("reviewUrl") or f"{title}|{body}"),
            str(item.get("date") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        row = {field: item.get(field) for field in fields}
        row["sku_id"] = sku_id
        row["asin"] = item.get("asin") or asin
        row["marketplace"] = item.get("marketplace") or marketplace
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--marketplace", default="US")
    parser.add_argument("--actor-id", default=ACTOR_ID_DEFAULT)
    parser.add_argument("--max-reviews", type=int, default=100)
    parser.add_argument(
        "--sorts",
        nargs="+",
        default=["recent", "helpful"],
        choices=["recent", "helpful"],
    )
    parser.add_argument("--asin", action="append", help="Optional ASIN allowlist")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    seed_rows = read_seed(args.seed)
    if args.asin:
        allowed = {asin.strip() for asin in args.asin}
        seed_rows = [row for row in seed_rows if row["asin"] in allowed]

    plan = plan_rows(seed_rows, args.marketplace, args.max_reviews, args.sorts, args.actor_id)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    plan_csv = args.out_dir / "authorized_review_crawl_plan_v1.csv"
    manifest_json = args.out_dir / "authorized_review_crawl_plan_v1.json"
    write_csv(plan_csv, plan, list(plan[0].keys()) if plan else ["sku_id", "asin"])

    token = token_from_env()
    manifest: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "execute" if args.execute else "dry_run",
        "gate_status": "ready_to_execute" if args.execute and token else "dry_run_no_external_calls",
        "seed_path": str(args.seed),
        "eligible_rows": len(seed_rows),
        "actor_id": args.actor_id,
        "marketplace": args.marketplace,
        "sorts": args.sorts,
        "star_filters": STAR_FILTERS,
        "max_reviews_per_star_filter": min(args.max_reviews, 100),
        "plan_csv": str(plan_csv),
        "external_calls_made": False,
        "outputs": [],
        "blocked_reason": "",
        "rules": [
            "identity_whitelist_candidate only",
            "review text remains internal until claim review",
            "no search candidates, variant clusters, or blocked examples",
            "no public DTC copy authorization",
        ],
    }

    if args.execute and not token:
        manifest["gate_status"] = "blocked_missing_apify_token"
        manifest["blocked_reason"] = "APIFY_TOKEN/APIFY_API_TOKEN is not set"
        write_json(manifest_json, manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 3

    if args.execute:
        manifest["external_calls_made"] = True
        fields = [
            "sku_id",
            "asin",
            "productName",
            "productUrl",
            "reviewId",
            "title",
            "body",
            "rating",
            "date",
            "author",
            "authorUrl",
            "isVerifiedPurchase",
            "helpfulVotes",
            "reviewUrl",
            "marketplace",
            "scrapedAt",
            "_source_star_filter",
            "_source_sort",
            "_source_actor_id",
        ]
        for seed in seed_rows:
            asin = seed["asin"]
            csv_path = args.out_dir / f"amazon_reviews_{args.marketplace}_{asin}.csv"
            jsonl_path = args.out_dir / f"amazon_reviews_{args.marketplace}_{asin}.jsonl"
            if csv_path.exists() and jsonl_path.exists() and not args.force:
                manifest["outputs"].append(
                    {"sku_id": seed["sku_id"], "asin": asin, "status": "skipped_existing", "csv": str(csv_path), "jsonl": str(jsonl_path)}
                )
                continue
            items = fetch_one_asin(
                token=token,
                actor_id=args.actor_id,
                asin=asin,
                marketplace=args.marketplace,
                max_reviews=args.max_reviews,
                sorts=args.sorts,
            )
            reviews = normalize_reviews(items, seed["sku_id"], asin, args.marketplace)
            write_csv(csv_path, reviews, fields)
            with jsonl_path.open("w", encoding="utf-8") as handle:
                for review in reviews:
                    handle.write(json.dumps(review, ensure_ascii=False) + "\n")
            manifest["outputs"].append(
                {"sku_id": seed["sku_id"], "asin": asin, "status": "fetched", "rows": len(reviews), "csv": str(csv_path), "jsonl": str(jsonl_path)}
            )

    write_json(manifest_json, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
