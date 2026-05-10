#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
RUN_ROOT = REPO / "docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery"
PASS_STATUS = "FINBOT_OPEN_ALPHA_DISCOVERY_8H_PASS"
TZ = timezone(timedelta(hours=8))


OPS = [
    {
        "role": "finbot_research",
        "companyId": "470afc19-473b-4794-9191-c957d34aa330",
        "projectId": "ac80804a-2e52-4368-81a4-aece6bf30649",
        "agentId": "ede1270f-8cce-433b-bcf8-e6b313f68ff7",
        "title": "Finbot open-ended alpha discovery 8h research readback",
        "priority": "high",
        "description": """Validate Finbot Research's open-ended alpha discovery package.

Evidence root: {root}

Required checks:
- Confirm wall clock >= 8 hours and effective cycles >= 10.
- Confirm source candidates >= 80, themes >= 30, opportunity candidates >= 120, alpha-qualified cases >= 30, full decision memos >= 12 and top surprising opportunities >= 10.
- Inspect 05_opportunity_board.json, 06_top_surprising_opportunities.json, 07_alpha_qualified_casebook.json, 16_cycle_by_cycle_substantive_delta_audit.json and 20_final_validation.json.
- Confirm outputs are research-only: no investment advice, no buy/sell/hold, no target price, no position sizing, no trade signal, no broker action, no production watchlist.
- Comment must start with: Open-ended alpha discovery validation complete
- Include token: {status}
""",
    },
    {
        "role": "finbot_engineering",
        "companyId": "470afc19-473b-4794-9191-c957d34aa330",
        "projectId": "ac80804a-2e52-4368-81a4-aece6bf30649",
        "agentId": "ede1270f-8cce-433b-bcf8-e6b313f68ff7",
        "title": "Finbot Engineering open-ended alpha discovery capability support readback",
        "priority": "high",
        "description": """Validate Finbot Engineering support for the open-ended alpha discovery run.

Evidence root: {root}
Engineering implementation root: /vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company

No separate live Finbot Engineering company is being claimed; this is a Finbot Research evidence carrier for the engineering capability line.

Required checks:
- Confirm capability platform v1 remains pass and the new open-alpha validator is fail-closed.
- Inspect scripts/run_finbot_open_alpha_discovery_20260510.py, scripts/validate_finbot_open_alpha_discovery_20260510.py, 14_governance_false_pass_audit.json and 20_final_validation.json.
- Confirm endpoint-only, false readiness, advice/trading, target-price-as-advice, broker action and production watchlist are rejected.
- Confirm Readwise/Zotero/Alpaca/Daloopa/Quartr/Binance remain candidate unless separately approved; MiniMax/DeepSeek/Tavily/Brave remain quarantined/no-production-use.
- Comment must start with: Open-ended alpha discovery validation complete
- Include token: {status}
""",
    },
    {
        "role": "planning",
        "companyId": "79ea2b85-b980-4e61-95e1-57e629a6358f",
        "projectId": "b20e9c45-fe77-4a8c-bc25-bc6026ca620b",
        "agentId": "67dca5ac-a3ff-4d06-a01e-83c4aa50bc7e",
        "title": "Planning open-ended Finbot alpha discovery 7-day campaign readback",
        "priority": "high",
        "description": """Validate Planning follow-up for the open-ended Finbot alpha discovery package.

Evidence root: {root}

Required checks:
- Inspect 12_human_review_queue.json, 13_next_7_day_research_campaign.json, 17_current_truth.json, 18_blocker_board.json and 19_execution_matrix.json.
- Confirm Planning output is a concrete follow-up queue and 7-day campaign, not generic summary.
- Confirm all actions remain research-only and require human review before any escalation.
- Comment must start with: Open-ended alpha discovery validation complete
- Include token: {status}
""",
    },
    {
        "role": "governance",
        "companyId": "f3ef00b8-3654-48b2-abda-dd9d63a7c42d",
        "projectId": "ec69c0ac-0e0a-45f7-8f26-7f638d861356",
        "agentId": "11858cbd-02dd-4f43-9d00-553189dbd1bc",
        "title": "Governance open-ended Finbot alpha discovery false-pass and boundary readback",
        "priority": "high",
        "description": """Validate Governance boundaries for the open-ended Finbot alpha discovery package.

Evidence root: {root}

Required checks:
- Inspect 14_governance_false_pass_audit.json, 15_live_paperclip_readback.json, 16_cycle_by_cycle_substantive_delta_audit.json, 20_final_validation.json and scripts/validate_finbot_open_alpha_discovery_20260510.py.
- Confirm no sleep-only cycles were counted.
- Confirm top opportunities require primary evidence, counter-evidence, research_estimate_range, catalyst/watch window and human review question.
- Confirm no advice/trading/broker/target-price/production-watchlist outputs.
- Confirm MiniMax/DeepSeek/Tavily/Brave were not used and remain quarantined/no-production-use.
- Comment must start with: Open-ended alpha discovery validation complete
- Include token: {status}
""",
    },
]


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


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
    description = op["description"].format(root=RUN_ROOT, status=PASS_STATUS)
    for issue in list_company_issues(op["companyId"]):
        if issue.get("title") == op["title"]:
            return api("PATCH", f"issues/{issue['id']}", {
                "description": description,
                "assigneeAgentId": op["agentId"],
                "priority": op["priority"],
                "status": "backlog",
            })
    return api("POST", f"companies/{op['companyId']}/issues", {
        "projectId": op["projectId"],
        "title": op["title"],
        "description": description,
        "status": "backlog",
        "priority": op["priority"],
        "assigneeAgentId": op["agentId"],
    })


