# 2026-03-24 Public Agent Deliberation And Maint Unification Gemini Text Review Packet v1

## Task

Review the current `Public Agent deliberation + maintenance unification` blueprint set and the current repo state.

Deliver:

1. findings first, ordered by severity
2. architecture verdict
3. open risks / assumptions
4. recommended changes

Be strict. Do not be agreeable by default.

## Review Target

This packet compresses the intended review target for:

- `docs/dev_log/2026-03-24_public_agent_deliberation_and_maint_unification_blueprint_v1.md`
- `docs/dev_log/2026-03-24_public_agent_deliberation_and_maint_unification_plan_v1.md`
- `docs/dev_log/2026-03-24_public_agent_deliberation_and_maint_unification_walkthrough_v1.md`

Mirror source commit:

- `d84fe718e1478c59324e753a3637ed87b304d1fc`

## Intended Architecture Direction

The blueprint direction is:

1. `Public Agent` remains the only general northbound entry for external agents and clients.
2. `deliberation` should become an internal advanced reasoning plane under `Public Agent`, not a parallel public review controller.
3. `Maint Controller` remains separate because it has different privileges, action boundaries, and risk model.
4. `OpenClaw maintagent` should become the maintenance brain holding canonical machine context from `/vol1/maint`.
5. `guardian` should be removed, with deterministic sweep/notify absorbed into `maint_daemon` and judgment/escalation absorbed into `maintagent`.

The same blueprint also proposes MCP-facing capabilities such as:

- `deliberation_start/status/cancel/attach`
- deterministic work-package tools such as:
  - `work_package_prepare`
  - `work_package_validate`
  - `work_package_compile_channel`
  - `work_package_submit`

It also proposes:

- `single_review`
- `dual_review`
- `red_blue_debate`

as formal deliberation modes under the Public Agent architecture.

## Current Repo Facts To Evaluate Against

These are the code facts that the review should judge against.

### A. Public Agent MCP is still intentionally minimal

Current public MCP surface remains minimal and centered on:

- `advisor_agent_turn`
- `advisor_agent_status`
- `advisor_agent_cancel`

It is not currently exposing a separate deliberation tool family or deterministic work-package family.

Relevant file:

- `chatgptrest/mcp/agent_mcp.py`

### B. Consult/review is still a separate public surface today

Current FastAPI composition still loads:

- `advisor_v1`
- `consult_v1`
- `advisor_v3`
- `agent_v3`

So review/consult is not yet fully internalized under `agent_v3`.

Relevant file:

- `chatgptrest/api/app.py`

### C. `routes_consult.py` still owns a separate consultation state universe

Current consult router still exposes public consult endpoints:

- `POST /v1/advisor/consult`
- `GET /v1/advisor/consult/{consultation_id}`

And it still uses an in-memory `_consultations` map for consultation state.

Relevant file:

- `chatgptrest/api/routes_consult.py`

### D. `routes_agent_v3.py` still bridges consult/dual review through consult semantics

Current `agent_v3` does not yet have a unified deliberation ledger.
It still maps `goal_hint in {"consult", "dual_review"}` into consult defaults and creates/returns a separate `consultation_id`.

Relevant file:

- `chatgptrest/api/routes_agent_v3.py`

### E. `guardian` is still live and still carries policy/lifecycle behavior

Current topology still includes `guardian` semantics around:

- `wake_agent: main`
- `wake_session: main-guardian`

And the runner still does more than simple patrol/notify. It includes behavior around:

- ChatGPT Pro trivial-prompt checks
- violation filtering
- system-client classification
- guarded agent execution with `repair.check`
- client-issue stale/close sweeps

Relevant files:

- `config/topology.yaml`
- `ops/openclaw_guardian_run.py`

### F. `maintagent` is not yet wired as the real maintenance brain

Current rebuild/OpenClaw configuration still frames `maintagent` more as a watchdog/read-mostly lane for `main`, with minimal tool exposure.

Relevant file:

- `scripts/rebuild_openclaw_openmind_stack.py`

### G. `/vol1/maint` is already shared into current maintenance paths

The canonical machine-context source is directionally correct, but current code already shares `/vol1/maint` through shared maintenance-memory helpers into:

- maint-daemon Codex prompt bootstrap
- SRE lane prompt bootstrap

So `/vol1/maint` is already a shared maintenance substrate, not something uniquely consumed by `maintagent` in current execution.

Relevant file:

- `chatgptrest/ops_shared/maint_memory.py`

### H. Deterministic review/work-package tooling is still CLI/manual and partly fail-open

Current review packaging/sync tooling exists, but it is not yet a server-enforced deterministic compiler plane.

Current facts:

- `ops/code_review_pack.py` is a local CLI packer
- public/review sync still depends on `ops/sync_review_repo.py`
- some workflow validation still warns and asks humans to verify uploads
- Gemini file-count/size checks are not yet fully centralized as a hard server gate

Relevant files:

- `ops/code_review_pack.py`
- `ops/sync_review_repo.py`
- `.agents/workflows/code-review-upload.md`

## Review Questions

Please evaluate the following strictly:

1. Is it architecturally correct to keep `Public Agent` as the only general northbound entry and treat review/deliberation as an internal mode rather than a peer controller?
2. Is `Maint Controller` correctly kept separate?
3. Is removing `guardian` directionally right, or premature for the current repo state?
4. Is `maintagent` currently ready to become the maintenance brain, or is that still aspirational?
5. Is the proposed deterministic work-package plane coherent, or is it currently under-specified relative to the repo state?
6. Are hard channel rules and repo-first/attachment-first semantics correctly defined, or still too fragmented?
7. Is the rollout order safe?

## Expected Strictness

If the blueprint direction is right but the current repo has not actually achieved that unification yet, say that clearly.

If new MCP tool families would contradict the single-entry rule, say that clearly.

If `guardian` still contains live policy semantics that have not yet been remapped, say that clearly.
