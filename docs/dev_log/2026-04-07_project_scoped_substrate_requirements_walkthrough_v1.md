# 2026-04-07 Project-Scoped Substrate Requirements Walkthrough v1

日期：2026-04-07

## 为什么写这份文档

用户要求的不是继续讨论方向，而是：

1. 重新定义清晰目标
2. 重新定义验收条件
3. 基于真实代码和真实运行数据，写成一份可以给 Claude Code 审的需求定义文档

本次补的不是实现方案稿，而是要求级文档。

## 这次文档的核心变化

相较于前一版 adoption plan，这一版明确补了：

1. `Atom.scope_project` 的 dataclass / DB 对齐问题
2. `ContextResolveRequest` 必须补 `project_id`
3. authority 优先级合同必须同时覆盖：
   - `ContextAssembler`
   - `prompt_builder`
4. `KB evidence` 在优先级合同中的位置
5. `Phase 1` 与 `Phase 2` 必须同一 sprint 并行
6. `Phase 4` 不允许引入 project-specific schema

## 输出

正式需求定义文档：

- `docs/reviews/2026-04-07_project_scoped_substrate_requirements_for_claude_v1.md`

## 预期用途

让 Claude Code 审核：

1. 目标定义是否清晰
2. 字段级合同是否完整
3. 阶段排序是否合理
4. 验收矩阵是否足够具体
5. 是否已经能作为后续设计与实施的需求基线
