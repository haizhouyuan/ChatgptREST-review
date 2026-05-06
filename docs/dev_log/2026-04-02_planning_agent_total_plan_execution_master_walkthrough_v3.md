# 2026-04-02 Planning Agent Total Plan Execution Master Walkthrough v3

## 为什么出 v3

`v2` 已经把 phase-1 scope 收窄到了 `会议沉淀`，这件事没有变。

这次出 `v3`，只因为 `Step 0` 的前置 gate 还不够严格。

旧问题是：

1. 我们默认把“bridge 本体能打出正确 payload”近似等同于“OpenClawBot 主链能把会议材料送到 planning agent”

这轮核验后确认，这个近似不成立。

## v3 的真正变化

### 1. 把 Step 0 改成三层 gate

现在要分开看：

1. transport
2. bridge 本体
3. canonical main path

### 2. 不再把旧 replay gate 的 PASS 当主链证明

原因很明确：

1. 那套 harness 直接手工喂了 `runtime_ctx`
2. 它证明的是 bridge 本体，不是 OpenClawBot 主链

### 3. phase-1 其余框架保持不变

`会议沉淀` 仍然是第一条切片。  
`task_runtime` 仍然不是 phase-1 前置。  
`publicagentmcp` 仍然按薄边界收。

## 结果

这样改完之后，总计划的第一步就不再含糊：

1. 先证明 `OpenClawBot` 真能接住材料
2. 再证明 bridge 本体真会组对 payload
3. 再证明主链真会把正确上下文送到 bridge
4. 然后才谈 `task_id / checkpoint / continue`
