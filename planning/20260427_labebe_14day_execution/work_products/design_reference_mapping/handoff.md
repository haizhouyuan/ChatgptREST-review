# WP-D Handoff: Design Reference Mapping

> Worker: WP-D Design Reference Mapping
> Date: 2026-04-27
> Scope: `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/design_reference_mapping/`

---

## What Was Done

WP-D converted the existing Labebe design reference research into business-problem patterns. The work produced 5 artifacts:

1. **reference_pattern_mapping_draft.md** — Maps 15 reference patterns (8 same-category brands, 4 world-class web references, 3 AI/interactive commerce references, 4 page-level structural patterns) to Labebe business problems, shopper missions, category roles, PDP modules, conversion mechanisms, asset needs, and rejection conditions.

2. **commerce_pattern_library_draft.md** — Organizes 24 patterns by commerce touchpoint (homepage/nav, collection, PDP, gift flow, room flow, cart, AI Growth Studio). Each pattern is tagged P0/P1/P2 and includes business problem, shopper mission, conversion mechanism, asset need, and rejection condition.

3. **rejected_generic_patterns.md** — Documents 17 generic/templated patterns that must NOT be used for Labebe, with explicit rejection conditions, reasoning, and suggested alternatives. Includes a summary rejection matrix.

4. **handoff.md** — This file.

5. **evidence_manifest.json** — Machine-readable list of source files read, outputs produced, and acceptance criteria met.

---

## Key Decisions Made

### Decision 1: Pattern Format
All patterns use a uniform dimensional table:
- Business Problem
- Shopper Mission
- Category Role
- PDP Module
- Conversion Mechanism
- Asset Need
- What Not to Copy
- Rejection Condition

This ensures no pattern is a moodboard entry. Every pattern must map to a commerce function.

### Decision 2: P0 / P1 / P2 Classification
P0 patterns are required for the 14-day sprint. P1 patterns are strong upgrades if P0 is stable. P2 patterns require assets or capabilities that do not yet exist.

P0 count: 24 patterns across all touchpoints. This is intentionally comprehensive because the Commerce Decision Layer (LAB-007) must explain every module before high-fidelity prototype begins.

### Decision 3: Rejection Conditions Are Hard
Every pattern and every rejected generic pattern includes a specific, testable rejection condition. Examples:
- "Reject if the hero does not show at least 3 recognizable Labebe SKUs."
- "Reject if any claim in the PDP lacks a source label."
- "Reject if bundle items are not logically related."

These conditions are designed to be used by visual/browser QA and fresh agent review.

### Decision 4: No Pretty Sites Without Mapping
The reference_pattern_mapping_draft.md does not list any reference without a dimensional mapping. If a reference could not be mapped to a business problem, it was either excluded or included as a rejected generic pattern.

---

## Files and Locations

| File | Path | Size | Status |
|---|---|---|---|
| reference_pattern_mapping_draft.md | `.../design_reference_mapping/reference_pattern_mapping_draft.md` | ~26KB | Done |
| commerce_pattern_library_draft.md | `.../design_reference_mapping/commerce_pattern_library_draft.md` | ~29KB | Done |
| rejected_generic_patterns.md | `.../design_reference_mapping/rejected_generic_patterns.md` | ~17KB | Done |
| handoff.md | `.../design_reference_mapping/handoff.md` | This file | Done |
| evidence_manifest.json | `.../design_reference_mapping/evidence_manifest.json` | ~4KB | Done |

---

## What Needs to Happen Next

### For LAB-007 (Commerce Decision Layer v0)
The Commerce Decision Layer owner should:
1. Read these pattern files as input for `design_decision_matrix.csv`.
2. Map each P0 pattern to specific hero SKUs (Pink Unicorn, Learning Tower, Play Kitchen, Shelf, Storage).
3. Decide which P0 patterns are in-scope for the 14-day prototype vs. deferred.
4. Produce `rejected_direction_log.md` documenting which patterns were considered and rejected.

### For LAB-008 (DTC Prototype)
The prototype owner should:
1. Use the commerce_pattern_library_draft.md as the module checklist for homepage, collection, PDP, and cart.
2. Use rejected_generic_patterns.md as the anti-checklist during design review.
3. Ensure every implemented module has a corresponding pattern entry.

### For Browser/Visual QA
The QA owner should:
1. Use rejection conditions from both files as P0/P1 test criteria.
2. Flag any design that matches a rejected generic pattern.
3. Verify that every P0 pattern is traceable to a business problem.

---

## Limitations and Gaps

1. **No source URLs for all references**: Some reference files in `labebe_design_reference_pack/` are markdown notes without live URLs. The `evidence_manifest.json` records what was read. If live URLs are needed, they should be added to `source_registry.yaml` in a follow-up task.

2. **No quantitative conversion data**: Conversion mechanisms are stated as hypotheses ("raises AOV," "reduces bounce") based on Baymard/Shopify research, not Labebe-specific A/B tests. These should be treated as design rationale, not proven facts.

3. **No image asset inventory**: Asset needs are described but not mapped to existing Labebe assets. The `asset_readiness_matrix.csv` (LAB-007 output) should cross-reference these asset needs against what exists.

4. **No motion specification**: Motion patterns are described at the pattern level but not specified in frames, timing, or easing. The motion_guidelines.md from the design reference pack should be consulted for implementation.

5. **Mobile-only patterns not fully elaborated**: Some patterns (e.g., mobile menu structure) are mentioned but not fully specified. The `browser_qa_report_dtc.md` should verify 390px/430px behavior.

---

## Acceptance Criteria Verification

| Criterion | Status | Evidence |
|---|---|---|
| Every reference pattern states what Labebe business problem it solves | ✅ | Every entry in reference_pattern_mapping_draft.md has a Business Problem row. |
| Include what not to copy | ✅ | Every pattern has a "What Not to Copy" row. rejected_generic_patterns.md documents 17 patterns to avoid. |
| Include how the pattern could affect homepage, nav, collection, PDP or bundle flow | ✅ | commerce_pattern_library_draft.md is organized by touchpoint. reference_pattern_mapping_draft.md specifies Homepage/Nav/Collection/PDP/Bundle impact. |
| Include rejection conditions for generic/templated design | ✅ | Every pattern has a Rejection Condition. rejected_generic_patterns.md has explicit rejection conditions. |
| Do not call Pro/Gemini | ✅ | No external API calls made. |
| Do not list pretty sites without mapping | ✅ | No reference appears without dimensional mapping. |
| Do not design final UI | ✅ | No pixel specifications, component code, or final designs included. |
| Do not edit prototype code | ✅ | No files in `labebe-gemini-demo/` or `kimi_labebe_design_library/` were modified. |

---

## Next Agent Continuation Path

A fresh agent can continue from these files without reading chat history:

1. Read `reference_pattern_mapping_draft.md` for the full reference-to-business-problem map.
2. Read `commerce_pattern_library_draft.md` for the touchpoint-organized pattern library.
3. Read `rejected_generic_patterns.md` for the anti-patterns.
4. Read `handoff.md` for decisions, limitations, and next steps.
5. Read `evidence_manifest.json` for source traceability.
6. Proceed to LAB-007 (Commerce Decision Layer) or LAB-008 (DTC Prototype) with these patterns as input.
