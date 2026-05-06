# Premium Ingress Blueprint cc-sessiond Task Spec v2

Repo:
- `/vol1/1000/worktrees/chatgptrest-premium-ingress-20260318`

Branch:
- `feat/premium-ingress-blueprint-implementation`

## Goal

Complete the remaining premium ingress blueprint gaps. Do not treat the current branch as finished.

Read first:

1. `AGENTS.md`
2. `/vol1/1000/projects/ChatgptREST/docs/2026-03-17_premium_agent_ingress_and_execution_cabin_blueprint_v1.md`
3. `/vol1/1000/worktrees/chatgptrest-premium-ingress-20260318/docs/dev_log/2026-03-18_premium_ingress_blueprint_gap_review_v1.md`
4. `/vol1/1000/worktrees/chatgptrest-premium-ingress-20260318/docs/dev_log/2026-03-18_premium_ingress_blueprint_acceptance_todo_v1.md`

## Non-goals

- Do not merge.
- Do not rewrite the whole agent facade.
- Do not remove backward compatibility for clients that only send `message`.

## Required outcomes

### A. Real prompt-builder integration

Wire `chatgptrest/advisor/prompt_builder.py` into the actual `/v3/agent/turn` execution path.

Success bar:

- `AskContract` influences the final prompt actually sent downstream.
- The resulting behavior is visible through code inspection and direct tests.

### B. Real clarify gate

Implement a high-cost clarify gate before execution for materially incomplete contracts.

Success bar:

- Define contract completeness / missing-info thresholds.
- When the request is too incomplete for a premium ask, return an explicit clarification response instead of burning the ask.
- Document the compatibility behavior for existing callers.

### C. EvoMap writeback

Persist post-ask review signals into existing EvoMap or QA feedback infrastructure.

Success bar:

- Review writeback happens on successful answer generation.
- Failure to write back is non-fatal but observable.
- Add direct tests for success and safe-fallback behavior.

### D. Walkthrough

Add a versioned implementation walkthrough with `_v1.md` suffix.

## Testing requirements

Run at minimum:

- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py tests/test_agent_mcp.py tests/test_openclaw_cognitive_plugins.py tests/test_bi14_fault_handling.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_ask_contract.py tests/test_prompt_builder.py tests/test_post_review.py`

Add and run any missing tests needed to prove:

- prompt builder is in the real execution path
- clarify gate works
- EvoMap writeback works or degrades safely

## Git discipline

- Commit every meaningful slice.
- Do not overwrite previous docs; create new versioned files only.
- Run closeout before finishing.

## Final output

Return JSON only:

```json
{
  "status": "succeeded" | "blocked" | "failed",
  "branch": "feat/premium-ingress-blueprint-implementation",
  "summary": "short summary",
  "commits": ["sha subject", "..."],
  "tests": [
    {"command": "pytest ...", "status": "passed|failed|not_run", "details": "short note"}
  ],
  "walkthrough_path": "absolute path or empty string",
  "changed_files": ["path", "..."],
  "residual_risks": ["...", "..."],
  "notes": ["...", "..."]
}
```
