# 2026-03-21 Front Door Object Contract Walkthrough v2

## 为什么要修到 v2

这轮不是推翻 `v1`，而是把它从“方向对的 baseline”收紧成“实现前可冻结的 precision 版本”。

我独立核过后确认，review 提的 3 个点都是真的：

1. versioned canonical schema 却没有强制 `spec_version`
2. `task_spec.py` 被写得太像当前 live truth
3. source taxonomy 只有 enum，没有 legacy mapping

但它们都没有推翻主判断。

## 我的独立判断

### 1. `spec_version` 必须 required

这点我接受，而且是中优先级真问题。

因为后面一旦开始写 shared intake normalizer，没有版本号的 canonical object 会让：

- schema 迁移
- adapter 审计
- 兼容路径

全部变虚。

### 2. `task_spec.py` 需要降口径，不需要降地位

我不接受“既然还没实现，就别把它当目标模块”这种推论。

更准确的处理是：

- 保留它作为未来 canonical schema module 的目标地位
- 但明确说明它当前还不是 live-equivalent truth

### 3. source taxonomy 必须写死 legacy 映射

这点也是实质问题。

如果不写：

- `codex`
- `api`
- `direct`

这些旧值如何归一，adapter 层迟早会再次分叉。

## 这轮新增了什么

- [front_door_object_contract_v2](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_front_door_object_contract_v2.md)
- [task_intake_spec_v2.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_task_intake_spec_v2.json)
- [entry_adapter_matrix_v2](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_entry_adapter_matrix_v2.md)

## 下一步

这组 `v2` 出来后，前门对象这块就够稳了。下一步不该继续空谈 schema，而该进入：

1. shared intake normalizer 代码实现
2. `routes_agent_v3.py` 消费 `task_intake`
3. `/v2/advisor/ask` 复用同一 normalizer
