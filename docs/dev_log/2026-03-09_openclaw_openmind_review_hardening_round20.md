# 2026-03-09 OpenClaw OpenMind Review Hardening Round 20

## Trigger

After the controlled-access and provenance fixes landed, the live `lean` verifier was still failing on three review-facing checks:

- `openmind_tool_round`
- `main_sessions_spawn_negative_probe`
- `main_subagents_negative_probe`

The important part was that the direct reply checks were already passing:

- `OPENMIND_OK ...`
- `SESSIONS_SPAWN_UNAVAILABLE ...`
- `SUBAGENTS_UNAVAILABLE ...`

So this was not a shell/runtime regression. It was a verifier evidence-path bug.

## Root Cause

`ops/verify_openclaw_openmind_stack.py` resolved the main transcript by reading `sessions.json` and trusting `sessionId`.

On the current upstream runtime, that is not reliable enough for these verification probes:

- the session key `agent:main:main` is rebound to the latest probe run
- the runtime keeps the canonical transcript path in `sessionFile`
- `sessionId` can remain as an alias-like value that does not point at the actual JSONL transcript being appended

That caused the verifier to inspect a stale/nonexistent transcript path and report `missing user marker in transcript` even though the live probe conversation had succeeded.

## Changes

- updated `ops/verify_openclaw_openmind_stack.py`
  - `resolve_session_transcript_path()` now prefers `sessionFile` and only falls back to `sessionId`
- updated `tests/test_verify_openclaw_openmind_stack.py`
  - added coverage that locks the new `sessionFile` precedence behavior
- refreshed live verifier evidence after the fix:
  - `ops`: `artifacts/verify_openclaw_openmind/20260309T101413Z/verify_openclaw_openmind_stack.md`
  - `lean`: `artifacts/verify_openclaw_openmind/20260309T101239Z/verify_openclaw_openmind_stack.md`

## Validation

```bash
./.venv/bin/pytest -q \
  tests/test_verify_openclaw_openmind_stack.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_sync_review_repo.py

./.venv/bin/python -m py_compile \
  ops/verify_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py

timeout 240 ./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --expected-topology lean

./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --topology ops
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
timeout 240 ./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --expected-topology ops

./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --topology lean
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
```

## Outcome

Both live verifier runs now pass their transcript-sensitive checks:

- `openmind_tool_round`
- `main_sessions_spawn_negative_probe`
- `main_subagents_negative_probe`

That removes the last remaining verifier-side false negative in the public review package. At this point the remaining uncertainty is in the external reviewer verdict itself, not in an unclosed local proof gap.
