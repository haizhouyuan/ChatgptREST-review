# Work Memory Backfill Importer Walkthrough v1

## 目标

这轮把 `planning` 侧的 backfill manifest 接进 `ChatgptREST` durable work-memory 主链，交付的不是新 schema，而是 import bridge：

- importer kernel
- CLI operator 入口
- dry-run / execute / manual review queue
- import metadata / audit preservation
- replay / idempotent execute
- retrieval / explainability smoke

## 代码落点

- importer kernel: `chatgptrest/kernel/work_memory_importer.py`
- manager metadata bridge: `chatgptrest/kernel/work_memory_manager.py`
- resolver metadata explainability: `chatgptrest/cognitive/context_service.py`
- operator CLI: `chatgptrest/cli.py`

## importer 入口

内核入口是 `WorkMemoryImporter`，只接受两类 manifest object:

- `active_project`
- `decision_ledger`

每个 entry 都先走 `build_work_memory_object()` typed validation，再形成结构化 plan/result。

## gate 处理

- `ready`
  只能进入可写路径；默认 execute 只处理这类 entry。
- `manual_review_required`
  第一版不写 active work-memory；execute 时只入 `meta` tier review queue。
- unknown gate
  fail-closed，返回 machine-readable blocked reason。

## metadata 保留位置

planning manifest 的 metadata 没有塞进 payload contract，而是分层保留：

- active write:
  - `record.value.import_metadata`
  - `record.value.import_audit`
- manual review queue:
  - `record.value.import_metadata`
  - `record.value.review_note`

这样 `seed_id`、`source_seed_doc`、`conditions`、`provenance_grade`、`do_not_infer`、`import_gate`、`manifest_id` 都能从导入结果和落库记录里追溯。

## idempotency / replay

这轮 replay 的关键是把 import 缺省字段稳定化，而不是让每次 execute 重新补当前时间。

- `valid_from` 缺省时冻结为 `manifest.generated_at`
- `active_project.last_updated` 缺省时跟随稳定 `valid_from`
- `session_id` 缺省为 `wm-import::{account_id}::{role_id}::{manifest_id}`
- `thread_id` 缺省为 `wm-import::{role_id}::{object_type}::{manifest_id}`
- `trace_id` 缺省为 `sha1(manifest_id:seed_id)` 派生的稳定值

重复 execute 同一 manifest / seed 时，会在同 identity scope 下走 dedup merge，而不是制造不可控重复 active object。

## CLI/operator

CLI 入口：

```bash
chatgptrestctl work-memory import-manifest
```

核心参数：

- `--manifest PATH` 可重复
- `--dry-run`
- `--execute`
- `--account-id`
- `--role-id`
- `--session-id`
- `--thread-id`
- `--only-gate ready|manual_review_required|all`
- `--limit`
- `--json-out`
- `--report-out`

## 验证结果

### 单元回归

已通过：

```bash
./.venv/bin/pytest -q tests/test_work_memory_importer.py tests/test_work_memory_manager.py tests/test_context_service_work_memory.py tests/test_cli_chatgptrestctl.py -k 'work_memory or import_manifest'
```

结果：

- `28 passed`

### 真实 manifest dry-run

命令：

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

结果摘要：

- `27` entries parsed
- `24 ready`
- `3 manual_review_required`
- `0 blocked`

### 真实 manifest execute ready

命令：

```bash
env OPENMIND_MEMORY_DB=/tmp/work_memory_import_smoke.db \
  ./.venv/bin/python -m chatgptrest.cli work-memory import-manifest \
  --manifest /vol1/1000/projects/planning/docs/backfill/active_project_seed_manifest_v1.json \
  --manifest /vol1/1000/projects/planning/docs/backfill/decision_ledger_seed_manifest_v1.json \
  --execute \
  --account-id acct-backfill \
  --role-id planning \
  --json-out /tmp/work_memory_import_execute_1.json \
  --report-out /tmp/work_memory_import_execute_1.md
```

结果摘要：

- `24 written`
- `3 skipped`
- `0 blocked`
- `0 queued_review`

### replay execute

再次执行同一 ready import：

- `24 written`
- `24 duplicate`

说明 replay 已进入可预测 dedup 路径。

### manual review queue

命令：

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

结果摘要：

- `3 queued_for_review`
- `24 skipped`
- `0 written`

manual review 项没有混进 active context。

### retrieval / explainability smoke

在同一 temp DB 上运行 `ContextResolver.resolve()`：

- query: `shared cognition 四端 联合验收`
  - 命中 imported active project `AP-007`
  - 命中 imported active project `AP-006`
  - 命中 imported decision `DCL-20260329-SC-BLOCKER`
- query: `会议录音 ASR 知识沉淀`
  - 命中 imported active project `AP-006`
  - 命中 imported decision `DCL-20260330-LTM-PROJECTIONONLY`

explainability 结果确认：

- `work_memory_scope_hits.active_project == account_role`
- `work_memory_scope_hits.decision_ledger == account_role`
- `work_memory_query_sensitive == true`
- `### Active Project Map` 仍在 `### Decision Ledger` 前面
- manual review 项 `AP-005 九号软模合同谈判` 不会出现在 active context

## 这轮没有做什么

- 没改 planning manifest 内容口径
- 没新增 HTTP import API
- 没碰 `Judgment Card`
- 没做 planning authority sync / seed import automation
- 没重新设计 work-memory schema

## 结论

这轮交付让 planning backfill manifest 第一次真正进入 `ChatgptREST` durable work-memory 主链，并具备：

- 可 dry-run
- 可 execute
- 可审计
- 可 replay
- 可通过 resolver 召回
