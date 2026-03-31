# 2026-03-21 Phase 3 Planning Scenario Pack Review Walkthrough v1

## 目标

这轮不是做“Phase 3 是否接上线”的核验，而是做更偏产品与架构质量的评审：

- planning pack 是否符合真实场景使用
- route / clarify / prompt / runtime 组合后，结果质量会不会稳定
- 是否存在“接通了，但体验会偏重、偏虚、偏误判”的地方

## 本轮实际怎么评

### 1. 先看阶段文档，再看代码，不倒推结论

我先读了：

- `docs/dev_log/2026-03-21_planning_scenario_pack_v1.md`
- `docs/dev_log/2026-03-21_phase3_planning_scenario_pack_completion_v1.md`

确认这轮自我声明的目标是：

- planning 从单一 scenario 升级成稳定 pack
- strategist / prompt / controller / graph / funnel 都消费它
- planning 当前固定走 `job`

### 2. 重点看 5 个 live 消费层

我逐个看了：

- `chatgptrest/advisor/scenario_packs.py`
- `chatgptrest/advisor/ask_strategist.py`
- `chatgptrest/advisor/prompt_builder.py`
- `chatgptrest/controller/engine.py`
- `chatgptrest/advisor/graph.py`
- `chatgptrest/advisor/funnel_graph.py`
- `chatgptrest/api/routes_agent_v3.py`
- `chatgptrest/api/routes_advisor_v3.py`

重点不是“字段有没有传”，而是：

- pack 是否会把用户误导进过重的 route
- pack 是否真的帮助 clarify
- pack 元数据是否真的被 runtime 使用

### 3. 复跑回归，确认不是实现崩坏

我重新跑了你列的两组 pytest 和 py_compile，全部通过。

这说明这轮主要问题不是 crash、syntax 或直接回归，而是更上层的：

- 场景判定是否准
- 任务体量是否分层
- 缺信息时是否真的先澄清

### 4. 做了几组最小复现

我额外做了几组本地最小复现，重点观察 scenario pack 命中与后续策略：

1. `请总结面试纪要`
2. `请帮我做一个业务规划框架，先给简要版本，不要走复杂流程`
3. `请整理今天例会纪要`

从这些复现里，确认了 4 类质量问题：

- note-taking ask 会直接执行而不是先 clarify
- business planning 会被过早重型化
- 常见中文写法 `例会纪要` 当前不会命中 `meeting_summary`
- `watch_policy / funnel_profile` 还没有真正变成 runtime policy

## 关键判断

### 判断一：Phase 3 做成了“稳定 pack”

这一点我认可。

因为它现在确实不是一个裸 label，而是：

- profile
- route_hint
- execution_preference
- prompt_template_override
- acceptance
- evidence
- review_rubric

并且这些东西已经进入 live ingress 和 runtime path。

### 判断二：Phase 3 还没有做成“高质量场景成品”

这一点我不认可。

主要原因不是方向错，而是“pack policy 太粗”：

- 一部分 ask 明显还应该先 clarify
- 一部分 ask 明显不该直接进入重型 funnel
- 一部分高频真实词法还没覆盖

也就是说，这轮已经从“架构未成形”进入了“策略调优阶段”。

## 我给这轮的最终定性

我给的定性不是“不过”，而是：

- **实现层完成**
- **产品层未完全调优**

如果后面要继续做 Phase 3.1 之类的小收尾，我会建议按这个顺序：

1. 先修 clarify gate，让 meeting/interview notes 不再低上下文直跑
2. 再加 light planning 分层，别把所有 planning 都塞进 funnel
3. 最后补齐中文高频 planning/note-taking 词法

## 产物

本轮新增：

- `docs/dev_log/2026-03-21_phase3_planning_scenario_pack_review_v1.md`
- `docs/dev_log/2026-03-21_phase3_planning_scenario_pack_review_walkthrough_v1.md`
