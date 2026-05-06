# Finbotfree OpenRouter Guardrails And Rollout v1

## What changed

This pass hardens the new `finbotfree` lane so the free-tier path behaves like a real low-cost tier instead of silently drifting back into paid routing.

Changed areas:

- `chatgptrest/kernel/llm_connector.py`
  - explicit `openrouter` requests now fail if `OPENROUTER_API_KEY` is missing
  - OpenRouter `429` now maps to connector cooldown semantics
  - OpenRouter `401/403` now maps to connector auth/cooldown handling instead of generic failure
  - empty OpenRouter completion content is now treated as an error
- `chatgptrest/finbot.py`
  - lane execution now rejects blank LLM text instead of writing empty successful artifacts
- `ops/systemd/chatgptrest-finbotfree-*.service`
  - both free-tier services pin `OPENROUTER_DEFAULT_MODEL=nvidia/nemotron-3-super-120b-a12b:free`

## Why this was needed

The initial `finbotfree` implementation had two unsafe behaviors:

1. If OpenRouter credentials were missing, the explicit free-tier path could silently fall back to paid Coding Plan.
2. If OpenRouter returned an empty completion body, finbot would treat that as success and continue writing dossier artifacts with empty lane output.

Both behaviors break the intended contract:

- free tier must stay free tier
- empty model output must fail closed

## Verification

Targeted regression tests:

- `./.venv/bin/pytest -q tests/test_llm_connector.py tests/test_finbot.py tests/test_finbot_dashboard_service_integration.py`

Added coverage for:

- missing OpenRouter key does not fall back to paid path
- OpenRouter `429` becomes cooldown
- empty OpenRouter content becomes error
- finbot lane rejects empty OpenRouter text

Runtime probe:

- direct OpenRouter connector probe against `nvidia/nemotron-3-super-120b-a12b:free`
- confirmed non-empty text response after guardrails patch

## Rollout notes

The user-level `finbotfree` units should be installed from the templated systemd files with the real repo root substituted for `__CHATGPTREST_ROOT__`, then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now chatgptrest-finbotfree-daily-work.timer
systemctl --user enable --now chatgptrest-finbotfree-theme-batch.timer
systemctl --user start chatgptrest-finbotfree-daily-work.service
```

This keeps the free lane running on timers while also forcing an immediate first sweep.