def wake(op: dict[str, str], issue: dict[str, Any]) -> dict[str, Any]:
    return api("POST", f"agents/{op['agentId']}/wakeup", {
        "source": "assignment",
        "triggerDetail": "manual",
        "reason": "finbot_open_alpha_discovery_8h_validation",
        "payload": {
            "issueId": issue["id"],
            "identifier": issue.get("identifier"),
            "title": issue["title"],
            "artifactRoot": str(RUN_ROOT),
            "requiredPassStatus": PASS_STATUS,
        },
        "idempotencyKey": f"finbot-open-alpha-8h-{issue['id']}-{int(time.time())}",
        "forceFreshSession": True,
    })


def issue_runs(identifier: str) -> list[dict[str, Any]]:
    data = api("GET", f"issues/{identifier}/runs")
    return data if isinstance(data, list) else []


def issue_comments(identifier: str) -> list[dict[str, Any]]:
    data = api("GET", f"issues/{identifier}/comments", query={"order": "asc"})
    return data if isinstance(data, list) else []


def maybe_done(issue: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    latest = api("GET", f"issues/{issue['identifier']}")
    if latest.get("status") == "done":
        return latest, None
    try:
        api("PATCH", f"issues/{issue['id']}", {"status": "done"})
        return api("GET", f"issues/{issue['identifier']}"), None
    except RuntimeError as exc:
        return latest, str(exc)


def wait_for_acceptance(op: dict[str, str], issue: dict[str, Any], run_id: str, timeout_s: int) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    identifier = issue["identifier"]
    first_seen_started_at = None
    last_run = None
    while time.time() < deadline:
        runs = issue_runs(identifier)
        matching = [r for r in runs if (r.get("runId") or r.get("id")) == run_id]
        if matching and first_seen_started_at is None:
            first_seen_started_at = matching[-1].get("startedAt") or matching[-1].get("createdAt")
        candidate_runs = []
        for run in runs:
            rid = run.get("runId") or run.get("id")
            if rid == run_id:
                candidate_runs.append(run)
            elif first_seen_started_at and (run.get("startedAt") or run.get("createdAt") or "") >= first_seen_started_at:
                candidate_runs.append(run)
        if candidate_runs:
            last_run = candidate_runs[0]
        succeeded = {
            (r.get("runId") or r.get("id")): r
            for r in candidate_runs
            if r.get("status") == "succeeded"
        }
        if succeeded:
            for comment in reversed(issue_comments(identifier)):
                body = comment.get("body") or ""
                crid = comment.get("createdByRunId")
                if (
                    comment.get("authorAgentId") == op["agentId"]
                    and crid in succeeded
                    and PASS_STATUS in body
                    and ("open-ended alpha discovery" in body.lower() or "open ended alpha discovery" in body.lower())
                ):
                    latest, status_error = maybe_done(issue)
                    return {
                        "identifier": identifier,
                        "role": op["role"],
                        "issueId": issue["id"],
                        "title": issue["title"],
                        "issueStatus": latest.get("status"),
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
                            "id": crid,
                            "status": "succeeded",
                            "agentId": op["agentId"],
                            "startedAt": succeeded[crid].get("startedAt"),
                            "finishedAt": succeeded[crid].get("finishedAt"),
                            "logRef": succeeded[crid].get("logRef"),
                        },
                        "discardedRuns": [
                            {"runId": r.get("runId") or r.get("id"), "status": r.get("status")}
                            for r in candidate_runs
                            if (r.get("runId") or r.get("id")) != crid and r.get("status") in {"failed", "cancelled"}
                        ],
                    }
        time.sleep(10)
    raise RuntimeError(f"timeout waiting for {identifier} run {run_id}; last_run={last_run}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-s", type=int, default=1800)
    args = parser.parse_args()
    api("GET", "health")
    live_issues = []
    for op in OPS:
        issue = ensure_issue(op)
        run = wake(op, issue)
        run_id = run.get("id") or run.get("runId")
        if not run_id:
            raise RuntimeError(f"wakeup did not return run id for {issue}")
        print(json.dumps({"identifier": issue.get("identifier"), "role": op["role"], "runId": run_id, "status": "woken"}, ensure_ascii=False), flush=True)
        live_issues.append(wait_for_acceptance(op, issue, run_id, args.timeout_s))
    readback = {
        "schema": "finbot.open_alpha.live_readback.v1",
        "generated_at": now_iso(),
        "status": "PASS_LIVE_READBACK",
        "required_status": PASS_STATUS,
        "issues": live_issues,
        "notes": [
            "Accepted evidence requires agent-authored comments bound to succeeded runs.",
            "Finbot Engineering role is carried by a Finbot Research live issue because no separate live Engineering company exists.",
            "This package remains research-only and no-advice/no-trading/no-broker/no-production-watchlist.",
        ],
    }
    write_json(RUN_ROOT / "15_live_paperclip_readback.json", readback)
    print(json.dumps({"status": "live_readback_pass", "issues": [(i["identifier"], i["role"], i["acceptedRun"]["id"]) for i in live_issues]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
