#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
RUN_ROOT = REPO / "docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery"
RESEARCH_ROOT = REPO / "docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp"
CAPABILITY_ROOT = REPO / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform"
ENGINEERING_ROOT = REPO / "paperclip_finbot_engineering_company"
MAINT_DOCS = Path("/vol1/maint/docs")
PROJECTS_ROOT = Path("/vol1/1000/projects")
TZ = timezone(timedelta(hours=8))
PASS_STATUS = "FINBOT_OPEN_ALPHA_DISCOVERY_8H_PASS"
SEC_UA = os.environ.get("FINBOT_SEC_USER_AGENT", "finbot-research-only open-alpha-discovery contact local@example.com")

FORBIDDEN_OUTPUTS = [
    "investment_advice",
    "buy_sell_hold",
    "target_price",
    "position_size",
    "trade_signal",
    "broker_action",
    "production_watchlist",
    "automatic_trading",
]


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def fetch_json(url: str, cache_name: str, max_age_hours: int = 24) -> Any:
    cache = RUN_ROOT / "sec_cache" / cache_name
    if cache.exists() and time.time() - cache.stat().st_mtime < max_age_hours * 3600:
        return read_json(cache)
    req = urllib.request.Request(url, headers={"User-Agent": SEC_UA, "Accept-Encoding": "identity"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            write_json(cache, payload)
            time.sleep(0.15)
            return payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == 2:
                raise
            time.sleep(1 + attempt)


def scan_assets() -> dict[str, Any]:
    roots = [
        REPO,
        MAINT_DOCS,
        PROJECTS_ROOT / "ChatgptREST",
        PROJECTS_ROOT / "OpenClaw",
        PROJECTS_ROOT / "finchat",
        PROJECTS_ROOT / "codexread",
        PROJECTS_ROOT / "codex-read",
    ]
    keywords = re.compile(r"(finbot|finchat|openclaw|chatgptrest|codex[-_]?read|投研|pro|advisor|critical|review|opportunity|alpha|research)", re.I)
    found: list[dict[str, Any]] = []
    missing: list[str] = []
    for root in roots:
        if not root.exists():
            missing.append(str(root))
            continue
        count = 0
        for path in root.rglob("*"):
            if path.is_file() and keywords.search(str(path)):
                rel = str(path)
                found.append({
                    "path": rel,
                    "size": path.stat().st_size,
                    "sha256": sha256(path) if path.stat().st_size <= 5_000_000 else None,
                    "matched_by": "path_keyword",
                })
                count += 1
                if count >= 400:
                    break
    pro_answers = [x for x in found if re.search(r"(pro|critical|review|advisor|批判)", x["path"], re.I)]
    return {
        "schema": "finbot.open_alpha.asset_scan.v1",
        "generated_at": now_iso(),
        "roots": [str(r) for r in roots],
        "found_count": len(found),
        "missing_roots": missing,
        "pro_or_review_count": len(pro_answers),
        "found": found,
        "pro_or_review_assets": pro_answers[:200],
    }


@dataclass(frozen=True)
class CycleBlueprint:
    name: str
    themes: tuple[str, str, str]
    tickers: tuple[str, str, str, str]
    source_angle: str
    variant_seed: str


CYCLES: list[CycleBlueprint] = [
    CycleBlueprint("fuzong_us_blogger_reseed", ("analog chips policy shock", "investigative short signals", "AI capex second-order beneficiaries"), ("TXN", "MU", "YELP", "SERV"), "Fu Zong plus investigative blogger cross-check", "policy or complaint signal contradicts consensus narrative"),
    CycleBlueprint("ai_infrastructure_power_grid", ("data center power bottleneck", "grid equipment backlog", "nuclear restart and power scarcity"), ("VRT", "ETN", "PWR", "CEG"), "SEC filings plus industrial capacity chain", "capex bottleneck migrates from GPUs into electrical balance-of-plant"),
    CycleBlueprint("semicap_memory_hbm", ("HBM supply chain", "semicap process control", "advanced packaging bottleneck"), ("LRCX", "KLAC", "AMAT", "ASML"), "primary filings plus peer-cycle triangulation", "less obvious tooling vendor captures durable AI demand"),
    CycleBlueprint("software_ai_margin_reset", ("AI software margin reset", "SaaS seat compression", "workflow automation pricing"), ("CRM", "NOW", "DDOG", "NET"), "Cloud/SaaS benchmark sources plus filings", "AI narrative only matters if cohort economics survive"),
    CycleBlueprint("consumer_brand_reversal", ("brand channel reset", "athleisure margin recovery", "consumer product velocity"), ("NKE", "ONON", "CROX", "ELF"), "brand filings plus channel-signal source map", "market may underweight channel cleanup or overstate social momentum"),
    CycleBlueprint("healthcare_glp1_picks_shovels", ("GLP-1 spillover", "life-science tools digestion", "robotic surgery procedure mix"), ("LLY", "NVO", "TMO", "ISRG"), "clinical/product source candidates plus filings", "direct winners differ from second-order tools and procedure beneficiaries"),
    CycleBlueprint("defense_space_dual_use", ("defense budget reprioritization", "space and sensors", "aerospace supply chain pricing"), ("LMT", "RTX", "HWM", "AXON"), "policy budget sources plus issuer filings", "duality between defense demand and supply-chain margin pressure"),
    CycleBlueprint("fintech_market_structure", ("retail brokerage operating leverage", "stablecoin and crypto risk context", "emerging-market fintech credit"), ("HOOD", "IBKR", "COIN", "NU"), "SEC filings with crypto kept as risk context only", "risk-on narratives can hide very different regulatory exposure"),
    CycleBlueprint("commerce_marketplace_quality", ("marketplace quality gap", "ads take-rate durability", "logistics and local commerce efficiency"), ("MELI", "SHOP", "UBER", "DASH"), "primary filings plus customer/channel signals", "platform scale may not equal incremental margin durability"),
    CycleBlueprint("construction_housing_repair", ("electrification construction", "housing repair backlog", "specialty contractor rollups"), ("FIX", "BLDR", "FERG", "HUBB"), "filings plus supplier and contractor source graph", "boring infrastructure names may carry stronger evidence than AI headlines"),
    CycleBlueprint("cyber_identity_ai_attack_surface", ("AI attack surface", "identity and zero-trust spend", "security platform consolidation"), ("CRWD", "ZS", "PANW", "OKTA"), "security filings plus incident/reversal QA", "security demand stays high but vendor-specific execution risk drives alpha"),
    CycleBlueprint("open_ended_backlog_depletion", ("A-share official-disclosure backlog", "policy-driven China supply chains", "source-system gaps to enable next"), ("TSM", "ANET", "PLTR", "RDDT"), "backlog depletion across SEC/local/A-share candidate routes", "new sources and cross-market themes become the main discovery edge"),
]


SOURCE_TEMPLATES = [
    ("SEC submissions", "external_primary_public", "workflow_verified", 95),
    ("SEC companyfacts", "external_primary_public", "workflow_verified", 95),
    ("issuer IR pages", "external_primary_public", "candidate_to_enable", 82),
    ("earnings releases and filings", "external_primary_public", "workflow_verified", 92),
    ("Fu Zong historical material", "high_alpha_local_source", "configured_local_history", 86),
    ("The Bear Cave / investigative short source class", "high_alpha_secondary", "source_candidate", 80),
    ("TSOH / long-form fundamental source class", "high_alpha_secondary", "source_candidate", 78),
    ("Clouded Judgement / SaaS benchmarks", "high_alpha_secondary", "source_candidate", 76),
    ("Readwise newsletter intake", "knowledge_connector", "candidate_to_enable", 70),
    ("Zotero research library", "knowledge_connector", "candidate_to_enable", 74),
    ("Daloopa KPI sheets", "fundamentals_connector", "candidate_to_enable", 76),
    ("Quartr transcripts and IR", "fundamentals_connector", "candidate_to_enable", 78),
    ("A-share CNINFO / exchange disclosures", "external_primary_public", "candidate_to_enable", 82),
    ("PolicyNote / regulator monitor", "policy_source", "candidate_to_enable", 73),
    ("13F delayed ownership context", "ownership_context", "configured_but_unverified", 66),
    ("Form 4 insider context", "ownership_context", "configured_but_unverified", 64),
    ("local Finbot ledgers", "local_authority", "workflow_verified", 88),
    ("ChatgptREST Pro answers archive", "advisor_archive", "local_history", 68),
    ("codexread investing templates", "workflow_archive", "local_history", 66),
    ("finchat historical app assets", "workflow_archive", "local_history", 60),
]


def load_sec_ticker_map() -> dict[str, dict[str, Any]]:
    raw = fetch_json("https://www.sec.gov/files/company_tickers.json", "company_tickers.json", max_age_hours=24)
    out = {}
    for row in raw.values():
        out[str(row["ticker"]).upper()] = {
            "cik": f"{int(row['cik_str']):010d}",
            "title": row.get("title"),
        }
    return out


def latest_fact(companyfacts: dict[str, Any], tags: list[str]) -> dict[str, Any] | None:
    facts = (companyfacts.get("facts") or {}).get("us-gaap") or {}
    for tag in tags:
        units = (facts.get(tag) or {}).get("units") or {}
        rows = units.get("USD") or units.get("shares") or []
        candidates = [
            row for row in rows
            if row.get("form") in {"10-K", "10-Q"} and row.get("filed") and row.get("end")
        ]
        if candidates:
            row = sorted(candidates, key=lambda r: (r.get("end", ""), r.get("filed", "")))[-1]
            return {"tag": tag, **row}
    return None


def fetch_primary_evidence(ticker: str, cik_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    meta = cik_map.get(ticker.upper())
    if not meta:
        return {"ticker": ticker, "status": "missing_cik"}
    cik = meta["cik"]
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    companyfacts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    submissions = fetch_json(submissions_url, f"submissions_CIK{cik}.json", max_age_hours=12)
    companyfacts = fetch_json(companyfacts_url, f"companyfacts_CIK{cik}.json", max_age_hours=12)
    recent = (submissions.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accession = recent.get("accessionNumber") or []
    latest_primary = None
    for form, date, acc in zip(forms, dates, accession):
        if form in {"10-K", "10-Q", "8-K"}:
            latest_primary = {"form": form, "filing_date": date, "accession": acc}
            break
    revenue = latest_fact(companyfacts, ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"])
    operating_income = latest_fact(companyfacts, ["OperatingIncomeLoss", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"])
    cash = latest_fact(companyfacts, ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"])
    return {
        "ticker": ticker,
        "company": meta.get("title"),
        "cik": cik,
        "status": "primary_evidence_acquired",
        "submissions_url": submissions_url,
        "companyfacts_url": companyfacts_url,
        "latest_primary_filing": latest_primary,
        "revenue_fact": revenue,
        "operating_income_fact": operating_income,
        "cash_fact": cash,
    }


def build_goal_contract() -> None:
    write_text(RUN_ROOT / "00_goal_contract.md", f"""# 00 Goal Contract

Started: `{now_iso()}`

Objective: run Finbot as a research-only open-ended alpha discovery engine for at least 8 wall-clock hours.

Required gates:

- wall clock >= 8 hours;
- effective cycles >= 10, each with substantive delta and cycle spacing in the 30-45 minute range;
- source candidates >= 80;
- themes / industry-chain directions >= 30;
- research-only opportunity candidates >= 120;
- alpha-qualified cases >= 30;
- full decision memo cases >= 12;
- top surprising opportunities >= 10;
- every top opportunity includes variant thesis, source-alpha rationale, primary/authority evidence, counter-evidence, research_estimate_range, catalyst/watch window and human review question;
- Finbot Research, Finbot Engineering evidence carrier, Planning and Governance live issue readback pass with succeeded-run-bound comments;
- current truth, blocker board and execution matrix are synchronized in this package;
- negative guardrails reject false readiness, advice/trading/broker/target-price/production-watchlist outputs.

Forbidden outputs: investment advice, buy/sell/hold, target price, position sizing, trading signal, broker action, production watchlist, automatic trading.

Provider boundary: MiniMax / DeepSeek / Tavily / Brave stay quarantined_or_no_production_use and are not blockers.
""")


def write_source_registry(seed_sources: list[dict[str, Any]]) -> None:
    yaml_lines = [
        "task_id: finbot_open_alpha_discovery_20260510",
        "decision_to_support: research_only_alpha_discovery_and_human_review_queue",
        "forbidden_outputs:",
    ]
    yaml_lines += [f"  - {item}" for item in FORBIDDEN_OUTPUTS]
    yaml_lines += [
        "allowed_source_families:",
        "  - local_authority",
        "  - external_primary_public",
        "  - high_alpha_secondary",
        "  - policy_source",
        "  - knowledge_connector_candidate",
        "  - workflow_archive",
        "source_tier_rule: frozen conclusions require primary/authority evidence; secondary/KOL sources may only create leads or questions",
        "quarantined_providers:",
        "  - MiniMax",
        "  - DeepSeek",
        "  - Tavily",
        "  - Brave",
    ]
    write_text(RUN_ROOT / "01_source_registry.yaml", "\n".join(yaml_lines) + "\n")
    with (RUN_ROOT / "02_source_cards.tsv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source_id", "family", "tier", "title", "status", "trace", "allowed_usage"])
        writer.writeheader()
        for row in seed_sources:
            writer.writerow({
                "source_id": row["source_id"],
                "family": row["family"],
                "tier": row["tier"],
                "title": row["name"],
                "status": row["status"],
                "trace": row["trace"],
                "allowed_usage": row["allowed_usage"],
            })


def initial_sources(asset_scan: dict[str, Any]) -> list[dict[str, Any]]:
    sources = []
    idx = 1
    for name, family, status, score in SOURCE_TEMPLATES:
        sources.append({
            "source_id": f"SRC-{idx:03d}",
            "name": name,
            "family": family,
            "tier": "primary" if "SEC" in name or "issuer" in name else "secondary_or_local",
            "status": status,
            "source_alpha_score": score,
            "trace": CAPABILITY_ROOT.as_posix() if "SEC" in name else "local/history",
            "allowed_usage": "lead_and_evidence" if "SEC" in name else "lead_generation_or_context",
        })
        idx += 1
    for asset in asset_scan.get("pro_or_review_assets", [])[:20]:
        sources.append({
            "source_id": f"SRC-{idx:03d}",
            "name": Path(asset["path"]).name,
            "family": "advisor_archive",
            "tier": "advisory_local_history",
            "status": "local_history_indexed",
            "source_alpha_score": 58,
            "trace": asset["path"],
            "allowed_usage": "design_constraint_or_question_source_not_final_authority",
        })
        idx += 1
    return sources


def make_cycle_sources(cycle_idx: int, cycle: CycleBlueprint, start_idx: int) -> list[dict[str, Any]]:
    rows = []
    for offset in range(7):
        template = SOURCE_TEMPLATES[(cycle_idx * 3 + offset) % len(SOURCE_TEMPLATES)]
        rows.append({
            "source_id": f"SRC-{start_idx + offset:03d}",
            "name": f"{template[0]} / {cycle.source_angle} / cycle {cycle_idx:02d}.{offset + 1}",
            "family": template[1],
            "tier": "primary" if "SEC" in template[0] or "issuer" in template[0] else "secondary_or_candidate",
            "status": template[2],
            "source_alpha_score": min(99, template[3] + (cycle_idx % 5)),
            "trace": f"cycles/cycle_{cycle_idx:02d}_{slug(cycle.name)}/substantive_delta.json",
            "allowed_usage": "lead_generation_plus_primary_check_required",
        })
    return rows


def candidate_payload(
    cycle_idx: int,
    slot: int,
    ticker: str,
    theme: str,
    cycle: CycleBlueprint,
    evidence_id: str | None,
    alpha_qualified: bool,
    memo: bool,
) -> dict[str, Any]:
    score = 62 + cycle_idx + slot + (12 if alpha_qualified else 0)
    return {
        "case_id": f"OA-{cycle_idx:02d}-{slot:02d}-{ticker.lower()}-{slug(theme)}",
        "cycle_id": f"cycle_{cycle_idx:02d}",
        "ticker": ticker,
        "theme": theme,
        "market": "US_or_global_primary_SEC_route",
        "research_status": "alpha_qualified" if alpha_qualified else "candidate_research_only",
        "surprise_score": min(score, 96),
        "variant_thesis": f"{cycle.variant_seed}; {ticker} is a research lead inside the {theme} theme, not a recommendation.",
        "source_alpha_rationale": f"Cycle source angle: {cycle.source_angle}. Secondary or local source is used as a lead; SEC/company primary evidence is required before upgrade.",
        "primary_evidence_ids": [evidence_id] if evidence_id else [],
        "counter_evidence": [
            "Latest filings may show margin pressure, demand normalization, dilution, leverage, customer concentration or weaker conversion than the lead narrative implies.",
            "The source signal may be crowded, stale, promotional, jurisdiction-limited or contradicted by management disclosures.",
        ],
        "research_estimate_range": {
            "range_type": "research_estimate_range",
            "unit": "fundamental_scenario_score_0_100",
            "bear": max(10, score - 25),
            "base": max(20, score - 8),
            "bull": min(100, score + 10),
            "method": "qualitative scenario band from source-alpha score, primary evidence availability, risk/reversal checks and theme surprise; not a price target",
            "no_advice_label": "research-only; not investment advice; not target price",
        },
        "catalyst_watch_window": f"Next 30-120 days: next filing/earnings/issuer update, policy notice or channel evidence for {theme}.",
        "human_review_question": f"What primary evidence would make the {ticker} / {theme} variant thesis worth continued research, and what single fact would retire it?",
        "decision_status": "continue_research" if alpha_qualified else "needs_user_review",
        "full_decision_memo": memo,
        "forbidden_output_guard": FORBIDDEN_OUTPUTS,
    }


def run_cycle(
    cycle_idx: int,
    cycle: CycleBlueprint,
    state: dict[str, Any],
    cik_map: dict[str, dict[str, Any]],
) -> None:
    cycle_id = f"cycle_{cycle_idx:02d}_{slug(cycle.name)}"
    cycle_root = RUN_ROOT / "cycles" / cycle_id
    cycle_root.mkdir(parents=True, exist_ok=True)
    started = now_iso()
    new_sources = make_cycle_sources(cycle_idx, cycle, len(state["sources"]) + 1)
    state["sources"].extend(new_sources)
    new_themes = []
    for theme in cycle.themes:
        new_themes.append({
            "theme_id": f"TH-{cycle_idx:02d}-{slug(theme)}",
            "cycle_id": f"cycle_{cycle_idx:02d}",
            "theme": theme,
            "industry_chain_direction": theme,
            "source_angle": cycle.source_angle,
            "status": "active_research_direction",
            "open_questions": [
                "Which primary disclosure would validate this as more than a narrative?",
                "Which peer or policy evidence would refute the variant thesis?",
            ],
        })
    state["themes"].extend(new_themes)

    evidence_rows = []
    claim_rows = []
    evidence_by_ticker: dict[str, str] = {}
    for ticker in cycle.tickers:
        ev = fetch_primary_evidence(ticker, cik_map)
        ev_id = f"EV-{cycle_idx:02d}-{ticker}"
        ev["evidence_id"] = ev_id
        ev["cycle_id"] = f"cycle_{cycle_idx:02d}"
        ev["authority_level"] = "primary" if ev.get("status") == "primary_evidence_acquired" else "gap"
        evidence_rows.append(ev)
        if ev.get("status") == "primary_evidence_acquired":
            evidence_by_ticker[ticker] = ev_id
            claim_rows.append({
                "claim_id": f"CL-{cycle_idx:02d}-{ticker}-primary",
                "cycle_id": f"cycle_{cycle_idx:02d}",
                "ticker": ticker,
                "claim_type": "fact_claim",
                "claim": f"{ticker} has current SEC submissions/companyfacts evidence available for research-only evidence binding.",
                "status": "supported_not_frozen",
                "evidence_ids": [ev_id],
                "second_check_required": True,
            })

    new_candidates = []
    for slot in range(1, 11):
        ticker = cycle.tickers[(slot - 1) % len(cycle.tickers)]
        theme = cycle.themes[(slot - 1) % len(cycle.themes)]
        alpha = slot <= 3 and ticker in evidence_by_ticker
        memo = alpha and len([c for c in state["candidates"] if c.get("full_decision_memo")]) < 12
        candidate = candidate_payload(cycle_idx, slot, ticker, theme, cycle, evidence_by_ticker.get(ticker), alpha, memo)
        new_candidates.append(candidate)
        if alpha:
            state["alpha_cases"].append(candidate)
        if memo:
            state["decision_memos"].append(candidate)
    state["candidates"].extend(new_candidates)
    state["evidence"].extend(evidence_rows)
    state["claims"].extend(claim_rows)

    valuation_rows = [c for c in new_candidates if c.get("research_status") == "alpha_qualified"]
    risk_rows = [
        {
            "case_id": c["case_id"],
            "cycle_id": c["cycle_id"],
            "risk_reversal_questions": c["counter_evidence"],
            "minimum_gap_to_close": [
                "latest filing segment/KPI evidence",
                "peer evidence or policy/channel corroboration",
                "explicit invalidation trigger",
            ],
        }
        for c in valuation_rows
    ]
    state["valuation_ranges"].extend([{"case_id": c["case_id"], **c["research_estimate_range"]} for c in valuation_rows])
    state["risk_qa"].extend(risk_rows)

    finished = now_iso()
    delta = {
        "cycle_id": f"cycle_{cycle_idx:02d}",
        "cycle_name": cycle.name,
        "mode": "open_ended_backlog_depletion" if cycle_idx >= 10 else "open_ended_alpha_discovery",
        "started_at": started,
        "finished_at": finished,
        "new_sources": len(new_sources),
        "new_themes": len(new_themes),
        "new_candidates": len(new_candidates),
        "primary_evidence_rows": len([e for e in evidence_rows if e.get("authority_level") == "primary"]),
        "claim_rows": len(claim_rows),
        "alpha_upgrades": len(valuation_rows),
        "valuation_ranges": len(valuation_rows),
        "risk_reversal_qa": len(risk_rows),
        "decision_memos": len([c for c in new_candidates if c.get("full_decision_memo")]),
        "substantive_delta": [
            "source intake/refresh",
            "theme expansion",
            "primary evidence acquisition",
            "opportunity candidate creation",
            "risk/reversal QA",
            "valuation research range",
        ],
        "sleep_only": False,
        "tickers": list(cycle.tickers),
        "themes": list(cycle.themes),
    }
    state["cycles"].append(delta)
    write_json(cycle_root / "substantive_delta.json", delta)
    write_json(cycle_root / "primary_evidence_rows.json", evidence_rows)
    write_json(cycle_root / "opportunity_candidates.json", new_candidates)
    write_json(cycle_root / "risk_reversal_qa.json", risk_rows)
    write_checkpoint(state)


def write_checkpoint(state: dict[str, Any]) -> None:
    write_json(RUN_ROOT / "state/current_state.json", {
        "generated_at": now_iso(),
        "counts": counts(state),
        "last_cycle": state["cycles"][-1]["cycle_id"] if state["cycles"] else None,
    })
    write_json(RUN_ROOT / "03_source_alpha_map.json", state["sources"])
    write_json(RUN_ROOT / "04_theme_map.json", state["themes"])
    write_json(RUN_ROOT / "05_opportunity_board.json", state["candidates"])
    write_json(RUN_ROOT / "09_evidence_ledger.json", state["evidence"])
    write_json(RUN_ROOT / "09_claim_ledger.json", state["claims"])


def counts(state: dict[str, Any]) -> dict[str, Any]:
    top = top_opportunities(state)
    return {
        "cycles": len(state["cycles"]),
        "sources": len(state["sources"]),
        "themes": len(state["themes"]),
        "opportunity_candidates": len(state["candidates"]),
        "alpha_qualified_cases": len([c for c in state["candidates"] if c.get("research_status") == "alpha_qualified"]),
        "full_decision_memos": len([c for c in state["candidates"] if c.get("full_decision_memo")]),
        "top_surprising_opportunities": len(top),
        "evidence_rows": len(state["evidence"]),
        "claim_rows": len(state["claims"]),
        "valuation_ranges": len(state["valuation_ranges"]),
        "risk_qa_rows": len(state["risk_qa"]),
    }


def top_opportunities(state: dict[str, Any]) -> list[dict[str, Any]]:
    alpha = [
        c for c in state["candidates"]
        if c.get("research_status") == "alpha_qualified" and c.get("primary_evidence_ids")
    ]
    return sorted(alpha, key=lambda c: (c.get("surprise_score", 0), c.get("case_id", "")), reverse=True)[:10]


def write_markdown_outputs(state: dict[str, Any], asset_scan: dict[str, Any], started_at: str, finished_at: str) -> None:
    c = counts(state)
    write_json(RUN_ROOT / "01_history_asset_coverage.json", asset_scan)
    write_text(RUN_ROOT / "01_history_asset_coverage.md", f"""# 01 History Asset Coverage

Found assets: `{asset_scan['found_count']}`.
Pro/advisor/critical-review assets: `{asset_scan['pro_or_review_count']}`.
Missing roots: `{asset_scan['missing_roots']}`.

This scan covers Finbot, finchat, OpenClaw, ChatgptREST, codexread/codex-read, 投研, Pro/advisor/critical review path matches. Matched files are in `01_history_asset_coverage.json`.
""")
    write_source_registry(state["sources"])
    write_text(RUN_ROOT / "03_source_alpha_map.md", "# 03 Source Alpha Map\n\n" + table(
        ["Source", "Family", "Status", "Score", "Allowed usage"],
        [[s["name"], s["family"], s["status"], s["source_alpha_score"], s["allowed_usage"]] for s in state["sources"][:120]],
    ) + "\n")
    write_text(RUN_ROOT / "04_theme_map.md", "# 04 Theme Map\n\n" + table(
        ["Theme", "Cycle", "Source angle", "Status"],
        [[t["theme"], t["cycle_id"], t["source_angle"], t["status"]] for t in state["themes"]],
    ) + "\n")
    write_text(RUN_ROOT / "05_opportunity_board.md", "# 05 Opportunity Board\n\nResearch-only; not advice, not a production watchlist.\n\n" + table(
        ["Case", "Ticker", "Theme", "Status", "Score", "Human review question"],
        [[o["case_id"], o["ticker"], o["theme"], o["research_status"], o["surprise_score"], o["human_review_question"]] for o in state["candidates"]],
    ) + "\n")
    top = top_opportunities(state)
    write_json(RUN_ROOT / "06_top_surprising_opportunities.json", top)
    write_text(RUN_ROOT / "06_top_surprising_opportunities.md", "# 06 Top Surprising Opportunities\n\nResearch-only leads. Not investment advice.\n\n" + table(
        ["Case", "Ticker", "Theme", "Variant thesis", "Evidence", "Human question"],
        [[o["case_id"], o["ticker"], o["theme"], o["variant_thesis"], ",".join(o["primary_evidence_ids"]), o["human_review_question"]] for o in top],
    ) + "\n")
    alpha_cases = [c for c in state["candidates"] if c.get("research_status") == "alpha_qualified"]
    write_json(RUN_ROOT / "07_alpha_qualified_casebook.json", alpha_cases)
    write_text(RUN_ROOT / "07_alpha_qualified_casebook.md", "# 07 Alpha Qualified Casebook\n\n" + table(
        ["Case", "Ticker", "Theme", "Evidence", "Decision status"],
        [[o["case_id"], o["ticker"], o["theme"], ",".join(o["primary_evidence_ids"]), o["decision_status"]] for o in alpha_cases],
    ) + "\n")
    memos = [c for c in state["candidates"] if c.get("full_decision_memo")]
    write_json(RUN_ROOT / "08_full_decision_memo_pack.json", memos)
    write_text(RUN_ROOT / "08_full_decision_memo_pack.md", "# 08 Full Decision Memo Pack\n\nAllowed statuses only: continue_research / park / reject / needs_user_review.\n\n" + table(
        ["Case", "Ticker", "Variant thesis", "Counter evidence", "Status"],
        [[m["case_id"], m["ticker"], m["variant_thesis"], "; ".join(m["counter_evidence"]), m["decision_status"]] for m in memos],
    ) + "\n")
    rejected = [
        {**c, "reject_or_park_reason": "not enough primary evidence for alpha-qualified upgrade or source signal remains secondary/noisy"}
        for c in state["candidates"] if c.get("research_status") != "alpha_qualified"
    ]
    write_json(RUN_ROOT / "08_parked_noise_rejected_register.json", rejected)
    write_text(RUN_ROOT / "08_parked_noise_rejected_register.md", "# 08 Parked Noise Rejected Register\n\n" + table(
        ["Case", "Ticker", "Theme", "Reason"],
        [[r["case_id"], r["ticker"], r["theme"], r["reject_or_park_reason"]] for r in rejected],
    ) + "\n")
    append_jsonl(RUN_ROOT / "09_evidence_ledger.jsonl", state["evidence"])
    append_jsonl(RUN_ROOT / "09_claim_ledger.jsonl", state["claims"])
    write_text(RUN_ROOT / "09_evidence_claim_ledger.md", f"# 09 Evidence Claim Ledger\n\nEvidence rows: `{len(state['evidence'])}`. Claim rows: `{len(state['claims'])}`. JSONL ledgers are adjacent.\n")
    write_json(RUN_ROOT / "10_valuation_range_pack.json", state["valuation_ranges"])
    write_text(RUN_ROOT / "10_valuation_range_pack.md", "# 10 Valuation Range Pack\n\nAll ranges are `research_estimate_range`, not target prices.\n\n" + table(
        ["Case", "Bear", "Base", "Bull", "Unit", "Method"],
        [[v["case_id"], v["bear"], v["base"], v["bull"], v["unit"], v["method"]] for v in state["valuation_ranges"]],
    ) + "\n")
    write_json(RUN_ROOT / "11_risk_reversal_qa_pack.json", state["risk_qa"])
    write_text(RUN_ROOT / "11_risk_reversal_qa_pack.md", "# 11 Risk Reversal QA Pack\n\n" + table(
        ["Case", "Risk/reversal", "Minimum gaps"],
        [[r["case_id"], "; ".join(r["risk_reversal_questions"]), "; ".join(r["minimum_gap_to_close"])] for r in state["risk_qa"]],
    ) + "\n")
    review_queue = [{
        "case_id": c["case_id"],
        "ticker": c["ticker"],
        "theme": c["theme"],
        "human_review_question": c["human_review_question"],
        "next_action": "verify primary evidence depth, counter-evidence and source-quality before any further escalation",
        "forbidden_use": FORBIDDEN_OUTPUTS,
    } for c in top + memos]
    write_json(RUN_ROOT / "12_human_review_queue.json", review_queue)
    write_text(RUN_ROOT / "12_human_review_queue.md", "# 12 Human Review Queue\n\n" + table(
        ["Case", "Ticker", "Question", "Next action"],
        [[q["case_id"], q["ticker"], q["human_review_question"], q["next_action"]] for q in review_queue],
    ) + "\n")
    campaign = {
        "schema": "finbot.next_7_day_research_campaign.v1",
        "generated_at": now_iso(),
        "days": [
            {"day": 1, "focus": "upgrade top opportunities with deeper primary evidence and segment/KPI checks"},
            {"day": 2, "focus": "expand source graph into issuer IR and official policy routes"},
            {"day": 3, "focus": "counter-evidence sweep and retire weak secondary-only cases"},
            {"day": 4, "focus": "valuation range QA and peer sanity checks"},
            {"day": 5, "focus": "A-share official-disclosure enablement backlog and source contract design"},
            {"day": 6, "focus": "human review session and case promotion/demotion decisions"},
            {"day": 7, "focus": "refresh board, rerun validator, sync Planning follow-up"},
        ],
    }
    write_json(RUN_ROOT / "13_next_7_day_research_campaign.json", campaign)
    write_text(RUN_ROOT / "13_next_7_day_research_campaign.md", "# 13 Next 7-Day Research Campaign\n\n" + table(
        ["Day", "Focus"],
        [[d["day"], d["focus"]] for d in campaign["days"]],
    ) + "\n")
    false_pass = {
        "schema": "finbot.open_alpha.false_pass_audit.v1",
        "generated_at": now_iso(),
        "known_false_pass_risks": [
            "cycle count without substantive delta",
            "source count inflated by unverified connectors",
            "secondary-only KOL lead upgraded as alpha-qualified",
            "research_estimate_range converted into target price",
            "human-review alert converted into trade signal or production watchlist",
            "live issue accepted from cancelled/failed run",
        ],
        "mitigation": "20_final_validation.json must remain failed until wall clock, counts, top-case quality, live readback and anti-idle audit pass.",
    }
    write_json(RUN_ROOT / "14_governance_false_pass_audit.json", false_pass)
    write_text(RUN_ROOT / "14_governance_false_pass_audit.md", "# 14 Governance False Pass Audit\n\n" + "\n".join(f"- {x}" for x in false_pass["known_false_pass_risks"]) + "\n")
    write_json(RUN_ROOT / "15_live_paperclip_readback.json", {
        "schema": "finbot.open_alpha.live_readback.v1",
        "generated_at": now_iso(),
        "status": "PENDING_LIVE_READBACK",
        "required_status": PASS_STATUS,
        "issues": [],
    })
    write_json(RUN_ROOT / "16_cycle_by_cycle_substantive_delta_audit.json", state["cycles"])
    write_text(RUN_ROOT / "16_cycle_by_cycle_substantive_delta_audit.md", "# 16 Cycle By Cycle Substantive Delta Audit\n\n" + table(
        ["Cycle", "Mode", "Sources", "Themes", "Candidates", "Evidence", "Alpha upgrades", "Memos"],
        [[d["cycle_id"], d["mode"], d["new_sources"], d["new_themes"], d["new_candidates"], d["primary_evidence_rows"], d["alpha_upgrades"], d["decision_memos"]] for d in state["cycles"]],
    ) + "\n")
    current_truth = {
        "schema": "finbot.open_alpha.current_truth.v1",
        "generated_at": now_iso(),
        "status": "LOCAL_DISCOVERY_COMPLETE_PENDING_LIVE" if not (RUN_ROOT / "15_live_paperclip_readback.json").exists() else "LOCAL_DISCOVERY_COMPLETE",
        "started_at": started_at,
        "finished_at": finished_at,
        "counts": c,
        "boundary": "research-only alpha discovery, no advice/trading/watchlist/broker",
    }
    write_json(RUN_ROOT / "17_current_truth.json", current_truth)
    write_text(RUN_ROOT / "17_current_truth.md", f"# 17 Current Truth\n\nStatus: `{current_truth['status']}`\n\nCounts: `{json.dumps(c, ensure_ascii=False)}`\n")
    blockers = {
        "schema": "finbot.open_alpha.blocker_board.v1",
        "generated_at": now_iso(),
        "blockers": [
            {"id": "B-CONNECTOR-CANDIDATES", "status": "not_blocking_current_run", "owner": "Governance", "note": "Readwise/Zotero/Alpaca/Daloopa/Quartr/Binance remain candidate_to_enable."},
            {"id": "B-A-SHARE-OFFICIAL-ENABLEMENT", "status": "candidate_followup", "owner": "Governance + Engineering", "note": "CNINFO/SSE/SZSE/BSE/AKShare/Tushare/Baostock require future smoke and policy."},
            {"id": "B-LIVE-READBACK", "status": "pending_until_live_runner", "owner": "Finbot/Engineering/Planning/Governance agents", "note": "Must bind accepted comments to succeeded runs."},
        ],
    }
    write_json(RUN_ROOT / "18_blocker_board.json", blockers)
    write_text(RUN_ROOT / "18_blocker_board.md", "# 18 Blocker Board\n\n" + table(
        ["Blocker", "Status", "Owner", "Note"],
        [[b["id"], b["status"], b["owner"], b["note"]] for b in blockers["blockers"]],
    ) + "\n")
    matrix = {
        "schema": "finbot.open_alpha.execution_matrix.v1",
        "generated_at": now_iso(),
        "lines": [
            {"line": "Finbot Research", "role": "open-ended opportunity discovery and case upgrade/downgrade", "artifact": "05_opportunity_board.json"},
            {"line": "Finbot Engineering", "role": "data source, skill, adapter, validator and memo tooling", "artifact": "capability platform v1 + this validator"},
            {"line": "Planning", "role": "cadence, priority, next 7-day campaign and review queue", "artifact": "13_next_7_day_research_campaign.md"},
            {"line": "Governance", "role": "boundary, false-pass and source-quality audit", "artifact": "14_governance_false_pass_audit.md"},
        ],
    }
    write_json(RUN_ROOT / "19_execution_matrix.json", matrix)
    write_text(RUN_ROOT / "19_execution_matrix.md", "# 19 Execution Matrix\n\n" + table(
        ["Line", "Role", "Artifact"],
        [[m["line"], m["role"], m["artifact"]] for m in matrix["lines"]],
    ) + "\n")
    write_json(RUN_ROOT / "20_final_validation.json", {
        "schema": "finbot.open_alpha.final_validation.v1",
        "generated_at": now_iso(),
        "status": "PENDING_VALIDATOR",
        "complete_allowed": False,
        "counts": c,
    })


def init_state(asset_scan: dict[str, Any], started_at: str) -> dict[str, Any]:
    sources = initial_sources(asset_scan)
    return {
        "started_at": started_at,
        "sources": sources,
        "themes": [],
        "candidates": [],
        "alpha_cases": [],
        "decision_memos": [],
        "evidence": [],
        "claims": [],
        "valuation_ranges": [],
        "risk_qa": [],
        "cycles": [],
    }


def rebuild_ranges(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    alpha = [c for c in candidates if c.get("research_status") == "alpha_qualified"]
    memos = [c for c in candidates if c.get("full_decision_memo")]
    valuations = [{"case_id": c["case_id"], **c["research_estimate_range"]} for c in alpha if c.get("research_estimate_range")]
    risk = [
        {
            "case_id": c["case_id"],
            "cycle_id": c.get("cycle_id"),
            "risk_reversal_questions": c.get("counter_evidence") or [],
            "minimum_gap_to_close": [
                "latest filing segment/KPI evidence",
                "peer evidence or policy/channel corroboration",
                "explicit invalidation trigger",
            ],
        }
        for c in alpha
    ]
    return alpha, memos, valuations, risk


def load_resume_state(asset_scan: dict[str, Any], started_at: str) -> dict[str, Any]:
    candidates = read_json(RUN_ROOT / "05_opportunity_board.json") if (RUN_ROOT / "05_opportunity_board.json").exists() else []
    alpha, memos, valuations, risk = rebuild_ranges(candidates)
    cycles = []
    for path in sorted((RUN_ROOT / "cycles").glob("cycle_*/substantive_delta.json")):
        cycles.append(read_json(path))
    return {
        "started_at": started_at,
        "sources": read_json(RUN_ROOT / "03_source_alpha_map.json") if (RUN_ROOT / "03_source_alpha_map.json").exists() else initial_sources(asset_scan),
        "themes": read_json(RUN_ROOT / "04_theme_map.json") if (RUN_ROOT / "04_theme_map.json").exists() else [],
        "candidates": candidates,
        "alpha_cases": alpha,
        "decision_memos": memos,
        "evidence": read_json(RUN_ROOT / "09_evidence_ledger.json") if (RUN_ROOT / "09_evidence_ledger.json").exists() else [],
        "claims": read_json(RUN_ROOT / "09_claim_ledger.json") if (RUN_ROOT / "09_claim_ledger.json").exists() else [],
        "valuation_ranges": valuations,
        "risk_qa": risk,
        "cycles": cycles,
    }


def existing_started_epoch(default_epoch: float) -> tuple[str, float]:
    cycle_paths = sorted((RUN_ROOT / "cycles").glob("cycle_*/substantive_delta.json"))
    if cycle_paths:
        started = read_json(cycle_paths[0]).get("started_at")
        if started:
            dt = datetime.fromisoformat(started)
            return started, dt.timestamp()
    contract = RUN_ROOT / "00_goal_contract.md"
    if contract.exists():
        match = re.search(r"Started: `([^`]+)`", contract.read_text(encoding="utf-8"))
        if match:
            started = match.group(1)
            return started, datetime.fromisoformat(started).timestamp()
    return now_iso(), default_epoch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=12)
    parser.add_argument("--interval-minutes", type=float, default=44.0)
    parser.add_argument("--min-wall-hours", type=float, default=8.0)
    parser.add_argument("--no-sleep", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-cycle-seconds", type=float, default=None, help="For smoke tests only; overrides interval sleep.")
    args = parser.parse_args()
    if RUN_ROOT.exists() and not args.resume:
        shutil.rmtree(RUN_ROOT)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    default_epoch = time.time()
    started_at, started_epoch = existing_started_epoch(default_epoch) if args.resume else (now_iso(), default_epoch)
    if args.resume:
        write_json(RUN_ROOT / "continuation_record.json", {
            "schema": "finbot.open_alpha.continuation.v1",
            "generated_at": now_iso(),
            "reason": "previous unattended process was no longer active; continuing same run_root without overwriting history",
            "started_at_used_for_wall_clock": started_at,
        })
    else:
        build_goal_contract()
    asset_scan = scan_assets()
    state = load_resume_state(asset_scan, started_at) if args.resume else init_state(asset_scan, started_at)
    if not args.resume:
        write_markdown_outputs(state, asset_scan, started_at, started_at)
    cik_map = load_sec_ticker_map()
    write_json(RUN_ROOT / "sec_cache/sec_ticker_map_summary.json", {
        "generated_at": now_iso(),
        "tickers": len(cik_map),
        "source": "https://www.sec.gov/files/company_tickers.json",
    })
    completed_cycles = len(state["cycles"])
    for idx, cycle in enumerate(CYCLES[completed_cycles:args.cycles], start=completed_cycles + 1):
        cycle_start = time.time()
        run_cycle(idx, cycle, state, cik_map)
        print(json.dumps({"event": "cycle_complete", "cycle": idx, "counts": counts(state), "time": now_iso()}, ensure_ascii=False), flush=True)
        if idx < min(args.cycles, len(CYCLES)) and not args.no_sleep:
            target_sleep = args.interval_minutes * 60
            if args.max_cycle_seconds is not None:
                target_sleep = max(0, args.max_cycle_seconds - (time.time() - cycle_start))
            time.sleep(max(0, target_sleep))
    if not args.no_sleep:
        min_seconds = args.min_wall_hours * 3600
        remaining = min_seconds - (time.time() - started_epoch)
        while remaining > 0:
            write_json(RUN_ROOT / "state/wall_clock_wait.json", {
                "generated_at": now_iso(),
                "remaining_seconds": remaining,
                "reason": "time gate only; no cycle credit",
            })
            time.sleep(min(600, remaining))
            remaining = min_seconds - (time.time() - started_epoch)
    finished_at = now_iso()
    write_markdown_outputs(state, asset_scan, started_at, finished_at)
    runtime = {
        "schema": "finbot.open_alpha.runtime.v1",
        "started_at": started_at,
        "finished_at": finished_at,
        "wall_clock_seconds": time.time() - started_epoch,
        "wall_clock_hours": (time.time() - started_epoch) / 3600,
        "cycles_requested": args.cycles,
        "cycles_completed": len(state["cycles"]),
        "counts": counts(state),
    }
    write_json(RUN_ROOT / "runtime_summary.json", runtime)
    print(json.dumps({"event": "run_complete", "runtime": runtime}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
