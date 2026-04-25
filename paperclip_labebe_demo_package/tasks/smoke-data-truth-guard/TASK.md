# CASE 1 - Data Truth Guard end-to-end smoke

Identifier: `LAB-SMOKE-001`

Assignee: Data Truth Guard

Priority: high

Status before smoke: todo

Acceptance:

- Data Truth Guard selects `LAB-SMOKE-001` via `LABEBE_TARGET_ISSUE_IDENTIFIER`.
- Worker writes `outputs/case-LAB-SMOKE-001-data-truth-guard.md`.
- Paperclip issue receives a comment containing the artifact path.
- Paperclip issue status becomes `done`.
- Evidence export includes non-empty issues, MCP policy check, artifact ledger, package manifest, and secret scan.
