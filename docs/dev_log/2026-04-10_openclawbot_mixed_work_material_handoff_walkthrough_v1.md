# OpenClawBot Mixed Work-Material Handoff Walkthrough v1

日期：2026-04-10

## 背景

在 `workspace-material ops lane` 上线后，真实 Feishu mixed ask 暴露了新的偏航：

- ask 同时包含工作规划与本地文件路径
- `feishu-intake` 把 first turn 几乎全花在 `openmind_work_material_ops`
- 没有优先进入 `openmind_advisor_ask`

## 本次动作

1. 复盘现场 transcript，确认问题是 mixed ask handoff policy 偏航
2. 在 `openmind-advisor` plugin 中保留并复用显式本地路径 preflight 投影
3. 在 `scripts/rebuild_openclaw_openmind_stack.py` 中收紧 `feishu-intake`：
   - mixed ask 先走 advisor
   - 纯本地材料操作才先走 material ops
   - first turn 禁止先扫父目录和猜归档位置
4. 更新 rebuild tests 与 plugin source tests
5. focused pytest 回归通过
6. rebuild OpenClaw cognitive stack
7. restart `openclaw-gateway.service`

## 结果

- `feishu-intake` 的 route policy 已从“文件优先”改成“混合型工作 ask advisor 优先”
- advisor lane 会自动携带显式路径和 local-material preflight
- 后续 fresh Feishu mixed ask 不应再退化成目录探测主路径

## 备注

- 这次不是新造第二套协议
- 只是把已经存在的 `openmind_advisor_ask` 映射层，通过更严格的 `feishu-intake` handoff policy 接通到正确 first action
