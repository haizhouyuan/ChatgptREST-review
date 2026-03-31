# Wait Pipeline 系统级优化方案（2026-02-21）

## 1) 目标与问题定义

用户反馈的核心痛点是：

- 在 viewer 里已看到答案，但客户端仍长期停留在 `in_progress/cooldown`。
- 交互层只看到“还在等”，缺少“到底在等什么”的可解释性。
- 极端情况下出现重复 wait 循环，浪费时间并放大风控暴露面。

本方案目标不是局部 patch，而是把“等答案”链路升级为：

- 更快：尽早返回“可交付答案已可用”信号。
- 更稳：避免 guard/export 误判导致的长时间循环。
- 更可观测：客户端能看到明确阶段与阻塞原因。

## 2) 现网证据（基于 `state/jobdb.sqlite3`）

### 2.1 总体事件分布

- `wait_requeued`: `18977`
- `completion_guard_downgraded`: `1601`
- `answer_completed_from_export`: `919`
- `assistant_answer_ready`: `596`

结论：`wait_requeued` 与 `completion_guard_downgraded` 是主要“等待放大器”。

### 2.2 时延侧证

- 有 `assistant_answer_ready -> completed` 的 job：
  - 样本数 `450`
  - 平均 `373.83s`
  - 最大 `6611.71s`
- 有 `answer_completed_from_export -> completed` 的 job：
  - 样本数 `379`
  - 平均 `274.10s`
  - 最大 `7242.34s`

这说明“答案可见”与“任务完成”之间存在明显长尾。

### 2.3 关键异常样本（结构性误判）

job: `688db2883f954208a013f45a7dc1e94a`

- `completion_guard_downgraded` 次数：`162`
- 降级原因全部为：`conversation_export_missing_reply`
- 但同一 payload 显示：
  - `answer_chars=37924`
  - `min_chars_required=15000`
  - `match_kind=exact`
  - `export_last_role=assistant`

该样本反映：completion/export 判定在部分路径上存在“有答案却持续打回等待”的行为。

## 3) 根因分层分析

### A. 多层轮询叠加导致可见延迟

- worker wait slice 默认 60s（`chatgptrest/core/config.py:61-84`，`chatgptrest/worker/worker.py:3449-3460`）。
- `in_progress` 默认 requeue 间隔约 60s（`chatgptrest/worker/worker.py:4792-4857`）。
- API `/wait` 仅终态返回，默认 poll 1s（`chatgptrest/api/routes_jobs.py:510-536`）。

结果：即使答案出现，最终态写回可能仍受 slice+requeue 周期影响。

### B. completion/export guard 的“保护过度”与循环

- 当前 guard 在 `chatgptrest/worker/worker.py:3755-3897`。
- export 匹配在 `chatgptrest/worker/worker.py:2187-2274`。
- 典型模式是 matched 但判定 missing assistant，触发降级回 `in_progress`，再进入下一轮 wait。

### C. 完成语义单一（只暴露 terminal）

- 客户端当前只能靠 `completed/error/...` 判断结束，缺少“答案已就绪但在收尾校验”的中间语义。
- 导致用户体感是“明明能看见答案但系统不承认”。

### D. 观测信号不足

- `assistant_answer_ready` 事件覆盖率不高（显著低于 completed job 数），无法稳定驱动“早返回”策略。

## 4) 系统级改造方案

## 4.1 新增“可见完成”语义层（不破坏现有状态机）

不新增 DB `status` 枚举（避免兼容风险），新增派生进度字段：

- `progress_state`: `queued | sent | waiting_model | answer_visible | finalizing | completed`
- `waiting_on`: `model_generation | export_sync | completion_guard | cooldown_backoff | no_thread_url`
- `answer_chars_observed`
- `last_progress_at`

落点：

- 写入 `jobs` 扩展列或 `result_json`（推荐扩展列，便于查询）
- `/v1/jobs/{id}` 与 `/wait` 返回这些字段

### 4.2 `/wait` 增加“早返回策略”

新增参数：

- `return_on=completed|answer_visible`（默认 `completed` 兼容）
- `min_visible_chars`（默认 200）

行为：

- 当 `progress_state=answer_visible` 且满足阈值时可提前返回；
- 客户端可先展示内容，再继续后台等待最终 `completed`（可选）。

### 4.3 completion/export 判定去抖与防环

新增 `CompletionEvidence` 聚合判定，至少包括：

- Driver evidence：`answer`, `answer_id`, `answer_chars`
- Export evidence：matched window / assistant reply / export freshness
- Timeline evidence：`assistant_answer_ready`/`answer_ready`

决策策略：

- 强证据（driver answer 足够长）优先；
- export 缺失仅作弱负证据，不得无限压制强证据；
- 对同一 `answer_hash + reason` 降级做去重与次数上限（例如 2 次后 fail-open 完成并打 warning 事件）。

### 4.4 自适应 wait/requeue 节奏

按 `progress_state` 动态计算 `not_before`：

- `waiting_model`: 20-60s（指数退避）
- `answer_visible/finalizing`: 3-8s（快速收敛）
- `no_thread_url`: 15-30s

避免当前固定 60s 带来的“看得见但要再等一整轮”。

### 4.5 观测与告警

新增核心指标：

- `t_visible_to_completed_ms`
- `completion_guard_loops_per_job`
- `export_missing_reply_false_positive_rate`
- `wait_requeued_per_completed_job`

并建立 SLO：

- P50 `t_visible_to_completed` < 10s
- P95 `t_visible_to_completed` < 45s

## 5) 实施计划（分阶段，带回滚）

### Phase P0（1-2 天，低风险高收益）

- 加进度字段（只读，不改现有 status）
- `/jobs` 与 `/wait` 返回 `progress_state/waiting_on/answer_chars_observed`
- completion_guard 降级去重（同 hash + 同 reason 限流）
- 自适应 `not_before`（仅 wait phase）

涉及文件：

- `chatgptrest/worker/worker.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/api/schemas.py`
- `chatgptrest/core/job_store.py`

回滚：关 env 开关恢复旧行为。

### Phase P1（2-4 天，体验升级）

- `/wait?return_on=answer_visible`
- CLI/MCP 透传 `return_on` 并展示 `waiting_on`
- 新增 `answer_visible` 事件

涉及文件：

- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/mcp/server.py`
- `chatgptrest/cli.py`

### Phase P2（3-5 天，鲁棒性强化）

- `CompletionEvidence` 判定器重构
- export 判定逻辑重写为“证据加权”而非单点否决
- 全量回归测试 + 监控报表

## 6) 测试与验收

新增测试建议：

- `tests/test_wait_return_on_answer_visible.py`
- `tests/test_completion_guard_dedupe.py`
- `tests/test_wait_adaptive_not_before.py`
- `tests/test_export_missing_reply_no_infinite_loop.py`

验收样本：

- 复现历史极端 job（如 `688db...`）应在有限轮内结束，不再出现百次级降级循环。
- 新增 SLO 指标在 24h soak 内达标。

## 7) 立即可执行的配置建议（临时缓解）

在大改前，可先保守调整：

- `CHATGPTREST_WAIT_SLICE_SECONDS` 从 60 调到 30（已支持最小 30）
- 将 completion guard 的重复降级阈值收紧（需代码支持后启用）
- 对超大 `min_chars` 任务开启软门槛模式（需代码支持后启用）

---

本方案优先解决“答案可见但客户端仍等待”的结构性问题，并保持向后兼容：默认行为不变，通过新参数/新字段渐进启用。
