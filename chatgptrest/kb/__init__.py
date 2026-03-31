"""
Knowledge Base (Layer 3) – Personal Knowledge Infrastructure.

Implements the hybrid PKM model from KB DR:
- PARA outside (directory organization)
- Evergreen inside (note style)
- FTS + Vector + Graph underneath (retrieval)

Sub-modules:
    registry   – Artifact registry (SQLite metadata store)
    scanner    – File discovery (backfill + watchdog)
    pipeline   – Ingestion pipeline (normalize → classify → dedup → score → index)
    retrieval  – Hybrid retrieval (FTS5 + vector + RRF fusion)
"""
