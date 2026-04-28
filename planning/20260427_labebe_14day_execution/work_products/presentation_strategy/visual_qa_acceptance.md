# Visual QA Acceptance Plan

Generated: 2026-04-27
Owner: Presentation Strategy Worker
Applies to: Labebe DTC walkthrough, Boss Gallery, screenshots, and videos

## Principle

Technical load success is not enough. A page, screenshot, or video is not
accepted unless it looks intentional on desktop and phone, stays claim-safe, and
has screenshot evidence. Vision model review can assist, but final acceptance
requires human/main-controller judgment.

This plan combines:

- `work_products/runtime_qa_templates/browser_harness_p0_contract.md`
- `work_products/runtime_qa_templates/visual_ai_slop_checklist.md`
- `work_products/runtime_qa_templates/design_review_report_template.md`
- `/vol1/1000/projects/gstack/qa/SKILL.md`
- `/vol1/1000/projects/gstack/design-review/SKILL.md`
- `/vol1/1000/projects/gstack/review/design-checklist.md`

## Surface Separation Gate

| Surface | Pass condition | Instant fail |
| --- | --- | --- |
| Labebe DTC website | Pure consumer commerce: product, room, age, gift, PDP, cart/bundle direction. | Paperclip, AI Studio, internal Claim Gate, runtime proof, or technical demo language appears in the shopper surface. |
| Boss Gallery | Internal AI business result gallery: outcome first, controls second. | Consumer shopping path is confused with the internal AI demo or fake production claims. |
| Video / screenshots | Presentation artifacts clearly label prototype/evidence status. | Video captions or overlays add unsupported claims not present in approved docs. |

## Required Viewports

| Viewport | Purpose | Minimum evidence |
| --- | --- | --- |
| 390x844 mobile | Phone video framing and top-screen composition. | Header, hero, primary CTA, first interaction. |
| 390x1200 or CDP full-page mobile | Scroll QA and overflow check. | Full-page screenshot for home/PDP/gallery. |
| 768x1024 tablet | Breakpoint sanity when time allows. | One homepage/gallery screenshot. |
| 1440x1100 desktop | Current QA standard. | Full-page screenshot for each target route. |
| 1920x1080 video | Final desktop recording. | Main walkthrough export. |
| 1080x1920 or 1080x1350 video | Mobile/social cutdown. | Phone-readable cut. |

## Browser Harness P0 Checks

For each accepted page or video source route:

| Check | Pass standard |
| --- | --- |
| HTTP/page load | 200 or expected local route fallback; no blank screen. |
| Console | No uncaught errors affecting page render or interaction. |
| Network/media | Required images/video/posters load. Broken media is high severity. |
| Horizontal overflow | `document.documentElement.scrollWidth <= window.innerWidth + 1`. |
| Nonblank pixels | Screenshot has real content distribution, not black/white/transparent failure. |
| Text overflow | No clipped button labels, card titles, headings, or captions. |
| Overlap | No incoherent overlap between navigation, media, copy, controls, or cards. |
| Touch targets | Primary mobile controls are at least 44px high/wide. |
| Reduced motion | Site respects reduced-motion preference where animation exists. |

Browser Harness is evidence support only. It does not decide design direction,
publish, edit code, or declare boss-ready without human acceptance.

## Human Design Review Gates

Use the gstack design-review stance: rendered output first, screenshots as
evidence, specific fixes over vague opinions.

### DTC website

Required reviewer questions:

1. What makes this specifically Labebe?
2. Which shopper mission does this page serve?
3. What product fact changes this layout?
4. Which claim is blocked or downgraded?
5. Would a parent understand the page by scanning headlines only?
6. Does mobile feel designed, not merely stacked?

Pass standards:

- first viewport shows product value, not generic atmosphere;
- shopper routes are legible: room, age, gift, play world;
- PDP makes image, price, supported review count, badges, and action easy to compare;
- no fake ratings, awards, certifications, testimonials, Amazon rank, or safety claims;
- body text is readable on mobile without zoom;
- primary CTA is visually dominant but not oversized or clipped.

### Boss Gallery

Required reviewer questions:

1. Does the first screen show a business outcome before explaining tools?
2. Can each Demo A-F card answer "what did AI produce for Labebe?"
3. Can each impressive output be traced to evidence and review status?
4. Is Claim Gate visually memorable?
5. Does the gallery avoid generic SaaS dashboard language and layout?
6. Would a decision maker know the next decision: prototype exploration, not production launch?

