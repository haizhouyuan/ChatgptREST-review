# ASF-18 Chief Manifest Transition Checker Checkpoint

- Date: 2026-04-24
- Scope: design-only control-plane manifest, drift detector, and transition-checker contract for `hermes-chief-of-staff`
- Output target: `/vol1/maint/docs/checkpoints/2026-04-24_asf18_chief_manifest_transition_checker_checkpoint.md`
- Constraints observed: no live MCP mutation, no live prompt mutation, no live skill activation, no workspace expansion, no blocked-lane unfreeze

## Executive Conclusion

`ASF-18` is no longer a generic “MCP / skills registry integration” task.

It is now the **automation blocker** for the Hermes chief control plane.

The purpose of this checkpoint is to freeze the design specification for a future machine-checkable control layer with five explicit parts:

1. canonical chief capability manifest
2. expected vs actual metadata reconciliation
3. drift detector contract
4. minimal transition checker contract
5. no-op / degraded-gate policy for scheduled governance runs

This is the first checkpoint whose direct goal is **not** proving another lane artifact. Its goal is to define the manifest and checker contract required before the system can safely reason about its own state without relying on sidecar memory.

### AOP-65 Amendment

Primary red-team review `AOP-65` returned `Conditional No-Go`, not because the contract direction was wrong, but because this checkpoint overclaimed maturity.

This amended version makes three corrections:

- It frames `ASF-18` as a design specification for a compiled control layer, not the compiled layer itself.
- It states that the drift detector is a reporting-format contract until a later implementation issue defines input acquisition and execution.
- It adds a deterministic candidate-selection rule for `todo -> in_review`; if that rule cannot select one lane, the correct output is `no_op`.

## Why This Is Now The Blocker

Completed proof stack so far:

- `ASF-15`: live inventory of chief runtime / config / metadata gaps
- `ASF-16`: auth-lane proof
- `ASF-17`: chief role / routing / escalation contract

What remains unresolved:

- Multica-visible chief metadata is still incomplete (`mcp_config=null`, `skills=[]`)
- actual chief capability surface still partly lives outside Multica-visible state
- scheduled governance sweep still creates issues instead of operating from a dry-run state transition engine
- fallback red-team policy is now graded in this checkpoint, but not yet enforced by a runnable gate

Therefore:

> broader chief self-advance remains blocked until the manifest + checker + drift policy design is accepted and a later implementation issue produces a runnable dry-run harness.

## Evidence Inputs

- `/vol1/maint/docs/checkpoints/2026-04-24_asf15_hermes_control_plane_inventory_checkpoint.md`
- `/vol1/maint/docs/checkpoints/2026-04-24_asf16_hermes_auth_lane_proof_checkpoint.md`
- `/vol1/maint/docs/checkpoints/2026-04-24_asf17_hermes_chief_prompt_routing_contract_checkpoint.md`
- `/vol1/maint/docs/2026-04-23_multica_hermes_operating_spec_v2.md`
- latest Pro red-team review packet and answer summary
- live `hermes-chief-of-staff` agent record
- live chief autopilot record
- sanitized Hermes home config metadata

## Current Reconciliation Snapshot

### Expected chief state

From prior checkpoints and current sidecar rulings, the expected chief state is:

| Area | Expected |
| --- | --- |
| role | chief-of-staff control entry |
| model provider | `openai-codex` |
| model name | `gpt-5.5` |
| reasoning effort | `xhigh` |
| auth lane | isolated, dedicated auth-only Codex source |
| MCP lane | `chatgptrest` present |
| skill surface | bundled Hermes skills + external planning skills |
| automation mode | governance reporter only, not autonomy layer |

### Current Multica-visible state

| Area | Current visible value |
| --- | --- |
| agent `model` | `gpt-5.5` |
| agent `mcp_config` | `null` |
| agent `skills` | `[]` |
| runtime | `Hermes (YogaS2)` |
| autopilot title | `Chief Scheduled Governance Reporter` |
| autopilot mode | `create_issue` |

### Current Hermes-home-local state

| Area | Current local value |
| --- | --- |
| `model.provider` | `openai-codex` |
| `model.default` | `gpt-5.5` |
| `model.base_url` | `https://api.minimaxi.com/anthropic` |
| `model.api_mode` | `anthropic_messages` |
| `agent.reasoning_effort` | `xhigh` |
| `mcp_servers` | `chatgptrest` |
| `skills.external_dirs` | `/vol1/1000/projects/planning/hermes-skills` |
| bundled local skill tree | present |

## Canonical Chief Manifest

The chief must have a machine-visible manifest that answers:

- who the chief is
- what exact capability surface it has
- what source of truth each field comes from
- what drift means
- what transitions it may request or execute

