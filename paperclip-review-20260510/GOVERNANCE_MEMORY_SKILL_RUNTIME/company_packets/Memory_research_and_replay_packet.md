# Memory Research And Replay Packet

Generated: `2026-05-10T08:27:22+08:00`

Memory Company keeps durable recall separate from authority. Planning and Finbot outputs may create `candidate_memory_delta`; Governance decides whether anything is promoted.

| Provider or pattern | Status | Boundary |
| --- | --- | --- |
| EvidenceLog | authority baseline | Paperclip-native evidence ledger; auditable and exportable. |
| AuthorityLedger | authority baseline | Stores accepted source/evidence authority, not rationale chatter. |
| LLM Wiki | candidate knowledge workspace | Useful for searchable summaries; not authoritative without evidence pointers. |
| thought-retriever | candidate retrieval pattern | Can retrieve reasoning traces; must not promote private rationale to authority. |
| Graphiti | no-write challenger | Interesting graph memory; blocked for authority promotion until privacy/provenance/export reviewed. |
| Supermemory | no-write challenger | External provider boundary requires account/privacy/export approval. |
| GBrain | no-write challenger | Candidate only; no production authority until Governance approval. |
| MemPalace | no-write challenger | Candidate only; may help long-form recall but cannot override EvidenceLog. |

| Layer | Definition |
| --- | --- |
| current_truth | Latest operational state; can change quickly; must link to evidence. |
| authority | Accepted evidence, contracts and source-of-truth docs. |
| verbatim | Exact quoted/source text under copyright and privacy limits. |
| rationale | Agent reasoning summaries; never promoted without source evidence. |
| candidate_memory_delta | Proposed memory update awaiting Governance review. |

Replay records:

- Planning case replay: overnight cadence decision is stored as candidate_memory_delta with pointer to `Planning_overnight_closeout.md`.
- Finbot case memory_delta: only case IDs, evidence IDs and unresolved human-review questions are durable candidates; no buy/sell/hold, target price or production watchlist is stored.
- Authority promotion exclusion: KOL-only thesis notes, endpoint-only connector claims, fixture adapter proofs and agent rationale cannot become authority.
