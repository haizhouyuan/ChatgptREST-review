# Boss Gallery Completion Plan

Generated: 2026-04-27
Owner: Presentation Strategy Worker
Scope: Paperclip / Boss Gallery AI business-result presentation only

## Purpose

Complete the internal Boss Gallery so a decision maker sees business impact
first, then governance. This is not the Labebe consumer website. It is the place
to show how AI turns Labebe product facts, VOC, and media assets into concepts,
channel assets, and approval-ready work with controls.

Core sentence:

```text
Show the outcome, then show the control.
```

## Current State

| Asset | Path | Status |
| --- | --- | --- |
| Boss Gallery v0 | `paperclip_runtime_duel/outputs/boss_gallery_v0/index.html` | Review-ready v0. |
| Existing result-first video | `paperclip_runtime_duel/outputs/labebe_wow/labebe_ai_application_wow.mp4` | Usable as hero video. |
| Video poster | `paperclip_runtime_duel/outputs/labebe_wow/labebe_ai_application_wow_poster.jpg` | Use as single cover frame. |
| Video contact sheet | `paperclip_runtime_duel/outputs/labebe_wow/labebe_ai_application_wow_contact_sheet.jpg` | Evidence only, not cover art. |
| Storyboard | `paperclip_runtime_duel/outputs/labebe_wow/storyboard.md` | Pro-aligned result-first story. |
| Runtime evidence | `paperclip_runtime_duel/outputs/evidence/` | Hashes, scorecard, secret scan, run evidence. |
| Gallery screenshots | `qa/labebe-commerce-v2/boss-gallery-desktop-cdp-v2.png`, `boss-gallery-mobile-cdp.png` | Current desktop/mobile evidence. |

Current v0 already has:

- separated internal surface;
- hero video;
- Demo A-F cards;
- one-SKU-to-channel matrix;
- Claim Gate blocked/allowed framing.

Current gaps:

- Demo A-F are cards, not complete evidence-backed detail experiences;
- each demo is now connected to existing Paperclip issue/evidence documents;
- no final 60-90 second gallery walkthrough recording;
- no visual model plus human QA closeout;
- mobile works but needs readability and hierarchy hardening before boss use.

## Required Final Package

| Deliverable | Description |
| --- | --- |
| Boss Gallery final HTML | Interactive surface with hero, Demo A-F details, matrix, Claim Gate, evidence drawer. |
| Demo detail pages or modals | Each demo shows input, output, business use, review status, evidence ID, blocked claims. |
| Boss walkthrough video | 60-90 sec result-first video for desktop and phone viewing. |
| Poster frame | One strong outcome frame, not a contact sheet. |
| Screenshot evidence set | Desktop and mobile for gallery home, demo detail, matrix, Claim Gate. |
| Evidence manifest | Maps every demo card to file paths, Paperclip issue IDs, source status, claim status. |
| QA acceptance report | Pass/fail against `visual_qa_acceptance.md`. |

## Information Architecture

### 1. Hero: Result First

Purpose: make the first screen immediately understandable.

Required elements:

- title: outcome-first, not tool-first;
- existing video as the main visual;
- one sentence: "Prototype exploration only. Claim Gate blocks unverified safety, demand, cost and production claims.";
- two actions:
  - `Watch 60s walkthrough`;
  - `Open Claim Gate`.

Do not lead with runtime aliases, logs, or internal implementation details.

### 2. Demo A-F Result Lanes

Each demo needs the same detail contract:

| Field | Meaning |
| --- | --- |
| Business question | What decision does this help Labebe make? |
| Input | Product facts, VOC, SKU, media, or source packet. |
| AI output | Concept, storyboard, matrix, channel asset, or preflight decision. |
| Human review status | Draft, needs review, blocked, approved structure, or prototype-only. |
| Evidence link | Paperclip issue ID, artifact path, screenshot path, source file. |
| Claim Gate result | Which claims were allowed, downgraded, or blocked. |
| Next production step | What must happen before external use. |

Demo lane requirements:

| Demo | Business wow | Completion requirement |
| --- | --- | --- |
| A - Design Opportunity Radar | AI finds the next product/design opportunity from portfolio and source constraints. | Show the selected opportunity, rejected alternatives, source facts, and why SpaceSmart was chosen. |
| B - VOC to New Concept | Review pain clusters become a new concept brief. | Show pain cluster, concept brief, storyboard frame, and blocked overclaims. |
| C - Sketch to Concept | Rough product idea becomes visual and feature directions. | Show before sketch/brief, generated concept board, feature cards, and review status. |
| D - Custom Toy Kitchen Builder | Configurable product directions become SKU variants or scene options. | Show configuration options, output examples, and DFM/safety pending labels. |
| E - Design Director + DFM/Safety Preflight | AI critiques brand fit, feasibility, and risk before publishing. | Show red/yellow/green decision table with exact blocked reasons. |
| F - Concept-to-Market Asset Matrix | One SKU expands into channel-specific assets. | Show PDP, Amazon A+, TikTok, Meta, Google, email, and site module drafts with source/review status. |

