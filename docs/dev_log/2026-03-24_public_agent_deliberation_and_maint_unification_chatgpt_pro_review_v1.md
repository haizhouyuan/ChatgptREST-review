# 2026-03-24 Public Agent Deliberation And Maint Unification ChatGPT Pro Review v1

## Source

- reviewer: `ChatGPT Pro`
- review target:
  - `docs/dev_log/2026-03-24_public_agent_deliberation_and_maint_unification_blueprint_v1.md`
  - `docs/dev_log/2026-03-24_public_agent_deliberation_and_maint_unification_plan_v1.md`
  - `docs/dev_log/2026-03-24_public_agent_deliberation_and_maint_unification_walkthrough_v1.md`
- mirror source commit: `d84fe718e1478c59324e753a3637ed87b304d1fc`
- local raw export copy:
  - [chatgpt_pro_answer_v2.md](/vol1/1000/projects/ChatgptREST/artifacts/reviews/2026-03-24_deliberation_maint_unification_dual_review/chatgpt_pro_answer_v2.md)

## Review

I re-checked the mirror metadata first: the current review mirror is aligned to source commit `d84fe718e1478c59324e753a3637ed87b304d1fc`, and `REVIEW_CONTEXT.md` reflects the same review branch/commit.

## Findings

1. **Critical — the blueprint contradicts its own “single northbound entry” rule.**
   The strongest idea in the blueprint is “Public Agent stays the only general northbound entry,” and “deliberation is an internal mode under Public Agent.” But the same blueprint then proposes separate public MCP families for `deliberation_start/status/cancel/attach` and `work_package_*`. That is not a single public entry anymore; it is a second northbound contract family on the same server. The current public MCP is intentionally minimal and only exposes `advisor_agent_turn`, `advisor_agent_status`, and `advisor_agent_cancel`; that pattern is much more consistent with a true single-entry architecture. Problematic paths: `2026-03-24_public_agent_deliberation_and_maint_unification_blueprint_v1.md`; `chatgptrest/mcp/agent_mcp.py`.

2. **Critical — review is still a parallel public subsystem, not a real internal execution mode of Public Agent.**
   The running code still treats consult/review as its own public surface and its own state universe. `app.py` loads `consult_v1` as a core router alongside `advisor_v3` and `agent_v3`; `routes_consult.py` still exposes `POST /v1/advisor/consult` and `GET /v1/advisor/consult/{consultation_id}`; and `routes_agent_v3.py` handles `goal_hint in {"consult", "dual_review"}` by handing off to the consult defaults and minting a separate `consultation_id`. Worse, `routes_consult.py` stores consultations in an in-memory `_consultations` map, which is exactly the kind of side ledger the blueprint says it does not want. Problematic paths: `chatgptrest/api/app.py`; `chatgptrest/api/routes_consult.py`; `chatgptrest/api/routes_agent_v3.py`.

3. **High — removing `guardian` now would drop real policy and lifecycle behavior that the blueprint does not fully remap.**
   The end-state of “no third maintenance brain” is right, but the proposed absorb map is too shallow for the current codebase. Today the guardian sidecar is still active in topology with `wake_agent: main` and `wake_session: main-guardian`; its runner is not just “patrol + notify,” it also carries ChatGPT Pro trivial-prompt checks, violation-status filtering, system-client classification, guarded agent execution with `repair.check` guidance, and client-issue stale/close sweeps. By contrast, `maintagent` is still configured read-mostly with only `sessions_send` and `sessions_list`, and the rebuild script still frames it as a watchdog for `main`, not a replacement controller. If you delete guardian in phase 1, you will almost certainly drop live policy coverage unless every one of those behaviors is explicitly reassigned first. Problematic paths: `config/topology.yaml`; `ops/openclaw_guardian_run.py`; `scripts/rebuild_openclaw_openmind_stack.py`.

4. **High — “maintagent owns canonical machine context from `/vol1/maint`” is directionally good, but the actual wiring is not there yet.**
   The repo already has shared maint-memory helpers that read `/vol1/maint/exports` and inject compact bootstrap memory into maint-daemon Codex prompts and SRE lane prompts. So `/vol1/maint` is already a shared maintenance substrate, not something that maintagent uniquely owns in execution. At the same time, OpenClaw still defines `maintagent` as a volatile, minimal-tool, read-mostly watchdog in `/vol1/1000/openclaw-workspaces/maintagent`, and the extension set under `openclaw_extensions/` is generic OpenMind plumbing rather than a maint-specific integration layer. The blueprint is right about canonical source location, but it overstates maintagent readiness as the maintenance brain. Problematic paths: `chatgptrest/ops_shared/maint_memory.py`; `scripts/rebuild_openclaw_openmind_stack.py`; `openclaw_extensions/`.

