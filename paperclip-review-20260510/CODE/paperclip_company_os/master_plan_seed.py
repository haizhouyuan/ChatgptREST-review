from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

from .api import PaperclipClient


MASTER_PROJECT = "Paperclip Production Master Plan 20260507"
MASTER_PLAN_PATH = "/vol1/1000/projects/toyresearch/docs/PAPERCLIP_PRODUCTION_MASTER_PLAN_20260507.md"


@dataclass(frozen=True)
class CompanyTarget:
    company_id: str
    project_name: str
    agent_id: str | None


COMPANIES: dict[str, CompanyTarget] = {
    "governance": CompanyTarget(
        "f3ef00b8-3654-48b2-abda-dd9d63a7c42d",
        MASTER_PROJECT,
        "11858cbd-02dd-4f43-9d00-553189dbd1bc",
    ),
    "planning": CompanyTarget(
        "79ea2b85-b980-4e61-95e1-57e629a6358f",
        MASTER_PROJECT,
        "948f728e-7dbd-4b54-a49c-409c15724538",
    ),
    "learning": CompanyTarget(
        "b862eb50-4a58-4b93-86ef-30a625a5a29c",
        MASTER_PROJECT,
        "726864d8-88e0-4d83-8589-535f86acdd03",
    ),
    "memory": CompanyTarget(
        "51fc5dce-c1a9-49f4-8458-ee0000ae25a3",
        MASTER_PROJECT,
        "918b15d2-e906-44fb-8a8d-e61e171f0b5e",
    ),
    "finbot": CompanyTarget(
        "470afc19-473b-4794-9191-c957d34aa330",
        "Finbot Complete Company Execution 20260507",
        "ff8b06ea-7069-4fb7-ab2d-aecf87c48c92",
    ),
    "labebe": CompanyTarget(
        "9ca70186-256c-49f4-8d87-038a94f32acb",
        MASTER_PROJECT,
        "19f88a52-0983-4aa4-a00c-2eb3a1c41cfe",
    ),
    "design_studio": CompanyTarget(
        "1cb6d439-2bdf-4f63-ad9a-b5326d5546df",
        MASTER_PROJECT,
        "21bb4465-6cc8-4b1e-bfe7-99ca18cceb63",
    ),
    "local_llm": CompanyTarget(
        "292a1435-520a-405a-9c65-34c35390c843",
        MASTER_PROJECT,
        "0a5e71d1-c0fe-4093-852c-4bbeebd40f78",
    ),
    "runtime": CompanyTarget(
        "91916737-9533-4d63-9c1e-e04894dabd41",
        MASTER_PROJECT,
        "b32456b6-9507-4da6-9039-145f31406796",
    ),
    "pecl_runtime": CompanyTarget(
        "e22d147c-3d93-4022-bc68-04630ad39607",
        MASTER_PROJECT,
        "0170a003-4096-472e-979f-3a9981502ea9",
    ),
}


def contract_description(stage: str, objective: str, outputs: list[str], extra: str = "") -> str:
    output_lines = "\n".join(f"- {item}" for item in outputs)
    return f"""# {stage}

Master plan: `{MASTER_PLAN_PATH}`

## Objective

{objective}

## Required execution loop

Use the Paperclip company-owned loop:

`intake -> contract -> preflight -> lease -> worker -> evidence -> validator -> memory_delta/no_write -> Paperclip sync -> readback -> closeout`

## Hard boundaries

- Produce durable evidence artifacts with stable paths.
- Do not close as `done` without evidence, validator result, memory closeout and Paperclip readback.
- If blocked, set the issue to `blocked` and write the blocker artifact.
- Domain artifacts must be produced by this assigned company/agent, not by the controller.
- Runtime/MCP/skill config changes require: snapshot -> proposal -> risk review -> one bounded change -> live smoke -> rollback proof -> Paperclip closeout.

## Terminal outputs

{output_lines}
{extra}
"""


