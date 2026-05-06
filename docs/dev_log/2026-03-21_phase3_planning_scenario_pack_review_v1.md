# 2026-03-21 Phase 3 Planning Scenario Pack Review v1

## 总评

`Phase 3: Planning Scenario Pack` 的方向是对的，而且已经不只是 schema 冻结，而是真正进入了 live ingress、strategist、prompt、controller、advisor graph、funnel graph 这条主链。

但如果这轮评审标准不是“代码已接通”，而是“是否符合真实场景使用、是否稳定产出高质量结果”，那我不会直接给满分通过。当前实现最主要的问题不是 crash，而是 **过度重型化、澄清不足、语义覆盖不够完整、以及 pack 元数据有一部分还停在 paper contract**。

## Findings

### 1. 会议纪要 / 面试纪要这类低上下文请求，当前会经常直接执行而不是先澄清，质量风险偏高

这是我认为最影响实际输出质量的一点。

当前链路里：

- `meeting_summary / interview_notes` pack 会把 canonical `scenario` 固定为 `planning`
- `task_intake -> AskContract` 时，`planning` 又会被统一映射成 `implementation_planning`
- `AskContract.calculate_completeness()` 会因为 `objective + output_shape + non-general task_template` 给到约 `0.6`
- `build_strategy_plan()` 对 `medium` risk ask 只有在 completeness `< 0.50` 才会真正触发 clarify

直接证据：

- `chatgptrest/advisor/task_intake.py:320`
- `chatgptrest/advisor/task_intake.py:344`
- `chatgptrest/advisor/ask_contract.py:91`
- `chatgptrest/advisor/ask_contract.py:108`
- `chatgptrest/advisor/ask_strategist.py:169`
- `chatgptrest/advisor/ask_strategist.py:171`

我本地最小复现确认：

- 对 `“请总结面试纪要”`
- pack 会命中 `interview_notes`
- contract 会变成 `task_template=implementation_planning`
- `contract_completeness=0.6`
- strategist 会产出多条 clarify questions，但 `clarify_required=False`

这意味着用户没有给出候选人、岗位、轮次、使用目的时，系统仍会直接交给 report route 执行。对纪要类场景，这很容易产出“结构完整但对象错、范围错、结论发虚”的结果。

### 2. `business_planning` 现在是一旦命中就强制走 `funnel + job`，会把轻量规划也重型化

从用户角度，这是第二个明显的使用体验风险。

当前 `business_planning` pack 的策略是：

- profile 命中后直接给 `route_hint=funnel`
- `execution_preference=job`
- controller 再用 `scenario_pack` 强制 route override + 强制 execution kind = `job`

直接证据：

- `chatgptrest/advisor/scenario_packs.py:391`
- `chatgptrest/advisor/scenario_packs.py:397`
- `chatgptrest/controller/engine.py:833`
- `chatgptrest/controller/engine.py:835`
- `chatgptrest/controller/engine.py:1747`
- `chatgptrest/controller/engine.py:1750`

我本地最小复现确认：

- `“请帮我做一个业务规划框架，先给简要版本，不要走复杂流程”`
- 仍然会命中 `business_planning`
- strategist 最终 `route_hint=funnel`
- execution path 会被固定在 `job`

这会带来两个问题：

- 用户明确想要“简要/轻量版本”时，系统仍会推到重型规划链路，延迟和交互成本变高
- `planning` pack 目前缺少“light planning / quick planning memo”分支，导致 route policy 不区分任务体量

### 3. 会议纪要场景的中文覆盖还不够，常见写法 `例会纪要` 当前不会命中 `meeting_summary`

这是一个更偏“场景覆盖率”的问题，但它很真实。

当前 `meeting_summary` 的关键词列表覆盖了：

- `会议总结`
- `会议纪要`
- `会议记录`
- `复盘纪要`
- `meeting summary / meeting notes / meeting minutes`

但没有覆盖常见中文短写：

- `例会纪要`

直接证据：

- `chatgptrest/advisor/scenario_packs.py:58`
- `chatgptrest/advisor/scenario_packs.py:67`
- `chatgptrest/advisor/scenario_packs.py:208`

我本地最小复现确认：

- `“请整理今天例会纪要”`
- `resolve_scenario_pack(...)` 返回 `None`

