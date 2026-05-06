# 2026-04-04 Codex SRE Token Budget Controls v1

## 背景

`ops/maint_daemon.py` 里的 incident Codex SRE analyze 原先只按 incident 粒度限流，并且在 `last_ok != True` 时会按最小间隔继续重跑。`sre.fix_request` controller prompt 也会默认拼接较大的上下文块，导致：

- 同一 `provider + target_job + failure family` 被反复分析
- quota/auth 错误后仍继续尝试 fresh analyze
- prompt 体积偏大，实际 token 消耗远高于有效新增信息

## 本次改动

### P0 调度治理

- 新增 target/family 决策缓存，key 为 `provider|target_job_id|sig_hash`
- 新增 fresh analyze 全局熔断：
  - usage-limit / quota 类错误进入全局 pause
  - auth 类错误进入较短 pause
  - 若错误文本含 `Try again at ...`，优先解析 reset 时间
- 新增 recent failure cooldown：
  - 同一 target/family 在失败冷却窗口内不再重复 fresh analyze
- 复用 cached decision 时，本地 incident 仍会写入：
  - `codex/sre_actions.json`
  - `codex/sre_actions.md`
  - `codex/source_lane.json`
  - `codex/run_meta.json`

### P1 Prompt 瘦身

- `ops/maint_daemon.py`
  - `_incident_context_pack()` 改为只注入紧凑 manifest / summary / focused issues excerpt / compact job rows / compact repair report
  - `global_memory_excerpt` 仅在没有 targeted preferred actions 时才注入
- `chatgptrest/executors/sre.py`
  - controller prompt 默认缩小：
    - bootstrap memory
    - repo memory
    - lane history / manifest
    - context pack
    - target result / run_meta / events / answer
    - GitNexus / playbook excerpt
  - prompt 用 compact context pack，去掉 `global_memory_md` 这类重复路径字段

### P2 可观测性

- `sre_fix_request` report / request 新增 `prompt_stats`
  - `prompt_chars`
  - `estimated_tokens`
  - `sections`
- incident Codex run_meta 新增：
  - `runner_mode`
  - `prompt_chars`
  - `prompt_estimated_tokens`
- maint daemon JSONL 新增：
  - `codex_sre_reused`
  - `codex_sre_skipped`
  - `codex_sre_global_pause_set`

## 新默认值

- `--codex-sre-decision-reuse-seconds=14400`
- `--codex-sre-failure-cooldown-seconds=1800`
- `--codex-sre-quota-pause-seconds=21600`
- `--codex-sre-auth-pause-seconds=3600`
- `--codex-sre-cache-max-entries=256`

## 影响

- 首次新问题仍会走 fresh Codex analyze
- 同类重复问题优先复用近期决策，不再把 Codex 当热路径轮询器
- quota/auth 命中后会 fail-closed，避免额度耗尽后继续自激
- runtime autofix / manual / open_pr 分流能力保留

## 验证

- `python3 -m py_compile ops/maint_daemon.py chatgptrest/executors/sre.py`
- `./.venv/bin/python -m pytest tests/test_maint_daemon_codex_sre.py -q`
- `./.venv/bin/python -m pytest -q tests/test_sre_fix_request.py::test_sre_fix_request_records_prompt_stats_and_compacts_prompt_context`
- `./.venv/bin/python -m pytest -q tests/test_sre_fix_request.py::test_sre_fix_request_decision_override_routes_runtime_fix_without_codex`
