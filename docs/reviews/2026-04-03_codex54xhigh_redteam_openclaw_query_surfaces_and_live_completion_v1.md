# 2026-04-03 Codex 5.4-xhigh Redteam OpenClaw Query Surfaces And Live Completion v1

## 1. redteam 结论

这轮我用 `codex 5.4-xhigh` 代替 `claudegac` 做了两轮红队。

最终 verdict：

`approve-with-fixes`

## 2. 第一轮红队我采纳了什么

第一轮红队指出并被我采纳的硬问题：

1. `openmind_advisor_session_get` 需要 fail-closed 的 runtime session 限制
2. `task_list/session_get/task_get` 不该继续把过宽 raw payload 暴露给 plugin
3. live completion runner 不能再 `ok=true`
4. probe/polling 失败需要结构化 fail-closed
5. `cancelled` 映射需要补齐
6. planning task GET/list 的 refresh 需要至少做到：
   - no-op 不写盘
   - refresh 异常不把读接口拖死

这些都已经进代码并过测试。

## 3. 第二轮红队我接受到什么程度

第二轮红队还保留了 3 条意见：

### 3.1 我接受为已知中风险

`GET/list` 仍然是 stateful read。

我的判断：

- 这在 phase-1 continuity sidecar 里仍是设计债
- 但已经不再是 blocking bug

### 3.2 我接受为后续 boundary 项

`/v3/agent/session/{session_id}` 后端 REST 仍然比 plugin 侧更宽。

我的判断：

- 这条成立
- 但它会触碰更多现有 client/status surface
- 这批先不硬改，转入下一批 boundary 收口

### 3.3 我部分接受

planning task REST payload 仍带 `identity_key`。

我的判断：

- 这是 server payload 过宽，不是 plugin 侧继续泄漏
- 可以作为下一批 surface 清理项
- 当前不阻断这批提交

## 4. 一句话综合判断

这轮 `codex 5.4-xhigh` 红队没有推翻主线，但把这批代码从：

- `有明显 blocker`

推进成了：

- `可提交，但带着明确的 medium follow-ups`
