# OpenClawBot Feishu Systemic Root-Cause Fix Readiness Review v1

日期：2026-04-11

## 结论

这轮修复不是 prompt 级补丁，而是把 4 个根因一起收口：

1. Feishu DM session scope 错误
2. 个人绩效/周报 ask 被误关联到项目
3. inbound rich context 没稳定进入 advisor/task_intake
4. mixed ask 首轮允许 move/rename

当前 readiness 结论：

- `code/tests = pass`
- `live config = applied`
- `gateway restart = applied`
- `session store = cleaned`
- `next-step live proof = pending next real Feishu turn`

## 代码变更面

- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
- [rebuild_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/scripts/rebuild_openclaw_openmind_stack.py)
- [test_openclaw_entry_policy_contract.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_entry_policy_contract.py)
- [test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py)
- [test_rebuild_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/tests/test_rebuild_openclaw_openmind_stack.py)

## 现场证据

### 1. focused tests

命令：

```bash
./.venv/bin/pytest -q \
  tests/test_openclaw_entry_policy_contract.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_openclaw_cognitive_plugins.py
```

结果：`42 passed`

### 2. live config 已切换

当前 live 配置确认：

- `session.dmScope = per-account-channel-peer`
- `feishu/default -> feishu-intake`

### 3. 旧 session 污染已归档清空

已将旧 `agent:feishu-intake:main` transcript/store 归档到：

- `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/feishu-intake/sessions/archive_20260411T031446Z`

当前：

- [sessions.json](/home/yuanhaizhou/.home-codex-official/.openclaw/agents/feishu-intake/sessions/sessions.json) = `{}`

## 这轮修复解决了什么

### 已解决

- live Feishu DM 不再强制共用 `agent:feishu-intake:main`
- 个人绩效/周报 ask 不再默认吃 `shortmobility` 项目规则
- inbound `BodyForAgent` 中的显式本地路径可以穿透到 advisor/task_intake
- mixed ask 首轮不会再擅自 move/rename

### 还没在现场证明的

- 下一条真实飞书 mixed ask 的 first action / final answer 还需要现场复验

这不是代码缺口，而是缺一条新的 live evidence turn。

## 风险评估

- `openmind-advisor` 改动面属于高风险执行路径，但 focused tests 已覆盖 entry-policy、plugin source、workspace rebuild 三个最相关面
- 当前最大残余风险不是代码错误，而是下一条真实 Feishu turn 仍可能暴露新的 message-shape 变体

## 建议

下一步不要再靠本地推断，直接用一条新的真实飞书 mixed ask 复验：

- 绩效总结 + 明确本地材料路径
- 明确要求“先按模块梳理，不要先移动文件”

验收重点：

1. session key 不应再是 `agent:feishu-intake:main`
2. `openmind_advisor_ask` 应先形成工作框架
3. 不应出现 `shortmobility` / `两轮车车身业务` 项目污染
4. 首轮不应执行 move/rename

