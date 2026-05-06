# 2026-03-20 Session Truth Decision Verification Walkthrough v1

## What I checked

This verification re-audited:

- [2026-03-20_session_truth_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v1.md)

I focused on five questions:

1. Is `state/agent_sessions` really the durable owner for `/v3/agent/*` session APIs?
2. Is `jobdb` really execution-correlation truth rather than continuity truth?
3. Did `/v2/advisor/ask` or `/v2/advisor/advise` grow a hidden durable session ledger?
4. Is `~/.openclaw` really the right way to name the channel-native continuity owner?
5. Are there other stateful DBs that look similar but are only derived projections?

## What held up

These parts of the document survived verification:

- the system is better described as layered truth, not as three equal ledgers
- `state/agent_sessions` is the canonical facade-local truth for `/v3/agent/*`
- `jobdb` is the durable execution-correlation ledger
- `/v2/advisor/ask` and `/v2/advisor/advise` are session-aware ingress only
- `state/dashboard_control_plane.sqlite3` should not be counted as a competing ledger because it is a derived read model

That means the document’s core architecture is materially sound.

## What did not hold up cleanly

The remaining problems are both about boundary precision.

### 1. Layer A was written too broadly

The document freezes layer A as literal `~/.openclaw`, and expands that into `OpenClaw / Feishu / DingTalk / agent runtime`.

What the direct code and state evidence actually proves is narrower:

- OpenClaw runtime continuity is upstream
- the active owner is the configured `OPENCLAW_STATE_DIR`
- the current deployment pins that to `/home/yuanhaizhou/.home-codex-official/.openclaw`

I did not find direct current-state evidence in this pass strong enough to keep the full `Feishu / DingTalk` wording as-is.

### 2. `jobdb` does not own artifact payload bytes

The document’s execution layer wording is nearly right, but it slightly blurs two things:

- `jobdb` owns run/work/checkpoint/artifact correlation metadata
- the actual request/result/conversation payload files live under `artifacts/jobs/*`

That distinction matters if later telemetry or recovery work tries to use `jobdb` as if it were the full artifact store.

## Why this matters

This matters because the next proposed document is `telemetry_contract_fix_v1`.

If telemetry is built on top of an imprecise session-truth decision, it will likely:

- emit continuity signals against the wrong owner path
- overstate channel ownership on the OpenClaw layer
- conflate jobdb correlation state with artifact payload storage

## Deliverables

This verification added:

- [2026-03-20_session_truth_decision_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_verification_v1.md)
- [2026-03-20_session_truth_decision_verification_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_verification_walkthrough_v1.md)

## Test Note

This was a documentation and code-evidence verification task. No code was changed, and no test suite was run.
