---
name: "labebe-demo-governance"
description: >
  Use when any Labebe demo agent reads evidence, makes product claims,
  drafts launch copy, creates safety/cost language, or decides whether work
  needs human review. Do not use for generic Paperclip API mechanics.
metadata:
  paperclip:
    tags:
      - governance
      - evidence
      - red-team
---

# Labebe Demo Governance

Use this skill for the Labebe AI Design Studio demo.

Rules:

- Keep Paperclip in local trusted private mode.
- Keep real credentials and external account actions out of the demo.
- Label evidence as verified fact, demo sample, assumption, or forbidden.
- Convert uncertainty into Paperclip review issues.
- Require human review for strategy, safety, DFM, cost, launch, and compliance-adjacent claims.

Claim labels:

- `verified_fact`: directly supported by an attached local source or user-provided file.
- `demo_sample`: local sample data used only to demonstrate workflow shape.
- `assumption`: plausible working hypothesis that needs review.
- `forbidden`: a claim type that must not appear in output.

Human review gates:

- CEO strategy approval.
- Product opportunity approval.
- Safety, DFM, material, stability, small-part, and pinch-point review.
- Preliminary BOM or cost review.
- External channel, ad, marketplace, email, or waitlist publication.

Required behavior:

1. Read `docs/DATA_TRUTH.md`, `docs/FORBIDDEN_CLAIMS.md`, and `docs/ACTION_POLICY.md`.
2. Add the source label beside each important output claim.
3. If a claim is unsupported, mark it as an assumption or create a Paperclip blocker.
4. Never convert demo samples into verified demand, rank, safety, or compliance claims.
