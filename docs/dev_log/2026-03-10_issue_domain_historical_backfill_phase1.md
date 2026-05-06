# 2026-03-10 Issue Domain Historical Backfill Phase 1

## Scope

Executed the approved narrow `issue_domain` phase from `#112`, after scope was reduced to:

- coverage parity
- synthetic evidence provenance
- curated family registry
- stronger `DocEvidence`

Explicitly not included in this phase:

- `Issue -> Commit/File/Symbol` GitNexus bridge
- new runtime consumers outside `issue_domain`
- ledger write-path changes

## What Changed

### 1. Coverage parity

- `sync_issue_canonical()` no longer truncates canonical sync to the query/export limit.
- canonical sync now walks the full authoritative ledger via pagination and stores coverage meta:
  - `authoritative_issue_count`
  - `canonical_issue_count`
  - `coverage_gap_count`
  - `missing_issue_ids`
- canonical summaries for:
  - `/v1/issues/canonical/query`
  - `/v1/issues/canonical/export`
  - `/v1/issues/graph/snapshot`
  - open-issue list projection
  now surface the coverage drift fields.

Files:

- [issue_canonical.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/issue_canonical.py)
- [test_issue_canonical_api.py](/vol1/1000/projects/ChatgptREST/tests/test_issue_canonical_api.py)

Commit:

- `d99493e` `fix(issues): sync canonical issue coverage without query ceiling`

### 2. Synthetic evidence provenance

- historically synthesized `Verification` and `UsageEvidence` now carry explicit canonical provenance:
  - `synthetic=true`
  - `derived_from.event_id`
  - `derived_from.event_type`
- canonical objects for synthesized evidence now use:
  - `authority_level=derived`
  - `source_table=client_issue_events`
- explicit evidence tables remain authoritative when present.

Files:

- [issue_canonical.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/issue_canonical.py)
- [test_issue_canonical_api.py](/vol1/1000/projects/ChatgptREST/tests/test_issue_canonical_api.py)

Commit:

- `8172335` `feat(issues): formalize synthetic canonical evidence provenance`

### 3. Curated family registry

- added machine-readable registry:
  - [issue_family_registry.json](/vol1/1000/projects/ChatgptREST/docs/issue_family_registry.json)
- added runtime matcher:
  - [issue_family_registry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/issue_family_registry.py)
- `issue_graph._issue_family_id/_issue_family_label` now consult the curated registry before falling back to fingerprint families.

Initial curated families:

- `gemini_followup_thread_handoff`
- `gemini_wait_no_progress`
- `upload_path_normalization`
- `completion_guard_false_downgrade`
- `provider_job_kind_contract_drift`

### 4. Stronger `DocEvidence`

- `_doc_refs()` now resolves:
  - docs root from `CHATGPTREST_DOCS_ROOT` when set
  - first matching locator
  - excerpt
  - content hash
- canonical issue projection now materializes `DocEvidence` objects instead of weak file-only document refs.
- canonical graph snapshot now exposes `doc_evidence_count`.

Files:

- [issue_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/issue_graph.py)
- [issue_canonical.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/issue_canonical.py)
- [test_issue_canonical_api.py](/vol1/1000/projects/ChatgptREST/tests/test_issue_canonical_api.py)

Commit:

- `8a70b8a` `feat(issues): add curated issue families and doc evidence`

## Validation

Ran:

- `PYTHONPATH=. ./.venv/bin/pytest -q tests/test_issue_canonical_api.py tests/test_issue_graph_api.py tests/test_export_issue_views.py`
- `python3 -m py_compile chatgptrest/core/issue_canonical.py chatgptrest/core/issue_graph.py chatgptrest/core/issue_family_registry.py tests/test_issue_canonical_api.py`

Key coverage added:

- canonical sync ignores query/export limit when syncing authoritative issues
- coverage drift fields are present in canonical summaries
- synthesized verification/usage evidence is marked derived from issue events
- curated family registry compresses repeated provider/job-kind drift into one family
- `DocEvidence` carries `locator`, `excerpt`, and `content_hash`

## Follow-up

The next `issue_domain` phase should start from the new coverage numbers after this parity fix lands, then decide whether there is any real residual backfill gap left.

The GitNexus bridge remains intentionally deferred to the next approval round.
