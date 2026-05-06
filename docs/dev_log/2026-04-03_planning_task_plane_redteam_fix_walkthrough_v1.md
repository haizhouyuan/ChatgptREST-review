# 2026-04-03 Planning Task Plane Redteam Fix Walkthrough v1

## 改动文件

1. `chatgptrest/planning/meeting_task_store.py`
2. `chatgptrest/api/routes_agent_v3.py`
3. `tests/test_meeting_task_store.py`
4. `tests/test_routes_agent_v3_planning_task_plane.py`
5. `AGENTS.md`

## 关键动作

1. 收掉 `list_public()` 的空 identity 泄漏。
2. 给 `GET /planning/tasks` 引入 limit clamp。
3. 把 `implementation_plan` 从“默认 pack profile 直接决定”改成“显式 goal / 真实实施语义”。
4. 给 `_planning_checkpoint_seed()` 加安全文本序列归一化。
5. 补 store / route 双层测试。
6. 重新导出 acceptance pack evidence。

## 关键命令

```bash
python3 -m py_compile \
  chatgptrest/planning/meeting_task_store.py \
  chatgptrest/api/routes_agent_v3.py \
  tests/test_meeting_task_store.py \
  tests/test_routes_agent_v3_planning_task_plane.py

./.venv/bin/pytest -q \
  tests/test_meeting_task_store.py \
  tests/test_routes_agent_v3_planning_task_plane.py

./.venv/bin/pytest -q \
  tests/test_routes_agent_v3_meeting_task_layer.py \
  tests/test_routes_agent_v3_planning_task_plane.py \
  tests/test_export_planning_phase1_continuity_acceptance_pack.py

./.venv/bin/pytest -q \
  tests/test_agent_v3_routes.py \
  tests/test_public_agent_mcp_validation.py

./.venv/bin/python ops/export_planning_phase1_continuity_acceptance_pack.py \
  --output-dir docs/dev_log/artifacts/planning_task_plane_acceptance_pack_20260403_v3
```