TASKS: list[dict[str, Any]] = [
    {
        "key": "governance",
        "title": "MASTER-A4-A5 Current truth snapshot and false-completion rules",
        "priority": "high",
        "stage": "Stage A",
        "objective": "Write the current truth snapshot for all active companies and freeze false-completion/non-claim rules for this master run.",
        "outputs": [
            "`docs/paperclip_production_current_truth_20260507.md`",
            "`docs/paperclip_company_blocker_board_20260507.md` initial blocker/non-claim section",
            "Paperclip issue status/comment readback",
        ],
    },
    {
        "key": "runtime",
        "title": "MASTER-B Company operating kernel acceptance",
        "priority": "high",
        "stage": "Stage B",
        "objective": "Verify and extend the shared `paperclip_company_os` kernel so it satisfies B1-B10: contract schema, preflight, lease ledger, evidence manifest, validator result, memory closeout, Paperclip sync/readback, and matrix generation.",
        "outputs": [
            "`paperclip_company_os/` schema/CLI/tests",
            "`docs/paperclip_company_kernel_acceptance_20260507.md`",
            "test output for company OS acceptance",
            "memory closeout/no_write reason",
        ],
    },
    {
        "key": "runtime",
        "title": "MASTER-C Runtime production optimization gated run",
        "priority": "high",
        "stage": "Stage C",
        "objective": "Run C1-C10: snapshot runtime wrappers, build live probes, classify excluded runtimes, smoke KimiCode/ClaudeKimi/ClaudeMinimax/ClaudeDS/Gemini/Codex, produce fallback policy, and apply only approved bounded runtime config changes.",
        "outputs": [
            "`docs/paperclip_runtime_skill_mcp_gate_report_20260507.md` runtime sections",
            "runtime snapshot manifest",
            "runtime live probe results",
            "runtime config-change gated closeout or blocker",
        ],
    },
    {
        "key": "governance",
        "title": "MASTER-D-E MCP and skill production optimization gated run",
        "priority": "high",
        "stage": "Stage D/E",
        "objective": "Run D1-D8 and E1-E7: snapshot MCP/skill surfaces, classify ownership/trust, smoke safe servers/skills, propose changes, apply approved bounded changes only, prove rollback, and publish boards.",
        "outputs": [
            "`docs/paperclip_runtime_skill_mcp_gate_report_20260507.md` MCP/skill sections",
            "MCP snapshot and smoke report",
            "skill lifecycle registry",
            "at least one approved skill/MCP lifecycle decision or explicit blocker",
        ],
    },
    {
        "key": "governance",
        "title": "MASTER-F Governance company production loop",
        "priority": "high",
        "stage": "Stage F",
        "objective": "Run F1-F5: company registry reconciliation, unsafe production-claim gate, runtime/MCP/skill approval workflow, memory provider promotion policy, and proof that Governance can block unsafe company states.",
        "outputs": [
            "governance closeout with evidence path",
            "policy decision artifact",
            "memory provider promotion policy artifact",
            "Paperclip readback proving blocked/done state",
        ],
    },
    {
        "key": "planning",
        "title": "MASTER-G Planning production loop",
        "priority": "high",
        "stage": "Stage G",
        "objective": "Run G1-G5: strategy brief, HR/org note, meeting intake/transcript management, fresh-agent resume test, and Planning usefulness review.",
        "outputs": [
            "strategy brief artifact",
            "HR/org note artifact",
            "meeting decisions/actions artifact",
            "fresh-agent resume report",
            "memory delta/no_write closeouts for each Planning job",
        ],
    },
    {
        "key": "learning",
        "title": "MASTER-H1 Learning research provider-eval intake",
        "priority": "high",
        "stage": "Stage H1",
        "objective": "Produce the Learning Research contract for memory provider evaluation and route concrete provider tests to Memory Research Lab.",
        "outputs": [
            "provider evaluation research contract",
            "source registry",
            "experiment design",
            "Paperclip readback",
        ],
    },
    {
        "key": "memory",
        "title": "MASTER-H2-H8 Memory provider no-write evaluation suite",
        "priority": "high",
        "stage": "Stage H",
        "objective": "Run Graphiti clean-room no-write projection, MemPalace read-path/verbatim adapter, Supermemory privacy/export/provenance gate, GBrain ops sandbox, native baseline comparison, blind fresh-agent memory test, and provider decision recommendation.",
        "outputs": [
            "`docs/paperclip_memory_provider_eval_20260507.md`",
            "raw provider outputs/traces/scorers",
            "provider quarantine/rollback decisions",
            "blind fresh-agent recovery report",
        ],
    },
    {
        "key": "finbot",
        "title": "MASTER-I Finbot research-only production loop",
        "priority": "high",
        "stage": "Stage I",
        "objective": "Run I1-I7 across the existing FIN-8..FIN-14 evidence: material readiness, official connector graph, collection validator, OpportunityCase/ReviewWindow dry run, Finbot memory closeout, no-advice audit, and Pro packet/action register.",
        "outputs": [
            "material ledger or formal blocker",
            "official source evidence graph with checksums or blockers",
            "validator v1.3+ report",
            "research-only blocked/park/rank report",
            "Finbot no-advice/no-watchlist/no-trading audit",
        ],
    },
    {
        "key": "labebe",
        "title": "MASTER-J Labebe production loop",
        "priority": "high",
        "stage": "Stage J",
        "objective": "Run J1-J5: claim-safe evidence bundle, product/copy/page improvement, demo/package closeout, memory closeout/resume test, and Labebe production usability decision.",
        "outputs": [
            "claim-safe evidence bundle",
            "product/copy/page output with claim-safety validation",
            "demo/package closeout",
            "memory closeout and resume report",
        ],
    },
    {
        "key": "design_studio",
        "title": "MASTER-JX Labebe Design Studio active-company closed loop",
        "priority": "medium",
        "stage": "Stage J active-company coverage",
        "objective": "Because Labebe AI Design Studio is active, run one closed-loop claim-safe design/demo issue or formally recommend bind/merge/archive action without unsupported claims.",
        "outputs": [
            "design-studio closed-loop artifact or bind/merge/archive recommendation",
            "claim-safety validation",
            "memory closeout/no_write reason",
        ],
    },
    {
        "key": "local_llm",
        "title": "MASTER-K Local LLM research-only loop",
        "priority": "high",
        "stage": "Stage K",
        "objective": "Run K1-K5: HomePC capability verification, local digest/extraction benchmark, quality/fallback/privacy evaluation, future automation class policy, and non-use audit for Paperclip system-building.",
        "outputs": [
            "local model live probe report",
            "digest/extraction benchmark",
            "quality/fallback/privacy decision report",
            "local-model non-use audit",
        ],
    },
    {
        "key": "pecl_runtime",
        "title": "MASTER-KX PECL Runtime Steward active-company closeout",
        "priority": "medium",
        "stage": "Active company coverage",
        "objective": "Because PECL Runtime Steward Company remains active, run one closed-loop historical-infra/current-boundary closeout proving it is a lab lane, not daily business governance.",
        "outputs": [
            "PECL runtime steward boundary closeout",
            "evidence path and validator",
            "memory closeout/no_write reason",
        ],
    },
    {
        "key": "runtime",
        "title": "MASTER-L Operator surface and final review package",
        "priority": "high",
        "stage": "Stage L",
        "objective": "Run L1-L10: build execution matrix, blocker board, memory delta board, runtime/MCP/skill boards, current-truth handoff, Pro packet, Pro review/action register, P0 blocker handling and final master closeout.",
        "outputs": [
            "`docs/paperclip_company_execution_matrix_20260507.md`",
            "`docs/paperclip_company_blocker_board_20260507.md`",
            "`docs/paperclip_runtime_skill_mcp_gate_report_20260507.md`",
            "`docs/pro_review_packets/paperclip_production_master_review_20260507.zip`",
            "`docs/paperclip_production_master_closeout_20260507.md`",
        ],
    },
]


