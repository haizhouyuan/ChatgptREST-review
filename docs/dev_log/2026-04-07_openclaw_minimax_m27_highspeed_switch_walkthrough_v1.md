# OpenClaw MiniMax M2.7 Highspeed Switch Walkthrough v1

日期：2026-04-07

## 本次目标

把 OpenClaw 前台接话模型从 `MiniMax-M2.5` 切到 `MiniMax-M2.7-highspeed`，并保持生成源与 live runtime 一致，避免下次重建时被回滚。

## 为什么改

- 当前 Feishu / OpenClaw 前台仍在使用 `MiniMax-M2.5`
- 用户明确要求升级到 `MiniMax-M2.7-highspeed`
- 官方文档已列出 `MiniMax-M2.7-highspeed` 为兼容模型，适合直接替换前台默认模型

## 改动范围

1. `scripts/rebuild_openclaw_openmind_stack.py`
   - 把 `DEFAULT_MINIMAX_MODEL_REF` 改成 `minimax/MiniMax-M2.7-highspeed`
   - 把生成的 provider model id/name 改成 `MiniMax-M2.7-highspeed`
2. `tests/test_rebuild_openclaw_openmind_stack.py`
   - 同步更新断言，确保生成配置与 telemetry 默认模型一致

## 运行态动作

1. 用 `PYTHONPATH=. ./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --topology lean` 重建 live `openclaw.json`
2. 重启 `openclaw-gateway.service`
3. 复核 `/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json` 中：
   - `models.providers.minimax.models[0].id`
   - `plugins.entries.openmind-telemetry.config.defaultModel`
   - `agents.defaults.model.primary`

## 边界

- 本次只切 OpenClaw 前台默认 MiniMax 模型
- 不改 ChatgptREST backend 的 coding-agent executor contract
- 不改 `openclaw.json` 以外的 memory / workspace / topology