这说明 pack 虽然已经进入主链，但语义词表还没有覆盖到高频真实说法。对中文业务场景，这会直接影响 pack 命中率。

### 4. `watch_policy` 和 `funnel_profile` 目前还没有真正变成 runtime policy，更多还是说明性元数据

这不是立即的功能 bug，但会影响“这轮是否真的把 scenario pack 做成完整产品 contract”的判断。

在 `ScenarioPack` 里现在已经冻结了：

- `watch_policy`
- `funnel_profile`

直接证据：

- `chatgptrest/advisor/scenario_packs.py:29`
- `chatgptrest/advisor/scenario_packs.py:30`
- `chatgptrest/advisor/scenario_packs.py:35`

但我在当前代码里能确认到的 live 消费是：

- `watch_policy` 只在 prompt builder 里被渲染进 `Scenario Pack` block
- `funnel_profile` 没有看到实际 runtime 消费点

直接证据：

- `chatgptrest/advisor/prompt_builder.py:457`
- `chatgptrest/advisor/prompt_builder.py:463`

也就是说，这两项目前更像“未来 policy 预留字段”，还不是已经能改善交付质量或观测行为的 live policy。

## 这轮做对了什么

尽管上面有问题，我仍然认为这轮做对了几件关键事：

- `planning` 终于不再只是一个裸 `scenario` 值，而是有 profile、route、acceptance、prompt contract 的稳定对象
- ingress 层已经把 `scenario_pack` 和 canonical `task_intake` 一起带下游，说明这不是文档层 freeze，而是 live path 语义收敛
- `meeting_summary / interview_notes` 走 `report`、`implementation/business/workforce` 走 `funnel` 这个大方向基本符合用户心智
- `planning` 当前强制 `job` 而不是 `team`，短期内是务实的，避免 team lane 语义再次把 planning 弄漂

## 评审判断

如果这轮评审标准是：

- `planning` 是否已经成为稳定 scenario pack
- live path 是否已经能消费它

这轮通过。

如果这轮评审标准是：

- 真实用户在 planning / 纪要 / 面试笔记场景里，是否已经能稳定得到“既不过重，也不缺澄清”的高质量结果

这轮还不能写成“质量已稳定”。

我会把当前状态定性成：

- **architecture direction: correct**
- **live integration: complete enough**
- **scenario quality: not yet fully tuned**

## 最值得优先补的 3 件事

1. 让 `meeting_summary / interview_notes` 这类低上下文场景更容易触发 clarify，而不是因为 completeness 被高估而直接执行。
2. 给 `planning` 增加 light / outline 分支，避免所有 business planning 都被一刀切进 `funnel + job`。
3. 扩充中文 planning / note-taking 词表，至少补上 `例会纪要`、`周会纪要`、`讨论纪要` 这类高频真实写法。

## 本轮复跑

我重新执行并通过了你列的两组回归：

```bash
./.venv/bin/pytest -q \
  tests/test_scenario_packs.py \
  tests/test_ask_strategist.py \
  tests/test_prompt_builder.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_advisor_graph.py \
  tests/test_funnel_graph.py \
  tests/test_controller_engine_planning_pack.py

./.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_feishu_ws_gateway.py \
  tests/test_agent_v3_routes.py \
  tests/test_advisor_v3_end_to_end.py \
  tests/test_business_flow_advise.py \
  -k 'openclaw or feishu or advise or v3 or agent_turn'

python3 -m py_compile \
  chatgptrest/advisor/scenario_packs.py \
  chatgptrest/advisor/ask_strategist.py \
  chatgptrest/advisor/prompt_builder.py \
  chatgptrest/advisor/graph.py \
  chatgptrest/advisor/funnel_graph.py \
  chatgptrest/api/routes_agent_v3.py \
  chatgptrest/api/routes_advisor_v3.py \
  chatgptrest/controller/engine.py \
  chatgptrest/advisor/feishu_ws_gateway.py \
  tests/test_scenario_packs.py \
  tests/test_ask_strategist.py \
  tests/test_prompt_builder.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_advisor_graph.py \
  tests/test_funnel_graph.py \
  tests/test_controller_engine_planning_pack.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_feishu_ws_gateway.py \
  tests/test_agent_v3_routes.py \
  tests/test_advisor_v3_end_to_end.py \
  tests/test_business_flow_advise.py
```
