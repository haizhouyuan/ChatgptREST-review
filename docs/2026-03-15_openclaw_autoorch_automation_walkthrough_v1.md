# OpenClaw AutoOrch Automation Walkthrough v1

日期：2026-03-15  
仓库：ChatgptREST

## 本轮做了什么

1. 将 `ops` 拓扑从 `main + maintagent` 扩成 `main + maintagent + autoorch`。
2. 在 `scripts/rebuild_openclaw_openmind_stack.py` 中新增：
   - `autoorch` agent spec
   - `autoorch` heartbeat
   - `autoorch` workspace docs
   - managed cron jobs 写入
3. 新增后台自动化模块：
   - `chatgptrest/autoorch.py`
   - `ops/openclaw_autoorch.py`
4. 实现两个任务：
   - `dashboard-refresh`
   - `watchlist-scout`
5. 实现 inbox 协议：
   - `inbox-list`
   - `inbox-ack`
6. 补齐定向测试。

## 为什么这样做

- `main` 的主上下文不应该被 cron 噪音污染。
- `maintagent` 目前已经承担健康 watchdog，直接并入业务自动化会增加迁移风险。
- `autoorch` 负责“刷新 + 扫描 + 写 inbox”，是更窄、更稳定的后台运行面。

## 测试

执行：

```bash
PYTHONPATH=. pytest -q \
  tests/test_autoorch.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py
```

结果：

- `41 passed`

## 风险和后续

- 当前只落了自动化基础设施，没有碰 Graph page。
- `watchlist-scout` 依赖本机 `finagent` CLI 可用。
- GitNexus MCP 在本轮多次超时；已先用本地上下文 + 定向测试收口，后续可在 index 恢复后补跑图谱级 impact/detect。
