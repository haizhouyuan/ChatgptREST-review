# 2026-03-09 OpenClaw + OpenMind Review Hardening Round 9

## Goal

Remove residual private-path noise from the public review baseline before the next external review round completes.

## Change

Removed two unused constants from `scripts/rebuild_openclaw_openmind_stack.py`:

- `UPSTREAM_OPENCLAW_ROOT`
- `OPENCLAW_WORKSPACE_ROOT`

Why:

- they were not referenced anywhere in the script
- they pointed at host-private local paths
- leaving them in the public review branch created avoidable ambiguity about whether the baseline still depended on a local OpenClaw worktree

This is a hardening/clarity cleanup, not a behavior change.

## Validation

```bash
./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py
./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py
```

## Outcome

The public rebuild script no longer carries dead private-path constants that could be misread as part of the supported baseline.
