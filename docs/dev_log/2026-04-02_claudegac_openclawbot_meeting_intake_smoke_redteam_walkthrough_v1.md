# 2026-04-02 ClaudeGAC OpenClawBot Meeting Intake Smoke Redteam Walkthrough v1

## 做了什么

1. 用 `claudegac` 跑了一轮针对 `Step 0 smoke spec` 的原子级红队审核
2. 红队同时读了：
   - `openmind-advisor` bridge
   - OpenClaw `plugin tool context`
   - `pi-tool-definition-adapter`
   - `auto-reply -> runEmbeddedPiAgent` 主链
3. 我又补查了旧的 dynamic replay gate，确认它的 PASS 其实来自“手工注入 runtime_ctx”的受控重放
4. 最后把红队意见和本地代码核验并成一个正式审稿

## 为什么要做这版

`v1 smoke spec` 的方向是对的，但它对两个点说得还不够硬：

1. `MediaPaths -> context.files/attachments` 不是“尚未证实”，而是按当前主链代码更接近不存在
2. runtime identity 也不是“待 smoke 观察”，而是当前 embedded tool path 上存在明确错位风险

如果不先把这两个点收紧，后面的 `task_id / checkpoint / continue` 实施规格会建立在假连续性之上。

## 红队最关键的收获

1. `OpenClawPluginToolContext` 没有 `files / attachments`
2. `buildPluginToolContext()` 也没构造这些字段
3. `runEmbeddedPiAgent()` 主链只传身份、threading、workspace、images 等字段
4. `toToolDefinitions()` 会把 `_ctx` 丢掉，再用 `tool.execute(toolCallId, params, signal, onUpdate)` 调工具
5. 旧的 dynamic replay gate 不是主链证明，因为它直接给 plugin 喂了 `runtime_ctx`

## 结果

所以这轮没有改代码，而是做了 3 个收口动作：

1. 写红队审稿
2. 准备把 `Step 0` 升成 `v2`
3. 准备把总计划同步升成 `v3`

## 备注

这次 `claudegac` run 中途先产出了 `stdout.log` 子结论，随后才正常补齐 `result/claude_result.json`。最终正式结果又把问题收紧了一步：

1. 不只是 framework 没有把 `MediaPaths` 自动投影进 bridge
2. 还必须验证 real tool caller / agent model 会不会把文件路径写进 `params.context`
