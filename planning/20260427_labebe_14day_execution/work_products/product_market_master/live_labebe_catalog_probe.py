#!/usr/bin/env python3
"""Probe current Labebe collection pages without overwriting prior crawls."""

from __future__ import annotations

import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


BASE_URL = "https://labebeclub.com"
COLLECTION_URLS = [
    ("all", "https://labebeclub.com/collections/all"),
    ("rockers-ride-ons", "https://labebeclub.com/collection/rockers-ride-ons"),
    ("pretend-play", "https://labebeclub.com/collection/pretend-play"),
    ("activity-educational-toys", "https://labebeclub.com/collection/activity-educational-toys"),
    ("furniture", "https://labebeclub.com/collection/furniture"),
    ("new-in", "https://labebeclub.com/collection/new-in"),
    ("storage-shelving", "https://labebeclub.com/collection/storage-shelving"),
]

OUT_DIR = Path(__file__).resolve().parent / "live_crawl_20260428"
OUT_DIR.mkdir(parents=True, exist_ok=True)


PRICE_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?")
REVIEWS_RE = re.compile(r"\((\d+)\)")
DISCOUNT_RE = re.compile(r"-(\d+)%")


def clean_title(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw or "").strip()
    text = re.sub(r"(?i)quick add", " ", text)
    text = re.sub(r"(?i)\bnew!\s*", " ", text)
    text = re.sub(r"(?i)\bhot\b", " ", text)
    text = DISCOUNT_RE.sub(" ", text)
    text = PRICE_RE.sub(" ", text)
    text = REVIEWS_RE.sub(" ", text)
    text = text.replace("| labebe®", " ")
    text = re.sub(r"\s+", " ", text).strip(" -|")
    return text


def extract_products(page, collection_slug: str) -> list[dict[str, str]]:
    products = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a[href*="/product/"]')).map((a) => {
          const href = a.getAttribute('href') || '';
          const text = (a.innerText || a.textContent || '').replace(/\\s+/g, ' ').trim();
          let card = a.closest('li, article, [class*="product"], [class*="Product"], [class*="goods"], [class*="card"]');
          let img = '';
          if (card) {
            const imgEl = card.querySelector('img');
            img = imgEl ? (imgEl.currentSrc || imgEl.src || imgEl.getAttribute('data-src') || '') : '';
          }
          return { href, text, image_url: img };
        }).filter((x) => x.href.includes('/product/') && x.text.length > 0)
        """
    )

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in products:
        href = str(item.get("href") or "")
        if not href.startswith("/product/") and "/product/" not in href:
            continue
        url = urljoin(BASE_URL, href.split("?")[0])
        slug = url.rstrip("/").split("/product/")[-1]
        if not slug or slug in seen:
            continue
        raw = str(item.get("text") or "")
        prices = PRICE_RE.findall(raw)
        reviews = REVIEWS_RE.search(raw)
        discount = DISCOUNT_RE.search(raw)
        rows.append(
            {
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "collection_probe": collection_slug,
                "slug": slug,
                "product_url": url,
                "title_raw": raw,
                "title_clean_probe": clean_title(raw),
                "price_current_probe": prices[0] if prices else "",
                "price_original_probe": prices[1] if len(prices) > 1 else "",
                "discount_probe": f"{discount.group(1)}%" if discount else "",
                "reviews_count_probe": reviews.group(1) if reviews else "",
                "image_url_probe": str(item.get("image_url") or "").split("?")[0],
            }
        )
        seen.add(slug)
    return rows


def main() -> None:
    all_rows: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 1200},
        )
        page = context.new_page()

        for collection_slug, url in COLLECTION_URLS:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)
                for _ in range(6):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(700)
                rows = extract_products(page, collection_slug)
                all_rows.extend(rows)
                print(f"{collection_slug}: {len(rows)} rows")
            except Exception as exc:  # noqa: BLE001
                failures.append({"collection_probe": collection_slug, "url": url, "error": repr(exc)})
                print(f"{collection_slug}: ERROR {exc!r}")

        context.close()
        browser.close()

    deduped: dict[str, dict[str, str]] = {}
    collection_seen: dict[str, set[str]] = {}
    for row in all_rows:
        slug = row["slug"]
        collection_seen.setdefault(slug, set()).add(row["collection_probe"])
        if slug not in deduped or row["collection_probe"] == "all":
            deduped[slug] = dict(row)

    final_rows = []
    for slug, row in sorted(deduped.items()):
        row["collection_probes_seen"] = ";".join(sorted(collection_seen.get(slug, [])))
        final_rows.append(row)

    csv_path = OUT_DIR / "labebe_products_live_probe.csv"
    fieldnames = [
        "observed_at",
        "collection_probe",
        "collection_probes_seen",
        "slug",
        "product_url",
        "title_raw",
        "title_clean_probe",
        "price_current_probe",
        "price_original_probe",
        "discount_probe",
        "reviews_count_probe",
        "image_url_probe",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_rows)

    manifest = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source_urls": [{"collection": c, "url": u} for c, u in COLLECTION_URLS],
        "raw_row_count": len(all_rows),
        "deduped_product_count": len(final_rows),
        "failures": failures,
        "output_csv": str(csv_path),
    }
    (OUT_DIR / "live_probe_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
