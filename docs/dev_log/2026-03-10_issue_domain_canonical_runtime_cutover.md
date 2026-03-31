# 2026-03-10 Issue Domain Canonical Runtime Cutover

## Scope

- Turn `issue_domain` from a canonical reader demo into a real runtime consumer.
- Keep authoritative writes in `client_issues` / `client_issue_events`.
- Cut over canonical-preferred read surfaces with legacy fallback.

## Authority Inventory

- Authoritative write plane remains:
  - `chatgptrest/core/client_issues.py`
  - `state/jobdb.sqlite3`
- Canonical reader already existed:
  - `chatgptrest/core/issue_canonical.py`
  - `/v1/issues/canonical/query`
  - `/v1/issues/canonical/export`
- Legacy read surfaces before cutover:
  - `/v1/issues/graph/query`
  - `/v1/issues/graph/snapshot`
  - `ops/export_issue_graph.py`
  - `ops/export_issue_views.py`

## Cutover

- `routes_issues.py`
  - `/v1/issues/graph/query` now prefers canonical graph projection and falls back to legacy graph.
  - `/v1/issues/graph/snapshot` now prefers canonical snapshot and falls back to legacy graph snapshot.
  - `/v1/issues/canonical/query` and `/v1/issues/canonical/export` now sync from authoritative ledger before reading.
- `issue_canonical.py`
  - Added schema bootstrap and issue-domain sync into canonical DB.
  - Added graph snapshot/query helpers backed by canonical objects/relations.
  - Added issue list view snapshot helper for open/recent projections.
  - Added derived evidence visibility for verification and usage nodes.
- `ops/export_issue_graph.py`
  - Now exports canonical-preferred graph snapshots with legacy fallback.
- `ops/export_issue_views.py`
  - Now exports canonical-preferred open/recent issue lists with legacy fallback.
  - History tail still reads authoritative `client_issue_events`.

## Verification

- `tests/test_issue_canonical_api.py`
- `tests/test_issue_graph_api.py`
- `tests/test_export_issue_views.py`
- `tests/test_mcp_issue_tools.py`
- `tests/test_openclaw_guardian_issue_sweep.py`

## Notes

- Legacy fallback is explicit and tested; canonical unavailability should not break existing issue graph and exporter paths.
- Canonical evidence visibility now includes:
  - `Verification`
  - `UsageEvidence`
- This work stops at `issue_domain`; it does not expand planning/research/codex history consumers.
