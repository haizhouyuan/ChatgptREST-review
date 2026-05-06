# 2026-04-03 Planning Task Plane Redteam Fix Walkthrough v2

## 触发原因

第二轮 `claudegac` 在审 `cdd78ceb` 时，通过解释器直接打出了 store 层 `_normalize_text_list()` 的脏输入问题。

我没有直接照单全收，而是先本地复现：

```bash
./.venv/bin/python3 - <<'PY'
from chatgptrest.planning.meeting_task_store import _normalize_text_list
for label, value in [('dict', {'bad': 'shape'}), ('int', 1), ('mixed', ['good', {'skip': 'me'}, None, 42])]:
    try:
        print(label, _normalize_text_list(value))
    except Exception as exc:
        print(label, 'CRASH', repr(exc))
PY
```

## 实际改动

1. 收紧 `_normalize_text_list()`
2. 收紧 `_merge_unique()`
3. 补 `store` 层 malformed shape 测试
4. 重新跑 planning task plane 回归
5. 重新导出 acceptance pack

## 关键命令

```bash
python3 -m py_compile \
  chatgptrest/planning/meeting_task_store.py \
  tests/test_meeting_task_store.py

./.venv/bin/pytest -q \
  tests/test_meeting_task_store.py \
  tests/test_routes_agent_v3_planning_task_plane.py \
  tests/test_routes_agent_v3_meeting_task_layer.py \
  tests/test_export_planning_phase1_continuity_acceptance_pack.py

./.venv/bin/python ops/export_planning_phase1_continuity_acceptance_pack.py \
  --output-dir docs/dev_log/artifacts/planning_task_plane_acceptance_pack_20260403_v4
```

## 本轮判断

这轮不是新功能，而是把 route/store 两层的同类输入归一化漏洞一起压平。