### 3. Claim Gate

Claim Gate must be a remembered moment, not a small compliance footnote.

Blocked claims:

- certified safe without source evidence;
- proven demand without marketplace verification;
- lower cost without cost model evidence;
- available now for concept work;
- production-ready CAD without engineering source;
- fake ratings, reviews, awards, or customer quotes.

Allowed outputs:

- prototype exploration based on local DTC facts;
- source-labeled price and review-count usage where captured;
- synthetic image/video/storyboard drafts with labels;
- channel asset plans pending brand, claim, and commerce review.

### 4. Evidence Drawer

Add a compact evidence section near the bottom or as a modal:

- Runtime Duel evidence manifest:
  `paperclip_runtime_duel/outputs/evidence/MANIFEST.md`
- Scorecard:
  `paperclip_runtime_duel/outputs/evidence/scorecard.json`
- Secret scan:
  `paperclip_runtime_duel/outputs/evidence/secret_scan.json`
- Labebe smoke:
  `paperclip_runtime_duel/outputs/evidence/labebe_final_smoke_verification.json`
- Known runtime truth wording:
  `paperclip_runtime_duel/outputs/final_boss_entry.md`

This drawer is for audit depth. The hero stays result-first.

## Walkthrough Video Plan

Target: 60-90 seconds, usable on desktop and mobile.

| Time | Shot | Message |
| --- | --- | --- |
| 0-8s | Boss Gallery hero video/poster | Start with what Labebe gets, not what the tool is. |
| 8-20s | Demo A/B detail | AI turns product facts and VOC into a concrete SpaceSmart concept. |
| 20-34s | Demo F matrix | One SKU becomes PDP, Amazon A+, TikTok, Meta, Google, email, and site assets. |
| 34-48s | Claim Gate | The system refuses unsafe, unsupported, or fake claims. |
| 48-62s | Demo E preflight | Human review and evidence gates sit before launch. |
| 62-78s | Evidence drawer | Runs, hashes, smoke proof, secret scan, and source status are available on demand. |
| 78-90s | Decision close | Approve next prototype exploration, not production launch. |

Voiceover framing:

```text
This is the internal AI application gallery, separate from the consumer store.
The point is not that AI made more content.
The point is that one Labebe product can become a governed business asset system.
Here is the concept, here are the channel drafts, and here is what the system
refuses to say until evidence exists.
```

## Mobile And Desktop Requirements

Desktop:

- first viewport must show title, video, and control statement without scrolling;
- Demo A-F cards can use a 3-column grid only if each card has unique product evidence and business role;
- evidence drawer should not dominate the hero.

Mobile:

- header label must not compete with the hero headline;
- hero headline must stay readable without horizontal scroll;
- video controls must remain reachable;
- Demo cards should become a prioritized sequence, not six equal blocks with no hierarchy;
- Claim Gate should be visible as a standalone moment within the first 2-3 scrolls after the hero.

## Completion Backlog

### P0 - Boss-ready minimum

1. Add detail views or modals for Demo A-F using the demo contract above.
2. Add evidence ID/path fields to every demo.
3. Add Claim Gate as a high-contrast, easy-to-record section.
4. Capture desktop and mobile screenshots for hero, Demo detail, matrix, and Claim Gate.
5. Record the 60-90 second walkthrough.
6. Run visual model plus human QA.

### P1 - Stronger wow

1. Add side-by-side "input -> output -> gate" animation for one SKU.
2. Add a short outcome board for SpaceSmart concept.
3. Add a channel-card preview set with labels: `Draft`, `Needs review`, `Blocked`, `Approved structure`.
4. Add direct links to the DTC prototype only as context, not as a mixed consumer/demo page.

### P2 - Operational polish

1. Add persistent evidence manifest download.
2. Add print/PDF one-pager for executives.
3. Add versioned changelog with previous demo limitations and current improvements.

## Acceptance Gates

Reject the Boss Gallery final if any of these are true:

- It looks like a generic SaaS dashboard after changing the Labebe logo.
- The hero explains Paperclip before showing the business result.
- Demo cards cannot be traced to evidence or claim status.
- The video implies production readiness, real customer validation, certified safety, market demand, or ROI.
- The Claim Gate is present but visually forgettable.
- Mobile text is too small, clipped, or arranged like a compressed desktop screen.
- The contact sheet is used as the video cover.
