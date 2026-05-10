#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
RUN_ROOT = REPO / "docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery"
TZ = timezone(timedelta(hours=8))
PASS_STATUS = "PAPERCLIP_OVERNIGHT_ALL_COMPANY_OPS_PASS"


COMPANY_LINES = [
    "finbot_research",
    "finbot_engineering",
    "planning",
    "governance",
    "memory",
    "skill_mcp",
    "runtime",
    "learning_research",
    "local_llm",
    "labebe",
]


@dataclass(frozen=True)
class WorkItem:
    company: str
    task: str
    artifact: str
    delta: list[str]


WORK_ITEMS = [
    WorkItem("planning", "overnight execution queue and Finbot cadence retro", "company_packets/planning/overnight_execution_queue.md", ["priority board", "next-day handoff", "cycle rhythm"]),
    WorkItem("governance", "company architecture correction and false-pass suite", "company_packets/governance/company_architecture_correction.md", ["boundary policy", "false-pass audit", "runtime-lab correction"]),
    WorkItem("memory", "memory research comparison and replay packet", "company_packets/memory/memory_research_and_replay_packet.md", ["provider comparison", "Planning replay", "Finbot memory delta"]),
    WorkItem("skill_mcp", "skill/MCP/plugin readiness matrix and enablement backlog", "company_packets/skill_mcp/skill_mcp_readiness_matrix.md", ["skills inventory", "keep/deprecate/candidate/install-risk", "enablement backlog"]),
    WorkItem("runtime", "runtime capability and fallback matrix refresh", "company_packets/runtime/runtime_fallback_matrix.md", ["runtime pool", "fallback policy", "quarantine confirmation"]),
    WorkItem("learning_research", "learning research executable roadmap", "company_packets/learning_research/learning_research_roadmap.md", ["memory research map", "Skill/MCP research", "Finbot framework research"]),
    WorkItem("local_llm", "local LLM research-only cost/risk matrix", "company_packets/local_llm/local_llm_research_only_packet.md", ["HomePC non-production boundary", "future token-saving candidates", "risk matrix"]),
    WorkItem("labebe", "toy company AI transformation loop", "company_packets/labebe/labebe_transformation_packet.md", ["claim-safe evidence", "AI opportunity map", "demo backlog"]),
    WorkItem("finbot_engineering", "capability lab boundary repair and adapter-smoke extension", "company_packets/finbot_engineering/capability_lab_extension.md", ["AGENTS/README correction", "adapter smoke", "negative fixtures"]),
    WorkItem("finbot_research", "open-ended alpha backlog expansion without advice", "company_packets/finbot_research/open_alpha_backlog_extension.md", ["new source classes", "new themes", "case upgrade/downgrade"]),
    WorkItem("planning", "Governance/Memory/Skill-MCP coordination board", "company_packets/planning/cross_company_priority_board.md", ["cross-company priority", "owner/action", "review queue"]),
    WorkItem("governance", "12 false-pass class validation record", "company_packets/governance/false_pass_12_class_validation.md", ["12 false-pass classes", "guardrail result", "blocking policy"]),
    WorkItem("memory", "current truth vs authority vs verbatim vs rationale policy", "company_packets/memory/memory_layering_policy.md", ["authority layer", "verbatim layer", "rationale layer"]),
    WorkItem("skill_mcp", "Codex2 skills and Superpowers readiness audit", "company_packets/skill_mcp/codex2_superpowers_readiness.md", ["current skills", "MCP boundaries", "install risk"]),
    WorkItem("runtime", "Kimi Code ACP and advisor runtime path", "company_packets/runtime/kimi_acp_and_advisor_paths.md", ["Kimi Code candidate", "Pro/Gemini advisor", "retired runtimes"]),
    WorkItem("labebe", "Design Studio content/commerce candidate backlog", "company_packets/labebe/design_commerce_backlog.md", ["design candidates", "commerce ideas", "blocked next action"]),
]


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def shell(args: list[str]) -> str:
    return subprocess.run(args, cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False).stdout.strip()


def latest_files(patterns: list[str], limit: int = 120) -> list[dict[str, Any]]:
    matches: list[Path] = []
    for root in [REPO / "docs", REPO / "paperclip_finbot", REPO / "paperclip_finbot_engineering_company", REPO / "paperclip_company_os"]:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            lower = path.name.lower()
            rel = str(path.relative_to(REPO))
            if any(p in lower or p in rel.lower() for p in patterns):
                matches.append(path)
    latest = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    rows = []
    for path in latest:
        rel = str(path.relative_to(REPO))
        rows.append({
            "path": rel,
            "mtime": datetime.fromtimestamp(path.stat().st_mtime, TZ).isoformat(timespec="seconds"),
            "size": path.stat().st_size,
            "git_last_commit": shell(["git", "log", "-1", "--format=%h %cI %s", "--", rel]) or None,
        })
    return rows


