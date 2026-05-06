# Planning Bulk Promotion And Runtime Pack Release Runbook V1

Date: 2026-04-08

## 1. Purpose

This runbook covers the two distinct planning knowledge maintenance lanes introduced and clarified during V6:

1. **planning bulk promotion**
   - promotes bounded planning atoms into `active` / `candidate`
2. **planning reviewed runtime pack release**
   - exports the reviewed explicit pack and assembles the ready release bundle consumed by explicit planning-pack search

These are separate lanes and must not be conflated.

## 2. Live systemd units

### Bulk promotion lane

- [chatgptrest-planning-bulk-promotion.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-bulk-promotion.service)
- [chatgptrest-planning-bulk-promotion.timer](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-bulk-promotion.timer)

### Reviewed maintenance lane

- [chatgptrest-planning-review-maintenance.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-review-maintenance.service)
- [chatgptrest-planning-review-maintenance.timer](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-review-maintenance.timer)

## 3. Manual commands

### Run bulk promotion once

```bash
systemctl --user start chatgptrest-planning-bulk-promotion.service
```

### Dry-run bulk promotion

```bash
./.venv/bin/python ops/run_planning_bulk_groundedness_promotion.py --max-atoms 2000 --batch-size 200
```

### Refresh explicit planning runtime pack and release bundle

```bash
./.venv/bin/python ops/run_planning_runtime_pack_refresh.py
```

### Check current explicit bundle pointer

```bash
./.venv/bin/python - <<'PY'
from chatgptrest.evomap.knowledge.planning_runtime_pack_search import planning_runtime_pack_bundle_status
import json
print(json.dumps(planning_runtime_pack_bundle_status(), ensure_ascii=False, indent=2))
PY
```

## 4. Evidence roots

### Bulk promotion

- `artifacts/monitor/planning_bulk_groundedness_promotion/<stamp>/`

### Raw reviewed runtime pack

- `artifacts/monitor/planning_reviewed_runtime_pack/<stamp>/`

### Explicit release bundle

- `artifacts/monitor/planning_runtime_pack_release_bundle/<stamp>/`

### Validation / sensitivity / observability

- `artifacts/monitor/planning_runtime_pack_validation/<stamp>/`
- `artifacts/monitor/planning_runtime_pack_sensitivity_audit/<stamp>/`
- `artifacts/monitor/planning_runtime_pack_observability_samples/<stamp>/`

## 5. Success criteria

The explicit planning pack is healthy only when all of the following are true:

1. `planning_runtime_pack_bundle_status()` reports:
   - `available=true`
   - `ready_for_explicit_consumption=true`
   - `bundle_freshness=fresh`
2. the release bundle manifest has:
   - `offline_validation_ok=true`
   - `sensitivity_clear=true`
   - `observability_schema_present=true`
3. explicit planning-pack smoke queries hit the fresh bundle rather than an older ready bundle

## 6. Guardrails

1. Do not write `groundedness = quality_auto`.
2. Do not broad-promote pure-text planning atoms without runtime anchors into `active`.
3. Do not assume raw pack export means the explicit consumer pointer has advanced.
4. Do not confuse reviewed maintenance with bulk promotion scheduling.
