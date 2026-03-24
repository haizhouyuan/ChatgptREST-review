# 2026-03-20 Authority Matrix Verification Walkthrough v1

## What I checked

This verification re-audited the authority claims in:

- [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md)

I deliberately re-ran the underlying fact checks instead of trusting the original walkthrough:

1. `systemctl --user is-active` for `openclaw-gateway.service`, `chatgptrest-api.service`, `chatgptrest-mcp.service`, and `chatgptrest-feishu-ws.service`
2. `systemctl --user cat ...` for the same units
3. direct SQLite counts on `state/jobdb.sqlite3`, `data/evomap_knowledge.db`, `~/.home-codex-official/.openmind/*`, and `/tmp/cc-sessions.db`
4. code inspection of:
   - [openmind_paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/openmind_paths.py)
   - [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py)
   - [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
   - [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)
   - [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py)
   - [evomap/paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/paths.py)
   - [openmind-advisor plugin](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
5. `journalctl --user -u openclaw-gateway.service` for telemetry health

## Why the result is partial, not full pass

Most of the document's hard facts did hold up:

- service liveness
- repo-local `jobdb`
- repo-local `artifacts`
- large repo-local `evomap_knowledge.db`
- thin HOME-relative OpenMind stores
- OpenClaw plugin on `/v3/agent/turn`
- Feishu on `/v2/advisor/advise`

The failures were not random factual errors. They were compression errors in the highest-risk rows:

1. the front-door story omitted `/v2/advisor/ask`
2. the EvoMap story omitted the separate HOME-relative signals DB
3. the routing story treated `ModelRouter` as live runtime authority without evidence of runtime injection
4. the session-truth story omitted `state/agent_sessions`

Those four omissions matter because they are exactly the rows that feed the next planned decision docs:

- `knowledge_authority_decision_v1`
- `routing_authority_decision_v1`
- `front_door_contract_v1`
- `session truth` follow-up work

## Why I wrote a separate verification doc instead of editing v1

This repo's doc discipline forbids overwriting prior versions. The right move here was:

1. preserve [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md) unchanged as the original claim set
2. add a separate verification artifact that records what re-checking proved and disproved

That keeps the audit trail intact and makes a later `authority_matrix_v2` easy to justify.

## Deliverables

This verification added:

- [2026-03-20_authority_matrix_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_verification_v1.md)
- [2026-03-20_authority_matrix_verification_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_verification_walkthrough_v1.md)

## Test Note

This was a documentation and evidence-verification task. No code paths were changed, and no test suite was run.
