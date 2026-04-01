# 2026-03-20 Post-Reconciliation Next Phase Plan Walkthrough v1

## 做了什么

- 基于 `system_state_reconciliation_master_audit v1/v2` 收了一版下一阶段正式计划
- 没有继续写泛架构蓝图，而是直接给出阶段顺序、每阶段目标、交付物和验收
- 把“先做 authority，再做 contract，再恢复 runtime 主链”作为硬顺序写死

## 这版计划最重要的取舍

1. 先不做新平台
2. 先不重启通用 multi-agent 大工程
3. 先不扶正 `cc-sessiond`
4. 先围绕 `planning / research` 两个主场景收敛
5. 先把 `OpenClaw` 当 runtime substrate，用起来，而不是重造同类层

## 为什么这样排

因为当前系统最危险的不是“功能缺”，而是：

- authority 冲突
- front door contract 分裂
- runtime host 停机
- knowledge 层不对称

如果不按这个顺序来，后面再做任何新层都会继续叠加混乱。

## 计划使用方式

这版文档适合作为下一轮具体执行的总纲。
后面每开一个阶段，都应该再单独落对应的 `v1` 子计划或实施文档，而不是在这一份里持续追加。
