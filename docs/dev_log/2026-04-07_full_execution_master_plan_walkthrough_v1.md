# 2026-04-07 Full Execution Master Plan Walkthrough v1

本记录用于说明为什么新增 `full_execution_master_plan_v1`。

## 1. 背景

用户要求本轮不仅修 `public agent MCP`，还要把此前讨论过的 `A-F` 主线全部纳入一个可执行、可审计、可持续的计划里，并要求：

1. 用计划文档固定实施路径
2. 用开发记录固定阶段结论
3. 用每步提交避免上下文压缩后丢失关键决策

## 2. 为什么现在需要 master plan

当前上下文里已经存在多份相关文档：

1. layered architecture
2. substrate adoption plan
3. substrate requirements
4. full implementation plan

但这些文档分别面向：

1. 架构边界
2. substrate 设计
3. requirements
4. Claude 评审给 Codex 的初稿

还缺一份**真正绑定当前执行顺序与审核闭环的 master execution 文档**。

## 3. 这次补了什么

新增文档明确冻结了：

1. 当前 `A-F` 的执行批次
2. `Claude resume` 官方能力结论
3. 本机 smoke test 真实结论
4. 为什么不能依赖现有旧 `claudegac` session
5. 为什么要创建新受控审核会话
6. 每批的验收目标和证据纪律

## 4. 作用

后续每个 PR 都以这份文档为锚，不再依赖聊天上下文来记住：

1. 当前做到哪一批
2. 审核怎么跑
3. 哪些主线先做、哪些后做
4. 哪些事情明确不混进当前 PR
