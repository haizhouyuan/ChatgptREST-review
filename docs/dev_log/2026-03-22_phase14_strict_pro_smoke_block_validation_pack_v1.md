# Phase 14 Strict Pro Smoke Block Validation Pack v1

## Goal

Freeze the repository state where `ChatGPT Pro` and `Gemini Pro` smoke/trivial requests are hard-blocked, even if callers continue to send legacy override flags.

## Scope

- API submission policy:
  - `chatgpt_web.ask`
  - `gemini_web.ask`
- Override resistance:
  - `allow_trivial_pro_prompt`
  - `allow_pro_smoke_test`
- Active documentation surfaces:
  - [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)
  - [docs/contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md)
  - [docs/runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md)
  - [docs/client_projects_registry.md](/vol1/1000/projects/ChatgptREST/docs/client_projects_registry.md)

## Checks

1. `chatgpt_pro_smoke_override_blocked`
   - `purpose=smoke`
   - `preset=pro_extended`
   - `allow_pro_smoke_test=true`
   - expected: `400 pro_smoke_test_blocked`
2. `chatgpt_pro_trivial_override_blocked`
   - trivial prompt
   - `preset=pro_extended`
   - `allow_trivial_pro_prompt=true`
   - expected: `400 trivial_pro_prompt_blocked`
3. `gemini_pro_smoke_override_blocked`
   - `purpose=smoke`
   - `preset=pro`
   - `allow_pro_smoke_test=true`
   - expected: `400 pro_smoke_test_blocked`
4. `active_docs_scrubbed`
   - active docs no longer advertise `allow_trivial_pro_prompt`
   - active docs no longer advertise `allow_pro_smoke_test`

## Implementation

- Validation module:
  - [chatgptrest/eval/pro_smoke_block_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/pro_smoke_block_validation.py)
- Runner:
  - [ops/run_pro_smoke_block_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_pro_smoke_block_validation.py)
- Tests:
  - [tests/test_pro_smoke_block_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_pro_smoke_block_validation.py)

## Acceptance

- Validation runner exits `0`
- Report shows `4/4` checks passed
- Live policy code no longer honors request-level Pro override flags
