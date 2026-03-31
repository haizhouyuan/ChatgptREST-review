# Premium Ingress Blueprint Gap Review v1

Date: 2026-03-18
Branch: `feat/premium-ingress-blueprint-implementation`

## Current state

Round 1 implementation landed these commits:

- `6b4a098 feat(premium-ingress): add ask contract funnel front gate`
- `1ea422d test: add tests for ask contract, prompt builder, and post-review`

The branch now contains:

- `chatgptrest/advisor/ask_contract.py`
- `chatgptrest/advisor/prompt_builder.py`
- `chatgptrest/advisor/post_review.py`
- route integration in `chatgptrest/api/routes_agent_v3.py`
- unit tests for the new modules

## What is complete

1. Ask contract schema exists and is normalized from either explicit contract fields or free-text message.
2. `/v3/agent/turn` stores contract metadata in request context and returns contract metadata in the response.
3. A lightweight post-ask review is generated and returned in the response payload.
4. Backward compatibility is preserved for clients that only send `message`.

## Remaining blueprint gaps

### 1. Prompt builder is not on the real execution path

`prompt_builder.py` exists, but `/v3/agent/turn` does not actually use it to assemble the final prompt that reaches controller or downstream execution substrates.

Required completion bar:

- `build_prompt_from_contract()` must materially influence the executed request.
- There must be a clear, testable data path from `AskContract` to the final prompt/message submitted downstream.

### 2. Funnel is only a synthesis step, not a true clarify gate

The current route synthesizes a contract, but it does not stop high-cost execution when critical information is missing.

Required completion bar:

- Define a minimum contract completeness / missing-info gate for premium asks.
- When the contract is materially incomplete, return an explicit clarification response instead of executing the expensive ask.
- Preserve compatibility for low-risk or explicitly permissive cases.

### 3. Post-ask review is not written back to EvoMap

Review generation currently stops at response payload creation.

Required completion bar:

- Write post-ask review signals into the existing EvoMap / QA feedback path.
- Fail closed or degrade safely if EvoMap is unavailable.
- Add direct tests for writeback behavior or the non-fatal fallback path.

### 4. Review remains heuristic-only and is not integrated with heavier quality paths

The current review is useful as a lightweight signal, but it does not yet interact with the existing quality feedback infrastructure beyond local generation.

Required completion bar:

- At minimum, integrate heuristic review with persistent quality feedback writeback.
- It is acceptable to defer heavy LLM judge work if the persistence and routing semantics are correct.

### 5. Implementation walkthrough is missing

The first round returned an empty `walkthrough_path`.

Required completion bar:

- Add a versioned walkthrough doc describing what changed, what remains intentionally deferred, and which tests were run.

## Merge recommendation

Do not merge this branch yet as “full premium ingress blueprint”.

It may only be merged after:

1. prompt builder is wired into real execution
2. clarify gate is real
3. EvoMap writeback exists
4. walkthrough is added
5. acceptance regression passes
