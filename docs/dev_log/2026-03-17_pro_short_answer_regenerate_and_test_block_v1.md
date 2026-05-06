# 2026-03-17 Pro Short Answer Regenerate And Test Block v1

## 背景

近期 `openclaw + openmind` 上线后，`chatgpt_web.ask + pro_extended` 的请求量明显升高，其中混入了较多低价值短问和测试型请求。运行面同时出现两类问题：

1. `pro_extended` 偶发“秒出短答案”，没有正常 20-50 分钟的思考过程。
2. 用户在浏览器里手工点 `Regenerate` 后能看到更正常的答案，因此需要确认 ChatgptREST 是否会把前一个中间答案误判成最终答案。

## 调查样本

重点检查了以下近期会话：

- `79896fd2fa544a5da56d2dd045ff2895`
- `391205e34a4a49dfabff9b3b32d3f820`
- `1767cdf658a346e9bffe679cfe06d68b`
- `ecf7176eef404f5abe262a0b1a66c15a`

调查结论：

- 异常会话 `79896...` 与 `391205...` 的 `conversation.json` 都没有 `response 1/2` 分支，`branch_points=0`。
- 当前主问题不是“分支选错”，而是 conversation export 中把“附件取数失败 / 仅做前半段分析”的中间回答当成了候选答案。
- `79896...` 的典型文本是“无法获取 review bundle，请重新上传文件”；`391205...` 的典型文本是“我先审了部分文件，接下来继续分析”。
- 正常短答样本 `1767...` 和正常长答样本 `ecf717...` 都能被当前质量分类识别为 `final`。

## 根因

### 1. Pro 秒出短答的假完成

`classify_answer_quality()` 之前能识别纯 meta-commentary，但对“上下文获取失败”和“半截评审 stub”覆盖不够，导致 worker 在 wait/export 阶段把这些文本当成了可接受候选。

### 2. completion guard 的收口方式过软

即使识别到了短答风险，系统之前更多是“继续等”，没有把这类 `pro_extended` 异常快速答案显式切到 `needs_followup + regenerate` 路径。

### 3. 客户端仍能发低价值 Pro 短问

系统已经阻断了 `请回复 OK` 和 `purpose=smoke/test`，但像“请用四句话解释…”、“请简要说明…”这类低价值简短 Pro 请求仍能进入系统，增加官方风控风险。

## 修复

### A. 扩大异常短答识别面

文件：

- `chatgptrest/core/conversation_exports.py`

新增 `suspect_context_acquisition_failure`，覆盖两类中间答案：

- 附件 / bundle / upload / file retrieval failure
- “先看了一部分，后面继续分析”的 partial-review stub

### B. 对异常 Pro 短答切换到 regenerate 自愈

文件：

- `chatgptrest/worker/worker.py`

当以下条件同时满足时：

- thinking preset (`pro_extended` / `thinking_*`)
- answer quality 为 `suspect_short_answer` / `suspect_meta_commentary` / `suspect_context_acquisition_failure`
- 存在 `conversation_url`

worker 不再只给 `in_progress`，而是直接转成：

- `status = needs_followup`
- `error_type = ProInstantAnswerNeedsRegenerate`

同时，自动修复白名单新增这条 error type 的专属动作：

- `regenerate`
- `refresh`
- `restart_driver`

在 live 配置里 `CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX=1` 已开启，因此这条状态会实际触发 repair/autofix，而不是停留在静态标记。

### C. 前置阻断更多低价值 Pro 请求

文件：

- `chatgptrest/api/routes_jobs.py`

扩展 trivial brevity 检测，新增阻断：

- `请简要说明…`
- `请简短解释…`
- `简单介绍…`
- `简述…`

仍然允许通过 `allow_trivial_pro_prompt=true` 显式放行。

## 回归

执行通过：

```bash
./.venv/bin/pytest -q \
  tests/test_answer_quality_completion_guard.py \
  tests/test_block_smoketest_prefix.py \
  tests/test_worker_auto_autofix_submit.py \
  tests/test_worker_and_answer.py \
  tests/test_job_view_progress_fields.py \
  tests/test_gemini_answer_quality_guard.py \
  tests/test_longest_candidate_extraction.py \
  tests/test_min_chars_completion_guard.py \
  tests/test_deep_research_export_guard.py
```

## 结果解释

这轮修复后，系统对你关心的两个问题的行为变成：

1. **Pro 秒出短答案**
   - 不再直接 `completed`
   - 会被识别为异常快速答案
   - 自动切到 `needs_followup + regenerate`

2. **客户端再发测试短问题**
   - 默认直接在 `/v1/jobs` 前置拒绝
   - 不再让这类低价值 Pro 请求进入运行面

## 残留边界

这轮没有新增“多分支 response 1/2 显式择优”逻辑。当前调查样本里异常案例都没有 branch point，所以这不是主根因。若后续确认浏览器手工 `Regenerate` 后 conversation export 出现多分支，但 `current_node` 未稳定指向最终分支，再单独补 branch-aware export 选择。
