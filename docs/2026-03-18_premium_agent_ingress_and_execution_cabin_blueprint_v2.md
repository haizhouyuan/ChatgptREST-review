# Premium Agent Ingress And Execution Cabin Blueprint v2

## 1. Core Positioning

`public /v3/agent/*` should not be treated as a fast chat endpoint.

It should be treated as a **premium deliberation ingress** for high-cost asks:

- the user only asks when the opportunity cost is real
- the system should first understand whether the question is worth asking
- the system should decide how to ask it well
- only then should it spend a premium model invocation

`cc-sessiond` remains the **execution cabin** for slow-path work:

- long-running development
- multi-agent collaboration
- debate / planner-reviewer-implementer loops
- heavy execution with durable continuation

It must not become the default backend for ordinary premium asks.


## 2. Problem Statement

The current premium ingress still has a structural gap:

- `AskContract` exists, but is mostly schema + heuristic synthesis
- `prompt_builder` exists, but is mostly template rendering
- `post_review` exists, but is still lightweight heuristic review
- `public /v3/agent/turn` still lets the controller path consume raw user message semantics

This means the system can format a prompt, but it still cannot reliably answer:

- What is the user really trying to decide?
- Is this ask worth a premium invocation?
- Is the current information sufficient?
- Which route / provider / model mix is most appropriate?
- Should the system clarify instead of execute?

That is the missing layer.


## 3. Architecture Target

The target chain is:

`raw ask -> strategist -> structured contract -> clarify gate -> prompt compiler -> execution -> post-ask review -> EvoMap`

Responsibilities:

- **Strategist**
  - understand the ask
  - normalize or synthesize the real task
  - decide whether to clarify
  - choose route / provider / evaluation rubric
- **Prompt Compiler**
  - compile a provider-specific prompt from the strategy plan
  - do not decide intent
- **Execution**
  - route to ChatGPT / Gemini / consult / image
  - do not redo ask strategy
- **Post-Ask Review**
  - judge question quality, route quality, model fit, answer quality
  - write feedback into EvoMap


## 4. New Core Primitive: AskStrategyPlan

Introduce a new server-side planning artifact:

`AskStrategyPlan`

Minimum fields:

- `strategy_id`
- `contract`
- `clarify_required`
- `clarify_questions`
- `clarify_reason`
- `recommended_route`
- `recommended_provider`
- `recommended_model_family`
- `recommended_prompt_style`
- `recommended_output_rubric`
- `required_evidence_level`
- `worth_it`
- `worth_it_reason`
- `risk_class`
- `opportunity_cost`
- `missing_information`
- `strategy_confidence`

The existing `AskContract` becomes a nested part of this plan, not the whole plan.


## 5. Strategist Layer

### 5.1 What it does

The strategist is the first real decision-maker.

Input:

- raw user message
- client context
- file list
- goal hint
- session identity

Output:

- `AskStrategyPlan`

### 5.2 What it must decide

- Is this a real premium ask or a badly formed one?
- Is the request actionable with current inputs?
- Should the system ask follow-up questions first?
- Which task template applies?
- Which route is best?
- Which provider or provider combination is best?
- What rubric should judge the answer afterward?

### 5.3 Implementation rule

This layer should be allowed to use LLM reasoning.

Do not reduce it to pure heuristics.

For premium ingress, a small upfront planning cost is acceptable because it avoids wasting a much more expensive downstream invocation on a bad question.

### 5.4 Initial policy

- low-risk and well-formed asks may use a cheaper strategist path
- medium/high-risk asks should use a stronger strategist path
- strategist must be configurable behind feature flags


## 6. Clarify Gate

The clarify gate should no longer rely only on simple completeness thresholds.

It should block execution when:

- the ask is not worth a premium call
- the decision to support is unclear
- the available inputs are materially insufficient
- the output shape is under-specified
- the intended route would likely underperform without clarification

Clarify responses should return:

- `clarify_required = true`
- `clarify_reason`
- `clarify_questions`
- `recommended_reask_template`
- partial `contract`

Session continuity requirement:

- clarification must stay inside the same agent session
- the follow-up should resume the same strategy thread


## 7. Prompt Compiler

### 7.1 What stays

Keep `chatgptrest/advisor/prompt_builder.py`.

### 7.2 What changes

Its role changes from “prompt optimizer” to “prompt compiler”.

It should accept `AskStrategyPlan`, not just a raw contract.

### 7.3 Output

For each provider route, compile:

- `system_prompt`
- `user_prompt`
- `output_contract`
- `uncertainty_policy`
- `evidence_requirements`
- `review_rubric`
- `provider_hints`

### 7.4 Hard requirement

The controller-backed path must also consume compiled prompts.

The system is not complete while the direct routes use compiled prompts but the controller path still consumes raw message semantics.


