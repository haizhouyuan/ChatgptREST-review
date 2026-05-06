# OpenClawBot Feishu Systemic Root-Cause Contract v1

日期：2026-04-11  
范围：`feishu/default -> feishu-intake -> openmind_advisor_ask / openmind_work_material_ops`

## 目标

冻结 `OpenClawBot` 在飞书工作入口上的 4 条系统性约束，避免继续靠 prompt 修补 mixed ask、项目串线、会话污染、首轮误操作。

## 已确认根因

1. 会话隔离不正确
   旧 live 配置把飞书 DM 会话收敛成 `agent:feishu-intake:main`，导致不同轮次和不同任务共用同一 entry。

2. 项目关联过度激进
   `openmind-advisor` 的项目规则把个人绩效/周报类 ask 误判成 `shortmobility` 项目请求，并且对新 ask 过度使用 cached association。

3. inbound rich context 没被稳定投影到 advisor lane
   runtime 真实 `BodyForAgent / RawBody / CommandBody / MediaPaths` 已经到达 OpenClaw，但 plugin 更信 tool 参数里的 `question`，导致显式本地路径和用户原始意图容易在 handoff 里丢失。

4. mixed ask 首轮允许执行 move
   对“先梳理/总结，再看材料并归档”的混合请求，material lane 可能在尚未形成工作框架前就尝试移动文件。

## 新 contract

### 1. Feishu DM session scope

- live `session.dmScope` 必须是 `per-account-channel-peer`
- `feishu/default` 仍路由到 `feishu-intake`
- 不允许再把飞书 DM 会话回收到 `agent:feishu-intake:main`

### 2. 非项目型工作 ask 的项目关联抑制

当 ask 命中以下信号时，project association 必须 fail-closed 到 `none`，并给出 `association_reason=non_project_work_intent`：

- `绩效`
- `考核`
- `考核表`
- `季度总结`
- `工作总结`
- `周报`
- `个人绩效`

同时：

- 对 `new` task mode 不允许默认吃 cached project association
- 只有 `continue / branch / status` 才允许使用 cached association

### 3. inbound rich context 必须进入 advisor/task_intake 构建

`deriveRuntimeContext()` 必须把以下 inbound 字段投影到 `mergedContext`：

- `BodyForAgent`
- `CommandBody`
- `RawBody`
- `Body`
- `ReplyToBody`
- `MediaPath / MediaPaths`
- `MessageSid`
- `SessionKey`
- `SenderName`
- `ThreadId / MessageThreadId`

`openmind_advisor_ask` 在构建 `routingQuestion / explicit_local_paths / local_material_preflight` 时，必须优先考虑这些 inbound 文本源，而不是只信 tool 参数里的 `question`。

### 4. mixed ask 首轮禁止 move/rename

当 ask 同时命中高层工作 framing 信号时：

- `梳理`
- `总结`
- `模块`
- `框架`
- `方案`
- `复盘`
- `汇报`
- `报告`
- `怎么做`
- `绩效`
- `周报`

`openmind_work_material_ops(action=move)` 必须 fail-closed：

- `error = move_deferred_requires_planning_frame`
- `guard_reason = higher_order_work_ask_detected`

这类请求首轮允许做：

- inspect exact files
- workbook sheet listing
- narrow path inspection

这类请求首轮禁止做：

- move
- rename
- invent archive destination
- scan broad parent directories before advisor framing

## 对 `feishu-intake` 的操作约束

`feishu-intake` 的 AGENTS / TOOLS / ROLE_PACKS 必须共同表达以下规则：

1. mixed ask 先 `openmind_advisor_ask`
2. 纯 local ops 才先 `openmind_work_material_ops`
3. mixed ask 首轮不得 move/rename
4. `exec` 不是这个 lane 的恢复手段

## 最小验收

1. focused tests 通过：
   - `tests/test_openclaw_entry_policy_contract.py`
   - `tests/test_rebuild_openclaw_openmind_stack.py`
   - `tests/test_openclaw_cognitive_plugins.py`

2. live config 生效：
   - `openclaw.json.session.dmScope == per-account-channel-peer`

3. `feishu-intake` session store 已清空旧污染：
   - `agents/feishu-intake/sessions/sessions.json == {}`

4. 下一条真实 mixed ask 不应再默认继承 `shortmobility`

