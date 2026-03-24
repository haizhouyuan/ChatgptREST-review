# Finbotfree OpenRouter Guardrails And Rollout v2

## Scope

This version records the actual deployment and remote landing after the v1 guardrails patch.

## Remote landing

Feature branch:

- branch: `feature/system-optimization-20260316`
- hardening commit: `5f35244`
- pushed to: `origin/feature/system-optimization-20260316`

Master:

- feature commit landed as: `d7f9ac2`
- hardening commit landed as: `5a557e3`
- pushed to: `origin/master`

The master push was done from a clean `origin/master` worktree by cherry-picking only the two relevant finbotfree commits, rather than force-pushing the whole feature branch.

## Live user-unit rollout

Installed active user units:

- `~/.config/systemd/user/chatgptrest-finbotfree-daily-work.service`
- `~/.config/systemd/user/chatgptrest-finbotfree-daily-work.timer`
- `~/.config/systemd/user/chatgptrest-finbotfree-theme-batch.service`
- `~/.config/systemd/user/chatgptrest-finbotfree-theme-batch.timer`

Key live settings:

- `FINBOT_TIER=free`
- `OPENROUTER_DEFAULT_MODEL=nvidia/nemotron-3-super-120b-a12b:free`
- credentials loaded from:
  - `~/.config/chatgptrest/chatgptrest.env`
  - `/vol1/maint/MAIN/secrets/credentials.env`

## Runtime verification

### 1. Timers enabled

Verified:

- `chatgptrest-finbotfree-daily-work.timer`
- `chatgptrest-finbotfree-theme-batch.timer`

Observed schedule:

- daily-work next run: about every 4 hours
- theme-batch next run: nightly at `20:30`

### 2. First live run succeeded

Manual start:

```bash
systemctl --user start chatgptrest-finbotfree-daily-work.service
```

Observed result:

- unit exited `status=0/SUCCESS`
- runtime about `33.7s`
- updated finbot inbox artifacts for:
  - watchlist
  - theme radar
  - deepening brief

Observed journal output confirmed the free-tier daily-work path ran end-to-end and returned structured JSON.

### 3. Free-tier OpenRouter path is live

Direct lane probe with:

- `FINBOT_TIER=free`
- `OPENROUTER_DEFAULT_MODEL=nvidia/nemotron-3-super-120b-a12b:free`

Returned:

- provider: `openrouter/nvidia/nemotron-3-super-120b-a12b:free`
- non-empty markdown: `hello`

This verified that the new lane path is not just a timer shell; it can reach the OpenRouter free model successfully.

## Guardrails now enforced

- missing `OPENROUTER_API_KEY` no longer falls back to paid Coding Plan
- OpenRouter `429` maps to cooldown semantics
- OpenRouter `401/403` maps to auth/cooldown handling
- empty OpenRouter completions fail closed
- finbot lanes reject blank LLM text instead of writing empty successful artifacts

## Tests

Executed:

```bash
./.venv/bin/pytest -q tests/test_llm_connector.py tests/test_finbot.py tests/test_finbot_dashboard_service_integration.py
```

Also re-ran the same targeted suite from the clean master worktree using the shared repo virtualenv before pushing `origin/master`.
