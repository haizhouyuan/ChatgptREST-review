# Skill Market Source Intake Guide v1

更新时间：2026-03-29

这份文档描述 ChatgptREST skill platform 当前的外部 source intake 规则。目标不是自动安装第三方 skill，而是把外部候选以 **allowlisted source -> quarantine candidate** 的方式接入现有 market gate。

## 1. 当前原则

- canonical skill authority 仍然是：
  - `ops/policies/skill_platform_registry_v1.json`
- 外部 source 只负责把候选 skill 导入 quarantine：
  - 不直接进入 bundle
  - 不直接进入 production runtime
  - 不跳过 `evaluate -> promote/deprecate`

## 2. Source Allowlist

默认 allowlist 文件：

- `ops/policies/skill_market_sources_v1.json`

每个 source 至少包含：

- `source_id`
- `enabled`
- `kind`
- `source_market`
- `trust_level`
- `manifest_uri`
- `allowed_uri_prefixes`

当前首批保留的 source family：

- `openclaw_official_registry`
- `curated_github_registry`

注意：

- 默认 `enabled=false`
- 只有 operator 明确批准后才应填写 `manifest_uri`
- 这一步的目标是受控 intake，不是开放 market crawl

## 3. Candidate Manifest Contract

目前 intake 脚本支持 `json_manifest`，最小格式：

```json
{
  "candidates": [
    {
      "skill_id": "wechat-sender",
      "source_uri": "https://clawhub.ai/skills/wechat-sender",
      "capability_ids": ["social_automation"],
      "summary": "wechat message sender"
    }
  ]
}
```

可选字段：

- `source_market`
- `linked_gap_id`
- `evidence`

导入时会自动补：

- `source_id`
- `source_kind`
- `source_trust_level`
- `manifest_uri`

## 4. Operator Commands

列出 allowlisted sources：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/manage_skill_market_candidates.py list-sources
```

从 allowlisted source 导入候选：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/manage_skill_market_candidates.py import-source \
  --source-id curated_github_registry \
  --manifest-uri file:///tmp/skill_market_manifest.json \
  --allow-disabled
```

直接调用 intake helper：

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/import_skill_market_candidates.py
```

说明：

- `import-source` 会按 `(skill_id, source_market, source_uri)` 去重
- 重复来源不会再次注册 candidate，而是记入 `skipped_existing`
- 新 candidate 仍然是 `quarantine / pending / unreviewed`

## 5. 后续流程

导入后继续走现有 market gate：

1. `list`
2. `evaluate`
3. `promote`
4. `deprecate`

也就是说，外部 source intake 只解决：

- 候选从哪来
- 如何受控导入
- 如何避免重复 origin

它不负责：

- 自动安装
- 自动进入 runtime
- 自动加入 bundle

## 6. 当前边界

这版只实现了：

- allowlisted source authority
- manifest import
- operator CLI entry
- quarantine de-dup

还没实现：

- 官方 registry 的自动抓取 adapter
- curated GitHub 的自动索引 adapter
- 中文生态 source 的专门 adapter

这些都应该在后续 slice 里补，而且仍然必须维持 quarantine-first。
