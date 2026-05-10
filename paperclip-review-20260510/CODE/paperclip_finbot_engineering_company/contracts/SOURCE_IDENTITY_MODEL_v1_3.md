# Source Identity Model v1.3

Status: frozen for Finbot v2.1 minimal gatekeeper.

This model resolves the v2 inconsistency between `source_id`, `source_route_id`, and `source_account_id`. The rule is simple: routes, accounts, content, evidence, and claims are different entities and must not share IDs.

## Entity Types

| Entity | Prefix | Meaning | Can Emit EvidenceItem? |
|---|---|---|---|
| SourceRoute | `SR-` | Official/data/platform route used by a connector | Yes, if route type and artifact pass gate |
| SourceAccount | `SA-` | KOL, blogger, creator, analyst, or account identity | No |
| ContentItem | `CI-` | One article, video, post, transcript, filing, or raw captured content unit | No |
| EvidenceItem | `EI-` | Gate-passed official or primary artifact with raw file and checksum | Already evidence |
| Claim | `CLM-` | Atomic statement extracted from a ContentItem | No |
| FetchAttempt | `FA-` | Connector retrieval attempt, including failed or blocked fetches | No |
| EvidenceGap | `EG-` | Missing source/evidence requirement | No |
| SignalRule | `SRULE-` | Research-only rule contract for review alerts | No |

## Prefix Patterns

```text
SourceRoute:   SR-{MARKET}-{CODE}
SourceAccount: SA-{TIER}-{CODE}
ContentItem:   CI-{SOURCE}-{DATE}-{N}
EvidenceItem:  EI-{SOURCE}-{DATE}-{N}
Claim:         CLM-{SOURCE}-{DATE}-{N}
FetchAttempt:  FA-{SOURCE}-{DATE}-{N}
EvidenceGap:   EG-{SOURCE}-{DATE}-{N}
SignalRule:    SRULE-{THEME}-{N}
```

Examples:

```text
SR-US-SEC
SR-CN-CNINFO
SR-CN-SSE
SR-US-OPENBB
SA-D-FUZONG
SA-D-BEARCAVE
CI-FUZONG-BILI-20260117-001
EI-SEC-20260226-TSLA10K
CLM-FUZONG-20260117-001
FA-CNINFO-20260507-001
EG-FUZONG-20260428-DOUYINURL
```

## Authority Rules

1. `SourceAccount` and `ContentItem` can produce claims, but never EvidenceItems.
2. KOL/blogger/social sources start as tier `D` and `access_tag=research_only`.
3. A KOL claim may point to an `EvidenceGap`, not to a synthetic EvidenceItem.
4. If a KOL claim is corroborated, the EvidenceItem belongs to the official `SourceRoute`, not to the KOL account.
5. A blocked or failed fetch is a `FetchAttempt`, never an `EvidenceItem`.
6. An EvidenceItem requires raw artifact path, SHA-256 checksum, `published_at`, and `available_at`.
7. `SourceScore` cannot change evidence authority tier.

## Current Forbidden Conversions

```text
SA-D-FUZONG -> EvidenceItem
CI-FUZONG-* -> EvidenceItem
blocked FetchAttempt -> EvidenceItem
OCR-only visual context -> speech Claim
Douyin placeholder URL -> ContentItem source_url
D-only claim -> candidate OpportunityCase
```

## Minimal Gatekeeper Requirement

Every v2.1 connector, material recovery, claim extraction, and replay artifact must pass `tools/minimal_gatekeeper.py` before it can be used by later validators.
