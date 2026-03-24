# Pro Review: Large .py Split Plan (2026-02-16)

- Pro job: `3f2527901bd14127a7444cedf7811e74`
- Answer: `artifacts/jobs/3f2527901bd14127a7444cedf7811e74/answer.md`
- Conversation export: `artifacts/jobs/3f2527901bd14127a7444cedf7811e74/conversation.json`

## Key takeaways (high signal)
1) Split is feasible, but refactor must be guarded by executable constraints:
- REST contract tests (idempotency, single-flight 409, answer chunking semantics)
- driver tool registry snapshot tests (tool names + args schema)

2) Prevent “hidden double instances” when splitting global state:
- centralize runtime singleton construction for locks/ratelimit/idempotency/state_paths
- enforce strict dependency direction (tools -> providers -> playwright/runtime)

3) Treat side-effectful actions as a distinct layer:
- shadow runs must be read-only (wait/export/parse/verify/self_check)
- never shadow-send prompts

4) Unify error taxonomy + event schema as an audit asset:
- normalize driver errors into stable `status/phase/reason_type/error_type`
- enforce required event fields and evidence refs

5) Auto actions must be fail-closed + rate-limited + audited:
- drain-guard for restarts when send-stage is active
- evidence pack manifest required even when an action is blocked

## Follow-ups
- Plan doc updated: `docs/refactor_large_py_split_plan_20260216.md`
