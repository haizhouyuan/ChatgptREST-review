# 2026-03-09 OpenClaw/OpenMind Rebuild Round 5

## Summary

- Corrected the rebuild script so it no longer injects a global `channels.defaults.heartbeat` override into `~/.openclaw/openclaw.json`.
- Preserved user-authored heartbeat defaults and only scrubbed the exact legacy managed override that had been introduced by the previous rebuild round.
- Rebuilt the live OpenClaw/OpenMind stack and verified that removing the global heartbeat suppression did not immediately reintroduce `feishu:heartbeat` failures.
- Confirmed that the remaining runtime blocker is not heartbeat visibility. It is stale OpenAI Codex OAuth material in some agent auth stores, especially `main`.

## Why This Round Was Necessary

The previous rebuild round forced:

```json
{
  "channels": {
    "defaults": {
      "heartbeat": {
        "showOk": false,
        "showAlerts": false,
        "useIndicator": true
      }
    }
  }
}
```

That fixed a noisy symptom, but it was the wrong layer. Upstream OpenClaw treats `channels.defaults.heartbeat` as a global visibility rule for deliverable channels. Silencing it there risks muting legitimate heartbeat alerts for all channels and accounts.

Independent verification against upstream:

- `src/infra/heartbeat-visibility.ts`
- `src/infra/outbound/targets.ts`
- `src/infra/heartbeat-runner.returns-default-unset.test.ts`

These confirmed:

- heartbeat target `none` is already internal-only
- the default visibility resolution is global/per-channel/per-account
- forcing `channels.defaults.heartbeat` is too broad

## Code Changes

### `scripts/rebuild_openclaw_openmind_stack.py`

- Renamed the old forced payload to `LEGACY_MANAGED_CHANNEL_HEARTBEAT_VISIBILITY`
- Added `normalize_channel_defaults(...)`
- New behavior:
  - if the current config contains exactly the legacy managed heartbeat override, remove it
  - otherwise preserve the existing user-defined heartbeat defaults
  - do not inject a heartbeat default when none exists

### `tests/test_rebuild_openclaw_openmind_stack.py`

- Removed the assertion that rebuild should force a global heartbeat default
- Added regression coverage that:
  - the rebuild does not inject `channels.defaults.heartbeat`
  - the legacy managed override is scrubbed
  - a custom heartbeat default is preserved verbatim

## Validation

### Code-level

Passed:

```bash
./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py
./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py tests/test_rebuild_openclaw_openmind_stack.py
```

### Live rebuild

Executed:

```bash
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --openclaw-bin /home/yuanhaizhou/.local/bin/openclaw
```

Observed:

- backup created under `~/.openclaw.migration-backup-*`
- OpenMind plugins remained linked and healthy
- `~/.openclaw/openclaw.json` now has `channels.defaults = {}`

### Service validation

After restart:

- `openclaw-gateway.service` came back `active`
- `chatgptrest-api.service` came back `active`
- `openclaw channels status --probe` succeeded for the configured Feishu and DingTalk channels
- post-restart journal scan showed no immediate recurrence of `feishu:heartbeat` delivery failures

## External Review Loop

### Gemini Deep Think

Gemini produced a blocking review that correctly challenged the global heartbeat mute as too broad. That review forced this correction round.

Relevant artifact:

- `artifacts/jobs/9dd91f44ae35402d906f0df4c2e1d71c/answer.md`

### ChatGPT Pro

The attachment-based ChatGPT Pro review remained in preamble/progressive export state and did not yet produce a final verdict during this round. Interim content aligned with Gemini on the heartbeat-risk direction, but was not treated as final authority.

## Remaining Runtime Blocker

The live system still has a Codex OAuth problem for `main`:

- gateway journal repeatedly reports `refresh_token_reused`
- `planning` remained healthy on Gemini
- `main` failed because its OpenAI Codex auth store had stale credentials

This is a separate issue from heartbeat visibility and is handled in the next round.
