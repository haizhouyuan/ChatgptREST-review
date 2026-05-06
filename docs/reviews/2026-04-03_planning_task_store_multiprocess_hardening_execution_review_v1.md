# 2026-04-03 Planning Task Store Multiprocess Hardening Execution Review v1

## 1. 这一步做了什么

这一步不是继续扩 planning task type，而是补 `MeetingTaskStore` 最硬的 runtime 缺口：

1. file-backed store 的多进程安全
2. `_normalize_text_list()` 对 `set` 的非确定性输入

到这一步之前，planning task plane 已经有：

1. `OpenClawBot` 主链 acceptance
2. owner guard
3. implicit continue 收紧

但仍然缺一条很硬的底层保证：

> 两个进程同时读写同一个 planning task store 时，不能分裂任务，也不能丢 checkpoint merge。

## 2. 代码改动

### 2.1 store 层新增 process lock

[meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py)

`MeetingTaskStore` 现在不再只靠进程内 `threading.RLock()`。

新增的是：

1. store 根目录下的 `.lock`
2. 基于 `fcntl.flock()` 的跨进程独占锁
3. 所有 `get / put / get_public / list_public / resolve_task / update_checkpoint` 的 critical section 统一走 `_guard()`

这意味着当前 phase-1 planning sidecar truth 至少在：

1. 同一台 Linux 机器
2. 多 Python 进程
3. 同一个 store 目录

这三个条件下，已经不是“纯单进程假设”。

### 2.2 `_normalize_text_list()` 不再接收 `set`

之前 `_normalize_text_list()` 会接受 `set`。

问题不是 crash，而是：

1. `set` 无顺序
2. 同一输入可能在不同进程/不同运行次序里产出不同顺序
3. 对 checkpoint merge 和回归断言都不友好

现在行为是：

1. `list / tuple` 正常处理
2. `str` 仍按单元素处理
3. `set / dict / scalar malformed shape` 统一 fail-closed

## 3. 新增验证

[test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py)

这一步新增了两类更硬的证据：

1. `test_meeting_task_store_resolve_task_is_process_safe_for_same_identity`
   - 两个独立进程同时对同 identity / 同材料发起 resolve
   - 断言只会产生一个 `task_id`
   - 结果必须是 `1 new + 1 continue`
2. `test_meeting_task_store_update_checkpoint_is_process_safe_for_artifact_merge`
   - 两个独立进程同时对同 task 做 checkpoint writeback
   - 断言不同 `artifact_refs` 都能保留下来

这两条测试的价值比单进程单元测试高，因为它们直接回答了：

> 当前 file-backed store 是否仍然存在明显的本机多进程分裂/覆盖风险。

## 4. 当前判断

这一步之后，口径应更新成：

1. planning task plane 的 phase-1 sidecar truth 现在已经具备本机多进程锁保护
2. 这不等于它已经变成最终 canonical task runtime
3. 但“多 worker/多入口本机进程一碰就分裂”的红队批评，当前不应再原样保留

更准确的说法是：

1. `single-host multiprocess safety` 已补上
2. `distributed / network filesystem / cross-host` durability 仍未证明

## 5. 本地验证

通过：

1. [test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py)
2. [test_routes_agent_v3_meeting_task_layer.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_meeting_task_layer.py)
3. [test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py)
4. [test_openclawbot_planning_task_plane_acceptance.py](/vol1/1000/projects/ChatgptREST/tests/test_openclawbot_planning_task_plane_acceptance.py)
5. [test_openclawbot_meeting_intake_smoke.py](/vol1/1000/projects/ChatgptREST/tests/test_openclawbot_meeting_intake_smoke.py)
6. [test_openclaw_dynamic_replay_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_dynamic_replay_gate.py)
7. [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py)

另外，`OpenClawBot` 主链 acceptance pack 已重新导出并保持全绿：

1. [manifest.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_acceptance_pack_20260403_v1/manifest.json)
2. [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_acceptance_pack_20260403_v1/report_v1.md)

## 6. 一句话结论

这一步真正收掉的是：

> planning task plane 不再只是“语义边界更稳”，而是连本机多进程 file-backed truth 的最直接竞争风险也补到了可验证状态。
