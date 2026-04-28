# Multica Migration Inventory

Date: 2026-04-27

Source:

- Live Multica CLI export from Assistant Factory workspace:
  - `planning/20260427_multica_migration_raw/assistant_factory_issues.json`
- Live Multica CLI export from Assistant Ops workspace:
  - `planning/20260427_multica_migration_raw/assistant_ops_issues.json`
- Completion summary:
  - `/vol1/1000/projects/ChatgptREST/tmp/review_packets/2026-04-27_multica_chief_completion_summary.md`
- Classification table:
  - `planning/20260427_multica_migration_raw/multica_issue_classification.tsv`

## 1. Live Export Summary

Multica CLI is available:

```text
/home/yuanhaizhou/.local/bin/multica
multica 6c0f469
```

Exported issues:

| Workspace | Count | Status |
|---|---:|---|
| Assistant Factory | 26 | 26 done |
| Assistant Ops | 91 | 74 done, 17 cancelled |
| Total | 117 | 100 done, 17 cancelled |

## 2. Classification Result

| Migration class | Count | Meaning |
|---|---:|---|
| `migrate_lesson_or_followup` | 53 | Useful for Paperclip platform governance or follow-up issue design. |
| `archive_as_blueprint_or_future_project` | 20 | Useful historical design/blueprint, but not immediate runtime governance work. |
| `archive_do_not_migrate_as_success` | 17 | Cancelled or superseded issues; keep as failure/obsolete evidence only. |
| `review_manually` | 27 | Packet/red-team/fallback reviews that may contain lessons but should not be blindly migrated. |

## 3. Domain Counts

| Domain | Count | Migration stance |
|---|---:|---|
| `packet-review-fallback` | 33 | Review manually; extract review process patterns, not every issue. |
| `control-plane-review` | 16 | Migrate as governance patterns. |
| `issue-contract-governance` | 9 | Migrate into Paperclip issue contract policy. |
| `control-plane` | 8 | Migrate into Paperclip control-plane org. |
| `planning-memory` | 8 | Archive as future memory-system blueprint. |
| `native-no-write-readonly-proof` | 7 | Migrate into runtime safety / no-write smoke work. |
| `chief-ops-contract` | 7 | Migrate into AI Runtime Governance org. |
| `specialist-contracts` | 6 | Archive as assistant blueprint. |
| `redteam-harness` | 5 | Migrate into QA/review gates. |
| `chatgptrest-capability` | 4 | Migrate into Browser and Vision Lab. |
| `finbot` | 4 | Archive as future Finbot blueprint. |
| `cancelled-lc-nw-smoke-fixture` | 4 | Archive as failed fixture; do not count as success. |
| `autopilot-dryrun-governance` | 4 | Migrate into no-write dry-run governance. |
| `education` | 2 | Archive as future assistant blueprint. |

## 4. Most Important Lessons To Migrate

### 4.1 Control Plane Must Start Read-Only

Multica matured to:

```text
bounded observer/proposer
+ packet-only/read-only/design-only execution
+ P3/P4 sidecar reduction candidate
- native no-write worker smoke
- write actuator
- unsupervised state mutation
```

Migration rule:

- Paperclip governance org should start as read-only/design-only.
- Do not create an autonomous write actuator until no-write smoke, approval, locks and audit trail are proven.

### 4.2 Issue Done Does Not Mean Product Done

Multica issue completion often means a design, contract, packet or review was done, not that the underlying product is production-ready.

Examples:

- `planning-memory-system` done does not mean production memory system exists.
- `finbot-personal-research-system` done does not mean production investment assistant exists.
- `chatgptrest-capability-governance` done does not mean ChatGPTREST code/runtime capabilities are fixed.

Migration rule:

- Paperclip issue titles and acceptance criteria must distinguish:
  - design completed;
  - sample validated;
  - smoke passed;
  - production implementation completed.

### 4.3 Avoid Issue-Creation As Fake Progress

Multica identified that autopilot creating governance issues was not real autonomy.

Migration rule:

- Paperclip should not treat "issue created" as progress.
- The useful signal is artifact + evidence + QA + state transition + reviewer/owner.

### 4.4 Cancelled Smoke Fixtures Are Evidence, Not Success

Cancelled issues such as `AOP-81..AOP-84` were old LC-NW-1 smoke fixtures. They must not be used as success evidence.

