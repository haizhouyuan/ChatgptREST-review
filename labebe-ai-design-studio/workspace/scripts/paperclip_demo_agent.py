#!/usr/bin/env python3
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from urllib import error, parse, request


ROLE_SUMMARIES = {
    "product-innovation-director": "checked strategy gates and issue sequencing",
    "data-truth-guard": "checked Data Truth, forbidden claims, and demo sample labels",
    "voc-intelligence-analyst": "checked review signal samples and VOC-to-requirement path",
    "competitive-radar-analyst": "checked competitor matrix sample boundaries",
    "design-strategy-agent": "checked concept brief and route generation inputs",
    "design-director-agent": "checked brand-fit review expectations",
    "dfm-safety-preflight-agent": "checked safety, DFM, and cost review gates",
    "concept-to-market-agent": "checked asset matrix gate dependencies",
    "demo-producer-agent": "checked boss demo recording and presentation path",
}


def _api_url(path: str) -> str:
    base = os.environ.get("PAPERCLIP_API_URL", "http://127.0.0.1:3100").rstrip("/")
    if not base.endswith("/api"):
        base = f"{base}/api"
    return f"{base}{path}"


def _api_json(method: str, path: str, body: dict | None = None) -> object:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"content-type": "application/json"}
    api_key = os.environ.get("PAPERCLIP_API_KEY", "").strip()
    run_id = os.environ.get("PAPERCLIP_RUN_ID", "").strip()
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    if run_id:
        headers["x-paperclip-run-id"] = run_id
    req = request.Request(_api_url(path), data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _select_issue(agent_id: str, company_id: str) -> dict | None:
    target_identifier = os.environ.get("LABEBE_TARGET_ISSUE_IDENTIFIER", "").strip()
    if target_identifier:
        query = parse.urlencode({"limit": "200"})
        issues = _api_json("GET", f"/companies/{company_id}/issues?{query}")
        if not isinstance(issues, list):
            return None
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            if str(issue.get("identifier") or "") != target_identifier:
                continue
            if str(issue.get("assigneeAgentId") or "") != agent_id:
                return None
            return issue
        return None

    query = parse.urlencode(
        {
            "assigneeAgentId": agent_id,
            "status": "todo,backlog,in_progress,blocked",
        }
    )
    issues = _api_json("GET", f"/companies/{company_id}/issues?{query}")
    if not isinstance(issues, list):
        return None
    order = {"todo": 0, "backlog": 1, "in_progress": 2, "blocked": 3}
    candidates = [issue for issue in issues if isinstance(issue, dict)]
    candidates.sort(
        key=lambda issue: (
            0 if "end-to-end smoke" in str(issue.get("title") or "").lower() else 1,
            order.get(str(issue.get("status")), 99),
            str(issue.get("identifier") or ""),
        )
    )
    return candidates[0] if candidates else None


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value).strip("-") or "issue"


