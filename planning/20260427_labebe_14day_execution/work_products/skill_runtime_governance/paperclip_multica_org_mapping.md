# Paperclip / Multica Organization Mapping

Date: 2026-04-27
Scope: Map Paperclip org structure, Multica archive lessons, maint governance, and GStack methods into the Labebe masterplan without changing the active sprint boundary.

## North Star

Use Paperclip as the evidence and issue operating model for Labebe deliverables. Use Multica only as a read-only archive and pattern library. Use maint as the machine/runtime governance source. Use GStack as a method reference for review and browser QA.

Do not use any of these systems to put AI/Paperclip internal surfaces into the Labebe consumer DTC website.

## Active Organization Model

### Active Org 1: Labebe Commercial Studio

Purpose:

- Deliver the Labebe consumer DTC replacement site and the evidence base behind it.

Source alignment:

- Current local tree: `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/paperclip_org_tree.md`
- Paperclip task model: `/vol1/1000/projects/paperclip/doc/TASKS.md`
- Paperclip architecture: `/vol1/1000/projects/paperclip/docs/start/architecture.md`

Projects:

| Project | Local Issue IDs | Primary Outputs | Boundary |
| --- | --- | --- | --- |
| `00_scope_and_source_registry` | `LAB-001` | `scope_boundary.md`, `source_registry.yaml`, `source_cards.tsv` | No DTC/Boss Gallery mixing. |
| `01_product_channel_intelligence` | `LAB-002`, `LAB-003`, `LAB-004`, `LAB-005` | product master, sample dossiers, ASIN sample, method failures | No fake reviews, ratings, Amazon claims, or unknown fields. |
| `02_public_media_asset_library` | `LAB-006` | media manifest, scene index, asset caveats | Public capture is not legal clearance. |
| `03_commerce_decision_layer` | `LAB-007` | portfolio, shopper mission, hero/nav/PDP/bundle matrices | Design decisions must trace to evidence. |
| `04_pure_dtc_prototype` | `LAB-008` | prototype build/URL, route map, QA screenshots/reports | No Paperclip board, AI Studio, claim gate, or internal matrix. |
| `05_ai_boss_gallery` | `LAB-009` | Boss Gallery pages, claim ledger, blocked claims, QA | Separate internal demo; result first, then control. |
| `06_executive_pack` | `LAB-010` | executive pack, artifact index, handoff | Summarize evidence and next build scope. |

Owner roles:

- Program Strategist / Evidence Steward
- Product Data Analyst
- Product Intelligence Analyst
- Marketplace Intelligence Analyst
- Media Asset Researcher
- Commerce Strategist / UX Architect
- UX Designer / Prototype Engineer
- AI Demo Producer / Claim Steward

Operating rule:

- Use Paperclip's single-assignee model. If an issue needs multiple agents, create sub-issues rather than assigning multiple owners to one unit of work.

### Active Org 2: Paperclip Runtime & Evidence Kernel

Purpose:

- Keep issue execution evidence-backed, claim-safe, browser-tested, and resumable.

Source alignment:

- Current local kernel: `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/`
- Paperclip execution policy: `/vol1/1000/projects/paperclip/docs/guides/execution-policy.md`
- Maint verified delegation ADR: `/vol1/maint/docs/control_plane/adr/ADR-001-chief-verified-delegation-control-plane.md`

Projects:

| Project | Local Issue IDs | Primary Outputs | Boundary |
| --- | --- | --- | --- |
| `00_issue_evidence_contract` | `PCL-001` | `issue_evidence_contract.md`, closeout rules | Agent self-report does not count as evidence. |
| `01_gate_kernel` | `PCL-001` | `gate_kernel_v0.md` | Mandatory gates are only those needed for current deliverables. |
| `02_runtime_policy_thin_gate` | governance follow-up | skill/MCP/runtime decision notes | No write actuator or chief direct mutation. |
| `03_visual_browser_qa` | Browser Harness support | QA templates, screenshot harness | QA/evidence support only, not autonomous brain. |
| `04_agent_delegation_and_handoff` | future Paperclip connection | handoff templates, issue/evidence IDs | Sidecar remains responsible for promotion decisions. |

Owner roles:

- Paperclip Program Architect
- Runtime Governance Steward
- Browser Harness Maintainer
- Claim Steward
- Evidence Steward

