#!/usr/bin/env python3
"""Download and compare sample Amazon images against DTC/live probe images."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import urllib.request
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageOps


BASE = Path(__file__).resolve().parent
LIVE_DIR = BASE / "live_crawl_20260428"
OUT_DIR = LIVE_DIR / "image_identity_sample"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLES = [
    {
        "sku_id": "pink-unicorn-plush-rocker",
        "asin": "B072LXVM36",
        "dtc_local_path": "/vol1/1000/projects/toyresearch/data/labebe/images/pink-unicorn-plush-rocker.jpg",
    },
    {
        "sku_id": "doll-stroller-baby-push-walker",
        "asin": "B087P9SXZQ",
        "dtc_local_path": "",
    },
]


def fetch_url(url: str, path: Path) -> bool:
    if path.exists() and path.stat().st_size > 1000:
        return True
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            path.write_bytes(resp.read())
        return path.stat().st_size > 1000
    except Exception:
        return False


def pick_amazon_image(asin: str) -> str:
    data = json.loads((LIVE_DIR / f"amazon_{asin}_structured.json").read_text(encoding="utf-8"))
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
        if "product_insurance" in src or "Shop Cakes body" in alt:
            continue
        score = width * height
        if alt and ("labebe" in alt.lower() or asin == "B072LXVM36"):
            score += 100000
        candidates.append((score, src))
    if not candidates:
        return ""
    return sorted(candidates, reverse=True)[0][1]


def pick_dtc_image(sample: dict[str, str], live: pd.DataFrame) -> tuple[str, Path]:
    local_path = sample.get("dtc_local_path")
    if local_path and Path(local_path).exists():
        return "local_catalog", Path(local_path)
    row = live[live["slug"].eq(sample["sku_id"])].head(1)
    if len(row) and str(row.iloc[0].get("image_url_probe") or "").startswith("http"):
        url = str(row.iloc[0]["image_url_probe"])
        out = OUT_DIR / f"{sample['sku_id']}_dtc_probe.jpg"
        ok = fetch_url(url, out)
        if ok:
            return "live_probe_url", out
    return "missing", Path("")


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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_contact_sheet(rows: list[dict[str, str]]) -> None:
    cell_w, cell_h = 420, 360
    sheet = Image.new("RGB", (cell_w * 2, cell_h * len(rows)), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, row in enumerate(rows):
        y0 = idx * cell_h
        for col, key in enumerate(["dtc_path", "amazon_path"]):
            x0 = col * cell_w
            path = Path(row[key])
            try:
                img = Image.open(path).convert("RGB")
                img.thumbnail((cell_w - 28, cell_h - 80), Image.Resampling.LANCZOS)
                sheet.paste(img, (x0 + 14, y0 + 44))
            except Exception:
                pass
            label = "DTC" if key == "dtc_path" else "Amazon"
            draw.text((x0 + 14, y0 + 12), f"{label}: {row['sku_id']} / {row['asin']}", fill=(0, 0, 0))
        draw.text((14, y0 + cell_h - 28), f"hash_sim={row['hash_similarity']} color_sim={row['color_similarity']} decision={row['visual_match_status']}", fill=(0, 0, 0))
    sheet.save(OUT_DIR / "amazon_dtc_image_identity_contact_sheet.jpg", quality=90)


def main() -> None:
    live = pd.read_csv(LIVE_DIR / "labebe_products_live_probe.csv")
    out_rows = []

    for sample in SAMPLES:
        amazon_url = pick_amazon_image(sample["asin"])
        amazon_path = OUT_DIR / f"{sample['asin']}_amazon_main.jpg"
        amazon_ok = fetch_url(amazon_url, amazon_path) if amazon_url else False
        dtc_source, dtc_path = pick_dtc_image(sample, live)

        if amazon_ok and dtc_path.exists():
            hash_sim = round((hamming_similarity(ahash(amazon_path), ahash(dtc_path)) + hamming_similarity(dhash(amazon_path), dhash(dtc_path))) / 2, 4)
            color_sim = round(color_hist_similarity(amazon_path, dtc_path), 4)
            if hash_sim >= 0.72 or color_sim >= 0.75:
                status = "probable_visual_match"
            elif hash_sim >= 0.58 or color_sim >= 0.55:
                status = "weak_visual_match_needs_human_review"
            else:
                status = "visual_mismatch_or_different_asset_needs_review"
        else:
            hash_sim = 0.0
            color_sim = 0.0
            status = "image_download_or_source_missing"

        out_rows.append(
            {
                "sku_id": sample["sku_id"],
                "asin": sample["asin"],
                "dtc_source": dtc_source,
                "dtc_path": str(dtc_path),
                "amazon_image_url": amazon_url,
                "amazon_path": str(amazon_path) if amazon_ok else "",
                "dtc_sha256": sha256(dtc_path) if dtc_path.exists() else "",
                "amazon_sha256": sha256(amazon_path) if amazon_ok else "",
                "hash_similarity": hash_sim,
                "color_similarity": color_sim,
                "visual_match_status": status,
                "note": "Automated similarity is a triage signal, not final proof; use contact sheet for human visual review.",
            }
        )

    with (OUT_DIR / "amazon_dtc_image_identity_sample.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    make_contact_sheet(out_rows)
    print(json.dumps({"rows": out_rows, "out_dir": str(OUT_DIR)}, indent=2))


if __name__ == "__main__":
    main()
