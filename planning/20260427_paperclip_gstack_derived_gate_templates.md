# Paperclip Gate Templates Derived From GStack

Date: 2026-04-27

These templates convert useful GStack review patterns into Paperclip-native gates. They are intentionally plain Markdown so they can be attached to Paperclip issues, copied into org playbooks, or turned into skills later.

They do not import GStack runtime behavior.

## Gate A: CEO / Wow Review

Use before implementing:

- Labebe website design direction;
- AI Wow / Boss Gallery demos;
- Paperclip org/project creation;
- high-risk runtime architecture changes.

Required output:

```text
ceo_wow_review.md
```

Template:

```md
# CEO / Wow Review

Date:
Issue:
Owner:
Target audience:

## 1. Current State

What exists now. Include URLs, files, screenshots, known defects and previous attempts.

## 2. Actual Outcome

What business/user result this work must create.

## 3. First 30 Seconds

What the decision maker sees first, in order.

1.
2.
3.

## 4. Premise Challenge

- Is this the right problem?
- Are we solving a proxy problem?
- What happens if we do nothing?
- What assumption is weakest?

## 5. Implementation Approaches

| Approach | Summary | Effort | Risk | Reuses | Why It Might Win |
|---|---|---:|---|---|---|
| A Minimal | | | | | |
| B Strong | | | | | |
| C 10x | | | | | |

## 6. 10x Version

Describe the version that would make a decision maker say this changes what is possible.

## 7. Explicitly Out Of Scope

- 

## 8. Failure Modes

| Failure | Signal | Prevention | Recovery |
|---|---|---|---|
| Generic demo | | | |
| Unsupported claim | | | |
| Weak mobile experience | | | |
| No evidence | | | |

## 9. Acceptance Criteria

- [ ] Business/user outcome is specific.
- [ ] At least two approaches compared.
- [ ] First 30 seconds are defined.
- [ ] Weakest assumption is named.
- [ ] Evidence required before close is listed.

## Verdict

PASS / PASS_WITH_CHANGES / FAIL
```

## Gate B: Design Review

Use after a rendered UI exists.

Required output:

```text
design_review_report.md
design_baseline.json
screenshots/
```

Template:

```md
# Design Review

Date:
URL:
Issue:
Reviewer:

## 1. First Impression

The site communicates:

I notice:

The first 3 things my eye goes to:

One-word verdict:

## 2. Product / Brand Signal

- Brand/product unmistakable in first viewport: YES / NO
- Main visual anchor:
- Primary action:
- What feels generic:

## 3. Rendered Design System

| Item | Observed | Problems |
|---|---|---|
| Fonts | | |
| Colors | | |
| Heading scale | | |
| Spacing rhythm | | |
| Radius/shadow system | | |
| Motion | | |

## 4. Screenshot Set

| View | Path | Pass |
|---|---|---|
| Desktop | | |
| Tablet | | |
| Mobile | | |
| Annotated | | |

## 5. AI-Slop Check

| Pattern | Present? | Notes |
|---|---|---|
| Generic SaaS hero | | |
| 3-column feature grid | | |
| Purple/blue gradient default | | |
| Decorative blobs/orbs | | |
| Centered everything | | |
| Cards where layout should be used | | |
| Placeholder/generic copy | | |

## 6. UX Checks

| Check | Pass | Evidence |
|---|---|---|
| Mobile has no horizontal overflow | | |
| Text does not overlap | | |
| Touch targets >= 44px | | |
| CTA is clear | | |
| Navigation is understandable | | |
| Core task can be completed | | |

## 7. Scores

Design Score: A / B / C / D / F

AI-Slop Score: A / B / C / D / F

## 8. Top Fixes

1.
2.
3.
4.
5.

## Verdict

PASS / PASS_WITH_CHANGES / FAIL
```

## Gate C: Browser QA

Use before showing any website/demo URL.

Required output:

```text
browser_qa_report.md
qa_baseline.json
screenshots/
```

