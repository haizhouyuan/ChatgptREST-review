# Work Memory Backfill Importer Runbook v1

## 适用范围

用于把 `planning` 侧 import-ready manifest 导入 `ChatgptREST` durable work-memory。

当前支持：

- `active_project`
- `decision_ledger`

## 前置条件

- 当前仓库：`/vol1/1000/projects/ChatgptREST`
- manifest 已由 planning 产出并通过 review
- operator 知道目标：
  - `account_id`
  - `role_id`

## manifest 路径

当前 planning 主 manifest：

- `/vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json`
- `/vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json`

## 1. dry-run

先做 dry-run，不要跳过。

```bash
env OPENMIND_MEMORY_DB=/tmp/work_memory_import_smoke.db \
  ./.venv/bin/python -m chatgptrest.cli work-memory import-manifest \
  --manifest /vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json \
  --manifest /vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json \
  --dry-run \
  --only-gate all \
  --json-out /tmp/work_memory_import_dry_run.json \
  --report-out /tmp/work_memory_import_dry_run.md
```

检查点：

- `blocked_count == 0`
- `ready` 和 `manual_review_required` 数量符合预期
- JSON report 和 Markdown report 都能落盘

## 2. execute ready

默认只导入 `ready`。

```bash
env OPENMIND_MEMORY_DB=/tmp/work_memory_import_smoke.db \
  ./.venv/bin/python -m chatgptrest.cli work-memory import-manifest \
  --manifest /vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json \
  --manifest /vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json \
  --execute \
  --account-id acct-backfill \
  --role-id planning \
  --json-out /tmp/work_memory_import_execute_ready.json \
  --report-out /tmp/work_memory_import_execute_ready.md
```

检查点：

- `written_count` 等于 ready entry 数
- `queued_review_count == 0`
- `blocked_count == 0`

## 3. execute manual review queue

这一步只在需要显式建 review queue 时运行。

```bash
env OPENMIND_MEMORY_DB=/tmp/work_memory_import_smoke.db \
  ./.venv/bin/python -m chatgptrest.cli work-memory import-manifest \
  --manifest /vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json \
  --manifest /vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json \
  --execute \
  --only-gate manual_review_required \
  --account-id acct-backfill \
  --role-id planning \
  --json-out /tmp/work_memory_import_execute_manual.json
```

检查点：

- `queued_review_count` 等于 manual-review entry 数
- `written_count == 0`
- review records 落在 `meta` tier

## 4. replay 检查

重复执行 ready import，确认进入 dedup 路径：

```bash
env OPENMIND_MEMORY_DB=/tmp/work_memory_import_smoke.db \
  ./.venv/bin/python -m chatgptrest.cli work-memory import-manifest \
  --manifest /vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json \
  --manifest /vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json \
  --execute \
  --account-id acct-backfill \
  --role-id planning \
  --json-out /tmp/work_memory_import_execute_replay.json
```

检查点：

- `duplicate_count` 应增长到 ready entry 数
- 不应产生不可控重复 active object

## 5. retrieval smoke

用 temp DB 验证 imported objects 能进入 `Active Context`：

```bash
env OPENMIND_MEMORY_DB=/tmp/work_memory_import_smoke.db \
  OPENMIND_KB_DB=/tmp/work_memory_import_smoke_kb.db \
  OPENMIND_KB_VEC_DB=/tmp/work_memory_import_smoke_kb_vec.db \
  ./.venv/bin/python - <<'PY'
import json
from chatgptrest.advisor.runtime import reset_advisor_runtime, get_advisor_runtime
from chatgptrest.cognitive.context_service import ContextResolver, ContextResolveOptions

reset_advisor_runtime()
runtime = get_advisor_runtime()
resolver = ContextResolver(runtime)
result = resolver.resolve(ContextResolveOptions(
    query='shared cognition 四端 联合验收',
    session_id='sess-antigravity',
    account_id='acct-backfill',
    agent_id='antigravity',
    role_id='planning',
    thread_id='thread-antigravity',
    sources=('memory', 'policy'),
))
print(json.dumps({
    'scope_hits': result.metadata.get('work_memory_scope_hits'),
    'query_sensitive': result.metadata.get('work_memory_query_sensitive'),
    'import_hits': result.metadata.get('work_memory_import_hits'),
}, ensure_ascii=False, indent=2))
PY
```

检查点：

- `Active Project Map` 和 `Decision Ledger` 都存在
- imported `active_project` 与 `decision_ledger` 至少各命中一条
- `work_memory_query_sensitive == true`
- `scope_hits` 仍是 `account_role`
- manual-review 项不出现在 `Active Context`

## metadata / audit 追溯位置

- ready write:
  - `record.value.import_metadata`
  - `record.value.import_audit`
- manual review queue:
  - `record.value.import_metadata`
  - `record.value.review_note`

## 边界

- 不要修改 planning manifest 口径
- 不要绕过 governance 直接写 active
- 不要把 `manual_review_required` 伪装成 approved
- 不要新增公共 HTTP import surface
