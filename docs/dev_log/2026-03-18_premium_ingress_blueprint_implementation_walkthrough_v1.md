# Premium Ingress Blueprint Implementation Walkthrough v1

Date: 2026-03-18
Branch: `feat/premium-ingress-blueprint-implementation`

## What I Did

Completed the remaining premium ingress blueprint gaps that were identified in the gap review:

### 1. Wired Prompt Builder into Real Execution Path

**File Modified:** `chatgptrest/api/routes_agent_v3.py`

- Added import for `build_prompt_from_contract` from `prompt_builder.py`
- Modified `_enrich_message()` function to use `build_prompt_from_contract` when an AskContract exists in context
- The function now:
  - Retrieves `ask_contract` from context
  - Reconstructs `AskContract` from stored dict
  - Calls `build_prompt_from_contract()` with contract and model provider
  - Uses the built prompt's `user_prompt` instead of just the raw message

**Backward Compatibility:** Preserved. If no contract exists in context, falls back to original message enrichment behavior.

### 2. Added Clarify Gate for Materially Incomplete Premium Asks

**File Modified:** `chatgptrest/api/routes_agent_v3.py`

Added a clarify gate that checks contract completeness before executing expensive premium calls:

- **High-risk asks:** Return clarification if completeness < 60%
- **Medium-risk asks:** Return clarification if completeness < 50%
- **Server-synthesized contracts:** Return clarification if completeness < 40%

When triggered, returns early with:
- Status: `clarification_needed`
- Answer: Specific message listing what's missing
- Review: Generated with quality assessment

### 3. Added EvoMap Writeback for Post-Ask Review Signals

**File Modified:** `chatgptrest/api/routes_agent_v3.py`

Added new function `_write_review_to_evomap()` that:
- Writes structured signals to EventBus for EvoMap persistence
- Emits the following signal types:
  - `premium_ask.review.contract_completeness`
  - `premium_ask.review.question_quality`
  - `premium_ask.review.answer_quality`
  - `premium_ask.review.model_route_fit`
  - `premium_ask.review.hallucination_risk`

Integrated into `_build_agent_response()`:
- Called when review exists in payload
- Called when auto-generated review is created
- Non-fatal failures logged but don't break the request

## Tests Run

All tests passed:

```bash
# Contract/Review tests
pytest -q tests/test_ask_contract.py tests/test_prompt_builder.py tests/test_post_review.py
# Result: 25 tests passed

# Route tests
pytest -q tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py tests/test_agent_mcp.py
# Result: 24 tests passed

# Additional acceptance tests
pytest -q tests/test_openclaw_cognitive_plugins.py tests/test_bi14_fault_handling.py
# Result: 24 tests passed
```

## What Remains Intentionally Deferred

Per the blueprint, the following are intentionally deferred to future iterations:

1. **Heavy LLM Judge Integration:** The current review is heuristic-only. Full LLM-based quality evaluation can be added later.
2. **Heavy Funnel Integration:** The current clarify gate is lightweight. Full funnel with ProjectCard generation can be added later.
3. **cc-sessiond Execution Cabin:** The full execution cabin capabilities (profile/MCP pack/skill pack/topology) are out of scope for this iteration.

## Git Commit

```
0982598 feat(premium-ingress): wire prompt-builder, add clarify gate, add EvoMap writeback
```

## Changed Files

- `chatgptrest/api/routes_agent_v3.py` - Main implementation

## Notes

- Backward compatibility preserved for clients that only send `message`
- Clarify gate only triggers on materially incomplete contracts
- EvoMap writeback is non-fatal (fails gracefully if EventBus unavailable)
- All existing tests pass with no regressions