Pass standards:

- hero video/poster is visible above the fold on desktop;
- mobile headline and video are readable without horizontal scroll;
- Claim Gate blocks unsafe/unsupported claims in plain language;
- evidence drawer is available but not the hero;
- no fake ROI, conversion lift, safety certification, demand, cost, or availability claim.

## AI-Slop Rejection Signals

Any one of these requires revision or explicit waiver:

- page could become any children's toy brand after logo swap;
- hero image is atmospheric but does not show actual product value;
- product cards look like stock marketplace filler;
- typography scale feels arbitrary or template-generated;
- mobile page feels like a compressed desktop screenshot;
- sections are decorative cards rather than decision modules;
- copy explains the website instead of helping a shopper or decision maker;
- Boss Gallery looks like a generic SaaS dashboard;
- contact sheet is used as a video cover;
- decorative blobs, fake metrics, generic purple gradients, or icon-in-circle grids carry the design.

## Vision Model Review

Vision model review is a second pair of eyes, not final approval.

Allowed uses:

- identify likely overlap, clipping, blank areas, broken media, tiny text;
- critique AI-template risk;
- compare desktop and mobile composition;
- flag unreadable video frames or captions.

Forbidden uses:

- make factual product claims;
- approve unsupported safety or marketplace claims;
- decide final acceptance without human/main-controller review.

Suggested prompt for screenshot review:

```text
Review this Labebe presentation screenshot as a senior product designer.
Check: brand specificity, hierarchy, readable text, product visibility,
mobile composition, AI-template risk, overlap/clipping, broken media,
and unsupported claims. Return pass/fail, severity, and exact visible evidence.
Do not infer product facts beyond what is visible.
```

## Severity And Ship Rules

Use the gstack QA taxonomy:

| Severity | Meaning | Ship rule |
| --- | --- | --- |
| Critical | Core page/video unusable, blank, broken, or materially misleading. | Cannot ship. |
| High | Major visual/claim problem with no reasonable workaround. | Cannot ship boss-facing package. |
| Medium | Noticeable issue with workaround or known gap. | Can ship only with logged fix owner and caveat. |
| Low | Cosmetic polish issue. | Can ship if not part of the first impression. |

Minimum acceptance:

- zero critical issues;
- zero unresolved high issues;
- all medium issues listed in closeout;
- screenshot evidence for every accepted route and key video frame;
- DTC and Boss Gallery separation explicitly checked.

## Evidence Naming

Use stable, descriptive file names:

| Evidence | Example |
| --- | --- |
| DTC desktop home | `dtc-home-desktop-1440.png` |
| DTC mobile home | `dtc-home-mobile-390.png` |
| DTC PDP desktop | `dtc-pdp-unicorn-desktop-1440.png` |
| DTC PDP mobile | `dtc-pdp-unicorn-mobile-390.png` |
| Boss desktop hero | `boss-gallery-hero-desktop-1440.png` |
| Boss mobile hero | `boss-gallery-hero-mobile-390.png` |
| Boss Claim Gate | `boss-gallery-claim-gate-desktop-1440.png` |
| Video keyframe | `walkthrough-keyframe-00-claim-gate.png` |
| QA report | `browser_qa_report.md` or `visual_qa_report.md` |

## Acceptance Workflow

1. Capture screenshots for all required surfaces and viewports.
2. Run browser checks: load status, console, media, overflow, nonblank pixels.
3. Run visual model review on the accepted screenshot set.
4. Human reviewer performs design-review pass using the questions above.
5. Red-circle or annotate any issue that blocks acceptance.
6. Re-capture after fixes; keep before/after evidence.
7. Write final closeout with:
   - accepted files;
   - rejected/blocked files;
   - unresolved medium/low issues;
   - exact statement that DTC and Boss Gallery remained separated.

## Final Pass Checklist

- [ ] DTC video contains no Paperclip/AI/internal workflow.
- [ ] Boss video starts with business outcome, not tool internals.
- [ ] Desktop and mobile screenshots exist for both surfaces.
- [ ] No horizontal overflow on accepted mobile captures.
- [ ] No unreadable or clipped button/card text.
- [ ] Video poster is a single compelling frame, not a contact sheet.
- [ ] Claim Gate appears in Boss Gallery and blocks unsafe claims.
- [ ] Asset rights caveats are listed where catalog, AI, or mixed media are used.
- [ ] Vision model review completed.
- [ ] Human design review completed.
- [ ] Evidence manifest or closeout links every accepted artifact.

