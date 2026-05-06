# AsterREST Broker/Harness Pro Answer Digest v1

Date: 2026-05-01

## Source

- original ask job: `82ad0a99d0424946a191bd1a419af465`
- conversation export job: `6be2e75bde4e42b1acd2b88e5ce0acde`
- conversation URL: `https://chatgpt.com/c/69f420aa-0be0-839e-905e-ec5a10b3d4de`
- canonical answer path: `artifacts/jobs/6be2e75bde4e42b1acd2b88e5ce0acde/answer.md`
- answer chars: `39967`
- answer sha256: `a8b0c18ba9cc03b9f31c74b054fdb725cf9519425c5340a8e362a2ad68a0c023`
- conversation export sha256: `b779797056350ab12df1086302260a03cb35f1d1b1bccba2322f3cf059b22013`

The original ask job reached `needs_followup` because the completion guard downgraded an initial quick/provisional response. The final long answer was visible in the conversation export. A dedicated read-only conversation export job was therefore created and is the canonical evidence for this digest.

## Executive Digest

The Pro review validates the conservative direction:

```text
AsterREST Job Kernel
+ Browser Harness
+ Policy-Gated Adaptive Recovery
+ TaskFabric-facing ExternalModelBrokerAgent
```

It explicitly rejects making a free-form browser agent the default execution engine for authenticated provider web sessions.

The reviewer says the proposal is not too conservative. It is closer to a production posture because the existing Job Kernel already owns hard-to-rebuild responsibilities: idempotency, queueing, worker leases, cooldowns, artifacts, completion/finality contracts, conversation recovery, and public surface validation.

## Main Corrections To Our Plan

1. `Adaptive Recovery` must become a policy-gated recovery subsystem, not a generic "call an agent on failure" path.

2. `Browser Harness` must exist before semantic locator, visual QA, or general browser-agent fallback.

3. `ExternalModelBrokerAgent` must stay narrow. It can submit, query, fetch, validate artifacts, and return evidence. It must not attach to browser sessions, own credentials, or bypass provider lane state.

4. Add explicit `ProviderLaneState` and session policy. This is stronger than our original sketch and should be P0, not a later operational concern.

5. Keep general browser agents as P4 sandbox/offline tools only. They may propose selector migrations or script patches; they should not execute actions in authenticated provider sessions.

## Proposed Internal Architecture

The review recommends a stricter variant called a policy-gated external model broker architecture:

- `Job Kernel`: business truth, queue, idempotency, terminalization, finality, artifact registry.
- `Browser Harness Core`: controlled browser connection, profile/context/page lease, deterministic action execution, observation capture, action ledger.
- `Browser Observation Layer`: DOM digest, accessibility snapshot, screenshot/crop/hash, URL/title, tab identity, network/console summary.
- `Failure Classifier`: selector timeout, unexpected modal, rate limit, login expired, challenge page, answer-visible/export-missing, export 429, target closed, browser crash, operator interference.
- `Recovery Policy Engine`: maps failure class + lane state + job state + risk level to allowed observations, allowed actions, forbidden actions, max attempts, terminal/pause/handoff rule.
- `Finality Reconciler`: compares browser-visible answer, raw export, rendered answer, URL, message count, last assistant digest, export freshness, and finality contract.

## Important State Model

The answer says to separate at least these state families:

- `JobState`
- `BrowserAttemptState`
- `ProviderLaneState`
- `ArtifactFinalityState`
- `FailureClass`

Provider lane examples:

- `AVAILABLE`
- `FRONTEND_RATE_LIMITED`
- `EXPORT_RATE_LIMITED`
- `LOGIN_EXPIRED`
- `CHALLENGE_REQUIRED`
- `MAINTENANCE`
- `OPERATOR_RESERVED`

This is the clearest architectural addition from the review: provider lane state must be first-class, not an incidental cooldown flag.

## Production Failure Handling

The review maps the key historical failure modes to detection/recovery rules:

- UI drift: try accessibility or semantic locator under postcondition checks; otherwise operator handoff.
- Session collision: pause lane, never continue in an unknown tab.
- Frontend rate limit: set provider lane rate-limited; no agent click-through.
- Backend export 429: export cooldown; do not treat fallback as clean success.
- Stale export: reject artifact as final; retry read-only fetch/export.
- Partial answer or progress stub: non-final; wait/reconcile rather than terminalize.
- Login or challenge page: fail closed, operator only.
- Browser crash: capture evidence, restart clean profile once if safe, repeated crash goes to maintenance.
- Duplicate jobs: return/reuse existing job, do not submit again.
- Raw export full but rendered answer incomplete: generate full transcript via conversation recovery job and keep artifact types distinct.

