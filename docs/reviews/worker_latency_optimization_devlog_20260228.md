# Worker 延迟优化开发记录（2026-02-28）

## 背景

基于架构深度分析报告（修订版），识别出 ChatgptREST 的主要延迟来自：

1. **发送前排队/限流** — `min_prompt_interval=61s` + backlog，create→prompt p50=188s
2. **Wait 阶段固定 60s 重排** — wait_requeued→claimed p50=60.44s，min=60.0s
3. **多次 Conversation Export** — 每 job 中位 2 次 MCP 调用

数据来源：近 7 天 121 个 completed `chatgpt_web.ask` job。

## 改动内容

### Opt-1: 自适应 Wait Slice

| 文件 | 改动 |
|------|------|
| `chatgptrest/core/config.py` | 新增 `_env_float()` 和 `wait_slice_growth_factor` 字段（默认 1.0） |
| `chatgptrest/worker/worker.py` | 查询 `wait_requeued` event 计数，按 `base * factor^count` 递增 slice |

**环境变量**: `CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR`（默认 `1.0` = 不变，`1.5` 推荐）

**效果示例**（factor=1.5, base=60s）:

| wait_requeued 次数 | slice 大小 |
|-------------------|-----------|
| 0 | 60s |
| 1 | 90s |
| 2 | 135s |
| 3 | 202s |

slice 增长上限为 job 的 `max_wait_seconds`。

### Opt-2: Export 结果缓存

| 文件 | 改动 |
|------|------|
| `chatgptrest/worker/worker.py` | `_maybe_export_conversation` 新增 `cache` 参数，5 个调用点传入 `_export_cache` |

**零配置生效**。`_run_once` 作用域内声明 `_export_cache: dict`，首次 export 成功后缓存结果，后续非 `force` 调用直接跳过。`force=True`（completion guard）仍正常执行。

### Opt-3: EventBatch 模块

| 文件 | 改动 |
|------|------|
| `chatgptrest/core/event_batch.py` | 新建，`EventBatch.add()` + `flush()` 批量写入 |

模块已就绪但尚未接入 `_run_once`，留作下阶段集成。

## 测试

### 新增测试

| 测试文件 | 用例数 | 覆盖内容 |
|---------|--------|---------|
| `tests/test_adaptive_wait_slice.py` | 5 | growth_factor=1 noop / 增长 / cap / 无 requeue / env 读取 |
| `tests/test_export_cache.py` | 3 | 缓存命中 / force 绕过 / 无 cache 兼容 |
| `tests/test_event_batch.py` | 3 | batch flush / 空 flush noop / clear 验证 |

### 回归

- 全量 ~800 测试通过
- 修复 1 个因新字段导致的 `test_repair_autofix_codex_fallback.py` 构造缺参

## Git

```
845d4a7 Merge branch 'feat/worker-latency-opt'
a45bc4a perf(worker): adaptive wait slice, export caching, event batch
```

7 files changed, 560 insertions(+)

## 追加修复：MCP HTTP Failure Hooks（commit `4343d13`）

`test_mcp_failure_autoreport.py` 中 3 个测试引用了未实现的函数，现已补齐：

| 新增函数 | 作用 |
|---------|------|
| `_mcp_auto_report_issue_from_failure` | Stub auto-report，支持按 `failure_kind:error_type` 去重 |
| `_mcp_handle_http_failure` | JSONL 失败日志 + 触发 auto-report |
| `_http_json` 新增 `enable_failure_hooks` | 默认 True，可按调用关闭 |

修复后全量回归 **0 failures**。

## 部署建议

1. **立即生效**: Opt-2 export 缓存无需配置
2. **推荐启用**: 在 systemd service 里加 `Environment=CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR=1.5`
3. **观测指标**: 对比启用前后 `wait_requeued` 事件数 / prompt→complete 耗时
