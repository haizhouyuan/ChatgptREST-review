# 2026-04-03 Codex 5.4 xHigh OpenClawBot Session/Job Alignment Redteam Walkthrough v1

## 做了什么

对 `OpenClawBot session/job alignment` 这批改动做了两轮 `codex 5.4 xhigh` 红队。

## 第一轮结果

第一轮没有直接签字，指出了三类问题：

1. Gemini canonical base-app query 变体没完全覆盖
2. 非误伤验证只到 helper 层
3. 文档把代码说得过窄

## 中间修复

随后做了三件事：

1. 路由侧改为复用仓内 `_gemini_is_base_app_url(...)`
2. 新增 route-level 正向测试
3. 文档改成和代码完全同口径

## 第二轮结果

第二轮 verdict 变成：

1. `approve`

也就是说，这批当前已经没有红队视角下的剩余阻塞项。

## 当前结论

这批现在可以安全进入：

1. doc obligations 检查
2. staged scope 检查
3. commit
4. closeout
