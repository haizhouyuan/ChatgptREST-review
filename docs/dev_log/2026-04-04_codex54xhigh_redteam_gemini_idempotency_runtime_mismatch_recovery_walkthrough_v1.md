# 2026-04-04 Codex 5.4 xhigh Redteam Gemini Idempotency Runtime Mismatch Recovery Walkthrough v1

## Red-team sequence

1. sent the first version of the batch for red-team review
2. received a `reject` verdict on two high-risk regressions
3. accepted both highs as real
4. reverted the Gemini wait broadening
5. redesigned the idempotency change around runtime mismatch
6. expanded tests for same-runtime, non-`chatgptrest:`, and legacy-schema cases
7. sent the narrowed batch back through `gpt-5.4 xhigh` review
8. treated the final red-team state as `approve-with-fixes`

## What mattered most

The valuable red-team contribution in this batch was not stylistic review; it changed the implementation direction.

Without the first rejection, this batch would have committed an unsafe recovery rule that could duplicate same-process queued sends and an over-broad Gemini wait downgrade. The final committed design is narrower because of that red-team intervention.
