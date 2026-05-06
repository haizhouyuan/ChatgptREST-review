# 2026-03-24 Public Agent Pro Review Shallow Answer Regenerate Fix Walkthrough v1

## 做了什么

修补了 `ChatGPT Pro` 高价值 review 任务中“长且空泛的伪最终答案”无法触发自动 regenerate 的缺口。

## 为什么做

真实事故里，系统拿到了一条：

- 结构完整
- 字数不短
- 但实际没有做深入评审

的 `Pro` 回答。旧规则只会拦：

- 短答
- meta-commentary
- context acquisition failure

所以它被当成 `final` 漏过去了。

## 怎么做的

### 1. 给 answer quality 增加 review-aware 窄规则

只有当 prompt 明确表现出以下特征时才会生效：

- `required reading`
- `Findings first`
- `cite the problematic path`
- 正式 review / 评审语义

然后再看 answer 是否：

- 伪造 `Path:` / `路径:` 标签
- 但没有真实文件路径锚点

或：

- 大量泛化认可措辞
- 完全不回扣 prompt 里的 repo / commit / file anchors

### 2. 把这条规则接到两个关键位置

- completion guard
- export reconcile guard

这样不会出现：

- worker 主路径拦住了
- export candidate 又绕过去

### 3. 补回归

新增覆盖了：

- classifier 本身
- export reconcile
- worker 的 same-turn regenerate
- public-agent 的 `ProInstantAnswerNeedsRegenerate` 投影

## 结果

现在高价值 review prompt 再遇到这类“长文套话假结论”，不会直接完成，而会被降级成：

- `needs_followup`
- `same_session_repair`
- `ProInstantAnswerNeedsRegenerate`

## 没做的

- 没把它扩成通用语义评分器
- 没对普通 concise answer 增加额外负担
- 没做任何新的 ChatGPT Pro smoke
