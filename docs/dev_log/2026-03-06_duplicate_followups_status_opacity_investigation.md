# 2026-03-06 会话 `69aa9315-a310-83aa-bc90-1fae3cead471` 重复追问与 worker 状态不透明调查

## 结论摘要

这次并不是 driver 自己把同一条 follow-up 发了两遍，而是上层 agent 在同一会话上先后新建了两个 follow-up job：

- `4d4c69ef003d40a08aff59d26cd5c215`
- `e4b1e068fc5b456ea1307646662813ce`

之所以会发生二次、三次追问，核心不是单点故障，而是三层问题叠加：

1. ChatGPT send 阶段把明显未完成的短答直接标记为 `completed`。
2. 统一 MCP 接口 `chatgptrest_ask` / `chatgptrest_followup` 没把 `min_chars` 这类质量阈值暴露给调用方。
3. `JobView` / `chatgptrest_result` 对调用方暴露的运行态信息过少，外部 agent 很难区分：
   - “真的完成了”
   - “只是先吐了一句正在看 / 又补了一小段”
   - “prompt 还没真正发出去，只是在 send 阶段续租”

结果就是：上层 agent 只能根据一段很短的 answer 文本自行猜测系统状态，于是把“质量问题”误操作成“继续追问”。

## 调查范围

- 会话 URL：`https://chatgpt.com/c/69aa9315-a310-83aa-bc90-1fae3cead471`
- 相关作业：
  - `8af57eb0ecab46029f90ad3fd8f0009b`：初始提问
  - `4d4c69ef003d40a08aff59d26cd5c215`：第一次 follow-up
  - `e4b1e068fc5b456ea1307646662813ce`：第二次 follow-up
- 主要证据：
  - `artifacts/jobs/<job_id>/events.jsonl`
  - `artifacts/jobs/<job_id>/answer.md`
  - `artifacts/mcp_calls.jsonl`
  - `state/jobdb.sqlite3`

## 时间线

| 时间 | 事件 | 证据 |
| --- | --- | --- |
| 2026-03-06 16:40:41 | 创建初始 job `8af57...` | `artifacts/jobs/8af57eb0ecab46029f90ad3fd8f0009b/events.jsonl` |
| 2026-03-06 16:41:43 | 初始 job 记录 `prompt_sent` 与 `assistant_answer_ready` | 同上 |
| 2026-03-06 16:41:55 | 初始 job 被标记为 `completed`，answer 仅 172 chars | `artifacts/jobs/8af57.../answer.md` |
| 2026-03-06 16:47:17 | 创建第一次 follow-up job `4d4c69...` | `artifacts/jobs/4d4c69.../events.jsonl` |
| 2026-03-06 16:57:18 | 第一次 follow-up 记录 `prompt_sent` 与 `assistant_answer_ready` | 同上 |
| 2026-03-06 16:57:30 | 第一次 follow-up 被标记为 `completed`，answer 仅 319 chars | `artifacts/jobs/4d4c69.../answer.md` |
| 2026-03-06 17:13:14 | 创建第二次 follow-up job `e4b1e0...` | `artifacts/jobs/e4b1e0.../events.jsonl` |
| 2026-03-06 17:21:56 | 第二次 follow-up 仍处于 `send/in_progress`，只看到 `lease_renewed` | `state/jobdb.sqlite3` + `artifacts/jobs/e4b1e0.../events.jsonl` |

## 关键发现

### 1. 两次追问来自上层新建 job，不是 worker/driver 自动重发

`4d4c69...` 和 `e4b1e0...` 都有独立的 `job_created` 事件，且 `input.parent_job_id` 指向同一个父 job `8af57...`。这说明是调用方显式又提交了两个 follow-up，而不是 send worker 自己重复发送。

直接证据：

- `artifacts/jobs/4d4c69ef003d40a08aff59d26cd5c215/events.jsonl`
- `artifacts/jobs/e4b1e068fc5b456ea1307646662813ce/events.jsonl`

### 2. 前两次 job 都以明显不完整的短答进入 `completed`

本地答案文件显示：

- `8af57...` 的 answer 只有 172 chars：
  - `I’m pulling the branch ...`
- `4d4c69...` 的 answer 只有 319 chars：
  - `Another systemic issue is ...`

这两条都更像“过程性片段”而不是最终审查报告，但系统仍把 job 收敛为 `completed`。

