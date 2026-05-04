# Paperclip Memory Research Lab Orchestrator

Memory management methods research laboratory for Paperclip.
Compares and evaluates memory systems (thought-retriever, Gbrain, graphiti, mempalace, supermemory) to provide best-practice recommendations for memory-management agents.

## Company

- **Company ID**: `51fc5dce-c1a9-49f4-8458-ee0000ae25a3`
- **Issue prefix**: `MEM`
- **Purpose**: 记忆管理方法研究实验室。对比研究 thought-retriever、Gbrain、graphiti、mempalace、supermemory 等记忆系统，为记忆管理 agent 提供最佳实践。

## Architecture

```
Paperclip API
  └─ run_from_paperclip(payload)
       ├─ MemoryResearchRequest (Pydantic validation)
       ├─ _route_runtime() → allocator_mvp (audit) + claudekimi pin
       ├─ _run_stub() → structured placeholder result
       ├─ _save_report() → ~/.paperclip/memory_reports/
       └─ MemoryResearchResponse (Pydantic)
```

## Task Types

| Task Type | Description |
|-----------|-------------|
| `system_eval` | Evaluate a single memory system across standard dimensions |
| `benchmark` | Run a standardized benchmark across multiple systems |
| `comparison` | Side-by-side comparison of multiple systems |
| `recommendation` | Produce a best-practice recommendation report |

## Known Memory Systems

- `thought-retriever`
- `gbrain`
- `graphiti`
- `mempalace`
- `supermemory`

Unknown system names are accepted with a warning reason code.

## Usage

### CLI

```bash
# Comparison of all known systems (Chinese output)
python -m paperclip_memory.memory_orchestrator --task-type comparison

# Single system eval
python -m paperclip_memory.memory_orchestrator \
  --task-type system_eval \
  --systems graphiti \
  --query "evaluate multi-hop recall on 10k entity graph"

# From JSON payload file
python -m paperclip_memory.memory_orchestrator --payload-file request.json

# Pipe payload
echo '{"task_type":"recommendation","memory_systems":["gbrain","supermemory"]}' | \
  python -m paperclip_memory.memory_orchestrator --payload -
```

### Python

```python
from paperclip_memory import run_from_paperclip

response = run_from_paperclip({
    "task_type": "comparison",
    "memory_systems": ["gbrain", "graphiti", "supermemory"],
    "query_context": "Which system best handles temporal knowledge graphs?",
    "output_language": "Chinese",
})
```

## Runtime

- Default provider: `claudekimi` (mimo-v2.5-pro) — research tasks need quality
- Default output language: Chinese
- Runtime allocation uses the shared `runtime_allocator/allocator_mvp.py` for audit; claudekimi is hard-pinned unless overridden
- Reports saved to `~/.paperclip/memory_reports/`

## Status

The orchestrator currently runs a **stub** that returns structured placeholder results. Real memory-system adapters will be added as individual modules (e.g., `adapters/graphiti_adapter.py`).

## Reference

This package follows the same pattern as `paperclip_finbot/`. See `finbot_orchestrator.py` and `tradingagents_adapter.py` for the reference implementation.
