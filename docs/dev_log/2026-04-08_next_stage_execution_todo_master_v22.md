# Next Stage Execution TODO Master V22

## Objective

Complete the compressed ingress-quality policy wave on top of the existing execution fabric.

## Checklist

- [x] Freeze execution plan v2
- [ ] Finalize ingress normalization in `task_intake.py`
- [ ] Finalize `visit_cooperation_prep` scenario pack
- [ ] Finalize Codex default routing policy in `routes_agent_v3.py`
- [ ] Finalize posture-aware clarify behavior in `ask_strategist.py`
- [ ] Finalize interaction-learning module and runtime integration
- [ ] Add focused tests for task intake, scenario packs, strategy, interaction learning, and route behavior
- [ ] Add raw-ingress quality dataset / harness
- [ ] Run focused pytest suite
- [ ] Run work-sample validation for the new dataset
- [ ] Run doc obligations check
- [ ] Run GitNexus detect-changes before each commit
- [ ] Commit meaningful code batch
- [ ] Commit quality-harness / docs batch
- [ ] Run repo closeout

## Guardrails

- Use existing execution infrastructure; do not rebuild a new lane system.
- Keep changes scoped to ingress quality, routing policy, closure contract, and interaction learning.
- Do not touch unrelated dirty files already present in the worktree.
