---
title: Q1绩效考核表 v3 Windows 兼容修复 walkthrough
version: v1
status: completed
updated: 2026-04-12
---

# 触发原因

用户在 Windows 机器打开 `2026-04-12_Q1绩效考核表草稿_v2.xlsx` 时收到 Excel 恢复日志，提示：

- `sheet1.xml` 有 XML 错误
- `calcChain.xml` 被删除

这说明之前的结论“`v2` 可以交付”不成立，需要继续闭环，直到 Windows Excel 也能正常打开。

# 本次处理原则

不把问题归因于“用户本地环境”，而是按 renderer 产物缺陷处理。

执行顺序：

1. 直接检查 `v2.xlsx` 内部 OOXML
2. 定位 renderer 根因
3. 修代码与测试
4. 不覆盖 `v2`，重新生成 `v3`
5. 对 `v3` 做 OOXML、公式、可读性三重验收

# 定位过程

## 先排除无效方向

先检查：

- `sheet1.xml` 是否包含控制字符
- 是否有 `NULL` 字节
- 是否有 BOM

结果：

- 无控制字符
- 无 `NULL`
- 无 BOM

说明问题不是“文本脏字符”。

## 再看 `sheet1.xml` 根节点

检查发现：

- `sheet1.xml` 写成了 `mc:Ignorable="x14ac xr xr2 xr3"`
- 但未声明这些 prefix 的 `xmlns:*`

这类文件 `xmllint` 也可能过，因为它不理解 OOXML 的 prefix-ignorable 语义；但 Windows Excel 会按 OOXML 规则报修复。

## 顺手检查 `calcChain`

发现：

- `xl/calcChain.xml` 仍存在
- workbook relationship 仍指向它
- content types 仍声明它

这会让 Excel 在恢复时删除它。

# 修复动作

## 修复 1：补齐 Ignorable 前缀声明

在 `ops/materialize_performance_sheet_from_answer.py`：

- 注册了 `mc / x14ac / xr / xr2 / xr3` namespace
- 新增 `_repair_ignorable_prefix_declarations()`
- 在 `sheet_tree.write(...)` 之后对根标签做 post-write 修正

为什么要 post-write：

- `ElementTree` 只会声明“序列化时实际用到”的前缀
- `Ignorable` 里的 prefix 文本不是结构性节点
- 所以 `xr2/xr3` 这类只出现在 `Ignorable` 中的前缀，不会自动声明

## 修复 2：删除陈旧 calcChain

同一脚本中新增 `_drop_calc_chain()`：

- 删除 `xl/calcChain.xml`
- 删除 `[Content_Types].xml` 里的 calcChain override
- 删除 `workbook.xml.rels` 里的 calcChain relationship

## 修复 3：补测试

在 `tests/test_materialize_performance_sheet_from_answer.py` 中新增：

- `_repair_ignorable_prefix_declarations` 的 namespace 修复测试
- `_drop_calc_chain` 的 part/relationship 删除测试

# 代码提交

两次修复分别提交：

- `338eb786` `Fix performance sheet OOXML namespace compatibility`
- `c856503f` `Drop stale calcChain during performance sheet materialization`

# 重新生成产物

为避免覆盖旧证据版本，重新生成：

- `/vol1/1000/projects/planning/个人绩效/2026Q1/输出/2026-04-12_Q1绩效考核表草稿_v3.xlsx`

生成方式仍然基于同一条系统答案 artifact，而不是人工重写：

- template = `..._v1.xlsx`
- answer = `artifacts/monitor/openclawbot_feishu_proxy_turn/20260412T074951Z/materialize_performance_sheet.answer.md`

因此这次变化仅限 renderer 兼容性修复，不改变任务本身的业务判断。

# 最终验收

## OOXML 层

`sheet1.xml` 现在包含：

- `xmlns:x14ac`
- `xmlns:xr`
- `xmlns:xr2`
- `xmlns:xr3`

且：

- `calcChain.xml` 已彻底移除

## 公式层

`formula_check.py`：

- `total_errors = 0`

## 可读性层

关键新增区域仍保持：

- 自动换行
- 行高足够
- 第 8 行内容未被回滚或截断

# 结果判断

`v2` 应被视为已知问题版本，仅保留证据用途。

当前真正可交付的版本是：

- `2026-04-12_Q1绩效考核表草稿_v3.xlsx`
