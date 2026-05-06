# 2026-03-19 Memory / KB / Graph Inventory Audit Walkthrough v1

## This Slice

Produced a comprehensive inventory of:

- memory management
- knowledge base
- image library / gallery handling
- knowledge graph surfaces

Primary artifact:

- [2026-03-19_memory_kb_graph_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_memory_kb_graph_inventory_audit_v1.md)

## Why This Was Needed

The repository has accumulated multiple adjacent knowledge subsystems over time.
Without a current-state inventory, it is too easy to:

- assume dead code is still dead when live data has changed
- assume image handling exists because image generation exists
- treat memory, KB, and EvoMap as one thing when they are three different stores
- create architecture plans that collide with existing ingestion or lifecycle logic

## Evidence Used

Code audit:

- `chatgptrest/kernel/memory_manager.py`
- `chatgptrest/cognitive/memory_capture_service.py`
- `chatgptrest/cognitive/context_service.py`
- `chatgptrest/kb/registry.py`
- `chatgptrest/kb/hub.py`
- `chatgptrest/kb/writeback_service.py`
- `chatgptrest/kb/scanner.py`
- `chatgptrest/cognitive/ingest_service.py`
- `chatgptrest/evomap/knowledge/db.py`
- `chatgptrest/evomap/knowledge/graph_builder.py`
- `chatgptrest/evomap/knowledge/retrieval.py`
- `chatgptrest/evomap/activity_ingest.py`
- `chatgptrest/cognitive/graph_service.py`
- `chatgptrest/core/issue_graph.py`
- `chatgptrest/evomap/knowledge/extractors/antigravity_extractor.py`

Test surface audit:

- memory-related test grep
- KB-related test grep
- graph-related test grep
- direct reads of representative tests such as `tests/test_kb.py`,
  `tests/test_cognitive_api.py`, and `tests/test_antigravity_extractor.py`

Live data snapshot:

- `~/.openmind/memory.db`
- `~/.openmind/kb_search.db`
- `~/.openmind/kb_registry.db`
- `~/.openmind/kb_vectors.db`
- `data/evomap_knowledge.db`

## Key Findings

1. Memory is a real subsystem with active capture and recall, but semantic
   consolidation remains nearly absent.
2. KB is real and production-meaningful, but stability governance is still not
   operationalized.
3. 图库 is not a first-class subsystem; image handling mostly lives in runtime
   execution artifacts, not knowledge ingestion.
4. EvoMap graph is no longer an empty future shell; the live graph store is
   large and active.
5. The repository currently contains multiple graph domains that should not be
   conflated in later architecture work.

## Why The Audit Uses “code / runtime / live data” As Separate Axes

This repository repeatedly shows a pattern where:

- code exists
- some code is wired
- some code is wired and populated

Those are materially different maturity levels. The inventory therefore
classifies each subsystem using all three axes rather than just “implemented /
not implemented”.

## No Code Changes

This slice only produced documentation. No runtime code was modified.
