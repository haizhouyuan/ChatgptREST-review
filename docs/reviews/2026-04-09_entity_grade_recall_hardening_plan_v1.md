# 2026-04-09 Entity-Grade Recall Hardening Plan v1

## Judgment

The next highest-ROI technical gap is no longer generic recall. It is entity-grade recall.

Current live benchmark state:

- `entity_rate = 0.0`
- bridge recall is strong enough for canary
- dossier / company-profile asks still land on `bridge + clarify` or `bridge + answer`, not true entity retrieval

This is the most likely weakness to surface first in Feishu canary usage.

## What this means

Current system behavior is already useful for:

- visit preparation
- topic analysis
- adjacent strategic context

But it is still weak for:

- `XX 公司整体情况`
- `XX 董事长背景`
- `XX 融资历史`
- exact company dossier retrieval

## Priority order

### E1. Targeted re-ingest first

Do not start with a generic entity registry.

First check whether the source material already exists but is not being retrieved strongly enough:

- company meeting notes
- company research notes
- due diligence fragments
- controlled planning materials

Priority entities:

1. `绿源`
2. `钛虎机器人`
3. other real canary misses that appear during watch window

### E2. Entity-aware ranking boost second

Boost exact or near-exact entity hits in:

- document title
- raw ref
- canonical question
- answer excerpt

This should stay scoped to planning explicit retrieval, not global hot path.

### E3. Entity registry only if E1/E2 are insufficient

Entity registry is a heavier framework move and should only be introduced when:

- source material exists
- targeted re-ingest already landed
- ranking boost still fails to provide reliable entity-grade recall

## Acceptance

For the current benchmark family:

- `entity_rate > 0.0`
- `绿源公司整体情况和产品线` no longer falls below bridge-only posture
- `钛虎机器人董事长背景和公司融资历史` no longer depends entirely on indirect bridge context
- no increase in misassociation rate
