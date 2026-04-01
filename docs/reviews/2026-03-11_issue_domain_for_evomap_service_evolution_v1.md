# 2026-03-11 Issue-Domain For EvoMap Service Evolution v1

## Purpose

This note answers one narrow architecture question:

- how `issue_domain` should serve `EvoMap`
- so that future agents and runtime services actually improve from real failures
- without polluting normal retrieval with raw issue noise

The immediate trigger is Gemini issue `#113`, but the scope is broader than one
bug. The question is what the correct system shape should be.

## Current State

### 1. `issue_domain` already has an authoritative and canonical path

The current issue stack already has real structure:

- authoritative write plane:
  - `client_issues`
  - `client_issue_events`
  - `client_issue_verifications`
  - `client_issue_usage_evidence`
- canonical issue projection:
  - `chatgptrest/core/issue_canonical.py`
  - `POST /v1/issues/canonical/query`
  - `GET /v1/issues/canonical/export`
- canonical-preferred graph view:
  - `POST /v1/issues/graph/query`
  - `GET /v1/issues/graph/snapshot`

This means `issue_domain` is no longer just a loose operational ledger. It is
already the authoritative incident plane plus a derived canonical read plane.

### 2. `EvoMap` already has real ingest, retrieval, and evolution surfaces

The current EvoMap implementation already includes:

- live signals through `EvoMapObserver`
- knowledge ingestion through extractors in `chatgptrest/evomap/knowledge/extractors/`
- retrieval through `chatgptrest/evomap/knowledge/retrieval.py`
- runtime consumption through:
  - `chatgptrest/kernel/context_assembler.py`
  - `chatgptrest/cognitive/context_service.py`
- actuator hooks such as:
  - `CircuitBreaker`
  - `GateAutoTuner`
  - `KBScorer`

So the missing piece is not “create EvoMap from scratch”.

### 3. The missing bridge is issue-domain -> EvoMap semantics

Today EvoMap ingests:

- chat followups
- runbooks
- notes
- commits
- antigravity history
- activity events such as agent closeout and git commit

But it does **not** yet ingest the structured issue lifecycle itself.

There is no dedicated extractor that turns:

- issue family
- evidence
- fix commit
- verification
- qualifying success

into EvoMap archive/review/service objects.

## Key Design Decision

`issue_domain` and `EvoMap` should not be collapsed into one plane.

They should play different roles:

1. `issue_domain` is the authoritative incident and proof plane.
2. `EvoMap` is the governed retrieval and evolution plane.
3. The bridge between them should be selective, replayable, and audited.

This is the same archive/review/service separation already identified in the
EvoMap review architecture.

## Why Direct Raw Ingest Is Wrong

If raw issue text is pushed directly into EvoMap retrieval, the system will
learn the wrong thing.

### Risk A: runtime retrieval currently allows `staged`

Current EvoMap retrieval still allows:

- `promotion_status=active`
- `promotion_status=staged`

That means a newly ingested issue atom could become visible to runtime
consumers before it is semantically reviewed.

### Risk B: open incidents are not reusable knowledge

An open issue is evidence of a problem, not yet a service lesson.

Examples of things that should **not** become default runtime answers:

- raw GitHub issue bodies
- one-off broken job traces
- temporary mitigations without verification
- issue chatter that has no stable operational rule

### Risk C: graph/canonical objects are not the same as retrievable lessons

Canonical issue objects are excellent for:

- authoritative history
- traceability
- family grouping
- evidence linking

But they are not automatically suitable as:

- agent guidance
- troubleshooting best practice
- routing policy
- service evolution memory

## The Correct System Shape

The right pipeline is:

1. intake
2. authoritative issue state
3. canonical issue projection
4. EvoMap archive ingest
5. EvoMap review / promotion
6. runtime retrieval
7. actuator / routing / policy feedback

### Stage 1. Intake

Accepted intake sources:

- worker auto report
- manual `/v1/issues/report`
- GitHub issue thread as human coordination anchor

Important:

- GitHub issue is coordination-only
- it is not the authoritative incident store

### Stage 2. Authoritative issue state

The issue ledger remains the source of truth for:

- issue identity
- status transitions
- family assignment
- evidence links
- verifications
- usage evidence

This is where `#113` must be properly backfilled and where future real Gemini
usage verifies the fix.

### Stage 3. Canonical issue projection

Canonical projection should continue to normalize issue-domain structure into:

- `Issue`
- `IssueFamily`
- `Job`
- `FixCommit`
- `Verification`
- `UsageEvidence`
- `DocEvidence`

This plane exists to make the history queryable and replayable.

### Stage 4. EvoMap archive ingest

This is the missing implementation step.

Add a dedicated extractor, conceptually:

- `IssueCanonicalExtractor`

Source:

