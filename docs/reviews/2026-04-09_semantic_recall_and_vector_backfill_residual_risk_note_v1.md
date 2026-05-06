# Semantic Recall And Vector Backfill Residual Risk Note V1

这轮之后仍然保留 4 个边界。

## 1. `绿源` 已非零，但还不是 entity-grade

当前 harness 里 `绿源来访准备` 已经能返回 `4` 条结果。  
但 top hit 仍偏泛化的“资源与现场准备/过渡方案”，不是直接命中“绿源拜访纪要/绿源公司画像”。

结论：

- recall 已修通
- ranking 仍需继续做 entity-aware boosting

## 2. `钛虎` 仍然是 bridging 命中，不是实体档案命中

当前 `钛虎机器人关节模组合作` 已非零，但主要命中的是：

- 机器人零部件
- 关节模组
- 合作

这说明：

- 系统已经能把 query 关联到“机器人/模组合作”主题
- 但还没有“钛虎”这个实体的高质量 planning 语料面

## 3. vector backfill 这轮只覆盖 allowlist slice

当前 `4547` vectors 来自 planning allowlist buckets，不是全部 `active + candidate`。

这次是刻意的：

- 先保证高价值 slice 可观测、可恢复、可验收
- 再决定是否扩到剩余 candidate

## 4. USER_HOT_PATH 没改

这轮的提升只发生在：

- `PLANNING_EXPLICIT_PATH`
- EvoMap vector lane

默认 `USER_HOT_PATH` 没被放宽，也没有把 generic staged 混进去。  
这保证了 runtime safety，但也意味着这轮不是“全 surface 通吃”的终局优化。
