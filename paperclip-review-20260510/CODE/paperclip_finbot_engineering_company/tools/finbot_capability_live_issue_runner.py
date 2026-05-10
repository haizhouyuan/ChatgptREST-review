#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


BASE = "http://127.0.0.1:3100/api"
REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO.parent
DOC_ROOT = PROJECT / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform"
PASS_STATUS = "FINBOT_ENGINEERING_CAPABILITY_PLATFORM_V1_PASS"
GENERATED_AT = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


OPS = [
    {
        "role": "engineering_implementation",
        "companyId": "470afc19-473b-4794-9191-c957d34aa330",
        "projectId": "ac80804a-2e52-4368-81a4-aece6bf30649",
        "agentId": "ede1270f-8cce-433b-bcf8-e6b313f68ff7",
        "title": "Finbot Engineering capability platform v1 implementation validation",
        "priority": "high",
        "targetStatus": "done",
        "description": f"""Validate the Finbot Engineering Capability Platform v1 implementation.

Evidence root: {DOC_ROOT}
Engineering repo implementation owner: {REPO}

No separate live Finbot Engineering company is being claimed. This Finbot Research issue is the live evidence carrier for the Engineering repo implementation only.

Required check:
- Inspect README.md, RUNLOG.md, contracts/, fixtures/capability_platform/, tools/ and tests/ in the Engineering repo.
- Inspect 00-15 deliverables under the evidence root.
- Confirm scope is governed capability_lab_v1, not investment advice, trading, broker action, production watchlist, trade signal, target-price recommendation, or native runtime/MCP/skill config mutation.
- Confirm hard validator pre-live result has no local errors and remains pending live readback until this succeeded-run evidence is attached.
- Comment must start with: Capability platform validation complete
- If accepted, include token: {PASS_STATUS}
- Use the phrase: capability platform
""",
    },
    {
        "role": "governance_boundary",
        "companyId": "f3ef00b8-3654-48b2-abda-dd9d63a7c42d",
        "projectId": "ec69c0ac-0e0a-45f7-8f26-7f638d861356",
        "agentId": "11858cbd-02dd-4f43-9d00-553189dbd1bc",
        "title": "Governance Finbot capability platform v1 boundary validation",
        "priority": "high",
        "targetStatus": "done",
        "description": f"""Validate Governance boundaries for Finbot Engineering Capability Platform v1.

Evidence root: {DOC_ROOT}
Engineering repo: {REPO}

Required check:
- Inspect 02_data_source_readiness_matrix.json, 03_connector_smoke_results.json, 06_validator_design.md, 12_governance_approval_packet.md and tools/validate_finbot_capability_platform.py.
- Confirm endpoint_alive_only and tool_callable_only are not counted as workflow_verified.
- Confirm Readwise, Zotero, Alpaca watch-only, Daloopa, Quartr and Binance risk context remain candidate_to_enable unless separately approved.
- Confirm MiniMax, DeepSeek, Tavily and Brave remain quarantined_or_no_production_use and were not called.
- Confirm no trading, no broker permissions, no investment advice, no production watchlist, no trade signal, no target-price-as-advice, no native config mutation.
- Confirm Controller & Runtime Company is only runtime lab / adapter lab; Capability Governance owns Skill/MCP/Runtime/Memory policy.
- Comment must start with: Capability platform validation complete
- If accepted, include token: {PASS_STATUS}
- Use the phrase: capability platform
""",
    },
    {
        "role": "finbot_research_handoff",
        "companyId": "470afc19-473b-4794-9191-c957d34aa330",
        "projectId": "ac80804a-2e52-4368-81a4-aece6bf30649",
        "agentId": "ede1270f-8cce-433b-bcf8-e6b313f68ff7",
        "title": "Finbot Research capability platform v1 handoff acknowledgement",
        "priority": "high",
        "targetStatus": "done",
        "description": f"""Acknowledge what Finbot Research agents may use from Finbot Engineering Capability Platform v1.

Evidence root: {DOC_ROOT}
Engineering repo: {REPO}

Required check:
- Inspect 04_skill_contracts_for_finbot_agents.md, 05_schema_extension_design.md, 08_valuation_range_research_prototype.json, 09_alert_monitoring_prototype.json, 10_decision_memo_prototype.json and 11_engineering_to_research_handoff.md.
- Confirm Research agents may consume validated contracts, schemas, runner outputs, research_estimate_range, human-review alerts and bounded decision memos only.
- Confirm this does not claim investment-readiness, production watchlist readiness, trade signal readiness, broker readiness, advice readiness, or target-price output.
- Confirm decision memo statuses are limited to continue_research / park / reject / needs_user_review.
- Comment must start with: Capability platform validation complete
- If accepted, include token: {PASS_STATUS}
- Use the phrase: capability platform
""",
    },
]


