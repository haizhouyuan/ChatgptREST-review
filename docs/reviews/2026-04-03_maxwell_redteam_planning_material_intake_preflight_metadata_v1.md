# 2026-04-03 Maxwell Redteam Planning Material Intake Preflight Metadata v1

## Verdict

`approve`

## What redteam accepted

Confirmed by redteam:
- planning-only roles no longer leak through the auto-derived path for non-planning scenarios
- composite archives such as `*.tar.gz` are now classified as `archive` and route to `unpack_first`
- the Feishu-side test change does not overclaim new production intake behavior

## Residual low-risk note

The remaining low-risk boundary is this:
- if a caller explicitly injects `context.attachment_inventory`, `build_task_intake_spec()` currently trusts it and does not sanitize it back to scenario-scoped shape

This is not the same issue as the earlier unconditional leakage bug.
It is a caller-trust boundary and can stay as a later tightening item.

## Judgment used for this batch

The redteam result means this batch can be committed as:
- real `W3 material inventory / preflight metadata`
- not yet `material processing / ingestion automation`
