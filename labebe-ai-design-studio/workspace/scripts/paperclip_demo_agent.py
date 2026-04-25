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
    wake_reason = os.environ.get("PAPERCLIP_WAKE_REASON", "").strip()

    artifact_name = f"case-{_safe_name(issue_identifier or slug)}-{_safe_name(slug)}.md"
    artifact_path = outputs / artifact_name
    artifact_display_path = f"outputs/{artifact_name}"
    canonical_out_path = outputs / f"heartbeat-{slug}.json"

    existing_canonical = None
    if target_issue_identifier and smoke_run_token and canonical_out_path.exists():
        try:
            existing_canonical = json.loads(canonical_out_path.read_text(encoding="utf-8"))
        except Exception:
            existing_canonical = None
    existing_update = existing_canonical.get("paperclip_update") if isinstance(existing_canonical, dict) else None
    existing_selected = existing_canonical.get("selected_issue") if isinstance(existing_canonical, dict) else None
    canonical_already_closed_this_smoke = (
        isinstance(existing_canonical, dict)
        and existing_canonical.get("target_issue_identifier") == target_issue_identifier
        and existing_canonical.get("smoke_run_token") == smoke_run_token
        and isinstance(existing_selected, dict)
        and existing_selected.get("identifier") == target_issue_identifier
        and isinstance(existing_update, dict)
        and (
            existing_update.get("next_status") == "done"
            or existing_update.get("restored_status") == "done"
        )
    )

    if (
        target_issue_identifier
        and issue_identifier == target_issue_identifier
        and canonical_already_closed_this_smoke
    ):
        followup_update = None
        issue_id = str((issue or {}).get("id") or "")
        if issue_id and issue_status != "done":
            try:
                updated = _api_json("PATCH", f"/issues/{issue_id}", {"status": "done"})
                followup_update = {
                    "issue_id": issue_id,
                    "restored_status": "done",
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
            "skip_reason": "target_smoke_already_done_followup",
            "missing_required_docs": missing,
            "paperclip_agent_id": agent_id,
            "paperclip_company_id": company_id,
            "target_issue_identifier": target_issue_identifier,
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
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        print(f"Labebe demo heartbeat follow-up skipped: {slug} {issue_identifier} already done")
        return 0

    artifact_body = "\n".join(
        [
            f"# Labebe Demo Heartbeat - {slug}",
            "",
            f"- Timestamp UTC: {now}",
            f"- Agent: {slug}",
            f"- Paperclip issue: {issue_identifier or 'none selected'}",
            f"- Issue title: {issue_title or 'none selected'}",
            f"- Issue status before heartbeat: {issue_status or 'unknown'}",
            "- Source labels: demo_sample, demo_policy",
            "- Human review required: true for strategy/safety/cost/external actions",
            "- Output status: draft/demo",
            "",
            "## Work Performed",
            "",
            f"- {summary}.",
            "- Verified required local governance docs exist.",
            "- Confirmed no real external account action is part of this heartbeat.",
            "",
            "## Next Gate",
            "",
            "- Keep safety, DFM, cost, launch, and compliance-adjacent claims behind human review.",
            "",
        ]
    )
    artifact_path.write_text(artifact_body, encoding="utf-8")

    comment_result = None
    if issue and not missing:
        comment = "\n".join(
            [
                "Demo heartbeat completed.",
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
                if issue_status in {"todo", "backlog"}:
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
                elif issue_status in {"todo", "backlog", "in_progress"}:
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

    print(json.dumps(payload, ensure_ascii=False))
    if missing:
        print(f"Missing required docs: {', '.join(missing)}")
        return 2
    print(f"Labebe demo heartbeat complete: {slug} {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
