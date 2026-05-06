# 2026-03-16 OpenClaw Agent Model Fallback Reorder Walkthrough v1

## What changed

This change aligns the managed OpenClaw agents and the ChatgptREST Coding Plan
connector to the requested fallback order:

1. `MiniMax-M2.5`
2. `qwen3-coder-plus`
3. Gemini

## Why

Before this change, the generated OpenClaw config still pinned `main` and
`maintagent` to `openai-codex/gpt-5.4`, while `finbot` started on Gemini. The
runtime Coding Plan connector also mixed older API-chain entries and only fell
back to MiniMax direct after exhausting the API list.

That produced two problems:

- the configured OpenClaw agent defaults did not match the intended
  `MiniMax -> Qwen -> Gemini` order;
- the runtime connector did not expose Gemini as the third hop in the direct
  Coding Plan path.

## Repo changes

### OpenClaw config generation

Updated `scripts/rebuild_openclaw_openmind_stack.py` to:

- set `main`, `maintagent`, and `finbot` primary model to
  `minimax/MiniMax-M2.5`;
- set shared fallbacks to
  `qwen-coding-plan/qwen3-coder-plus -> google-gemini-cli/gemini-2.5-pro`;
- generate `models.providers.minimax` and `models.providers.qwen-coding-plan`
  so the gateway can resolve both API-backed providers without manual edits.

### ChatgptREST runtime fallback

Updated `chatgptrest/kernel/llm_connector.py` to:

- reduce the direct Coding Plan API chain to `MiniMax-M2.5` then
  `qwen3-coder-plus`;
- use Gemini Web as the next fallback before the legacy MiniMax Anthropic
  rescue path.

### Tests

Updated:

- `tests/test_rebuild_openclaw_openmind_stack.py`
- `tests/test_llm_connector.py`

to assert the new primary/fallback order and the Gemini third-hop behavior.

## Validation

### Unit tests

Ran:

```bash
./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py tests/test_llm_connector.py
python3 -m py_compile scripts/rebuild_openclaw_openmind_stack.py chatgptrest/kernel/llm_connector.py
```

Both succeeded.

### Live config application

Applied the generated config to the active OpenClaw state:

```bash
python3 scripts/rebuild_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --openclaw-bin /home/yuanhaizhou/.home-codex-official/.local/bin/openclaw \
  --openmind-base-url http://127.0.0.1:18711 \
  --topology ops
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
```

Verified with:

```bash
HOME=/home/yuanhaizhou/.home-codex-official \
  /home/yuanhaizhou/.home-codex-official/.local/bin/openclaw models status --agent <agent> --json
```

Observed for `main`, `maintagent`, and `finbot`:

- `resolvedDefault = minimax/MiniMax-M2.5`
- `fallbacks = [qwen-coding-plan/qwen3-coder-plus, google-gemini-cli/gemini-2.5-pro]`

## Commit

- `5906a17` `Align agent model fallback order`