Template:

```md
# Browser QA

Date:
URL:
Issue:
Reviewer:

## 1. Entry URLs

| URL | HTTP | Loads Visually | Notes |
|---|---:|---|---|
| | | | |

## 2. Console Health

| Page/Action | Errors | Warnings | Notes |
|---|---:|---:|---|
| Initial load | | | |
| Navigation | | | |
| Core interaction | | | |

## 3. User Flows Tested

| Flow | Steps | Result | Screenshot |
|---|---|---|---|
| Homepage scan | | | |
| Primary navigation | | | |
| Product/PDP or demo detail | | | |
| Cart / CTA / main action | | | |
| Mobile main path | | | |

## 4. Findings

| ID | Severity | Category | Repro | Evidence | Fix |
|---|---|---|---|---|---|
| | | | | | |

## 5. Health Score

Console:
Links:
Visual:
Functional:
UX:
Performance:
Content:
Accessibility:

Final score:

## Verdict

PASS / PASS_WITH_CHANGES / FAIL
```

## Gate D: Runtime Policy Review

Use before changing MCPs, skills, CLI wrappers, browser automation, media API flows or child-runtime permissions.

Required output:

```text
runtime_policy_review.md
secret_surface_map.md
```

Template:

```md
# Runtime Policy Review

Date:
Issue:
Owner:
Runtime:

## 1. Change Summary

What changes in tools, permissions, keys, browser access, or automation behavior.

## 2. Surfaces

| Surface | Change | Risk | Mitigation |
|---|---|---|---|
| Filesystem read | | | |
| Filesystem write | | | |
| Network | | | |
| Browser cookies/session | | | |
| Secrets/API keys | | | |
| Child runtime | | | |
| Prompt/skill content | | | |

## 3. MCP / CLI / Skill Decision

Chosen shape:

- MCP:
- CLI:
- Skill:
- Service:

Reason:

## 4. Secret Handling

- Secret values appear in artifacts: YES / NO
- Redaction rule:
- Storage:
- Rotation/rollback:

## 5. Isolation

- Production lane touched: YES / NO
- Experiment lane:
- Tailscale/external exposure:
- Human approval needed:

## 6. Failure Modes

| Failure | Impact | Prevention | Recovery |
|---|---|---|---|
| 429 loop / rate limit | | | |
| Cookie/session leak | | | |
| Tool writes outside scope | | | |
| Prompt injection in skill | | | |

## Verdict

PASS / PASS_WITH_CHANGES / FAIL
```

## Gate E: Ship / Checkpoint Closeout

Use before marking a Paperclip issue done.

Required output:

```text
closeout.md
checkpoint.md
evidence_manifest.json
```

Template:

```md
# Issue Closeout

Date:
Issue:
Owner:
Status:

## 1. Acceptance Criteria Evidence

| Acceptance Criterion | Evidence | Pass |
|---|---|---|
| | | |

## 2. Artifacts Created / Changed

| Artifact | Path/URL | Purpose |
|---|---|---|
| | | |

## 3. Verification

| Check | Command/Method | Result |
|---|---|---|
| HTTP | | |
| Build/test | | |
| Screenshot QA | | |
| Video/frame QA | | |
| Claim scan | | |

## 4. Known Limitations

- 

## 5. Claims Not Proven

- 

## 6. Handoff

What the next agent needs to know:

Next recommended issue:

Resume command or URL:

## Verdict

DONE / DONE_WITH_CONCERNS / BLOCKED
```

Evidence manifest shape:

```json
{
  "issue": "",
  "status": "done_with_concerns",
  "artifacts": [
    {
      "path": "",
      "type": "markdown|screenshot|video|url|json|csv|code",
      "purpose": "",
      "created_at": ""
    }
  ],
  "claims": [
    {
      "claim": "",
      "evidence": "",
      "confidence": "high|medium|low"
    }
  ],
  "limitations": []
}
```

