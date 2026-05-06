# 2026-04-03 Planning Agent Total Plan Execution Master v15

## 1. v15 相比 v14 的关键变化

`v15` 的变化不是扩主线，而是继续做 strict red-team 驱动的基础收口。

新增事实：

1. 第二轮 `claudegac` 虽未出 terminal verdict，但已经提前暴露出 store 层 `_normalize_text_list()` 的脏输入问题。
2. 这个问题已被本地独立复现并修复。
3. 现在 route/store 两层的“文本列表归一化”都做了 fail-closed 收口。

## 2. 到 v15 为止的状态

### 2.1 已确认收口的问题

1. 空 identity list 泄漏
2. list limit 无界
3. route 层 checkpoint seed 脏输入 shape
4. store 层 `_normalize_text_list()` 脏输入 crash / 错读
5. `implementation_plan` 被 generic planning 默认 pack profile 吞掉的风险

### 2.2 仍待最终 red-team sign-off

1. `_should_continue()` 的“单一材料重叠即继续”是否过宽
2. acceptance pack 对真实 writeback failure mode 的证明是否仍偏弱
3. 第二轮 `claudegac` 最终 verdict

## 3. v15 的当前口径

现在可以更准确地说：

1. planning task plane 已不只是“能跑”，而是开始进入输入卫生、fail-closed 和真实边界治理阶段。
2. 当前最大的剩余不确定性，不再是前一轮那种明显泄漏/误判，而是更细的 continue 策略和 evidence 充分性。

## 4. v15 的 Next 3

### 4.1 Next 1

基于修完 store 归一化后的新提交，再跑一次 strict `claudegac`。

### 4.2 Next 2

如果第二轮真正收口后仍只剩中低优先问题，再把 acceptance 往 `OpenClawBot` 主链推进。

### 4.3 Next 3

开始准备把当前 planning task plane 的 repo-internal proof，升级成更贴近真实入口的主链验收。

## 5. 一句话结论

`v15` 的核心变化是：

> planning task plane 现在连 route/store 两层的同类脏输入漏洞都开始成组收口，主线仍在推进，但标准已经从“有功能”抬到了“边界也要稳”。
