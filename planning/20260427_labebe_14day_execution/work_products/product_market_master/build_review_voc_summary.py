#!/usr/bin/env python3
"""Build a conservative internal VOC summary from authorized review CSVs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

THEMES = {
    "gift_moment": ["gift", "birthday", "christmas", "granddaughter", "grandson", "niece", "nephew", "present"],
    "assembly_instruction": ["assembly", "assemble", "instructions", "screw", "part", "parts", "holes", "driver", "manual"],
    "stability_safety": ["sturdy", "stable", "tipped", "tip", "safe", "seat belt", "balance", "wobble", "stability"],
    "wheel_mobility": ["wheel", "wheels", "roll", "turn", "steer", "squeak", "straight", "resistance"],
    "material_quality": ["quality", "wood", "fabric", "plush", "thread", "finish", "durable", "broke", "break"],
    "design_aesthetic": ["cute", "beautiful", "adorable", "design", "aesthetic", "nursery", "color", "matches"],
    "size_fit": ["size", "height", "larger", "small", "tall", "short", "age", "one year", "1 year"],
    "child_engagement": ["loves", "love", "favorite", "fun", "play", "push", "walk", "learning to walk"],
}


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def rating_bucket(value: str) -> str:
    try:
        rating = float(value)
    except Exception:
        return "unknown"
    if rating >= 4:
        return "positive_4_5"
    if rating == 3:
        return "mixed_3"
    if rating > 0:
        return "negative_1_2"
    return "unknown"


def review_text(row: dict[str, str]) -> str:
    return clean(f"{row.get('title', '')} {row.get('body', '')}")


def theme_hits(text: str) -> list[str]:
    lower = text.lower()
    hits = []
    for theme, keywords in THEMES.items():
        if any(keyword in lower for keyword in keywords):
            hits.append(theme)
    return hits or ["uncategorized"]


def quote_snippet(text: str, max_len: int = 220) -> str:
    text = clean(text)
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "..."


def read_reviews(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                row["_source_file"] = str(path)
                rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fallback_header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else fallback_header
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--label", default="authorized_reviews")
    parser.add_argument("--identity-warning", default="")
    args = parser.parse_args()

    rows = read_reviews(args.inputs)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    by_sku: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        sku = clean(row.get("sku_id")) or clean(row.get("asin")) or "unknown"
        by_sku[sku].append(row)

    summary_rows: list[dict[str, Any]] = []
    quote_rows: list[dict[str, Any]] = []
    for sku, sku_rows in by_sku.items():
        theme_counter: Counter[str] = Counter()
        rating_counter: Counter[str] = Counter()
        quote_counts: Counter[str] = Counter()
        for row in sku_rows:
            text = review_text(row)
            rating_counter[rating_bucket(row.get("rating", ""))] += 1
            for theme in theme_hits(text):
                theme_counter[theme] += 1
                if text and quote_counts[theme] < 3:
                    quote_counts[theme] += 1
                    quote_rows.append(
                        {
                            "sku_id": sku,
                            "asin": clean(row.get("asin")),
                            "theme": theme,
                            "rating": clean(row.get("rating")),
                            "date": clean(row.get("date")),
                            "verified": clean(row.get("isVerifiedPurchase")),
                            "snippet": quote_snippet(text),
                            "source_file": row.get("_source_file", ""),
                            "public_copy_allowed": "no",
                        }
                    )
        total = len(sku_rows)
        for theme, count in theme_counter.most_common():
            summary_rows.append(
                {
                    "sku_id": sku,
                    "theme": theme,
                    "mentions": count,
                    "share_of_reviews": round(count / total, 4) if total else 0,
                    "total_reviews_in_input": total,
                    "positive_4_5": rating_counter["positive_4_5"],
                    "mixed_3": rating_counter["mixed_3"],
                    "negative_1_2": rating_counter["negative_1_2"],
                    "unknown_rating": rating_counter["unknown"],
                    "public_copy_allowed": "no",
                }
            )

    summary_csv = args.out_dir / f"{args.label}_voc_theme_summary_v1.csv"
    quotes_csv = args.out_dir / f"{args.label}_voc_quote_queue_v1.csv"
    manifest_json = args.out_dir / f"{args.label}_voc_manifest_v1.json"
    report_md = args.out_dir / f"{args.label}_voc_report_v1.md"

    write_csv(summary_csv, summary_rows, ["sku_id", "theme", "mentions"])
    write_csv(quotes_csv, quote_rows, ["sku_id", "theme", "snippet"])

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "input_files": [str(path) for path in args.inputs],
        "input_review_rows": len(rows),
        "sku_count": len(by_sku),
        "summary_csv": str(summary_csv),
        "quote_queue_csv": str(quotes_csv),
        "identity_warning": args.identity_warning,
        "public_copy_allowed": False,
        "claim_gate_required": True,
    }
    manifest_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# VOC Summary v1: {args.label}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Boundary",
        "",
        "This is an internal review-analysis artifact. It does not authorize public review quotes, product claims, safety claims, ratings, or marketplace performance claims.",
    ]
    if args.identity_warning:
        lines += ["", f"Identity warning: {args.identity_warning}"]
    lines += [
        "",
        "## Summary",
        "",
        f"- Input review rows: {len(rows)}",
        f"- SKU/ASIN groups: {len(by_sku)}",
        f"- Theme rows: {len(summary_rows)}",
        f"- Quote queue rows: {len(quote_rows)}",
        "",
        "## Top Theme Rows",
        "",
        "| SKU | Theme | Mentions | Share | Reviews |",
        "|---|---|---:|---:|---:|",
    ]
    for row in summary_rows[:20]:
        lines.append(
            f"| {row['sku_id']} | {row['theme']} | {row['mentions']} | "
            f"{row['share_of_reviews']} | {row['total_reviews_in_input']} |"
        )
    lines += ["", f"Full summary: `{summary_csv.name}`", f"Quote queue: `{quotes_csv.name}`"]
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
