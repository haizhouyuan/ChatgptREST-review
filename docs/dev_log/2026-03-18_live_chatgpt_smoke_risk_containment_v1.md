# 2026-03-18 live ChatGPT smoke 风险围堵修复 v1

## 背景

用户指出两个真实问题：

1. smoke / fault probe 这类低价值请求仍然会创建真实 `chatgpt.com/c/...` 会话。
2. 之前虽然加过 `Pro + smoke` 阻断，但仍然没有真正把风险围堵住。

这次调查确认，根因不是单点 bug，而是策略漂移：

- `/v1/jobs` 入口里保留了三段散落的本地 guard，只覆盖了 `Pro + smoke`、`Pro + trivial` 和 `smoketest` 前缀。
- `prompt_policy.py` 没有成为真正的单一策略源。
- `ops/smoke_test_chatgpt_auto.py` 仍然能直接发 live `chatgpt_web.ask`。
- `ops/codex_cold_client_smoke.py` 对 `provider=chatgpt` 仍可能走高成本 preset。
- worker auto repair 会对同一个 `conversation_url` 在短窗口里重复提交 `repair.autofix`。

## 本次修复

### 1. 统一服务端提交策略

文件：

- `chatgptrest/core/prompt_policy.py`
- `chatgptrest/api/routes_jobs.py`

改动：

- `routes_jobs.create_job_route()` 不再自己散落维护 smoke / Pro guard。
- 统一改为调用 `enforce_prompt_submission_policy()`。
- 新增 `live_chatgpt_smoke_blocked`：
  - 对 `chatgpt_web.ask`，以下情形默认 fail-closed：
    - `params.purpose in smoke/test/probe/...`
    - `smoketest` 前缀
    - synthetic fault-probe prompt，如 `test blocked state`
    - 注册的 smoke client 名
- 保留原有 `trivial_pro_prompt_blocked` 和 `pro_smoke_test_blocked`。
- 兼容原有显式 override：
  - `allow_live_chatgpt_smoke`
  - `allow_trivial_pro_prompt`
  - `allow_pro_smoke_test`

### 2. 旧 smoke 脚本默认 fail-closed

文件：

- `ops/smoke_test_chatgpt_auto.py`
- `ops/codex_cold_client_smoke.py`

改动：

- `ops/smoke_test_chatgpt_auto.py`
  - 默认拒绝运行 live ChatGPT smoke
  - 只允许 `preset=auto`
  - 需要显式 `--allow-live-chatgpt-smoke` 才能例外
- `ops/codex_cold_client_smoke.py`
  - `provider=chatgpt` 的默认 preset 从 `pro_extended` 改为 `auto`
  - 默认拒绝 live ChatGPT cold-client smoke
  - 需要显式 `--allow-live-chatgpt-smoke`
  - 即使显式允许 live ChatGPT smoke，仍只允许 `preset=auto`

### 3. worker auto repair conversation 级冷却

文件：

- `chatgptrest/worker/worker.py`

改动：

- `_maybe_submit_worker_autofix()` 新增按 `conversation_url` 的冷却查询。
- 默认窗口：
  - `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_CONVERSATION_COOLDOWN_SECONDS=1800`
- 如果最近窗口内，`worker_auto_codex_autofix` 已经对同一个 `conversation_url` 提交过 `repair.autofix`，则直接跳过。

## 测试

已运行：

```bash
./.venv/bin/pytest -q tests/test_block_smoketest_prefix.py tests/test_codex_cold_client_smoke.py tests/test_smoke_test_chatgpt_auto.py
./.venv/bin/pytest -q tests/test_worker_auto_autofix_submit.py tests/test_repair_autofix_codex_fallback.py tests/test_mcp_repair_submit.py
./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py tests/test_conversation_single_flight.py tests/test_cli_chatgptrestctl.py -k 'submit or smoke'
```

## 结果

- live ChatGPT smoke 现在默认 fail-closed。
- `Pro` 不再是 smoke 脚本可默认触达的路径。
- 旧脚本的默认行为已从“谨慎建议”升级为“硬阻断”。
- worker auto repair 对同一会话的短时间重复碰线被压下来了。

## 为什么之前没彻底做好

因为之前的修复只覆盖了“Pro smoke”和少数 prompt pattern，但没有做到：

- 单一策略源
- 脚本 fail-closed
- synthetic probe 覆盖
- repair 会话级去重

这次修复的重点不是再加一个正则，而是把整个风险面收成统一策略与默认阻断。
