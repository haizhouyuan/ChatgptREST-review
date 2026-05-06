# 2026-03-09 Qwen Disable Runtime Shutdown

## Goal

Treat Qwen as intentionally disabled on this host instead of leaving it half-enabled in runtime and issue automation.

## Why

- Live env still had `CHATGPTREST_QWEN_ENABLED=1`.
- `chatgptrest-worker-send-qwen.service` was still enabled and running.
- Qwen was already removed from `CHATGPTREST_UI_CANARY_PROVIDERS`, but maint-daemon default logic still treated `qwen` as a default provider when the env var was absent.
- Issue ledger still had open `_QwenNotLoggedInError` entries even though the operator decision is now "provider disabled", not "needs login".

## Code Changes

- `ops/maint_daemon.py`
  - Added `_qwen_enabled()` and `_default_ui_canary_providers()`.
  - `_parse_ui_canary_providers("")` now defaults to `["chatgpt", "gemini"]` unless `CHATGPTREST_QWEN_ENABLED=1`.
  - CLI default for `--ui-canary-providers` now follows the same rule.
- `tests/test_maint_daemon_ui_canary.py`
  - Updated default expectation to `chatgpt,gemini`.
  - Added regression coverage for the explicit `CHATGPTREST_QWEN_ENABLED=1` path.
- `docs/maint_daemon.md`
  - Documented that Qwen is opt-in for canary.
- `docs/runbook.md`
  - Added explicit "fully disable Qwen" operator steps.
- `ops/systemd/chatgptrest.env.example`
  - Clarified that canary should not include `qwen` unless Qwen runtime is explicitly enabled.

## Live Runtime Changes

- Updated `~/.config/chatgptrest/chatgptrest.env`
  - `CHATGPTREST_QWEN_ENABLED=0`
  - kept `CHATGPTREST_UI_CANARY_PROVIDERS=chatgpt,gemini`
- `systemctl --user stop chatgptrest-worker-send-qwen.service`
- `systemctl --user disable chatgptrest-worker-send-qwen.service`
- `systemctl --user restart chatgptrest-worker-send.service`
- `systemctl --user restart chatgptrest-maint-daemon.service`
- `bash ops/qwen_chrome_stop.sh`
- killed the remaining Qwen viewer tunnel / noVNC-side leftovers so no `qwen|qianwen|9335|5905|6085` process remains

## Verification

- Targeted tests passed:
  - `PYTHONPATH=. ./.venv/bin/pytest -q tests/test_maint_daemon_ui_canary.py tests/test_ops_shared_subsystems.py`
- Syntax check passed:
  - `./.venv/bin/python -m py_compile ops/maint_daemon.py tests/test_maint_daemon_ui_canary.py`
- Live state after restart:
  - `chatgptrest-worker-send-qwen.service` -> `inactive (dead)` and `disabled`
  - `chatgptrest-worker-send.service` restarted at `2026-03-09 12:24:15 CST`
  - `chatgptrest-maint-daemon.service` restarted at `2026-03-09 12:24:15 CST`
  - `CHATGPTREST_QWEN_ENABLED=0` in live env
  - `ops/maint_daemon.py` default provider evaluation returns `['chatgpt', 'gemini']`
  - `pgrep -af 'qwen|qianwen|9335|5905|6085'` shows no active Qwen runtime process

## Ledger Cleanup

- Marked as `mitigated` because the provider is intentionally disabled:
  - `iss_512ae3d14aae4ef8834f20b7b7474741`
  - `iss_413d43141d4546849ee1e501a587451d`

## Remaining Open Issues Not Closed

These were not closed because this task did not fix them:

- `iss_85c224e728624823988f1b35121b6617`
  - external ChatGPT review environment cannot read local bundle path
- `iss_d393c768256b416fa1c3c61a5dbd28aa`
  - Gemini `WaitNoThreadUrlTimeout`
- `iss_a18e4ca32e55400c8f14cf51b9664f3f`
  - Gemini `WaitNoThreadUrlTimeout`
- `iss_4c9071e8ae1b41e7a7870af580422d18`
  - Gemini Deep Research plan-stub / `needs_followup: RuntimeError`
- historical upload-path failures still open in issue ledger:
  - `iss_0fa9633044d248f7846f332835133a60`
  - `iss_04734ac4122e41368743596afa49b740`
  - `iss_353e912deac64756a70e61a2f477cc9e`
  - `iss_701eef7252d6473cba206989d8bba847`
  - `iss_57b2bf04123e4aa2bd1b81f96054d818`
  - `iss_7f680fcfede4429cb8d81de2911b11d9`
  - `iss_5bfde014d0e243c7bba8f4de6f0fe6f8`
  - `iss_9d4b19b0584048eda1e5440f3e558c23`
  - `iss_419e7a607a864e398ffc5cabd651cfcd`
  - `iss_8a33e17496744004a14a8138fb64e0ce`
  - `iss_9e609bd1c165475988040ee29634ee53`
  - `iss_2b873003a690433fbe4f831765e30f70`

## Result

Qwen is now treated as an explicitly disabled provider in both code defaults and live runtime on this host. The remaining open issues are unrelated to Qwen shutdown and were intentionally left open.
