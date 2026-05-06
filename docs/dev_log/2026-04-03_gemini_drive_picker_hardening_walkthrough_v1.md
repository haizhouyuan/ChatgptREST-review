# 2026-04-03 Gemini Drive Picker Hardening Walkthrough v1

## 做了什么

这轮不是扩 planning 面，而是回到当前 live blocker，补 `gemini_web.ask` 的 Drive 附件 UI 链。

实际动作：

1. 重查 live session/job，确认旧的 `fetch failed` 不再是当前主 blocker
2. 核到真实 job 失败已经落在：
   - `Gemini upload menu item not found`
   - `Timed out waiting for visible Google Drive picker iframe.`
3. 用 CDP 直接抓了 Gemini upload menu 的现场文本，确认当前 live menu 里确实有：
   - `上传文件`
   - `从云端硬盘添加`
   - `更多上传选项`
4. 代码上把 `click drive item + wait picker` 链条硬化成：
   - 更宽的 live label 匹配
   - `更多上传选项` fallback
   - picker 打开重试
   - 错误里带 visible menu labels
5. 新增窄单测，避免这批回退成“只靠现场猜”
6. 跑完 Gemini 相关回归与 planning live-gate 相关回归

## 为什么这样改

当前问题不是：

1. OpenClawBot 主链不通
2. ChatgptREST 不能建 session
3. Gemini capability 消失

当前问题更像：

1. 进入 Gemini 页面后，Drive 附件菜单链脆弱
2. 现场 UI 小漂移或点击/等待时序不稳，就会把附件阶段打断

所以这轮最合理的策略不是重构 executor，也不是继续扩 planning 功能，而是先把最前面的 live 脆弱点补成 fail-closed + retryable + diagnosable。

## 当前结果

当前结果是：

1. 代码已补
2. 相关回归已过
3. live root-cause 口径已更新
4. 但还没把新的 live completion gate 结果冻结成终态证据

所以下一步应继续做 live rerun，而不是停在“单测绿了”。
