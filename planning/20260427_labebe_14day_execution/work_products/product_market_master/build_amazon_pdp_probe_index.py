#!/usr/bin/env python3
"""Index all Amazon PDP Browser Harness probe JSON files."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
LIVE_DIR = BASE / "live_crawl_20260428"
QA_DIR = Path("/vol1/1000/projects/toyresearch/qa/marketplace_probe")
SEARCH_SUMMARY = LIVE_DIR / "amazon_search_candidate_summary_v1.csv"
OUT_FACTS = LIVE_DIR / "amazon_pdp_probe_facts_v1.csv"
OUT_SKU_CANDIDATES = LIVE_DIR / "amazon_pdp_probe_sku_candidates_v1.csv"
OUT_REPORT = LIVE_DIR / "amazon_pdp_probe_index_v1.md"


def clean_int(value: object) -> str:
    match = re.search(r"[\d,]+", str(value or ""))
    return match.group(0).replace(",", "") if match else ""


def clean_float(value: object) -> str:
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return match.group(0) if match else ""


def probe_quality(data: dict) -> tuple[str, str]:
    page_state = data.get("page_state") or {}
    if page_state.get("captcha_like"):
        return "blocked_captcha_like", "PDP capture hit captcha-like page."
    if page_state.get("blank_like") or int(page_state.get("body_text_len") or 0) < 300:
        return "weak_blank_or_incomplete", "PDP capture is blank or too short; retry or use provider."
    if not data.get("rating_text") and not data.get("review_count_text"):
        return "weak_no_marketplace_social_proof", "PDP capture has title but no rating/review; may be unavailable, region-limited, or incomplete."
    if not data.get("sold_by"):
        return "partial_no_seller", "PDP capture has social proof but seller field is missing; needs retry or provider."
    return "usable_pdp_fact_sample", "PDP captured title, social proof, seller/ship fields and screenshot."


def main() -> None:
    search = pd.read_csv(SEARCH_SUMMARY) if SEARCH_SUMMARY.exists() else pd.DataFrame()
    candidate_by_asin: dict[str, list[dict]] = {}
    if not search.empty:
        for _, row in search.iterrows():
            asin = str(row.get("asin") or "")
            if not asin:
                continue
            candidate_by_asin.setdefault(asin, []).append(
                {
                    "sku_id": row.get("sku_id", ""),
                    "dtc_title": row.get("dtc_title", ""),
                    "candidate_score": row.get("candidate_score", ""),
                    "search_candidate_status": row.get("search_candidate_status", ""),
                    "search_candidate_note": row.get("search_candidate_note", ""),
                }
            )

    fact_rows = []
    candidate_rows = []
    for path in sorted(LIVE_DIR.glob("amazon_*_structured.json")):
        asin = path.name.removeprefix("amazon_").removesuffix("_structured.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        quality, note = probe_quality(data)
        candidates = candidate_by_asin.get(asin, [])
        fact_rows.append(
            {
                "asin": asin,
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
                "image_count": data.get("image_count", ""),
                "body_text_len": (data.get("page_state") or {}).get("body_text_len", ""),
                "blank_like": (data.get("page_state") or {}).get("blank_like", ""),
                "captcha_like": (data.get("page_state") or {}).get("captcha_like", ""),
                "probe_quality": quality,
                "probe_quality_note": note,
                "candidate_sku_count": len(candidates),
                "candidate_skus": ";".join(str(item.get("sku_id", "")) for item in candidates),
                "source_json": str(path),
                "source_screenshot": str(QA_DIR / f"amazon_{asin}_structured.png"),
                "observed_at": data.get("captured_at", ""),
            }
        )
        for item in candidates:
            candidate_rows.append(
                {
                    "asin": asin,
                    "sku_id": item.get("sku_id", ""),
                    "dtc_title": item.get("dtc_title", ""),
                    "candidate_score": item.get("candidate_score", ""),
                    "search_candidate_status": item.get("search_candidate_status", ""),
                    "pdp_probe_quality": quality,
                    "pdp_title": data.get("title", ""),
                    "pdp_rating": clean_float(data.get("rating_text", "")),
                    "pdp_review_count": clean_int(data.get("review_count_text", "")),
                    "source_json": str(path),
                }
            )

    facts = pd.DataFrame(fact_rows)
    sku_candidates = pd.DataFrame(candidate_rows)
    facts.to_csv(OUT_FACTS, index=False, encoding="utf-8-sig")
    sku_candidates.to_csv(OUT_SKU_CANDIDATES, index=False, encoding="utf-8-sig")

    quality_counts = facts["probe_quality"].value_counts().sort_index().to_dict() if not facts.empty else {}
    lines = [
        "# Amazon PDP Probe Index",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Boundary",
        "",
        "This table indexes PDP evidence. It does not promote a SKU-to-ASIN match by itself. Promotion still requires image, title, seller/variant and claim gates.",
        "",
        "## Counts",
        "",
        f"- PDP JSON files indexed: {len(facts)}",
        f"- ASIN-to-SKU candidate rows joined: {len(sku_candidates)}",
    ]
    for quality, count in quality_counts.items():
        lines.append(f"- {quality}: {count}")
    lines.extend(
        [
            "",
            "## Usable / Partial PDP Facts",
            "",
            facts[[
                "asin",
                "probe_quality",
                "price",
                "rating",
                "review_count",
                "sold_by",
                "candidate_sku_count",
                "candidate_skus",
                "title",
            ]].to_markdown(index=False)
            if not facts.empty
            else "No PDP facts indexed.",
            "",
            "## Outputs",
            "",
            f"- `{OUT_FACTS.name}`",
            f"- `{OUT_SKU_CANDIDATES.name}`",
        ]
    )
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"facts": str(OUT_FACTS), "sku_candidates": str(OUT_SKU_CANDIDATES), "report": str(OUT_REPORT)}, indent=2))


if __name__ == "__main__":
    main()