直接证据：

- `artifacts/jobs/8af57eb0ecab46029f90ad3fd8f0009b/answer.md`
- `artifacts/jobs/4d4c69ef003d40a08aff59d26cd5c215/answer.md`

旁证：

- `ops/verify_job_outputs.py:289-290` 已经把 `completed && answer_chars < 200` 视为 `short_completed_answer`，说明离线核验链路已经承认“短答 completed”是可疑态，但在线运行态没有同级护栏。

### 3. `min_chars` 在 ChatGPT send 阶段没有真正参与“完成判定”

执行器会从 params 里解析 `min_chars`，默认值是 800：

- `chatgptrest/executors/chatgpt_web_mcp.py:583`

但这个值只明确传给 wait/regenerate：

- wait：`chatgptrest/executors/chatgpt_web_mcp.py:675-682`
- regenerate：`chatgptrest/executors/chatgpt_web_mcp.py:934-941`

send 阶段调用 `_tool_and_args(...)` 发送 `chatgpt_web_ask` 时，并没有把 `min_chars` 透传到 ask tool，也没有在 send 返回 `status=completed` 后做“短答降级”。

对应代码：

- send 调用：`chatgptrest/executors/chatgpt_web_mcp.py:699-715`
- send 后只对“瞬时错误”和“thought guard”做处理：`chatgptrest/executors/chatgpt_web_mcp.py:882-1004`

也就是说，只要 send tool 先给了一个 `completed`，即使 answer 很短，也会直接落地为 `completed`，不会自动回到 wait。

### 4. 统一 MCP 接口退化了调用方对质量阈值的控制力

旧接口 `chatgptrest_chatgpt_ask_submit` 明确暴露了 `min_chars`，默认 800：

- `chatgptrest/mcp/server.py:2088-2138`

但新的统一入口 `chatgptrest_ask` 没有 `min_chars` 参数，构造 job params 时也没有写入：

- 定义：`chatgptrest/mcp/server.py:3179-3202`
- 构造 params：`chatgptrest/mcp/server.py:3253-3260`

`chatgptrest_followup` 又只是简单委托给 `chatgptrest_ask`：

- `chatgptrest/mcp/server.py:3441-3472`

这带来两个后果：

- 调用方无法显式要求“长答未达阈值不要当 completed”。
- follow-up 场景默认继承了统一 ask 的弱语义，而不是旧 submit 工具的强约束。

### 5. `JobView` / `chatgptrest_result` 没把“为什么现在是这个状态”讲清楚

`JobView` 当前字段主要有：

- `status`
- `phase`
- `preview`
- `conversation_url`
- `retry_after_seconds`
- `estimated_wait_seconds`
- `reason_type` / `reason`

见：

- schema：`chatgptrest/api/schemas.py:84-112`
- job view 组装：`chatgptrest/api/routes_jobs.py:292-332`

缺失的恰恰是外部 agent 最需要的诊断信息：

- 当前 send 还是 wait
- 最近一个关键事件是什么
- `prompt_sent` 是否已经发生
- `assistant_answer_ready` 是否已经发生
- `answer_chars`
- 是否命中了 completion guard
- 当前完成判定的置信度/质量等级

`chatgptrest_result` 在 `completed` 时只负责把 answer 取出来，并给 `action_hint=answer_ready`：

- `chatgptrest/mcp/server.py:3319-3427`

因此，调用方看到的是“完成了 + 有一段文本”，但看不到“这段文本其实只有 172/319 chars，且极可能只是中间态”。

### 6. 第二次 follow-up 卡在 send 阶段时，对外几乎不可诊断

截至本次调查时点，`e4b1e0...` 仍然是：

- `phase=send`
- `status=in_progress`

但 artifacts 里只有持续的 `lease_renewed`，没有 `prompt_sent`，也没有 `assistant_answer_ready`。

这说明对外部 agent 来说，以下三种情况都可能被折叠成同一个 `in_progress`：

- prompt 还没真正送达
- prompt 已送达但模型还没开始出答案
- 模型已在网页里工作，但 worker 还没拿到可收敛结果

这正是“worker 状态不透明”的直接体现。

## 根因链

### 根因 A：完成判定过于依赖底层 tool 的 `status=completed`

当前 ChatGPT 执行器对 send 返回值的二次判定太弱。它会拦截：

