#!/usr/bin/env python3
"""Capture Labebe PDP source text for the 8-SKU decision sample.

This probe is intentionally conservative: it records official PDP text and
keyword contexts, but it does not promote any material, safety, dimension, or
certification claim into public copy.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path("/vol1/1000/projects/toyresearch")
WORK_DIR = ROOT / "planning/20260427_labebe_14day_execution/work_products/product_market_master"
OUT_DIR = WORK_DIR / "live_crawl_20260428/pdp_source_probe_v1"
LIVE_MASTER = WORK_DIR / "live_crawl_20260428/product_master_live_probe_v1.csv"
QA_DIR = ROOT / "qa/labebe_pdp_source_probe_v1"

SAMPLE_SKUS = [
    "pink-unicorn-plush-rocker",
    "cream-wooden-play-kitchen-set-with-storage",
    "foldable-learning-tower-montessori-kitchen-tower-log-color",
    "children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art",
    "kids-toy-storage-organizer-bookshelf-with-bins",
    "natural-wood-montessori-shelf-with-storage-boxes",
    "wooden-mud-kitchen-outdoor-play-kitchen-with-planter-box-sink",
    "activity-cube-baby-push-walker",
]

KEYWORDS = {
    "dimensions": ["dimension", "size", "inch", "height", "width", "length", "weight"],
    "materials": ["material", "wood", "pine", "birch", "mdf", "rubber wood", "finish", "paint"],
    "safety": ["safety", "safe", "cpc", "astm", "en71", "certified", "non-toxic", "warning"],
    "age": ["age", "month", "year", "toddler", "kids", "children"],
    "assembly": ["assembly", "assemble", "instruction", "tool", "installation"],
    "care": ["care", "clean", "wipe", "maintenance", "storage"],
    "shipping": ["shipping", "package", "box", "delivery"],
}


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def load_samples() -> list[dict[str, str]]:
    with LIVE_MASTER.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    by_sku = {row["sku_id"]: row for row in rows}
    samples = []
    missing = []
    for sku in SAMPLE_SKUS:
        row = by_sku.get(sku)
        if row:
            samples.append(row)
        else:
            missing.append(sku)
    if missing:
        raise SystemExit(f"Missing sample SKU(s) in live master: {', '.join(missing)}")
    return samples


def keyword_contexts(text: str) -> tuple[dict[str, int], dict[str, list[str]]]:
    lower = text.lower()
    hits: dict[str, int] = {}
    contexts: dict[str, list[str]] = {}
    lines = [norm(line) for line in text.splitlines() if norm(line)]
    for group, words in KEYWORDS.items():
        group_hits = 0
        group_contexts: list[str] = []
        for word in words:
            group_hits += lower.count(word)
        for line in lines:
            low_line = line.lower()
            if any(word in low_line for word in words):
                group_contexts.append(line[:260])
            if len(group_contexts) >= 8:
                break
        hits[group] = group_hits
        contexts[group] = group_contexts
    return hits, contexts


def extract_page(page, row: dict[str, str]) -> dict[str, object]:
    url = row["product_url"]
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2200)
    for _ in range(4):
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(450)

    data = page.evaluate(
        """
        () => {
          const text = document.body ? ((document.body.innerText || '').trim() || document.body.textContent || '') : '';
          const title = document.querySelector('h1')?.innerText || document.title || '';
          const buttons = [...document.querySelectorAll('button, a')].slice(0, 100).map((el) => (
            el.innerText || el.getAttribute('aria-label') || ''
          )).filter(Boolean);
          const images = [...document.querySelectorAll('img')].slice(0, 80).map((img) => ({
            src: img.currentSrc || img.src || img.getAttribute('data-src') || '',
            alt: img.alt || ''
          })).filter((img) => img.src);
          return {
            title,
            text,
            buttons,
            images,
            url: location.href,
            scrollHeight: document.documentElement.scrollHeight,
            bodyScrollWidth: document.body.scrollWidth,
            docScrollWidth: document.documentElement.scrollWidth,
            innerWidth
          };
        }
        """
    )
    return data


def write_claim_queue(context_rows: list[dict[str, object]]) -> Path:
    queue_path = OUT_DIR / "labebe_pdp_source_claim_review_queue_v1.csv"
    fieldnames = [
        "sku_id",
        "product_url",
        "claim_type",
        "source_excerpt",
        "decision",
        "decision_reason",
        "observed_at",
    ]
    queue_rows: list[dict[str, str]] = []
    for row in context_rows:
        contexts = row.get("contexts") or {}
        if not isinstance(contexts, dict):
            continue
        for claim_type, snippets in contexts.items():
            if not isinstance(snippets, list):
                continue
            for snippet in snippets:
                clean = norm(str(snippet))
                if not clean:
                    continue
                queue_rows.append({
                    "sku_id": str(row["sku_id"]),
                    "product_url": str(row["product_url"]),
                    "claim_type": str(claim_type),
                    "source_excerpt": clean[:500],
                    "decision": "manual_review_required",
                    "decision_reason": "Official PDP source text captured, but exact claim scope and public wording still need human review.",
                    "observed_at": str(row["observed_at"]),
                })
    with queue_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(queue_rows)
    return queue_path


def write_report(rows: list[dict[str, object]], manifest: dict[str, object]) -> None:
    report = OUT_DIR / "labebe_pdp_source_probe_report_v1.md"
    lines = [
        "# Labebe PDP Source Probe v1",
        "",
        f"Observed at: `{manifest['observed_at']}`",
        "",
        "## Summary",
        "",
        "This run captures official Labebe PDP text for the 8-SKU decision sample. It is a source-capture layer only; it does not approve public copy claims.",
        "",
        "| SKU | Text chars | Keyword hit groups | Source status | Screenshot |",
        "|---|---:|---|---|---|",
    ]
    for row in rows:
        groups = [
            group
            for group in KEYWORDS
            if int(row.get(f"{group}_hits", 0)) > 0
        ]
        lines.append(
            f"| `{row['sku_id']}` | {row['text_length']} | {', '.join(groups) or 'none'} | {row['source_status']} | `{row['screenshot']}` |"
        )

    lines.extend([
        "",
        "## Claim Gate Guidance",
        "",
        "- Treat keyword hits as review leads, not claim approvals.",
        "- Only promote exact, product-specific statements after a human reads the raw PDP text.",
        "- If a field is not present in the raw PDP text, keep the prototype wording generic or hide the field.",
        "- Safety, certification, material, weight capacity, and age claims need exact source text and manual approval.",
        "",
        "## Outputs",
        "",
        f"- CSV: `{OUT_DIR / 'labebe_pdp_source_probe_v1.csv'}`",
        f"- Context JSONL: `{OUT_DIR / 'labebe_pdp_source_contexts_v1.jsonl'}`",
        f"- Claim review queue: `{OUT_DIR / 'labebe_pdp_source_claim_review_queue_v1.csv'}`",
        f"- Raw text folder: `{OUT_DIR / 'raw_text'}`",
        f"- Screenshots: `{QA_DIR}`",
    ])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "raw_text").mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    samples = load_samples()
    observed_at = datetime.now(timezone.utc).isoformat()
    output_rows: list[dict[str, object]] = []
    context_rows: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1200},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        for product in samples:
            sku = product["sku_id"]
            screenshot = QA_DIR / f"{sku}.png"
            raw_text_path = OUT_DIR / "raw_text" / f"{sku}.txt"
            try:
                extracted = extract_page(page, product)
                text = norm(str(extracted.get("text") or ""))
                raw_text_path.write_text(str(extracted.get("text") or ""), encoding="utf-8")
                page.screenshot(path=str(screenshot), full_page=True)
                hits, contexts = keyword_contexts(str(extracted.get("text") or ""))
                status = "captured_official_pdp_text" if len(text) > 800 else "captured_but_text_thin"
                output_row: dict[str, object] = {
                    "sku_id": sku,
                    "title_clean": product["title_clean"],
                    "product_url": product["product_url"],
                    "resolved_url": extracted.get("url", ""),
                    "source_status": status,
                    "text_length": len(text),
                    "button_count": len(extracted.get("buttons") or []),
                    "image_count": len(extracted.get("images") or []),
                    "horizontal_overflow": bool(
                        extracted.get("docScrollWidth", 0) > extracted.get("innerWidth", 0) + 2
                        or extracted.get("bodyScrollWidth", 0) > extracted.get("innerWidth", 0) + 2
                    ),
                    "raw_text_path": str(raw_text_path),
                    "screenshot": str(screenshot),
                    "observed_at": observed_at,
                }
                for group, count in hits.items():
                    output_row[f"{group}_hits"] = count
                output_rows.append(output_row)
                context_rows.append({
                    "sku_id": sku,
                    "product_url": product["product_url"],
                    "contexts": contexts,
                    "observed_at": observed_at,
                })
                print(f"{sku}: {status}, chars={len(text)}")
            except Exception as exc:  # noqa: BLE001
                failures.append({"sku_id": sku, "product_url": product.get("product_url", ""), "error": repr(exc)})
                print(f"{sku}: ERROR {exc!r}")
        context.close()
        browser.close()

    csv_path = OUT_DIR / "labebe_pdp_source_probe_v1.csv"
    fieldnames = [
        "sku_id",
        "title_clean",
        "product_url",
        "resolved_url",
        "source_status",
        "text_length",
        "button_count",
        "image_count",
        "horizontal_overflow",
        "dimensions_hits",
        "materials_hits",
        "safety_hits",
        "age_hits",
        "assembly_hits",
        "care_hits",
        "shipping_hits",
        "raw_text_path",
        "screenshot",
        "observed_at",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    context_path = OUT_DIR / "labebe_pdp_source_contexts_v1.jsonl"
    with context_path.open("w", encoding="utf-8") as f:
        for row in context_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    claim_queue_path = write_claim_queue(context_rows)

    manifest = {
        "observed_at": observed_at,
        "sample_count": len(samples),
        "captured_count": len(output_rows),
        "failures": failures,
        "csv": str(csv_path),
        "contexts_jsonl": str(context_path),
        "claim_review_queue_csv": str(claim_queue_path),
        "raw_text_dir": str(OUT_DIR / "raw_text"),
        "screenshot_dir": str(QA_DIR),
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_report(output_rows, manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
