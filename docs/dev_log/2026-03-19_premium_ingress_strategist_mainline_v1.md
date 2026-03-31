# 2026-03-19 Premium Ingress Strategist Mainline v1

## What Changed

Completed the missing premium ingress strategist mainline in the public agent
facade and controller path without moving ordinary asks onto `cc-sessiond`.

The new flow is now:

`raw ask -> AskContract -> AskStrategyPlan -> strategist clarify gate -> compiled prompt -> controller execution -> post-review -> richer EvoMap signals`

## Code Changes

- `chatgptrest/advisor/ask_strategist.py`
  - added `AskStrategyPlan`
  - added deterministic strategist synthesis from `AskContract + goal_hint + context`
  - added structured clarify questions, route hints, output contract, evidence
    requirements, uncertainty policy, and review rubric

- `chatgptrest/advisor/prompt_builder.py`
  - added `build_prompt_from_strategy(...)`
  - kept `build_prompt_from_contract(...)` as compatibility wrapper
  - expanded `PromptBuildResult` with:
    - `output_contract`
    - `uncertainty_policy`
    - `evidence_requirements`
    - `review_rubric`
    - `provider_hints`

- `chatgptrest/api/routes_agent_v3.py`
  - strategist plan is now created during `/v3/agent/turn`
  - clarify gate now comes from strategist output instead of raw completeness thresholds
  - clarify responses now persist session state, so same-session clarification can continue
  - `_enrich_message()` now prefers compiled strategist prompt when present
  - EvoMap writeback now emits additional signals for:
    - missing inputs
    - prompt rewrite pressure
    - route/model miss

- `chatgptrest/controller/engine.py`
  - `_build_enriched_question()` now consumes compiled prompt text from
    `stable_context["compiled_prompt"]`
  - this keeps controller route planning on raw ask, while execution uses the
    strategist-compiled prompt body

## Why

Before this change:

- premium ingress only had `AskContract + threshold clarify + template prompt builder`
- clarify responses returned early without durable session continuity
- controller execution still consumed raw free-text semantics

That meant the advertised strategist layer did not really exist yet.

This change keeps the rollout additive and low-risk:

- route planning still uses the raw ask
- compiled prompt semantics only affect the final execution question
- older `build_prompt_from_contract(...)` callers still work

## Behavioral Result

- incomplete high-stakes asks now return strategist-driven clarification
- that clarification is durable in the public session store
- clients can continue the same session with more context
- completed turns still use the same response/review surface
- controller-backed execution now sees compiled prompt structure instead of only raw ask text

## Tests Added

- `tests/test_ask_strategist.py`
- `tests/test_controller_engine_prompt_compile.py`

## Tests Updated

- `tests/test_prompt_builder.py`
- `tests/test_routes_agent_v3.py`
- `tests/test_agent_v3_routes.py`

## Validation

Ran:

```bash
./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py \
  tests/test_agent_v3_routes.py \
  tests/test_agent_mcp.py \
  tests/test_ask_contract.py \
  tests/test_prompt_builder.py \
  tests/test_post_review.py \
  tests/test_ask_strategist.py \
  tests/test_controller_engine_prompt_compile.py
```

Also re-verified adjacent fixes still pass:

```bash
./.venv/bin/pytest -q \
  tests/test_agent_mcp.py \
  tests/test_leases.py::test_cancel_wait_phase_with_active_lease_finalizes_immediately \
  tests/test_leases.py::test_cancel_wait_phase_with_expired_lease_finalizes_immediately \
  tests/test_cleanup_cc_sessiond_pool.py
```

## Residual Notes

- The two preserved historical `cc-sessiond` strategist failures remain as
  evidence records:
  - `04fd194171b4`
  - `21f4e10e869d`
- This change does not attempt to rehabilitate those old runs; it finishes the
  strategist mainline directly in the repository runtime.
