# Gate Kernel v0

Issue: `PCL-001`

## Mandatory Gates

### Scope Separation Gate

Trigger:

- before DTC or Boss Gallery implementation.

Evidence:

- `scope_boundary.md`

Pass standard:

- DTC has no AI Studio, Paperclip board or internal product matrix;
- Boss Gallery is not presented as a consumer shopping site.

### Evidence Integrity Gate

Trigger:

- before product facts enter design decisions.

Evidence:

- `current_data_qa.md`
- `do_not_use_fields.md`

Pass standard:

- products can be uniquely identified;
- dirty fields and join risks are explicit;
- unsafe fields are blocked from copy.

### ASIN Identity Gate

Trigger:

- before Amazon listing/review/VOC data enters decisions.

Evidence:

- `asin_match_scoring.md`

Pass standard:

- ASINs have status: accepted, probable, candidate, rejected or no-match;
- VOC is blocked until identity confidence is sufficient.

### Claim Gate

Trigger:

- before copy, PDP claim, demo claim or asset matrix claim is shown.

Evidence:

- `claim_permission_matrix.csv`
- `blocked_claims.md`

Pass standard:

- unsupported safety, material, certification, review, demand, cost, CAD and production claims are blocked or downgraded.

### Design Decision Gate

Trigger:

- before high-fidelity DTC prototype.

Evidence:

- `design_decision_matrix.csv`
- `rejected_direction_log.md`

Pass standard:

- hero, navigation, PDP, collection, bundle and asset decisions trace to evidence and rejected alternatives.

### Browser / Visual QA Gate

Trigger:

- before user/boss-facing review.

Evidence:

- screenshots;
- browser QA report;
- design review report.

Pass standard:

- HTTP/page load works;
- desktop/mobile/tablet reviewed;
- console/link/core flow issues logged;
- text overflow and visual hierarchy checked;
- cheap AI-template feel explicitly critiqued.

### Closeout Gate

Trigger:

- before issue done.

Evidence:

- `handoff.md`
- `evidence_manifest.json`
- acceptance artifacts.

Pass standard:

- each criterion maps to evidence;
- limitations are explicit.

## Advisory Gates

- CEO / Wow Review.
- Full Design Review Scoring.
- Fresh Agent Review.
- Skill Curator Review.
- Future Pro review after prototypes only if a new decision conflict appears.

