# 2026-04-03 Planning Agent Total Plan Execution Master v28

## 1. v28 Current Mouthpiece

`v28` freezes the state after the latest compact-normalization and Gemini-wait-budget tightening batch.

The correct current mouthpiece is:

1. the compact implementation-plan lane is locally tightened and less permissive
2. the consult regression is closed and explicitly covered by test
3. Gemini wait recovery remains fail-closed and its local retry envelope is now explicit
4. the remaining front blocker is still live Gemini thread persistence, not local compact-routing logic

## 2. What Became Stronger In v28

1. compact normalization now trusts runtime scenario-pack selection, not caller-provided context flags
2. consult path regression coverage is now explicit
3. retry-budget semantics are tighter in tests and less likely to drift silently
4. the full unfinished-work implementation plan is now frozen in `planning_agent_full_unfinished_implementation_plan_v4`

## 3. What Is Still Not True

1. `OpenClawBot` live completion is not yet newly proven green in this batch
2. full planning task coverage is not yet complete
3. OpenClawBot material-intake automation is not yet complete
4. harness and EvoMap remain later work packages, not current completed capability

## 4. Immediate Priority Order

### P0
1. finish a fresh live-completion evidence run
2. keep W1 focused on Gemini live thread persistence until green

### P1
1. expand task truth layer from narrow slices to the remaining planning P0 task families
2. move OpenClawBot from text-first dispatch to usable material intake with fail-closed preflight

### P2
1. knowledge freshness/promotion/writeback closure
2. policy-layer hardening without re-inflating `publicagentmcp`
3. harness and EvoMap rollout

## 5. One-Line Conclusion

> `v28` should now be read as: the latest local hardening batch is approved, the full remaining-work plan is frozen, and the live Gemini persistence blocker is still the front line until new evidence overturns it.
