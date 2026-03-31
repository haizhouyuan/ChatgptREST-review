# 2026-03-24 Public Agent Deliberation And Maint Unification Development Plan v1

## Objective

Implement the blueprint in a way that:

- does not create a second public controller peer to Public Agent
- removes `guardian` cleanly
- makes `maintagent` the maintenance brain with canonical machine context
- adds deterministic work-package tooling under the MCP server
- adds `deliberation_start` as Public Agent's high-value review mode
- aligns wrappers, skills, and agent docs so usage is obvious by default

## Delivery Strategy

Do this in phased slices. Do **not** try to land all moving parts in one patch.

## Todo List

### Phase 0. Baseline And Contract Lock

- [ ] Reconfirm current `Public Agent` MCP and `/v3/agent/*` extension points
- [ ] Reconfirm current dual-review/prompt assets in `ask_contract.py`, `prompt_builder.py`, and `routes_consult.py`
- [ ] Reconfirm current deterministic review-pack/review-repo tooling
- [ ] Reconfirm current `maint_daemon`, `maintagent`, `guardian`, and `/vol1/maint` context wiring
- [ ] Write or update contract docs for:
  - [ ] `deliberation_start`
  - [ ] deterministic work-package tools
  - [ ] hard channel rules

### Phase 1. Guardian Removal And Maintenance Responsibility Migration

- [ ] Identify every live or documented `guardian` responsibility
- [ ] Move deterministic sweep/notify/housekeeping into `maint_daemon`
- [ ] Move judgment/escalation-to-main semantics into `maintagent`
- [ ] Retire `chatgptrest-guardian.service` and `chatgptrest-guardian.timer`
- [ ] Keep only a compatibility shim if required during rollout
- [ ] Update topology/runbook docs so `guardian` no longer appears as a first-class maintenance brain

### Phase 2. `maintagent` Machine-Context Unification

- [ ] Define one canonical machine-context load path from `/vol1/maint`
- [ ] Teach `maintagent` to default-load:
  - [ ] memory index
  - [ ] machine snapshot
  - [ ] repo/workspace snapshot
  - [ ] JSON packet
- [ ] Keep ordinary agents on pointer-only context, not full preload
- [ ] Add validation proving `maintagent` sees current canonical machine context
- [ ] Update OpenClaw role docs/prompts if needed

### Phase 3. Deterministic Work-Package MCP Tools

- [ ] Add `work_package_prepare`
- [ ] Add `work_package_validate`
- [ ] Add `work_package_compile_channel`
- [ ] Add `work_package_submit`
- [ ] Add `work_package_status`
- [ ] Add `work_package_cancel`
- [ ] Make them deterministic, auditable, and fail-closed
- [ ] Reuse existing:
  - [ ] `ops/code_review_pack.py`
  - [ ] `ops/sync_review_repo.py`
  - [ ] code-review-upload workflow rules

### Phase 4. `deliberation_start` Single-Review Path

- [ ] Add MCP/API contract for `deliberation_start`
- [ ] Add `deliberation_status`
- [ ] Add `deliberation_cancel`
- [ ] Add `deliberation_attach`
- [ ] Implement `reasoning_mode=single_review`
- [ ] Reuse Public Agent session/lifecycle/delivery model
- [ ] Ensure channel policy is enforced before reviewer submit

### Phase 5. `dual_review`

- [ ] Implement `target=dual`
- [ ] Submit independent first-pass reviews to:
  - [ ] `ChatGPT Pro`
  - [ ] `GeminiDT`
- [ ] Preserve independence before synthesis
- [ ] Add structured compare/synthesis stage
- [ ] Return structured result object with:
  - [ ] shared facts
  - [ ] disagreements
  - [ ] known unknowns
  - [ ] recommendation strength

### Phase 6. `red_blue_debate`

- [ ] Add `reasoning_mode=red_blue_debate`
- [ ] Implement stage order:
  - [ ] `independent_pass`
  - [ ] `role_assignment`
  - [ ] `red_attack`
  - [ ] `blue_defense`
  - [ ] `arbiter_verdict`
- [ ] Default role map:
  - [ ] `Blue = ChatGPT Pro`
  - [ ] `Red = GeminiDT`
- [ ] Allow explicit override
- [ ] Add structured verdict output contract

### Phase 7. Review Memory And Runbook Selector

- [ ] Define review-memory boundary:
  - [ ] `domain_memory`
  - [ ] `review_memory`
  - [ ] `artifact_memory`
- [ ] Add review runbook selector
- [ ] Create at least:
  - [ ] `code_review_runbook`
  - [ ] `strategy_review_runbook`
  - [ ] `framework_review_runbook`
  - [ ] `report_generation_runbook`
  - [ ] `red_blue_debate_runbook`
  - [ ] `gemini_dt_channel_runbook`
  - [ ] `repo_first_review_runbook`
- [ ] Inject memory/runbook context without creating a second truth source

