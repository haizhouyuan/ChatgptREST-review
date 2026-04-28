#!/usr/bin/env python3
"""Build a DTC-vs-Amazon visual gate sheet for PDP candidates."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import urllib.request
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageOps


BASE = Path(__file__).resolve().parent
LIVE_DIR = BASE / "live_crawl_20260428"
OUT_DIR = LIVE_DIR / "image_identity_expanded_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PRODUCT_MASTER = LIVE_DIR / "product_master_live_probe_v1.csv"
PDP_CANDIDATES = LIVE_DIR / "amazon_pdp_probe_sku_candidates_v1.csv"
PDP_FACTS = LIVE_DIR / "amazon_pdp_probe_facts_v1.csv"


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")[:140]


def fetch_url(url: str, path: Path) -> bool:
    if path.exists() and path.stat().st_size > 1000:
        return True
    if not str(url).startswith("http"):
        return False
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            path.write_bytes(resp.read())
        return path.stat().st_size > 1000
    except Exception:
        return False


def pick_amazon_image(asin: str) -> str:
    path = LIVE_DIR / f"amazon_{asin}_structured.json"
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates = []
    for img in data.get("images", []):
        src = img.get("src", "")
        alt = img.get("alt", "")
        width = int(img.get("width") or 0)
        height = int(img.get("height") or 0)
        if not src.startswith("http"):
            continue
        if "m.media-amazon.com/images/I/" not in src:
            continue
        if any(bad in src.lower() for bad in ["sprite", "transparent", "grey-pixel"]):
            continue
        score = width * height
        if alt and "labebe" in alt.lower():
            score += 100000
        candidates.append((score, src))
    return sorted(candidates, reverse=True)[0][1] if candidates else ""


def ahash(path: Path, size: int = 16) -> str:
    img = Image.open(path).convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    return "".join("1" if p >= avg else "0" for p in pixels)


def dhash(path: Path, size: int = 16) -> str:
    img = Image.open(path).convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    bits = []
    for y in range(size):
        for x in range(size):
            bits.append("1" if img.getpixel((x, y)) > img.getpixel((x + 1, y)) else "0")
    return "".join(bits)


def hamming_similarity(a: str, b: str) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dist = sum(x != y for x, y in zip(a, b))
    return 1 - dist / len(a)


def color_hist_similarity(a: Path, b: Path) -> float:
    def hist(path: Path) -> list[float]:
        img = Image.open(path).convert("RGB").resize((128, 128), Image.Resampling.LANCZOS)
        raw = img.histogram()
        total = sum(raw) or 1
        return [x / total for x in raw]

    ha, hb = hist(a), hist(b)
    dot = sum(x * y for x, y in zip(ha, hb))
    na = math.sqrt(sum(x * x for x in ha))
    nb = math.sqrt(sum(y * y for y in hb))
    return dot / (na * nb) if na and nb else 0.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def token_set(value: str) -> set[str]:
    stop = {
        "and",
        "with",
        "for",
        "the",
        "toy",
        "toys",
        "kids",
        "kid",
        "baby",
        "toddler",
        "toddlers",
        "wooden",
        "labebe",
        "plush",
        "rocking",
        "horse",
        "set",
    }
    return {t for t in re.findall(r"[a-z0-9]+", str(value).lower()) if len(t) > 2 and t not in stop}


def visual_decision(row: dict[str, str]) -> tuple[str, str]:
    quality = row["pdp_probe_quality"]
    title_overlap = float(row["title_token_overlap"])
    search_status = row["search_candidate_status"]
    hash_sim = float(row["hash_similarity"])
    color_sim = float(row["color_similarity"])
    if quality != "usable_pdp_fact_sample":
        return "blocked_weak_pdp_probe", "PDP probe is weak or incomplete; retry or provider source required before visual promotion."
    if search_status == "search_competitor_or_generic_top_result" and title_overlap < 0.45:
        return "blocked_search_false_positive", "Search candidate status and title overlap indicate likely wrong product or competitor."
    if hash_sim >= 0.70 or color_sim >= 0.62:
        return "visual_probable_same_product", "Automated visual similarity is strong enough for probable match, pending human review."
    if title_overlap >= 0.62:
        return "visual_needs_human_review_title_promising", "Title overlap is strong but image similarity is weak; likely scene/variant issue."
    return "visual_needs_human_review", "Image similarity and title overlap are not sufficient for automatic promotion."


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, width: int) -> None:
    words = str(text).split()
    lines = []
    cur = ""
    for word in words:
        nxt = f"{cur} {word}".strip()
        if len(nxt) > width:
            lines.append(cur)
            cur = word
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    x, y = xy
    for line in lines[:5]:
        draw.text((x, y), line, fill=(0, 0, 0))
        y += 16


def make_contact_sheet(rows: list[dict[str, str]]) -> Path:
    cell_w, cell_h = 420, 430
    sheet_path = OUT_DIR / "amazon_dtc_visual_gate_contact_sheet_v1.jpg"
    sheet = Image.new("RGB", (cell_w * 2, cell_h * len(rows)), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, row in enumerate(rows):
        y0 = idx * cell_h
        for col, key in enumerate(["dtc_path", "amazon_path"]):
            x0 = col * cell_w
            draw.rectangle([x0, y0, x0 + cell_w - 1, y0 + cell_h - 1], outline=(218, 218, 218))
            label = "DTC" if key == "dtc_path" else "Amazon"
            draw.text((x0 + 14, y0 + 12), f"{label}: {row['sku_id']} / {row['asin']}", fill=(0, 0, 0))
            try:
                img = Image.open(row[key]).convert("RGB")
                img = ImageOps.contain(img, (cell_w - 28, 250), Image.Resampling.LANCZOS)
                sheet.paste(img, (x0 + (cell_w - img.width) // 2, y0 + 46))
            except Exception:
                draw.text((x0 + 14, y0 + 100), "image missing", fill=(160, 0, 0))
            title = row["dtc_title"] if key == "dtc_path" else row["pdp_title"]
            draw_text(draw, (x0 + 14, y0 + 310), title, 48)
        draw_text(
            draw,
            (14, y0 + cell_h - 54),
            f"{row['visual_gate_status']} | hash={row['hash_similarity']} color={row['color_similarity']} title={row['title_token_overlap']}",
            96,
        )
    sheet.save(sheet_path, quality=90)
    return sheet_path


def main() -> None:
    products = pd.read_csv(PRODUCT_MASTER)
    candidates = pd.read_csv(PDP_CANDIDATES)
    facts = pd.read_csv(PDP_FACTS)
    product_by_sku = products.set_index("sku_id").to_dict("index")
    fact_by_asin = facts.set_index("asin").to_dict("index")
    out_rows: list[dict[str, str]] = []

    for _, cand in candidates.iterrows():
        sku_id = str(cand.get("sku_id") or "")
        asin = str(cand.get("asin") or "")
        product = product_by_sku.get(sku_id, {})
        fact = fact_by_asin.get(asin, {})
        dtc_url = str(product.get("primary_image_url_probe") or "")
        amazon_url = pick_amazon_image(asin)
        dtc_path = OUT_DIR / f"{safe_name(sku_id)}_dtc.jpg"
        amazon_path = OUT_DIR / f"{asin}_amazon.jpg"
        dtc_ok = fetch_url(dtc_url, dtc_path)
        amazon_ok = fetch_url(amazon_url, amazon_path)
        if dtc_ok and amazon_ok:
            hash_sim = round((hamming_similarity(ahash(dtc_path), ahash(amazon_path)) + hamming_similarity(dhash(dtc_path), dhash(amazon_path))) / 2, 4)
            color_sim = round(color_hist_similarity(dtc_path, amazon_path), 4)
        else:
            hash_sim = 0.0
            color_sim = 0.0
        dtc_tokens = token_set(str(cand.get("dtc_title") or product.get("title_clean") or ""))
        pdp_tokens = token_set(str(cand.get("pdp_title") or fact.get("title") or ""))
        title_overlap = round(len(dtc_tokens & pdp_tokens) / max(1, len(dtc_tokens)), 4)
        row = {
            "sku_id": sku_id,
            "asin": asin,
            "dtc_title": str(cand.get("dtc_title") or product.get("title_clean") or ""),
            "pdp_title": str(cand.get("pdp_title") or fact.get("title") or ""),
            "pdp_probe_quality": str(cand.get("pdp_probe_quality") or fact.get("probe_quality") or ""),
            "search_candidate_status": str(cand.get("search_candidate_status") or ""),
            "candidate_score": str(cand.get("candidate_score") or ""),
            "pdp_rating": str(cand.get("pdp_rating") or ""),
            "pdp_review_count": str(cand.get("pdp_review_count") or ""),
            "dtc_image_url": dtc_url,
            "amazon_image_url": amazon_url,
            "dtc_path": str(dtc_path) if dtc_ok else "",
            "amazon_path": str(amazon_path) if amazon_ok else "",
            "dtc_sha256": sha256(dtc_path) if dtc_ok else "",
            "amazon_sha256": sha256(amazon_path) if amazon_ok else "",
            "hash_similarity": str(hash_sim),
            "color_similarity": str(color_sim),
            "title_token_overlap": str(title_overlap),
        }
        status, note = visual_decision(row)
        row["visual_gate_status"] = status
        row["visual_gate_note"] = note
        out_rows.append(row)

    out_csv = LIVE_DIR / "amazon_dtc_visual_gate_v1.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    sheet_path = make_contact_sheet(out_rows)

    counts = pd.Series([row["visual_gate_status"] for row in out_rows]).value_counts().sort_index().to_dict()
    report = LIVE_DIR / "amazon_dtc_visual_gate_v1.md"
    lines = [
        "# Amazon DTC Visual Gate v1",
        "",
        "## Boundary",
        "",
        "This is a visual triage artifact. It does not independently approve a marketplace match for public copy. Use it to decide which ASINs deserve human review, retry, provider extraction, or claim gating.",
        "",
        "## Counts",
        "",
        f"- Candidate visual rows: {len(out_rows)}",
    ]
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- `{out_csv.name}`",
            f"- `image_identity_expanded_v1/{sheet_path.name}`",
        ]
    )
    report.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"csv": str(out_csv), "contact_sheet": str(sheet_path), "report": str(report), "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
