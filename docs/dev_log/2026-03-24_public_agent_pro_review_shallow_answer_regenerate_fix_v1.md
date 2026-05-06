# 2026-03-24 Public Agent Pro Review Shallow Answer Regenerate Fix v1

## 背景

在对 `ChatGPT Pro` 的高价值评审任务进行真实提交时，出现了一个明显低质量但“形式上像最终答案”的回复：

- 回答很快出现
- 有 `Findings / Verdict` 等结构
- 语义上明显空泛、顺从
- 没有真正引用 prompt 明确要求的具体路径/材料锚点

现有保护链没有自动触发 same-turn regenerate。

## 根因

现有 `classify_answer_quality()` 主要覆盖三类问题：

- `suspect_short_answer`
- `suspect_meta_commentary`
- `suspect_context_acquisition_failure`

这意味着：

- 短答、思考前奏、附件获取失败能被拦住
- 但“长且有结构的空泛评审套话”会被误判成 `final`

进而：

- worker completion guard 不会降级
- `_should_reconcile_export_answer()` 也会把 export candidate 当作可接受最终答
- 不会进入 `ProInstantAnswerNeedsRegenerate`

## 修复策略

不粗暴放大全局规则，而是新增一个**只对高价值 review prompt 生效**的窄判定：

- 新质量标签：`suspect_review_shallow_verdict`
- 触发条件：
  - prompt 明确是 review/正式评审场景
  - prompt 明确要求 `Findings first`、`required reading`、`cite the problematic path` 等
  - answer 给出 `Path:`/`路径:` 样式标签，但没有任何真实文件路径锚点
  - 或 answer 大量使用 `sound / solid / realistic / coherent` 之类泛化认可词，同时对 prompt 中明确给出的 repo/commit/file anchors 完全没有回扣

## 代码改动

### 1. `conversation_exports.py`

- 为 `classify_answer_quality()` 增加可选参数 `question_text`
- 新增 review shallow verdict 检测：
  - `_extract_review_prompt_anchors()`
  - `_looks_like_review_shallow_verdict()`
- 在 `extract_answer_from_conversation_export_obj()` 的候选质量评估里传入 `question`

### 2. `worker.py`

- `_run_once()` 的 completion guard 传入 `question_text`
- `answer_quality_suspect_review_shallow_verdict` 纳入 same-turn regenerate 允许集合
- `_should_reconcile_export_answer()` 也传入 `question`，避免 export candidate 旁路这条新规则

## 验证

通过的定向回归：

- `tests/test_answer_quality_completion_guard.py`
- `tests/test_deep_research_export_guard.py`
- `tests/test_worker_and_answer.py::test_completion_guard_routes_suspicious_pro_short_answer_to_regenerate_followup`
- `tests/test_worker_and_answer.py::test_completion_guard_routes_generic_pro_review_verdict_to_regenerate_followup`
- `tests/test_public_agent_pro_regenerate_guard.py`
- `tests/test_longest_candidate_extraction.py`

并通过：

- `python3 -m py_compile`

## 边界

- 这次修的是 **review 类 Pro 任务的 shallow long-answer 自动 regenerate**
- 不是 full semantic grading engine
- 不是新的 live provider proof
- 不是对所有长答都做“语义质量审判”

## 结论

修复后，系统不再只拦截“短/元评论/上下文失败”三类异常。

对于 prompt 已明确要求具体路径和必读材料的 Pro review 任务，长而空泛、缺少材料锚点的“伪最终答”现在会被判成：

- `answer_quality_suspect_review_shallow_verdict`
- `needs_followup`
- `ProInstantAnswerNeedsRegenerate`

从而进入 same-conversation regenerate，而不是直接漏过。
