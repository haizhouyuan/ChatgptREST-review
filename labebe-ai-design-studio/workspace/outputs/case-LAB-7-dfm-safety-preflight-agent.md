# Labebe Demo Artifact - LAB-7

- Timestamp UTC: 2026-04-25T17:11:30+00:00
- Agent: dfm-safety-preflight-agent
- Paperclip issue: LAB-7
- Issue title: EPIC 7 - DFM / Safety / Cost Preflight
- Issue status before run: in_review
- Source labels: demo_sample, demo_policy
- Human review required: true for strategy/safety/cost/external actions
- Output status: draft/demo

## DFM / Safety / Cost Preflight

| Area | Preliminary concern | Engineering question | Gate |
| --- | --- | --- | --- |
| Tipping | child movement and side loading | what base width and ballast are required? | human engineering review |
| Pinch | fold hinge and latch | what finger-clearance standard applies? | human engineering review |
| Small parts | knobs, caps, accessories | which removable parts need size checks? | human engineering review |
| Cost | hinge, latch, packaging | what BOM delta is acceptable? | finance and sourcing review |

## BOM Assumption

- Preliminary only: wood/plastic panels, hinge/latch set, rail hardware, packaging insert.
- No certification, compliance, production, or cost claim is made.

## Stop / Go Preflight

| Use case | Gate result | Allowed next action |
| --- | --- | --- |
| Internal boss demo | Go with visible caveats | Show concept, risks, and next evidence ask |
| Prototype exploration | Conditional go | Require human engineering review before build |
| External marketing | Stop | Do not publish safety, age, certification, cost, or launch claims |
| Certification language | Stop | Use only after certification source is available |

## Risk Register

| Risk | Severity | Evidence state | Decision | Owner |
| --- | --- | --- | --- | --- |
| Tipping | High | no physical test data | block safety claim | Engineering |
| Pinch point | High | fold hinge is conceptual | require hinge and clearance review | DFM |
| Small parts | Medium | accessories may be removable | require size and age-grade check | Safety |
| Cleanability | Medium | geometry is only a concept | require cleaning test | Product |
| Cost | Unknown | no BOM quote | block margin and price claims | Finance / Sourcing |

## Blocked Claim Demo

Input temptation: "Can we say this is certified safe and proven in market?"

System response: Blocked. No certification source exists, demo samples cannot prove demand, and human safety review is required.
## Guardrails

- Source labels used: demo_sample, demo_policy, user_provided_source, verified_fact.
- No real external accounts, ad platforms, marketplaces, or email systems are accessed.
- Safety, DFM, cost, compliance, launch, and revenue claims remain human-review gates.