- canonical issue plane, not GitHub markdown

Archive-plane outputs in EvoMap:

- one `Document` per canonical snapshot or issue-family export batch
- one `Episode` per issue lifecycle object or transition
- archive atoms that preserve the structured incident story

These atoms should initially remain non-service material.

### Stage 5. EvoMap review and promotion

Only reviewed issue-derived knowledge should become retrievable for runtime.

Recommended promotion contract:

- open / in_progress issues:
  - archive only
  - not default runtime visible
- mitigated without verification:
  - review only
  - maybe retrievable in explicit debug mode
- mitigated + verification:
  - eligible for distilled troubleshooting/procedure atoms
- closed + qualifying usage:
  - eligible for `active` lesson/procedure atoms

The important point is:

- service should retrieve the learned operational rule
- not the raw issue narrative

### Stage 6. Runtime retrieval

The runtime should retrieve only issue-derived atoms that satisfy all of:

- reviewed/distilled
- grounded by evidence
- tied to a stable family or rule
- promoted for service use

This likely means:

- the raw issue archive remains in EvoMap but hidden from default retrieval
- only distilled lessons become `active`
- default retrieval should move toward `active_only`

### Stage 7. Evolution feedback

Once issue-derived lessons are in EvoMap, they can help the system evolve in
two ways.

#### A. Knowledge path

Future agents can retrieve:

- what failed before
- what fix pattern worked
- what verification proved the mitigation
- what usage evidence proved real-world recovery

This improves:

- debugging
- repair planning
- postmortem quality
- regression triage

#### B. Control path

Issue lifecycle should also emit explicit EvoMap signals such as:

- `issue.reported`
- `issue.reopened`
- `issue.mitigated`
- `issue.verified`
- `issue.closed`
- `issue.usage_confirmed`
- `issue.family_recurred`

These should feed:

- route/risk awareness
- provider guardrails
- quality gate tuning
- future evolution experiments

The point is not to make actuators fire directly from GitHub comments.
The point is to let the authoritative issue lifecycle become structured
evolution feedback.

## What This Means For #113

For `#113`, the correct path is:

1. keep GitHub issue `#113` as the human coordination anchor
2. ensure authoritative issue-domain records capture the three distinct families
3. add or confirm the narrow family for the still-live bug:
   - `gemini_anchor_only_bogus_completion`
4. attach the actual code fix commit:
   - `6b64aaa`
5. add real post-fix verification from a Gemini usage run
6. once mitigated/verified or closed with qualifying usage, distill the lesson
   into EvoMap

The lesson that should enter service is not:

- "`#113` happened"

The lesson that should enter service is something closer to:

- anchor-only Gemini UI residue must fail closed
- `ui_noise_empty_after_sanitize` is contamination, not success
- short bogus completions must not terminalize as `completed`

That is the reusable operational rule.

## Recommended Work Packages

### WP1. Finish issue-domain semantics for `#113`

- register or confirm the right family mapping
- backfill the cited jobs into authoritative/canonical issue records
- record post-fix verification
- record qualifying usage if recovery is confirmed

### WP2. Build the issue-domain -> EvoMap extractor

Add a dedicated extractor from canonical issue projection to EvoMap archive.

It should emit at least:

- issue summary atoms
- mitigation/fix atoms
- verification-backed troubleshooting atoms
- family-level lesson candidates

### WP3. Add runtime visibility rules for issue-derived atoms

Before broad ingest, add an explicit rule so unresolved issue atoms do not
leak into normal runtime retrieval.

At minimum:

- archive/review atoms stay non-default
- only distilled active lessons are default-visible

### WP4. Add issue lifecycle signals into EvoMap observer

Emit structured signals on:

- report
- reopen
- mitigation
- verification
- closure
- recurring-family detection

### WP5. Prove one real business loop

The first success criterion should be narrow and real:

- a future agent debugging a Gemini-like failure retrieves the correct lesson
- the retrieved lesson points to the known fix shape and verification pattern
- the issue lifecycle continues to enrich EvoMap without polluting general QA

## Anti-Patterns To Avoid

Do not:

- treat GitHub issue text as the authoritative incident source
- ingest raw issue bodies straight into default EvoMap retrieval
- bypass verification and usage evidence before promoting issue-derived atoms
- confuse canonical queryability with service readiness
- use issue chatter as a substitute for distilled operational rules

## Bottom Line

`issue_domain` exists so EvoMap can evolve the service from real failures.

But that only works if the system preserves the right layering:

- issue ledger and canonical graph hold the authoritative incident truth
- EvoMap ingests that truth as archive material
- review/promotion distills reusable lessons
- only verified lessons become service-visible
- lifecycle transitions emit structured evolution signals

That is the system shape that turns issues like `#113` into durable agent
experience instead of just accumulating more operational text.