This directly reinforces the bugs we have recently seen.

## Observability Minimum

The minimum action ledger should include:

- job/attempt/provider/lane/profile/context/page identity
- script and harness version
- action sequence
- actor type
- risk class
- action type
- selector strategy
- expected postcondition
- timeout/retry
- before/after observation refs
- network and console summaries
- artifact refs
- failure class
- recovery policy id
- decision
- error stack hash

The replay bundle should include:

- state transition timeline
- action ledger
- screenshots/crops
- DOM/accessibility snapshots
- network summary with sensitive fields redacted
- console summary
- raw export and rendered answer artifacts
- conversation URL
- finality reconciliation report
- failure classifier output
- recovery attempts
- script/harness versions
- provider lane state timeline

## Token/Cost Position

The review is very explicit: happy path should use zero LLM/VLM calls.

Recommended cost ladder:

1. deterministic selector/postcondition
2. DOM query / URL / network status
3. accessibility subtree
4. provider-specific regex classifier
5. screenshot crop
6. small LLM classifier on redacted DOM/accessibility
7. VLM classifier on crop
8. semantic locator proposal
9. operator handoff
10. general browser agent in sandbox only

LLM/VLM calls are justified for ambiguous modal classification, selector drift proposals, replay summary, short progress-stub classification, and offline patch suggestions. They are not justified for every click, normal submit, normal export, cooldown override, login/challenge solving, or duplicate submission decisions.

## TaskFabric Integration

The review says `ExternalModelBrokerAgent` should be the only TaskFabric role authorized to request external model work through AsterREST.

Allowed:

- `ask_external_model`
- `status`
- `result`
- `fetch_conversation_url`
- restricted `repair_job`
- artifact listing/attachment

Forbidden:

- direct browser automation
- direct CDP attach
- arbitrary Playwright sessions
- provider login
- account settings pages
- challenge solving
- rate-limit bypass
- direct browser profile access

Other coding, research, review, planner, test-fixing, general browser, semantic locator, and visual QA agents should not touch provider browser sessions directly.

## Implementation Plan From Review

### P0

Safety and state correctness, no agentic recovery:

- provider lane state machine
- richer job state split
- minimal action ledger
- dedicated automation browser profile
- rate-limit fail-closed
- idempotency hardening
- public surface validation

### P1

Production Browser Harness and replay bundle:

- wrap existing deterministic scripts
- before/after checkpoints
- screenshot/crop policy
- DOM/accessibility digest
- network/console summaries
- replay bundle
- finality reconciliation report
- artifact freshness checks

### P2

Constrained Adaptive Recovery:

- failure taxonomy
- recovery policy table
- accessibility snapshot fallback
- semantic locator proposal for known intents
- deterministic postcondition validation
- DOM/export/visible-answer reconciliation
- browser crash restart under lease
- operator handoff

### P3

Visual QA and limited model-assisted diagnostics:

- modal classifier using screenshot crop
- replay-bundle summary for operator
- progress-stub classifier on short redacted excerpts
- visual/DOM disagreement detector
- recovery cost budget

### P4

General browser agent evaluation only:

- sandbox-only general browser agent
- offline UI exploration from replay bundle
- script patch proposal generator
- selector migration assistant
- no production CDP attach

## Hard No-Go Conditions

The review lists these hard no-go conditions:

- arbitrary agents can attach to AsterREST CDP ports
- automation uses the operator daily browser profile
- adaptive recovery exists before ledger/replay/failure classification
- rate-limit/login/challenge pages are not fail-closed
- job terminalization can happen without finality evidence
- backend export 429 is treated as successful fallback
- duplicate submission remains possible
- public surface can be stale without detection
- replay bundles leak secrets without retention/redaction controls
- no provider-lane kill switch
- general browser agent can operate authenticated sessions by default
- browser lifecycle/memory is unbounded
- operator handoff is not explicit

## Our Updated Interpretation

The Pro review does not just endorse our plan. It raises the bar:

1. The first engineering target is not "smart browser automation".
2. The first target is state correctness: provider lane state, artifact finality state, and failure taxonomy.
3. The second target is replayability: action ledger and replay bundles around existing deterministic scripts.
4. Only then should we add adaptive recovery.
5. Free-form browser agents should stay in sandbox/offline tooling unless future evidence proves they are safe.

## Recommended Next Engineering Tasks

1. Implement provider-lane state and failure taxonomy around the existing worker/job model.
2. Wrap current deterministic browser scripts with a minimal action ledger and replay bundle.
3. Build finality reconciler and artifact repair path for visible-answer/export/raw-render mismatch.

These should happen before Stagehand/browser-use/AgentQL-style integrations.

