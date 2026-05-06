# ChatgptREST Call Pro Wait Skill Update v1

Date: 2026-04-27

## Scope

This note records the caller-side follow-up to:

- `docs/dev_log/2026-04-27_pro_thinking_fast_answer_partial_finality_rca_v1.md`
- commit `89cc0eea` (`Fail closed on in-progress Pro exports`)

The triggering incident was Codex session `019dc032-6429-7bd3-821f-c4d53d0c5a37` and its ChatGPT Pro job chain:

- `fce0398f3ec847b194e4cc89fe9cf3ef`
- `d6bfdc79dae94a1aaa4faf5a654a7243`
- `06a8a546d4f0451c804b6e02a5043bd6`
- `076c4a2b073b495d87bb93a7d097b12a`

## Finding

The server-side RCA found a finality bug: Pro/thinking jobs could be marked complete from DOM text even while the backend export still showed the matched assistant turn as `in_progress`.

The caller-side review found an additional gap in `skills-src/chatgptrest-call`:

1. The skill text already said substantial ChatGPT Pro answers should be treated as asynchronous human-scale work.
2. The wrapper default still used the generic agent budget of 300 seconds when the caller did not pass `--job-timeout-seconds`.
3. That mismatch encourages exactly the wrong behavior for Pro review: short foreground expectations, tight polling, and corrective follow-ups before the previous turn is genuinely final.

This is not the root cause of the server bug fixed in `89cc0eea`, but it is a systemic contributing factor. A client wrapper that documents long Pro waits while defaulting to a five-minute budget leaves too much room for future agents to repeat the same operational mistake.

## Root Cause

The system had inconsistent contracts across layers:

- Server finality had to fail closed on incomplete backend exports.
- Client skills had to teach agents to wait on the same job/conversation instead of reacting to early visible text.
- The wrapper had to encode the same expectation as defaults, not only as prose.

Only the first part had been fixed before this update.

## Change

`skills-src/chatgptrest-call/scripts/chatgptrest_call.py` now uses longer defaults when the caller does not explicitly set a job budget:

- `provider=chatgpt` + Pro preset: 3600 seconds.
- `provider=chatgpt` + Pro preset + `--deep-research`: 7200 seconds.
- Non-Pro/default agent calls remain at 300 seconds.

The skill documentation now explicitly says:

- Browser-visible Pro thinking is not model-selection evidence; backend/export metadata is.
- `status=completed` alone is not external-review evidence.
- Prompt echo, stale DOM text, truncated output, and shallow generic output must be treated as quality/finality problems.
- Do not send short-interval corrective follow-ups while the same Pro job is still awaiting assistant answer or showing retry/finality downgrade events.

## Tests

Added/updated skill wrapper coverage to assert:

- ChatGPT Pro agent-mode submits use the long Pro default budget.
- ChatGPT Pro Deep Research uses the longer default budget.
- Non-Pro agent-mode calls keep the existing 300-second default.

## Operational Rule

For high-value Pro review, the correct client behavior is:

1. Submit once with a durable idempotency key and enough budget.
2. Return the receipt to the front agent.
3. Continue local work.
4. Check status/events only at low frequency or on push.
5. Send a same-thread follow-up only after the prior answer is final and the remaining issue is answer quality, not generation latency.

This rule is now reflected in both server behavior and the reusable `chatgptrest-call` skill.
