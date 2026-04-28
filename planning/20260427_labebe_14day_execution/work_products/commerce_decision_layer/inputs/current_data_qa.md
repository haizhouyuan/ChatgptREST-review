# Current Data QA — Draft

Date: 2026-04-27
Worker: WP-A Product Data QA (Claude Code, delegated)
Scope: only the local Labebe independent-site scrape outputs in
`data/labebe/`. No external crawl. No source-data overwrites.

This is a draft. Main controller integrates into `current_data_qa.md` for
LAB-003 (Evidence Integrity Gate input).

## 0. Top-line answer to the gate question

> Are the 46 known DTC products uniquely identifiable?

**Yes, after one normalization rule.**

- `data/labebe/labebe_products.csv` (CSV A) has 46 rows with 46 distinct
  `slug` values.
- `data/labebe/all_product_images.json` (JSON gallery index) has 46 keys.
- 45 / 46 slugs match identically across CSV A and JSON.
- 1 / 46 slug differs by listing vs PDP normalization
  (`children-s-…` vs `childrens-…`). Same product, two slug shapes.
- Apply the rule `re.sub(r'(\w)-s-', r'\1s-', slug)` on the listing slug
  before joining to the JSON or to the gallery image stems and the join
  closes with zero loss.

After that single rule the **46-product set is uniquely identified**. Every
other field (price, reviews, badges, etc.) is **secondary** and per-row
quality varies — see §4 and §5.

## 1. What was inspected (and how)

| Source | Approach |
| --- | --- |
| `labebe_products.csv` (CSV A) | parsed every row, regex-matched titles, joined to JSON and disk. |
| `labebe_products_with_images.csv` (CSV B) | parsed; compared slug set and column completeness vs CSV A. |
| `all_product_images.json` | parsed; per-key gallery counts; intersection vs CSV slugs. |
| `data/labebe/images/` | listed files, computed slug stems by stripping `_<n>` suffixes; counted per stem. |
| `scrape_labebe.py` | read end-to-end to understand title-shape origin and dirty-CSV root cause. |
| `docs/labebe-scrape-report-2026-04-24.md` | cross-checked stated counts (46 / 460 / collection split). |

Outputs of this inspection are the three CSV reports and this document.

The only commands run in the working directory:

```bash
ls -la data/labebe/
ls -la data/labebe/images/                              # counts only
wc -l data/labebe/labebe_products.csv \
       data/labebe/labebe_products_with_images.csv
python3 planning/20260427_labebe_14day_execution/work_products/product_data_qa/build_drafts.py
```

The build script is committed alongside the outputs (`build_drafts.py`).

## 2. Reconciliation

| Metric | CSV A | CSV B | JSON | Disk |
| --- | ---: | ---: | ---: | ---: |
| Distinct slugs / keys / stems | 46 | 46 | 46 | 47 |
| Slug set ≡ CSV A’s slug set | – | ✓ | 45 ✓ + 1 normalized | 45 ✓ + 1 dup variant |
| Files / URLs total | – | – | 459 | 460 |
| `image_url` column populated | 0 / 46 | 0 / 46 | n/a | n/a |
| `local_image_path` column populated | 46 / 46 | 0 / 46 | n/a | n/a |
| Hero file exists on disk | 46 / 46 | n/a | n/a | – |

Reading: CSV A is the canonical product list. CSV B is a stale earlier
checkpoint despite its `_with_images` filename and should be ignored. The
JSON is the authoritative gallery URL source. Local image directory is
complete and joinable to CSV A’s `local_image_path` 1:1.

## 3. Slug join risk (the 1 / 46 mismatch)

| Side | Slug |
| --- | --- |
| CSV A `slug` | `children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art` |
| CSV A `product_url` trailing segment | identical to CSV slug |
| JSON gallery key | `childrens-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art` |
| Disk filename stems | **both variants exist**: 1 file under the CSV form (the hero only) and 13 files under the JSON form (full gallery) |

Why this happened (analysis only, scraper not modified):

`scrape_labebe.py` derives slug from the listing-card href via
`href.replace('/product/', '').replace(/\/$/, '')`. The listing-side URL
encodes the apostrophe in `Children's` as `-s-`. The PDP-side URL on the
same site encodes it as `s-`. Two valid slugs for one product.

Effect on data:

- 13 of the 14 PDP gallery images for this product live under the **JSON
  slug** filename on disk, not under the CSV slug.
- The CSV row’s `local_image_path` points at the **hero only**, which is
  the file actually written under the CSV slug.
- Without the normalization rule, naively counting `gallery_files_on_disk`
  by CSV slug would give 1, falsely implying a near-empty gallery.

Documented in:

- `slug_image_join_report_draft.csv` rows for both slug shapes (status
  `csv_to_json_normalize_required` / `json_to_csv_normalize_required`).
