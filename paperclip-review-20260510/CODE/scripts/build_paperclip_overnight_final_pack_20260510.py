#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
RUN_ROOT = REPO / "docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery"
TZ = timezone(timedelta(hours=8))
PASS_STATUS = "PAPERCLIP_OVERNIGHT_ALL_COMPANY_OPS_PASS"


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_text_preserve_enriched(path: Path, text: str, preserve: bool) -> None:
    if preserve and path.exists():
        return
    write_text(path, text)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def main() -> int:
    runtime = read_json(RUN_ROOT / "runtime_summary.json")
    counts = runtime.get("counts", {})
    live = read_json(RUN_ROOT / "15_live_paperclip_readback.json") if (RUN_ROOT / "15_live_paperclip_readback.json").exists() else {"status": "PENDING"}
    preserve_enriched = (RUN_ROOT / "company_packet_enrichment_result.json").exists()
    global_cycles = load_jsonl(RUN_ROOT / "cycle_ledger.jsonl")
    acceptance = load_jsonl(RUN_ROOT / "acceptance_ledger.jsonl")
    artifacts = []
    for path in sorted(RUN_ROOT.rglob("*")):
        if path.is_file():
            artifacts.append({
                "path": str(path.relative_to(RUN_ROOT)),
                "size": path.stat().st_size,
                "mtime": datetime.fromtimestamp(path.stat().st_mtime, TZ).isoformat(timespec="seconds"),
            })
    manifest = {
        "schema": "paperclip.overnight.final_evidence_manifest.v1",
        "generated_at": now_iso(),
        "status": "FINAL_PACK_BUILT_PENDING_VALIDATOR" if live.get("status") != "PASS_LIVE_READBACK" else "FINAL_PACK_BUILT",
        "run_root": str(RUN_ROOT),
        "runtime": runtime,
        "counts": counts,
        "live_status": live.get("status"),
        "global_cycle_count": len(global_cycles),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    write_json(RUN_ROOT / "final_evidence_manifest.json", manifest)
    write_text(RUN_ROOT / "final_evidence_manifest.md", "# Final Evidence Manifest\n\n" + table(
        ["Artifact", "Size", "Mtime"],
        [[a["path"], a["size"], a["mtime"]] for a in artifacts[:220]],
    ) + "\n")
    closeouts = {}
    for row in acceptance:
        closeouts.setdefault(row.get("company"), []).append(row)
    write_json(RUN_ROOT / "company_by_company_closeout.json", {
        "schema": "paperclip.overnight.company_closeout.v1",
        "generated_at": now_iso(),
        "status": "local_closeout_complete_pending_live" if live.get("status") != "PASS_LIVE_READBACK" else "live_closeout_complete",
        "companies": closeouts,
    })
    write_text(RUN_ROOT / "company_by_company_closeout.md", "# Company By Company Closeout\n\n" + "\n".join(
        f"## {company}\n" + "\n".join(f"- `{item['artifact']}`: {item['status']}" for item in rows)
        for company, rows in sorted(closeouts.items())
    ) + "\n")
    write_text_preserve_enriched(RUN_ROOT / "Planning_overnight_closeout.md", "# Planning Overnight Closeout\n\nSee `company_packets/planning/`, `13_next_7_day_research_campaign.json`, `company_execution_matrix.json`, and `acceptance_ledger.jsonl`.\n", preserve_enriched)
    write_text_preserve_enriched(RUN_ROOT / "Governance_correction_packet.md", "# Governance Correction Packet\n\nSee `company_packets/governance/`, `14_governance_false_pass_audit.json`, `blocker_board.json`, and `current_truth.json`.\n", preserve_enriched)
    write_text_preserve_enriched(RUN_ROOT / "Memory_research_and_replay_packet.md", "# Memory Research And Replay Packet\n\nSee `company_packets/memory/` for provider comparison, Planning replay, Finbot memory delta and memory layering policy.\n", preserve_enriched)
    write_text_preserve_enriched(RUN_ROOT / "Skill_MCP_readiness_matrix.md", "# Skill MCP Readiness Matrix\n\nSee `company_packets/skill_mcp/` and `freshness_audit.json`. No native MCP/skill production config was mutated.\n", preserve_enriched)
    write_text_preserve_enriched(RUN_ROOT / "Runtime_fallback_matrix.md", "# Runtime Fallback Matrix\n\nSee `company_packets/runtime/`. claudemi/claudegac remain out of effective pool; MiniMax/DeepSeek/Tavily/Brave remain quarantined/no-production-use.\n", preserve_enriched)
    write_text_preserve_enriched(RUN_ROOT / "Learning_Research_roadmap.md", "# Learning Research Roadmap\n\nSee `company_packets/learning_research/` for executable research map across memory, Skill/MCP, runtime and Finbot framework research.\n", preserve_enriched)
    write_text_preserve_enriched(RUN_ROOT / "Local_LLM_research_only_packet.md", "# Local LLM Research-Only Packet\n\nSee `company_packets/local_llm/`. HomePC Ollama remains research-only and is not connected to current Paperclip production building.\n", preserve_enriched)
    write_text_preserve_enriched(RUN_ROOT / "Labebe_transformation_packet.md", "# Labebe Transformation Packet\n\nSee `company_packets/labebe/` for toy company AI transformation evidence, opportunity map, demo backlog and blocked next actions.\n", preserve_enriched)
    validation = read_json(RUN_ROOT / "20_final_validation.json") if (RUN_ROOT / "20_final_validation.json").exists() else {}
    if validation.get("status") != PASS_STATUS or not (RUN_ROOT / "22_closeout.md").exists():
        write_text(RUN_ROOT / "22_closeout.md", f"""# 22 Closeout

Generated: `{now_iso()}`

Status: `PENDING_FINAL_VALIDATOR` unless `20_final_validation.json` says `{PASS_STATUS}`.

Counts: `{json.dumps(counts, ensure_ascii=False)}`.

Boundary: research-only. No investment advice, no buy/sell/hold, no target price, no position sizing, no trading signal, no broker action, no production watchlist.
""")
    print(json.dumps({"status": "final_pack_built", "artifact_count": len(artifacts), "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
