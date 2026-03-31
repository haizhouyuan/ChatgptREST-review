# 2026-03-10 Issue Domain Historical Data Backfill Approval

## Scope

- This document stays strictly inside `issue_domain`.
- It assumes the canonical reader and canonical-preferred runtime cutover already exist.
- It does **not** propose new runtime consumers for `planning`, `research`, `codex_history`, or `memory_hot`.
- Goal: use broader real data to define the next approved work package for `issue_domain` so the canonical plane becomes complete, trustworthy, and worth querying.

## Real Data Snapshot

Audit time: 2026-03-10 CST

### Authoritative ledger (`state/jobdb.sqlite3`)

- `client_issues`: `242`
- `client_issue_events`: `675`
- `client_issue_verifications`: `1`
- `client_issue_usage_evidence`: `30`
- `incidents`: `4703`
- `jobs`: `6771`

Issue status distribution:

- `closed`: `151`
- `mitigated`: `79`
- `open`: `12`

Issue event distribution:

- `issue_reported`: `322`
- `issue_status_updated`: `284`
- `issue_evidence_linked`: `38`
- `issue_usage_evidence_recorded`: `30`
- `issue_verification_recorded`: `1`

### Canonical issue plane (`state/knowledge_v2/canonical.sqlite3`)

- `canonical_objects`: `4432`
- `object_sources`: `4432`
- `projection_targets`: `4632`
- `canonical_relations`: `23283`

Canonical issue-domain object counts:

- `Incident`: `3480`
- `Document`: `219`
- `Issue`: `200`
- `Family`: `194`
- `Job`: `160`
- `Verification`: `90`
- `UsageEvidence`: `89`

Projection targets:

- `graph`: `4432`
- `ledger_ref`: `200`

Top relation types:

- `documented_in`: `15941`
- `linked_incident`: `6622`
- `belongs_to_family`: `200`
- `uses_job`: `178`
- `latest_job`: `163`
- `validated_by`: `90`
- `proven_by_usage`: `89`

Canonical sync meta:

- `last_issue_event_id`: `675`
- `last_sync_issue_count`: `200`

### Current projection outputs

- Open issue list:
  - [latest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/open_issue_list/latest.json)
  - [latest.md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/open_issue_list/latest.md)
- Issue graph:
  - [latest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/issue_graph/latest.json)
  - [latest.md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/issue_graph/latest.md)

### Historical text sources

- Registry entries in [issues_registry.yaml](/vol1/1000/projects/ChatgptREST/docs/issues_registry.yaml): `18`
- March dev logs under [docs/dev_log](/vol1/1000/projects/ChatgptREST/docs/dev_log): `79` markdown files
- [handoff_chatgptrest_history.md](/vol1/1000/projects/ChatgptREST/docs/handoff_chatgptrest_history.md) is useful narrative context, but it currently has very weak direct issue-id linkage compared with dev logs and ledger events.

## Findings

### 1. Canonical coverage is live but incomplete

- Authoritative ledger has `242` issues.
- Canonical plane currently has `200` issue objects.
- That leaves `42` authoritative issues missing from the canonical issue plane.

This is the highest-priority gap. `issue_domain` is already a real canonical runtime consumer, so missing coverage is no longer acceptable as a "later backfill" problem.

### 2. Historical evidence is already being synthesized, but implicitly

- Authoritative tables currently only contain:
  - `1` explicit verification record
  - `30` explicit usage evidence rows
- Canonical plane currently exposes:
  - `90` verification nodes
  - `89` usage evidence nodes

This means the system is already deriving valuable evidence from historical state transitions and related events. That is good, but it is currently too implicit. The next phase should formalize this as first-class evidence provenance instead of leaving it as hidden read-time synthesis.

### 3. Family compression is still weak

- `200` issue objects map to `194` family objects.

That is only marginally better than treating each issue as its own family. The current family layer is still dominated by fallback logic rather than curated recurrence semantics.

### 4. Document linkage is broad, but too weakly provenanced

- `documented_in` edges dominate the graph.
- Current links are useful for recall, but too coarse for trust:
  - mostly file-level
  - no stable locator
  - no excerpt
  - no content hash for the exact supporting passage

The graph is now good enough to browse, but not yet strong enough to act as a high-confidence evidence system.

### 5. Dev logs are the richest historical backfill source

For `issue_domain`, the highest-value historical sources are not long narrative histories but:

- `client_issue_events`
- `jobs` and `job_events`
- `docs/dev_log/*.md`
- `docs/issues_registry.yaml`
- GitHub issue comments on operational threads such as `#96`, `#107`, and `#112`

