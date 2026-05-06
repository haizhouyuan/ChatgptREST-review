# 2026-04-03 Codex 5.4 xHigh Gemini Upload Menu Selector Redteam Walkthrough v1

## 做了什么

对 `Gemini upload menu selector resilience` 这批改动做了两轮 `codex 5.4 xhigh` 红队。

## 第一轮结果

第一轮没有直接签字，指出了三类问题：

1. 测试不够真
2. 选择器可能过宽
3. 文档对 live 进展说得偏满

## 中间修复

随后做了四件事：

1. 把 current exact label 提前
2. 改了 fake selector 匹配模型
3. 补了多候选负向测试
4. 把文档降口径

## 第二轮结果

第二轮 verdict 变成：

1. `approve`

## 当前结论

这批现在可以安全进入：

1. commit
2. closeout
3. 下一批 live gate 验证
