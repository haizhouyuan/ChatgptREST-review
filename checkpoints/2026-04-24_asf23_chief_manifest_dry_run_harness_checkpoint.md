# ASF-23 Chief Manifest Dry-Run Harness Checkpoint

- Date: 2026-04-24
- Scope: runnable dry-run proof layer for Hermes chief control-plane manifest and next-lane selection
- Issue: `ASF-23` (`d9891a85-976c-4427-99fa-041762319d6c`)
- Red-team gate: `AOP-66` pass 2 returned `Conditional Go`
- Constraints observed: no live Multica mutation, no live prompt/MCP/auth/skills mutation, no autopilot wiring, no raw secret reads

## Executive Conclusion

`ASF-23` now has a first runnable dry-run harness.

This is still **not** autonomy. It is a proof layer that can read declared JSON inputs, compute manifest/board hashes, detect drift, evaluate candidate issues, and return one of:

- `no_op`
- `drift_report_only`
- `propose_transition`

The harness cannot execute a transition. It does not call Multica and does not write issue state.

## Artifacts

| Artifact | Path |
| --- | --- |
| canonical manifest | `/vol1/maint/docs/control_plane/chief_manifest.v0.json` |
| manifest validation contract | `/vol1/maint/docs/control_plane/chief_manifest.schema.json` |
| dry-run harness | `/vol1/maint/ops/scripts/chief_advance_one_dry_run.py` |
| fixtures | `/vol1/maint/docs/control_plane/fixtures/` |
| checkpoint | `/vol1/maint/docs/checkpoints/2026-04-24_asf23_chief_manifest_dry_run_harness_checkpoint.md` |

## Command Interface

Single snapshot dry-run:

```bash
python3 /vol1/maint/ops/scripts/chief_advance_one_dry_run.py \
  --manifest /vol1/maint/docs/control_plane/chief_manifest.v0.json \
  --board-snapshot /vol1/maint/docs/control_plane/fixtures/current_high_drift_asf9_blocked.json \
  --run-id manual-check \
  --pretty
```

Bundled fixture self-test:

```bash
python3 /vol1/maint/ops/scripts/chief_advance_one_dry_run.py --self-test --pretty
```

The script intentionally has no live mode. Live board capture and autopilot wiring require a separate issue and review gate.

## Implemented Behavior

### Manifest validation

The harness validates the required manifest fields directly in Python and uses the JSON schema file as the external validation contract.

It checks:

- actor identity
- runtime summary
- model provider/name/reasoning (`openai-codex` / `gpt-5.5` / `xhigh`)
- auth proof reference and secret policy
- MCP lane presence
- skill visibility expectation
- dry-run-only transitions
- red-team gate metadata
- no secret-like values in manifest or board snapshots

Malformed manifest inputs fail closed with `allowed_action: no_op`.

### Drift detection

The harness compares manifest expectations against a declared `chief_state` snapshot.

High or critical drift blocks advancement. Current known high-drift examples:

- `mcp_config` missing `chatgptrest`
- `skills` empty while the manifest expects a non-empty visible summary
- model or reasoning mismatch

### Transition checking

The harness evaluates only `todo` issue candidates and requires:

- full issue contract
- no blocked/unresolved dependency
- no open red-team blocker
- no high/critical drift
- action class is not `implementation`
- high-risk lanes are not cleared solely by degraded grade-C fallback

### Candidate selection

Candidate order follows the `ASF-18` design:

1. explicit sidecar/user unlock order
2. issue priority
3. project priority
4. issue number
5. `created_at`

If the top two candidates remain tied after these fields, the harness returns `no_op` with `ambiguous_candidate_selection`.

## ASF-18 / ASF-23 Action Mapping

`ASF-18` used the design phrase `single_next_lane_proposed`.

`ASF-23` uses the machine action value:

- `single_next_lane_proposed` -> `propose_transition`

`single_next_lane_executed` is deliberately omitted from `ASF-23`. This harness is dry-run only and cannot execute.

## Fixtures And Evidence

The bundled self-test covers the red-team-required cases:

| Fixture | Expected result |
| --- | --- |
| `current_high_drift_asf9_blocked.json` | `no_op`; ASF-9 blocked by OpportunityCase dependency and implementation class |
| `metadata_drift_missing_mcp_skills.json` | `no_op`; high drift blocks transition |
| `multiple_eligible_ambiguous.json` | `no_op`; deterministic fields still tie |
| `fallback_grade_c_high_risk.json` | `no_op`; grade-C fallback cannot clear high-risk gate |
| `clean_low_risk_governance.json` | `propose_transition`; exactly one low-risk governance lane |
| `manifest_invalid_missing_model.json` | `no_op`; malformed manifest fails closed |

Verification run:

```text
python3 ops/scripts/chief_advance_one_dry_run.py --self-test --pretty
ok: true
```

Python syntax verification:

```text
python3 -m py_compile ops/scripts/chief_advance_one_dry_run.py
ok
```

## What Remains Text-Only

These items remain design/policy only:

- live Multica board capture
- live Hermes sanitized config capture
- persisted run ledger
- autopilot integration
- actual `todo -> in_review` mutation
- Multica metadata reconciliation write-back
- cross-workspace red-team read bridge

## What This Does Not Authorize

This checkpoint does not authorize:

- chief self-advance
- scheduled live transitions
- autopilot changes
- MCP/skill/auth/prompt mutation
- unblocking `ASF-6` or `ASF-9`
- routing to OpenClaw

Any live transition path still needs a separate implementation issue, red-team review, and sidecar/user approval.

## Sidecar Ruling

`ASF-23` may be accepted as the first runnable dry-run proof layer.

The next safe lane is not autonomy. The next safe lane is one of:

1. implement a read-only live snapshot exporter that feeds this harness without exposing secrets, or
2. build the cross-workspace red-team evidence bridge so review issues can always see target contracts, or
3. keep using fixture-only dry-runs while PRD/harness work proceeds.

Recommended next step: create a separate review-gated issue for a **read-only live snapshot exporter**, not autopilot execution.