- 瞬时错误文本
- Pro 思考异常标记

但不会拦截：

- 明显过短的片段答复
- 像 “I’m pulling the branch...” 这种过程性答复
- 导出会话里最后一条 assistant 仍处于未完成态的情况

### 根因 B：统一接口把质量约束削弱了，但没有补齐新的可见性

`chatgptrest_ask` 的目标是“统一 provider 接口 + 自动后台等待”，但它减少了调用参数，却没有增加足够的结果语义。最终变成：

- 调用更简单
- 但调用方更难知道“是否真的完成”

### 根因 C：状态模型没有把“运行进度”和“完成质量”拆开

当前 `status` 既承担“生命周期状态”，又被调用方拿来近似代表“内容质量状态”。这会导致：

- worker 认为 job 生命周期结束了，于是写 `completed`
- agent 认为内容也完成了，于是读取短答
- 短答不够用时，agent 只能再次 follow-up

正确做法应该把这两类信息拆开：

- 生命周期：`queued / send / wait / completed / error ...`
- 质量：`partial / suspect / final / export_mismatch / low_confidence ...`

## 建议改进

### P0: 在 ChatGPT send 阶段补一个强制 completion guard

目标：不要再让 100-300 chars 的过程性片段直接落到 `completed`。

建议：

- 在 `chatgptrest/executors/chatgpt_web_mcp.py` 的 send 后归一化前加入二次判定：
  - 若 `status=completed` 但 `answer_chars < min_chars`
  - 或 answer 命中“过程性短答/占位答复”模式
  - 或导出会话显示最后 assistant 未完成
  - 则把状态降级为 `in_progress` 或 `needs_followup`
- 优先降级到 `in_progress` 并继续 wait/export，不要重新发 prompt。

### P0: 给 `chatgptrest_ask` / `chatgptrest_followup` 恢复 `min_chars`

目标：统一接口不能比旧接口更弱。

建议：

- 为 `chatgptrest_ask` 增加 `min_chars` 参数。
- 为 `chatgptrest_followup` 同样暴露 `min_chars`。
- provider 默认值保持一致：
  - ChatGPT：800
  - Gemini/Qwen：200

### P1: 在 JobView / result 中增加“进度可观测性”字段

目标：让 agent 不需要翻 artifacts 才知道 worker 到哪一步了。

建议增加：

- `answer_chars`
- `last_event_type`
- `last_event_at`
- `prompt_sent_at`
- `assistant_answer_ready_at`
- `send_started_at`
- `phase_detail`
  - `awaiting_prompt_send`
  - `awaiting_assistant_answer`
  - `awaiting_export`
  - `quality_guard_wait`
- `completion_quality`
  - `suspect_short_answer`
  - `partial_visible_answer`
  - `export_pending`
  - `final`

### P1: 在 `completed` 但“质量可疑”时返回不同的 action hint

当前只有 `answer_ready` / `fetch_answer`，语义太粗。

建议增加：

- `answer_suspect_poll_export`
- `answer_short_wait_more`
- `answer_partial_do_not_followup_yet`

这样上层 agent 才不会把短答直接解释成“应该继续追问”。

### P1: 把离线核验规则前移到在线路径

既然 `ops/verify_job_outputs.py` 已经把 `short_completed_answer` 视为异常信号，就应把同一规则前移到运行时，而不是只在离线审计时发现。

### P2: 补测试矩阵

至少需要覆盖：

- send 阶段返回短答 + `status=completed`
- unified ask/followup 未传 `min_chars`
- JobView/result 返回的进度字段
- follow-up 场景下 `completed but suspect` 不触发额外人工追问

## 建议 issue 标题

`ChatGPT short partial answers can be marked completed, causing duplicate follow-ups and opaque worker state`

## Walkthrough

本次调查做了三件事：

1. 用 conversation URL 定位本地 job 链，确认两次追问分别对应 `4d4c69...` 和 `e4b1e0...` 两个独立 follow-up job，而不是 driver 重发。
2. 对比 `events.jsonl`、`answer.md`、`mcp_calls.jsonl`，确认前两次都以短答 `completed` 收敛，第三次则长期停在 `send/in_progress` 且对外不可诊断。
3. 反查 MCP 接口、执行器和 JobView 契约，确认问题由“send 阶段无强 completion guard + unified ask/followup 丢失 min_chars + 运行态字段过少”共同造成。
