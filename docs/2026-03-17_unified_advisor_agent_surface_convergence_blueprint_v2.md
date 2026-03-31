# 2026-03-17 Unified Advisor Agent Surface Convergence Blueprint v2

## 1. v2 调整原因

`v1` 的方向是对的，但还有一个潜在误区：

- 为了“省模型调用”，把 public agent facade 做成过度依赖规则的薄控制层
- 结果是 agent 看起来统一了，但实际上更笨，容易选错 route、误判完成、恢复能力差

这和用户目标冲突。用户真正要的是：

- agent 层更像一个可靠执行者
- 质量第一、效率第一
- 不因为节省少量 LLM 调用，换来更多误路由、返工、重试、用户二次指挥

因此 v2 的明确原则是：

**ChatgptREST 的 public agent interaction layer 必须 quality-first，不为省 LLM 而降智。**

## 2. 新核心原则

### 2.1 质量优先于 agent-layer 节流

可以节流的地方：

- 同一请求重复执行
- 无意义的第二次大模型质检
- 明显 trivial 的 planner 调用

不能为了省而降级的地方：

- 复杂任务的 route/plan
- 多附件/多目标任务的 prompt assembly
- 结果完成态判断
- 恢复后的再判断
- 高风险任务的最终验收

### 2.2 Public agent facade 不是 rule-only wrapper

v2 要求 public facade 至少具备三个智能节点：

1. **Planner**
   - 把用户意图、附件、上下文转换成真正可执行的 task plan
   - 在复杂场景下允许使用强模型做 planning / prompt synthesis / route adjudication

2. **Executor**
   - 调用现有 advisor / jobs / consult / image / repair substrate

3. **Judge**
   - 对最终结果做质量判定
   - 在必要时自动触发重试、升级 lane、二次评审或 follow-up

没有 `planner + judge` 的 facade，只是统一入口，不是可靠 agent。

### 2.3 成本不是主优化目标

这层的优化目标排序改成：

1. correctness / quality
2. total end-to-end latency
3. user steering burden
4. operator debuggability
5. cost

原因：

- 一个省了 1 次 LLM，但多了 2 次错误路由和 1 次人工返工的系统，整体更贵
- 用户体验差会直接压低吞吐和可信度

## 3. 目标架构修正

在 `v1` 的 public facade 基础上，明确新增一条 quality-first control loop：

```text
client
  -> /v3/agent/turn
      -> planner
      -> execution substrate
      -> judge
      -> if needed: retry/escalate/recover
      -> final delivery
```

### 3.1 Planner 该什么时候用 LLM

以下情况默认允许或推荐用强模型 planner：

- 用户意图模糊
- 请求含多个目标
- 带附件，尤其 zip / repo / 多文件
- 代码评审、架构评审、双模型评审、deep research
- 需要 deciding between `quick_ask / deep_research / consult / image / repair`
- 前一次同 session 已发生过 recovery / retry / suspect completion

以下场景才适合 deterministic fast path：

- 明确 KB direct hit
- 明确 status / cancel / result lookup
- 明确单一、低风险、无附件的简单 turn

### 3.2 Judge 该做什么

Judge 不只是看长度门槛。它至少要看：

- 是否回答了用户真实目标
- 是否正确消费了附件/上下文
- 是否应该继续等待，而不是错误 completed
- 是否需要升级为双模型 review
- 是否存在明显空转、占位回复、ack、模板化空结论

Judge 可分两档：

- deterministic gate
  - 长度
  - completion quality
  - artifact completeness
- LLM judge
  - 语义完成度
  - 与目标匹配度
  - 是否需要重新规划

### 3.3 Recovery 后必须重新 adjudicate

恢复动作后不能直接把结果交给用户，必须重新过 judge。

否则会出现：

- 会话恢复成功但答案质量仍差
- 自动重试成功但 route 仍错
- attachment 修好后仍没真正纳入上下文

## 4. v1 计划中需要修改的部分

### 4.1 Batch A 不再只是 facade shell

`v1` 的 Batch A 主要强调 contract 与 API surface。  
`v2` 要求 Batch A 同时落：

- public `/v3/agent/*`
- planner node
- judge node
- recovery-aware finalization

否则只是把旧系统包了一个新壳。

### 4.2 Public MCP 不能只是 HTTP 透传

`advisor_agent_turn` 的语义不能只是把用户文本转发到 `/v3/agent/turn` 再返回原始状态。

它应该：

- 走 quality-first public agent contract
- 拿到最终交付物
- 在返回里包含 provenance / next_action / recovery_status

### 4.3 OpenClaw convergence 不能只换 endpoint

`openmind_advisor_ask` 改打 `/v3/agent/turn` 只是第一步。  
更重要的是它得到的 contract 要比旧 `ask|advise` 更智能、更稳。

### 4.4 CLI / wrapper 不能保留“默认 provider-first”

如果 `chatgptrest_call.py` 只是表面包一层，但默认仍让用户选 provider/preset，那 public agent 心智仍然没建立。

## 5. 修订后的推荐实现范围

第一轮开发应一次性完成：

1. public `/v3/agent/*`
2. planner / judge / recovery-aware finalize
3. public `chatgptrest-agent-mcp`
4. OpenClaw advisor plugin convergence
5. CLI / wrapper convergence
6. 文档和接入规范同步

仍然保持：

- additive
- backward compatible
- 不删除旧入口

## 6. 质量优先的实现建议

### 6.1 Planner strategy

不要做“全量每 turn 大模型规划”，但也不要做“几乎全规则”。

建议：

- trivial / direct / status 类请求：规则
- ambiguous / complex / attachment-heavy / high-stakes：强模型 planner
- planner 输出结构化 plan：
  - intent
  - route
  - execution mode
  - required artifacts
  - quality expectation

### 6.2 Judge strategy

建议：

- default deterministic judge always on
- semantic LLM judge on for:
  - review
  - research
  - multi-attachment tasks
  - recovery-touched tasks
  - dual-model requested tasks

### 6.3 Escalation strategy

当 judge 认为不足时，允许：

- same-lane retry
- route escalation
- dual-model consult
- stronger-provider re-run

不要因为“省一次模型”而直接把弱结果交付。

## 7. 对 Claude Code 实施方式的影响

如果让 CC 来开发，任务规格必须显式要求：

- planner/judge/recovery 不是可选项
- 质量优先于 cost optimization
- 可以合理使用更强模型、更多 model-assisted review
- 最终要做 full integration tests 和 PR

## 8. 最终结论

`v1` 的收敛方向保留，但 `v2` 明确修正了一个关键点：

**Agent 版本的 ChatgptREST 交互层，不能因为想省模型调用而变成“统一但很笨”的 façade。**

正确做法是：

- 统一 surface
- 复用现有底座
- 在 planner / judge / recovery 节点上明确允许质量优先的 LLM 使用

这样得到的才是“更像 agent、同时更稳更快”的系统。