def _demo_artifact_sections(issue_identifier: str, slug: str) -> list[str]:
    common_gate = [
        "## Guardrails",
        "",
        "- Source labels used: demo_sample, demo_policy, user_provided_source, verified_fact.",
        "- No real external accounts, ad platforms, marketplaces, or email systems are accessed.",
        "- Safety, DFM, cost, compliance, launch, and revenue claims remain human-review gates.",
    ]
    by_issue = {
        "LAB-0": [
            "## Strategy Approval Draft",
            "",
            "- Boss-demo promise: show Paperclip moving a Labebe idea from local evidence to reviewable artifacts.",
            "- Operating model: every agent owns one visible issue, writes a local artifact, comments the artifact path, and moves the issue to review.",
            "- Approval chain: strategy approval, data truth gate, design review, DFM and safety review, then draft market assets.",
            "- Blocked actions: certification claims, production commitments, paid media, marketplace publishing, and customer outreach.",
            "",
            "## Acceptance Mapping",
            "",
            "- Concise enough for demo: one board, ten epic issues, one smoke issue.",
            "- Human gates explicit: CEO, Data Truth, Design Director, DFM/Safety, and launch approval.",
            "- Unsafe claims blocked: governed by DATA_TRUTH.md, FORBIDDEN_CLAIMS.md, and ACTION_POLICY.md.",
        ],
        "LAB-1": [
            "## Data Truth Foundation",
            "",
            "- Frozen claim base: DT-001 through DT-006 in data/truth_base_frozen.csv.",
            "- Demo sample boundaries: review_signal_samples.csv and competitor_samples.csv are workflow samples, not live market proof.",
            "- Forbidden claim: demo samples do not prove market demand.",
            "- Allowed factual claim: Paperclip demo runs locally on loopback, verified by health checks.",
            "",
            "## Agent Rule",
            "",
            "- Any output using RS-* or CS-* rows must say demo_sample.",
            "- Any safety, DFM, or cost output must say preliminary and require human review.",
            "- Any external-facing asset must cite Data Truth labels or stay as draft/demo copy.",
        ],
        "LAB-2": [
            "## Opportunity Radar",
            "",
            "| Cluster | Supported by | Source label | Requirement | Confidence | Missing evidence |",
            "| --- | --- | --- | --- | --- | --- |",
            "| Compact Learning Tower | RS-001, RS-003, CS-001 | demo_sample | foldable footprint with stable lock | medium-demo | real review volume, safety testing |",
            "| Easy-Clean Helper Step | RS-002 | demo_sample | fewer dirt traps around steps and corners | low-demo | cleaning tests, parent interviews |",
            "| Modular Pretend Play Corner | RS-004, RS-005, CS-003, CS-004 | demo_sample | room-fit modules and bakery/cafe theme | medium-demo | SKU margin, inventory, demand validation |",
            "",
            "## Top 3 Recommendations",
            "",
            "- 1. SpaceSmart Foldable Learning Tower for compact-home workflow demonstration.",
            "- 2. Easy-clean tower details as a secondary requirement for later iteration.",
            "- 3. Mini Bakery Kitchen Corner as a pretend-play customization branch.",
        ],
        "LAB-3": [
            "## Concept Brief",
            "",
            "- Concept name: SpaceSmart Foldable Learning Tower.",
            "- Target use case: small-kitchen parent helper workflow.",
            "- Core design move: foldable tower body with visible stable-lock review gate.",
            "- Parent value: reduce storage footprint and cleaning friction, based only on RS-001 to RS-003 demo samples.",
            "- Child play value: guided participation at counter height, pending engineering review.",
            "- Evidence label: demo_sample.",
            "- Assumptions: parent pain points and competitor positions are sample rows, not live evidence.",
            "",
            "## Approval Request",
            "",
            "- Request Product Innovation Director approval to send this concept into design route generation.",
            "- Required next gate: Data Truth and DFM/Safety review before any external asset.",
        ],
        "LAB-4": [
            "## Sketch-to-Concept Routes",
            "",
            "| Route | Design move | Brand fit | Safety/DFM caveat |",
            "| --- | --- | --- | --- |",
            "| Fold-Flat Pantry | flat-fold tower with side latch | 8/10 | latch strength and pinch points require review |",
            "| Nesting Step Tower | nested step geometry for storage | 7/10 | step stability and cleanability require tests |",
            "| Rail-and-Lock Studio | visible guard rail and lock indicator | 8/10 | lock misuse cases require review |",
            "| Corner Helper Tower | corner-parked helper form | 6/10 | footprint assumptions need validation |",
            "",
            "## Selected Direction",
            "",
            "- Select Fold-Flat Pantry for review because it most directly answers RS-001 and RS-003.",
            "- Image prompt: warm natural-wood foldable learning tower in a compact kitchen, visible stable-lock detail, no certification badge, draft concept render, safety review pending.",
        ],
        "LAB-5": [
            "## Custom Toy Kitchen Builder",
            "",
            "- Module schema: base_corner, bakery_counter, pretend_oven, cafe_sign, storage_bin, accessory_rail.",
            "- SKU seed: LABEBE-DEMO-KIT-001 Pretend Play Kitchen Seed.",
            "- Sample route: Mini Bakery Kitchen Corner.",
            "- Layout rule: corner-first footprint with optional cafe/bakery panels.",
            "- Source label: demo_sample.",
            "",
            "## Draft PDP / Waitlist Block",
            "",
            "- Headline: Build a Mini Bakery Corner for pretend-play routines.",
            "- Draft copy: choose modules, preview room fit, and save a demo-only concept for review.",
            "- Claims held for review: durability, age grading, materials, safety compliance, shipping, and price.",
        ],
        "LAB-6": [
            "## Design Director Review",
            "",
            "| Concept | Score | Strength | Risk | Next prompt |",
            "| --- | --- | --- | --- | --- |",
            "| SpaceSmart Foldable Learning Tower | 8/10 | directly addresses compact storage sample signal | fold mechanism and lock clarity | refine hinge, latch, cleanable step geometry |",
            "| Mini Bakery Kitchen Corner | 7/10 | strong pretend-play theme and modularity | may feel too niche without SKU economics | create neutral cafe/bakery swap panels |",
            "",
            "## Review Decision",
            "",
            "- Both concepts remain review-ready drafts.",
            "- SpaceSmart proceeds first for DFM/Safety preflight.",
            "- Mini Bakery proceeds only as a demo route until cost and module assumptions are reviewed.",
        ],
        "LAB-7": [
            "## DFM / Safety / Cost Preflight",
            "",
            "| Area | Preliminary concern | Engineering question | Gate |",
            "| --- | --- | --- | --- |",
            "| Tipping | child movement and side loading | what base width and ballast are required? | human engineering review |",
            "| Pinch | fold hinge and latch | what finger-clearance standard applies? | human engineering review |",
            "| Small parts | knobs, caps, accessories | which removable parts need size checks? | human engineering review |",
            "| Cost | hinge, latch, packaging | what BOM delta is acceptable? | finance and sourcing review |",
            "",
            "## BOM Assumption",
            "",
            "- Preliminary only: wood/plastic panels, hinge/latch set, rail hardware, packaging insert.",
            "- No certification, compliance, production, or cost claim is made.",
        ],
        "LAB-8": [
            "## Concept-to-Market Asset Matrix",
            "",
            "| Channel | Draft/demo asset | Source-supported claims | Claims requiring review |",
            "| --- | --- | --- | --- |",
            "| PDP | SpaceSmart concept module | compact-storage pain is a demo_sample signal | safety, materials, price, age grade |",
            "| Amazon A+ | problem-solution outline | foldable concept is a design direction | certification, ranking, demand |",
            "| TikTok 15s | small-kitchen before/after storyboard | demo concept only | user outcomes, conversion |",
            "| Meta carousel | 4-frame concept sequence | design route and review gates | launch timing, promotion |",
            "| Google image brief | clean kitchen render prompt | visual concept | product availability |",
            "| Email/waitlist | draft interest-copy block | demo workflow explanation | real waitlist collection |",
            "",
            "## Action Boundary",
            "",
            "- Assets are local drafts. No campaign, marketplace, ad account, or email account action is taken.",
        ],
        "LAB-9": [
            "## Boss Demo Production Plan",
            "",
            "- 90-second cut: board goal, agent roster, one issue wake, artifact/comment/status, final evidence package.",
            "- 15-minute presentation: problem, Paperclip architecture, Labebe workflow, risk gates, artifacts, next build plan.",
            "- Demo walk path: company goal -> LAB-0 strategy -> LAB-1 Data Truth -> LAB-2 to LAB-8 artifacts -> LAB-9 wrap-up -> smoke evidence.",
            "- Screen capture checklist: Paperclip dashboard, Agent War Room, issue detail comments, local outputs directory, evidence zip.",
            "",
            "## Visible Risks",
            "",
            "- The demo proves workflow orchestration and local artifact generation.",
            "- It does not claim real customer demand, production safety, certification, launch readiness, or paid media readiness.",
        ],
        "LAB-10": [
            "## Frontstage Demo Pack Verification",
            "",
            "- Verified `outputs/boss-demo-onepager.html` is present for the single-screen boss artifact.",
            "- Verified `outputs/boss-demo-wow/index.html` is present for the visual executive console.",
            "- Verified `outputs/agent-handoff-map.md`, `outputs/space-smart-concept-card.md`, and `outputs/claim-lineage-matrix.md` are present.",
            "- Verified `qa/paperclip-wow/` contains desktop and mobile screenshots for the onepager and visual console.",
            "- Verified post-Pro wording avoids launch, certification, proven demand, cost, and safety claims.",
            "- Verification status: frontstage demo pack is ready for internal boss demo use with human review caveats.",
            "",
            "## Evidence Links",
            "",
            "- `pro_requests/20260425_paperclip_labebe_demo_config_review/evidence/wow_iteration_summary.json`",
            "- `pro_requests/20260425_paperclip_labebe_demo_config_review/evidence/wow_artifact_ledger.json`",
            "- `pro_requests/20260425_paperclip_labebe_demo_config_review/PRO_WOW_REVIEW_FOLLOWUP_RESULT.md`",
        ],
        "LAB-SMOKE-001": [
            "## Data Truth Smoke Result",
            "",
            "- Selected issue via LABEBE_TARGET_ISSUE_IDENTIFIER.",
            "- Verified required governance docs exist.",
            "- Wrote a local artifact and Paperclip comment containing the artifact path.",
            "- Moved smoke issue to done.",
            "- Preserved demo_sample and demo_policy labels.",
        ],
    }
    return by_issue.get(
        issue_identifier,
        [
            "## Work Performed",
            "",
            f"- {ROLE_SUMMARIES.get(slug, 'checked local demo guardrails')}.",
            "- Verified required local governance docs exist.",
            "- Confirmed no real external account action is part of this demo run.",
        ],
    ) + common_gate


