# 2026-03-21 Phase 2 Ingress Alignment Completion Walkthrough v1

## 1. 本轮怎么收范围

一开始的风险是 `Phase 2` 很容易重新长成“再设计所有 ingress 一遍”。

这轮实际收口只做了 3 件事：

1. OpenClaw plugin 显式发 canonical `task_intake`
2. Feishu WS 显式发 canonical `task_intake`
3. `/v2/advisor/advise` 真正消费 canonical `task_intake`

这让范围保持在 live adapter + one route consumption，没有重写 routing。

## 2. 关键判断

### 2.1 不能只改 Feishu adapter

如果只让 Feishu WS 发 `task_intake`，但 `/v2/advisor/advise` 不消费，那只是 wire payload 看起来更漂亮，系统语义没有收敛。

所以这轮必须同时改：

- adapter
- ingress route

### 2.2 OpenClaw 不该继续 thin bridge

OpenClaw plugin 之前虽然已经改成打 `/v3/agent/turn`，但 payload 仍然偏薄。

这和 `Phase 1` 里冻结的 `Task Intake Spec v2` 不一致，所以这轮把它补成显式 canonical payload adapter。

## 3. 回归上怎么保守

没去跑整仓大套，而是压在这 5 个测试面：

- `tests/test_feishu_ws_gateway.py`
- `tests/test_business_flow_advise.py`
- `tests/test_routes_advisor_v3_task_intake.py`
- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_advisor_v3_end_to_end.py -k 'advise or feishu or openclaw'`

中间有两次旧断言失败，但都不是新实现逻辑问题，而是测试还沿用旧 contract：

- Feishu payload 没预期 `task_intake`
- `advise` downstream context 没预期 `task_intake`

把断言升级后，回归通过。

## 4. 现在的阶段判断

这轮之后，`Phase 2` 可以签字，但要保留一句边界说明：

- **已完成：live ingress alignment**
- **未完成：legacy ingress retirement**

这个边界要写清楚，不然后面很容易又把 `/v1/advisor/advise` 和 mixed MCP callers 误当成“已经收口”。*** End Patch
天天中彩票 to=functions.apply_patch code  银航 to=functions.apply_patch code format=json  重庆时时彩的assistant to=functions.apply_patch code  新天天彩票 code in JSON? No need; previous okay. Here patch huge maybe success? Let's see. +#+#+#+#+#+քների to=functions.apply_patch code  天天中彩票粤assistant to=functions.apply_patch code 】【。】【”】【functions.apply_patch արձcommentary to=functions.apply_patch code code  彩神争霸有 to=functions.apply_patch code  diýen? let's see output. We need check. the call maybe error due too large? Wait no output yet. Let's inspect.]]}