### Proposed schema

```yaml
manifest_id: chief-control-plane
manifest_version: 0.1.0
manifest_hash: sha256:...
updated_at: 2026-04-24T...

actor:
  agent_id: 48251656-cdc5-48e3-804d-4fd338614b7b
  name: hermes-chief-of-staff
  workspace_id: bbc33e1b-a6d8-4724-b29f-b35ac8372572
  role_contract_ref: ASF-17
  role_contract_hash: sha256:...

runtime:
  runtime_id: c27532f7-13f2-44fe-82da-a1660f421def
  runtime_provider: hermes
  runtime_mode: local
  runtime_status: online

model:
  provider: openai-codex
  name: gpt-5.5
  reasoning_effort: xhigh
  api_mode: anthropic_messages
  base_url: https://api.minimaxi.com/anthropic
  source_of_truth: hermes_home_config
  multica_visible: partial

auth:
  lane_id: hermes-auth-only-codex
  auth_store: ~/.hermes/auth.json
  proof_ref: ASF-16
  proof_strength: current_state_strong
  daily_lane_overlap: false

mcp:
  lanes:
    - name: chatgptrest
      source_of_truth: hermes_home_config
      multica_visible: false
      permission_scope: app-specific runtime automation lane
      drift_if_missing: high

skills:
  bundled_local: true
  external_dirs:
    - /vol1/1000/projects/planning/hermes-skills
  multica_visible_agent_skills: []
  source_of_truth: split
  drift_if_empty_in_multica: high

tool_scope:
  default_mode: governance_only
  scheduled_sweep_allowlist:
    - multica issue list/get
    - multica project list/get
    - multica agent get
    - multica runtime list
    - multica issue status/comment
  prohibited:
    - multica --help
    - pwd
    - broad file discovery
    - environment probing
    - blocked-lane unfreeze
    - agent/project/workspace expansion

transitions:
  may_propose:
    - no_op
    - report_drift
    - propose_single_next_lane
  may_execute_if_checker_green:
    - todo_to_in_review_for_one_lane
  forbidden:
    - unblock_blocked_lane
    - implementation_start_without_gate
    - live_prompt_mutation
    - live_mcp_mutation

red_team:
  primary_gate: redteam-claudegac
  fallback_gate: redteam-codex-xhigh-fallback
  fallback_independence: degraded
  policy_ref: ASF-18
```

## Source-of-Truth Rule

The chief control plane currently has split truth sources. This checkpoint does **not** collapse them into one storage location. It defines how they relate.

### Rule

| Field family | Current source of truth | Desired visibility |
| --- | --- | --- |
| role contract | checkpoint doc (`ASF-17`) | doc + manifest |
| model / reasoning | Hermes home config | manifest + Multica visible summary |
| auth lane | Hermes auth store + proof checkpoint | manifest summary |
| MCP lanes | Hermes home config | manifest + eventually Multica visible summary |
| skills surface | Hermes bundled tree + external dirs | manifest + eventually Multica visible summary |
| issue / project / runtime state | Multica | Multica authoritative |
| blocked / allowed transitions | checker policy | manifest + checker |

### Implication

Multica does **not** need to become the literal storage location for every low-level value.

But it must become able to answer:

- expected value
- actual visible value
- source of truth
- whether drift exists

without sidecar memory.

## Drift Detector Contract

The drift detector is not a runnable detector here. It is the reporting-format contract for how drift must be reported.

A later implementation issue must define:

- who runs the detector
- when it runs
- how it collects Multica state
- how it summarizes Hermes-home-local state without exposing secrets
- where the detector output and hashes are stored

### Input

- chief manifest
- current Multica agent/runtime state
- current Hermes-home-local summarized state
- latest proof refs (`ASF-15`, `ASF-16`, `ASF-17`)

### Input acquisition rule

The runnable implementation must collect inputs through declared readers only:

| Input | Reader | Secret policy |
| --- | --- | --- |
| chief manifest | manifest file / Multica metadata snapshot | no secret values |
| Multica state | `multica agent/runtime/issue/autopilot` read commands | no raw auth |
| Hermes config summary | local sanitized config reader | no token or key content |
| auth proof refs | prior checkpoint metadata | fingerprints only |

Until those readers exist, this detector remains a design contract and cannot be used as evidence of self-advance readiness.

### Output

```yaml
detector_run_id: ...
manifest_hash: ...
board_state_hash: ...
drift_items:
  - field: mcp.lanes.chatgptrest.multica_visible
    expected: present
    actual: absent
    severity: high
    required_action: report_only | block_transition | ask_user
  - field: skills.multica_visible_agent_skills
    expected: explicit summary or declared-null-with-rationale
    actual: []
    severity: high
    required_action: block_transition
```

