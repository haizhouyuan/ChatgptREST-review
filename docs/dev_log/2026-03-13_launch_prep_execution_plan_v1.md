# 2026-03-13 Launch Prep Execution Plan v1

## Goal

Prepare the current `origin/master` product surface, now including merged
`#177`, for release with:

- verified merge state
- full repository regression
- launch-critical scenario reruns
- explicit adjudication of any non-green signal
- a release-ready summary that can be used as the final operator handoff

## Constraints

- work only in a clean worktree rooted at current `origin/master`
- treat short external-model answers as non-final; do not accept preambles as
  launch evidence
- prefer fixing real blockers over adding more docs
- keep all non-code artifacts versioned

## Execution Steps

### 1. Freeze launch baseline

Action:

- confirm worktree cleanliness
- confirm `origin/master` head includes merged `#177`
- record the exact launch baseline in a todo/walkthrough pair

Effect:

- removes ambiguity about what code is being launched

Acceptance:

- clean worktree
- `HEAD == origin/master` or branch is a clean fast-forward derivative

### 2. Re-run repository regression

Action:

- run `./.venv/bin/pytest -q`

Effect:

- ensures no hidden cross-suite regression remains after the latest planning fix

Acceptance:

- exit code `0`
- any failure must be fixed or explicitly adjudicated as non-product noise

### 3. Re-run planning groundedness and planning-review scenarios

Action:

- rerun the planning review suite used by `#177`
- rerun planning review/report/export/cycle scripts as needed

Effect:

- proves the merged fix works on both the fresh and stale-rerun groundedness
  paths

Acceptance:

- targeted suite green
- stale-groundedness rerun scenario remains green

### 4. Re-run launch-critical product scenarios

Action:

- rerun the minimum critical product smokes:
  - execution plane parity
  - EvoMap launch smoke
  - EvoMap telemetry live smoke
  - OpenClaw runtime guard smoke
  - convergence validation bundle

Effect:

- verifies no product-grade regression escaped the planning fix merge

Acceptance:

- all required smokes green
- live states accepted only if explicitly adjudicated

### 5. Repair anything real

Action:

- if any scenario is red, patch code
- rerun only after the concrete defect is fixed
- document each fix and why it was needed

Effect:

- avoids carrying known defects into release

Acceptance:

- no unresolved evidence-backed blocker remains

### 6. Optional documentation mergeback

Action:

- evaluate whether the post-merge validation documentation branch should be
  merged or cherry-picked into the release prep branch for audit completeness

Effect:

- keeps launch evidence closer to the code baseline

Acceptance:

- explicit yes/no decision recorded

### 7. Final release report

Action:

- write final walkthrough and report
- include exact commands, artifacts, residuals, and release decision

Effect:

- provides operator-grade launch handoff

Acceptance:

- final report exists
- closeout can reference it directly
