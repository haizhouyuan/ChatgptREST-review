# Handoff — WP-A Product Data QA

Date: 2026-04-27
Worker: WP-A Product Data QA (Claude Code, delegated)
Write scope: `planning/20260427_labebe_14day_execution/work_products/product_data_qa/`
Sprint issue: `LAB-003 Product Master v0 and Data QA` (still open — this draft
is one input, not the closeout).

## 1. What the controller can trust

These statements are evidenced by the artifacts in this directory and the
hashes in `evidence/source_hashes.json`.

1. **46 products are uniquely identifiable** across CSV A, the PDP gallery
   JSON, and the local image directory, after applying one slug
   normalization rule (`re.sub(r'(\w)-s-', r'\1s-', slug)`).
2. `data/labebe/labebe_products.csv` is the canonical 46-row product list
   on disk. Every row’s `local_image_path` resolves to a file that exists.
3. `data/labebe/all_product_images.json` is the authoritative gallery URL
   index. 46 keys × 459 image URLs. Disk has 460 image files (the +1 is the
   duplicated slug variant for the desk product).
4. All 46 raw titles parse with the documented regex. The parsed fields are
   in `product_master_v0_draft.csv` and the per-row anomalies are in
   `dirty_title_parse_report_draft.csv`.
5. The slug join risk is a single product (the desk + cork-board listing).
   Direction of mismatch and a normalization rule are documented in
   `slug_image_join_report_draft.csv` and §3 of `current_data_qa_draft.md`.
6. CSV B (`labebe_products_with_images.csv`) is a **stale earlier
   checkpoint** despite its filename — its `local_image_path` column is
   empty. Documented in §1.6 of `do_not_use_fields_draft.md`.
7. Listing badges (`NEW!`, `HOT`, `From `) are merchandising tags from a
   single 2026-04-24 capture. They are **not** demand signals, **not**
   release dates, and **not** sales-rank evidence.

## 2. What the controller should inspect before integrating

These items need a human / main-controller decision the worker should not
make:

1. **Slug-as-key vs URL-as-key.** This worker recommends `product_url` as
   the primary key for any LAB-004+ enrichment table, with `slug` kept as
   a display key only. Confirm before LAB-004 stratification.
2. **Treatment of the 3 desk SKUs**
   (`kids-desk-chair-set-with-cork-board-hutch`,
   `children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art`,
   `kids-wooden-desk---chair-set-with-corkboard--hutch-storage---organizer`).
   They share the $179.99 anchor price, similar discount, and overlapping
   names. They may be one physical product re-listed for SEO, or genuinely
   distinct. Cannot be resolved from listing data alone. Strong candidate
   for the LAB-004 "near-duplicate furniture SKU" sample slot, especially
   because the middle row is also the slug-mismatch product.
3. **Variant-family treatment** for Learning Tower (4 colors/forms) and
   Magnetic Easel (3 colors). The source has no parent-product field. Pro
   feedback (06_pro_feedback_synthesis section 2.3) lists "variant_theme"
   as a missing schema field; this worker did not invent one.
4. **CSV column trust.** This worker recommends ignoring CSV A’s
   `discount`, `original_price`, `reviews_count`, and `image_url` columns
   in favor of the re-derived columns in `product_master_v0_draft.csv`.
   See `do_not_use_fields_draft.md` §1.

## 3. What is explicitly NOT yet usable

These items are surfaced by this work but require an upstream task to
close. Marking sprint-level done before they are addressed would violate
the Evidence Integrity Gate.

| Gap | Owner / Issue | Notes |
| --- | --- | --- |
| PDP body (dimensions, age, materials, certifications, warnings, assembly) | LAB-004 dossiers, then LAB-007 | Source has none of these. |
| Variant relationships | LAB-004 + LAB-007 | Listing data does not expose parent product. |
| Image role classification | LAB-006 / WP-C | 460 files unlabelled. |
| Multi-collection membership | LAB-004 PDP enrichment | Scraper kept first-collection per slug only. |
| Live pricing / coupon / stock | LAB-004 / LAB-007 | Single capture from 2026-04-24. |
| ASIN identity | WP-B / LAB-005 | Out of scope here. |
| Onsite review **rating** and **text** | LAB-004 PDP enrichment | Source captured **count** only on 32 / 46 cards. |

## 4. What the controller can pick up immediately

- Use `product_master_v0_draft.csv` directly as the LAB-003 evidence-side
  input to the Evidence Integrity Gate. The `unknown_fields` column tells
  the gate exactly what is missing per row.
