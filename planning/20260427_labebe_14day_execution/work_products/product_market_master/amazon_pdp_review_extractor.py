#!/usr/bin/env python3
"""Extract top reviews from Amazon PDP pages (bypasses /product-reviews sign-in wall).

Amazon PDP (/dp/ASIN) loads without sign-in and embeds ~10-15 top reviews.
This script scrapes those embedded reviews using Playwright + basic stealth.
Output format is compatible with build_review_voc_summary.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

STEALTH_SCRIPT = """
() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    window.chrome = { runtime: {} };
}
"""

DEFAULT_SEED = Path(
    "planning/20260427_labebe_14day_execution/work_products/"
    "product_market_master/live_crawl_20260428/amazon_review_voc_seed_v1.csv"
)
DEFAULT_OUT_DIR = Path(
    "planning/20260427_labebe_14day_execution/work_products/"
    "product_market_master/live_crawl_20260428/authorized_reviews"
)

OUTPUT_FIELDS = [
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
    "_source_method",
]


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


def extract_reviews(html: str, sku_id: str, asin: str, product_name: str) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # Amazon embeds reviews as data-hook="review" blocks inside PDP
    # Each block contains: title, rating, body, author, date, verified, helpful
    blocks = re.findall(
        r'<div[^>]*data-hook="review"[^>]*>(.*?)</div>\s*</div>\s*</div>\s*</div>',
        html,
        re.DOTALL | re.IGNORECASE,
    )

    for block in blocks:
        # reviewId from data-reid or review URL
        rid_match = re.search(r'data-reid="([^"]+)"', block)
        review_id = rid_match.group(1) if rid_match else ""

        # Title
        title_match = re.search(
            r'<a[^>]*data-hook="review-title"[^>]*>.*?<span[^>]*>(.*?)</span>.*?</a>',
            block,
            re.DOTALL | re.IGNORECASE,
        )
        title = clean_html(title_match.group(1)) if title_match else ""

        # Body
        body_match = re.search(
            r'<span[^>]*data-hook="review-body"[^>]*>.*?<span[^>]*>(.*?)</span>.*?</span>',
            block,
            re.DOTALL | re.IGNORECASE,
        )
        body = clean_html(body_match.group(1)) if body_match else ""

        # Rating
        star_match = re.search(
            r'<i[^>]*data-hook="review-star-rating"[^>]*>.*?([0-9.]+)\s*out of\s*5.*?</i>',
            block,
            re.DOTALL | re.IGNORECASE,
        )
        rating = star_match.group(1) if star_match else ""

        # Date
        date_match = re.search(
            r'<span[^>]*data-hook="review-date"[^>]*>(.*?)</span>',
            block,
            re.DOTALL | re.IGNORECASE,
        )
        date_str = clean_html(date_match.group(1)) if date_match else ""

        # Author
        author_match = re.search(
            r'<span[^>]*class="a-profile-name"[^>]*>(.*?)</span>',
            block,
            re.DOTALL | re.IGNORECASE,
        )
        author = clean_html(author_match.group(1)) if author_match else ""

        # Verified
        verified = "yes" if re.search(r'data-hook="avp-badge"', block, re.IGNORECASE) else "no"

        # Helpful votes
        helpful_match = re.search(
            r'<span[^>]*data-hook="helpful-vote-statement"[^>]*>(.*?)</span>',
            block,
            re.DOTALL | re.IGNORECASE,
        )
        helpful_text = clean_html(helpful_match.group(1)) if helpful_match else ""
        helpful_votes = re.search(r'(\d+)', helpful_text)
        helpful = helpful_votes.group(1) if helpful_votes else "0"

        if not body:
            continue
        key = review_id or f"{title}|{body[:60]}"
        if key in seen_ids:
            continue
        seen_ids.add(key)

        reviews.append({
            "sku_id": sku_id,
            "asin": asin,
            "productName": product_name,
            "productUrl": f"https://www.amazon.com/dp/{asin}",
            "reviewId": review_id,
            "title": title,
            "body": body,
            "rating": rating,
            "date": date_str,
            "author": author,
            "authorUrl": "",
            "isVerifiedPurchase": verified,
            "helpfulVotes": helpful,
            "reviewUrl": f"https://www.amazon.com/gp/customer-reviews/{review_id}" if review_id else "",
            "marketplace": "US",
            "scrapedAt": datetime.now(timezone.utc).isoformat(),
            "_source_method": "pdp_embedded_top_reviews",
        })
    return reviews


def clean_html(raw: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fetch_pdp_reviews(
    asin: str,
    sku_id: str,
    product_name: str,
    max_wait: int = 10000,
) -> list[dict[str, Any]]:
    url = f"https://www.amazon.com/dp/{asin}"
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = context.new_page()
        page.add_init_script(STEALTH_SCRIPT)
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(max_wait)
        html = page.content()
        browser.close()
    return extract_reviews(html, sku_id, asin, product_name)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--marketplace", default="US")
    parser.add_argument("--asin", action="append", help="Optional ASIN allowlist")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    seed_rows = read_seed(args.seed)
    if args.asin:
        allowed = {a.strip() for a in args.asin}
        seed_rows = [r for r in seed_rows if r["asin"] in allowed]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "execute",
        "method": "pdp_embedded_top_reviews",
        "gate_status": "executed",
        "seed_path": str(args.seed),
        "eligible_rows": len(seed_rows),
        "marketplace": args.marketplace,
        "outputs": [],
        "rules": [
            "identity_whitelist_candidate only",
            "review text remains internal until claim review",
            "no public DTC copy authorization",
            "source_method: pdp_embedded_top_reviews (bypasses /product-reviews sign-in)",
        ],
    }

    for seed in seed_rows:
        asin = seed["asin"]
        sku_id = seed["sku_id"]
        product_name = seed.get("pdp_title", "")
        csv_path = args.out_dir / f"amazon_reviews_{args.marketplace}_{asin}.csv"
        jsonl_path = args.out_dir / f"amazon_reviews_{args.marketplace}_{asin}.jsonl"

        if csv_path.exists() and jsonl_path.exists() and not args.force:
            manifest["outputs"].append({
                "sku_id": sku_id, "asin": asin,
                "status": "skipped_existing",
                "csv": str(csv_path), "jsonl": str(jsonl_path),
            })
            continue

        print(f"Fetching PDP reviews for {sku_id} ({asin}) ...")
        try:
            reviews = fetch_pdp_reviews(asin, sku_id, product_name)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            manifest["outputs"].append({
                "sku_id": sku_id, "asin": asin,
                "status": "failed", "error": str(exc),
            })
            continue

        write_csv(csv_path, reviews, OUTPUT_FIELDS)
        with jsonl_path.open("w", encoding="utf-8") as handle:
            for review in reviews:
                handle.write(json.dumps(review, ensure_ascii=False) + "\n")

        manifest["outputs"].append({
            "sku_id": sku_id, "asin": asin,
            "status": "fetched", "rows": len(reviews),
            "csv": str(csv_path), "jsonl": str(jsonl_path),
        })
        print(f"  -> {len(reviews)} reviews written")

    manifest_json = args.out_dir / "pdp_review_extraction_manifest_v1.json"
    write_json(manifest_json, manifest)
    print(f"\nManifest: {manifest_json}")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