## 8. Execution Layer

Default premium ingress execution remains LLM-backed:

- `chatgpt_web.ask`
- `gemini_web.ask`
- `consult`
- `gemini_web.generate_image`

Not default:

- `cc-sessiond`
- `cc_executor`
- Codex repair lanes

These only appear when the request is explicitly a slow-path execution-cabin task.


## 9. Scenario Packs

The strategist must select from scenario packs rather than treating all asks as generic.

Initial packs:

- `decision_support`
- `deep_research`
- `code_review`
- `implementation_planning`
- `stakeholder_communication`
- `image_generation`

Each pack should define:

- minimum ask checklist
- contract minimums
- preferred route
- fallback route
- output rubric
- post-review rubric


## 10. Post-Ask Review

Keep two layers:

- **fast review**
  - existing `post_review.py`
  - always-on heuristic review
- **heavy review**
  - `qa_inspector.py`
  - only for high-stakes or suspicious answers

The review layer must answer:

- Was the question well-formed?
- Was the route correct?
- Was the model/provider fit correct?
- Was the answer actually useful?
- If not, should the question be rewritten, rerouted, or both?


## 11. EvoMap Writeback

EvoMap should receive structured premium-ingress learning signals, not just route counters.

New signal families:

- `premium_ask.review.question_quality`
- `premium_ask.review.contract_completeness`
- `premium_ask.review.model_route_fit`
- `premium_ask.review.answer_quality`
- `premium_ask.review.hallucination_risk`
- `premium_ask.review.prompt_rewrite_hint`
- `premium_ask.review.template_gap`
- `premium_ask.review.missing_input_pattern`

Heavy-review outputs should write richer knowledge atoms for future routing and prompt strategy.


## 12. Reuse of Legacy Funnel

Do not restore the old funnel state machine as the literal public ingress path.

Reuse these assets from `chatgptrest/workflows/funnel.py`:

- ambiguity detection
- request-type classification ideas
- stage/rubric concepts
- gating vocabulary

But keep the new ingress chain lightweight and session-first.


## 13. Feature Flags

Additive rollout only.

Required flags:

- `CHATGPTREST_PREMIUM_STRATEGIST_ENABLED`
- `CHATGPTREST_PREMIUM_CLARIFY_GATE_ENABLED`
- `CHATGPTREST_PREMIUM_PROMPT_COMPILER_ENABLED`
- `CHATGPTREST_PREMIUM_HEAVY_POST_REVIEW_ENABLED`

Rollout order:

1. strategist planning on, clarify off
2. clarify for high-risk only
3. compiled prompt on direct routes
4. compiled prompt on controller path
5. heavy review for selected classes


## 14. Concrete Implementation Plan

### Phase A: Strategist foundation

- add `chatgptrest/advisor/ask_strategist.py`
- define `AskStrategyPlan`
- add tests for strategist output

### Phase B: Clarify gate upgrade

- replace threshold-only clarify logic in `routes_agent_v3.py`
- drive clarify from strategist output
- support same-session resume after clarify

### Phase C: Prompt compiler upgrade

- update `prompt_builder.py` to accept strategy plan
- compile provider-specific prompt bundles
- preserve backward compatibility for direct callers

### Phase D: Controller path cutover

- pass compiled prompt into controller execution
- stop using raw message semantics as the effective ask payload
- ensure direct routes and controller routes share the same planning source

### Phase E: Post-review closure

- keep fast review always on
- add heavy-review escalation policy
- write richer premium signals into EvoMap


## 15. Test Plan

### Unit

- strategist synthesis
- clarify decision logic
- prompt compiler output
- route selection policy
- post-review outputs

### Integration

- `/v3/agent/turn` clarify flow
- `/v3/agent/turn` compiled prompt flow
- deferred + stream behavior
- same-session clarification resume
- EvoMap writeback

### Business scenarios

- code review
- deep research
- dual review
- stakeholder rewrite
- implementation planning
- image generation

### Regression guarantees

- public agent facade still does not default to `cc-sessiond`
- OpenClaw still uses public agent facade
- public MCP surface remains minimal


## 16. Non-Goals

This blueprint does not make `cc-sessiond` the default public ask backend.

It also does not move ordinary premium asks onto Codex or Claude execution-cabin paths.

`cc-sessiond` remains the slow-path execution cabin for:

- long-running development
- multi-agent debate
- durable orchestration
- profile / MCP pack / skill pack controlled runs


## 17. Definition of Done

This blueprint is complete only when:

- strategist exists and is LLM-capable
- clarify gate is strategist-driven
- prompt compiler is used on both direct and controller paths
- post-ask review writes actionable signals to EvoMap
- same-session clarify/resume works
- regression tests prove premium asks still stay on LLM default paths
