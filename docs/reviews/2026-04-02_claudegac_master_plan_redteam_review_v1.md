# 2026-04-02 ClaudeGAC Master Plan Redteam Review v1

## 1. 这份文档在做什么

这份文档记录的是：

1. `claudegac` 对 master plan v1 的红队审核
2. 我对这些红队意见的独立判断
3. 哪些意见会进入 master plan v2

这份文档不是把红队当裁判，而是把它当 adversarial input。

本轮 red-team 对应：

1. `run_id`: `ccjob_20260402T150001Z_e9109d8d`
2. `run_dir`: `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T150001Z_e9109d8d`
3. `stdout.log`: `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T150001Z_e9109d8d/logs/stdout.log`
4. `claude_result.json`: `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260402T150001Z_e9109d8d/result/claude_result.json`

## 2. 红队最重要的 7 条意见

### 2.1 F1

master plan 把：

1. `task_id allocation`
2. `checkpoint write`
3. `checkpoint read-back`
4. `OpenClawBot resume`

说得太像“找落点”，实际更像要建 3 到 4 个新集成点。

### 2.2 F2

`OpenClawBot -> canonical task plane` 现在不能叫“收敛”，更准确应该叫“建设”。

### 2.3 F3

当前 `openmind-advisor` 插件只有：

1. `openmind_advisor_ask`

没有：

1. `task_id` 参数
2. `resume` 能力
3. `status` 能力

所以 master plan 里“从 OpenClawBot 找回并继续”这半条链当前没有代码现实。

### 2.4 F4

master plan 一边说 `publicagentmcp` “不再继续长胖”，一边又让任务连续性落在现有 canonical task plane 上，这里存在实际张力。

### 2.5 F5

6 字段 checkpoint 虽然方向对，但当前仍然是 paper design，不是现成能力。

### 2.6 F6

“每步都要有红队 gate”说得太满，操作上更现实的是“每个切片 / 每个里程碑 red-team gate”。

### 2.7 F7

`Feishu` 这件事不能只靠 owner 拍板来假设成立。

需要先验证：

1. `OpenClawBot` 现在能不能接住 `会议沉淀` 所需材料
2. 这些材料能不能真实带到 `/v3/agent/turn`

## 3. 我独立核验后接受的部分

### 3.1 接受：F1

这点我接受。

我独立核到：

1. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L349) 只有 `logical_task_id`
2. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L396) 只是 telemetry 透传
3. [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py) 对 `task_id / checkpoint / task_runtime` 没有真实接线

所以 master plan v1 的确低估了工程量。

### 3.2 接受：F2

这点我接受。

`OpenClawBot -> canonical task plane` 现在只能说：

1. 已有 `/v3/agent/turn` 调用桥

不能说：

1. 已有完整 task continuity 桥

所以 v2 会把“收敛”改成“建设”。

### 3.3 接受：F3

这点我接受。

我独立核到：

1. [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L358) 只注册了 `openmind_advisor_ask`
2. 文件里没有 `task_id`
3. 也没有 `status` / `resume` tool

所以“从 OpenClawBot 找回并继续”不能再写得像已存在半条能力。

### 3.4 接受：F5

这点我接受。

6 字段 checkpoint 是方向，不是现成件。

### 3.5 接受：F6

这点我接受。

后续口径从：

1. 每步红队

改成：

1. 每个切片 / 里程碑红队

更诚实，也更可执行。

### 3.6 接受：F7

这点我接受。

`Feishu -> OpenClawBot` owner 已经拍板，但：

1. owner 拍板不等于会议沉淀材料链已经成立

所以在实施规格之前，必须先做一轮 `OpenClawBot` 材料 smoke test。

## 4. 我部分接受的部分

### 4.1 部分接受：F4

红队说：

1. `publicagentmcp` “不再继续长胖”与 MVP 连续性要求矛盾

我部分接受。

更准确的独立判断是：

1. 不应继续机会主义扩张 `publicagentmcp`
2. 但 phase-1 MVP 如果要通过 canonical task plane 证明任务连续性，允许有 **最小的 continuity-related 增量**

所以 v2 会把口径改成：

> 不做大杂烩式扩张，但允许为 phase-1 MVP 增加最小的 `task_id / checkpoint query` 相关能力。

## 5. 我不按原话采纳的部分

### 5.1 不直接采纳：绕开 `task_runtime`，完全改走 `AgentSessionStore`

红队给出的替代建议是：

1. `task_id` 放在 `/v3/agent/turn`
2. checkpoint 放到 `AgentSessionStore` sidecar
3. 先完全绕开 `task_runtime`

我的独立判断是：

1. 这条建议很有现实价值，适合作为 phase-1 MVP 的实施路径候选
2. 但我不会把它写成“最终任务层架构”

所以 v2 会采取更准确的说法：

> phase-1 MVP 允许使用 `AgentSessionStore` sidecar 作为临时 continuity carrier，但这不等于最终 task truth layer 就等于 session store。

## 6. 进入 v2 的改写

master plan v2 将做 6 个改写：

1. 把“收敛”改成“建设”
2. 增加 `Step 0: OpenClawBot 会议沉淀材料 smoke test`
3. 把 checkpoint 明确改成“baseline”，不再写成像冻结成品
4. 把红队 gate 改成“每切片 / 每里程碑”
5. 把 `publicagentmcp` 口径改成“不做 opportunistic sprawl，但允许 MVP 最小增量”
6. 把 phase-1 continuity carrier 写成：
   - 优先考虑 `/v3/agent/turn + AgentSessionStore sidecar`
   - 不把 full `task_runtime` 当 MVP 前置

## 7. 一句话判断

这轮红队没有推翻 master plan 的方向，但它成功证明：

> v1 版本把第一条切片说得还不够“工程化”。v2 需要把它从“总计划主控稿”进一步改成“带依赖顺序、带最小实现路径、带 smoke-test 前置”的实施主控稿。
