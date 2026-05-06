# OpenClawBot Feishu Systemic Root-Cause Fix Walkthrough v1

日期：2026-04-11

## 为什么这次不再做“症状修复”

之前连续多轮都在修同一类现象：

- 先扫目录不先做工作 framing
- 误把个人绩效 ask 串成项目 ask
- 会话落在 `agent:feishu-intake:main`
- mixed ask 首轮试图 move 文件

这些现象如果继续逐条堵，只会形成更多 prompt patch。  
这次改成先追根因，再同时收 4 个约束。

## 我实际做了什么

### 1. 修 `openmind-advisor` 的项目关联根因

在 [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)：

- 从 `shortmobility` 规则里移除了会把个人 ask 误伤的个人姓名模式
- 新增 `NON_PROJECT_WORK_PATTERNS`
- 对非项目型工作 ask 返回：
  - `association_source = none`
  - `association_reason = non_project_work_intent`
- cached project association 只保留给 `continue / branch / status`

### 2. 修 rich context handoff 根因

同一文件里：

- 新增 inbound context copy keys
- 把 `BodyForAgent / RawBody / CommandBody / MediaPaths / MessageSid / SessionKey ...`
  全部投影进 `mergedContext`
- `openmind_advisor_ask` 的 `routingQuestion / explicitLocalPaths` 不再只信 tool 参数里的 `question`

### 3. 修 mixed ask 首轮误操作根因

同一文件里：

- 给 `openmind_work_material_ops(action=move)` 增加 higher-order work ask guard
- mixed ask 首轮直接 fail-closed，不允许 move/rename

### 4. 修 live session scope 根因

在 [rebuild_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/scripts/rebuild_openclaw_openmind_stack.py)：

- live config 写入 `session.dmScope = per-account-channel-peer`
- 同时把 `feishu-intake` 的 AGENTS/TOOLS/ROLE_PACKS 都写成统一规则：
  - mixed ask 先 advisor
  - pure local ops 才先 material ops
  - mixed ask 首轮禁止 move/rename

## 验证步骤

1. 跑 focused tests
2. 用 `PYTHONPATH=. python3 scripts/rebuild_openclaw_openmind_stack.py --topology ops` rebuild live config
3. `systemctl --user restart openclaw-gateway.service`
4. 归档旧 `feishu-intake` session store
5. 重写空的 `sessions.json`

## 现场结果

- rebuild 成功
- gateway restart 成功
- live `dmScope` 已切到 `per-account-channel-peer`
- `feishu-intake` 旧 session store 已归档
- 当前 session store 为空，下一条真实飞书消息会从干净 entry 开始

## 这次没有做什么

- 没有继续强化 prompt-level routing 作为主方案
- 没有继续把 mixed ask 的归档位置硬编码成某个项目目录
- 没有试图靠“再补一句系统提示”来掩盖项目串线和会话污染

## 下一步

需要一条新的真实飞书 mixed ask 来做现场复验。  
如果这条消息仍然偏航，就不再是旧的 session/project 污染问题，而会是新的 message-shape 或 execution-order 问题。

