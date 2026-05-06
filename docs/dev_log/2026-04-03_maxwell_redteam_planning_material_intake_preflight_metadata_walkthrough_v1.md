# 2026-04-03 Maxwell Redteam Planning Material Intake Preflight Metadata Walkthrough v1

## What happened

I sent the `W3 material intake preflight metadata` batch to Maxwell for critical review.

The first redteam pass identified two real issues:
- planning-only taxonomy leaked into non-planning auto-derived paths
- `*.tar.gz` style composite archives could still be misclassified

I accepted both, fixed them in code, reran the relevant regression suite, and then asked Maxwell to review again.

## Final redteam outcome

Final verdict: `approve`

Remaining note:
- explicit caller-provided `context.attachment_inventory` is still trusted as-is

That note is kept as a later boundary-hardening item, not as a blocker for this batch.
