# 2026-04-06 OpenMind Advisor Human Fallback Guard Walkthrough v1

## 做了什么

补了一处 `OpenClaw` 插件层的人类可读性漏口：

1. `openmind_advisor_ask` 在 `completed / needs_followup / failed` 之外，
   对 `cancelled / queued / pending / running / in_progress` 也会返回人类可读提示。
2. 未覆盖状态且没有答案时，不再把原始 `JSON.stringify(payload)` 直接展示给用户。
3. 增加回归测试，锁定新的用户可读 fallback 文案和“不得裸回 JSON”约束。

## 为什么做

在对 `planning` 主线的插件层评审里，剩余的代码层问题已经很少。
这次补的是一个低频但明显的出口风险：

- 如果 backend 返回意外状态或非终态状态，
  插件不应该把原始 JSON 暴露给终端用户。

## 结果

当前 `OpenClaw -> openmind_advisor_ask` 的结果展示已经进一步收敛为：

- 正常完成：先给答案
- 需要补充：给人话说明和下一步建议
- 失败：给人话失败提示
- 处理中/已取消/未知状态：仍然给人类可读提示，而不是机器 payload
