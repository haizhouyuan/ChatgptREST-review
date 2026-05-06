# 2026-03-21 Research Evidence Policy v1

## Purpose

Freeze the evidence expectations used by `research` scenario packs so ingress, strategist, `deep_research`, and `report_graph` all read the same contract.

## Policy Table

| Profile | Lane | Min Evidence | Sources | Primary Sources | Traceable Claims |
|---|---|---:|---|---|---|
| `topic_research` | `deep_research` | 3 | required | preferred | required |
| `comparative_research` | `deep_research` | 4 | required | preferred | required |
| `research_report` | `report` | 4 | required | preferred | required |

## Runtime Effects

- Strategist:
  - uses `evidence_gate` watch policy for research profiles
  - blocks low-context `research_report` asks earlier than generic medium-risk work
- Report graph:
  - `web_research` skip threshold is no longer fixed at `3`
  - threshold becomes `max(3, acceptance.min_evidence_items)`
- Deep research:
  - pack profile and evidence expectations are injected into research context notes
- Consult:
  - research-heavy packs default to deep-research-capable model sets when caller does not force a mode

## Clarify Expectations

### `research_report`

Clarify when:

- completeness is still below the report threshold
- no grounding files / prior materials are attached
- research question, scope, or audience is still underspecified

### `topic_research`

Clarify when:

- the ask is still vague enough that there is no concrete scope or decision question
- no grounding inputs exist and completeness stays below the research threshold

### `comparative_research`

Clarify when:

- the compared objects are not explicit enough
- decision dimensions are still missing
- no grounding inputs exist and completeness stays below the comparative threshold