### Phase 8. Wrapper / Skill / Agent-Doc Alignment

- [ ] Update wrapper so it becomes a thin MCP client for deliberation
- [ ] Keep local-only UX features such as summary-file writing in the wrapper
- [ ] Update:
  - [ ] `AGENTS.md`
  - [ ] `CLAUDE.md`
  - [ ] `GEMINI.md`
  - [ ] skill docs
  - [ ] workflow docs
- [ ] Make defaults explicit:
  - [ ] ordinary task -> `advisor_agent_turn`
  - [ ] high-value review -> `deliberation_start`
  - [ ] maintenance -> `maintagent` / Maint Controller

### Phase 9. Validation Packs

- [ ] Add deterministic work-package validation pack
- [ ] Add deliberation single-review validation pack
- [ ] Add dual-review validation pack
- [ ] Add red/blue debate validation pack
- [ ] Add `maintagent` machine-context validation pack
- [ ] Add guardian-removal / responsibility-migration validation pack
- [ ] Add integrated northbound usage validation proving wrappers/agents follow the same default path

### Phase 10. Rollout And Cutover

- [ ] Start with docs + validation harness
- [ ] Land deterministic package tools first
- [ ] Land `single_review` before `dual_review`
- [ ] Land `dual_review` before `red_blue_debate`
- [ ] Retire `guardian` only after `maint_daemon + maintagent` absorb duties and validation is green
- [ ] Cut wrappers/docs after live MCP surfaces are ready

## Hard Policy Checklist

These rules must be tested, not just documented.

- [ ] `GeminiDT` only uses `gemini_web.ask`
- [ ] no Gemini CLI downgrade for `GeminiDT`
- [ ] `ChatGPT Pro` trivial/smoke remains blocked
- [ ] repo-first remains default for code/text-heavy review
- [ ] attachment-first only for raw attachment fidelity cases
- [ ] `master_single` missing -> fail closed
- [ ] required material not represented in `master_single` -> fail closed
- [ ] Gemini file overflow -> fail closed
- [ ] upload-chip mismatch -> fail closed
- [ ] no hidden target rerouting

## Validation Targets

### Deterministic Work-Package Plane

Must prove:

- pack preparation is deterministic
- validation catches missing `master_single`
- validation catches required-source omissions
- Gemini file-cap enforcement works
- channel compilation selects the expected transport

### Deliberation Plane

Must prove:

- `single_review` works through Public Agent session semantics
- `dual_review` keeps independent first passes
- `red_blue_debate` follows the required stage order
- `deliberation_status` exposes stage and reviewer channel state
- `deliberation_attach` returns stable operator guidance

### Maintenance Plane

Must prove:

- `guardian` responsibilities are absorbed
- `maint_daemon` performs the deterministic portions
- `maintagent` sees canonical machine context and performs the judgment portions
- `main` only receives net-new actionable deltas

## Risks

### Risk 1. Silent Re-Creation Of A Second Public Controller

Mitigation:

- keep `deliberation_start` under Public Agent MCP, not as a separate top-level product surface

### Risk 2. LLM Encroachment Into Deterministic Tooling

Mitigation:

- keep package compile/validate/submit deterministic
- treat model reasoning as orchestration and synthesis only

### Risk 3. Guardian Responsibilities Partially Survive In Two Places

Mitigation:

- document a one-by-one absorption map
- remove timer/service once coverage proves green

### Risk 4. Review Memory Becomes A New Polluted Truth Source

Mitigation:

- define strict memory boundaries
- distinguish facts, judgments, and known unknowns

### Risk 5. Wrapper Diverges From MCP Semantics

Mitigation:

- force wrapper to become a thin client
- keep local UX tasks local, but move server semantics to MCP

## Non-Goals For This Development Plan

This plan does **not** include:

- a full GUI/TUI review operator product
- new external provider capabilities beyond current allowed lanes
- general webhook-style external answer push for arbitrary third-party systems
- full-stack provider completion proof
- heavy execution lane approval

## Recommended Implementation Order

1. guardian absorption + maintenance responsibility rewrite
2. `maintagent` canonical machine-context wiring
3. deterministic work-package tools
4. `deliberation_start` with `single_review`
5. `dual_review`
6. `red_blue_debate`
7. memory/runbook selector
8. wrapper/doc alignment
9. integrated validation packs

## Done Condition

This development plan is complete only when:

- `guardian` is removed or explicitly downgraded to a short-lived compatibility shim
- `maintagent` holds canonical machine context by default
- `maint_daemon` is the only deterministic maintenance patrol/evidence plane
- deterministic work-package tools are live on MCP
- `deliberation_start` is live for `single_review`, `dual_review`, and `red_blue_debate`
- wrappers and agent docs all teach the same defaults

## One-Line Summary

Build this as:

- **one public task brain**
- **one internal deliberation plane**
- **one maintenance brain**
- **one deterministic packaging/gating layer**

and remove every leftover parallel attention brain on the path.
