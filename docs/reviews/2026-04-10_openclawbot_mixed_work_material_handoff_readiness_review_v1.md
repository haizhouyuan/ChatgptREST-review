# OpenClawBot Mixed Work-Material Handoff Readiness Review v1

日期：2026-04-10

## 现场问题

真实 Feishu ask：

- 要做 Q1 绩效总结
- 需要先按模块梳理工作总结
- 同时给了 4 个本地 `xlsx` 路径

现场 transcript 显示：

- `feishu-intake` 反复调用 `openmind_work_material_ops`
- 没有先用 `openmind_advisor_ask` 定工作框架
- 目录探测和材料 inspection 吞掉了 first turn

结论：问题不在 transport，也不在 advisor pipeline，而在 mixed ask 的 handoff policy 仍偏向本地材料操作。

## 本轮修复

1. 收紧 `feishu-intake` 规则
   - mixed ask 默认先走 `openmind_advisor_ask`
   - 明确高层工作推理关键词优先级
   - 禁止在 first turn 先扫父目录/先猜归档位置

2. 保留并复用已有 advisor 映射能力
   - 显式本地路径自动进入：
     - `explicit_local_paths`
     - `local_material_preflight`
     - `local_material_preflight_summary`
     - `attachments`

3. 回归覆盖
   - `tests/test_rebuild_openclaw_openmind_stack.py`
   - `tests/test_openclaw_cognitive_plugins.py`
   - `tests/test_openclawbot_meeting_intake_smoke.py`

## 验证结论

- focused tests：通过
- rebuild：完成
- gateway：`active`

## 仍需说明的边界

- 当前 live Feishu session 仍表现为复用既有 `feishu-intake` session store
- 旧 session 残留会放大之前的局部策略惯性
- 本轮已把规则修正到正确方向，但要获得最干净的真实验证，需要从 fresh session 重新发一条 mixed ask

## Ready 判定

判定：`ready_for_fresh_feishu_retry`

含义：

- 代码、规则、回归、runtime 都已切好
- 下一条 fresh Feishu mixed ask 可以作为正式验证样本