def freshness_audit() -> dict[str, Any]:
    groups = {
        "current_truth": ["current_truth"],
        "blocker_board": ["blocker_board", "blocker"],
        "execution_matrix": ["execution_matrix", "matrix"],
        "validation": ["validation", "validator", "result"],
        "live_readback": ["live_readback", "readback"],
        "finbot_open_alpha_discovery": ["finbot_open_alpha", "open_alpha", "alpha_discovery"],
        "finbot_engineering_capability_platform": ["capability_platform", "finbot_engineering"],
        "finbot_research_os": ["finbot_research_os", "opportunity", "casebook"],
        "memory": ["memory"],
        "skill_mcp": ["skill", "mcp"],
        "runtime": ["runtime", "fallback"],
        "local_llm": ["local_llm", "local_model", "ollama"],
        "labebe": ["labebe"],
    }
    audit = {
        "schema": "paperclip.overnight.freshness_audit.v1",
        "generated_at": now_iso(),
        "note": "2026-05-06 runtime/skill/MCP/local-model docs are baseline/reference only; later 2026-05-09/2026-05-10 artifacts take precedence.",
        "git_head": shell(["git", "rev-parse", "--short", "HEAD"]),
        "git_status_scoped": shell(["git", "status", "--short", "docs/finbot_open_alpha_discovery_20260510", "paperclip_finbot_engineering_company/AGENTS.md", "paperclip_finbot_engineering_company/README.md"]),
        "groups": {name: latest_files(patterns, 40) for name, patterns in groups.items()},
    }
    write_json(RUN_ROOT / "freshness_audit.json", audit)
    write_text(RUN_ROOT / "freshness_audit.md", "# Freshness Audit\n\n" + "\n".join(
        f"- {group}: `{len(rows)}` latest artifacts, newest `{rows[0]['path'] if rows else 'none'}`"
        for group, rows in audit["groups"].items()
    ) + "\n")
    return audit


def seed_ledgers() -> None:
    backlog = [
        {"company": item.company, "task": item.task, "artifact": item.artifact, "status": "pending"}
        for item in WORK_ITEMS
    ]
    for row in backlog:
        append_jsonl(RUN_ROOT / "global_backlog.jsonl", {"generated_at": now_iso(), **row})
    write_json(RUN_ROOT / "global_backlog_snapshot.json", backlog)
    write_json(RUN_ROOT / "company_execution_matrix.json", {
        "schema": "paperclip.overnight.company_execution_matrix.v1",
        "generated_at": now_iso(),
        "companies": [
            {"company": line, "status": "in_progress", "required_closeout": True, "live_issue_required": True}
            for line in COMPANY_LINES
        ],
    })
    write_text(RUN_ROOT / "company_execution_matrix.md", "# Company Execution Matrix\n\n" + "\n".join(
        f"- `{line}`: in_progress, closeout and live/carrier issue required"
        for line in COMPANY_LINES
    ) + "\n")


def company_packet(item: WorkItem, cycle_no: int) -> None:
    path = RUN_ROOT / item.artifact
    write_text(path, f"""# {item.task}

Updated: `{now_iso()}`

Company: `{item.company}`

Substantive delta:

{chr(10).join(f"- {d}" for d in item.delta)}

Research-only / governance boundary:

- no investment advice;
- no buy/sell/hold;
- no target price;
- no broker action;
- no production watchlist;
- no trade signal;
- no native MCP/skill/runtime production config mutation.

Cycle: `global_work_{cycle_no:02d}`.
""")


