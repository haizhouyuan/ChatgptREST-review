# 2026-04-02 OpenClawBot Meeting Intake Smoke Test Spec Walkthrough v2

## 为什么出 v2

`v1` 的主要问题不是方向错，而是把两个不同层次混在了一起：

1. bridge 本体是不是能组对 payload
2. OpenClaw 主链是不是会把正确上下文送到 bridge

这轮红队和本地核验都说明，这两件事不能再合并表述。

## 这次具体改了什么

### 1. 把旧的 Smoke B 拆成 B1 + B2

现在明确区分：

1. `B1`: 受控直调 bridge
2. `B2`: 真实 OpenClaw main path

这样旧的 dynamic replay gate 就只能覆盖 `B1`，不能再被误读为整条链已通。

### 2. 把 runtime identity 从“未知”改成“主链代码级风险”

原因很直接：

1. `pi-tool-definition-adapter` 当前会丢掉 `_ctx`
2. 然后用 `tool.execute(toolCallId, params, signal, onUpdate)` 调工具
3. `openmind-advisor` 现在却把第三个参数当 runtime ctx

所以这件事不再只是“等 smoke 看看”，而是代码上已经值得 fail-closed 地对待。

### 3. 明确 `MediaPaths` 没有自动投影层

现在已经写清楚：

1. Feishu transport 产生的是 `MediaPaths`
2. bridge 读的是 `context.files / context.attachments`
3. canonical plugin tool context 里没有这两个字段
4. 主链里也没看到任何自动映射

## 结果

`Step 0` 现在更像一个三层 gate：

1. transport
2. bridge contract
3. canonical main path

这能避免后续把“桥本体能过”误判成“OpenClawBot 真能把会议材料送进 planning agent”。
