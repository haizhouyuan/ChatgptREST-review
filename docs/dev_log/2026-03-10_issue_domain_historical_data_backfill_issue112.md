# 2026-03-10 Issue Domain Historical Data Backfill for Issue #112

## What I Did

- audited authoritative issue-domain data in `state/jobdb.sqlite3`
- audited canonical issue-domain data in `state/knowledge_v2/canonical.sqlite3`
- compared authoritative issue counts with canonical issue counts
- inspected projection outputs in `artifacts/monitor/open_issue_list/` and `artifacts/monitor/issue_graph/`
- sampled historical sources:
  - `docs/issues_registry.yaml`
  - `docs/dev_log/*.md`
  - `docs/handoff_chatgptrest_history.md`
- wrote a narrow approval proposal for `issue_domain` only

## Why

`issue_domain` is already a real canonical runtime consumer. The next step should be driven by real data gaps, not another abstract roadmap.

## Main Findings

- authoritative ledger has `242` issues, canonical has `200`
- authoritative explicit evidence is sparse, but canonical already derives much richer evidence from history
- family compression is weak: `200` issues -> `194` families
- dev logs are a stronger historical backfill source than the handoff history file
- document provenance needs locators and excerpts, not only file-level links

## Output

- review doc:
  - [2026-03-10_issue_domain_historical_data_backfill_approval.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-03-10_issue_domain_historical_data_backfill_approval.md)

## Next Action

- post the summary and approval request to GitHub issue `#112` as `issue graph codex`
