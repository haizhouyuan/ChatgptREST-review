# 2026-04-03 Planning Task Plane Redteam Fix Execution Review v2

## 1. 为什么会有 v2

`v1` 刚收掉 route 侧和 list 泄漏问题后，第二轮 `claudegac` 在继续审 `cdd78ceb` 时又暴露出一个同类问题：

1. store 层 `_normalize_text_list()` 仍会对脏输入出错
2. top-level `int` 会直接抛异常
3. top-level `dict` 会被误读成 key 列表
4. mixed list 中的 `dict` 会被错误串化进结果

这不是我直接照抄红队意见，而是我随后用本地解释器独立复现后确认成立。

## 2. 这轮新增修复

### 2.1 store 层文本序列归一化

`chatgptrest/planning/meeting_task_store.py`

1. `_normalize_text_list()` 现在对 top-level shape fail-closed：
   - `None -> []`
   - `str -> [str]`
   - `list/tuple/set -> 按项归一`
   - 其它类型直接 `[]`
2. nested `dict/list/tuple/set` 会被跳过，不再串化进 checkpoint。
3. `int` 这类非容器 top-level 值不再 crash。

### 2.2 merge 逻辑同步收紧

1. `_merge_unique()` 不再用 `list(existing or []) + list(incoming or [])`
2. 它现在先对两边分别 `_normalize_text_list(...)`
3. 避免 `str` 被拆成字符、脏 shape 被错误展开

## 3. 独立复现证据

修复前，本地复现实锤：

```text
dict ['bad']
int CRASH TypeError("'int' object is not iterable")
mixed ['good', "{'skip': 'me'}", '42']
```

这说明 route 层虽然已经收紧，但 store 层的同类输入归一化仍然不安全。

## 4. 新增测试

### 4.1 单元级

`tests/test_meeting_task_store.py`

新增：

1. `test_normalize_text_list_fail_closes_on_malformed_shapes`
2. `test_meeting_task_store_checkpoint_seed_ignores_malformed_list_shapes`

### 4.2 回归级

继续覆盖：

1. `tests/test_routes_agent_v3_planning_task_plane.py`
2. `tests/test_routes_agent_v3_meeting_task_layer.py`
3. `tests/test_export_planning_phase1_continuity_acceptance_pack.py`

## 5. 回归结果

通过：

```bash
python3 -m py_compile \
  chatgptrest/planning/meeting_task_store.py \
  tests/test_meeting_task_store.py

./.venv/bin/pytest -q \
  tests/test_meeting_task_store.py \
  tests/test_routes_agent_v3_planning_task_plane.py \
  tests/test_routes_agent_v3_meeting_task_layer.py \
  tests/test_export_planning_phase1_continuity_acceptance_pack.py
```

## 6. Evidence

acceptance pack 重导出后继续全绿：

- `docs/dev_log/artifacts/planning_task_plane_acceptance_pack_20260403_v4/manifest.json`
- `docs/dev_log/artifacts/planning_task_plane_acceptance_pack_20260403_v4/report_v1.md`

结果：

1. `overall_pass = true`
2. `7/7` scenario 通过

## 7. 本轮结论

现在更准确的说法是：

1. route 层脏输入保护和 store 层脏输入保护都已经补上
2. planning task plane 在“文本列表归一化”这类基础卫生上更完整了
3. 第二轮 strict red-team 仍应重跑，但当前已知同类漏洞不再只修了一半
