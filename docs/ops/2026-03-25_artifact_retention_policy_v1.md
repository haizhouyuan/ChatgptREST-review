# ChatgptREST Artifact Retention Policy v1

> 日期: 2026-03-25
> 状态: maintainer-facing policy, no cleanup execution
> 目的: 把“哪些能讨论 retention、哪些根本不是清理对象”先说清楚

## 1. 当前执行期硬规则

Phase 1-4 期间：

- 禁止删除任何 artifact tree
- 禁止删除 `.run/*`
- 禁止删除 `artifacts/jobs/*`
- 禁止删除 `artifacts/monitor/*`
- 禁止改写 `state/*`

当前任务只允许：

- 写 policy
- 做分类
- 做 backlog

真正清理动作必须另起任务并单独批准。

## 2. 当前容量判断

只读盘点显示：

- `artifacts/`: `160G`
- `artifacts/monitor/`: `128G`
- `artifacts/monitor/maint_daemon`: `120G`
- `artifacts/jobs/`: `7.7G`
- `docs/dev_log/artifacts/`: `2.5M`

结论：

- 当前主要治理对象是 `artifacts/monitor/`
- `docs/dev_log/artifacts/` 不是当前主要容量压力点

## 3. 先分清 5 类对象

### 3.1 Live runtime state

典型路径：

- `.run/*`

性质：

- live runtime state
- 可能包含 pid、锁文件、浏览器 profile 指针、当前运行面控制状态

硬规则：

- 不能按“旧文件清理”思路处理
- 只能在服务停稳或 runbook 明确指示下处理
- 本轮不做任何删除、重写、迁移

### 3.2 Persistent runtime state

典型路径：

- `state/*`

性质：

- 持久运行状态
- 可能包含 driver state、job db、lane state、review packs、temporary runtime state

硬规则：

- 不是 retention cleanup 入口
- 本轮只观察和写 policy，不处理内容

### 3.3 Runtime canonical evidence

典型路径：

- `artifacts/jobs/*`
- `artifacts/monitor/maint_daemon/incidents/*`

性质：

- canonical runtime evidence
- 与 job / incident 主键绑定

当前口径：

- 先保留
- 不在本轮做目录级清理

### 3.4 Runtime rolling telemetry

典型路径：

- `artifacts/monitor/*`
- `logs/*`

性质：

- 可增长
- 可讨论 future retention / budget / archive
- 但本轮只做 policy，不执行 cleanup

优先级：

- 第一治理对象

### 3.5 Validation / review / historical docs

典型路径：

- `docs/dev_log/artifacts/*`
- `artifacts/reviews/*`
- `artifacts/release_validation/*`
- `docs/dev_log/*`

性质：

- 偏验证、审计、review、历史记录
- 当前体量不是主要风险源

当前口径：

- 不做体积驱动清理
- 先做分类与索引边界

## 4. `.run/` 的特别说明

这轮必须把 `.run/` 从“普通 retention 对象”里单独提升出来。

因为它通常不是“历史产物桶”，而是：

- 当前 live runtime state
- 各类进程状态协同面
- 浏览器/worker/viewer 运行时指针集合

因此：

- `.run/*` 不能纳入 age-based janitor
- `.run/*` 不能纳入“找老文件删掉”
- `.run/*` 不能与 `artifacts/monitor/*` 按同一种治理动作处理

正确口径是：

- `.run/*` 只在服务停稳或 runbook 明确指示下处理
- 本轮只把它写进 policy 和禁行动作

## 5. 当前阶段允许谈什么，不允许做什么

### 可以谈

- 哪类目录未来适合做 archive
- 哪类目录适合做 budget guard
- 哪类目录只该做索引和分类

### 不能做

- 直接删 monitor 子树
- 直接删 jobs 子树
- 直接删 `.run/*`
- 直接删 `state/*`
- 把 retention policy 落成自动脚本并立刻执行

## 6. 后续真正要治理时的优先级

后续独立任务应按这个顺序考虑：

1. `artifacts/monitor/`
2. `logs/`
3. review / validation / historical docs 的索引边界
4. 最后才讨论 archive / deletion mechanics

而不是：

- 先从 `docs/dev_log/artifacts/` 开刀
- 或把 `.run/` 当普通垃圾目录处理

## 7. 一句话结论

> `.run/` 是 live runtime state，不是普通 retention 对象；当前第一治理对象是 `artifacts/monitor/`，但本轮只做 policy，不执行任何实际清理。