`handoff_chatgptrest_history.md` remains valuable as a curated narrative, but it should not be treated as the primary backfill source.

## What Historical Issue Data Is Worth Pulling In

The next phase should not ingest full issue text blindly. It should extract the following high-signal objects and edges.

### Must-have structured objects

- `IssueFamily`
- `RootCause`
- `FixCommit`
- `Verification`
- `UsageEvidence`
- `ReviewFinding`
- `RepairAction`
- `EnvironmentSnapshot`
- `DocEvidence`

### Must-have high-value fields

- `family_id`
- `root_cause_summary`
- `failure_plane`
- `provider`
- `kind`
- `client_name`
- `job_id`
- `incident_id`
- `commit_sha`
- `pr_number`
- `status_transition`
- `verification_type`
- `verification_status`
- `usage_success`
- `source_ref`
- `source_locator`
- `excerpt`
- `content_hash`

### Must-have edges

- `Issue -> belongs_to_family -> IssueFamily`
- `Issue -> caused_by -> RootCause`
- `Issue -> fixed_by -> FixCommit`
- `Issue -> validated_by -> Verification`
- `Issue -> proven_by_usage -> UsageEvidence`
- `Issue -> documented_in -> DocEvidence`
- `Issue -> linked_incident -> Incident`
- `Issue -> uses_job -> Job`
- `Issue -> latest_job -> Job`
- `IssueFamily -> discussed_in -> GitHubComment`
- `IssueFamily -> documented_in -> DevLog`

## Approved Target for the Next Work Package

The next work package should turn the current canonical issue plane from "runtime consumer with partial history" into "runtime consumer with durable historical knowledge".

That work package should be restricted to these five deliverables.

### 1. Canonical coverage parity

- Remove the current issue-count truncation so canonical issue coverage matches the authoritative ledger.
- Add a coverage check that compares:
  - authoritative issue count
  - canonical issue count
  - missing issue ids
- Make the exporter surface coverage drift explicitly.

Success condition:

- no authoritative issue is silently absent from canonical issue projection

### 2. Formalize synthetic evidence provenance

- Keep explicit evidence tables authoritative.
- Add first-class canonical provenance for evidence derived from:
  - historical `issue_status_updated`
  - legacy close metadata
  - historical client success patterns
- Mark derived evidence explicitly as:
  - `synthetic=true`
  - `derived_from=<event or source>`

Success condition:

- `Verification` and `UsageEvidence` in canonical are explainable and auditable, not magic read-time side effects

### 3. Family registry instead of fingerprint-only grouping

- Introduce a small curated family registry for high-value recurring families.
- Start with the recurring families already seen in production:
  - Gemini follow-up / thread handoff
  - Gemini wait / no progress
  - upload path normalization
  - completion guard false downgrade
  - provider contract drift

Success condition:

- family count begins to compress meaningfully instead of shadowing raw issue count

### 4. Stronger document evidence contract

- Replace weak file-level `documented_in` references with `DocEvidence` records carrying:
  - file path
  - locator
  - excerpt
  - content hash
- Prefer dev logs and issue comments over broad file-name matching.

Success condition:

- a reviewer can trace a graph edge back to the exact supporting text span

### 5. GitNexus bridge for issue-domain only

- Add a minimal bridge from issue-domain to code-domain:
  - `Issue -> Commit`
  - `Issue -> File`
  - `Issue -> Symbol`
- Keep this strictly inside `issue_domain`.
- Do not expand to planning/research runtime consumers in this phase.

Success condition:

- issue graph queries can answer both:
  - "what happened"
  - "what code path fixed or caused it"

## Explicit Non-Goals

This approval request does **not** ask to:

- expand canonical runtime into `planning`
- expand canonical runtime into `research`
- expand canonical runtime into `codex_history`
- build `memory_hot`
- replace ledger authoritative writes
- replace GitNexus with a new code graph

## Approval Request

I am requesting approval on `#112` for the following narrow issue-domain phase:

1. fix canonical issue coverage parity
2. formalize synthetic evidence provenance
3. add a curated issue family registry
4. harden document evidence provenance
5. add a minimal GitNexus bridge for issue-domain only

## Why This Is the Right Next Step

The current `issue_domain` work is past the demo stage:

- canonical-preferred runtime reads already exist
- graph/query/export already exist
- live issue lifecycle already exists

The highest-value next step is not more planning. It is to make the historical data already present in production trustworthy, queryable, and useful enough to reduce repeat debugging.

That means:

- complete coverage
- explicit evidence provenance
- real families
- precise historical references
- code bridge

No new domain should jump ahead of that.
