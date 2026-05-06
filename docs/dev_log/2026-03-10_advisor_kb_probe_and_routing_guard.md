# 2026-03-10 advisor kb probe and routing guard

## Context

在真实 `/v2/advisor/advise` / `/v2/advisor/ask` 业务探针里发现两个比单测更重要的问题：

1. `kb_probe()` 几乎只按 hit 数量估算 `kb_answerability`
   - 3 个 hit 就能到 `0.75`
   - 即使 query 与 KB 片段完全不相关，也会被判成可直接回答
2. `analyze_intent()` 对真实中文业务语义覆盖不足
   - `我们要做一个销售奖励积分系统，请输出关键业务流程、核心实体和最小可行版本方案`
     被判成 `QUICK_QUESTION`
   - `调研行星滚柱丝杠产业链的关键玩家、国产替代进展和主要技术瓶颈`
     被判成 `WRITE_REPORT`

直接后果：

- `/v2/advisor/ask` 会把复杂业务请求误截成 `kb_answer`
- `/v2/advisor/advise` 会把无关 KB 片段直接吐给用户

## Root Cause

### 1. KB probe 过度乐观

旧逻辑：

- `answerability = min(0.3 + 0.15 * len(hits), 1.0)`
- `any hit => kb_has_answer = True`

这会把很多“只是 FTS 撞上了常见词”的检索结果错误提升成 direct-answer 级别。

### 2. 中文 build / research 信号不够

- build 类提示缺少：
  - `业务流程`
  - `核心实体`
  - `最小可行版本`
  - `积分系统`
  - `做/开发/...系统|方案` 这种产品实现模式
- write deliverable 信号里还残留了裸词 `进展`
  - 它会把“国产替代进展”这类研究问题误拉成 report

### 3. `/v2/advisor/advise` 还有一层 quick_ask 残口

即使 `kb_has_answer=False`，`execute_quick_ask()` 仍然会把 `kb_top_chunks` 原样塞进 `quick_ask()`，导致低质量 KB 命中继续污染 quick/hybrid 路径。

## Change

### KB probe

在 `chatgptrest/advisor/graph.py`：

- 新增 query term 抽取与 chunk 文本重叠比率
  - ASCII 词：长度 >= 3
  - 中文：对连续汉字段做 2/3-gram
- `kb_answerability` 改成：
  - 小幅 hit 数信号
  - 主要依赖 `term_overlap`
- `kb_has_answer` 只在 overlap 与 answerability 都过线时成立

### Intent

在 `analyze_intent()`：

- 移除裸词 `进展`
- 保留更明确的 `进展报告 / 进展汇报`
- 增加 build deliverable 信号：
  - `业务流程`
  - `关键业务流程`
  - `核心实体`
  - `实体关系`
  - `最小可行版本`
  - `最小可行方案`
  - `积分系统`
- 增加产品构建正则：
  - `做/开发/实现/设计/搭建/规划 ... 系统|应用|平台|工具|流程|方案|实体`

### KB direct safeguard

在 `chatgptrest/api/routes_advisor_v3.py`：

- 新增 `_kb_direct_completion_allowed()`
- 只有同时满足以下条件才允许 sync direct completion：
  - `route == kb_answer`
  - `intent_top == QUICK_QUESTION`
  - 非 multi-intent
  - 非 action / verification
  - `step_count_est <= 1`
  - `constraint_count == 0`
  - `kb_answerability >= 0.85`

### Quick ask residual guard

在 `execute_quick_ask()`：

- 只有 `kb_has_answer=True` 时才把 `kb_top_chunks` 作为 quick_ask 的 KB 输入

## Validation

### Targeted tests

- `./.venv/bin/pytest -q tests/test_advisor_graph.py tests/test_advisor_v3_end_to_end.py`
- `./.venv/bin/pytest -q tests/test_advisor_graph.py tests/test_advisor_v3_end_to_end.py tests/test_phase3_integration.py -k 'advisor or quick_ask'`
- `./.venv/bin/python -m py_compile chatgptrest/advisor/graph.py chatgptrest/api/routes_advisor_v3.py tests/test_advisor_graph.py tests/test_advisor_v3_end_to_end.py`

### Live business probes after API restart

入口：`http://127.0.0.1:18711`

结果：

- `什么是知识库检索增强？`
  - `/v2/advisor/advise`
  - `route=hybrid`
  - 不再吐无关 KB 片段，而是明确说明“当前知识库里没有直接定义”
- `请给我写一份关于行星滚柱丝杠资产梳理的正式汇报...`
  - `/v2/advisor/ask`
  - `route=report`
  - `status=submitted`
- `调研行星滚柱丝杠产业链的关键玩家、国产替代进展和主要技术瓶颈`
  - `/v2/advisor/ask`
  - `route=deep_research`
  - `status=submitted`
- `我们要做一个销售奖励积分系统，请输出关键业务流程、核心实体和最小可行版本方案`
  - `/v2/advisor/ask`
  - `route=funnel`
  - `status=submitted`

并且 3 个异步 job 已确认进入真实生命周期：

- report: `in_progress/send`
- deep_research: `in_progress/send`
- funnel: `queued`

## Conclusion

这轮收掉的不是“测试里一个小偏差”，而是 advisor 热路径里两个会直接影响真实业务体验的策略缺陷：

- KB 命中过度乐观
- 中文 build / research 业务语义识别不足

修完后，系统更保守，但明显更接近生产可用。
