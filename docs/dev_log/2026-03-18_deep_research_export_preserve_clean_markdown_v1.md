# 2026-03-18 Deep Research Export Preserve Clean Markdown v1

## 背景

用户反馈 Deep Research 导出的 `answer.md` 中仍然出现不可读的内部 citation token，例如：

- `citeturn45view3`
- `entity[...]`
- `image_group{...}`

同时，手工导出的 Word 文档包含可读链接，因此怀疑“正式 report/export 视图”比 `conversation export` 更接近原始可交付内容。

## 调查结论

这次没有把主要精力放在 `conversation export` token 还原，而是先确认更简单的主路径：

1. 仓库里已经有现成的 Deep Research 导出链：
   - `Export to Markdown`
   - `Export to Word (DOCX) -> pandoc -> GFM Markdown`
2. 历史样本表明，很多 job 的 `answer_raw.md` 已经是干净、可读、带来源的 Markdown。
3. 问题在于后续 worker reconciliation 可能又把带内部 token 的 `conversation export` 覆盖回最终 `answer.md`。

换句话说，问题不一定是“拿不到 Word”，而是“拿到了干净结果，后面又被脏 export 反覆盖”。

## 本次修复

在 `chatgptrest/worker/worker.py` 增加了一个非常窄的护栏：

- 当 `conversation export` candidate 含有内部 export markup（如 `cite...`、``）
- 而当前 answer 已经是干净 Markdown
- 则：
  - Deep Research export override 不再覆盖当前 answer
  - conversation reconcile 不再优先选择该 candidate

具体修改点：

- `_contains_internal_export_markup()`
- `_deep_research_should_override_answer_with_export()`
- `_should_prefer_conversation_answer()`
- `_run_once()` 中最终 reconcile 的 `prefer_export` 判定

## 为什么先这样修

用户提出的方向是对的：对 Deep Research，应该优先信任正式 report/export 视图，而不是依赖 `conversation export` 的内部 token 文本。

但本轮先不扩到 UI 自动点击“缩略 report -> 全屏 report”，原因是：

- 当前已有 Word/Markdown export 主链
- 主要 bug 是 worker 后处理覆盖
- 先修这个能最快止损，而且风险最小

后续若仍发现“明明 UI 上能展开全屏 report，但系统没有拿到 export”，再补第二阶段：

- 自动点击缩略 report
- 进入全屏 report 视图
- 再尝试 `Export to Markdown / Export to Word`

## 回归

本轮新增/更新测试：

- `tests/test_deep_research_markdown_override.py`
- `tests/test_conversation_export_reconcile.py`

实际运行：

```bash
./.venv/bin/pytest -q tests/test_deep_research_markdown_override.py tests/test_conversation_export_reconcile.py
./.venv/bin/pytest -q tests/test_worker_and_answer.py -k 'completion_guard or worker_completes_job_and_answer_chunks'
```

均通过。

## 范围说明

本轮没有修改：

- `chatgpt_web_mcp/_tools_impl.py` 的 deep research widget 展开自动化
- `conversation export` 本身的 citation hydration

目标是先确保：**已经拿到的干净导出，不再被脏 export 覆盖。**
