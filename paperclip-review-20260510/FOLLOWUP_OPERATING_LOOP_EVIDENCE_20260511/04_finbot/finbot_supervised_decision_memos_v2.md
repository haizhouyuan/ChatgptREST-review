# Finbot Supervised Decision Memos v2

Generated: 2026-05-11T01:09:00+08:00  
Controller: codex_parent

Boundary: research-only. These memos are not investment advice, not target-price
advice, not trade signals, not broker actions, not automatic trading, not
position sizing and not a production watchlist.

## How To Use

Each memo is a supervised research prompt. The next operator should either
continue evidence collection or park/reject the case. No memo authorizes a
portfolio action.

## Memos

### VRT / `OA-02-01-vrt-data-center-power-bottleneck`

- Why continue: primary SEC filing evidence and companyfacts support a
  traceable research case around data center power / thermal bottlenecks.
- Research score band: `52 / 69 / 87` on `fundamental_scenario_score_0_100`;
  not a price target.
- Next evidence: add peer/customer evidence for power equipment demand and one
  counter-evidence route for margin or backlog normalization.
- Retirement trigger: park if the next authority source does not show
  theme-specific exposure beyond generic data-center wording.

### FERG / `OA-10-03-ferg-specialty-contractor-rollups`

- Why continue: primary SEC filing evidence and companyfacts support a
  traceable specialty contractor / distribution research case.
- Research score band: `62 / 79 / 97`; not a price target.
- Next evidence: add acquisition/backlog/supplier graph evidence and peer
  contradiction.
- Retirement trigger: park if acquisition or contractor-rollup exposure cannot
  be separated from generic distribution revenue.

### ZS / `OA-11-02-zs-identity-and-zero-trust-spend`

- Why continue: primary SEC filing evidence supports a traceable zero-trust /
  identity security research case.
- Research score band: `62 / 79 / 97`; not a price target.
- Next evidence: add customer-spend or platform consolidation counter-evidence.
- Retirement trigger: park if filings and management commentary do not support
  identity/zero-trust demand beyond generic cybersecurity demand.

### PANW / `OA-11-03-panw-security-platform-consolidation`

- Why continue: primary SEC filing evidence supports a platform/security
  consolidation research case.
- Research score band: `63 / 80 / 98`; not a price target.
- Next evidence: add explicit management quote or customer/peer evidence for
  platform consolidation.
- Retirement trigger: park if consolidation evidence is generic marketing rather
  than observable financial or operating disclosure.

### ANET / `OA-12-02-anet-policy-driven-china-supply-chains`

- Why continue: primary SEC filing evidence supports a traceable data-center /
  supply-chain research case, but China/policy evidence needs stronger
  authority support.
- Research score band: `63 / 80 / 98`; not a price target.
- Next evidence: add workflow-verified policy/supply-chain authority source and
  contradiction route.
- Retirement trigger: park if China/policy exposure remains candidate-source
  only.

### PLTR / `OA-12-03-pltr-source-system-gaps-to-enable-next`

- Why continue: primary SEC filing evidence supports a traceable platform /
  software / AI research case.
- Research score band: `64 / 81 / 99`; not a price target.
- Next evidence: add exact customer/source-system evidence and a counter-route
  for customer concentration or deployment friction.
- Retirement trigger: park if the thesis stays at generic AI/platform language.

## User-Facing Decision Prompt

Choose one next sprint theme:

1. Power and data-center infrastructure.
2. Cybersecurity platform/identity consolidation.
3. Supply-chain and policy exposure.
4. Contractor/distribution rollups.
5. Source-system/customer evidence.

The correct next step is choosing a research sprint, not making an investment
decision.
