# 2026-03-20 Session Truth Decision Verification v1

## Scope

Target under verification:

- [2026-03-20_session_truth_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v1.md)

Verification method on `2026-03-20`:

- inspect commit `a5d7ba7`
- re-check the target document against current code and current local state
- verify whether `state/agent_sessions` is really the `/v3/agent/*` durable facade store
- verify whether `state/jobdb.sqlite3` is really execution-correlation truth rather than continuity truth
- verify whether `/v2/advisor/ask` and `/v2/advisor/advise` have any independent durable session ledger
- verify whether `~/.openclaw` was described with the correct scope and path precision

## Verdict

`session_truth_decision_v1` is materially closer to the truth than the earlier “three equal ledgers” framing, but it is still not safe to freeze as the final session-truth contract without tightening one layer.

The core model is correct:

1. `state/agent_sessions` is the durable session ledger for the public `/v3/agent/*` facade.
2. `state/jobdb.sqlite3` is the durable execution-correlation ledger.
3. `/v2/advisor/ask` and `/v2/advisor/advise` are session-aware ingress paths, not independent durable session-ledger owners.

But the OpenClaw layer is still overstated and a little too path-literal:

- the evidence directly proves `OpenClaw runtime state dir` continuity ownership, not a blanket `~/.openclaw = OpenClaw / Feishu / DingTalk / agent runtime` claim
- the active system is configured through `OPENCLAW_STATE_DIR`, and the runbook pins that to `/home/yuanhaizhou/.home-codex-official/.openclaw`

So this document should be treated as `partially verified`, not as the final frozen session-truth contract.

## Confirmed

The following claims in [2026-03-20_session_truth_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v1.md) were confirmed:

1. `state/agent_sessions` is the durable session ledger for the public `/v3/agent/*` facade.
   Evidence: [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L11) defines a file-backed session/event store; [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L25) resolves it relative to `CHATGPTREST_DB_PATH`; [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968) instantiates `AgentSessionStore`; [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L992) persists session state; [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1613), [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1624), and [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1667) expose session/status/stream/cancel APIs on top of it. Current local state also confirms three persisted `.json + .events.jsonl` pairs under `state/agent_sessions`.

2. `state/jobdb.sqlite3` is execution-correlation truth, not continuity truth.
   Evidence: [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L619) makes `controller_runs.run_id` the primary key, not `session_id`; [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L715) and [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L749) define `controller_work_items` and `controller_checkpoints`; [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L771) defines `controller_artifacts`; [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L299) and [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L312) write session identity into a run record, but only as correlated metadata. Current local data also matches the document’s numeric claim: `controller_runs` has `130` rows with `trace_id` and only `55` with non-empty `session_id`.

3. `/v2/advisor/ask` and `/v2/advisor/advise` are session-aware ingress paths, not independent durable session ledgers.
   Evidence: [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L500) and [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1622) only read `session_id` from request bodies and pass it into controller execution; repo search found `AgentSessionStore` only in [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L33) and nowhere in `routes_advisor_v3.py`.

4. `state/dashboard_control_plane.sqlite3` is not a competing session-truth owner.
   Evidence: [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L30) explicitly describes dashboard as read-only and backed by a derived read model; [control_plane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/dashboard/control_plane.py#L525) rebuilds that DB by deleting and re-inserting projection tables. So it is a materialized projection, not a primary session ledger.

## Findings

### 1. The OpenClaw layer is described too broadly and too literally as `~/.openclaw`

The target document freezes layer A as [2026-03-20_session_truth_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v1.md#L24):

- `~/.openclaw`
- responsible for `OpenClaw / Feishu / DingTalk / agent runtime`

The direct evidence collected in this document does not fully support that wording.

- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L194) proves OpenClaw runtime identity is upstream of ChatgptREST.
- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L226) and [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L281) prove that OpenClaw-derived continuity is passed into `/v3/agent/turn`.
- [verify_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/ops/verify_openclaw_openmind_stack.py#L23) and [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L519) show the active state owner is really the configured `OPENCLAW_STATE_DIR`, currently pinned to `/home/yuanhaizhou/.home-codex-official/.openclaw`.
- current live session indexes under `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/*/sessions/sessions.json` exist, but the sampled live provider values are `heartbeat`, not `feishu` or `dingtalk`.
- repo search found Feishu continuity under OpenClaw-related paths like [pipeline.py](/vol1/1000/projects/ChatgptREST/chatgptrest/pipeline.py#L61), but I did not find equivalent direct current-state evidence in this verification pass for DingTalk session continuity.

Impact:

- the layered model is still right, but layer A should be named more precisely
- literal `~/.openclaw` is shorthand, not the real runtime contract
- the current wording over-claims channel coverage beyond the evidence assembled in this document

Required correction:

- rewrite layer A as `OpenClaw runtime state dir (configured by OPENCLAW_STATE_DIR; currently /home/yuanhaizhou/.home-codex-official/.openclaw)`
- scope the ownership claim to `OpenClaw-native continuity` unless separate Feishu/DingTalk evidence is explicitly cited

### 2. `jobdb` is execution-correlation truth, but not the full artifact-content truth

The target document says the execution layer owns job/controller run/work items/checkpoints/artifacts truth in [2026-03-20_session_truth_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v1.md#L32) and [2026-03-20_session_truth_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v1.md#L175).

That is mostly right if `artifacts` means artifact correlation/indexing, but too strong if it means artifact payload bytes/content.

- [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L771) shows `controller_artifacts` stores metadata such as `path`, `uri`, and `metadata_json`.
- [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L36) and [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L108) show the actual job artifact payloads live on disk under `artifacts/jobs/<job_id>/...`.
- [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L243) writes `result.json` to the filesystem, not into `jobdb`.

Impact:

- `jobdb` is the correct execution-correlation ledger
- but the filesystem remains the durable payload store for actual job artifacts and exports

Required correction:

- tighten the wording from `artifact truth` to `artifact correlation/index truth`
- keep actual artifact payload truth with `artifacts/jobs/*` and related filesystem outputs

## Minimal Correction Set For v2

If this decision document is revised, the minimum safe fixes are:

1. Rename layer A from literal `~/.openclaw` to `OpenClaw runtime state dir / OPENCLAW_STATE_DIR`.
2. Narrow layer-A wording so it does not over-claim Feishu/DingTalk continuity without direct evidence.
3. Keep `state/agent_sessions` as canonical for `/v3/agent/*` surface.
4. Keep `state/jobdb.sqlite3` as execution-correlation truth, but clarify that artifact payload content still lives in `artifacts/jobs/*`.

## Bottom Line

`session_truth_decision_v1` correctly rejects the old “three equal ledgers” model.

Its strongest claims hold:

- `state/agent_sessions` is real canonical state for `/v3/agent/*`
- `jobdb` is execution-correlation truth
- `/v2/advisor/*` did not secretly grow a fourth durable session ledger

Its remaining weakness is concentrated in layer A and one execution wording edge:

- `~/.openclaw` should really be `OpenClaw runtime state dir / OPENCLAW_STATE_DIR`
- the current evidence directly proves OpenClaw-native continuity, but not the broader `OpenClaw / Feishu / DingTalk` phrasing
- `jobdb` tracks artifact correlation, while actual artifact payload truth still lives on disk

So this is a strong intermediate decision, but not yet the final session-truth freeze artifact. It should be superseded by a `session_truth_decision_v2` before `telemetry_contract_fix_v1` depends on it as an exact ledger contract.
