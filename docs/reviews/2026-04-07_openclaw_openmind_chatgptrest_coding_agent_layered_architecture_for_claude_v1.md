# 2026-04-07 OpenClaw / OpenMind / ChatgptREST / Coding-Agent Layered Architecture For Claude v1

## 1. 这份文档要解决什么问题

当前系统已经证明：

- Feishu 入口是 `OpenClaw`
- `OpenMind` 插件可以把复杂任务桥接到 `ChatgptREST`
- `ChatgptREST` 可以把 planning 任务结构化落盘
- `coding_agent` lane 已经证明 `codex` 与 `claudegac` 可以交付正式结果

但系统边界仍然容易被误解。

最常见的混乱是：

1. `OpenClawBot`、`OpenMind plugins`、`ChatgptREST`、`Codex/Claude Code` 都在试图承担“项目脑子”
2. 前台入口太薄，导致复杂项目不能稳定识别、转单、续做
3. 插件层被误当成“主系统”，而不是桥接层
4. `ChatgptREST` 被误当成“复杂项目长期脑子”，而它更适合做状态真相层
5. `resume` 长会话的优势和 `task/checkpoint` 结构化状态的优势没有被组合起来

这份方案的目标不是继续增加一套新系统，而是明确：

> 复杂项目型 agent 的最终形态里，哪一层该厚，哪一层该薄，哪些职责必须保留，哪些职责必须下放。

## 2. 当前最准确的事实关系

当前正确的链路不是平行多系统，而是：

`Feishu -> OpenClaw -> OpenMind plugin -> ChatgptREST -> execution lane`

其中：

1. `Feishu`
   - 只是用户入口

2. `OpenClaw`
   - 前台 agent runtime
   - 负责接收用户消息、理解是否需要工具调用、协调前台交互

3. `OpenMind plugins`
   - 装在 `OpenClaw` 里的工具桥
   - 负责把前台对话转成后端任务请求
   - 代表能力：
     - `openmind-advisor`
     - `openmind-memory`
     - `openmind-graph`
     - `openmind-telemetry`

4. `ChatgptREST`
   - 后端任务与状态中台
   - 负责：
     - task/session/checkpoint/handoff
     - continue/branch
     - public truth surface
     - quality gate
     - execution lane routing

5. `execution lane`
   - 负责真正产出内容
   - 当前已证明的主 execution lanes：
     - `web`
     - `coding_agent`
   - 其中 `coding_agent` 当前已纳入合同的 executors：
     - `codex`
     - `codex2`
     - `claudeminmax`
     - `claudegac`

## 3. 当前混乱的真正根因

当前最深的结构性问题，不是代码有没有，而是“脑子放错层了”。

过去几轮演进里，以下几层都部分承担了“项目脑子”的职责：

1. `OpenClaw` 前台 prompt
2. `OpenMind plugin` 的参数和展示逻辑
3. `ChatgptREST` 的 planning route / task plane
4. `Codex / Claude Code` 的长会话与 resume

这导致 4 个后果：

1. 前台入口太弱：
   - 不足以识别复杂项目的 continue / branch / project association

2. 插件层过重：
   - 容易把业务逻辑塞进桥接层

3. 后端被误当成长期项目脑子：
   - 实际上它更擅长结构化状态，而不是无限长会话推理

4. 长会话 agent 的优势没有被制度化利用：
   - 复杂项目真正需要的深度推进，天然更适合成熟 agent 长 session + resume

## 4. 最核心的设计判断

### 4.1 不应把 OpenMind plugin 取代掉

`OpenMind plugins` 不是应该被删除，而是应该被降级成“桥接层”。

它们不应该再承担：

- 项目长期脑子
- 复杂业务判断主逻辑
- 长期记忆主来源

它们应该承担：

- 前台到后端的转单
- 上下文注入
- 查状态
- 查图谱
- 记忆读取/写回的受控桥接
- 用户可读结果格式化

一句话：

> plugin 不是脑子，是桥。

### 4.2 不应把 ChatgptREST 取代掉

`ChatgptREST` 也不应该被 resume 会话完全替代。

原因是：

- 长 session 擅长连续理解
- 但不擅长提供结构化、可交接、可审计的系统真相

`ChatgptREST` 最适合保留的职责是：

- task 真相层
- checkpoint/handoff
- branch/continue contract
- artifact / status / evidence
- public truth surface

一句话：

> ChatgptREST 不是复杂项目的唯一脑子，但它必须继续做项目的结构化真相层。

### 4.3 复杂项目的主脑应该迁到成熟 coding agent

对于你这种复杂、长期、多材料、多轮讨论、多次改写的业务项目，最适合承担主脑角色的是：

- `Codex`
- `Claude Code`

前提是它们被当成成熟 agent 产品来配置，而不是一次性代码工具。

这意味着：

- 固定 workspace
- 固定项目资料入口
- 固定工具/MCP
- 长 session
- resume 续跑

一句话：

