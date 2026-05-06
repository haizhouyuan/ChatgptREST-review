# Premium Ingress Strategist Task Spec v1

## Mission

Upgrade the premium agent ingress from:

- contract heuristics
- template rendering

to:

- strategist-driven intent understanding
- clarify-first gating
- compiled prompts on the real execution path
- richer review writeback

This is not a cosmetic prompt refactor.


## Read First

1. `/vol1/1000/projects/ChatgptREST/AGENTS.md`
2. `/vol1/1000/projects/ChatgptREST/docs/2026-03-17_premium_agent_ingress_and_execution_cabin_blueprint_v1.md`
3. `/vol1/1000/projects/ChatgptREST/docs/2026-03-18_premium_agent_ingress_and_execution_cabin_blueprint_v2.md`
4. `/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-18_premium_ingress_blueprint_implementation_walkthrough_v1.md`


## Hard Requirements

- Do not move ordinary premium asks onto `cc-sessiond`.
- Do not make Codex the default backend for public agent ingress.
- Keep public MCP surface minimal.
- Preserve OpenClaw public-agent compatibility.
- Additive rollout only; use feature flags.


## Batch A: Strategist Layer

Implement:

- `chatgptrest/advisor/ask_strategist.py`
- `AskStrategyPlan`

Behavior:

- take raw message + context + goal hint + files
- decide whether the ask is worth premium execution
- produce a structured plan
- explicitly decide clarify vs execute
- choose route/provider/model family/rubric

This layer may use LLM reasoning.


## Batch B: Clarify Gate

Replace threshold-only clarify logic in `routes_agent_v3.py` with strategist-driven logic.

Required output:

- `clarify_required`
- `clarify_reason`
- `clarify_questions`
- `recommended_reask_template`

Continuation requirement:

- same session can continue after clarification


## Batch C: Prompt Compiler

Upgrade `chatgptrest/advisor/prompt_builder.py` so it compiles from `AskStrategyPlan`.

Required outputs:

- `system_prompt`
- `user_prompt`
- `output_contract`
- `uncertainty_policy`
- `evidence_requirements`
- `review_rubric`
- provider-specific hints


## Batch D: Real Execution Path Cutover

The controller path must consume compiled prompts, not raw free-text semantics.

That means:

- direct routes and controller route must both start from the same strategist output
- the current split behavior is not acceptable as final state


## Batch E: Review + EvoMap

Keep the existing fast review.

Add:

- richer premium review signals
- optional heavy-review escalation hooks
- writeback for prompt rewrite / model-route miss / missing-input patterns


## Tests To Add

- strategist synthesis tests
- clarify gate tests
- compiled prompt path tests
- controller-path compiled prompt tests
- same-session clarify/resume tests
- EvoMap writeback tests


## Minimum Tests To Run

```bash
./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py \
  tests/test_agent_v3_routes.py \
  tests/test_agent_mcp.py

./.venv/bin/pytest -q \
  tests/test_ask_contract.py \
  tests/test_prompt_builder.py \
  tests/test_post_review.py
```

Plus any new strategist / clarify / EvoMap tests you add.


## Deliverables

- code changes
- tests
- one new walkthrough doc with `_v1.md`
- final JSON status summary


## Done Means

Do not report success unless:

- strategist exists
- clarify is strategist-driven
- prompt compiler is on real execution path
- controller path no longer bypasses compiled prompt semantics
- EvoMap writeback is richer than the current heuristic-only path