Migration rule:

- Paperclip archive should preserve cancelled issues as failure/obsolete fixtures.
- Any new no-write smoke must use a fresh target and fresh evidence.

### 4.5 Runtime Guards and Permission Selftests Matter

Useful Multica themes:

- permission selftest;
- terminal allowlist;
- mutation tool policy;
- no-write smoke;
- runtime attestation;
- manifest/hash drift detection;
- worker command policy hardening.

Migration rule:

- These become core projects inside `AI Runtime Governance`, not optional notes.

### 4.6 Red-Team/Fallback Review Must Be Packetized

Multica moved from ad hoc review to packet-based review.

Migration rule:

- Every high-risk Paperclip change should have:
  - context packet;
  - source evidence;
  - claim ledger;
  - independent/fresh review where needed;
  - clear accept/reject criteria.

## 5. Paperclip Migration Buckets

### Bucket A: Directly Migrate As Governance Backlog

From Multica:

- `ASF-15..18`
- `ASF-23..26`
- `AOP-77..80`
- `AOP-85..91`
- `AOP-61..76`
- `AOP-19..27`

Paperclip target:

- AI Runtime Governance org.

Themes:

- runtime inventory;
- manifest and transition checker;
- live snapshot exporter;
- proof ledger;
- evidence bundle exporter;
- read-only dry-run reporter;
- no-write smoke;
- approval deny policy;
- issue contracts.

### Bucket B: Migrate As Browser/Capability Research Backlog

From Multica:

- `ASF-11`: existing web automation capability inventory.
- `ASF-12`: capability regression matrix.
- `ASF-13`: anything-cli / opencli upgrade path.
- `ASF-14`: UI automation upgrade plan.

Paperclip target:

- Browser and Vision Lab.

Themes:

- ChatGPTREST browser harness;
- opencli/anything-cli;
- browser-use alternatives;
- local vision model integration;
- computer-use replacement for Windows/headless constraints.

### Bucket C: Archive As Future Assistant Blueprints

From Multica:

- `AOP-1..6`: Chief/HR/Meeting/Strategy/Finbot/Education specialist contracts.
- `ASF-1..6`, `ASF-21..22`: planning memory designs.
- `ASF-7..10`: Finbot blueprint.
- `ASF-19..20`: Education assistant blueprint.

Paperclip target:

- Not immediate.
- Archive under Multica Archive and Migration.
- Re-open later if those assistant programs become active.

### Bucket D: Archive Failure / Cancelled Fixtures

From Multica:

- `AOP-81..84`: old LC-NW-1 smoke fixtures.
- other cancelled red-team/fallback duplicates.

Paperclip target:

- Multica Archive and Migration.

Rule:

- Preserve as "do not cite as success."

### Bucket E: Manual Review Before Migration

From Multica:

- 27 packet-review/fallback items.

Paperclip target:

- Review manually.

Reason:

- Many are review artifacts for specific ASF checkpoints. They may contain valuable review criteria, but migrating each as a live issue would create noise.

## 6. Immediate Migration Recommendations

Create Paperclip projects:

1. `runtime-context-and-permission-model`
2. `mcp-cli-skill-architecture`
3. `browser-harness-upgrade-research`
4. `vision-video-qa-harness`
5. `skill-governance-loop`
6. `multica-archive-and-lessons`

Do not create hundreds of historical issues. Start with a small curated set:

- no-write runtime smoke;
- MCP/profile inventory;
- skill usage ledger;
- skill curator protocol;
- browser harness method comparison;
- visual/video QA harness;
- machine topology inventory;
- Multica failure fixture archive.

## 7. Risks

1. Migrating all 117 issues directly would recreate Multica's backlog weight in Paperclip.
2. Treating completed design issues as implementation evidence would mislead downstream planning.
3. Paperclip orgs can become another documentation graveyard unless every issue has artifact + gate + owner.
4. Skill governance could become too heavy; logging must stay cheap.
5. Browser/computer-use R&D could destabilize ChatGPTREST if tested against production lanes. It needs isolated probes.

## 8. Next Step

Use this inventory to build the Paperclip multi-org issue tree proposal:

- orgs;
- projects;
- initial issues;
- acceptance criteria;
- evidence artifacts;
- what not to migrate.
