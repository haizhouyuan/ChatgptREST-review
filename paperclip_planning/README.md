# Paperclip Planning Work Assistant Orchestrator

Orchestrator for the "Planning Work Assistant" Paperclip company.

## Purpose

Strategic planning, HR policy drafting, meeting audio extraction, and document generation.

## Task Types

| Task Type | Allocator Class | Default Quality | Privacy |
|---|---|---|---|
| `strategic_plan` | `document_draft` | HIGH | PRIVATE_CLOUD |
| `hr_policy` | `hr_sensitive` | STANDARD | LOCAL |
| `meeting_extraction` | `meeting_summary` | STANDARD | PRIVATE_CLOUD |
| `document_draft` | `document_draft` | STANDARD | EXTERNAL_CLOUD |

## Runtime Routing

- Default provider: **minimax** (cheap, adequate for planning tasks)
- Allocator selects the best runtime based on task class, quality, privacy, and quota
- Caller can override with `provider_override`

## Usage

### From Paperclip (programmatic)

```python
from paperclip_planning import run_from_paperclip

response = run_from_paperclip({
    "task_type": "strategic_plan",
    "input_content": "Q3 expansion into Southeast Asia...",
    "output_language": "Chinese",
})
```

### CLI

```bash
# From input text
python -m paperclip_planning.planning_orchestrator \
  --task-type strategic_plan \
  --input "Q3 expansion plan into Southeast Asia market..." \
  --language Chinese

# From file
python -m paperclip_planning.planning_orchestrator \
  --task-type meeting_extraction \
  --input-file transcript.txt

# From JSON payload
python -m paperclip_planning.planning_orchestrator \
  --payload '{"task_type": "hr_policy", "input_content": "..."}'
```

## Output

Reports are saved to `~/.paperclip/planning_reports/` as paired JSON + Markdown files.

## Status

Currently a **stub** -- `_run_planning_work()` returns a structured placeholder.
Replace with real LLM pipeline calls when ready.
