#!/usr/bin/env python3
"""Summarize Amazon search-candidate output into a PDP-verification queue."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


BASE = Path(__file__).resolve().parent
LIVE_DIR = BASE / "live_crawl_20260428"
FULL_CSV = LIVE_DIR / "amazon_search_candidates_full_v1.csv"
OUT_SUMMARY = LIVE_DIR / "amazon_search_candidate_summary_v1.csv"
OUT_DUPES = LIVE_DIR / "amazon_search_candidate_duplicate_asins_v1.csv"
OUT_REPORT = LIVE_DIR / "amazon_search_candidate_summary_v1.md"


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def tokenize(value: str) -> set[str]:
    stop = {
        "and",
        "with",
        "for",
        "the",
        "set",
        "kids",
        "kid",
        "toy",
        "toys",
        "wooden",
        "labebe",
        "baby",
        "toddler",
        "toddlers",
        "children",
        "girls",
        "boys",
    }
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2 and token not in stop}


def looks_labebe(row: pd.Series) -> bool:
    title = norm(row.get("amazon_title")).lower()
    url = norm(row.get("amazon_url")).lower()
    image = norm(row.get("amazon_image")).lower()
    return "labebe" in title or "/labebe-" in url or "/labebe_" in url or "labebe-" in image


def candidate_score(row: pd.Series) -> int:
    score = 0
    if looks_labebe(row):
        score += 45
    try:
        rank = int(float(row.get("amazon_rank") or 99))
    except ValueError:
        rank = 99
    score += max(0, 20 - (rank - 1) * 3)
    dtc_tokens = tokenize(norm(row.get("dtc_title")))
    amazon_tokens = tokenize(norm(row.get("amazon_title")))
    if dtc_tokens and amazon_tokens:
        overlap = len(dtc_tokens & amazon_tokens) / max(1, len(dtc_tokens))
        score += round(overlap * 30)
    if norm(row.get("asin")):
        score += 5
    return min(score, 100)


def classify_top(row: pd.Series, duplicate_count: int) -> tuple[str, str]:
    score = int(row["candidate_score"])
    labebe_like = bool(row["labebe_like"])
    if not norm(row.get("asin")):
        return "no_asin_from_search", "No ASIN was extracted from the top candidate."
    if labebe_like and score >= 70 and duplicate_count == 1:
        return "pdp_queue_high_confidence", "Labebe-like top search result; run PDP probe and image/variant gate."
    if labebe_like and score >= 70 and duplicate_count > 1:
        return "pdp_queue_variant_cluster", "Labebe-like ASIN is shared by multiple DTC SKUs; run PDP variation and image gate before mapping."
    if labebe_like:
        return "pdp_queue_needs_review", "Labebe-like candidate, but title overlap or rank is weak."
    return "search_competitor_or_generic_top_result", "Top result appears to be a competitor or generic category result; keep as discovery context only."


def main() -> None:
    df = pd.read_csv(FULL_CSV)
    df["labebe_like"] = df.apply(looks_labebe, axis=1)
    df["candidate_score"] = df.apply(candidate_score, axis=1)
    df["amazon_rank_num"] = pd.to_numeric(df["amazon_rank"], errors="coerce").fillna(99)

    top = (
        df.sort_values(["sku_id", "amazon_rank_num", "candidate_score"], ascending=[True, True, False])
        .groupby("sku_id", as_index=False)
        .head(1)
        .copy()
    )
    duplicate_counts = top["asin"].value_counts().to_dict()
    statuses = top.apply(lambda row: classify_top(row, int(duplicate_counts.get(row["asin"], 0))), axis=1)
    top["search_candidate_status"] = [status for status, _ in statuses]
    top["search_candidate_note"] = [note for _, note in statuses]
    top["duplicate_top_asin_count"] = top["asin"].map(duplicate_counts).fillna(0).astype(int)

    summary_cols = [
        "sku_id",
        "dtc_title",
        "dtc_price",
        "dtc_review_count_visible",
        "asin",
        "amazon_rank",
        "amazon_title",
        "amazon_price",
        "amazon_rating_text",
        "amazon_review_count_text",
        "amazon_url",
        "amazon_image",
        "labebe_like",
        "candidate_score",
        "duplicate_top_asin_count",
        "search_candidate_status",
        "search_candidate_note",
        "screenshot",
    ]
    top[summary_cols].sort_values(["search_candidate_status", "candidate_score"], ascending=[True, False]).to_csv(
        OUT_SUMMARY, index=False, encoding="utf-8-sig"
    )

    dupes = (
        top[top["duplicate_top_asin_count"].gt(1)]
        .sort_values(["asin", "candidate_score"], ascending=[True, False])
        [["asin", "sku_id", "dtc_title", "amazon_title", "candidate_score", "search_candidate_status"]]
    )
    dupes.to_csv(OUT_DUPES, index=False, encoding="utf-8-sig")

    status_counts = top["search_candidate_status"].value_counts().sort_index().to_dict()
    high = top[top["search_candidate_status"].isin(["pdp_queue_high_confidence", "pdp_queue_variant_cluster"])].copy()
    lines = [
        "# Amazon Search Candidate Summary",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Boundary",
        "",
        "Search pages are candidate discovery only. Do not use search-page price, rating or review count as product facts. Promote only through PDP Browser Harness and image/variant gates.",
        "",
        "## Counts",
        "",
        f"- Searched SKUs: {top['sku_id'].nunique()}",
        f"- Candidate rows captured: {len(df)}",
        f"- Unique top ASINs: {top['asin'].nunique()}",
    ]
    for status, count in status_counts.items():
        lines.append(f"- {status}: {count}")
    lines.extend(
        [
            "",
            "## Next PDP Queue",
            "",
            high[[
                "sku_id",
                "asin",
                "candidate_score",
                "duplicate_top_asin_count",
                "search_candidate_status",
                "amazon_title",
            ]].head(25).to_markdown(index=False)
            if not high.empty
            else "No high-confidence PDP queue rows.",
            "",
            "## Duplicate Top ASINs",
            "",
            dupes.head(40).to_markdown(index=False) if not dupes.empty else "No duplicate top ASINs.",
            "",
            "## Outputs",
            "",
            f"- `{OUT_SUMMARY.name}`",
            f"- `{OUT_DUPES.name}`",
        ]
    )
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"summary": str(OUT_SUMMARY), "dupes": str(OUT_DUPES), "report": str(OUT_REPORT)}, indent=2))


if __name__ == "__main__":
    main()
