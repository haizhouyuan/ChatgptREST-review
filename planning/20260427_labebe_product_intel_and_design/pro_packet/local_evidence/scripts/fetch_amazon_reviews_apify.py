import os
import json
import argparse
from pathlib import Path
from typing import Any

import pandas as pd
from apify_client import ApifyClient


ACTOR_ID = "automation-lab/amazon-reviews-scraper"

STAR_FILTERS = [
    "five_star",
    "four_star",
    "three_star",
    "two_star",
    "one_star",
]


def fetch_reviews_for_filter(
    client: ApifyClient,
    asin: str,
    marketplace: str,
    star_filter: str,
    sort: str,
    max_reviews: int,
) -> list[dict[str, Any]]:
    run_input = {
        "asins": [asin],
        "marketplace": marketplace,
        "maxReviewsPerProduct": min(max_reviews, 100),
        "sort": sort,
        "filterByStars": star_filter,
        "maxRequestRetries": 5,
    }

    print(f"  Calling Apify actor with filter={star_filter}, sort={sort}")
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    dataset_id = run["defaultDatasetId"]

    items = []
    for item in client.dataset(dataset_id).iterate_items():
        item["_source_star_filter"] = star_filter
        item["_source_sort"] = sort
        items.append(item)

    return items


def normalize_reviews(items: list[dict[str, Any]]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(items)

    expected_cols = [
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
    ]

    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    df = df[expected_cols].copy()

    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["helpfulVotes"] = pd.to_numeric(df["helpfulVotes"], errors="coerce").fillna(0).astype(int)

    df["_dedupe_key"] = df["reviewId"].fillna("")
    missing_id = df["_dedupe_key"].eq("")

    df.loc[missing_id, "_dedupe_key"] = df.loc[missing_id, "reviewUrl"].fillna("")
    still_missing = df["_dedupe_key"].eq("")

    df.loc[still_missing, "_dedupe_key"] = (
        df.loc[still_missing, "asin"].fillna("")
        + "|"
        + df.loc[still_missing, "title"].fillna("")
        + "|"
        + df.loc[still_missing, "body"].fillna("")
    )

    df = df.drop_duplicates(subset=["marketplace", "asin", "_dedupe_key"], keep="first")

    return df.drop(columns=["_dedupe_key"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asin", required=True, help="Amazon ASIN, e.g. B087P9SXZQ")
    parser.add_argument("--marketplace", default="US", help="US/UK/DE/FR/IT/ES/CA/JP/IN/AU")
    parser.add_argument("--max-reviews", type=int, default=100)
    parser.add_argument("--out-dir", default="data")
    parser.add_argument(
        "--sorts",
        nargs="+",
        default=["recent"],
        choices=["recent", "helpful"],
        help="default recent; use recent helpful to supplement",
    )
    args = parser.parse_args()

    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("Missing APIFY_TOKEN environment variable")

    client = ApifyClient(token)

    all_items: list[dict[str, Any]] = []

    for sort in args.sorts:
        for star_filter in STAR_FILTERS:
            print(f"\nFetching asin={args.asin}, marketplace={args.marketplace}, sort={sort}, filter={star_filter}")
            items = fetch_reviews_for_filter(
                client=client,
                asin=args.asin,
                marketplace=args.marketplace,
                star_filter=star_filter,
                sort=sort,
                max_reviews=args.max_reviews,
            )
            print(f"  Got {len(items)} rows")
            all_items.extend(items)

    df = normalize_reviews(all_items)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / f"amazon_reviews_{args.marketplace}_{args.asin}.csv"
    jsonl_path = out_dir / f"amazon_reviews_{args.marketplace}_{args.asin}.jsonl"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in df.to_dict(orient="records"):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("\n" + "="*60)
    print("Done")
    print(f"Total rows after dedupe: {len(df)}")
    print(f"CSV:   {csv_path}")
    print(f"JSONL: {jsonl_path}")

    if not df.empty:
        print("\nRating distribution:")
        print(df["rating"].value_counts(dropna=False).sort_index())
        print(f"\nUnique reviewIds: {df['reviewId'].nunique(dropna=True)}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")


if __name__ == "__main__":
    main()