### Severity classes

| Severity | Meaning | Effect |
| --- | --- | --- |
| `low` | cosmetic / descriptive mismatch | report only |
| `medium` | incomplete visibility but not authority-critical | report + no automation promotion |
| `high` | capability boundary unclear | block self-advance transition |
| `critical` | auth / permission / transition safety unclear | block and escalate |

### Current high-severity drift items

1. chief `mcp_config` still null in Multica-visible state
2. chief `skills` still empty in Multica-visible state
3. capability source split remains implicit without manifest summary

## Minimal Transition Checker

The checker governs only the smallest allowable chief automation step:

> proposing or executing at most one `todo -> in_review` transition during a scheduled governance run

### Proposed contract

```yaml
checker_name: chief-next-lane-checker
checker_version: 0.1.0

inputs:
  - issue_id
  - board_state_hash
  - manifest_hash
  - dependency_snapshot
  - issue_contract_snapshot
  - red_team_status

checks:
  - issue_exists
  - issue_status_is_todo
  - full_issue_contract_present
  - no_blocked_dependency
  - no_open_red_team_blocker
  - no_live_drift_severity_high_or_above
  - run_has_not_already_proposed_or_executed_another_lane
  - action_class_not_implementation

output:
  eligible: true|false
  failed_checks: [...]
  candidate_order: [...]
  allowed_action: no_op | propose_transition | execute_transition
```

### Important rule

If any of these are true, `allowed_action` must degrade to `no_op`:

- blocked dependency present
- drift severity `high` or `critical`
- fallback red-team is the only available gate for a high-risk lane
- deterministic candidate selection returns no single winner

### Candidate selection rule

For a scheduled governance run, the checker must first build the eligible candidate set and then sort it by:

1. explicit sidecar or user unlock order, if present
2. issue priority, with `high` before `medium` before `low` before `none`
3. project priority, with `planned` control-plane projects before dormant backlog projects
4. lowest issue number
5. earliest `created_at`

If the sorted list still contains an ambiguity that cannot be explained from board state alone, the checker must return `no_op` with `failed_checks: ["ambiguous_candidate_selection"]`. It may report the tied candidates, but it must not choose based on hidden sidecar memory.

## No-Op Success Rule

A scheduled governance run is allowed to succeed with **no issue creation and no state transition**.

### Valid successful outputs

1. `no_op`
2. `drift_report_only`
3. `single_next_lane_proposed`
4. `single_next_lane_executed` only if checker green and risk class permits

### Invalid success signal

Creating a governance issue by itself is **not** progress.

If a scheduled run creates issues every time, it should be treated as noise unless it carries:

- concrete drift
- concrete policy failure
- or exactly one qualified next-lane proposal

## Red-Team Independence Policy

This checkpoint converts the current implicit fallback handling into an explicit policy.

### Independence grades

| Grade | Meaning | Can clear high-risk blocker? |
| --- | --- | --- |
| `A` | independent provider/model family and not involved in proposal creation | yes |
| `B` | sufficiently separate reviewer lane, not involved in proposal creation | maybe |
| `C` | same sidecar/model family ecosystem, critique useful but independence degraded | no |
| `D` | self-check only | no |

### Current policy

- `redteam-claudegac`: target `A/B`
- `redteam-codex-xhigh-fallback`: `C`

### Rule

If fallback grade is `C`, then for high-risk lanes it may:

- critique
- identify blockers
- support draft progression

but it may **not** be the sole basis for lifting a high-risk blocker.

## What This Blocks

Until this manifest/checker design is accepted and followed by a runnable dry-run harness, the system should **not** claim:

- trusted chief self-advance
- low-intervention autonomy
- reliable autonomous next-lane progression

## Recommended Next Step

After red-team review of `ASF-18`, the next action should be:

1. accept or reject this as a design baseline after `AOP-65`
2. create a narrower implementation issue for dry-run governance sweeps
3. do **not** jump to implementation-class chief automation yet

## Non-Goals

This checkpoint does **not**:

- mutate live MCP
- populate live Multica `mcp_config`
- populate live Multica `skills`
- change provider path
- unblock `ASF-9`
- unblock `ASF-6`

## Bottom Line

`ASF-18` is the design baseline for the point where the system stops being “well-written governance text with sidecar memory” and starts becoming an actual machine-checkable control plane.

If this checkpoint is not accepted, the system should remain in bounded orchestration mode.

If it is accepted, the next step is still not autonomy. The next step is a runnable `advance_one` dry-run harness that proves the manifest/checker rules can produce `no_op`, drift reports, and at most one proposed transition from real board snapshots.
