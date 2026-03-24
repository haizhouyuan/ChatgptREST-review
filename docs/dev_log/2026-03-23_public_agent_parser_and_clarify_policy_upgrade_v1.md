## Summary

This change upgrades the public agent control plane in three connected areas:

1. message-only ingress now has a lightweight labeled contract parser
2. clarify responses now return machine-readable diagnostics
3. `thinking_heavy` becomes an explicit clarify-policy input instead of only changing route selection

The goal is to move the public northbound surface closer to contract-first task submission without requiring every caller to immediately switch to fully structured `task_intake`.

## What Changed

### 1. Lightweight message contract parser

Added [`message_contract_parser.py`](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/message_contract_parser.py).

It extracts labeled fields from natural-language requests, including English and Chinese labels such as:

- `Task:` / `任务:`
- `Decision to support:` / `决策目的:`
- `Audience:` / `受众:`
- `Constraints:` / `约束:`
- `Available inputs:` / `已有输入:`
- `Missing inputs:` / `缺失信息:`
- `Output shape:` / `输出形式:`

The parser is intentionally shallow. Explicit request fields still win. This parser is only a fallback for message-first callers.

### 2. Canonical `task_intake` now consumes parser output

[`build_task_intake_spec(...)`](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_intake.py) now:

- parses the incoming message
- fills missing `objective`
- fills missing `decision_to_support`
- fills missing `audience`
- fills missing `constraints`
- fills missing `available_inputs`
- fills missing `missing_inputs`
- records parser metadata in `task_intake.context.message_contract_parser`

This keeps the canonical intake object as the first-class state holder.

### 3. `AskContract` synthesis uses parser output

[`normalize_ask_contract(...)`](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_contract.py) and its synthesis path now:

- prefer parser-derived `objective`
- backfill missing contract fields from the parsed message
- mark `contract_source="message_parser"` when the parser is the effective fallback source

This is still lower priority than explicit `task_intake` / `contract`.

### 4. Clarify gate is more explicitly execution-profile aware

[`build_strategy_plan(...)`](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py) now carries:

- `clarify_reason_code`

The clarify gate now has an explicit fast path:

- if `execution_profile == "thinking_heavy"`
- and route is `analysis_heavy`
- and risk is not `high`
- and `objective + decision_to_support + audience` are all present

then the ask can execute instead of being forced back into clarify just because completeness is only mid-level.

Deep-research and research-report policies stay stricter.

### 5. Clarify responses now include machine-readable diagnostics

[`routes_agent_v3.py`](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py) now emits richer `clarify_diagnostics`:

- `missing_fields`
- `contract_completeness`
- `clarify_gate_reason`
- `clarify_reason_detail`
- `recommended_contract_patch`
- `recommended_resubmit_payload`

This is designed so coding agents can repair and resubmit instead of guessing from prose-only questions.

## Why This Matters

Before this change:

- message-only asks were mostly treated as one large `objective`
- `thinking_heavy` changed route but not enough clarify behavior
- clarify was only partially machine-readable

After this change:

- message-first callers can still recover some structure
- `thinking_heavy` behaves more like a fast premium analysis lane
- clarify output is much easier for Codex / Claude Code / Antigravity to consume programmatically

## Remaining Gaps

This does **not** finish the full contract-first upgrade. Remaining items include:

- exposing machine-readable `task_intake` more broadly on the public surface
- same-session `contract_patch` usage patterns across all client wrappers
- northbound `acceptance / evidence / observability`
- a larger validation pack for parser fallback and clarify-resubmit loops

## Verification

Passed:

```bash
python3 -m py_compile \
  chatgptrest/advisor/message_contract_parser.py \
  chatgptrest/advisor/task_intake.py \
  chatgptrest/advisor/ask_contract.py \
  chatgptrest/advisor/ask_strategist.py \
  chatgptrest/api/routes_agent_v3.py \
  tests/test_task_intake.py \
  tests/test_ask_strategist.py \
  tests/test_routes_agent_v3.py

./.venv/bin/pytest -q \
  tests/test_task_intake.py \
  tests/test_ask_strategist.py \
  tests/test_routes_agent_v3.py
```
