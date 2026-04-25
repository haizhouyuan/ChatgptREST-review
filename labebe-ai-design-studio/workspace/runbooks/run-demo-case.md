# Run Demo Case

## Preconditions

- Paperclip tmux session is running: `paperclip-labebe-demo`.
- Health endpoint returns `ok`: `http://127.0.0.1:3100/api/health`.
- Company ID: `1cb6d439-2bdf-4f63-ad9a-b5326d5546df`.
- Agent adapters are `process`.
- Data Truth Guard adapter env includes `LABEBE_TARGET_ISSUE_IDENTIFIER=LAB-SMOKE-001`.
- Real external accounts remain disabled.

## Case

Create or reuse a small Paperclip issue assigned to Data Truth Guard:

- Identifier: `LAB-SMOKE-001`
- Title: `CASE 1 - Data Truth Guard end-to-end smoke`
- Status: `todo`
- Priority: `high`
- Expected result: Data Truth Guard heartbeat checks out the issue, writes a local artifact, comments in Paperclip, and marks the case done.

## Evidence

- Paperclip heartbeat run status is `succeeded`.
- Local artifact exists: `outputs/case-LAB-SMOKE-001-data-truth-guard.md`.
- Paperclip issue has a comment with the artifact path.
- `evidence/issues_redacted.json` is non-empty and contains `LAB-SMOKE-001`.
- `evidence/issue_consistency_check.json` reports all 10 epic identifiers plus the smoke issue as aligned.
- `evidence/mcp_tools_list_redacted.json` and `evidence/mcp_policy_check.json` are present.
- `evidence/artifact_ledger.json`, `evidence/package_manifest.txt`, and `evidence/secret_scan.txt` are present.
- No raw secret appears in the portable package or review packet.
