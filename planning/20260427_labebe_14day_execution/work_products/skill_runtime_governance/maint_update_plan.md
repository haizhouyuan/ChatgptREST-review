# Maint Update Plan

Date: 2026-04-27
Scope: Planned maint-side record updates after Labebe/Paperclip governance decisions are accepted.
Current action: no writes to `/vol1/maint` in this worker turn.

## Purpose

This plan defines what should be recorded in `/vol1/maint` later so machine/runtime governance stays aligned with the Labebe/Paperclip masterplan. It does not authorize immediate maint edits, service changes, MCP changes, skill installs, runtime mutation, or Multica/Paperclip state writes.

The immediate deliverables are the three files under:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/`

## Current Maint Truths To Preserve

| Maint Truth | Source | Implication For Labebe/Paperclip |
| --- | --- | --- |
| `/vol1/maint` is a machine hub but not the runtime brain | `/vol1/maint/docs/2026-04-19_maint_comprehensive_governance_runtime_audit.md` | Add a record of Labebe governance decisions, but do not centralize Labebe execution in maint. |
| Governance defaults to deny | `/vol1/maint/docs/checkpoints/2026-04-24_governance_default_deny_checkpoint.md`; `/vol1/maint/docs/control_plane/skill_policy.v0.json` | Any new governance worker lane starts with no mutation tools and explicit read paths only. |
| Chief is verified delegation, not autonomous executor | `/vol1/maint/docs/control_plane/adr/ADR-001-chief-verified-delegation-control-plane.md` | Labebe Paperclip must not claim chief write autonomy or unsupervised execution. |
| Native no-write and write actuator remain gated/narrow | `/vol1/maint/docs/control_plane/control_plane_readiness_policy.v0.json`; `/vol1/maint/docs/checkpoints/2026-04-26_aop84_aop85_deterministic_runtime_smoke_checkpoint.md` | Do not unlock worker dispatch/writeback for this sprint. |
| Skill and runtime policy must be machine-verifiable | `/vol1/maint/docs/checkpoints/2026-04-24_runtime_policy_attestation_checkpoint.md`; `/vol1/maint/docs/checkpoints/2026-04-25_multica_hermes_permission_selftest_checkpoint.md` | Use selftests and exact path allowlists before any runtime worker lane. |
| MiniMax MCP region/wrapper behavior is known | `/vol1/maint/docs/2026-04-13_minimax_mcp_and_skill_governance_maintenance.md` | Video/image/audio AI outputs should use existing governed wrapper assumptions, not ad hoc hosts. |
| Browser MCP/Codex config has a canonical live source | `/vol1/maint/docs/2026-04-12_codex_home_convergence_and_browser_mcp_refresh.md` | Browser harness changes must not hand-edit alternate Codex configs or stale MCP pins. |
| Runtime pool/read amplification can break Multica | `/vol1/maint/docs/checkpoints/2026-04-26_multica_pool_and_policy_audit_read_amplification_checkpoint.md` | Labebe should not add polling-heavy observers or broad workspace runtime reads. |

## Proposed Maint Changes

### Phase 0: No Maint Write During Current Worker

Status: complete by policy.

Allowed:

- Read maint docs.
- Produce local planning artifacts in the specified Toyresearch directory.

Forbidden:

- Edit `/vol1/maint/docs/*`.
- Edit maint scripts, service drop-ins, secrets, config, runtime state, or MCP configs.
- Run Multica issue mutation, worker launch, or maint control-plane transition commands.

### Phase 1: Add A Single Maint Handoff Record

Proposed future file:

- `/vol1/maint/docs/2026-04-27_labebe_paperclip_skill_runtime_governance_handoff.md`

Trigger:

- Main controller accepts these local work products and wants maint to remember the governance decision.

Content to include:

- Link to local work products:
  - `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/backlog_absorption.md`
  - `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/paperclip_multica_org_mapping.md`
  - `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/maint_update_plan.md`
- Decision summary:
  - two active Paperclip orgs only;
  - Multica Archive read-only;
  - GStack methods only, no runtime import;
  - DTC pure Labebe commerce;
  - Boss Gallery separate and claim-gated;
  - runtime governance thin, default-deny, no write actuator.
- Source list for cross-reference:
  - `/vol1/maint/docs/control_plane/adr/ADR-001-chief-verified-delegation-control-plane.md`
  - `/vol1/maint/docs/2026-04-23_multica_hermes_operating_spec_v2.md`
  - `/vol1/maint/docs/2026-04-13_minimax_mcp_and_skill_governance_maintenance.md`
  - `/vol1/1000/projects/paperclip/ROADMAP.md`
  - `/vol1/1000/projects/multica/HANDOFF_ARCHITECTURE_AUDIT.md`
  - `/vol1/1000/projects/gstack/qa/SKILL.md`

Acceptance:

- One maint doc exists with no runtime/config edits.
- It states that no authority is granted by the document.
- It points future agents back to Toyresearch work products as sprint-local truth.

### Phase 2: Optional Agent Index Pointer

Proposed future edit:

- `/vol1/maint/docs/agent_index.md`

Trigger:

- Repeated future agents ask where Labebe/Paperclip skill-runtime governance decisions live.

Minimal action:

- Add a small pointer under the agent config / skill / workflow governance area, not a large new canonical section.

Suggested wording:

```markdown
- For the 2026-04-27 Labebe/Paperclip sprint governance mapping, see:
  `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/`.
  It is sprint-local guidance: DTC remains pure Labebe commerce, Boss Gallery is separate, Multica is read-only archive, GStack is method-only.
```

Acceptance:

- Pointer does not downgrade existing maint canonical docs.
- Pointer does not make Toyresearch sprint outputs global machine policy.

### Phase 3: Optional Project Workspace Registry Link

Candidate future file:

- `/vol1/maint/docs/project_workspace_registry.md`

Trigger:

- If registry already tracks Toyresearch or Labebe workspaces and needs a link to current planning artifacts.

Action:

- Add or update only the project entry pointing to:
  - `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/`
  - `/vol1/1000/projects/toyresearch/labebe-gemini-demo/`
  - `paperclip_runtime_duel/outputs/boss_gallery_v0/index.html`

Acceptance:

- Registry describes artifact locations, not product readiness.
- DTC and Boss Gallery are explicitly separate.

### Phase 4: Skill/MCP Follow-Up Only If A Real Failure Occurs

Potential future edits:

- `/vol1/maint/docs/2026-04-13_minimax_mcp_and_skill_governance_maintenance.md`
- `/vol1/maint/docs/2026-04-12_codex_home_convergence_and_browser_mcp_refresh.md`
- `/vol1/maint/docs/2026-03-06_agent_instruction_skill_workflow_inventory.md`

Trigger:

- A Labebe deliverable is blocked by a concrete MiniMax, Browser Harness, Codex skill, or MCP mismatch.

Required evidence before editing:

- failing command or run evidence;
- exact skill/MCP path;
- expected vs actual behavior;
- whether current governed wrapper already covers the need;
- proposed rollback or no-op path.

Acceptance:

- No broad MCP matrix rewrite.
- No plugin/skill bulk install.
- No GStack installation or routing injection.
- Fix only the misleading or broken current entry.

## Do Not Update Maint For These

Do not create maint work merely because these ideas were mentioned:

- Full MCP/CLI/Skill decision matrix.
- Full machine topology policy.
- Historical conversation skill mining.
- AgencyAgents bulk extraction.
- GStack wholesale installation.
- Browser/Vision Lab active org.
- Skill Foundry active org.
- Full Multica migration.
- Generic write actuator.
- Native worker dispatch loop.

These are explicitly overhead or out of scope for the current Labebe/Paperclip sprint.

## Runtime Governance Checklist For Future Changes

Before any future maint-side runtime or skill change connected to this sprint:

1. State the deliverable blocked by the change.
2. Identify source artifact and target file path.
3. Confirm DTC purity is unaffected.
4. Confirm Boss Gallery remains separate and claim-gated.
5. Confirm no secret roots are read or copied.
6. Confirm no browser/admin token, MCP config, skill home, or runtime service is mutated unless explicitly approved.
7. If governance lane: use default-deny and exact read allowlist.
8. If worker lane: require no-launch permission selftest before launch.
9. If write action: require typed action schema, deterministic policy, expected diff, postcondition verifier, idempotency, and audit ledger.
10. Record validation output path.

Relevant maint policy sources:

- `/vol1/maint/docs/control_plane/skill_policy.v0.json`
- `/vol1/maint/docs/control_plane/worker_command_policy.v0.json`
- `/vol1/maint/docs/control_plane/action_class_registry.v0.json`
- `/vol1/maint/docs/control_plane/control_plane_readiness_policy.v0.json`

## Validation Commands For Future Maint Edits

Run from `/vol1/maint` after any future maint doc-only update:

```bash
python3 ops/scripts/audit_maint_governance_drift.py
```

If a future update touches control-plane JSON:

```bash
python3 -m json.tool docs/control_plane/skill_policy.v0.json >/tmp/skill_policy.json.valid
python3 -m json.tool docs/control_plane/worker_command_policy.v0.json >/tmp/worker_command_policy.json.valid
python3 -m json.tool docs/control_plane/action_class_registry.v0.json >/tmp/action_class_registry.json.valid
python3 -m json.tool docs/control_plane/control_plane_readiness_policy.v0.json >/tmp/control_plane_readiness_policy.json.valid
```

If a future update claims runtime policy behavior:

```bash
python3 ops/scripts/chief_validate_runtime_policy.py --stamp YYYYMMDDT_labebe_governance --include-smoke --pretty --timeout 120
```

If a future update claims Multica permission behavior:

```bash
python3 ops/scripts/chief_validate_multica_hermes_permission_selftest.py --stamp YYYYMMDDT_labebe_permission_selftest --pretty
```

Do not run mutation or worker-launch commands as part of a doc-only maint update.

## Acceptance For This Plan

- It names specific maint files that may need future updates.
- It keeps current worker writes limited to Toyresearch `work_products/skill_runtime_governance/`.
- It prevents maint updates from becoming hidden runtime/config changes.
- It preserves the current verified-delegation boundary: LLM/chief proposes, deterministic policy verifies, typed actuator executes only when separately proven.
- It explicitly says Labebe DTC remains pure commerce and Boss Gallery remains separate.

## Current Output Files

This worker produced:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/backlog_absorption.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/paperclip_multica_org_mapping.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/maint_update_plan.md`
