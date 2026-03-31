# 2026-03-08 外部评审收敛：补全 route.fallback 信号

## 背景
针对 EvoMap / 分层入库 / agent 进化链路，分别向 ChatGPT Pro 和 Gemini 发起了外部评审。

本地复核后发现：
- `ActivityExtractor` 已经存在并接入 runtime。
- `groundedness_checker` 已经存在，并实现了 path / service / staleness 基础校验。
- `Wave2` 的 manifest 与 screening decisions 已经生成，不是待做项。
- `scratch -> live` 迁移仍然应保持保守，不应因为外部建议而提前放开。

真正缺失的一项是：
- 路由执行链在 provider 失败后虽然会继续 fallback，但没有把“从哪个 provider 降级到哪个 provider”作为独立 EvoMap 信号留下来。

这会让后续 agent 演化只能看到 candidate outcome，难以直接识别脆弱 route sequence。

## 本次改动
1. 新增 `SignalType.ROUTE_FALLBACK`
   - 文件：`chatgptrest/evomap/signals.py`
2. 在 `FeedbackCollector` 中新增 `emit_fallback()`
   - 文件：`chatgptrest/kernel/routing/feedback.py`
3. 在 `RoutingFabric.get_llm_fn()` 的 fallback chain 中，当当前 provider 失败/空响应且还有下一个候选时，显式发出 `route.fallback`
   - 文件：`chatgptrest/kernel/routing/fabric.py`
4. 补测试
   - `tests/test_routing_fabric.py`
   - 覆盖：fallback 信号 payload；先失败后成功链路中确实发出 `route.fallback`

## 为什么只做这一项
Gemini 的其它建议里，有两项经核实已经完成：
- `ActivityExtractor`
- `groundedness_checker`

因此这次不重复实现已有能力，只补真实缺口。

## 验证
- `PYTHONPATH=. pytest -q tests/test_routing_fabric.py tests/test_routing_scenarios.py`
- 结果：通过

## 暂不执行的项
### `homeagent_gateway_port` 冲突
冲突是真实存在的：
- `maint` 当前 host fact：`18081`
- `homeagent` repo 默认和多份文档仍写 `18080`

但这不是 `ChatgptREST` 代码内问题，而且 `homeagent` 当前不是本次收口目标，因此仅在外部评审汇总中列为后续动作。

### `scratch -> live` 迁移
不因为这轮外部评审而提前放开。仍保持：
- scratch 持续验证
- live 单独治理
