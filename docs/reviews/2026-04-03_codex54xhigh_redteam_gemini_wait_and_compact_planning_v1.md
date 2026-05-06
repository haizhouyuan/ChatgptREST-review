# 2026-04-03 Codex 5.4-xhigh Redteam Gemini Wait And Compact Planning v1

## 1. Scope

This redteam review covers the staged batch around:

1. Gemini wait thread hardening
2. Gemini Drive picker resilience
3. compact `implementation_plan` scenario-pack routing
4. matching tests and execution reviews

## 2. Redteam Findings

### 2.1 Medium: same-session repair is still a bounded local retry, not an independent reopen mechanism

The new wait path adds one more controlled repair attempt after the loop-level reopen budget is exhausted.

That is useful and justified, but it should still be described as:

- a bounded local repair attempt
- still anchored to the requested concrete thread
- still fail-closed on mismatch

It should **not** be described as a separate session-level reopen mechanism already proven in production.

### 2.2 Medium: Drive picker popup/frame fallback is still heuristic

The current code now accepts popup-page and attached-frame fallback paths and exposes better picker debug, which is a real improvement.

But the redteam review notes that this still does not prove the chosen scope is always the currently interactive picker instance in live UI drift scenarios.

### 2.3 Medium: compact implementation-plan routing is locally proven, not live-proven end-to-end

The scenario-pack branch and tests prove:

1. route selection changes
2. provider hints change
3. acceptance contract changes

They do **not** yet prove that the live serialized provider request always reflects the compact path in real planning runs.

### 2.4 Low: Gemini login/error classification remains heuristic

`GeminiNotLoggedIn` classification is narrower than before and no longer treats generic `accounts.google.com` hops as automatic login failure.

That is better than the previous behavior, but it remains text-heuristic classification and should still be treated as a bounded helper, not a source of truth.

## 3. Redteam Verdict

The redteam verdict for this batch is:

> approve-with-fixes

There is no new hard blocker preventing commit, provided the documentation mouthpiece stays narrow and does not overclaim:

1. live thread persistence solved
2. compact planning path live-proven
3. transport timeout semantics broadly solved

## 4. My Independent Judgment

I accept the main tightening from the redteam review:

1. same-session repair should be described as one more bounded local repair layer
2. Drive picker fallback remains a residual risk, not a solved problem
3. compact implementation planning remains locally proven but not live-proven

I do **not** read the review as a reason to block this commit, because:

1. the batch remains fail-closed
2. focused tests pass
3. the staged docs already avoid claiming live green proof

## 5. One-Line Conclusion

> This batch is acceptable to commit if it is described as local hardening plus narrower planning routing, not as proof that live Gemini persistence or compact planning serialization is fully solved.