def api(method: str, path: str, payload: Any | None = None, query: dict[str, str] | None = None) -> Any:
    url = f"{BASE}/{path.lstrip('/')}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_company_issues(company_id: str) -> list[dict[str, Any]]:
    data = api("GET", f"companies/{company_id}/issues")
    if isinstance(data, dict) and isinstance(data.get("issues"), list):
        return data["issues"]
    if isinstance(data, list):
        return data
    return []


def ensure_issue(op: dict[str, str]) -> dict[str, Any]:
    for issue in list_company_issues(op["companyId"]):
        if issue.get("title") == op["title"]:
            return api("PATCH", f"issues/{issue['id']}", {
                "description": op["description"],
                "assigneeAgentId": op["agentId"],
                "priority": op["priority"],
                "status": "backlog",
            })
    return api("POST", f"companies/{op['companyId']}/issues", {
        "projectId": op["projectId"],
        "title": op["title"],
        "description": op["description"],
        "status": "backlog",
        "priority": op["priority"],
        "assigneeAgentId": op["agentId"],
    })


def wake(op: dict[str, str], issue: dict[str, Any]) -> dict[str, Any]:
    return api("POST", f"agents/{op['agentId']}/wakeup", {
        "source": "assignment",
        "triggerDetail": "manual",
        "reason": "finbot_engineering_capability_platform_v1_validation",
        "payload": {
            "issueId": issue["id"],
            "identifier": issue.get("identifier"),
            "title": issue["title"],
            "contextSource": "finbot_engineering_capability_platform_v1",
            "artifactRoot": str(DOC_ROOT),
            "engineeringRepo": str(REPO),
            "requiredPassStatus": PASS_STATUS,
        },
        "idempotencyKey": f"finbot-engineering-capability-platform-v1-{issue['id']}-{int(time.time())}",
        "forceFreshSession": True,
    })


def issue_runs(identifier: str) -> list[dict[str, Any]]:
    data = api("GET", f"issues/{identifier}/runs")
    return data if isinstance(data, list) else []


def issue_comments(identifier: str) -> list[dict[str, Any]]:
    data = api("GET", f"issues/{identifier}/comments", query={"order": "asc"})
    return data if isinstance(data, list) else []


def maybe_sync_status(issue: dict[str, Any], target_status: str) -> tuple[dict[str, Any], str | None]:
    identifier = issue["identifier"]
    latest = api("GET", f"issues/{identifier}")
    if latest.get("status") == target_status:
        return latest, None
    try:
        api("PATCH", f"issues/{issue['id']}", {"status": target_status})
        return api("GET", f"issues/{identifier}"), None
    except RuntimeError as exc:
        return latest, str(exc)


