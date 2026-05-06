# Residual Gap And Risk Note V2

Date: 2026-04-08

Supersedes:

- [Residual Gap And Risk Note V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_residual_gap_and_risk_note_v1.md)

## 1. Public-lane ambiguity still exists at the lifecycle level

Current fact:

- both `advisor_agent_*` and `coding_agent_*` exist on the public agent transport

What is resolved:

- `coding_agent_*` is now the narrow default lane for mature coding agents

What is not yet frozen:

- whether `advisor_agent_*` is long-term compatibility, temporary compatibility, or a separate broad product surface

Risk:

- future contributors could regrow ambiguity around which lane is truly default

## 2. The unified gate pack is still stronger on contract proof than on live finality proof

Current fact:

- the gate pack is green
- the pack verifies contract, scan, and maintenance behavior well

What remains:

- one harder live Deep Research finality gate

Risk:

- people may overread a green gate pack as full live finality proof for all research states

## 3. `scope_project` backfill is prepared but not yet approved for live execution

Current fact:

- audit tooling exists
- backfill tooling exists

What remains:

- explicit rerun and approval decision for live write-back

Risk:

- someone may mistake “script exists” for “safe to run on the live DB”

## 4. Promotion is observable but root cause is still not fully diagnosed

Current fact:

- inventory and refresh-only maintenance are now real

What remains:

- a diagnosis that identifies why low active coverage persists

Risk:

- teams may jump into threshold tuning or throughput work before the real cause is known

## 5. Corrected fact boundary

The following are **not** current residual gaps anymore:

- `engine.py` missing completion-contract logic
- `advisor_agent_status/wait` completely missing contract projection

Those claims were true earlier in the history, but they are no longer the correct diagnosis for the current HEAD.
