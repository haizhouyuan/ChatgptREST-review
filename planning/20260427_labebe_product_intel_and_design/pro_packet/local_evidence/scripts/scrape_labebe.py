import os
import json
import csv
import base64
import time
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    os.system("pip install playwright --break-system-packages -q")
    os.system("playwright install chromium --with-deps 2>&1 | tail -3")
    from playwright.sync_api import sync_playwright

BASE_URL = "https://labebeclub.com"
COLLECTIONS = [
    "rockers-ride-ons",
    "pretend-play",
    "activity-educational-toys",
    "furniture",
    "new-in",
]

OUTPUT_DIR = Path("data/labebe")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_products_from_page(page) -> list[dict[str, Any]]:
    js_code = """
    () => {
        const products = [];
        document.querySelectorAll('a[href*="/product/"]').forEach(el => {
            const title = el.textContent || '';
            const href = el.getAttribute('href') || '';
            if (!href.startsWith('/product/') || !title.includes('Quick add')) return;

            const parent = el.closest('li, article, div[class*="product"], .product-item');

            let price = '';
            if (parent) {
                const priceEl = parent.querySelector('.price, [class*="price"], .product-price');
                price = priceEl ? priceEl.textContent.trim() : '';
            }
            if (!price) {
                const match = title.match(/\\$[\\d,]+\\.?\\d*/);
                if (match) price = match[0];
            }

            let cleanTitle = title.replace(/Quick add\\s*/g, '').replace(/\\s+/g, ' ').trim();
            const discount = (title.match(/-(\\d+)%/) || [])[1] || '';
            const originalPrice = (title.match(/\\$[\\d,]+\\.?\\d*(?=\\s*$)/) || [])[0] || '';
            const currentPrice = (title.match(/^\\$[\\d,]+\\.?\\d*/) || [])[0] || price;
            const reviewsMatch = title.match(/\\((\\d+)\\)/);
            const reviewsCount = reviewsMatch ? reviewsMatch[1] : '';

            const slug = href.replace('/product/', '').replace(/\\/$/, '');

            products.push({
                product_url: 'https://labebeclub.com' + href,
                slug,
                title: cleanTitle,
                current_price: currentPrice,
                original_price: originalPrice,
                discount: discount ? discount + '%' : '',
                reviews_count: reviewsCount,
                image_url: '',
                collection: ''
            });
        });

        const seen = new Set();
        return products.filter(p => {
            if (seen.has(p.product_url)) return false;
            seen.add(p.product_url);
            return true;
        });
    }
    """
    return page.evaluate(js_code)


def get_product_image(page, product_url: str) -> str:
    try:
        page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.5)
        # Try to get main product image - look for media.cdn.ishopastro.com images first
        img_els = page.query_selector_all('img')
        for img_el in img_els:
            src = img_el.get_attribute("src") or img_el.get_attribute("data-src") or ""
            if "media.cdn.ishopastro.com" in src and "logo" not in src.lower():
                return src.split("?")[0]  # Remove query params
        # Fallback to any product image
        for img_el in img_els:
            src = img_el.get_attribute("src") or img_el.get_attribute("data-src") or ""
            if src and "cdn" in src and "logo" not in src.lower():
                return src.split("?")[0]
    except Exception as e:
        print(f"  Error getting image for {product_url}: {e}")
    return ""


def scrape_collection(collection_slug: str) -> list[dict[str, Any]]:
    url = f"{BASE_URL}/collection/{collection_slug}"
    print(f"Scraping: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()

        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        products = extract_products_from_page(page)

        browser.close()

    print(f"  Found {len(products)} products")
    return products


def download_image(url: str, save_path: Path, timeout: int = 10) -> bool:
    if not url:
        return False
    try:
        if url.startswith("//"):
            url = "https:" + url

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            save_path.write_bytes(data)
        return True
    except Exception as e:
        return False


def main():
    all_products = []
    all_slugs = set()

    for coll in COLLECTIONS:
        products = scrape_collection(coll)
        for p in products:
            p["collection"] = coll
            if p["slug"] not in all_slugs:
                all_slugs.add(p["slug"])
                all_products.append(p)

    print(f"\nTotal unique products: {len(all_products)}")

    csv_path = OUTPUT_DIR / "labebe_products.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "slug", "title", "current_price", "original_price", "discount",
            "reviews_count", "product_url", "image_url", "collection"
        ])
        writer.writeheader()
        writer.writerows(all_products)

    print(f"CSV saved: {csv_path}")

    img_dir = OUTPUT_DIR / "images"
    img_dir.mkdir(exist_ok=True)

    print(f"\nFetching images for each product page...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()

        for i, prod in enumerate(all_products):
            print(f"  [{i+1}/{len(all_products)}] Fetching: {prod['product_url']}")
            img_url = get_product_image(page, prod["product_url"])
            prod["image_url"] = img_url
            time.sleep(0.5)

        browser.close()

    print(f"\nDownloading images...")
    for i, prod in enumerate(all_products):
        if prod["image_url"]:
            ext = ".jpg"
            if "png" in prod["image_url"].lower():
                ext = ".png"
            img_path = img_dir / f"{prod['slug']}{ext}"
            ok = download_image(prod["image_url"], img_path)
            if ok:
                prod["local_image_path"] = str(img_path)
                print(f"  [{i+1}/{len(all_products)}] OK: {prod['slug']}{ext}")
            else:
                prod["local_image_path"] = ""
                print(f"  [{i+1}/{len(all_products)}] FAIL: {prod['slug']}")
        else:
            prod["local_image_path"] = ""

    csv_with_imgs = OUTPUT_DIR / "labebe_products_with_images.csv"
    with open(csv_with_imgs, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "slug", "title", "current_price", "original_price", "discount",
            "reviews_count", "product_url", "image_url", "local_image_path", "collection"
        ])
        writer.writeheader()
        writer.writerows(all_products)

    print(f"\nCSV with images saved: {csv_with_imgs}")
    print(f"Images dir: {img_dir}")
    print(f"Total images downloaded: {len([prod for prod in all_products if prod.get('local_image_path')])}")


if __name__ == "__main__":
    main()