def wait_for_acceptance(op: dict[str, str], issue: dict[str, Any], run_id: str, timeout_s: int = 1200) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    identifier = issue["identifier"]
    first_seen_started_at = None
    last_run = None
    while time.time() < deadline:
        runs = issue_runs(identifier)
        matching = [r for r in runs if r.get("runId") == run_id or r.get("id") == run_id]
        if matching and first_seen_started_at is None:
            first_seen_started_at = matching[-1].get("startedAt") or matching[-1].get("createdAt")
        candidate_runs = []
        for run in runs:
            rid = run.get("runId") or run.get("id")
            if rid == run_id:
                candidate_runs.append(run)
                continue
            if first_seen_started_at and (run.get("startedAt") or run.get("createdAt") or "") >= first_seen_started_at:
                candidate_runs.append(run)
        if candidate_runs:
            last_run = candidate_runs[0]
        succeeded_by_id = {
            (run.get("runId") or run.get("id")): run
            for run in candidate_runs
            if run.get("status") == "succeeded"
        }
        if succeeded_by_id:
            comments = issue_comments(identifier)
            for comment in reversed(comments):
                body = comment.get("body", "")
                comment_run_id = comment.get("createdByRunId")
                if (
                    comment.get("authorAgentId") == op["agentId"]
                    and comment_run_id in succeeded_by_id
                    and PASS_STATUS in body
                    and "capability platform" in body.lower()
                ):
                    accepted_run = succeeded_by_id[comment_run_id]
                    issue_latest, status_error = maybe_sync_status(issue, op["targetStatus"])
                    return {
                        "identifier": identifier,
                        "role": op["role"],
                        "issueId": issue["id"],
                        "title": issue["title"],
                        "issueStatus": issue_latest.get("status"),
                        "statusSyncError": status_error,
                        "accepted": True,
                        "acceptedComment": {
                            "id": comment.get("id"),
                            "authorAgentId": comment.get("authorAgentId"),
                            "createdByRunId": comment.get("createdByRunId"),
                            "createdAt": comment.get("createdAt"),
                            "bodyHead": body[:6000],
                        },
                        "acceptedRun": {
                            "id": comment_run_id,
                            "status": "succeeded",
                            "agentId": op["agentId"],
                            "startedAt": accepted_run.get("startedAt"),
                            "finishedAt": accepted_run.get("finishedAt"),
                            "logRef": accepted_run.get("logRef"),
                        },
                        "discardedRuns": [
                            {
                                "runId": r.get("runId") or r.get("id"),
                                "status": r.get("status"),
                                "reason": "not accepted evidence for capability platform v1",
                            }
                            for r in candidate_runs
                            if (r.get("runId") or r.get("id")) != comment_run_id
                            and r.get("status") in {"failed", "cancelled"}
                        ],
                    }
        time.sleep(10)
    raise RuntimeError(f"timeout waiting for {identifier} run {run_id}; last_run={last_run}")


def main() -> int:
    api("GET", "health")
    live_issues = []
    for op in OPS:
        issue = ensure_issue(op)
        run = wake(op, issue)
        run_id = run.get("id") or run.get("runId")
        if not run_id:
            raise RuntimeError(f"wake did not return a run id for {issue}")
        print(json.dumps({"identifier": issue.get("identifier"), "role": op["role"], "runId": run_id, "status": "woken"}, ensure_ascii=False))
        live_issues.append(wait_for_acceptance(op, issue, run_id))

    readback = {
        "schema": "finbot_engineering.live_readback.v1",
        "generated_at": GENERATED_AT,
        "status": "PASS_LIVE_READBACK",
        "required_validator_status": PASS_STATUS,
        "issues": live_issues,
        "notes": [
            "Accepted evidence requires agent-authored comments bound to succeeded runs.",
            "Engineering implementation uses Finbot Research live issue as evidence carrier only; no separate live Engineering company is claimed.",
            "Governance confirms connector candidates/quarantine and no-advice/no-trading/no-broker boundaries.",
        ],
    }
    write_json(DOC_ROOT / "13_live_paperclip_readback.json", readback)
    print(json.dumps({
        "status": "live_readback_pass",
        "issues": [(item["identifier"], item["role"], item["acceptedRun"]["id"]) for item in live_issues],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