def ensure_project(client: PaperclipClient, target: CompanyTarget) -> str:
    projects = client.get(f"companies/{target.company_id}/projects")
    for project in projects:
        if project.get("name") == target.project_name:
            return project["id"]
    created = client.post(
        f"companies/{target.company_id}/projects",
        {
            "name": target.project_name,
            "description": "Production master plan 2026-05-07 execution project.",
            "status": "in_progress",
            "color": "#0f766e",
        },
    )
    return created["id"]


def find_issue_by_title(client: PaperclipClient, company_id: str, title: str) -> dict[str, Any] | None:
    issues = client.get(f"companies/{company_id}/issues", {"limit": "200"})
    for issue in issues:
        if issue.get("title") == title:
            return issue
    return None


def ensure_issue(client: PaperclipClient, task: dict[str, Any], project_id: str, target: CompanyTarget) -> dict[str, Any]:
    existing = find_issue_by_title(client, target.company_id, task["title"])
    if existing:
        return existing
    payload = {
        "projectId": project_id,
        "title": task["title"],
        "description": contract_description(task["stage"], task["objective"], task["outputs"]),
        "status": "backlog",
        "priority": task["priority"],
        "assigneeAgentId": target.agent_id,
    }
    return client.post(f"companies/{target.company_id}/issues", payload)


def wake_issue(client: PaperclipClient, issue: dict[str, Any], target: CompanyTarget, *, run_tag: str) -> dict[str, Any] | None:
    if not target.agent_id:
        return None
    return client.post(
        f"agents/{target.agent_id}/wakeup",
        {
            "source": "assignment",
            "triggerDetail": "manual",
            "reason": "paperclip_production_master_plan",
            "payload": {
                "issueId": issue["id"],
                "identifier": issue.get("identifier"),
                "title": issue.get("title"),
                "contextSource": "master_plan_seed",
            },
            "idempotencyKey": f"20260507-master-{run_tag}-{issue['id']}",
            "forceFreshSession": True,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:3100/api")
    parser.add_argument("--wake", action="store_true")
    parser.add_argument("--run-tag", default="v1")
    parser.add_argument("--only-stage-prefix")
    args = parser.parse_args()

    client = PaperclipClient(args.base_url)
    results: list[dict[str, Any]] = []
    for task in TASKS:
        if args.only_stage_prefix and not task["stage"].startswith(args.only_stage_prefix):
            continue
        target = COMPANIES[task["key"]]
        project_id = ensure_project(client, target)
        issue = ensure_issue(client, task, project_id, target)
        wake = wake_issue(client, issue, target, run_tag=args.run_tag) if args.wake else None
        results.append(
            {
                "stage": task["stage"],
                "company_key": task["key"],
                "issue_id": issue["id"],
                "identifier": issue.get("identifier"),
                "title": issue["title"],
                "status": issue["status"],
                "assignee_agent_id": target.agent_id,
                "project_id": project_id,
                "wake_run_id": wake.get("id") if isinstance(wake, dict) else None,
                "wake_status": wake.get("status") if isinstance(wake, dict) else None,
            }
        )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
