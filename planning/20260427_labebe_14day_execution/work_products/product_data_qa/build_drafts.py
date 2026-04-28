"""Build the WP-A draft artifacts from local Labebe scrape outputs.

Inputs:
  - data/labebe/labebe_products.csv             (CSV A; canonical 46-row product list)
  - data/labebe/labebe_products_with_images.csv (CSV B; older/stale mirror; kept for QA)
  - data/labebe/all_product_images.json         (PDP gallery URL index per slug)
  - data/labebe/images/                          (local image files)

Outputs (written next to this script):
  - product_master_v0_draft.csv
  - slug_image_join_report_draft.csv
  - dirty_title_parse_report_draft.csv
  - evidence/source_hashes.json
  - evidence/build_drafts_log.txt

The script does NOT modify any source file. It is the fully reproducible record
of the parsing/joining done for this WP-A handoff. Re-run with:

    python3 planning/20260427_labebe_14day_execution/work_products/product_data_qa/build_drafts.py

Re-runs are idempotent.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "data" / "labebe"
OUT_DIR = Path(__file__).resolve().parent
EVIDENCE_DIR = OUT_DIR / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

CSV_A = DATA_DIR / "labebe_products.csv"
CSV_B = DATA_DIR / "labebe_products_with_images.csv"
JSON_GALLERIES = DATA_DIR / "all_product_images.json"
IMG_DIR = DATA_DIR / "images"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_slug(s: str) -> str:
    """Remove the inserted hyphen between a word and a trailing 's' that the
    listing scrape sometimes produces (`children-s-` -> `childrens-`)."""
    return re.sub(r"(\w)-s-", r"\1s-", s)


# Title parser: matches the listing-scrape concatenation pattern
#   "[-NN%][NEW!][HOT]<name>[From ]$<price1>[$<price2>][(<reviews>)]"
TITLE_RE = re.compile(
    r"^"
    r"(?:-(?P<discount>\d+)%)?"
    r"(?P<flag_new>NEW!)?"
    r"(?P<flag_hot>HOT)?"
    r"(?P<name>.*?)"
    r"(?P<from_>From )?"
    r"\$(?P<price1>[\d,]+\.?\d*)"
    r"(?:\$(?P<price2>[\d,]+\.?\d*))?"
    r"(?:\((?P<reviews>\d+)\))?"
    r"$"
)


def parse_title(t: str) -> dict:
    m = TITLE_RE.match(t)
    if not m:
        return {"_parse_ok": False, "_raw": t}
    g = m.groupdict()
    name = (g["name"] or "").strip()
    name_clean = re.sub(r"\s*\|\s*labebe®?\s*$", "", name).strip()
    discount = int(g["discount"]) if g["discount"] else None
    price1 = float(g["price1"].replace(",", "")) if g["price1"] else None
    price2 = float(g["price2"].replace(",", "")) if g["price2"] else None
    reviews = int(g["reviews"]) if g["reviews"] else None
    implied_discount = None
    if price1 and price2 and price2 > 0:
        implied_discount = round((1 - price1 / price2) * 100)
    return {
        "_parse_ok": True,
        "name_clean": name_clean,
        "name_raw_segment": name,
        "flag_new": bool(g["flag_new"]),
        "flag_hot": bool(g["flag_hot"]),
        "from_prefix": bool(g["from_"]),
        "discount_pct_listed": discount,
        "current_price_usd": price1,
        "original_price_usd": price2,
        "discount_pct_implied": implied_discount,
        "reviews_count_listed": reviews,
    }


def load_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> None:
    log_lines: list[str] = []

    def log(msg: str) -> None:
        log_lines.append(msg)
        print(msg)

    log(f"REPO_ROOT={REPO_ROOT}")
    log(f"DATA_DIR={DATA_DIR}")
    log(f"OUT_DIR={OUT_DIR}")

    # --- Source hashes / sizes / mtimes --------------------------------------
    src_meta = {}
    for label, p in [
        ("labebe_products.csv", CSV_A),
        ("labebe_products_with_images.csv", CSV_B),
        ("all_product_images.json", JSON_GALLERIES),
    ]:
        st = p.stat()
        src_meta[label] = {
            "path": str(p.relative_to(REPO_ROOT)),
            "size_bytes": st.st_size,
            "mtime_unix": int(st.st_mtime),
            "sha256": sha256(p),
        }
    img_files = sorted(os.listdir(IMG_DIR))
    src_meta["images_dir"] = {
        "path": str(IMG_DIR.relative_to(REPO_ROOT)),
        "file_count": len(img_files),
    }
    with open(EVIDENCE_DIR / "source_hashes.json", "w") as f:
        json.dump(src_meta, f, indent=2)
    log(f"source hashes written -> {EVIDENCE_DIR / 'source_hashes.json'}")

    # --- Load sources --------------------------------------------------------
    rows_a = load_csv(CSV_A)
    rows_b = load_csv(CSV_B)
    with open(JSON_GALLERIES) as f:
        galleries: dict[str, dict] = json.load(f)
    log(f"CSV A rows={len(rows_a)} CSV B rows={len(rows_b)} JSON keys={len(galleries)}")

    # Build image-stem index from disk
    stem_to_files: dict[str, list[str]] = defaultdict(list)
    for fn in img_files:
        base = os.path.splitext(fn)[0]
        stem = re.sub(r"_\d+$", "", base)
        stem_to_files[stem].append(fn)

    # Index slugs from each side
    csv_slugs = {r["slug"] for r in rows_a}
    json_slugs = set(galleries.keys())
    img_stems = set(stem_to_files.keys())

    # --- Slug-image join report ---------------------------------------------
    join_rows = []
    all_keys = sorted(csv_slugs | json_slugs | img_stems)
    for k in all_keys:
        in_csv = k in csv_slugs
        in_json = k in json_slugs
        in_img = k in img_stems
        # If not in CSV, see if a normalized match exists
        normalized_csv_match = ""
        normalized_json_match = ""
        if not in_csv:
            for s in csv_slugs:
                if normalize_slug(s) == k or s == normalize_slug(k):
                    normalized_csv_match = s
                    break
        if not in_json:
            for s in json_slugs:
                if normalize_slug(s) == k or s == normalize_slug(k):
                    normalized_json_match = s
                    break
        files_on_disk = stem_to_files.get(k, [])
        gallery_count = len(galleries.get(k, {}).get("images", [])) if in_json else 0
        join_rows.append(
            {
                "slug": k,
                "in_csv_a": "Y" if in_csv else "",
                "in_json": "Y" if in_json else "",
                "in_image_dir": "Y" if in_img else "",
                "files_on_disk": len(files_on_disk),
                "gallery_url_count_in_json": gallery_count,
                "normalized_csv_match": normalized_csv_match,
                "normalized_json_match": normalized_json_match,
                "join_status": classify_join(in_csv, in_json, in_img, normalized_csv_match, normalized_json_match),
            }
        )
    write_csv(
        OUT_DIR / "slug_image_join_report_draft.csv",
        join_rows,
        [
            "slug",
            "in_csv_a",
            "in_json",
            "in_image_dir",
            "files_on_disk",
            "gallery_url_count_in_json",
            "normalized_csv_match",
            "normalized_json_match",
            "join_status",
        ],
    )
    log(f"slug_image_join_report_draft.csv rows={len(join_rows)}")

    # --- Dirty title parse report -------------------------------------------
    parse_rows = []
    for r in rows_a:
        t = r["title"]
        p = parse_title(t)
        # Build per-row anomaly notes
        anomalies = []
        if not p.get("_parse_ok"):
            anomalies.append("regex_unmatched")
        else:
            # CSV column vs title-derived: discount
            csv_disc = r["discount"]
            parsed_disc = p["discount_pct_listed"]
            if parsed_disc and (not csv_disc or csv_disc != f"{parsed_disc}%"):
                anomalies.append(f"csv_discount_col_mismatch:csv='{csv_disc}' parsed='{parsed_disc}%'")
            if (not parsed_disc) and csv_disc:
                anomalies.append(f"csv_discount_col_present_but_title_has_none:'{csv_disc}'")
            # CSV column vs title-derived: original price
            csv_orig = r["original_price"]
            parsed_orig = p["original_price_usd"]
            if parsed_orig and not csv_orig:
                anomalies.append("csv_original_price_col_empty_but_title_has_msrp")
            if (not parsed_orig) and csv_orig:
                # CSV stored a value even though title had only a single price
                csv_curr = r["current_price"]
                if csv_curr == csv_orig:
                    anomalies.append(f"csv_orig=current_no_real_msrp:'{csv_orig}'")
                else:
                    anomalies.append(f"csv_original_price_col_present_but_title_has_only_one_price:'{csv_orig}'")
            # CSV column vs title-derived: reviews
            csv_rev = r["reviews_count"]
            parsed_rev = p["reviews_count_listed"]
            if parsed_rev is not None and (not csv_rev or csv_rev != str(parsed_rev)):
                anomalies.append(f"csv_reviews_col_mismatch:csv='{csv_rev}' parsed='{parsed_rev}'")
            if parsed_rev is None and csv_rev:
                anomalies.append(f"csv_reviews_present_but_title_none:'{csv_rev}'")
            # Title flags
            if p["flag_new"]:
                anomalies.append("title_starts_with_NEW!")
            if p["flag_hot"]:
                anomalies.append("title_contains_HOT")
            if p["from_prefix"]:
                anomalies.append("title_uses_From_prefix_likely_variant_min_price")
            # Discount math sanity
            if p["discount_pct_listed"] is not None and p["discount_pct_implied"] is not None:
                delta = abs(p["discount_pct_listed"] - p["discount_pct_implied"])
                if delta > 2:
                    anomalies.append(
                        f"discount_math_mismatch_listed={p['discount_pct_listed']}%_implied={p['discount_pct_implied']}%"
                    )
        parse_rows.append(
            {
                "slug": r["slug"],
                "raw_title": t,
                "parse_ok": "Y" if p.get("_parse_ok") else "N",
                "name_clean": p.get("name_clean", ""),
                "flag_new": "Y" if p.get("flag_new") else "",
                "flag_hot": "Y" if p.get("flag_hot") else "",
                "from_prefix": "Y" if p.get("from_prefix") else "",
                "current_price_usd": p.get("current_price_usd") or "",
                "original_price_usd": p.get("original_price_usd") or "",
                "discount_pct_listed": p.get("discount_pct_listed") or "",
                "discount_pct_implied": p.get("discount_pct_implied") or "",
                "reviews_count_listed": "" if p.get("reviews_count_listed") is None else p.get("reviews_count_listed"),
                "csv_current_price_col": r["current_price"],
                "csv_original_price_col": r["original_price"],
                "csv_discount_col": r["discount"],
                "csv_reviews_col": r["reviews_count"],
                "anomalies": "; ".join(anomalies),
            }
        )
    write_csv(
        OUT_DIR / "dirty_title_parse_report_draft.csv",
        parse_rows,
        [
            "slug",
            "raw_title",
            "parse_ok",
            "name_clean",
            "flag_new",
            "flag_hot",
            "from_prefix",
            "current_price_usd",
            "original_price_usd",
            "discount_pct_listed",
            "discount_pct_implied",
            "reviews_count_listed",
            "csv_current_price_col",
            "csv_original_price_col",
            "csv_discount_col",
            "csv_reviews_col",
            "anomalies",
        ],
    )
    log(f"dirty_title_parse_report_draft.csv rows={len(parse_rows)}")

    # --- Product master v0 ---------------------------------------------------
    master_rows = []
    for r in rows_a:
        slug = r["slug"]
        p = parse_title(r["title"])
        # join to JSON gallery (with normalization fallback)
        json_key = slug if slug in galleries else normalize_slug(slug) if normalize_slug(slug) in galleries else ""
        slug_match_status = (
            "identical" if (json_key and json_key == slug)
            else ("normalized_match" if json_key else "unmatched")
        )
        gallery = galleries.get(json_key, {}) if json_key else {}
        gallery_urls = gallery.get("images", [])
        # local hero image
        local_hero = r.get("local_image_path", "")
        local_hero_exists = bool(local_hero) and Path(local_hero).is_file()
        # gallery files on disk: union of disk stems for csv slug and json key
        files_csv_side = stem_to_files.get(slug, [])
        files_json_side = stem_to_files.get(json_key, []) if json_key and json_key != slug else []
        gallery_files_on_disk = len(files_csv_side) + len(files_json_side)

        unknowns = []
        if not p.get("original_price_usd"):
            unknowns.append("original_price")
        if p.get("reviews_count_listed") is None:
            unknowns.append("reviews_count_listing")
        # All product attributes below are NEVER in the source -> always unknown:
        unknowns.extend([
            "pdp_text",
            "dimensions",
            "weight",
            "materials",
            "age_range",
            "warnings",
            "certifications",
            "assembly_minutes",
            "shipping_dimensions",
            "variants",
            "inventory_status",
            "review_rating",
            "review_text",
            "asin",
        ])

        master_rows.append(
            {
                "slug_csv": slug,
                "slug_json": json_key,
                "slug_match_status": slug_match_status,
                "name_clean": p.get("name_clean", ""),
                "title_raw": r["title"],
                "current_price_usd": p.get("current_price_usd") or "",
                "original_price_usd": p.get("original_price_usd") or "",
                "discount_pct_listed": p.get("discount_pct_listed") or "",
                "discount_pct_implied": p.get("discount_pct_implied") or "",
                "flag_new_listing": "Y" if p.get("flag_new") else "",
                "flag_hot_listing": "Y" if p.get("flag_hot") else "",
                "from_prefix_listing": "Y" if p.get("from_prefix") else "",
                "reviews_count_listing": "" if p.get("reviews_count_listed") is None else p.get("reviews_count_listed"),
                "collection_listing": r["collection"],
                "product_url": r["product_url"],
                "local_hero_image_path": local_hero,
                "local_hero_image_exists": "Y" if local_hero_exists else "N",
                "pdp_gallery_url_count": len(gallery_urls),
                "gallery_files_on_disk": gallery_files_on_disk,
                "scrape_date_local": "2026-04-24",
                "unknown_fields": "; ".join(unknowns),
            }
        )
    write_csv(
        OUT_DIR / "product_master_v0_draft.csv",
        master_rows,
        [
            "slug_csv",
            "slug_json",
            "slug_match_status",
            "name_clean",
            "title_raw",
            "current_price_usd",
            "original_price_usd",
            "discount_pct_listed",
            "discount_pct_implied",
            "flag_new_listing",
            "flag_hot_listing",
            "from_prefix_listing",
            "reviews_count_listing",
            "collection_listing",
            "product_url",
            "local_hero_image_path",
            "local_hero_image_exists",
            "pdp_gallery_url_count",
            "gallery_files_on_disk",
            "scrape_date_local",
            "unknown_fields",
        ],
    )
    log(f"product_master_v0_draft.csv rows={len(master_rows)}")

    # --- Save log -----------------------------------------------------------
    with open(EVIDENCE_DIR / "build_drafts_log.txt", "w") as f:
        f.write("\n".join(log_lines) + "\n")


def classify_join(in_csv, in_json, in_img, n_csv, n_json):
    if in_csv and in_json and in_img:
        return "perfect"
    if in_csv and (not in_json) and in_img and n_json:
        return "csv_to_json_normalize_required"
    if (not in_csv) and in_json and in_img and n_csv:
        return "json_to_csv_normalize_required"
    if in_csv and (not in_json) and in_img:
        return "json_missing"
    if (not in_csv) and in_json and in_img:
        return "csv_missing"
    if in_csv and in_json and (not in_img):
        return "image_dir_missing"
    return "other_partial"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