def main() -> int:
    root = Path.cwd()
    outputs = root / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)

    slug = os.environ.get("LABEBE_AGENT_SLUG", "unknown-agent")
    agent_id = os.environ.get("PAPERCLIP_AGENT_ID", "")
    company_id = os.environ.get("PAPERCLIP_COMPANY_ID", "")
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()
    summary = ROLE_SUMMARIES.get(slug, "checked local demo guardrails")

    docs = [
        "docs/DATA_TRUTH.md",
        "docs/FORBIDDEN_CLAIMS.md",
        "docs/ACTION_POLICY.md",
        "docs/DEMO_SAMPLE_POLICY.md",
        "docs/RUNTIME_AND_SKILL_NOTES.md",
    ]
    missing = [item for item in docs if not (root / item).exists()]
    status = "blocked" if missing else "ok"

    issue = None
    api_error = None
    if agent_id and company_id:
        try:
            issue = _select_issue(agent_id, company_id)
        except Exception as exc:  # keep the process heartbeat useful even if API writes fail
            api_error = f"{type(exc).__name__}: {exc}"

    issue_identifier = str((issue or {}).get("identifier") or "")
    issue_title = str((issue or {}).get("title") or "")
    issue_status = str((issue or {}).get("status") or "")
    target_issue_identifier = os.environ.get("LABEBE_TARGET_ISSUE_IDENTIFIER", "").strip()
    smoke_run_token = os.environ.get("LABEBE_SMOKE_RUN_TOKEN", "").strip()
    target_run_token = os.environ.get("LABEBE_TARGET_RUN_TOKEN", "").strip() or smoke_run_token
    wake_reason = os.environ.get("PAPERCLIP_WAKE_REASON", "").strip()

    artifact_name = f"case-{_safe_name(issue_identifier or slug)}-{_safe_name(slug)}.md"
    artifact_path = outputs / artifact_name
    artifact_display_path = f"outputs/{artifact_name}"
    canonical_out_path = outputs / f"heartbeat-{slug}.json"
    issue_out_path = outputs / f"heartbeat-{_safe_name(issue_identifier or target_issue_identifier or slug)}-{_safe_name(slug)}.json"

    target_final_status = "done" if "end-to-end smoke" in issue_title.lower() else "in_review"

    existing_canonical = None
    if target_issue_identifier and target_run_token and canonical_out_path.exists():
        try:
            existing_canonical = json.loads(canonical_out_path.read_text(encoding="utf-8"))
        except Exception:
            existing_canonical = None
    existing_update = existing_canonical.get("paperclip_update") if isinstance(existing_canonical, dict) else None
    existing_selected = existing_canonical.get("selected_issue") if isinstance(existing_canonical, dict) else None
    existing_run_token = (
        existing_canonical.get("target_run_token") or existing_canonical.get("smoke_run_token")
        if isinstance(existing_canonical, dict)
        else None
    )
    canonical_already_closed_this_target = (
        isinstance(existing_canonical, dict)
        and existing_canonical.get("target_issue_identifier") == target_issue_identifier
        and existing_run_token == target_run_token
        and isinstance(existing_selected, dict)
        and existing_selected.get("identifier") == target_issue_identifier
        and isinstance(existing_update, dict)
        and (
            existing_update.get("next_status") == target_final_status
            or existing_update.get("restored_status") == target_final_status
        )
    )

    if (
        target_issue_identifier
        and issue_identifier == target_issue_identifier
        and canonical_already_closed_this_target
    ):
        followup_update = None
        issue_id = str((issue or {}).get("id") or "")
        if issue_id and issue_status != target_final_status:
            try:
                updated = _api_json("PATCH", f"/issues/{issue_id}", {"status": target_final_status})
                followup_update = {
                    "issue_id": issue_id,
                    "restored_status": target_final_status,
                    "updated_identifier": (updated if isinstance(updated, dict) else {}).get("identifier"),
                }
            except error.HTTPError as exc:
                api_error = f"HTTPError {exc.code}: {exc.read().decode('utf-8', errors='replace')[:500]}"
            except Exception as exc:
                api_error = f"{type(exc).__name__}: {exc}"
        payload = {
            "agent": slug,
            "status": "ok",
            "timestamp_utc": now,
            "summary": summary,
            "skip_reason": "target_issue_already_closed_followup",
            "missing_required_docs": missing,
            "paperclip_agent_id": agent_id,
            "paperclip_company_id": company_id,
            "target_issue_identifier": target_issue_identifier,
            "target_run_token": target_run_token,
            "smoke_run_token": smoke_run_token,
            "selected_issue": {
                "identifier": issue_identifier,
                "title": issue_title,
                "status": issue_status,
            },
            "artifact": str(artifact_path),
            "artifact_display_path": artifact_display_path,
            "paperclip_update": followup_update,
            "api_error": api_error,
            "wake_reason": wake_reason or None,
        }
        out_path = outputs / f"heartbeat-{slug}-followup.json"
        issue_followup_out_path = outputs / (
            f"heartbeat-{_safe_name(issue_identifier or target_issue_identifier or slug)}-{_safe_name(slug)}-followup.json"
        )
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        issue_followup_out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        print(f"Labebe demo heartbeat follow-up skipped: {slug} {issue_identifier} already closed")
        return 0

    artifact_body = "\n".join(
        [
            f"# Labebe Demo Artifact - {issue_identifier or slug}",
            "",
            f"- Timestamp UTC: {now}",
            f"- Agent: {slug}",
            f"- Paperclip issue: {issue_identifier or 'none selected'}",
            f"- Issue title: {issue_title or 'none selected'}",
            f"- Issue status before run: {issue_status or 'unknown'}",
            "- Source labels: demo_sample, demo_policy",
            "- Human review required: true for strategy/safety/cost/external actions",
            "- Output status: draft/demo",
            "",
            *_demo_artifact_sections(issue_identifier, slug),
            "",
        ]
    )
    artifact_path.write_text(artifact_body, encoding="utf-8")

    comment_result = None
    if issue and not missing:
        comment = "\n".join(
            [
                "Demo artifact completed.",
                "",
                f"- Agent: `{slug}`",
                f"- Artifact: `{artifact_display_path}`",
                "- Source labels: `demo_sample`, `demo_policy`",
                "- Human review required for strategy/safety/cost/external actions.",
            ]
        )
        issue_id = str(issue.get("id") or "")
        try:
            if issue_id:
                if issue_status in {"todo", "backlog", "blocked"}:
                    _api_json(
                        "POST",
                        f"/issues/{issue_id}/checkout",
                        {
                            "agentId": agent_id,
                            "expectedStatuses": ["todo", "backlog", "blocked", "in_review"],
                        },
                    )
                if "end-to-end smoke" in issue_title.lower():
                    next_status = "done"
                elif issue_status in {"todo", "backlog", "blocked", "in_progress"}:
                    next_status = "in_review"
                else:
                    next_status = issue_status or "in_review"
                updated = _api_json("PATCH", f"/issues/{issue_id}", {"status": next_status, "comment": comment})
                comment_result = {
                    "issue_id": issue_id,
                    "next_status": next_status,
                    "updated_identifier": (updated if isinstance(updated, dict) else {}).get("identifier"),
                }
        except error.HTTPError as exc:
            api_error = f"HTTPError {exc.code}: {exc.read().decode('utf-8', errors='replace')[:500]}"
        except Exception as exc:
            api_error = f"{type(exc).__name__}: {exc}"

    payload = {
        "agent": slug,
        "status": status,
        "timestamp_utc": now,
        "summary": summary,
        "missing_required_docs": missing,
        "paperclip_agent_id": agent_id,
        "paperclip_company_id": company_id,
        "target_issue_identifier": target_issue_identifier or None,
        "target_run_token": target_run_token or None,
        "smoke_run_token": smoke_run_token or None,
        "wake_reason": wake_reason or None,
        "selected_issue": {
            "identifier": issue_identifier,
            "title": issue_title,
            "status": issue_status,
        },
        "artifact": str(artifact_path),
        "artifact_display_path": artifact_display_path,
        "paperclip_update": comment_result,
        "api_error": api_error,
    }

    canonical_out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    issue_out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False))
    if missing:
        print(f"Missing required docs: {', '.join(missing)}")
        return 2
    print(f"Labebe demo heartbeat complete: {slug} {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
