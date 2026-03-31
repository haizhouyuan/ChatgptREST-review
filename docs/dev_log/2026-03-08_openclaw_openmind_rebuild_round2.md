# 2026-03-08 OpenClaw OpenMind Rebuild Round 2

## Why

The first rebuild blueprint captured the right direction, but the repo automation
was still drifting from the live, working stack:

- rebuild script still pointed OpenMind plugins at `127.0.0.1:18713`
- maint heartbeat still checked `18713`
- stock bundled plugins were still being mirrored into `~/.openclaw/extensions`,
  which recreates duplicate-plugin drift
- plugin `allow` / `load` state was not preserved by `build_config`
- helper docs still implied manual symlink installs instead of the official
  `openclaw plugins install --link` flow

## What changed

### `scripts/rebuild_openclaw_openmind_stack.py`

- default OpenMind base URL now follows the integrated host reality:
  `http://127.0.0.1:18711`
- added `--openmind-base-url` and `--openclaw-bin` overrides
- switched OpenMind plugin install flow to the official OpenClaw CLI:
  `openclaw plugins install --link <path>`
- stopped copying/symlinking bundled upstream plugins into
  `~/.openclaw/extensions`
- preserved existing `plugins.allow`, `plugins.load`, and `plugins.installs`
  state instead of dropping them during rebuild
- added quiet 3h heartbeats for `research-orch` and `openclaw-orch`
- updated main/maint heartbeat guidance to match actual non-blocking
  `sessions_spawn` behavior and the live OpenMind port
- Feishu account normalization now materializes `appSecretFile` into
  `appSecret` when the file exists, which matches the current local startup path

### `scripts/install_openclaw_cognitive_plugins.py`

- updated the example config snippet to `127.0.0.1:18711`
- clarified that the official best-practice path is
  `openclaw plugins install --link`

### Integration docs

- `openclaw_openmind_rebuild_blueprint_20260308.md`
  now explicitly says:
  - integrated-host OpenMind lives on `18711`
  - bundled plugins should come from the upstream runtime bundle
  - local development plugins should be linked via the OpenClaw CLI
- `openclaw_cognitive_substrate.md`
  now recommends official CLI link-install first, with the Python helper as a
  fallback

## Validation

- `./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py tests/test_install_openclaw_cognitive_plugins.py`
- `./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py scripts/install_openclaw_cognitive_plugins.py tests/test_rebuild_openclaw_openmind_stack.py`
- `./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --dry-run`

All passed after the adjustments above.