- `product_master_v0_draft.csv` columns `slug_csv`, `slug_json`,
  `slug_match_status` (`identical` for 45, `normalized_match` for 1).

Rule of normalization: `re.sub(r'(\w)-s-', r'\1s-', slug)`. This is not
generally safe across all kid-product slugs, but on this 46-product set it
is the only collision and it produces the right pair.

**Recommendation for main controller:** when extending to PDP enrichment
in LAB-004 / LAB-007, query products by `product_url` (which is unambiguous)
and treat `slug` as a derived display key.

## 4. Title parse — all 46 rows parse, but CSV column values are noisy

Every one of the 46 dirty titles parses cleanly with the regex documented
in `dirty_title_parse_report_draft.csv`. The pattern is

```
[-NN%][NEW!][HOT]<name>[ | labebe®][From ]$<price1>[$<price2>][(<reviews>)]
```

The CSV title column carries this concatenated string verbatim. The
**parsed** values disagree with the **stored CSV columns** in many places:

| CSV column anomaly | Count / 46 | What it means |
| --- | ---: | --- |
| `original_price` column empty though title contains MSRP | 27 | The scrape did not split the second `$NN.NN` from the title into the column for these. The MSRP IS recoverable from the title. |
| `discount` column empty | 38 | Only 8 / 46 listings displayed an `-NN%` banner. The other 30 have an implicit discount when both prices exist (mean implied ≈ 31 %). Empty `discount` does NOT mean zero discount. |
| `reviews_count` column empty | 14 | Listing card did not show `(N)`. Empty does NOT mean zero reviews — it means the card did not render the review count. |
| `original_price` column equals `current_price` | 1 | `wooden-round-stools-2-per-pack`: CSV stores `$35.99` in both, title shows only one `$35.99`. The CSV value is a back-fill artifact, not a genuine MSRP. |
| `image_url` column empty for every row | 46 | Listing-step never populated this. Use `local_image_path` (CSV A) and `all_product_images.json` instead. |

Per-row breakdown is in `dirty_title_parse_report_draft.csv` (column
`anomalies`).

**Recommendation:** never read CSV A’s `discount`, `original_price`,
`reviews_count`, or `image_url` columns directly for any downstream
decision. Use `product_master_v0_draft.csv`, where every numeric field has
been re-derived from the title and labelled with its provenance, plus an
`unknown_fields` column listing what is genuinely missing.

## 5. Listing badges and what they mean (and don’t mean)

| Badge | Count / 46 | What is supported | What is NOT supported |
| --- | ---: | --- | --- |
| `NEW!` prefix | 12 | This product was tagged "New" on the listing page on 2026-04-24. | Not a launch date, not a release year, not "new for 2026". |
| `HOT` prefix | 8 | This product had a "Hot" merchandising tag on 2026-04-24. | Not a sales rank, not a velocity claim, not a category leader claim. |
| `From ` price prefix | 1 (`white-swan-plush-rocker`) | This listing has multiple variants and `current_price` is the **starting** price, not a single SKU price. | Cannot use the `current_price` as the only listed price for that SKU; the variant matrix is unknown from this scrape. |

These badges are merchandising signals from a single capture date. Do not
elevate them into product positioning, demand evidence, or PDP copy.

## 6. Discount math sanity

For all 8 rows that display both an `-NN%` banner and a `$current$original`
pair, the listed discount and the implied discount agree to within 2
percentage points. No discount-math contradictions detected.

For the 30 rows with both prices but no banner, implied discount ranges
9 – 41 %. Worth flagging in PDP strategy work but not a data integrity
issue.

## 7. Per-product gallery completeness

Per-row `pdp_gallery_url_count` (from JSON) and `gallery_files_on_disk`
(counted under the CSV slug stem ∪ the JSON slug stem) match exactly for
every product after slug normalization. No partial download, no extra
files. The 2026-04-24 scrape is internally consistent on the gallery side.

Range of gallery sizes: 6 – 28 images (mean 10). Heavy galleries:

- `outdoor-garden-potting-bench-table` — 28
- `kids-art-table-chair-set-with-easel-3-in-1` — 24
- `midnight-serenity-wooden-play-kitchen-set` — 24
- `kids-toy-storage-organizer-bookshelf-with-bins` — 17
- `highlander-cattle-plush-rocker` — 16

Lean galleries (6 each):

- `learning-tower-montessori-kitchen-tower-unicorn-design`
- `wooden-round-stools-2-per-pack`
- `wooden-square-stools-2-per-pack`
- `wooden-toy-storage-organizer-with-shelves-bins`

These do not classify gallery images by role (hero / lifestyle / dimension
chart / packaging / assembly). Role classification is LAB-006 / LAB-007
work. Listed here so the next worker knows the raw counts.

