# OpenClaw Gateway SkillBundles Compatibility Fix Walkthrough v1

日期：2026-04-07

## 背景

在把 OpenClaw 前台模型切到 `MiniMax-M2.7-highspeed` 后，按既有流程重建 `openclaw.json` 并重启 `openclaw-gateway.service`，gateway 没有稳定起来。

实际报错不是 MiniMax 模型本身，而是：

- `agents.list[*].skillBundles` 被当前 `openclaw-gateway v2026.3.7` 视为非法键

## 根因

`scripts/rebuild_openclaw_openmind_stack.py` 仍会把 `skillBundles` 写进 runtime `openclaw.json`。  
当前 gateway 版本已经不接受这个字段，但仍接受最终 materialized 的 `skills` 列表。

也就是说：

- `skillBundles` 只对生成时的技能展开有用
- 对 runtime 配置本身已经是多余且有害的字段

## 修复

1. 保留 `spec.skill_bundles` 在脚本内部用于展开 runtime local skills
2. 停止把 `skillBundles` 写入 `agents.list[*]`
3. 保持最终 `skills` 字段不变
4. 同步更新 `tests/test_rebuild_openclaw_openmind_stack.py`

## 预期结果

- `openclaw.json` 仍能 materialize 到正确的 `skills`
- `openclaw-gateway.service` 可以重新接受生成后的配置
- MiniMax 前台模型切换不再被这个 schema 兼容性问题阻断