Operating rule:

- Treat Paperclip as control plane, not execution plane. Paperclip organizes issues, evidence, runs, approvals, and budgets; actual code/design/browser work happens through bounded agents and artifacts.

### Read-Only Area: Multica Archive / Pattern Library

Purpose:

- Preserve lessons from Multica and prior runtime work without making Multica an active Labebe control plane.

Source paths:

- `/vol1/maint/docs/2026-04-23_multica_paperclip_finbot_history_audit_handoff.md`
- `/vol1/maint/docs/2026-04-23_multica_hermes_operating_spec_v2.md`
- `/vol1/maint/docs/control_plane/2026-04-27_multica_chief_completion_summary.md`
- `/vol1/maint/docs/control_plane/2026-04-27_chief_autonomy_retrospective.md`
- `/vol1/1000/projects/multica/HANDOFF_ARCHITECTURE_AUDIT.md`
- `/vol1/1000/projects/multica/docs/workspace-url-refactor-proposal.md`
- `/vol1/1000/projects/multica/docs/plans/2026-04-16-remove-onboarding-and-fix-daemon-bootstrap.md`
- `/vol1/1000/projects/multica/CLAUDE.md`

Allowed extraction:

- "issue created is not progress"
- "issue done does not prove product ready"
- read-only first, permission selftest before runtime execution
- URL/context identity must be explicit and shareable
- workspace/organization scoping must be visible
- stale WebSocket/cache and localStorage context bugs are real governance risks
- runtime pool and heartbeat load must be bounded
- cancelled/failed smoke fixtures are evidence of failure, not success

Forbidden extraction:

- Bulk Multica issue migration.
- Reviving `assistant-factory` or `assistant-ops` as sprint control planes.
- Treating completed Multica issue counts as Labebe readiness proof.
- Using Multica assistant blueprints as Labebe active roles.
- Importing old observer/proposer architecture as mandatory Paperclip design.
- Adding native write worker or issue mutation authority to the Labebe sprint.

Potential future local output if needed:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/multica_lessons_readonly.md`
- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/failed_fixtures_do_not_count_as_success.md`

Those files are not required for this worker because this document captures the active mapping.

## Status Mapping

Local sprint status values from `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/05_ISSUE_INDEX_AND_ACCEPTANCE.md` should map to Paperclip workflow categories as follows:

| Local Status | Paperclip Category | Meaning | Allowed Transition |
| --- | --- | --- | --- |
| `draft` | Backlog | Defined but not active. | To `ready` only after inputs/outputs/guardrails exist. |
| `ready` | Unstarted | Accepted into execution plan. | To `active` when assigned. |
| `active` | Started | Work underway. | To `review`, `blocked`, or `deferred`. |
| `blocked` | Started or Backlog with blocker label | Waiting on concrete dependency. | To `active` only when blocker path is resolved. |
| `review` | Started / In Review | Outputs exist and need gate review. | To `done` only with evidence. |
| `done` | Completed | Closeout evidence accepted. | Terminal unless reopened with new issue. |
| `deferred` | Cancelled or Backlog | Explicitly out of sprint. | Reopen only through new decision. |

Do not count these as done:

- issue exists;
- run exists;
- agent says completed;
- page opens;
- screenshot exists with no visual judgment;
- old Multica issue is `done`;
- GStack-style review ran without Paperclip artifact capture.

## Issue Contract To Use

Every non-smoke issue should follow the Multica Hermes v2 issue contract from `/vol1/maint/docs/2026-04-23_multica_hermes_operating_spec_v2.md`, adapted into Paperclip:

```markdown
## Goal
What outcome should exist after this issue?

## Inputs
Which docs, repos, files, prior decisions, URLs, or data artifacts must the agent read?

## Output
What artifact paths must be produced or updated?

## Acceptance
How do we know it is good enough? Include browser/visual/claim gates when relevant.

## Guardrails
What must not be done?

## Escalation
When should the agent stop, mark blocked, or ask sidecar/user?

## Next Step
What should happen after this issue is accepted?
```

Local target for this pattern:

- `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/issue_evidence_contract.md`

## Runtime And Evidence Boundary

Maint has already separated product delegation maturity from actuation authority:

- Product goal can reach supervised delegation before live write autonomy.
- Actuation requires typed action schema, deterministic policy, postcondition verifier, and audit ledger.

