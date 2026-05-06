# 2026-03-20 Front Door Object Contract Verification v1

## Scope

Targets under verification:

- [2026-03-20_front_door_object_contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_object_contract_v1.md)
- [2026-03-20_task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json)
- [2026-03-20_entry_adapter_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_entry_adapter_matrix_v1.md)
- [2026-03-20_front_door_object_contract_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_object_contract_walkthrough_v1.md)

Verification method on `2026-03-21`:

- inspect commit `6e42968`
- re-check the document set against current live code
- verify whether the frozen JSON schema is syntactically valid
- verify whether the object hierarchy matches current ingress/runtime behavior
- verify whether the adapter matrix fully closes the current source taxonomy

## Verdict

`front_door_object_contract_v1` gets the main decision right:

1. `Task Intake Spec` should be the canonical front-door object.
2. `IntentEnvelope` should stay an adapter envelope, not a peer truth.
3. `StandardRequest` should stay a legacy carrier, not grow into a second schema system.
4. `AskContract` should remain, but only as a derived reasoning view.

That part is materially supported by the codebase.

But this is not yet a final freeze artifact. Three precision gaps remain:

- `task_intake_spec_v1.json` does not require `spec_version` on-wire
- `front_door_object_contract_v1.md` overstates `task_spec.py` as if it were already the canonical schema location in current code
- `entry_adapter_matrix_v1.md` does not finish the source-enum translation from current carriers into the frozen canonical enum

So the correct status is `mostly verified, but not fully closed`.

## Confirmed

### 1. `AskContract` is better treated as a derived reasoning view than as a peer front-door truth

This core decision holds.

- [ask_contract.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_contract.py#L49) defines `AskContract` as a compact premium-ingress structure centered on `objective`, `decision_to_support`, `audience`, `constraints`, `available_inputs`, `missing_inputs`, and `output_shape`.
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1219) still synthesizes or normalizes this contract out of request-time free-form inputs.
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1258) stores it in request context for downstream clarify/strategy/review use.

That is consistent with the document's downgraded role: it is still useful, but it is not the right place to define the canonical ingress object.

### 2. `StandardRequest` is a light carrier, not a viable canonical schema

This core decision also holds.

- [standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py#L24) shows `StandardRequest` only carries `question`, `source`, `trace_id`, `target_agent`, `preset`, `file_paths`, and `metadata`.
- It does not carry structured `acceptance`, `evidence_required`, `scenario`, or richer identity/context fields.

So demoting it to a legacy adapter carrier is the correct architectural call.

### 3. The need for a canonical intake object is real

The current live front door is still fragmented enough that a canonical object freeze is justified.

- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1219) still accepts `contract` plus scattered top-level compatibility fields.
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1605) still derives flow from `question`, `intent_hint`, `context`, and `file_paths`.
- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L257) still builds requests around `question`, then posts them as `message` to `/v3/agent/turn` at [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L282).

So the document's premise is sound: object unification is still a real missing seam.

### 4. The JSON syntax check claim is true

The user-stated validation claim was confirmed:

- `python3 -m json.tool docs/dev_log/2026-03-20_task_intake_spec_v1.json` succeeded during this verification run.

## Findings

### 1. `spec_version` is not required by the frozen canonical schema

The schema defines `spec_version`, but does not require it.

- [2026-03-20_task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json#L8) lists the required fields and omits `spec_version`.
- [2026-03-20_task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json#L17) defines `spec_version` as a `const` value, which only constrains the field if it is present.

Impact:

- downstream adapters can legally emit the canonical object without any explicit schema version
- that weakens future schema negotiation, migration guards, and telemetry/audit clarity for a versioned canonical contract

Required correction:

- either add `spec_version` to the schema `required` list
- or explicitly state that versioning is guaranteed out-of-band and intentionally absent from the required on-wire contract

### 2. `task_spec.py` is presented as if it were already the live canonical schema location

The target document is directionally correct about where Phase 1 should converge, but the wording is too strong for current code.

- [2026-03-20_front_door_object_contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_object_contract_v1.md#L41) says `task_spec.py` is retained as the canonical schema location.
- But [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py#L63) still defines a legacy `AcceptanceSpec` with only `none/light/full`.
- [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py#L78) still defines a materially different `TaskSpec` around `user_intent`, `deliverable_type`, `latency_budget_s`, `lane`, and `evidence_mode`.
- Those fields do not match the frozen JSON schema in [2026-03-20_task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json#L25), [2026-03-20_task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json#L67), [2026-03-20_task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json#L144), and [2026-03-20_task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json#L183).

To the document's credit, it later narrows this into an implementation direction:

- [2026-03-20_front_door_object_contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_object_contract_v1.md#L369) says `task_spec.py` must be upgraded into the canonical schema module.

Impact:

- the main architectural decision remains valid
- but the current wording can be misread as "already true in live code" instead of "frozen target module for upcoming implementation"

Required correction:

- revise the wording so `task_spec.py` is described as the intended landing module after Phase 1 implementation, not the current live canonical schema

### 3. The adapter matrix does not fully freeze the source translation from current carriers into the new canonical enum

The target schema and current carriers use different source taxonomies, but the matrix does not finish the translation contract.

- [2026-03-20_task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json#L25) freezes canonical `source` as `openclaw / feishu / rest / mcp / cli / cron / repair / unknown`.
- [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py#L28) still uses `feishu / codex / rest / cron / mcp / repair`.
- [standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py#L29) still documents current carrier values including `codex / api / direct`.
- [2026-03-20_entry_adapter_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_entry_adapter_matrix_v1.md#L19) lists the relevant entries, but it does not explicitly freeze how current `codex / api / direct` values must map into the canonical enum.

Impact:

- different adapters can map the same upstream caller into different canonical `source` values
- that would fragment telemetry, analytics, and later session/continuity reasoning

Required correction:

- add an explicit source-translation table for all currently live carrier values before implementation starts

## Minimal Correction Set For v2

If this document family is revised, the minimum safe fixes are:

1. Make `spec_version` required, or explicitly justify why it is intentionally optional.
2. Reword `task_spec.py` as the target landing module for the canonical schema, not the current live schema truth.
3. Freeze a source-enum translation table from current carrier values into the canonical `Task Intake Spec` enum.

## Bottom Line

`front_door_object_contract_v1` is a good Phase 1 baseline. Its central architectural decision survives review.

What is still missing is not a rethink of the object model, but a tighter contract around:

- versioning
- current-vs-target schema wording
- source-enum translation

So this should be treated as `v1 baseline verified with corrections pending`, not as the final freeze artifact.
