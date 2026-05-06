# 2026-03-21 Shared Task Intake Normalizer Walkthrough v1

## 为什么先做这步

前门对象契约已经冻结到 `v2`，再往下如果还只写文档，就会继续漂。

所以这轮选择了最小实现面：

- 新建一个共享 `task_intake` 模块
- 先接两条 live ask 路径
- 不直接大改旧 carrier 模块

## 这轮怎么判断风险

`advisor_ask` 的 GitNexus impact 是 `LOW`。  
`make_v3_agent_router` 的 impact 是 `CRITICAL`，因为它是 app 装配点，牵动大量测试和入口。

所以这轮的策略是：

- 不改 controller 接口
- 不改 route 语义
- 只给 `agent_v3` 和 `advisor_ask_v2` 增加 shared intake normalization

## 这轮最关键的实现决策

### 1. 不直接重写 `task_spec.py`

因为它现在还是旧 `TaskSpec` 语义。

如果一边改 live ingress，一边强行把旧 carrier 重写，风险会直接扩大到：

- 旧测试
- 旧 dispatch 语义
- 旧文档假设

### 2. `Task Intake Spec v2` 先落在 `stable_context/request_metadata`

这保证：

- canonical intake 已经进入 live 主链
- 但 controller 外部接口和 route execution 仍然稳定

### 3. `AskContract` 不废弃，但开始真正从 canonical intake 派生

这是这轮最重要的结构变化。

之前它更多还是直接吃散落 request fields。  
现在至少在 `agent_v3` 路径上，已经开始从 canonical intake 派生 contract seed 了。

## 结果

这轮完成后，前门对象已经从：

- “文档上冻结”

推进到：

- “两条 live 路径共享同一个 canonical intake normalizer”

这就是下一轮做 `standard_entry` 收编、`task_spec.py` 收编、OpenClaw payload 升级的基础。