Apply that to Labebe:

| Area | Allowed Now | Forbidden Now |
| --- | --- | --- |
| Paperclip issue planning | Create or map issue contracts, owner roles, evidence paths | Direct chief mutation of issue status, assignment, project, auth, MCP, skill, runtime |
| Browser QA | Run or define screenshot, console, route, mobile/desktop checks | Let QA harness touch production sessions or become a new autonomous control plane |
| Skills/MCP | Use existing governed skills/MCPs when needed for a deliverable | Bulk skill import, GStack install, tool routing injection, unscoped browser/admin tokens |
| DTC | Commerce prototype and QA evidence | Paperclip UI, AI workflow, internal matrix, fake claims |
| Boss Gallery | Result-first AI demo with claim gate and evidence links | Present concepts as production CAD/safety/demand proof |

## GStack Method Placement

Use GStack as an artifact method source:

| GStack Method | Source Path | Paperclip Artifact | Use Condition | Prohibited Part |
| --- | --- | --- | --- | --- |
| Browser QA taxonomy | `/vol1/1000/projects/gstack/qa/references/issue-taxonomy.md` | `browser_qa_report.md` | DTC/Boss Gallery review before user-facing handoff | GStack runtime, telemetry, proactive mode |
| QA report template | `/vol1/1000/projects/gstack/qa/templates/qa-report-template.md` | QA report structure | When a URL/build is review-ready | Auto-fix loop unless separately assigned |
| Pre-landing review checklist | `/vol1/1000/projects/gstack/review/checklist.md` | advisory review notes | Before implementation handoff or production move | Treating source review as visual QA |
| Design checklist | `/vol1/1000/projects/gstack/review/design-checklist.md` | design review report | Frontend/design changes | One-size-fits-all AI-slop policing without Labebe context |
| Browser command model | `/vol1/1000/projects/gstack/BROWSER.md` | Browser Harness P0 contract | Need repeatable screenshot/console/interaction evidence | Remote token sharing unless required |
| Guard/freeze concept | `/vol1/1000/projects/gstack/guard/SKILL.md`, `/vol1/1000/projects/gstack/freeze/SKILL.md` | scope-limited worker instruction | Parallel worker file boundaries | Relying on GStack hooks as enforcement here |

## Concrete Next Actions

| Action | File Path | Responsible Role | Acceptance |
| --- | --- | --- | --- |
| Keep `paperclip_org_tree.md` at two active orgs and one read-only archive | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/paperclip_org_tree.md` | Paperclip Program Architect | No Skill Foundry, Browser/Vision Lab, or Multica active org appears in sprint org tree. |
| Add issue contract snippet above to local evidence contract when next edited | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_kernel/issue_evidence_contract.md` | Runtime Governance Steward | Each issue contract has Goal, Inputs, Output, Acceptance, Guardrails, Escalation, Next Step. |
| Connect Boss Gallery cards to evidence IDs | `paperclip_runtime_duel/outputs/boss_gallery_v0/index.html`; `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/boss_gallery_v0/design_record.md` | AI Demo Producer / Claim Steward | Every demo card links to source artifact and claim status. |
| Keep DTC route map pure | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/dtc_prototype_v2/route_map.md` | UX Designer / Prototype Engineer | No internal demo routes, no Paperclip navigation, no claim gate surface. |
| Add GStack-derived QA severities to Browser Harness template if not already present | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/browser_qa_report_template.md` | Browser Harness Maintainer | Critical/high/medium/low severity and category taxonomy are represented. |
| Record runtime policy as "proposal only" unless typed actuator exists | `/vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/skill_runtime_governance/maint_update_plan.md` | Runtime Governance Steward | No future plan says chief or worker may directly write Multica/Paperclip state. |

## Final Organizational Boundary

For this masterplan:

```text
Labebe Commercial Studio
  owns product, marketplace, media, DTC, Boss Gallery, executive pack

Paperclip Runtime & Evidence Kernel
  owns issue contract, gates, evidence manifest, browser QA, runtime policy notes

Multica Archive / Pattern Library
  read-only lessons only

GStack
  method/checklist source only

maint
  machine/runtime governance reference, updated later through a separate doc-only plan
```

This mapping keeps the project narrow enough to finish while still absorbing the useful history from maint, Paperclip, Multica, and GStack.
