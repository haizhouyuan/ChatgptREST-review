# Convergence Test Program TODO

Date: 2026-03-13  
Repo: ChatgptREST  
Branch: `codex/convergence-validation-program-20260313`  
Worktree: `/vol1/1000/projects/ChatgptREST/.worktrees/convergence-validation-program-20260313`  
Owner: Codex

Status: in_progress

This revision continues the convergence validation program after tranche 2.

---

## Objective

Close the next repository-local gaps that still block stronger Gate B/C
confidence:

- Feishu WS duplicate-delivery protection
- deterministic regression coverage for duplicate replay handling
- better grounding for live-wave evidence and operator-facing interpretation

Do not overwrite existing versions.

---

## Scope For This Revision

- [ ] add duplicate replay protection to `FeishuWSGateway`
- [ ] add duplicate-delivery regression tests for Feishu WS ingress
- [ ] validate the updated gateway regression suite
- [ ] record a walkthrough for tranche 3
- [ ] commit each meaningful stage
- [ ] refresh PR #160
- [ ] close out the tranche

---

## Working Notes

- `FeishuWSGateway` blast radius is currently low and limited to the advisor
  channel surface, which makes it a good candidate for an incremental business-
  flow hardening change.
- The current WS gateway sends an ack and forwards the message, but does not
  defend itself against repeated delivery of the same `message_id`.
- Existing live evidence already shows provider-specific runtime truth; this
  revision should keep that honesty model rather than flattening every result
  into pass/fail.

---

## Planned Deliverables

- [ ] Feishu WS duplicate-claim support
- [ ] Feishu duplicate-replay tests
- [ ] `docs/dev_log/2026-03-13_convergence_test_program_walkthrough_v5.md`

---

## Validation Target

Recommended command set for this revision:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_feishu_ws_gateway.py
```

---

## Commit Plan

- Commit 1: add tranche todo v5
- Commit 2: add Feishu WS dedup hardening + regression tests
- Commit 3: add walkthrough v5, refresh PR, and closeout