5. **Medium-high — the deterministic work-package plane is coherent in concept, but the current tooling is still CLI/manual and partly fail-open.**
   This split is one of the better architectural ideas in the blueprint, but it is not yet realized. `ops/code_review_pack.py` is a local CLI packer, not a server-side compiler; in public-sync mode it only emits warnings when Gemini file-count or total-size limits are exceeded; and the workflow still tells humans to “Always verify uploads,” which means critical validation is not deterministic or server-enforced. I did not see evidence of a durable work-package ledger, upload attestation, or the kind of strict fail-closed compiler behavior that the blueprint now assumes. Problematic paths: `ops/code_review_pack.py`; `.agents/workflows/code-review-upload.md`; `ops/sync_review_repo.py`.

6. **Medium — the hard channel rules are mostly correct in substance, but they are fragmented across too many layers.**
   The repo already encodes the right intent in several places: GeminiDT/web-only Gemini review must stay on `gemini_web.ask`; ChatGPT Pro trivial/smoke prompts are blocked or discouraged; and the wrapper enforces the 61-second spacing rule. But those rules are split across workflow docs, wrapper docs, guardian policy, and consult model selection, while the low-level skill still documents legacy `provider=chatgpt` and `provider=gemini` mappings. So the blueprint is right to insist on “hard policy,” but wrong to assume the system already has one centralized enforcement point. Problematic paths: `.agents/workflows/code-review-upload.md`; `skills-src/chatgptrest-call/SKILL.md`; `chatgptrest/api/routes_consult.py`; `ops/openclaw_guardian_run.py`.

7. **Medium — the rollout phases are not in the safest order.**
   The blueprint/walkthrough want to absorb guardian first, make maintagent canonical second, add deterministic work-package tools third, and only then add deliberation modes. That sequencing is backwards for the current repo state. Guardian is still live and carrying policy semantics; the deterministic packaging plane is still immature; and consult state is not yet merged into the Public Agent ledger. I would move “centralized hard-policy + deterministic compiler” and “maintagent `/vol1/maint` plumbing” before any guardian removal, and I would not ship `dual_review`/`red_blue_debate` until consult-state unification is done. Problematic paths: `2026-03-24_public_agent_deliberation_and_maint_unification_blueprint_v1.md`; `2026-03-24_public_agent_deliberation_and_maint_unification_walkthrough_v1.md`; `config/topology.yaml`; `ops/openclaw_guardian_run.py`; `ops/code_review_pack.py`.

## Open Questions / Assumptions

- I only had two local 2026-03-24 attachments available in `/mnt/data`: the blueprint and the walkthrough. The implementation plan file referenced in the original prompt was not present in the provided local materials, so the phase/order judgment was based on those two docs plus the repo state.
- Are `deliberation_*` and `work_package_*` meant to be public tools for general coding agents, or internal/operator-only surfaces hidden behind `advisor_agent_turn`? That single choice changes scope items 1 and 2 more than anything else.
- What exactly is `master_single` in a repo-first review flow: canonical prompt, manifest, executive brief, or something else? If it is mandatory, who authors it, and how is drift between repo state and `master_single` prevented?
- Does “maintagent owns machine context” mean stewardship of the canonical source, or exclusive consumption? Current code already shares `/vol1/maint` into maint-daemon and SRE prompt bootstrap.
- What is the deprecation plan for `/v1/advisor/consult`, older advisor surfaces, and any direct consult clients? Without an explicit forwarding/removal path, “single northbound Public Agent” remains aspirational, not operational.
- Will blueprint naming (`gemini_dt`) replace current route/model naming (`gemini_deepthink` / `gemini_dr`), or are those intended to coexist? The migration path is not stated.

## Verdict

This is a **sound direction, but not yet a sound next-step architecture as written**. The parts agreed with are the important ones: keep review under Public Agent instead of creating a separate public Review Controller, and keep Maint Controller separate because `sre.fix_request` already embodies a distinct authority/risk boundary with constrained next routes and allowlist-aware runtime actions. The parts not bought yet are the new top-level deliberation tool family, the early guardian removal, and the assumption that maintagent + deterministic packaging are already specified tightly enough to carry the new design.

Net answers to scope:

- `(1)` yes in principle, no in current specification
- `(2)` yes
- `(3)` yes
- `(4)` yes in direction, not yet in implementation detail
- `(5)` right destination, incomplete mapping
- `(6)` coherent but still immature
- `(7)` mostly right in substance, but fragmented and under-enforced
- `(8)` no, the phases are not in the safest order
