# Finbot High-Quality Candidate Register

Generated: `2026-05-11T00:36:46+08:00`

Reviewer: `Worker B / Codex`

Boundary: research-only. This register does not provide investment advice, target-price advice, trade signals, broker actions, automatic trading, position sizing, or a production watchlist.

## Standard

A case can be called high-quality only when it has a complete five-tuple:

`Claim -> Evidence file -> Source -> Timestamp -> Reviewer`

It also needs primary/authority evidence that supports the specific research theme, not merely evidence that the ticker has SEC/companyfacts data. Risk and counter-evidence must be concrete enough for a future reviewer to retire or continue the case.

## Current Result

- Hard-reviewed cases: `10`
- Current high-quality cases: `0`
- Conditional high-quality candidates after evidence repair: `6`
- Parked cases: `8`
- Rejected cases: `2`

No case is promoted in this pass. The current packet is much better at proving ticker-level source availability than proving theme-level research quality.

## Conditional Candidates

| Case | Ticker | Current evidence strength | Missing before high-quality |
| --- | --- | --- | --- |
| `OA-12-03-pltr-source-system-gaps-to-enable-next` | PLTR | Ticker-aligned `EV-12-PLTR`; SEC submissions/companyfacts primary evidence; latest filing `10-Q` dated `2026-05-05`; risk row exists. | Exact primary-source trace tying the source-system-gaps theme to PLTR; concrete peer or management-disclosure counter-evidence; explicit retirement trigger. |
| `OA-12-02-anet-policy-driven-china-supply-chains` | ANET | Ticker-aligned `EV-12-ANET`; SEC submissions/companyfacts primary evidence; latest filing `10-Q` dated `2026-05-06`; risk row exists. | Workflow-verified China policy or supply-chain authority evidence; separation from candidate A-share/CNINFO route; concrete contradiction source. |
| `OA-11-03-panw-security-platform-consolidation` | PANW | Ticker-aligned `EV-11-PANW`; SEC submissions/companyfacts primary evidence; latest filing `8-K` dated `2026-04-13`; risk row exists. | Primary-source trace for platform consolidation; concrete peer/platform counter-evidence; local-ledger signal separated from authority evidence. |
| `OA-11-02-zs-identity-and-zero-trust-spend` | ZS | Ticker-aligned `EV-11-ZS`; SEC submissions/companyfacts primary evidence; latest filing `8-K` dated `2026-04-16`; risk row exists. | Primary-source trace for identity/zero-trust demand or spend; peer/customer contradiction route; explicit invalidation trigger. |
| `OA-10-03-ferg-specialty-contractor-rollups` | FERG | Ticker-aligned `EV-10-FERG`; SEC submissions/companyfacts primary evidence; latest filing `10-Q` dated `2026-05-05`; risk row exists. | Authority trace for contractor rollups, supplier graph or acquisition/backlog linkage; full decision memo; concrete peer contradiction. |
| `OA-02-01-vrt-data-center-power-bottleneck` | VRT | Ticker-aligned `EV-02-VRT`; SEC submissions/companyfacts primary evidence; latest filing `8-K` dated `2026-04-27`; full decision memo exists; risk row exists. | Exact authority trace for data-center power or balance-of-plant bottleneck; industrial/peer corroboration; explicit retirement trigger. |

## Parked But Not Candidate Yet

- `OA-12-01-tsm-a-share-official-disclosure-backlog`: `EV-12-TSM` is ticker-aligned, but the evidence row has `latest_primary_filing: null` and no metric trace. It remains parked until primary detail exists and the A-share official-disclosure route is enabled or replaced with an authority source.
- `OA-11-01-crwd-ai-attack-surface`: `EV-11-CRWD` is ticker-aligned, but `revenue_fact` is null and the AI attack-surface theme is not primary-source trace-bound. It remains parked until those gaps close.

## Rejected

- `OA-X139-pltr-china-anti-dumping-policy-exposure`: evidence id `EV-05-CROX` maps to CROX, not PLTR.
- `OA-X140-rddt-boring-infrastructure-rollup-alpha`: evidence id `EV-05-ELF` maps to ELF, not RDDT.

These should not re-enter the candidate queue by score alone. They need new ticker-aligned evidence ids and authority evidence.