> 对复杂项目，真正的长期项目脑子应该是成熟的长会话执行 agent。

## 5. 最终推荐的四层分工

### Layer A：Feishu / OpenClaw 入口层

定位：

- 用户交互层
- 项目关联识别层
- 任务编排层

应该变厚的地方：

1. 识别项目
   - 例如识别：
     - `两轮车车身业务`
     - `0497`
     - `金彭`
     - `行星滚柱丝杠`

2. 识别动作类型
   - `new`
   - `continue`
   - `branch`
   - `status`
   - `clarify`

3. 识别任务类型
   - planning
   - report
   - diagnosis
   - implementation

4. 在命中项目时自动带：
   - `projectRef`

5. 对结果做人类可读呈现

不应该变厚的地方：

- 不要把完整项目记忆塞进入口 prompt
- 不要把复杂业务判断全部前移到入口
- 不要让前台自己承担长期项目真相

结论：

> OpenClaw 应该从“太弱的壳”升级成“中等偏厚的前台编排层”。

### Layer B：OpenMind plugin 桥接层

定位：

- OpenClaw 与 ChatgptREST 之间的薄桥

应该保留的职责：

1. 参数打包
2. `projectRef` 解析
3. 项目上下文注入
4. 任务发起/续做/查状态
5. 结果展示与错误人话化

不应该继续承担的职责：

1. 项目主记忆
2. 长期业务逻辑
3. 项目层复杂判断

结论：

> plugin 应该薄到中等，不应该演化成新的业务大脑。

### Layer C：ChatgptREST 状态与任务中台

定位：

- 结构化状态真相层
- 任务合同层
- 路由与质量门层

应该保留的职责：

1. `task_id`
2. `session`
3. `continue / branch`
4. checkpoint / handoff
5. public truth surface
6. quality gate
7. execution lane routing

不应该继续承担的职责：

1. 充当唯一复杂项目长期脑子
2. 承担所有上游自然语言识别责任
3. 替代成熟长会话 agent 的深度推演

结论：

> ChatgptREST 应该厚在“状态与真相”，不应该厚在“所有项目推理都在这里完成”。

### Layer D：Codex / Claude Code 长会话执行层

定位：

- 复杂项目主脑
- 深度工作层

应该承担的职责：

1. 深度分析
2. 多轮修改
3. 风格统一
4. 复杂推演
5. 长期上下文保留
6. 大项目持续推进

不应该独自承担的职责：

1. 作为唯一系统真相来源
2. 让状态只存在 session history 里

结论：

> 长会话成熟 agent 应该成为复杂项目的主脑，但必须有外置真相层托底。

## 6. 哪些状态放哪里

这是整个方案里最关键的部分。

### 6.1 必须外置的状态

这些不能只放在 resume 会话里：

1. 项目定义
   - 项目名
   - alias
   - planning_base

2. 当前权威文档
   - authority docs list

3. 冻结事实
   - 哪些事实可以说
   - 哪些还不能冻结

4. 当前阶段
   - 当前工作阶段
   - 当前重点

5. 当前待执行修改
   - 本轮需要完成的修改和补漏项

6. 写作规则
   - 禁用表达
   - 统一口径

7. 任务结构化状态
   - `task_id`
   - status
   - checkpoint
   - handoff
   - artifact refs

这些状态应该放在：

- `_project_context.md`
- authority docs
- ChatgptREST checkpoint/handoff/task plane

### 6.2 适合放在长 session 里的状态

这些更适合由成熟 agent 在 resume 会话里承接：

1. 当前推理链
2. 最近几轮的改写上下文
3. 本轮深挖思路
4. 风格偏好和当前工作策略
5. 临时工作记忆

结论：

> 项目真相要外置，工作过程可以留在长 session。

## 7. 项目定义与项目关联应该放哪

这是当前最容易混的地方。

### 7.1 项目定义

项目定义不该主要放在：

- OpenClaw prompt
- plugin 逻辑
- resume session 自由记忆

项目定义应该放在显式文件和显式状态里。

当前最合适的载体是：

- `_project_context.md`

里面至少要有：

- `project`
- `alias`
- `planning_base`
- `authority_docs`
- `frozen_facts`
- `current_focus`
- `style_rules`

### 7.2 项目关联

项目关联应该主要由入口层做。

也就是：

- 用户说的是哪个项目
- 这轮是继续还是新开
- 是否需要自动带 `projectRef`

这是 `OpenClaw` 最应该加强的部分。

一句话：

> 项目定义外置，项目关联由入口识别。

## 8. 为什么不是“只靠 resume 会话”

只靠成熟 agent 的长 session + resume，确实能显著提升复杂项目的连续性。

但如果完全只靠它，会有 4 个风险：

1. 状态不可审计
2. 换人接手困难
3. session 污染后很难切开
4. 外部系统无法明确知道“当前项目做到哪了”

所以：

> 纯 resume 方案擅长做事，但不擅长做系统。