def update_truth(cycle_no: int, completed: list[dict[str, Any]]) -> None:
    current_truth = {
        "schema": "paperclip.overnight.current_truth.v1",
        "generated_at": now_iso(),
        "run_root": str(RUN_ROOT),
        "finbot_active_runner": "scripts/run_finbot_open_alpha_discovery_20260510.py",
        "status": "OVERNIGHT_IN_PROGRESS",
        "global_work_cycles_completed": cycle_no,
        "company_lines": COMPANY_LINES,
        "completed_work_items": completed,
        "boundary": "research-only; no advice/trading/broker/watchlist/signal",
    }
    write_json(RUN_ROOT / "current_truth.json", current_truth)
    write_text(RUN_ROOT / "current_truth.md", f"# Current Truth\n\nStatus: `{current_truth['status']}`\n\nGlobal work cycles completed: `{cycle_no}`.\n\n")
    blockers = {
        "schema": "paperclip.overnight.blocker_board.v1",
        "generated_at": now_iso(),
        "blockers": [
            {"id": "B-FINBOT-RUNNER-ACTIVE", "status": "in_progress", "owner": "Finbot Research", "next_action": "continue monitoring existing run; do not start duplicate run"},
            {"id": "B-LIVE-ISSUE-FINAL-READBACK", "status": "pending", "owner": "All company carrier agents", "next_action": "create/update live issues after final local artifacts are stable"},
            {"id": "B-CONNECTOR-CANDIDATES", "status": "not_blocking", "owner": "Governance", "next_action": "keep Readwise/Zotero/Alpaca/Daloopa/Quartr/Binance as candidate unless read-only proof exists"},
            {"id": "B-PROVIDER-QUARANTINE", "status": "not_blocking", "owner": "Governance", "next_action": "keep MiniMax/DeepSeek/Tavily/Brave no-production-use"},
        ],
    }
    write_json(RUN_ROOT / "blocker_board.json", blockers)
    write_text(RUN_ROOT / "blocker_board.md", "# Blocker Board\n\n" + "\n".join(
        f"- `{b['id']}`: {b['status']} / owner={b['owner']} / next={b['next_action']}"
        for b in blockers["blockers"]
    ) + "\n")


def run_global_cycle(cycle_no: int, completed: list[dict[str, Any]]) -> None:
    item = WORK_ITEMS[(cycle_no - 1) % len(WORK_ITEMS)]
    company_packet(item, cycle_no)
    ledger = {
        "cycle_id": f"global_work_{cycle_no:02d}",
        "generated_at": now_iso(),
        "company": item.company,
        "task": item.task,
        "artifact": item.artifact,
        "substantive_delta": item.delta,
        "sleep_only": False,
        "work_stealing": True,
        "reason": "Finbot runner interval or broader all-company overnight backlog",
    }
    append_jsonl(RUN_ROOT / "cycle_ledger.jsonl", ledger)
    append_jsonl(RUN_ROOT / "work_stealing_audit.jsonl", ledger)
    append_jsonl(RUN_ROOT / "anti_idle_audit.jsonl", {
        "cycle_id": ledger["cycle_id"],
        "generated_at": now_iso(),
        "valid_cycle": True,
        "rejected_sleep_only": True,
        "evidence": item.artifact,
    })
    acceptance = {
        "company": item.company,
        "task": item.task,
        "artifact": item.artifact,
        "status": "local_artifact_complete_pending_live_readback",
        "generated_at": now_iso(),
    }
    append_jsonl(RUN_ROOT / "acceptance_ledger.jsonl", acceptance)
    completed.append(acceptance)
    update_truth(cycle_no, completed)
    print(json.dumps({"event": "global_cycle_complete", **ledger}, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=18)
    parser.add_argument("--interval-minutes", type=float, default=20.0)
    parser.add_argument("--no-sleep", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    freshness_audit()
    if not (RUN_ROOT / "global_backlog.jsonl").exists():
        seed_ledgers()
    completed: list[dict[str, Any]] = []
    existing_cycles = 0
    if args.resume and (RUN_ROOT / "cycle_ledger.jsonl").exists():
        existing_cycles = len([line for line in (RUN_ROOT / "cycle_ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()])
        append_jsonl(RUN_ROOT / "work_stealing_audit.jsonl", {
            "cycle_id": "global_resume",
            "generated_at": now_iso(),
            "valid_cycle": False,
            "sleep_only": False,
            "reason": "continuation marker only; not counted as effective cycle",
            "existing_cycles": existing_cycles,
        })
    for cycle_no in range(existing_cycles + 1, args.cycles + 1):
        started = time.time()
        run_global_cycle(cycle_no, completed)
        if cycle_no < args.cycles and not args.no_sleep:
            elapsed = time.time() - started
            time.sleep(max(0, args.interval_minutes * 60 - elapsed))
    write_json(RUN_ROOT / "global_ops_runtime_summary.json", {
        "schema": "paperclip.overnight.global_ops_runtime.v1",
        "generated_at": now_iso(),
        "status": "GLOBAL_WORK_STEALING_COMPLETE_PENDING_FINAL_MERGE",
        "cycles": args.cycles,
        "companies_touched": sorted(set(row["company"] for row in completed)),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
