# Do-Not-Use Fields — Draft

Date: 2026-04-27
Worker: WP-A Product Data QA (Claude Code, delegated)
Purpose: enumerate fields and signals from the local Labebe scrape that
**must not be reused as factual claims, marketing copy, PDP claims, or
design-decision evidence** without first being re-derived from a stronger
source. Feeds the Claim Gate for `LAB-003 / LAB-007 / LAB-009`.

This is a draft. Main controller integrates into `do_not_use_fields.md`.

## 0. Summary of categories

1. CSV columns that exist but are stale or unreliable.
2. Fields the source data does not contain at all (no honest fallback).
3. Listing badges that look like demand signals but are not.
4. Slug strings that look like product identity but are not unique.
5. Image filenames and folders that look like role labels but are not.

Each row below states the field, what it looks like in the data, why it is
unsafe, and what to do instead.

## 1. CSV columns that exist but are stale or unreliable

### 1.1 `image_url` column in both CSVs

- State: empty in 46 / 46 rows of both `labebe_products.csv` and
  `labebe_products_with_images.csv`.
- Risk: a downstream worker may assume "no listing image".
- Reality: scrape never wrote it; hero images **do** exist (`local_image_path`
  in CSV A; full galleries in `all_product_images.json` and on disk).
- Do not use.
- Use instead: `local_image_path` from CSV A, or `images[]` from the JSON
  gallery index.

### 1.2 `original_price` column in CSV A

- State: filled in 14 / 46 rows; empty in 27 rows whose **titles** show an
  MSRP; equal to `current_price` in 1 row (`wooden-round-stools-2-per-pack`)
  whose title shows only one price.
- Risk: copy or banner that says "Was $X" using this column will be wrong
  for ~60 % of products and falsely inflate one row's MSRP.
- Do not use.
- Use instead: `original_price_usd` in `product_master_v0_draft.csv`,
  re-parsed from the title. Null means "no MSRP shown on listing on
  2026-04-24", not "the product has no MSRP".

### 1.3 `discount` column in CSV A

- State: filled in 8 / 46 rows; reflects only listings that displayed a
  banner like "-44 %".
- Risk: treating the empty rows as zero discount; treating the 8 displayed
  values as the only discounted SKUs.
- Do not use.
- Use instead: `discount_pct_listed` (banner) plus `discount_pct_implied`
  (computed when both prices exist) in `product_master_v0_draft.csv`.

### 1.4 `reviews_count` column in CSV A

- State: filled in 32 / 46 rows; empty in 14 rows because the listing card
  did not render `(N)` for those products on 2026-04-24.
- Risk: a website module that shows "X reviews" or sorts by review count
  will silently treat the 14 empty rows as "0 reviews" and bury them.
- Do not use as a count of reviews.
- Use instead: `reviews_count_listing` in `product_master_v0_draft.csv`,
  with the explicit caveat **listing-card count, not site-wide review
  count, on 2026-04-24, missing means "not rendered" not "zero".**
- Critical: this is a count, not a rating. There is **no rating data** in
  the source.

### 1.5 `current_price` for the one `From ` row

- State: `white-swan-plush-rocker` lists `From $139.99$179.99(6)`. The CSV
  stores `$139.99` in `current_price`.
- Risk: a price shown as a single SKU price is misleading; it is the
  starting price for a multi-variant listing whose variant matrix is
  unknown from this scrape.
- Do not use as the single SKU price.
- Use instead: in `product_master_v0_draft.csv` the `from_prefix_listing`
  flag is `Y` for this row. Treat its `current_price_usd` as a "starting
  at" value until variants are enumerated from the PDP.

### 1.6 The whole of `labebe_products_with_images.csv` (CSV B)

- State: 46-row stale mirror of CSV A. Every column populated except
  `local_image_path`, which is empty for every row, and `image_url`, which
  is empty for every row.
- Risk: filename suggests it is the richer "with images" file; reality is
  the opposite.
- Do not use.
- Use instead: CSV A and `all_product_images.json` and the
  `data/labebe/images/` folder.

## 2. Fields the source data does not contain at all

For every field below, the local scrape has **no value**. The honest
status is "unknown until PDP / brand / Amazon enrichment". Any value
produced from a guess, a model, or a stock template is a fabrication.