## 9. 为什么也不是“只靠 ChatgptREST task plane”

只靠 task plane，会得到：

- 结构清楚
- 状态清楚
- 任务线清楚

但在复杂项目上仍有天然短板：

1. 深度理解不如长 session 自然
2. 多轮复杂改写体验不如成熟 agent
3. 上下文容易被入口层损失

所以：

> 纯 task plane 方案擅长管理，不擅长成为最好的复杂项目主脑。

## 10. 推荐的最终形态

### 10.1 不是替代，而是分层组合

推荐的最终形态不是：

- 废掉 OpenMind plugins
- 废掉 ChatgptREST
- 一切都靠 Codex/Claude

而是：

1. `OpenClaw`
   - 做前台项目关联和交互编排

2. `OpenMind plugins`
   - 做薄桥接层

3. `ChatgptREST`
   - 做结构化状态真相层

4. `Codex / Claude Code`
   - 做复杂项目主脑

### 10.2 一句话定义

> 人通过 OpenClaw 说话，plugin 负责转单，ChatgptREST 负责保存任务真相，Codex/Claude 负责把复杂项目真正做下去。

## 11. 具体可实施方案

### Phase 1：保留当前桥接层，但停止让 plugin 继续变厚

做法：

1. 保留 `openmind-advisor`
2. 保留 `projectRef`
3. 保留 `_project_context.md`
4. 不再往 plugin 里塞更多项目级业务逻辑

目标：

- plugin 做稳定桥
- 不做项目主脑

### Phase 2：增强 OpenClaw 的入口能力

做法：

1. 增加项目识别能力
2. 增加 continue / branch / status 识别能力
3. 增加 `projectRef` 自动携带
4. 增加必要的澄清问题策略

目标：

- 前台入口不再太弱
- 复杂项目能稳定进入后端

### Phase 3：冻结项目型 agent 的外置真相层

做法：

1. 每个复杂项目有一个 `_project_context.md`
2. 结合 ChatgptREST task/checkpoint/handoff
3. authority docs 明确冻结

目标：

- 复杂项目不再只靠对话历史维持

### Phase 4：把 Codex / Claude Code 明确升级成项目主脑

做法：

1. 为复杂项目配置固定 workspace
2. 使用长 session + resume
3. 明确它们负责：
   - 深度分析
   - 长链修改
   - 最终复杂材料生产

目标：

- 让真正的复杂工作回到最适合的层

### Phase 5：把 ChatgptREST 收口成“真相层 + 调度层”

做法：

1. 保持 task plane
2. 保持 execution lane routing
3. 保持 checkpoint/handoff
4. 不再试图让它承担全部复杂项目脑子

目标：

- 后端系统稳定、清楚、可审计

## 12. 这套方案里谁厚谁薄

最终建议如下：

| 层 | 厚度 | 主要职责 |
|---|---|---|
| `OpenClaw` | 中等偏厚 | 项目关联、任务编排、用户交互 |
| `OpenMind plugins` | 薄到中等 | 转单、上下文注入、状态查询、展示 |
| `ChatgptREST` | 中等偏厚 | task truth、checkpoint、routing、quality gate |
| `Codex / Claude Code` | 最厚 | 复杂项目主脑、深度执行、长会话推进 |

一句话：

> 入口要比现在更厚，但 plugin 要比想象中更薄；真正最厚的应该是成熟 coding agent。

## 13. 这套方案为什么比“每层都做脑子”更好

因为它能同时满足 4 个目标：

1. 复杂项目能做深
2. 状态可审计
3. 入口对用户仍然自然
4. 系统边界可维护

## 14. Claude 应重点审什么

建议 Claude Code 重点审这 6 个问题：

1. 这份分层判断是否准确抓到了当前系统混乱的根因？
2. `OpenMind plugins` 降级成桥接层，而不是主脑，这个判断是否正确？
3. `OpenClaw` 应加强到“项目关联与编排层”，但不升级成完整项目主脑，这个厚薄判断是否合理？
4. `ChatgptREST` 保持“状态真相层 + 调度层”而不是“唯一项目脑子”，这个定位是否是正确收口？
5. `Codex / Claude Code` 作为复杂项目主脑，是否应该与 `task/checkpoint/project_context` 组合，而不是单独依赖 resume？
6. 这套实施顺序是否足够稳健，还是应该调整前后顺序？

## 15. 最终结论

最终我给出的判断是：

> 你设计的 OpenMind plugins 不该被删除，但应该被降级成薄桥接层；OpenClaw 入口应该比现在更强，强在项目关联与任务编排；ChatgptREST 应继续保留为结构化状态真相层；真正的复杂项目主脑，应该迁到成熟的 Codex / Claude Code 长会话 agent。

这不是替代关系，而是重新分工。

真正合理的最终形态是：

> OpenClaw 负责把人接住，plugin 负责把任务送进去，ChatgptREST 负责把状态存清楚，Codex/Claude 负责把复杂项目真正做成。