## 8. Near-duplicate / variant-family flags (for LAB-004 stratification)

Surfaced for the controller because `LAB-004` requires a "near-duplicate
furniture SKU" sample. Detected by slug similarity + name-prefix bucketing.
This is a flag, not a confirmed merger.

### 8.1 Three desk + chair + cork board SKUs in `furniture`

All three priced $179.99 with similar MSRPs and discounts:

| Slug | Name | Reviews | Discount |
| --- | --- | ---: | ---: |
| `kids-desk-chair-set-with-cork-board-hutch` | Kids' Desk & Chair Set with Cork Board & Hutch | 5 | -13 % |
| `children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art` | Children's Writing Desk and Chair Set with Hutch & Cork Board for Study & Art | 12 | -14 % |
| `kids-wooden-desk---chair-set-with-corkboard--hutch-storage---organizer` | Kids Wooden Desk & Chair Set with Corkboard, Hutch Storage & Organizer | 11 | -14 % |

Possibilities (not resolved here): same physical product re-listed as 3
SEO-targeted variants; near-duplicates with minor real differences
(material, hutch storage); or distinct products that converged on the same
price. Hard to tell from listing-only data. Strongly recommended as the
LAB-004 "near-duplicate furniture SKU" sample, especially because the
middle row is **also** the slug-normalize product.

### 8.2 Learning Tower family

Four SKUs: White, Gray, Unicorn Design, Foldable Log Color. None has a
listed `(N)` review count, so onsite review evidence is unavailable for
the whole family.

### 8.3 Magnetic Easel Deluxe Art Supplies

Three color SKUs (Pink / Purple / Colorful) at $93.99 / $95.99 / $93.99
MSRP $119.99. None has a review count on the listing card.

### 8.4 Storage / Organizer / Shelf

Multiple SKUs whose names overlap heavily (`wooden-toy-storage…`,
`kids-toy-storage…`, `rubber-wood-montessori-shelf`,
`natural-wood-montessori-shelf-with-storage-boxes`, etc.). Worth
cross-checking against PDP imagery before committing to a "Playroom
Reset" or "Home-fit Furniture" hero choice.

## 9. Limitations of this dataset

These are properties of the source scrape, not of this QA worker:

1. The scrape is **listing-only**. PDP body, structured data, dimensions,
   age guidance, materials, certifications, warnings, assembly text, and
   onsite review **text** are absent for all 46 products.
2. The listing card review count is sometimes missing. **Empty review
   counts are not zero reviews.** They reflect what the card rendered on
   2026-04-24.
3. Pricing is a single capture from 2026-04-24. Live prices, coupons,
   bundle discounts, and stock state are unknown.
4. Variant relationships are not modelled. The 4 Learning Tower SKUs and
   the 3 Magnetic Easel SKUs likely share parent products / variant
   themes but the source has no parent_product field.
5. A product appears in **at most one** collection in this dataset
   because the scraper de-duplicates by slug and stops at the first
   collection. Multi-collection membership cannot be derived.
6. Image gallery roles (hero / lifestyle / dimension chart / packaging /
   child-use scene / assembly diagram) are not labelled. The role
   classification is a separate task (LAB-006 / WP-C).
7. The CSV column values in CSV A are partially populated and partially
   stale; treat the title string as the canonical record and re-derive
   structured fields from it.
8. CSV B is a stale duplicate. Its filename
   `labebe_products_with_images.csv` is misleading — its
   `local_image_path` column is empty.

## 10. What this draft is good enough to feed

- **Yes:** Evidence Integrity Gate input for `LAB-003` (46 unique
  products, joins explicit, dirty fields enumerated).
- **Yes:** SKU stratification input for `LAB-004` (sample selection
  must include the `children-s-`/`childrens-` slug-mismatch product
  AND at least one near-duplicate desk SKU).
- **Yes:** Asset readiness baseline for `LAB-006` / `LAB-007`
  (hero per slug, gallery counts per slug; role classification still
  needed downstream).
- **Yes:** Inputs to `do_not_use_fields_draft.md` for the Claim Gate.

## 11. What this draft is NOT good enough for

- **No:** Final `product_master_v1.csv` for Phase 3. Missing PDP
  enrichment.
- **No:** Hero candidate selection. Missing demand signals (Amazon /
  marketplace) and asset role classification.
- **No:** Any safety / material / age / certification claim. Source
  data does not cover these.
- **No:** Any "demand", "best-seller", or "trending" copy. Listing
  badges (`NEW!`, `HOT`) are merchandising tags, not demand signals.
- **No:** Any per-SKU review-rating reference. Only review **counts**
  are observable, only on 32 / 46 listings, and rating is not
  captured.
