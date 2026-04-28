# Backlog Absorption Plan

Date: 2026-04-27
Scope: Labebe / Paperclip 14-day masterplan skill-runtime governance worker
Write boundary: this file is planning-only. Do not mutate `/vol1/maint`, `/vol1/1000/projects/multica`, `/vol1/1000/projects/paperclip`, or `/vol1/1000/projects/gstack` from this work product.

## Decision Frame

The Labebe sprint absorbs historical backlog only when it improves evidence-backed delivery without moving the consumer website away from a pure Labebe DTC replacement.

Hard boundaries:

- DTC website remains consumer commerce only. No Paperclip board, AI Studio, claim ledger, internal product matrix, or technical demo language in the consumer navigation or page content.
- AI / Paperclip demo remains a separate Boss Gallery / executive surface.
- Runtime governance is a thin support layer, not a new active platform.
- Multica history is a read-only pattern source. It is not revived as the daily control plane for this sprint.
- GStack is mined for methods and QA checklists, not imported as a runtime with telemetry, proactive routing, update checks, or `~/.gstack` state.

## Sources Read

Primary Labebe planning sources:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/master_scope/MASTER_SCOPE_AND_ACCEPTANCE.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/pro_packet/Labebe运营系统设计.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/scope_boundary.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/paperclip_org_tree.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/gate_kernel_v0.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/05_ISSUE_INDEX_AND_ACCEPTANCE.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/11_NEXT_EXECUTION_QUEUE.md`

External source directories and high-signal files:

- `/vol1/maint/docs/2026-04-23_multica_paperclip_finbot_history_audit_handoff.md`
- `/vol1/maint/docs/2026-04-23_multica_hermes_operating_spec_v2.md`
- `/vol1/maint/docs/2026-04-19_maint_comprehensive_governance_runtime_audit.md`
- `/vol1/maint/docs/2026-04-13_minimax_mcp_and_skill_governance_maintenance.md`
- `/vol1/maint/docs/2026-04-12_codex_home_convergence_and_browser_mcp_refresh.md`
- `/vol1/maint/docs/control_plane/skill_policy.v0.json`
- `/vol1/maint/docs/control_plane/worker_command_policy.v0.json`
- `/vol1/maint/docs/control_plane/action_class_registry.v0.json`
- `/vol1/maint/docs/control_plane/control_plane_readiness_policy.v0.json`
- `/vol1/maint/docs/control_plane/adr/ADR-001-chief-verified-delegation-control-plane.md`
- `/vol1/maint/docs/control_plane/2026-04-27_multica_chief_completion_summary.md`
- `/vol1/maint/docs/control_plane/2026-04-27_pro_autonomy_review_decision.md`
- `/vol1/maint/docs/control_plane/2026-04-27_chief_autonomy_retrospective.md`
- `/vol1/maint/docs/checkpoints/2026-04-24_governance_default_deny_checkpoint.md`
- `/vol1/maint/docs/checkpoints/2026-04-24_skill_policy_audit_checkpoint.md`
- `/vol1/maint/docs/checkpoints/2026-04-24_runtime_policy_attestation_checkpoint.md`
- `/vol1/maint/docs/checkpoints/2026-04-25_multica_hermes_permission_policy_checkpoint.md`
- `/vol1/maint/docs/checkpoints/2026-04-25_multica_hermes_permission_selftest_checkpoint.md`
- `/vol1/maint/docs/checkpoints/2026-04-26_multica_pool_and_policy_audit_read_amplification_checkpoint.md`
- `/vol1/maint/docs/checkpoints/2026-04-26_aop84_aop85_deterministic_runtime_smoke_checkpoint.md`
- `/vol1/1000/projects/multica/HANDOFF_ARCHITECTURE_AUDIT.md`
- `/vol1/1000/projects/multica/docs/workspace-url-refactor-proposal.md`
- `/vol1/1000/projects/multica/docs/plans/2026-04-16-remove-onboarding-and-fix-daemon-bootstrap.md`
- `/vol1/1000/projects/multica/CLAUDE.md`
- `/vol1/1000/projects/paperclip/ROADMAP.md`
- `/vol1/1000/projects/paperclip/doc/TASKS.md`
- `/vol1/1000/projects/paperclip/doc/TASKS-mcp.md`
- `/vol1/1000/projects/paperclip/docs/start/architecture.md`
- `/vol1/1000/projects/paperclip/docs/guides/board-operator/org-structure.md`
- `/vol1/1000/projects/paperclip/docs/guides/board-operator/execution-workspaces-and-runtime-services.md`
- `/vol1/1000/projects/paperclip/docs/guides/execution-policy.md`
- `/vol1/1000/projects/paperclip/doc/plans/2026-03-13-paperclip-skill-tightening-plan.md`
- `/vol1/1000/projects/paperclip/doc/plans/2026-03-13-agent-evals-framework.md`
- `/vol1/1000/projects/paperclip/doc/plans/2026-03-14-skills-ui-product-plan.md`
- `/vol1/1000/projects/paperclip/doc/plans/2026-03-14-adapter-skill-sync-rollout.md`
- `/vol1/1000/projects/paperclip/doc/plans/2026-03-13-features.md`
- `/vol1/1000/projects/paperclip/doc/plans/2026-03-11-agent-chat-ui-and-issue-backed-conversations.md`
- `/vol1/1000/projects/paperclip/doc/plans/2026-02-20-issue-run-orchestration-plan.md`
- `/vol1/1000/projects/paperclip/doc/plans/2026-04-08-agent-browser-process-cleanup-plan.md`
- `/vol1/1000/projects/paperclip/doc/plans/2026-04-08-agent-os-follow-up-plan.md`
- `/vol1/1000/projects/paperclip/report/2026-03-13-08-46-token-optimization-implementation.md`
- `/vol1/1000/projects/gstack/README.md`
- `/vol1/1000/projects/gstack/BROWSER.md`
- `/vol1/1000/projects/gstack/docs/REMOTE_BROWSER_ACCESS.md`
- `/vol1/1000/projects/gstack/docs/designs/GSTACK_BROWSER_V0.md`
- `/vol1/1000/projects/gstack/review/checklist.md`
- `/vol1/1000/projects/gstack/review/design-checklist.md`
- `/vol1/1000/projects/gstack/review/TODOS-format.md`
- `/vol1/1000/projects/gstack/qa/SKILL.md`
- `/vol1/1000/projects/gstack/qa/references/issue-taxonomy.md`
- `/vol1/1000/projects/gstack/qa/templates/qa-report-template.md`
- `/vol1/1000/projects/gstack/guard/SKILL.md`
- `/vol1/1000/projects/gstack/freeze/SKILL.md`
- `/vol1/1000/projects/gstack/TODOS.md`

## Absorb Now

| ID | Source | Absorb Into | Action | Acceptance |
| --- | --- | --- | --- | --- |
| ABS-001 | Paperclip issue model in `/vol1/1000/projects/paperclip/doc/TASKS.md`; current ledger in `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/05_ISSUE_INDEX_AND_ACCEPTANCE.md` | `PCL-001` issue contract and future Paperclip import | Keep single-owner issues; split collaborative work into sub-issues; map local statuses to Paperclip workflow categories before creating live issues. | Every issue has one owner role, required output paths, guardrails, and evidence criteria. |
| ABS-002 | Paperclip execution policy in `/vol1/1000/projects/paperclip/docs/guides/execution-policy.md` | `work_products/runtime_kernel/gate_kernel_v0.md` and future issue closeout | Treat comment-required, review, and approval as the local Closeout Gate equivalent. | No issue reaches `done` without `handoff.md`, `evidence_manifest.json`, and explicit limitation notes. |
| ABS-003 | Paperclip roadmap "Artifacts & Work Products" in `/vol1/1000/projects/paperclip/ROADMAP.md`; feature plan in `/vol1/1000/projects/paperclip/doc/plans/2026-03-13-features.md` | Executive pack and Boss Gallery evidence | Make artifacts first-class in the masterplan by registering preview URLs, screenshots, CSVs, markdown reports, and generated demo pages in evidence manifests. | Each impressive output has a path, owner, source, claim status, and review-ready link. |
| ABS-004 | Paperclip org hierarchy in `/vol1/1000/projects/paperclip/docs/guides/board-operator/org-structure.md` | `paperclip_multica_org_mapping.md` | Keep exactly two active orgs plus one read-only archive area. Use role reporting only to clarify escalation, not to create extra orgs. | Active org count remains two: `Labebe Commercial Studio` and `Paperclip Runtime & Evidence Kernel`. |
| ABS-005 | Maint verified delegation ADR in `/vol1/maint/docs/control_plane/adr/ADR-001-chief-verified-delegation-control-plane.md` | `maint_update_plan.md`, future runtime policy notes | Adopt "LLM proposes, deterministic policy verifies, typed actuator executes" as a boundary rule for any future automation. | No Labebe/Paperclip sprint work claims live write autonomy or chief write authority. |
| ABS-006 | Maint default-deny and skill policy in `/vol1/maint/docs/control_plane/skill_policy.v0.json`, `/vol1/maint/docs/checkpoints/2026-04-24_governance_default_deny_checkpoint.md` | Runtime governance acceptance | Any new skill/MCP/runtime change must start deny-by-default and add only explicit read/action permission. | Governance lanes do not expose browser actions, write tools, patch, delegate, MCP mutation, skill mutation, or secret roots by default. |
| ABS-007 | Maint MiniMax governance in `/vol1/maint/docs/2026-04-13_minimax_mcp_and_skill_governance_maintenance.md` | Video/media generation and skill placement | Use MiniMax through the existing governed skill/MCP path only when a concrete video/audio/image deliverable requires it. | Region host, wrapper, proxy behavior, and usage caveats are documented before relying on MiniMax output. |
| ABS-008 | Paperclip token optimization and skill isolation finding in `/vol1/1000/projects/paperclip/report/2026-03-13-08-46-token-optimization-implementation.md` | Skill/runtime governance backlog | Record a follow-up to isolate Paperclip skills per worktree or verify symlink targets before relying on runtime skill updates. | A future agent can prove which `skills/paperclip/SKILL.md` content was loaded for a run. |
| ABS-009 | Multica workspace URL and cache findings in `/vol1/1000/projects/multica/HANDOFF_ARCHITECTURE_AUDIT.md` and `/vol1/1000/projects/multica/docs/workspace-url-refactor-proposal.md` | Labebe route map and Paperclip org boundary rules | Absorb only the principle: URL/context must be explicit, shareable, and not localStorage-dependent. | DTC prototype routes and evidence links are stable URLs; Paperclip/Boss Gallery links never depend on hidden workspace state. |
| ABS-010 | Multica daemon/permission selftest in `/vol1/maint/docs/checkpoints/2026-04-25_multica_hermes_permission_selftest_checkpoint.md` | Runtime policy smoke standard | Use no-launch permission probes before allowing any worker lane to read files or touch browser sessions. | Permission selftest proves exact allowed read and rejects terminal, wrong-path read, secret path, and write attempts. |
| ABS-011 | GStack QA/browser docs in `/vol1/1000/projects/gstack/qa/SKILL.md`, `/vol1/1000/projects/gstack/BROWSER.md`, `/vol1/1000/projects/gstack/qa/templates/qa-report-template.md` | `work_products/runtime_qa_templates/` and DTC/Boss Gallery QA | Extract screenshot, console, link, responsive, interaction, and issue taxonomy patterns into Browser Harness P0 support. | QA reports cover desktop/mobile, console errors, broken links, core flows, visual hierarchy, and screenshots. |
| ABS-012 | GStack review/design checklists in `/vol1/1000/projects/gstack/review/checklist.md` and `/vol1/1000/projects/gstack/review/design-checklist.md` | Advisory gates only | Use as checklists for design review, pre-landing review, and AI-slop critique, not as an imported toolchain. | Findings cite file/path or screenshot evidence and are attached to Paperclip artifacts. |

## Defer Or Reject

| ID | Source | Decision | Reason | Revisit Trigger |
| --- | --- | --- | --- | --- |
| DEF-001 | `/vol1/1000/projects/multica` live board/runtime model | Reject for this sprint | Reusing Multica as daily control plane would revive old system weight and compete with Paperclip. | Only after Labebe DTC v2 and Boss Gallery v0 are accepted and a new control-plane decision is made. |
| DEF-002 | Full Multica issue migration | Reject | Old `done` does not prove current product readiness; issue migration would create false progress. | Never bulk migrate; only cite exact lessons or failed fixtures. |
| DEF-003 | GStack wholesale install/routing | Reject | GStack writes telemetry/config/routing state and assumes Claude-centric skill execution. | Never for this sprint; extract method text only. |
| DEF-004 | GStack Browser as shared remote-agent browser | Defer | Useful pattern, but remote session tokens/tunnels/admin scope are not needed for current DTC QA. | Use only if current CDP/browser harness cannot capture required evidence. |
| DEF-005 | Paperclip Cloud/Sandbox agents, MAXIMIZER MODE, Deep Planning, Work Queues, CEO Chat, Desktop App from `/vol1/1000/projects/paperclip/ROADMAP.md` | Defer | Product-roadmap scale exceeds Labebe 14-day goal. | Revisit after Paperclip issue/evidence IDs are connected to Boss Gallery cards. |
| DEF-006 | Paperclip Agent OS runtime experiment in `/vol1/1000/projects/paperclip/doc/plans/2026-04-08-agent-os-follow-up-plan.md` | Defer | Runtime substrate experiments risk blurring control plane vs execution plane. | Revisit only as an isolated adapter spike, not before Labebe deliverables. |
| DEF-007 | Paperclip issue-backed chat / command composer | Defer | Valuable for Paperclip product, not needed to deliver DTC or Boss Gallery now. | Revisit after Paperclip is actually used as the issue system for this project. |
| DEF-008 | Full MCP/CLI/Skill decision matrix | Defer | Current masterplan explicitly says it is not a DTC prototype prerequisite. | Revisit only after repeated skill/MCP failure blocks multiple deliverables. |
| DEF-009 | Write actuator or native worker smoke expansion from maint control plane | Reject for Labebe sprint | Maint shows native no-write and write actuator are still blocked or narrow proof-only. | Only under separate typed action policy, not inside Labebe delivery. |
| DEF-010 | Historical conversation skill mining | Reject | Too noisy and not evidence-bound to current Labebe artifacts. | Use only source docs and concrete failed/success artifacts. |

## Concrete Action Backlog

| Action | Target File / Artifact | Owner Role | Source Basis | Done Standard |
| --- | --- | --- | --- | --- |
| Add "issue created is not progress" rule to issue closeout text | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/issue_evidence_contract.md` | Paperclip Program Architect | `/vol1/maint/docs/control_plane/2026-04-27_chief_autonomy_retrospective.md`; `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/pro_packet/Labebe运营系统设计.md` | Done requires artifact evidence, not status text. |
| Add artifact registration checklist for previews, screenshots, CSVs, docs, videos | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/evidence_manifest_schema.json` | Evidence Steward | `/vol1/1000/projects/paperclip/ROADMAP.md`; `/vol1/1000/projects/paperclip/doc/plans/2026-03-13-features.md` | Manifest schema can represent DTC URL, Boss Gallery URL, screenshots, data CSV, and blocked claims. |
| Attach Paperclip issue/evidence IDs to Boss Gallery demo cards | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/design_record.md`; `paperclip_runtime_duel/outputs/boss_gallery_v0/index.html` | AI Demo Producer / Claim Steward | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/11_NEXT_EXECUTION_QUEUE.md` | Every Demo A-F card has claim status, evidence link, and blocked-claim note. |
| Keep DTC route map free of internal demos | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/dtc_prototype_v2/route_map.md` | UX Designer | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/scope_boundary.md` | No route points to Boss Gallery, Paperclip, AI Studio, claim gate, or internal matrix. |
| Convert GStack QA taxonomy into Browser Harness acceptance text | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/browser_harness_p0_contract.md` | Browser Harness Maintainer | `/vol1/1000/projects/gstack/qa/references/issue-taxonomy.md`; `/vol1/1000/projects/gstack/qa/templates/qa-report-template.md` | QA output distinguishes critical/high/medium/low and covers console, visual, functional, UX, content, performance, accessibility. |
| Add "no GStack runtime import" note to governance handoff | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/maint_update_plan.md` | Runtime Governance Steward | `/vol1/1000/projects/gstack/SKILL.md`; `/vol1/1000/projects/gstack/guard/SKILL.md`; `/vol1/1000/projects/gstack/freeze/SKILL.md` | Maint update plan says extract methods only and do not write `~/.gstack` as control state. |
| Add future skill isolation check | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/maint_update_plan.md` | Runtime Governance Steward | `/vol1/1000/projects/paperclip/report/2026-03-13-08-46-token-optimization-implementation.md` | Future run packet verifies loaded skill path and symlink target before trusting behavior. |
| Record Multica archive as read-only source set | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/paperclip_multica_org_mapping.md` | Program Strategist | `/vol1/maint/docs/2026-04-23_multica_paperclip_finbot_history_audit_handoff.md`; `/vol1/1000/projects/multica/HANDOFF_ARCHITECTURE_AUDIT.md` | Mapping lists allowed lessons and forbidden migrations. |

## Acceptance Criteria For This Absorption Work

- Every absorbed item cites a source path and a target artifact or future action path.
- Every rejected item has a reason and a revisit trigger or "never in this sprint" decision.
- DTC remains pure commerce and does not absorb Paperclip, AI demo, or control-plane UI.
- Boss Gallery remains separate and claim-gated.
- Runtime governance remains a thin support layer with default-deny, source-path evidence, and no live write autonomy claims.
- Future maintainers can continue from the three files in this directory without rereading the full external repos.
