# 2026-03-11 Planning Review State Audit Walkthrough v1

After the cycle automation was in place, the next missing piece was visibility.

The cycle script can now tell us:

- what needs review
- where reviewer outputs should land
- how to overlay and apply

But after a live apply, there still was no tiny, direct way to answer:

`Is the current planning reviewed slice still aligned with the allowlist, or has it drifted?`

That is what [report_planning_review_state.py](/vol1/1000/projects/ChatgptREST/ops/report_planning_review_state.py) is for.

## Why I added it

The planning line is now in maintenance mode, not one-shot import mode.

In maintenance mode, the operator needs quick answers to three different questions:

1. Do we have a new delta to review?
   - handled by `run_planning_review_cycle.py`
2. If we apply a reviewed baseline, does it bootstrap correctly?
   - handled by `import_review_plane + apply_bootstrap_allowlist`
3. After that apply, is the live slice still aligned?
   - this audit script answers that

Without the third check, you can have a technically successful apply but no small proof that the allowlist and live bootstrap slice still agree.

## What the live audit said

The live result was:

- `allowlist_docs = 116`
- `reviewed_docs = 156`
- `planning_review_plane_docs = 542`
- `201 active / 25 candidate / 40675 staged`
- `allowlist_docs_without_live_atoms = 0`
- `stale_live_atoms_outside_allowlist = 0`
- `reviewed_but_unclassified_docs = 3194`

The first five numbers are the important maintenance signal. They show the reviewed bootstrap slice is internally consistent.

The last number is the important backlog signal. It shows most planning docs still live outside the reviewed slice, which is expected and should not be confused with drift.

## Why `reviewed_but_unclassified_docs` matters

I deliberately kept that count in the audit output because otherwise a maintenance operator can misread “0 drift” as “planning is fully reviewed”.

It is not.

What is true is narrower:

- the currently reviewed and allowlisted planning slice is healthy
- the much larger planning family still contains a big unreviewed backlog

That distinction is exactly the boundary we have been keeping on `#114`.