- Use `dirty_title_parse_report_draft.csv` for the LAB-003 acceptance
  criterion "parse dirty titles".
- Use `slug_image_join_report_draft.csv` for the LAB-003 acceptance
  criterion "check slug/image/PDP joins".
- Use `do_not_use_fields_draft.md` for the LAB-003 acceptance criterion
  "list fields that cannot be used for copy or claim", and feed it
  forward into the LAB-007 Claim Gate input.
- Use `product_data_inventory.md` §2 for the LAB-001 / LAB-002
  source-method audit (it documents the schema each source actually has).

The closeout artifact `product_master_v0.csv` for LAB-003 should be
authored by the main controller by either renaming this draft or by
adding fields the controller decides are in scope. This worker did not
add any field beyond what is grounded in the source.

## 5. Forbidden actions this worker did NOT take

Per the WP-A prompt:

- Did not call Pro / Gemini / ChatGPTREST.
- Did not run a fresh Labebe / labebeclub.com / Amazon crawl.
- Did not modify `scrape_labebe.py` or any other source script (it was
  read-only for analysis; not reformatted, not "cleaned", not augmented).
- Did not modify `data/labebe/` files.
- Did not edit any planning document outside the assigned write scope.
- Did not silently repair any data — every cleanup is reported in the
  three CSV reports and in `current_data_qa_draft.md`.
- Did not mark `LAB-003` done. Closeout is a controller decision.

## 6. Recommended next actions for the main controller

1. Review the 1-row slug normalization risk and decide whether to push the
   normalization rule upstream into a future re-scrape, or to keep it as
   a derived QA layer in `product_master_v0.csv`.
2. Confirm the LAB-004 sample composition. This worker’s suggestion is
   that the 6–8 stratified SKUs include:
   - Pink Unicorn Plush Rocker — most-reviewed plush rocker (18 reviews
     listed; required by LAB-004 acceptance).
   - One Play Kitchen — `cream-wooden-play-kitchen-set-with-storage` (-32 %,
     9 reviews, gallery 12 images) is the most evidence-dense kitchen SKU.
   - One Learning Tower variant — pick one of the 4 (no listed reviews on
     any) plus check variant family.
   - One near-duplicate desk SKU — `children-s-writing-desk-…` (12 reviews
     listed; also the slug-mismatch row, so it tests both stratification
     goals at once).
   - One low/no-review-but-important SKU — `wooden-rainbow-rocking-chair`
     (no listed review count; gallery 8 images; rocker family).
   - The ASIN `B087P9SXZQ` cross-check — owner: WP-B.
   - One expected-no-match SKU — owner: WP-B.
   - One slug/data mismatch — covered above by the desk SKU.
3. Pass `do_not_use_fields_draft.md` forward into the LAB-007 Claim Gate
   prep before any claim copy is drafted.
4. Decide whether CSV B should be deleted, archived, or left in place with
   a `_stale_` rename. This worker did not touch it.

## 7. Files in this handoff

| File | Purpose |
| --- | --- |
| `product_data_inventory.md` | What sources exist, sizes, hashes, schemas, limitations. |
| `current_data_qa_draft.md` | QA findings, reconciliation, slug join risk, near-duplicate flags. |
| `product_master_v0_draft.csv` | 46 rows × 21 columns. Slug-joinable, parsed-from-title, with explicit unknowns. |
| `slug_image_join_report_draft.csv` | 47 rows. Per-slug presence in CSV / JSON / disk plus normalization match. |
| `dirty_title_parse_report_draft.csv` | 46 rows. Title-parse vs CSV-column comparison with anomaly notes. |
| `do_not_use_fields_draft.md` | Field-by-field block list for the Claim Gate. |
| `handoff.md` | This file. |
| `evidence_manifest.json` | Maps each output to its source files / commands / hashes. |
| `build_drafts.py` | Reproducible builder for the three CSV reports. |
| `evidence/source_hashes.json` | Source-side sha256 + size + mtime (captured at run time). |
| `evidence/build_drafts_log.txt` | Stdout log from the most recent build. |

## 8. Reproducing this handoff

```bash
cd /vol1/1000/projects/toyresearch
python3 planning/20260427_labebe_14day_execution/work_products/product_data_qa/build_drafts.py
```

Idempotent. Source-side hashes will be re-captured into
`evidence/source_hashes.json`; if those change, the controller should
investigate why before merging downstream.
