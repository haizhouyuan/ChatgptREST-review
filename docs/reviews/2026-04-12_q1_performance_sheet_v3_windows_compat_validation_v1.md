---
title: Q1绩效考核表 v3 Windows Excel 兼容性验证
version: v1
status: completed
updated: 2026-04-12
---

# 背景

用户在 Windows Excel 打开 `2026-04-12_Q1绩效考核表草稿_v2.xlsx` 时收到恢复日志：

- `sheet1.xml` 存在 XML 错误
- `calcChain.xml` 被删除

这说明 `v2` 虽然能被 `openpyxl`、`formula_check.py` 等 Python 工具读取，但 **并不满足 Windows Excel 的 OOXML 兼容性要求**，因此不能视为可交付版本。

# 根因判断

本次不是内容质量问题，而是 renderer 的 OOXML 序列化问题。

## 根因 1：`mc:Ignorable` 引用的前缀未声明

`v2.xlsx` 的 `xl/worksheets/sheet1.xml` 中存在：

- `mc:Ignorable="x14ac xr xr2 xr3"`

但根节点未声明：

- `xmlns:x14ac`
- `xmlns:xr`
- `xmlns:xr2`
- `xmlns:xr3`

这在 `xml.etree.ElementTree` 和 `xmllint` 层面不会报错，但对 Windows Excel 来说属于不合法的 OOXML 前缀引用，因此会触发工作表修复。

## 根因 2：保留了陈旧的 `calcChain.xml`

materialization 后仍保留：

- `xl/calcChain.xml`
- `[Content_Types].xml` 对应 override
- `xl/_rels/workbook.xml.rels` 对应 relationship

这会让 Excel 在恢复时删除计算链，虽然通常不致命，但会额外增加“文件被修复”的提示概率。

# 修复

文件：

- `ops/materialize_performance_sheet_from_answer.py`
- `tests/test_materialize_performance_sheet_from_answer.py`

## 修复 1：补齐 Ignorable 前缀声明

新增：

- `NS_MC / NS_X14AC / NS_XR / NS_XR2 / NS_XR3`
- `ET.register_namespace(...)`
- `_repair_ignorable_prefix_declarations(xml_path)`

效果：

- 对生成后的 `sheet1.xml` 根节点进行 post-write 修复
- 如果 `Ignorable` 中出现 `x14ac / xr / xr2 / xr3`，但根节点缺失对应 `xmlns:*` 声明，则自动补齐

## 修复 2：移除陈旧 calcChain

新增：

- `_drop_calc_chain(work_dir)`

效果：

- 删除 `xl/calcChain.xml`
- 删除 `[Content_Types].xml` 中的 `/xl/calcChain.xml` override
- 删除 `xl/_rels/workbook.xml.rels` 中指向 `calcChain.xml` 的 relationship

# 测试

本次新增并通过的测试：

- `test_repair_ignorable_prefix_declarations_adds_missing_namespaces`
- `test_drop_calc_chain_removes_part_and_relationships`

同时保留原有 materialize 基础测试。

# 新版本产物

本次不覆盖 `v2`，重新从同一条系统答案 artifact materialize 出：

- `/vol1/1000/projects/planning/个人绩效/2026Q1/输出/2026-04-12_Q1绩效考核表草稿_v3.xlsx`

该文件仍然使用：

- 模板：`v1.xlsx`
- 系统答案：`artifacts/monitor/openclawbot_feishu_proxy_turn/20260412T074951Z/materialize_performance_sheet.answer.md`

也就是说，本次修复的是 renderer，不是改写任务内容。

# v3 验收结果

## 1. OOXML 命名空间完整

`sheet1.xml` 根节点现在显式包含：

- `xmlns:x14ac`
- `xmlns:xr`
- `xmlns:xr2`
- `xmlns:xr3`

并保留：

- `mc:Ignorable="x14ac xr xr2 xr3"`

## 2. calcChain 已移除

检查结果：

- `xl/calcChain.xml` 不存在
- workbook rels 中不再引用 `calcChain.xml`
- `[Content_Types].xml` 中不再声明 `/xl/calcChain.xml`

## 3. 公式继续正确

`formula_check.py` 结果：

- `status = success`
- `total_formulas = 8`
- `total_errors = 0`

## 4. 可读性未退化

关键单元格 `B8 / C8 / E8 / F8` 保持：

- 自动换行 `wrap_text = True`
- 第 8 行行高 `202.5`
- 评分与备注区依旧留空

# 结论

当前正确交付版本应当是：

- `2026-04-12_Q1绩效考核表草稿_v3.xlsx`

而不是 `v2`。

`v3` 通过了：

- 内容边界检查
- 公式完整性检查
- 可读性检查
- Windows Excel 兼容性修复检查

当前建议：

- 将 `v2` 视为问题版本保留证据，不再作为交付件
- 后续若继续推进自评版/定稿版，应以 `v3` 为新基线
