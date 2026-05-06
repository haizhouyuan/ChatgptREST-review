# 2026-03-20 Front Door Object Contract Verification Walkthrough v1

## What I checked

This verification re-audited four deliverables from commit `6e42968`:

- [2026-03-20_front_door_object_contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_object_contract_v1.md)
- [2026-03-20_task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json)
- [2026-03-20_entry_adapter_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_entry_adapter_matrix_v1.md)
- [2026-03-20_front_door_object_contract_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_object_contract_walkthrough_v1.md)

I focused on five questions:

1. Is `Task Intake Spec` really the right canonical front-door level?
2. Do `IntentEnvelope`, `StandardRequest`, and `AskContract` really deserve the downgraded roles claimed by the document?
3. Does the frozen JSON schema actually line up with the current live code?
4. Does the adapter matrix fully close the translation from current ingress/carrier shapes into the new canonical object?
5. Did the claimed JSON validation actually pass?

## What held up

The main architecture held up.

### 1. `Task Intake Spec` is the right place to freeze the canonical object

This judgment is stronger than the alternatives:

- richer than `StandardRequest`
- closer to ingress truth than `AskContract`
- better suited to hold identity, acceptance, evidence, attachments, and scenario

### 2. `AskContract` should stay, but as a derived reasoning view

This is a correction, not a deletion.

Current code still needs `AskContract` for:

- clarify gating
- strategist input
- prompt shaping
- post-review metadata

But that does not make it the right front-door truth source.

### 3. The codebase still needs object unification

This is not a paper-only problem.

Current live ingress still spreads semantics across:

- `routes_agent_v3.py` scattered request fields
- `routes_advisor_v3.py` lightweight ask fields
- OpenClaw plugin request shape
- legacy adapter carriers in `task_spec.py` and `standard_entry.py`

So the decision to freeze a canonical intake object is justified.

### 4. The JSON syntax validation claim is correct

I reran:

```bash
python3 -m json.tool docs/dev_log/2026-03-20_task_intake_spec_v1.json
```

It passed.

## What did not hold up cleanly

The remaining issues are precision issues, not a collapse of the main model.

### 1. The versioned canonical schema does not actually require its own version field

The schema defines `spec_version`, but does not require it.

That means producers can emit the canonical object without any guaranteed explicit schema version, which is a weak point for a supposedly frozen cross-ingress contract.

### 2. `task_spec.py` is described more as current truth than as target landing zone

The document says `task_spec.py` is the canonical schema location, but current code still contains the older `TaskSpec` and `AcceptanceSpec` shape.

Later sections of the document do admit this is a Phase 1 implementation target, so the issue is not the intended direction. The issue is that the earlier freeze wording is easier to over-read than it should be.

### 3. The source taxonomy is not fully closed

Current carriers still use source values such as:

- `codex`
- `api`
- `direct`

The frozen canonical schema uses:

- `openclaw`
- `cli`
- `rest`
- `unknown`

The matrix identifies the entry families, but it does not finish the value-level translation contract. That leaves room for inconsistent adapter implementations.

## Why this matters

This matters because the next implementation step is not another concept memo. It is real adapter work.

If the contract enters implementation with:

- optional schema versioning
- ambiguous current-vs-target wording
- unfrozen source translation

then different adapters will normalize into slightly different "canonical" objects, and the whole purpose of the freeze will leak immediately.

## Deliverables

This verification added:

- [2026-03-20_front_door_object_contract_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_object_contract_verification_v1.md)
- [2026-03-20_front_door_object_contract_verification_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_object_contract_verification_walkthrough_v1.md)

## Test Note

This was a documentation and code-evidence verification task. No product code was changed, and no test suite was run.
