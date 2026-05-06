# 2026-04-04 W1 Gemini inline redteam fix walkthrough v1

## 1. 红队结论

对 `ea6317a6` 的 red-team 审核明确拒绝，理由不是泛泛而谈，而是给了可复现的失败场景：

1. 20KB 文本文件
2. 只会取前 ~12KB
3. 仍被记成 `single_text_inlined=true`
4. 同时跳过 Drive upload

这说明当前实现会静默丢材料。

## 2. 修复策略

这次没有去改通用 text snippet reader，因为它还服务于 bundle/overflow 路径。

只在 inline lane 做硬门槛：

1. 先检查真实 `st_size`
2. 大于 inline 上限就 fail closed 到 upload path
3. 不允许“截断后仍算 inline 成功”

## 3. 为什么这样改

这样改有两个好处：

1. 只修红队指出的 bug，不把 bundle 语义一并打乱
2. 对 live planning phase-1 更符合预期：小文件快走 inline，大文件继续走 Drive attach

## 4. 验证

除了红队反例测试，我还一起重跑了前面两批相关回归，确认：

1. 小文本 inline 还成立
2. 大文本回退到 Drive upload
3. send retry / lease semantics 没被打坏

## 5. 下一步

这批提交后，继续回到 `W1` 主线：

1. 重跑 OpenClawBot live completion gate
2. 看最新 live blocker 是否继续收窄