| Field family | Specific fields | Why a guess is dangerous |
| --- | --- | --- |
| Product dimensions | assembled W×H×D, packaged W×H×D, weight | Furniture buyers reject brands that lie about fit. |
| Materials | wood species, paint type, finish, fabric | Allergy / safety implications. |
| Age guidance | min age, max age, weight capacity | Maps to safety regulation, not marketing. |
| Safety / certification | CPSIA, ASTM F963, EN-71, choke-hazard warnings | Legal claim; cannot be invented. |
| Compliance copy | Prop 65, country of origin, warranty terms | Legal claim. |
| Assembly | parts count, time, tools, instructions | Returns / refund driver if false. |
| Variants | parent product, sibling SKUs, color/size matrix | Causes wrong inventory and add-to-cart paths. |
| Inventory | in-stock, lead time, ship-by | Can change daily; not in a 2026-04-24 capture. |
| Reviews | star rating, review text, reviewer count beyond the card, dates | Listing card has only a count for 32 / 46. |
| Sales / demand | velocity, BSR, units sold, "best-seller" rank | Source has zero demand data. |
| Marketplace identity | ASIN, UPC, GTIN, SKU code | Belongs to WP-B; out of scope here. |
| Structured PDP body | bullets, A+ content, FAQ, Q&A | PDP page body was never scraped. |
| Pricing freshness | live price, coupons, bundles, sale dates | Single 2026-04-24 capture. |
| Multi-collection membership | category cross-listing | Scraper stops at first collection per slug. |
| Image roles | hero / lifestyle / dimension / packaging / assembly / child-use | Not labelled. |

If a downstream worker (LAB-004 dossiers, LAB-007 Commerce Decision Layer,
or LAB-009 Boss Gallery) wants any of these, the value must come from a
named upstream source with a date and access notes. Otherwise the field
must remain blank or labelled `unknown`.

## 3. Listing badges that look like demand signals but are not

### 3.1 `NEW!` prefix (12 / 46)

- What it is: the listing-template badge "NEW!" on the product card.
- What it is NOT: a launch date, a release year, a "new for 2026" claim,
  or a "newest collection" marker.
- Do not use in copy that asserts a release timeline.
- Acceptable internal use: "this card showed NEW! on 2026-04-24" as a
  merchandising-state artefact.

### 3.2 `HOT` prefix (8 / 46)

- What it is: the listing-template badge "HOT" on the product card.
- What it is NOT: a sales rank, a velocity claim, a category leader claim,
  a parent-favorite claim, or a popularity proxy.
- Do not use in copy that asserts demand or sales.
- Acceptable internal use: same as `NEW!`, captured as an internal
  merchandising flag only.

### 3.3 Onsite review **count** as Amazon demand or sales proxy

- Listed counts on the 32 / 46 cards are, at most, "this many people left
  a review on the brand site". Source registry forbids using this as
  Amazon demand (`forbidden_shortcuts.treat onsite review count as Amazon
  demand`).
- Do not use as a demand signal anywhere outside the brand site itself.

## 4. Slug strings that look like product identity but are not unique

- One product has two slug shapes:
  `children-s-…-art` (CSV / listing) and `childrens-…-art` (PDP / JSON).
- Both share the same `product_url` (the URL is the only unambiguous key).
- Do not use the slug as the join key. Use `product_url` and treat slug
  as a derived display string.
- The 4 Learning Tower variants and the 3 Magnetic Easel color variants
  share name prefixes that are very similar to each other but are
  separate listings. Slug-only equality will under-merge or over-merge
  depending on the rule.

## 5. Image filenames and folders that look like role labels but are not

- `data/labebe/images/<slug>.jpg` — convention is "first image fetched =
  hero". This is convention, not a label. The first image is sometimes a
  studio shot and sometimes a lifestyle shot.
- `data/labebe/images/<slug>_<n>.jpg` — order is the order the gallery
  rendered, not a role taxonomy. Do not assume `_2` is a lifestyle shot
  or `_8` is a dimension chart.
- Do not use filename position as a role label. Role classification is
  LAB-006 / WP-C work.

## 6. Quick-reference table

The single-page summary the controller can paste into the Claim Gate
output:

| Field / signal | Status | Allowed downstream use |
| --- | --- | --- |
| `slug` | non-unique (1 split) | display only; join via `product_url` |
| `title` (CSV A) | dirty but parseable | source for re-derived fields, never copy |
| `current_price` (CSV A) | OK except `From ` row | numeric only; flag `from_prefix_listing` |
| `original_price` (CSV A) | unreliable | re-derive from title; null if absent |
| `discount` (CSV A) | unreliable | re-derive; null if absent |
| `reviews_count` (CSV A) | partial | re-derive; null is "unknown", never zero |
| `image_url` (CSV A/B) | always empty | do not read |
| `local_image_path` (CSV A) | OK | hero file path; verified to exist |
| `local_image_path` (CSV B) | always empty | do not read |
| `collection` | OK but single-membership | do not infer multi-category |
| `NEW!` flag | merchandising-only | not a launch date |
| `HOT` flag | merchandising-only | not a demand or rank |
| Listing review count | partial, listing-card only | not a rating, not an Amazon demand |
| `From ` price | starting price | not a single SKU price |
| Dimensions / age / materials / cert | absent | block all claims until enriched |
| Reviews text / rating | absent | block all "parents say…" copy |
| ASIN / UPC / GTIN | absent | block until WP-B verifies |
| Image role | absent | block role-based picks until WP-C |

Anything in the bottom three rows that ends up in a Boss Gallery demo,
DTC PDP, or claim ledger before its source is named must be downgraded to
`blocked` per the Claim Gate.
