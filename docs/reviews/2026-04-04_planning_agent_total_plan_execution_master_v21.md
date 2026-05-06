# 2026-04-04 Planning Agent Total Plan Execution Master v21

## 1. v21 compared with v20

`v21` adds one more narrowing result on top of `v20`:

1. MCP HTTP transport no longer replays `deadline exceeded` tool calls through a fresh session by default;
2. same-runtime blank Gemini idempotency reclaim is now tighter and more useful for ChatgptREST-owned keys;
3. the remaining W1 blocker is even more clearly located in Gemini live completion itself.

## 2. Current state at v21

### 2.1 Still standing

These remain true from `v20`:

1. planning task plane continuity proof still stands;
2. query-surface hardening still stands;
3. truthful fail-closed live gate still stands.

### 2.2 Newly added facts

At `v21`, these are additionally established:

1. deadline-bound MCP HTTP failures are no longer doubled by unconditional fresh-session replay;
2. same-runtime Gemini blank in-progress reclaim has an explicit short recovery path;
3. transport-level error text is now specific enough to distinguish timeout from generic empty failure.

### 2.3 Current remaining blockers

`W1` is still blocked by:

1. Gemini live lane still fails to reach completed answer quality under real integrated conditions;
2. current live Gemini jobs can still end up in blank no-thread timeout state;
3. ChatGPT live lane remains verification-blocked;
4. session boundary tightening is still pending.

## 3. Updated judgment

At `v21`, the system has removed another low-value source of latency and ambiguity. The remaining work is not generic transport cleanup anymore; it is the actual Gemini live completion path.

## 4. Next 3 from v21

### 4.1 Next 1

Inspect the real Gemini provider path after the transport replay tightening and find where the no-thread timeout is still occurring.

### 4.2 Next 2

Decide whether the phase-1 stable claim should remain Gemini-based or whether another provider path must take over before phase-1 is declared done.

### 4.3 Next 3

Continue session-boundary tightening and keep plugin-visible surfaces narrower than the raw server session surface.

## 5. One-line conclusion

`v21` means transport replay is less noisy; the remaining W1 problem is the real Gemini completion path itself.
