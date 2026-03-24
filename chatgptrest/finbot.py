from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from chatgptrest.core.config import AppConfig, load_config
from chatgptrest.dashboard import DashboardService
from chatgptrest.kernel.llm_connector import LLMConfig, LLMConnector

# --- Extracted sub-modules (Phase 5 refactoring) ---
# Re-exported under original underscore-prefixed names for backward compatibility.
# New code should import directly from chatgptrest.finbot_modules.*.
from chatgptrest.finbot_modules.claim_logic import (  # noqa: F401
    stable_claim_id as _stable_claim_id,
    stable_citation_id as _stable_citation_id,
    support_confidence as _support_confidence,
    claim_kind_from_row as _claim_kind_from_row,
    claim_status_from_row as _claim_status_from_row,
    claim_load_bearing as _claim_load_bearing,
    claim_relevance_label as _claim_relevance_label,
    claim_falsification_condition as _claim_falsification_condition,
    has_semantic_reversal as _has_semantic_reversal,
    match_previous_claim as _match_previous_claim,
    annotate_claim_rows as _annotate_claim_rows,
    build_claim_objects as _build_claim_objects,
    _DIRECTION_PAIRS,
    _DIRECTION_REVERSE,
    _ALL_DIRECTION_WORDS,
)
from chatgptrest.finbot_modules.source_scoring import (  # noqa: F401
    source_quality_score as _source_quality_score,
    source_quality_band as _source_quality_band,
    source_contribution_role as _source_contribution_role,
    source_focus as _source_focus,
    source_reason as _source_reason,
    source_information_role as _source_information_role,
)
from chatgptrest.finbot_modules.market_truth import (  # noqa: F401
    infer_market_from_ticker as _infer_market_from_ticker,
)

log = logging.getLogger(__name__)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FINAGENT_ROOT = Path("/vol1/1000/projects/finagent")
DEFAULT_FINAGENT_PYTHON = "python3"
DEFAULT_FINBOT_ROOT = REPO_ROOT / "artifacts" / "finbot"
DEFAULT_THEME_CATALOG_PATH = REPO_ROOT / "config" / "finbot_theme_catalog.json"
DEFAULT_RESEARCH_PACKAGE_MAX_AGE_HOURS = 18
DOSSIER_SCHEMA_VERSION = "3.0"
MULTILANE_SCHEMA_VERSION = "1.0"
SOURCE_SCORE_SCHEMA_VERSION = "2.0"
THEME_STATE_SCHEMA_VERSION = "2.0"


@dataclass(frozen=True)
class InboxItem:
    item_id: str
    created_at: float
    title: str
    summary: str
    category: str
    severity: str
    source: str
    action_hint: str
    payload: dict[str, Any]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "item"


def _normalize_match_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _text_value(value).lower())


def _stable_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def _inbox_item_id(prefix: str, logical_key: str) -> str:
    return f"{prefix}-{_slugify(logical_key)}"


def _text_value(raw: Any) -> str:
    return str(raw or "").strip()


def _as_float(raw: Any) -> float:
    try:
        return float(raw)
    except Exception:
        return 0.0


def _normalized_claim_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _text_value(value)).strip().lower()


def _decision_distance(value: Any) -> int:
    text = _text_value(value).lower()
    if text in {"act", "action", "invest", "invest_now"}:
        return 0
    if "prepare" in text:
        return 1
    if "watch" in text:
        return 2
    if text in {"review", "review_required", "monitor"}:
        return 3
    if text in {"archive", "archived", "ignore"}:
        return 4
    return 3


def ensure_inbox_dirs(root: Path = DEFAULT_FINBOT_ROOT) -> dict[str, Path]:
    pending = root / "inbox" / "pending"
    archived = root / "inbox" / "archived"
    pending.mkdir(parents=True, exist_ok=True)
    archived.mkdir(parents=True, exist_ok=True)
    return {"root": root, "pending": pending, "archived": archived}


def _extract_logical_key(payload: dict[str, Any]) -> str:
    nested = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    if isinstance(nested, dict):
        for key in ("logical_key", "candidate_id", "theme_slug"):
            value = _text_value(nested.get(key))
            if value:
                return value
        priority_target = nested.get("priority_target") if isinstance(nested.get("priority_target"), dict) else {}
        if isinstance(priority_target, dict):
            for key in ("thesis_id", "target_case_id", "ticker_or_symbol"):
                value = _text_value(priority_target.get(key))
                if value:
                    return value
    return ""


def _archive_path(base_dir: Path, filename: str) -> Path:
    candidate = base_dir / filename
    if not candidate.exists():
        return candidate
    return base_dir / f"{candidate.stem}-{int(time.time())}{candidate.suffix}"


def _candidate_slug(candidate_id: str) -> str:
    return _slugify(candidate_id.replace("candidate_", ""))


def _json_block(raw: str) -> dict[str, Any]:
    text = raw or ""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _markdown_without_json_block(raw: str) -> str:
    text = raw or ""
    return re.sub(r"```json\s*\{.*?\}\s*```", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def _opportunity_dirs(root: Path, candidate_id: str) -> dict[str, Path]:
    candidate_root = root / "opportunities" / _candidate_slug(candidate_id)
    history = candidate_root / "history"
    history.mkdir(parents=True, exist_ok=True)
    return {
        "candidate_root": candidate_root,
        "history": history,
        "latest_json": candidate_root / "latest.json",
        "latest_md": candidate_root / "latest.md",
        "latest_context": candidate_root / "latest_context.json",
    }


def _source_score_dirs(root: Path) -> dict[str, Path]:
    score_root = root / "source_scores"
    history = score_root / "history"
    history.mkdir(parents=True, exist_ok=True)
    return {
        "root": score_root,
        "history": history,
        "latest": score_root / "latest.json",
    }


def _theme_state_dirs(root: Path, theme_slug: str) -> dict[str, Path]:
    theme_root = root / "themes" / _slugify(theme_slug)
    history = theme_root / "history"
    history.mkdir(parents=True, exist_ok=True)
    return {
        "root": theme_root,
        "history": history,
        "latest": theme_root / "latest.json",
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dumps(payload) + "\n", encoding="utf-8")


def _load_latest_research_package(*, root: Path, candidate_id: str) -> dict[str, Any] | None:
    latest = _opportunity_dirs(root, candidate_id)["latest_json"]
    if not latest.exists():
        return None
    payload = _load_json(latest)
    return payload if payload else None


def _package_is_fresh(payload: dict[str, Any] | None, *, max_age_hours: int) -> bool:
    if not payload:
        return False
    generated_at = float(payload.get("generated_at") or 0)
    if generated_at <= 0:
        return False
    return (time.time() - generated_at) < max(1, int(max_age_hours)) * 3600


def _coerce_string_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [_text_value(item) for item in raw if _text_value(item)]
    text = _text_value(raw)
    if not text:
        return []
    parts = re.split(r"[;\n]+", text)
    cleaned = [_text_value(part) for part in parts if _text_value(part)]
    return cleaned or [text]


def _coerce_ranked_expressions(raw: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for index, item in enumerate(raw, start=1):
            if isinstance(item, dict):
                expression = _text_value(
                    item.get("expression")
                    or item.get("name")
                    or item.get("entity")
                    or item.get("ticker")
                )
                if not expression:
                    continue
                rows.append(
                    {
                        "rank": int(item.get("rank") or index),
                        "expression": expression,
                        "role": _text_value(item.get("role") or item.get("type") or item.get("bucket_role")),
                        "why_best": _text_value(item.get("why_best") or item.get("reason") or item.get("why")),
                        "why_not_best": _text_value(item.get("why_not_best") or item.get("why_not_now") or item.get("risk")),
                        "readiness": _text_value(item.get("readiness") or item.get("status") or item.get("recommended_action")),
                        "valuation_anchor": _text_value(item.get("valuation_anchor") or item.get("valuation") or item.get("multiple")),
                        "scenario_base": _text_value(item.get("scenario_base") or item.get("base_case")),
                        "scenario_bull": _text_value(item.get("scenario_bull") or item.get("bull_case")),
                        "scenario_bear": _text_value(item.get("scenario_bear") or item.get("bear_case")),
                    }
                )
            else:
                text = _text_value(item)
                if text:
                    rows.append(
                        {
                            "rank": index,
                            "expression": text,
                            "role": "",
                            "why_best": "",
                            "why_not_best": "",
                            "readiness": "",
                            "valuation_anchor": "",
                            "scenario_base": "",
                            "scenario_bull": "",
                            "scenario_bear": "",
                        }
                    )
    else:
        text = _text_value(raw)
        if text:
            rows.append(
                {
                    "rank": 1,
                    "expression": text,
                    "role": "",
                    "why_best": "",
                    "why_not_best": "",
                    "readiness": "",
                    "valuation_anchor": "",
                    "scenario_base": "",
                    "scenario_bull": "",
                    "scenario_bear": "",
                }
            )
    return rows


def _coerce_claim_ledger(raw: Any) -> list[dict[str, str]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if isinstance(item, dict):
            claim = _text_value(item.get("claim") or item.get("title") or item.get("statement"))
            if not claim:
                continue
            supporting_sources = []
            raw_sources = item.get("supporting_sources")
            if isinstance(raw_sources, list):
                for source in raw_sources:
                    if isinstance(source, dict):
                        name = _text_value(source.get("name") or source.get("source"))
                        if name:
                            supporting_sources.append(
                                {
                                    "name": name,
                                    "detail_href": _text_value(source.get("detail_href") or source.get("href")),
                                    "contribution_role": _text_value(source.get("contribution_role") or source.get("role")),
                                }
                            )
                    else:
                        name = _text_value(source)
                        if name:
                            supporting_sources.append({"name": name, "detail_href": "", "contribution_role": ""})
            rows.append(
                {
                    "claim": claim,
                    "claim_id": _text_value(item.get("claim_id")),
                    "claim_kind": _text_value(item.get("claim_kind")),
                    "status": _text_value(item.get("status")),
                    "supersedes_claim_id": _text_value(item.get("supersedes_claim_id")),
                    "evidence_grade": _text_value(item.get("evidence_grade") or item.get("grade") or item.get("confidence_band")),
                    "importance": _text_value(item.get("importance") or item.get("priority")),
                    "why_it_matters": _text_value(item.get("why_it_matters") or item.get("why") or item.get("implication")),
                    "next_check": _text_value(item.get("next_check") or item.get("next_milestone") or item.get("check")),
                    "falsification_condition": _text_value(item.get("falsification_condition") or item.get("what_breaks") or item.get("disconfirming_signal")),
                    "supporting_sources": supporting_sources,
                    "support_note": _text_value(item.get("support_note") or item.get("source_note")),
                }
            )
        else:
            claim = _text_value(item)
            if claim:
                rows.append(
                    {
                        "claim": claim,
                        "claim_id": "",
                        "claim_kind": "",
                        "status": "",
                        "supersedes_claim_id": "",
                        "evidence_grade": "",
                        "importance": "",
                        "why_it_matters": "",
                        "next_check": "",
                        "falsification_condition": "",
                        "supporting_sources": [],
                        "support_note": "",
                    }
                )
    return rows


def _coerce_risk_register(raw: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if isinstance(item, dict):
            risk = _text_value(item.get("risk") or item.get("name") or item.get("breaker"))
            if not risk:
                continue
            rows.append(
                {
                    "risk": risk,
                    "severity": _text_value(item.get("severity") or item.get("priority")),
                    "horizon": _text_value(item.get("horizon") or item.get("timeframe")),
                    "what_confirms": _text_value(item.get("what_confirms") or item.get("confirm_signal") or item.get("trigger")),
                    "what_refutes": _text_value(item.get("what_refutes") or item.get("relief_signal") or item.get("refute_signal")),
                }
            )
        else:
            risk = _text_value(item)
            if risk:
                rows.append(
                    {
                        "risk": risk,
                        "severity": "",
                        "horizon": "",
                        "what_confirms": "",
                        "what_refutes": "",
                    }
                )
    return rows


def _coerce_valuation_frame(raw: Any, *, market_truth: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    frame: dict[str, Any] = {
        "current_view": _text_value(raw.get("current_view") or raw.get("summary")),
        "base_case": _text_value(raw.get("base_case")),
        "bull_case": _text_value(raw.get("bull_case")),
        "bear_case": _text_value(raw.get("bear_case")),
        "key_variable": _text_value(raw.get("key_variable") or raw.get("swing_factor")),
    }
    if market_truth:
        frame["market_truth"] = market_truth
    return frame


def _default_claim_ledger(*, thesis_name: str, core_claims: list[str], supporting_evidence: list[str], critical_unknowns: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seed_claims = list(core_claims[:3])
    if not seed_claims and thesis_name:
        seed_claims = [thesis_name]
    for index, claim in enumerate(seed_claims, start=1):
        rows.append(
            {
                "claim": claim,
                "evidence_grade": "medium" if supporting_evidence else "low",
                "importance": "high" if index == 1 else "medium",
                "why_it_matters": supporting_evidence[0] if supporting_evidence else "",
                "next_check": critical_unknowns[0] if critical_unknowns else "",
            }
        )
    return rows


def _default_risk_register(*, thesis_breakers: list[str], timing_risks: list[str], disconfirming_signals: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    primary = thesis_breakers or timing_risks or disconfirming_signals
    for index, risk in enumerate(primary[:3], start=1):
        rows.append(
            {
                "risk": risk,
                "severity": "high" if index == 1 else "medium",
                "horizon": "near_term" if risk in timing_risks else "thesis",
                "what_confirms": disconfirming_signals[0] if disconfirming_signals else "",
                "what_refutes": "",
            }
        )
    return rows


def _default_valuation_frame(*, leader: str, comparison_logic: list[str], ranked_expressions: list[dict[str, Any]]) -> dict[str, str]:
    if not leader and not comparison_logic and not ranked_expressions:
        return {}
    top = ranked_expressions[0] if ranked_expressions else {}
    return {
        "current_view": comparison_logic[0] if comparison_logic else f"Leader today: {leader}" if leader else "",
        "base_case": _text_value(top.get("scenario_base")),
        "bull_case": _text_value(top.get("scenario_bull")),
        "bear_case": _text_value(top.get("scenario_bear") or top.get("why_not_best")),
        "key_variable": _text_value(top.get("valuation_anchor")),
    }


def _stable_claim_id(*, candidate_id: str, claim: str) -> str:
    return f"clm_{_stable_digest({'candidate_id': candidate_id, 'claim': claim})}"


def _stable_citation_id(*, source_id: str, source_name: str) -> str:
    return f"cit_{_stable_digest({'source_id': source_id or _slugify(source_name), 'name': source_name})}"


def _support_confidence(evidence_grade: str, contribution_role: str) -> str:
    grade = _text_value(evidence_grade).lower()
    role = _text_value(contribution_role).lower()
    if grade in {"high", "strong"} or role == "anchor":
        return "high"
    if grade in {"medium", "moderate"} or role == "corroborating":
        return "medium"
    return "low"


def _claim_kind_from_row(row: dict[str, Any]) -> str:
    importance = _text_value(row.get("importance")).lower()
    if importance == "high":
        return "core"
    if importance == "medium":
        return "supporting"
    return "monitor"


def _claim_status_from_row(row: dict[str, Any]) -> str:
    next_check = _text_value(row.get("next_check"))
    return "active" if next_check else "formed"


def _claim_load_bearing(row: dict[str, Any]) -> bool:
    importance = _text_value(row.get("importance")).lower()
    return importance in {"critical", "high", "p0", "load_bearing"} or _claim_kind_from_row(row) == "core"


def _claim_relevance_label(row: dict[str, Any]) -> str:
    if _claim_load_bearing(row):
        return "decision_blocker"
    if _text_value(row.get("evidence_grade")).lower() in {"weak", "speculative"}:
        return "needs_proof"
    return "supporting"


def _claim_falsification_condition(row: dict[str, Any], disconfirming_signals: list[str]) -> str:
    explicit = _text_value(row.get("falsification_condition"))
    if explicit:
        return explicit
    importance = _text_value(row.get("importance")).lower()
    if importance in {"critical", "high", "p0"} and disconfirming_signals:
        return disconfirming_signals[0]
    return _text_value(row.get("next_check"))

# ---------------------------------------------------------------------------
# Semantic reversal detection for claim evolution
# ---------------------------------------------------------------------------

# Financial direction word pairs: each key→value pair represents
# semantically opposite directions. Used to detect when two claims
# look similar in characters but carry opposite investment meaning.
_DIRECTION_PAIRS: dict[str, str] = {
    "增长": "下滑", "增加": "减少", "上升": "下降", "上涨": "下跌",
    "提升": "下降", "扩张": "收缩", "加速": "放缓", "盈利": "亏损",
    "增持": "减持", "利好": "利空", "超预期": "不及预期", "买入": "卖出",
    "增强": "削弱", "改善": "恶化", "回升": "回落", "突破": "跌破",
    "高于": "低于", "看多": "看空", "乐观": "悲观", "领先": "落后",
    "扩大": "缩小", "加仓": "减仓", "推荐": "回避", "强劲": "疲软",
    "繁荣": "萎缩", "复苏": "衰退", "正增长": "负增长",
    "升级": "降级", "加码": "削减", "涨停": "跌停",
}

# Build the reverse mapping so lookup works both directions
_DIRECTION_REVERSE: dict[str, str] = {v: k for k, v in _DIRECTION_PAIRS.items()}
_ALL_DIRECTION_WORDS: dict[str, str] = {**_DIRECTION_PAIRS, **_DIRECTION_REVERSE}


def _has_semantic_reversal(text_a: str, text_b: str) -> bool:
    """Return True if two texts contain opposite directional words.

    This is a lightweight guard (no ML/embedding needed) that catches the
    critical case where SequenceMatcher gives high similarity for texts with
    opposite investment semantics (e.g. '利润大幅增长' vs '利润大幅下滑').
    """
    if not text_a or not text_b:
        return False

    for word, opposite in _ALL_DIRECTION_WORDS.items():
        if word in text_a and opposite in text_b:
            return True
    return False


def _match_previous_claim(row: dict[str, Any], previous_claims: list[dict[str, Any]]) -> dict[str, Any]:
    current_norm = _normalized_claim_text(row.get("claim"))
    if not current_norm:
        return {}
    exact = next(
        (
            item
            for item in previous_claims
            if _normalized_claim_text(item.get("claim_text")) == current_norm
        ),
        None,
    )
    if exact:
        return dict(exact)
    best: dict[str, Any] | None = None
    best_ratio = 0.0
    current_kind = _text_value(row.get("claim_kind") or _claim_kind_from_row(row))
    for item in previous_claims:
        if current_kind and _text_value(item.get("claim_kind")) and _text_value(item.get("claim_kind")) != current_kind:
            continue
        ratio = SequenceMatcher(None, current_norm, _normalized_claim_text(item.get("claim_text"))).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = item
    if best is not None and best_ratio >= 0.72:
        best_text = _normalized_claim_text(best.get("claim_text"))
        if _has_semantic_reversal(current_norm, best_text):
            # High character similarity but opposite semantic direction.
            # Return with contradicted status instead of treating as persistent.
            return {**dict(best), "_match_status": "contradicted"}
        return dict(best)
    return {}


def _annotate_claim_rows(*, candidate_id: str, claim_ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for row in claim_ledger:
        claim_text = _text_value(row.get("claim"))
        if not claim_text:
            continue
        annotated.append(
            {
                **row,
                "claim_id": _text_value(row.get("claim_id")) or _stable_claim_id(candidate_id=candidate_id, claim=claim_text),
                "claim_kind": _text_value(row.get("claim_kind")) or _claim_kind_from_row(row),
                "status": _text_value(row.get("status")) or _claim_status_from_row(row),
                "supersedes_claim_id": _text_value(row.get("supersedes_claim_id")),
            }
        )
    return annotated


def _build_claim_objects(
    *,
    candidate_id: str,
    claim_ledger: list[dict[str, Any]],
    previous_payload: dict[str, Any] | None,
    disconfirming_signals: list[str],
) -> list[dict[str, Any]]:
    rows = _annotate_claim_rows(candidate_id=candidate_id, claim_ledger=claim_ledger)
    previous_claims = list((previous_payload or {}).get("claim_objects") or [])
    claim_objects: list[dict[str, Any]] = []
    for row in rows:
        previous = _match_previous_claim(row, previous_claims)
        now = time.time()
        first_seen_at = _as_float(previous.get("first_seen_at")) or _as_float((previous_payload or {}).get("generated_at")) or now
        previous_claim_id = _text_value(previous.get("claim_id"))
        claim_id = row["claim_id"]
        evolution_status = "new"
        if previous.get("_match_status") == "contradicted":
            evolution_status = "contradicted"
        elif previous and _normalized_claim_text(previous.get("claim_text")) == _normalized_claim_text(row.get("claim")):
            evolution_status = "persistent"
        elif previous_claim_id and previous_claim_id != claim_id:
            evolution_status = "reframed"
        falsification_condition = _claim_falsification_condition(row, disconfirming_signals)
        is_load_bearing = _claim_load_bearing(row)
        claim_objects.append(
            {
                "claim_id": claim_id,
                "claim_text": _text_value(row.get("claim")),
                "claim_kind": _text_value(row.get("claim_kind")),
                "status": _text_value(row.get("status")),
                "evidence_grade": _text_value(row.get("evidence_grade")),
                "importance": _text_value(row.get("importance")),
                "why_it_matters": _text_value(row.get("why_it_matters")),
                "next_check": _text_value(row.get("next_check")),
                "support_note": _text_value(row.get("support_note")),
                "falsification_condition": falsification_condition,
                "is_load_bearing": is_load_bearing,
                "decision_relevance": _claim_relevance_label(row),
                "first_seen_at": first_seen_at,
                "last_seen_at": now,
                "evolution_status": evolution_status,
                "supersedes_claim_id": _text_value(row.get("supersedes_claim_id")) or (previous_claim_id if evolution_status == "reframed" else ""),
            }
        )
    return claim_objects


def _build_citation_objects(
    *,
    source_scorecard: list[dict[str, Any]],
    source_scores_lookup: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for row in source_scorecard:
        source_name = _text_value(row.get("name"))
        if not source_name:
            continue
        score_row = dict((source_scores_lookup or {}).get(_text_value(row.get("source_id")) or source_name) or {})
        citation_id = _stable_citation_id(
            source_id=_text_value(row.get("source_id")),
            source_name=source_name,
        )
        citations.append(
            {
                "citation_id": citation_id,
                "source_id": _text_value(row.get("source_id")) or _slugify(source_name),
                "source_name": source_name,
                "detail_href": _text_value(row.get("detail_href")),
                "source_type": _text_value(row.get("source_type")),
                "source_trust_tier": _text_value(row.get("source_trust_tier")),
                "contribution_role": _text_value(row.get("contribution_role")),
                "information_role": _text_value(row.get("information_role")),
                "evidence_snippet": _text_value(row.get("focus") or row.get("reason")),
                "reason": _text_value(row.get("reason")),
                "confidence": _support_confidence("", _text_value(row.get("contribution_role"))),
                "quality_band": _text_value(score_row.get("quality_band") or row.get("quality_band")),
                "quality_score": _as_float(score_row.get("quality_score") or row.get("quality_score")),
                "trend_label": _text_value(score_row.get("trend_label") or row.get("trend_label")),
                "packages_seen": int(score_row.get("packages_seen") or 0),
            }
        )
    return citations


def _build_claim_citation_edges(
    *,
    claim_ledger: list[dict[str, Any]],
    claim_objects: list[dict[str, Any]],
    citation_objects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    claim_lookup = {
        _text_value(row.get("claim_id")): row
        for row in claim_objects
        if _text_value(row.get("claim_id"))
    }
    citation_by_name = {
        _normalize_match_key(row.get("source_name")): row
        for row in citation_objects
        if _normalize_match_key(row.get("source_name"))
    }
    edges: list[dict[str, Any]] = []
    seen: set[str] = set()
    for claim in claim_ledger:
        claim_id = _text_value(claim.get("claim_id"))
        if not claim_id:
            continue
        for source in claim.get("supporting_sources") or []:
            source_name = _text_value(source.get("name"))
            citation = citation_by_name.get(_normalize_match_key(source_name))
            if citation is None:
                continue
            support_type = _text_value(source.get("contribution_role") or citation.get("contribution_role") or "supporting")
            edge_id = f"{claim_id}->{citation['citation_id']}:{support_type}"
            if edge_id in seen:
                continue
            seen.add(edge_id)
            edges.append(
                {
                    "edge_id": edge_id,
                    "claim_id": claim_id,
                    "citation_id": _text_value(citation.get("citation_id")),
                    "support_type": support_type,
                    "confidence": _support_confidence(_text_value(claim.get("evidence_grade")), support_type),
                    "note": _text_value(claim.get("support_note") or citation.get("reason")),
                    "is_load_bearing": bool((claim_lookup.get(claim_id) or {}).get("is_load_bearing")),
                }
            )
    return edges


def _extract_theme_slugs(related_themes: list[dict[str, Any]]) -> list[str]:
    slugs: list[str] = []
    for row in related_themes:
        slug = _text_value(row.get("theme_slug"))
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs


def _load_source_score_ledger(*, root: Path) -> dict[str, Any]:
    latest = _source_score_dirs(root)["latest"]
    payload = _load_json(latest) if latest.exists() else {}
    sources = payload.get("sources")
    if not isinstance(sources, list):
        sources = []
    return {
        "schema_version": payload.get("schema_version") or SOURCE_SCORE_SCHEMA_VERSION,
        "updated_at": float(payload.get("updated_at") or 0),
        "sources": sources,
    }


def _source_quality_score(record: dict[str, Any]) -> float:
    accepted = min(int(record.get("accepted_route_count") or 0), 20) / 20.0
    validated = min(int(record.get("validated_case_count") or 0), 10) / 10.0
    supported = min(int(record.get("supported_claim_count") or 0), 24) / 24.0
    anchor = min(int(record.get("anchor_claim_count") or 0), 12) / 12.0
    load_bearing = min(int(record.get("load_bearing_claim_count") or 0), 12) / 12.0
    lead_support = min(int(record.get("lead_support_count") or 0), 8) / 8.0
    contradiction_penalty = min(int(record.get("contradicted_claim_count") or 0), 10) / 10.0
    theme_diversity = min(len(record.get("theme_slugs") or []), 8) / 8.0
    score = (
        (0.15 * accepted)
        + (0.15 * validated)
        + (0.20 * supported)
        + (0.18 * anchor)
        + (0.17 * load_bearing)
        + (0.10 * lead_support)
        + (0.10 * theme_diversity)
        - (0.05 * contradiction_penalty)
    )
    return round(score, 3)


def _source_quality_band(score: float) -> str:
    if score >= 0.75:
        return "core"
    if score >= 0.55:
        return "useful"
    if score >= 0.35:
        return "monitor"
    return "weak"


def _update_source_score_ledger(
    *,
    root: Path,
    candidate_id: str,
    theme_slugs: list[str],
    source_scorecard: list[dict[str, Any]],
    claim_citation_edges: list[dict[str, Any]],
    claim_objects: list[dict[str, Any]],
    history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ledger = _load_source_score_ledger(root=root)
    existing = {
        _text_value(row.get("source_id") or row.get("name")): dict(row)
        for row in ledger.get("sources") or []
        if _text_value(row.get("source_id") or row.get("name"))
    }
    claim_lookup = {
        _text_value(row.get("claim_id")): row
        for row in claim_objects
        if _text_value(row.get("claim_id"))
    }
    edge_count_by_citation: dict[str, int] = {}
    load_bearing_by_citation: dict[str, int] = {}
    for edge in claim_citation_edges:
        citation_id = _text_value(edge.get("citation_id"))
        if citation_id:
            edge_count_by_citation[citation_id] = edge_count_by_citation.get(citation_id, 0) + 1
            if bool(edge.get("is_load_bearing")):
                load_bearing_by_citation[citation_id] = load_bearing_by_citation.get(citation_id, 0) + 1
    retired_claims = {
        _normalized_claim_text(text)
        for text in (history or {}).get("retired_claims") or []
        if _normalized_claim_text(text)
    }
    updates: list[dict[str, Any]] = []
    now = time.time()
    dirs = _source_score_dirs(root)
    for row in source_scorecard:
        source_name = _text_value(row.get("name"))
        if not source_name:
            continue
        source_id = _text_value(row.get("source_id")) or _slugify(source_name)
        citation_id = _stable_citation_id(source_id=source_id, source_name=source_name)
        previous = dict(existing.get(source_id) or {})
        previous_score = float(previous.get("quality_score") or 0.0)
        supported_delta = int(edge_count_by_citation.get(citation_id) or 0)
        load_bearing_delta = int(load_bearing_by_citation.get(citation_id) or 0)
        lead_delta = 1 if _text_value(row.get("contribution_role")) == "anchor" and int(previous.get("packages_seen") or 0) == 0 and supported_delta > 0 else 0
        contradicted_delta = 0
        if retired_claims and supported_delta > 0:
            supported_claim_ids = [
                _text_value(edge.get("claim_id"))
                for edge in claim_citation_edges
                if _text_value(edge.get("citation_id")) == citation_id
            ]
            contradicted_delta = sum(
                1
                for claim_id in supported_claim_ids
                if _normalized_claim_text((claim_lookup.get(claim_id) or {}).get("claim_text")) in retired_claims
            )
        merged_theme_slugs = sorted({*_coerce_string_list(previous.get("theme_slugs") or []), *theme_slugs})
        support_history = list(previous.get("support_history") or [])
        support_history.append(
            {
                "at": now,
                "candidate_id": candidate_id,
                "theme_slugs": theme_slugs,
                "supported_claim_delta": supported_delta,
                "load_bearing_claim_delta": load_bearing_delta,
                "contribution_role": _text_value(row.get("contribution_role")),
            }
        )
        support_history = support_history[-12:]
        merged = {
            **previous,
            "source_id": source_id,
            "name": source_name,
            "source_type": _text_value(row.get("source_type")),
            "source_trust_tier": _text_value(row.get("source_trust_tier")),
            "track_record_label": _text_value(row.get("track_record_label")),
            "accepted_route_count": max(int(previous.get("accepted_route_count") or 0), int(row.get("accepted_route_count") or 0)),
            "validated_case_count": max(int(previous.get("validated_case_count") or 0), int(row.get("validated_case_count") or 0)),
            "packages_seen": int(previous.get("packages_seen") or 0) + 1,
            "supported_claim_count": int(previous.get("supported_claim_count") or 0) + supported_delta,
            "anchor_claim_count": int(previous.get("anchor_claim_count") or 0) + (supported_delta if _text_value(row.get("contribution_role")) == "anchor" else 0),
            "load_bearing_claim_count": int(previous.get("load_bearing_claim_count") or 0) + load_bearing_delta,
            "lead_support_count": int(previous.get("lead_support_count") or 0) + lead_delta,
            "contradicted_claim_count": int(previous.get("contradicted_claim_count") or 0) + contradicted_delta,
            "theme_slugs": merged_theme_slugs,
            "last_candidate_id": candidate_id,
            "last_supported_at": now,
            "latest_focus": _text_value(row.get("focus")),
            "latest_reason": _text_value(row.get("reason")),
            "information_role": _text_value(row.get("information_role")),
            "detail_href": _text_value(row.get("detail_href")),
            "support_history": support_history,
        }
        score = _source_quality_score(merged)
        merged["quality_score"] = score
        merged["quality_band"] = _source_quality_band(score)
        delta = round(score - previous_score, 3)
        merged["trend_label"] = "up" if delta > 0.02 else "down" if delta < -0.02 else "flat"
        merged["score_delta"] = delta
        merged["quality_explanation"] = (
            f"accepted={merged['accepted_route_count']}, validated={merged['validated_case_count']}, "
            f"supported_claims={merged['supported_claim_count']}, load_bearing={merged['load_bearing_claim_count']}, "
            f"lead_support={merged['lead_support_count']}, contradicted={merged['contradicted_claim_count']}"
        )
        existing[source_id] = merged
        updates.append(
            {
                "source_id": source_id,
                "name": source_name,
                "quality_score": score,
                "quality_band": merged["quality_band"],
                "score_delta": delta,
                "trend_label": merged["trend_label"],
                "supported_claim_delta": supported_delta,
                "load_bearing_claim_delta": load_bearing_delta,
                "detail_href": _text_value(row.get("detail_href")),
            }
        )
        history_path = dirs["history"] / f"{_slugify(source_id)}-{int(now)}.json"
        _write_json(history_path, merged)
    latest_payload = {
        "schema_version": SOURCE_SCORE_SCHEMA_VERSION,
        "updated_at": now,
        "sources": sorted(existing.values(), key=lambda item: (-float(item.get("quality_score") or 0), _text_value(item.get("name")))),
    }
    _write_json(dirs["latest"], latest_payload)
    return {"schema_version": SOURCE_SCORE_SCHEMA_VERSION, "updated_at": now, "sources": latest_payload["sources"], "updates": updates}


def _source_score_update_lookup(source_scores: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text_value(row.get("source_id") or row.get("name")): row
        for row in source_scores.get("updates") or []
        if _text_value(row.get("source_id") or row.get("name"))
    }


def _build_package_history(
    *,
    previous_payload: dict[str, Any] | None,
    current_payload: dict[str, Any],
    source_scores: dict[str, Any],
) -> dict[str, Any]:
    action_distance_after = _decision_distance(current_payload.get("current_decision"))
    if not previous_payload:
        return {
            "status": "new",
            "summary_lines": ["首次形成 research package。"],
            "field_changes": [],
            "new_claims": [row.get("claim_text") for row in current_payload.get("claim_objects") or []],
            "retired_claims": [],
            "new_risks": [row.get("risk") for row in current_payload.get("lanes", {}).get("skeptic", {}).get("risk_register", []) or []],
            "retired_risks": [],
            "source_updates": source_scores.get("updates") or [],
            "action_distance_before": None,
            "action_distance_after": action_distance_after,
            "action_distance_delta": None,
            "distance_label": "new",
            "goalpost_shifted": False,
        }
    action_distance_before = _decision_distance(previous_payload.get("current_decision"))
    field_changes: list[dict[str, str]] = []
    summary_lines: list[str] = []
    for field, label in (
        ("current_decision", "Current decision"),
        ("best_expression_today", "Best expression"),
        ("best_absorption_theme", "Absorption theme"),
        ("next_proving_milestone", "Next proving milestone"),
        ("thesis_status", "Thesis status"),
        ("why_not_investable_yet", "Why not investable yet"),
    ):
        before = _text_value(previous_payload.get(field))
        after = _text_value(current_payload.get(field))
        if before != after:
            field_changes.append({"field": field, "label": label, "before": before, "after": after})
            summary_lines.append(f"{label} changed: {before or '∅'} -> {after or '∅'}")
    previous_claims = {_text_value(row.get("claim_id")): _text_value(row.get("claim_text")) for row in previous_payload.get("claim_objects") or []}
    current_claims = {_text_value(row.get("claim_id")): _text_value(row.get("claim_text")) for row in current_payload.get("claim_objects") or []}
    new_claims = [text for claim_id, text in current_claims.items() if claim_id and claim_id not in previous_claims]
    retired_claims = [text for claim_id, text in previous_claims.items() if claim_id and claim_id not in current_claims]
    previous_risks = {_text_value(row.get("risk")) for row in previous_payload.get("lanes", {}).get("skeptic", {}).get("risk_register", []) or []}
    current_risks = {_text_value(row.get("risk")) for row in current_payload.get("lanes", {}).get("skeptic", {}).get("risk_register", []) or []}
    new_risks = sorted(risk for risk in current_risks if risk and risk not in previous_risks)
    retired_risks = sorted(risk for risk in previous_risks if risk and risk not in current_risks)
    source_updates = source_scores.get("updates") or []
    upgraded_sources = [row.get("name") for row in source_updates if _text_value(row.get("trend_label")) == "up"]
    downgraded_sources = [row.get("name") for row in source_updates if _text_value(row.get("trend_label")) == "down"]
    goalpost_shifted = (
        _text_value(previous_payload.get("next_proving_milestone")) != _text_value(current_payload.get("next_proving_milestone"))
        and action_distance_after >= action_distance_before
    )
    if new_claims:
        summary_lines.append(f"New claims: {', '.join(new_claims[:3])}")
    if new_risks:
        summary_lines.append(f"New risks: {', '.join(new_risks[:3])}")
    if upgraded_sources:
        summary_lines.append(f"Sources upgraded: {', '.join(upgraded_sources[:3])}")
    if downgraded_sources:
        summary_lines.append(f"Sources downgraded: {', '.join(downgraded_sources[:3])}")
    if action_distance_after != action_distance_before:
        direction = "closer to action" if action_distance_after < action_distance_before else "farther from action"
        summary_lines.append(f"Decision distance moved: {action_distance_before} -> {action_distance_after} ({direction})")
    elif goalpost_shifted:
        summary_lines.append("Next proving milestone moved without improving action distance.")
    if not summary_lines:
        summary_lines.append("No material thesis change versus the last package.")
    return {
        "status": "updated",
        "previous_generated_at": float(previous_payload.get("generated_at") or 0),
        "field_changes": field_changes,
        "summary_lines": summary_lines,
        "new_claims": new_claims,
        "retired_claims": retired_claims,
        "new_risks": new_risks,
        "retired_risks": retired_risks,
        "source_updates": source_updates,
        "action_distance_before": action_distance_before,
        "action_distance_after": action_distance_after,
        "action_distance_delta": action_distance_after - action_distance_before,
        "distance_label": "closer" if action_distance_after < action_distance_before else "farther" if action_distance_after > action_distance_before else "flat",
        "goalpost_shifted": goalpost_shifted,
        "upgraded_sources": upgraded_sources,
        "downgraded_sources": downgraded_sources,
    }


def _build_intelligence_requirements(
    *,
    next_proving_milestone: str,
    blocking_facts: list[str],
    research_gaps: list[str],
    key_sources: list[str],
) -> list[str]:
    rows: list[str] = []
    if next_proving_milestone:
        rows.append(f"优先盯住下一证明节点：{next_proving_milestone}")
    for row in blocking_facts[:2]:
        rows.append(f"围绕阻碍项搜证：{row}")
    for row in research_gaps[:2]:
        rows.append(f"补研究缺口：{row}")
    for row in key_sources[:2]:
        rows.append(f"回看/复核关键 source：{row}")
    return rows[:5]


def _write_theme_state_snapshot(
    *,
    root: Path,
    theme: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    theme_slug = _text_value(theme.get("theme_slug"))
    if not theme_slug:
        return {}
    dirs = _theme_state_dirs(root, theme_slug)
    previous = _load_json(dirs["latest"]) if dirs["latest"].exists() else {}
    best_expression = _text_value((result.get("best_expression") or {}).get("entity"))
    payload = {
        "schema_version": THEME_STATE_SCHEMA_VERSION,
        "generated_at": time.time(),
        "theme_slug": theme_slug,
        "title": _text_value(theme.get("title") or theme.get("spec_context", {}).get("title") or theme_slug),
        "recommended_posture": _text_value(result.get("recommended_posture")),
        "best_expression": best_expression,
        "run_root": _text_value(result.get("run_root")),
        "investor_question": _text_value(theme.get("spec_context", {}).get("investor_question")),
        "why_now": _text_value(theme.get("spec_context", {}).get("why_now")),
        "why_mispriced": _text_value(theme.get("spec_context", {}).get("why_mispriced")),
        "current_posture": _text_value(theme.get("spec_context", {}).get("current_posture")),
        "action_distance": _decision_distance(result.get("recommended_posture")),
    }
    field_changes: list[dict[str, str]] = []
    summary_lines: list[str] = []
    if previous:
        for field, label in (
            ("recommended_posture", "Posture"),
            ("best_expression", "Best expression"),
            ("why_now", "Why now"),
            ("action_distance", "Action distance"),
        ):
            before = _text_value(previous.get(field))
            after = _text_value(payload.get(field))
            if before != after:
                field_changes.append({"field": field, "label": label, "before": before, "after": after})
                summary_lines.append(f"{label} changed: {before or '∅'} -> {after or '∅'}")
    else:
        summary_lines.append("首次形成 theme snapshot。")
    payload["history"] = {
        "status": "updated" if previous else "new",
        "previous_generated_at": float(previous.get("generated_at") or 0),
        "field_changes": field_changes,
        "summary_lines": summary_lines,
    }
    history_path = dirs["history"] / f"{int(payload['generated_at'])}.json"
    _write_json(history_path, payload)
    _write_json(dirs["latest"], payload)
    return payload


def _coalesce_pending_duplicates(item: InboxItem, *, dirs: dict[str, Path]) -> None:
    logical_key = _extract_logical_key({"payload": item.payload}) or _text_value(item.payload.get("logical_key"))
    if not logical_key:
        return
    for path in sorted(dirs["pending"].glob("*.json")):
        if path.stem == item.item_id:
            continue
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(existing, dict):
            continue
        if _text_value(existing.get("category")) != item.category:
            continue
        if _extract_logical_key(existing) != logical_key:
            continue
        target_json = _archive_path(dirs["archived"], path.name)
        path.replace(target_json)
        markdown = path.with_suffix(".md")
        if markdown.exists():
            markdown.replace(_archive_path(dirs["archived"], markdown.name))


def refresh_dashboard_projection(*, cfg: AppConfig | None = None, force: bool = True) -> dict[str, Any]:
    service = DashboardService(cfg or load_config())
    control_plane = service.refresh_control_plane(force=force)
    return {
        "ok": True,
        "refreshed_at": time.time(),
        "root_count": int(control_plane.get("root_count") or 0),
        "refresh_status": str(control_plane.get("refresh_status") or "unknown"),
        "db_path": str(control_plane.get("db_path") or ""),
    }


def _run_finagent_json_command(
    *,
    finagent_root: Path,
    python_bin: str,
    args: list[str],
    timeout: int = 180,
) -> dict[str, Any]:
    proc = subprocess.run(
        [python_bin, "-m", "finagent.cli", *args],
        cwd=str(finagent_root),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"finagent rc={proc.returncode}")
    return json.loads(proc.stdout)


def _run_finagent_script_json(
    *,
    finagent_root: Path,
    python_bin: str,
    script_rel: str,
    args: list[str],
    timeout: int = 600,
) -> dict[str, Any]:
    proc = subprocess.run(
        [python_bin, script_rel, *args],
        cwd=str(finagent_root),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip() or f"finagent script rc={proc.returncode}")
    return json.loads(proc.stdout)


def _fetch_market_truth(
    *,
    finagent_root: Path,
    python_bin: str,
    ticker: str,
    market: str = "CN",
) -> dict[str, Any] | None:
    """Fetch real-time market snapshot from finagent's market-snapshot CLI.

    Returns a standardised dict with price, PE, market_cap etc., or None on failure.
    """
    if not ticker or not market:
        return None
    try:
        result = _run_finagent_json_command(
            finagent_root=finagent_root,
            python_bin=python_bin,
            args=["market-snapshot", "--ticker", ticker, "--market", market],
            timeout=60,
        )
        if result.get("ok"):
            return result
        log.warning("market-snapshot returned not-ok: %s", result.get("error"))
        return None
    except Exception as exc:
        log.warning("Failed to fetch market truth for %s (%s): %s", ticker, market, exc)
        return None


def _infer_market_from_ticker(ticker: str) -> str:
    """Best-effort market inference from ticker format."""
    t = ticker.strip().upper()
    if re.match(r"^\d{6}\.(SZ|SH|BJ)$", t) or re.match(r"^\d{6}$", t):
        return "CN"
    if re.match(r"^\d{1,5}\.HK$", t):
        return "HK"
    if re.match(r"^[A-Z]{1,5}$", t):
        return "US"
    return "CN"  # default


def _run_finagent_snapshot(*, finagent_root: Path, python_bin: str, scope: str = "today", limit: int = 8) -> dict[str, Any]:
    return _run_finagent_json_command(
        finagent_root=finagent_root,
        python_bin=python_bin,
        args=["integration-snapshot", "--scope", scope, "--limit", str(limit)],
    )


# ---------------------------------------------------------------------------
# Lane execution with retry
# ---------------------------------------------------------------------------

_DEFAULT_LANE_MAX_RETRIES = 1
_DEFAULT_LANE_BACKOFF_SECONDS = 2.0


def _run_lane_with_retry(
    *,
    lane_slug: str,
    system_prompt: str,
    prompt: str,
    max_retries: int = _DEFAULT_LANE_MAX_RETRIES,
    backoff_seconds: float = _DEFAULT_LANE_BACKOFF_SECONDS,
) -> dict[str, Any]:
    """Run an LLM lane call with automatic retry on failure.

    Returns the lane result dict. On exhausting retries, returns a dict
    with 'structured': {} and 'error' describing the failure.
    """
    last_exc: Exception | None = None
    for attempt in range(1 + max_retries):
        try:
            result = _ask_coding_plan_lane(
                lane_slug=lane_slug,
                system_prompt=system_prompt,
                prompt=prompt,
            )
            return result
        except Exception as exc:
            last_exc = exc
            log.warning(
                "Lane %s attempt %d/%d failed: %s",
                lane_slug, attempt + 1, 1 + max_retries, exc,
            )
            if attempt < max_retries:
                time.sleep(backoff_seconds * (attempt + 1))
    return {
        "structured": {},
        "markdown": "",
        "error": f"lane {lane_slug} failed after {1 + max_retries} attempts: {last_exc}",
    }


def _run_finagent_daily_refresh(
    *,
    finagent_root: Path,
    python_bin: str,
    limit: int = 5,
    timeout: int = 900,
) -> dict[str, Any]:
    return _run_finagent_json_command(
        finagent_root=finagent_root,
        python_bin=python_bin,
        args=["daily-refresh", "--limit", str(limit)],
        timeout=timeout,
    )


def _run_theme_radar_board(*, finagent_root: Path, python_bin: str, limit: int = 8) -> dict[str, Any]:
    return _run_finagent_json_command(
        finagent_root=finagent_root,
        python_bin=python_bin,
        args=["theme-radar-board", "--limit", str(limit)],
    )


def _run_opportunity_inbox(*, finagent_root: Path, python_bin: str, limit: int = 8) -> dict[str, Any]:
    return _run_finagent_json_command(
        finagent_root=finagent_root,
        python_bin=python_bin,
        args=["opportunity-inbox", "--limit", str(limit)],
    )


def _run_kol_suite(
    *,
    finagent_root: Path,
    python_bin: str,
    run_root: Path,
    suite_slug: str,
    timeout: int = 900,
) -> dict[str, Any]:
    return _run_finagent_script_json(
        finagent_root=finagent_root,
        python_bin=python_bin,
        script_rel="scripts/run_event_mining_kol_suite.py",
        args=["--run-root", str(run_root), "--suite-slug", suite_slug],
        timeout=timeout,
    )


def _get_finbot_connector() -> LLMConnector:
    """Get the LLM connector based on FINBOT_TIER env var.

    FINBOT_TIER values:
    - "free" or "finbotfree": use OpenRouter (free tier)
    - "paid" or "finbot": use Coding Plan (paid tier, default)
    - not set: use Coding Plan (default)
    """
    import os
    tier = os.environ.get("FINBOT_TIER", "").lower()

    if tier in ("free", "finbotfree"):
        return LLMConnector(config=LLMConfig(default_provider="openrouter", default_preset="planning"))
    else:
        return LLMConnector(config=LLMConfig(default_provider="coding_plan", default_preset="planning"))


def _coding_plan_connector() -> LLMConnector:
    """Legacy function - use _get_finbot_connector() for tier-aware routing."""
    return _get_finbot_connector()


def _get_lane_provider() -> str:
    """Get the provider based on FINBOT_TIER env var."""
    import os
    tier = os.environ.get("FINBOT_TIER", "").lower()
    if tier in ("free", "finbotfree"):
        return "openrouter"
    return "coding_plan"


def _get_finbot_tier_tag() -> str:
    """Get the current finbot tier tag for artifact metadata.

    Returns:
    - "free-tier": when FINBOT_TIER=free or finbotfree
    - "paid-tier": when FINBOT_TIER=paid/finbot or not set (default)
    """
    import os
    tier = os.environ.get("FINBOT_TIER", "").lower()
    if tier in ("free", "finbotfree"):
        return "free-tier"
    return "paid-tier"


def _ask_coding_plan_lane(
    *,
    lane_slug: str,
    system_prompt: str,
    prompt: str,
    preset: str = "planning",
    timeout: float = 90.0,
) -> dict[str, Any]:
    provider = _get_lane_provider()
    response = _coding_plan_connector().ask(
        prompt,
        system_msg=system_prompt,
        provider=provider,
        preset=preset,
        timeout=timeout,
    )
    if response.status != "success":
        raise RuntimeError(response.error or f"coding_plan failed with status={response.status}")
    raw_text = response.text if isinstance(response.text, str) else ""
    if not raw_text.strip():
        raise RuntimeError(
            f"{response.provider or provider} returned empty text for lane {lane_slug}"
        )
    structured = _json_block(raw_text)
    markdown = _markdown_without_json_block(raw_text)
    return {
        "lane_slug": lane_slug,
        "provider": response.provider,
        "preset": response.preset,
        "latency_ms": response.latency_ms,
        "structured": structured,
        "markdown": markdown,
        "raw_text": raw_text,
    }


def _ask_coding_plan_dossier(*, system_prompt: str, prompt: str, preset: str = "planning", timeout: float = 90.0) -> dict[str, Any]:
    return _ask_coding_plan_lane(
        lane_slug="decision",
        system_prompt=system_prompt,
        prompt=prompt,
        preset=preset,
        timeout=timeout,
    )


def load_theme_catalog(path: Path = DEFAULT_THEME_CATALOG_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_watchlist_item(snapshot: dict[str, Any]) -> InboxItem | None:
    targets = list(snapshot.get("priority_targets") or [])
    queue_summary = dict(snapshot.get("queue_summary") or {})
    top = targets[0] if targets else {}
    active_queues = {key: int(value or 0) for key, value in queue_summary.items() if int(value or 0) > 0}
    if not top and not active_queues:
        return None
    title = f"Finbot scout · {top.get('thesis_title') or 'no priority target'}"
    summary_parts: list[str] = []
    if top:
        summary_parts.append(
            f"{top.get('target_case_id') or top.get('ticker_or_symbol') or 'target'} → "
            f"{top.get('action_state') or top.get('raw_posture') or 'watch'}"
        )
    if active_queues:
        summary_parts.append("queues=" + ", ".join(f"{key}:{value}" for key, value in sorted(active_queues.items())))
    if top.get("reason"):
        summary_parts.append(str(top.get("reason")))
    payload = {
        "logical_key": top.get("thesis_id") or top.get("target_case_id") or top.get("ticker_or_symbol") or "watchlist",
        "scope": snapshot.get("scope") or "today",
        "priority_target": top,
        "queue_summary": queue_summary,
        "summary": snapshot.get("summary") or {},
        "top_theses": snapshot.get("top_theses") or [],
    }
    item_id = _inbox_item_id("finbot-watchlist", str(payload["logical_key"]))
    return InboxItem(
        item_id=item_id,
        created_at=time.time(),
        title=title,
        summary=" | ".join(part for part in summary_parts if part),
        category="watchlist_scout",
        severity="warning" if active_queues else "accent",
        source="finagent.integration_snapshot",
        action_hint="Review if posture or queue pressure changed materially; otherwise archive after reading.",
        payload=payload,
    )


def _build_theme_radar_item(radar: dict[str, Any], inbox: dict[str, Any]) -> InboxItem | None:
    candidates = list(inbox.get("items") or []) or list(radar.get("items") or [])
    top = candidates[0] if candidates else {}
    if not top:
        return None
    payload = {
        "logical_key": top.get("candidate_id") or top.get("thesis_name") or "candidate",
        "candidate_id": top.get("candidate_id"),
        "thesis_name": top.get("thesis_name"),
        "residual_class": top.get("residual_class"),
        "route": top.get("route"),
        "ranking_score": top.get("ranking_score"),
        "next_action": top.get("next_action"),
        "next_proving_milestone": top.get("next_proving_milestone"),
        "note": top.get("note"),
        "attention_capture_ratio": top.get("attention_capture_ratio"),
        "summary": radar.get("summary") or {},
    }
    title = f"Finbot radar · {top.get('thesis_name') or top.get('candidate_id') or 'theme candidate'}"
    summary = " | ".join(
        part
        for part in [
            f"{top.get('candidate_id') or 'candidate'} → {top.get('next_action') or top.get('route') or 'scan'}",
            f"class={top.get('residual_class') or 'unknown'}",
            f"score={top.get('ranking_score') or top.get('investability_score') or 0}",
            top.get("note") or "",
        ]
        if part
    )
    item_id = _inbox_item_id("finbot-radar", str(payload["logical_key"]))
    return InboxItem(
        item_id=item_id,
        created_at=time.time(),
        title=title,
        summary=summary,
        category="theme_radar",
        severity="accent" if str(top.get("route") or "") == "opportunity" else "info",
        source="finagent.theme_radar",
        action_hint="Corroborate frontier/adjacent candidate before promoting into a tracked theme.",
        payload=payload,
    )


def _build_theme_run_item(theme: dict[str, Any], run_result: dict[str, Any]) -> InboxItem | None:
    posture = str(run_result.get("recommended_posture") or "")
    best = dict(run_result.get("best_expression") or {})
    if posture not in {"watch_with_prepare_candidate", "prepare_candidate", "starter"} and not best:
        return None
    spec_context = dict(theme.get("spec_context") or {})
    payload = {
        "logical_key": theme.get("theme_slug") or "theme",
        "theme_slug": theme.get("theme_slug"),
        "title": theme.get("title"),
        "recommended_posture": posture,
        "best_expression": {
            "projection_id": best.get("projection_id"),
            "entity": best.get("entity"),
            "product": best.get("product"),
            "recommended_action": best.get("recommended_action"),
            "evidence_quality_band": best.get("evidence_quality_band"),
            "constraint_burden": best.get("constraint_burden"),
        },
        "spec_path": theme.get("spec_path"),
        "events_path": theme.get("events_path"),
        "as_of": theme.get("as_of"),
        "investor_question": spec_context.get("investor_question") or "",
        "thesis_statement": spec_context.get("thesis_statement") or "",
        "why_now": spec_context.get("why_now") or "",
        "why_mispriced": spec_context.get("why_mispriced") or "",
        "capital_gate": spec_context.get("capital_gate") or [],
        "stop_rule": spec_context.get("stop_rule") or [],
    }
    title = f"Finbot theme run · {theme.get('title') or theme.get('theme_slug')}"
    summary = " | ".join(
        part
        for part in [
            f"{theme.get('theme_slug') or 'theme'} → {posture or 'watch'}",
            f"best={best.get('entity') or best.get('projection_id') or 'n/a'}",
            f"action={best.get('recommended_action') or 'hold'}",
            f"quality={best.get('evidence_quality_band') or 'unknown'}",
        ]
        if part
    )
    item_id = _inbox_item_id("finbot-theme", str(payload["logical_key"]))
    return InboxItem(
        item_id=item_id,
        created_at=time.time(),
        title=title,
        summary=summary,
        category="theme_run",
        severity="warning" if posture == "watch_with_prepare_candidate" else "accent",
        source="finagent.event_mining.theme_suite",
        action_hint="Review whether the best expression merits a manual deepening pass or immediate watchlist escalation.",
        payload=payload,
    )


def _build_theme_radar_brief_item(candidate: dict[str, Any], *, related_themes: list[dict[str, Any]]) -> InboxItem | None:
    candidate_id = _text_value(candidate.get("candidate_id"))
    thesis_name = _text_value(candidate.get("thesis_name"))
    if not candidate_id or not thesis_name:
        return None
    theme_refs = [
        {
            "theme_slug": _text_value(theme.get("theme_slug")),
            "title": _text_value(theme.get("title")),
            "detail_href": _text_value(theme.get("detail_href")),
            "best_expression": _text_value(theme.get("best_expression")),
            "related_sources": list(theme.get("related_sources") or []),
        }
        for theme in related_themes[:3]
    ]
    suggested_sources: list[str] = []
    for theme in theme_refs:
        for source_name in theme["related_sources"]:
            if source_name not in suggested_sources:
                suggested_sources.append(source_name)
    payload = {
        "logical_key": candidate_id,
        "candidate_id": candidate_id,
        "thesis_name": thesis_name,
        "route": _text_value(candidate.get("route")),
        "residual_class": _text_value(candidate.get("residual_class")),
        "note": _text_value(candidate.get("note")),
        "next_action": _text_value(candidate.get("next_action") or "deepen_now"),
        "next_proving_milestone": _text_value(candidate.get("next_proving_milestone")),
        "ranking_score": candidate.get("ranking_score"),
        "related_themes": theme_refs,
        "suggested_sources": suggested_sources[:6],
        "research_questions": [
            "Which tracked theme should absorb this candidate first?",
            "What exact milestone would prove the candidate is becoming investable?",
            "Which first-hand source should be checked before promoting it?",
        ],
    }
    summary = " | ".join(
        part
        for part in [
            f"{candidate_id} → deepen",
            f"class={payload['residual_class'] or 'unknown'}",
            payload["next_proving_milestone"] or "",
            payload["note"],
        ]
        if part
    )
    return InboxItem(
        item_id=_inbox_item_id("finbot-brief", candidate_id),
        created_at=time.time(),
        title=f"Finbot deepening brief · {thesis_name}",
        summary=summary,
        category="deepening_brief",
        severity="accent",
        source="finagent.theme_radar",
        action_hint="Use this brief to decide whether to open a deeper research pass or attach the candidate to an existing theme.",
        payload=payload,
    )


def _source_cards_by_name(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for row in list(snapshot.get("strong_sources") or []) + list(snapshot.get("kols") or []):
        name = _text_value(row.get("name"))
        if name:
            cards[name] = dict(row)
    return cards


def _opportunity_context_bundle(
    *,
    service: DashboardService,
    snapshot: dict[str, Any],
    candidate_id: str,
) -> dict[str, Any]:
    opportunity = next(
        (item for item in snapshot.get("opportunities", []) if _text_value(item.get("candidate_id")) == candidate_id),
        None,
    )
    if opportunity is None:
        raise KeyError(candidate_id)
    source_lookup = _source_cards_by_name(snapshot)
    related_themes = []
    for row in opportunity.get("related_themes") or []:
        theme_slug = _text_value(row.get("theme_slug"))
        if not theme_slug:
            continue
        try:
            related_themes.append(service.investor_theme_detail(theme_slug))
        except Exception:
            continue
    related_sources = []
    for name in opportunity.get("suggested_sources") or []:
        source = source_lookup.get(_text_value(name))
        if source:
            related_sources.append(source)
    return {
        "opportunity": opportunity,
        "related_themes": related_themes,
        "related_sources": related_sources,
        "planning_doc_reader_href": snapshot.get("planning_doc_reader_href"),
        "planning_doc_path": snapshot.get("planning_doc_path"),
    }


def _render_theme_context(detail: dict[str, Any]) -> dict[str, Any]:
    theme = dict(detail.get("theme") or {})
    body = dict(detail.get("detail") or {})
    decision = dict(body.get("decision_card") or {})
    return {
        "theme_slug": theme.get("theme_slug"),
        "title": theme.get("title"),
        "investor_question": body.get("investor_question"),
        "thesis_statement": body.get("thesis_statement"),
        "why_now": body.get("why_now"),
        "why_mispriced": body.get("why_mispriced"),
        "recommended_posture": theme.get("recommended_posture"),
        "best_expression": theme.get("best_expression"),
        "decision_excerpt": decision.get("decision_excerpt"),
        "investor_excerpt": decision.get("investor_excerpt"),
        "capital_gate": list(decision.get("capital_gate") or []),
        "stop_rule": list(decision.get("stop_rule") or []),
        "thesis_level_falsifiers": list(decision.get("thesis_level_falsifiers") or []),
        "timing_level_falsifiers": list(decision.get("timing_level_falsifiers") or []),
    }


def _render_source_context(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": row.get("source_id"),
        "name": row.get("name"),
        "source_type": row.get("source_type"),
        "source_trust_tier": row.get("source_trust_tier"),
        "source_priority_label": row.get("source_priority_label"),
        "track_record_label": row.get("track_record_label"),
        "accepted_route_count": row.get("accepted_route_count"),
        "validated_case_count": row.get("validated_case_count"),
        "latest_viewpoint_summary": row.get("latest_viewpoint_summary"),
        "detail_href": row.get("detail_href"),
    }


def _source_contribution_role(source: dict[str, Any]) -> str:
    trust_tier = _text_value(source.get("source_trust_tier"))
    source_type = _text_value(source.get("source_type"))
    validated = int(source.get("validated_case_count") or 0)
    if trust_tier == "anchor" or (source_type == "official_disclosure" and validated >= 5):
        return "anchor"
    if source_type == "kol" or trust_tier == "derived":
        return "derived"
    return "corroborating"


def _source_focus(source: dict[str, Any], key_sources: list[str]) -> str:
    name = _text_value(source.get("name"))
    name_lower = name.lower()
    for row in key_sources:
        text = _text_value(row)
        if not text:
            continue
        if name and name_lower and name_lower in text.lower():
            return text
    return _text_value(source.get("latest_viewpoint_summary"))


def _source_reason(source: dict[str, Any], key_sources: list[str]) -> str:
    focus = _source_focus(source, key_sources)
    source_type = _text_value(source.get("source_type"))
    trust_tier = _text_value(source.get("source_trust_tier"))
    if focus:
        return "当前 dossier 直接引用了这条 source。"
    if source_type == "official_disclosure":
        return "这是当前候选机会最该先回看的第一手披露。"
    if trust_tier == "derived":
        return "这条 source 主要用于补充观点、交叉验证与预期差观察。"
    return "这条 source 作为补充证据保留在当前研究包中。"


def _source_information_role(source: dict[str, Any]) -> str:
    contribution_role = _source_contribution_role(source)
    if contribution_role == "anchor":
        return "originator"
    if contribution_role == "corroborating":
        return "corroborator"
    return "amplifier"


def _build_source_scorecard(
    *,
    related_sources: list[dict[str, Any]],
    key_sources: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in related_sources:
        rows.append(
            {
                "source_id": _text_value(source.get("source_id")),
                "name": _text_value(source.get("name")),
                "detail_href": _text_value(source.get("detail_href")),
                "source_type": _text_value(source.get("source_type")),
                "source_trust_tier": _text_value(source.get("source_trust_tier")),
                "source_priority_label": _text_value(source.get("source_priority_label")),
                "track_record_label": _text_value(source.get("track_record_label")),
                "accepted_route_count": int(source.get("accepted_route_count") or 0),
                "validated_case_count": int(source.get("validated_case_count") or 0),
                "contribution_role": _source_contribution_role(source),
                "information_role": _source_information_role(source),
                "focus": _source_focus(source, key_sources),
                "reason": _source_reason(source, key_sources),
            }
        )
    role_rank = {"anchor": 0, "corroborating": 1, "derived": 2}
    rows.sort(
        key=lambda row: (
            role_rank.get(_text_value(row.get("contribution_role")), 9),
            -int(row.get("validated_case_count") or 0),
            -int(row.get("accepted_route_count") or 0),
            _text_value(row.get("name")),
        )
    )
    return rows[:6]


def _enrich_claim_ledger_with_sources(
    *,
    claim_ledger: list[dict[str, Any]],
    source_scorecard: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not claim_ledger:
        return []
    anchors = [row for row in source_scorecard if _text_value(row.get("contribution_role")) == "anchor"]
    corroborating = [row for row in source_scorecard if _text_value(row.get("contribution_role")) == "corroborating"]
    derived = [row for row in source_scorecard if _text_value(row.get("contribution_role")) == "derived"]
    fallback_pool = anchors or corroborating or derived
    enriched: list[dict[str, Any]] = []
    for row in claim_ledger:
        current_sources = list(row.get("supporting_sources") or [])
        if not current_sources and fallback_pool:
            current_sources = [
                {
                    "name": _text_value(fallback_pool[0].get("name")),
                    "detail_href": _text_value(fallback_pool[0].get("detail_href")),
                    "contribution_role": _text_value(fallback_pool[0].get("contribution_role")),
                }
            ]
        support_note = _text_value(row.get("support_note"))
        if not support_note and current_sources:
            support_note = f"优先依赖 {current_sources[0].get('name') or 'anchor source'} 继续验证这条 claim。"
        enriched.append(
            {
                **row,
                "supporting_sources": current_sources,
                "support_note": support_note,
            }
        )
    return enriched


def _build_opportunity_dossier_prompt(*, bundle: dict[str, Any], kol_summary: dict[str, Any] | None) -> tuple[str, str]:
    opportunity = dict(bundle.get("opportunity") or {})
    theme_blocks = [_render_theme_context(item) for item in bundle.get("related_themes") or []]
    source_blocks = [_render_source_context(item) for item in bundle.get("related_sources") or []]
    context_payload = {
        "candidate": {
            "candidate_id": opportunity.get("candidate_id"),
            "thesis_name": opportunity.get("thesis_name"),
            "route": opportunity.get("route"),
            "residual_class": opportunity.get("residual_class"),
            "ranking_score": opportunity.get("ranking_score"),
            "note": opportunity.get("note"),
            "brief_next_action": opportunity.get("brief_next_action") or opportunity.get("next_action"),
            "brief_next_proving_milestone": opportunity.get("brief_next_proving_milestone") or opportunity.get("next_proving_milestone"),
        },
        "themes": theme_blocks,
        "sources": source_blocks,
        "kol_suite": kol_summary or {},
    }
    system_prompt = (
        "你是 Finbot 的投资研究合成器。"
        "只允许使用提供的上下文，不能编造不存在的事实。"
        "输出必须先给一个 JSON code block，再给一份人类可读的中文研究包。"
        "研究包要像投资人 briefing：先给当前判断，再给为什么现在值得看、为什么还不能下注、下一证明节点、反证和待补研究。"
    )
    prompt = (
        "请把下面的 frontier opportunity 上下文压成一个 investor-grade dossier。\n\n"
        "输出要求：\n"
        "1. 先输出一个 ```json``` 代码块，字段固定为："
        "headline,current_decision,thesis_status,best_absorption_theme,best_expression_today,"
        "why_not_investable_yet,next_proving_milestone,forcing_events,disconfirming_signals,key_sources,research_gaps。\n"
        "2. 然后输出中文 Markdown，按以下小节：\n"
        "## One-line judgment\n## Why this surfaced now\n## Absorption path\n## Best expression today\n## Why not investable yet\n## Forcing events\n## Disconfirming signals\n## Source map\n## Research gaps\n"
        "3. 内容必须短、硬、可执行，不要空话，不要展示原始 JSON。\n\n"
        f"上下文：\n```json\n{_json_dumps(context_payload)}\n```"
    )
    return system_prompt, prompt


def _build_claim_lane_prompt(*, bundle: dict[str, Any], kol_summary: dict[str, Any] | None) -> tuple[str, str]:
    opportunity = dict(bundle.get("opportunity") or {})
    theme_blocks = [_render_theme_context(item) for item in bundle.get("related_themes") or []]
    source_blocks = [_render_source_context(item) for item in bundle.get("related_sources") or []]
    context_payload = {
        "candidate": {
            "candidate_id": opportunity.get("candidate_id"),
            "thesis_name": opportunity.get("thesis_name"),
            "route": opportunity.get("route"),
            "residual_class": opportunity.get("residual_class"),
            "note": opportunity.get("note"),
            "next_proving_milestone": opportunity.get("brief_next_proving_milestone") or opportunity.get("next_proving_milestone"),
        },
        "themes": theme_blocks,
        "sources": source_blocks,
        "kol_suite": kol_summary or {},
    }
    system_prompt = (
        "你是 Finbot 的 claim lane。"
        "你的任务不是写长报告，而是把机会压成可检验的核心 claims。"
        "只允许使用给定上下文，必须短、硬、结构化。"
    )
    prompt = (
        "请提炼这个机会当前最值得跟踪的核心 claims。\n\n"
        "先输出 ```json```，字段固定为："
        "core_claims,supporting_evidence,critical_unknowns,key_sources,absorption_candidates,claim_ledger。"
        "`claim_ledger` 必须是数组，每个元素字段为："
        "claim,evidence_grade,importance,why_it_matters,next_check,falsification_condition,support_note。"
        "\n然后输出中文 Markdown，按小节：\n"
        "## Core claims\n## Claim ledger\n## Supporting evidence\n## Critical unknowns\n## Source priorities\n"
        f"\n上下文：\n```json\n{_json_dumps(context_payload)}\n```"
    )
    return system_prompt, prompt


def _build_skeptic_lane_prompt(*, bundle: dict[str, Any], claim_lane: dict[str, Any]) -> tuple[str, str]:
    opportunity = dict(bundle.get("opportunity") or {})
    context_payload = {
        "candidate": {
            "candidate_id": opportunity.get("candidate_id"),
            "thesis_name": opportunity.get("thesis_name"),
            "route": opportunity.get("route"),
            "residual_class": opportunity.get("residual_class"),
            "note": opportunity.get("note"),
        },
        "claim_lane": claim_lane,
    }
    system_prompt = (
        "你是 Finbot 的 skeptic lane。"
        "你的角色是反方分析师，只负责找最可能击穿 thesis 的路径、时间错配和竞争替代。"
        "不要重复多头论点。"
    )
    prompt = (
        "请针对这个机会给出最强的反方结构。\n\n"
        "先输出 ```json```，字段固定为："
        "bear_case,thesis_breakers,timing_risks,competing_paths,disconfirming_signals,risk_register。"
        "`risk_register` 必须是数组，每个元素字段为："
        "risk,severity,horizon,what_confirms,what_refutes。"
        "\n然后输出中文 Markdown，按小节：\n"
        "## Bear case\n## Risk register\n## Thesis breakers\n## Timing risks\n## Competing paths\n## Disconfirming signals\n"
        f"\n上下文：\n```json\n{_json_dumps(context_payload)}\n```"
    )
    return system_prompt, prompt


def _build_expression_lane_prompt(
    *,
    bundle: dict[str, Any],
    claim_lane: dict[str, Any],
    skeptic_lane: dict[str, Any],
) -> tuple[str, str]:
    opportunity = dict(bundle.get("opportunity") or {})
    theme_blocks = [_render_theme_context(item) for item in bundle.get("related_themes") or []]
    context_payload = {
        "candidate": {
            "candidate_id": opportunity.get("candidate_id"),
            "thesis_name": opportunity.get("thesis_name"),
            "route": opportunity.get("route"),
            "residual_class": opportunity.get("residual_class"),
        },
        "themes": theme_blocks,
        "claim_lane": claim_lane,
        "skeptic_lane": skeptic_lane,
    }
    system_prompt = (
        "你是 Finbot 的 expression lane。"
        "你的任务是在现有主题和表达里给出最值得准备的表达排序。"
        "不要泛泛而谈，要明确为什么 A 比 B 更好，以及为什么现在还不能直接行动。"
    )
    prompt = (
        "请给出这个机会当前最合理的表达排序。\n\n"
        "先输出 ```json```，字段固定为："
        "leader,ranked_expressions,comparison_logic,valuation_frame。"
        "`ranked_expressions` 必须是数组，每个元素字段为："
        "rank,expression,role,why_best,why_not_best,readiness,valuation_anchor,scenario_base,scenario_bull,scenario_bear。"
        "`valuation_frame` 为对象，字段固定为："
        "current_view,base_case,bull_case,bear_case,key_variable。"
        "\n然后输出中文 Markdown，按小节：\n"
        "## Leader\n## Ranking\n## Valuation frame\n## Why the leader wins today\n## Why the others do not\n"
        f"\n上下文：\n```json\n{_json_dumps(context_payload)}\n```"
    )
    return system_prompt, prompt


def _build_decision_lane_prompt(
    *,
    bundle: dict[str, Any],
    kol_summary: dict[str, Any] | None,
    claim_lane: dict[str, Any],
    skeptic_lane: dict[str, Any],
    expression_lane: dict[str, Any],
    market_truth: dict[str, Any] | None = None,
) -> tuple[str, str]:
    opportunity = dict(bundle.get("opportunity") or {})
    context_payload = {
        "candidate": {
            "candidate_id": opportunity.get("candidate_id"),
            "thesis_name": opportunity.get("thesis_name"),
            "route": opportunity.get("route"),
            "residual_class": opportunity.get("residual_class"),
            "ranking_score": opportunity.get("ranking_score"),
            "note": opportunity.get("note"),
            "brief_next_action": opportunity.get("brief_next_action") or opportunity.get("next_action"),
            "brief_next_proving_milestone": opportunity.get("brief_next_proving_milestone") or opportunity.get("next_proving_milestone"),
        },
        "claim_lane": claim_lane,
        "skeptic_lane": skeptic_lane,
        "expression_lane": expression_lane,
        "kol_suite": kol_summary or {},
    }
    if market_truth:
        context_payload["market_truth"] = market_truth
    system_prompt = (
        "你是 Finbot 的 decision lane。"
        "你要把 scout、claim、skeptic、expression 的结果压成投资人能用的结论。"
        "输出要短、硬、可执行，并且必须明确 why not yet。"
    )
    market_truth_instruction = ""
    if market_truth:
        market_truth_instruction = (
            "\n\n重要：上下文中包含 `market_truth` 字段，这是实时市场数据（价格、市盈率、市值等）。"
            "请在估值分析中以此为锚点，而非凭空推测。如果当前估值明显偏高或偏低，请在 judgment 和 distance_to_action 中明确说明。"
        )
    prompt = (
        "请把下面的 lane 结果合成为 investor-grade dossier。\n\n"
        "先输出一个 ```json``` 代码块，字段固定为："
        "headline,current_decision,thesis_status,best_absorption_theme,best_expression_today,"
        "why_not_investable_yet,next_proving_milestone,forcing_events,disconfirming_signals,key_sources,research_gaps,"
        "distance_to_action,blocking_facts,thesis_change_summary。\n"
        "然后输出中文 Markdown，按以下小节：\n"
        "## One-line judgment\n## Why this surfaced now\n## Absorption path\n## Best expression today\n## Why not investable yet\n## Distance to action\n## Forcing events\n## Disconfirming signals\n## Source map\n## Research gaps\n"
        + market_truth_instruction
        + f"\n上下文：\n```json\n{_json_dumps(context_payload)}\n```"
    )
    return system_prompt, prompt


def _compose_lane_markdown(*, markdown: str, lane_slug: str, structured: dict[str, Any]) -> str:
    lines = [markdown.strip()] if markdown.strip() else []
    lines.extend(["", f"## {lane_slug.title()} Lane JSON", "```json", _json_dumps(structured), "```"])
    return "\n".join(line for line in lines if line is not None).strip() + "\n"


def _compose_research_package_markdown(*, markdown: str, lane_summaries: dict[str, Any]) -> str:
    lines = [markdown.strip()] if markdown.strip() else []
    lines.extend(["", "## Analysis Lanes"])
    claim = dict(lane_summaries.get("claim") or {})
    skeptic = dict(lane_summaries.get("skeptic") or {})
    expression = dict(lane_summaries.get("expression") or {})
    source_scorecard = list(lane_summaries.get("source_scorecard") or [])
    claim_objects = list(claim.get("claim_objects") or [])
    citation_objects = list(lane_summaries.get("citation_objects") or [])
    package_history = dict(lane_summaries.get("history") or {})
    if claim:
        lines.append("")
        lines.append("### Claim lane")
        for row in claim.get("core_claims") or []:
            lines.append(f"- {row}")
            for row in claim.get("claim_ledger") or []:
                claim_text = _text_value(row.get("claim"))
                grade = _text_value(row.get("evidence_grade"))
                why = _text_value(row.get("why_it_matters"))
                if claim_text:
                    lines.append(f"- ledger: {claim_text} | grade={grade or 'n/a'} | {why}")
            supporting_sources = list(row.get("supporting_sources") or [])
            if supporting_sources:
                lines.append(
                    "  - sources: "
                    + ", ".join(_text_value(source.get("name")) for source in supporting_sources if _text_value(source.get("name")))
                )
            for row in claim.get("critical_unknowns") or []:
                lines.append(f"- unknown: {row}")
        if claim_objects:
            lines.append("- claim objects:")
            for row in claim_objects:
                lines.append(
                    f"  - {row.get('claim_id')}: {_text_value(row.get('claim_text'))} | kind={_text_value(row.get('claim_kind')) or 'n/a'} | status={_text_value(row.get('status')) or 'n/a'} | falsified_if={_text_value(row.get('falsification_condition')) or 'n/a'}"
                )
    if skeptic:
        lines.append("")
        lines.append("### Skeptic lane")
        if _text_value(skeptic.get("bear_case")):
            lines.append(f"- bear_case: {skeptic.get('bear_case')}")
        for row in skeptic.get("risk_register") or []:
            risk = _text_value(row.get("risk"))
            severity = _text_value(row.get("severity"))
            horizon = _text_value(row.get("horizon"))
            if risk:
                lines.append(f"- risk: {risk} | severity={severity or 'n/a'} | horizon={horizon or 'n/a'}")
        for row in skeptic.get("disconfirming_signals") or []:
            lines.append(f"- disconfirming: {row}")
    if expression:
        lines.append("")
        lines.append("### Expression lane")
        valuation = dict(expression.get("valuation_frame") or {})
        if valuation:
            lines.append(
                "- valuation: "
                f"current={_text_value(valuation.get('current_view')) or 'n/a'} | "
                f"base={_text_value(valuation.get('base_case')) or 'n/a'} | "
                f"bull={_text_value(valuation.get('bull_case')) or 'n/a'} | "
                f"bear={_text_value(valuation.get('bear_case')) or 'n/a'}"
            )
        for row in expression.get("ranked_expressions") or []:
            expr = _text_value(row.get("expression"))
            why = _text_value(row.get("why_best"))
            valuation_anchor = _text_value(row.get("valuation_anchor"))
            if expr:
                lines.append(f"- {row.get('rank')}. {expr} | {why} | valuation={valuation_anchor or 'n/a'}")
    if source_scorecard:
        lines.append("")
        lines.append("### Source scorecard")
        for row in source_scorecard:
            lines.append(
                "- "
                f"{_text_value(row.get('name'))} | role={_text_value(row.get('contribution_role')) or 'n/a'} | "
                f"trust={_text_value(row.get('source_trust_tier')) or 'n/a'} | "
                f"track={_text_value(row.get('track_record_label')) or 'n/a'} | "
                f"quality={_text_value(row.get('quality_band')) or 'n/a'}({row.get('quality_score') or 0}) | "
                f"why={_text_value(row.get('reason')) or 'n/a'}"
            )
    if citation_objects:
        lines.append("")
        lines.append("### Citation register")
        for row in citation_objects:
            lines.append(
                "- "
                f"{_text_value(row.get('citation_id'))} | {_text_value(row.get('source_name'))} | "
                f"role={_text_value(row.get('contribution_role')) or 'n/a'} | quality={_text_value(row.get('quality_band')) or 'n/a'}"
            )
    if package_history:
        lines.append("")
        lines.append("### What changed")
        for row in package_history.get("summary_lines") or []:
            lines.append(f"- {row}")
    return "\n".join(line for line in lines if line is not None).strip() + "\n"


def _write_lane_artifacts(*, lanes_dir: Path, lane_slug: str, lane_result: dict[str, Any]) -> dict[str, str]:
    lanes_dir.mkdir(parents=True, exist_ok=True)
    json_path = lanes_dir / f"{lane_slug}.json"
    md_path = lanes_dir / f"{lane_slug}.md"
    tier_tag = _get_finbot_tier_tag()
    payload = {
        "schema_version": MULTILANE_SCHEMA_VERSION,
        "lane_slug": lane_slug,
        "provider": lane_result.get("provider"),
        "preset": lane_result.get("preset"),
        "latency_ms": lane_result.get("latency_ms"),
        "tier": tier_tag,
        "structured": lane_result.get("structured") or {},
    }
    json_path.write_text(_json_dumps(payload) + "\n", encoding="utf-8")
    md_path.write_text(
        _compose_lane_markdown(
            markdown=_text_value(lane_result.get("markdown")),
            lane_slug=lane_slug,
            structured=dict(lane_result.get("structured") or {}),
        ),
        encoding="utf-8",
    )
    return {"json_path": str(json_path), "markdown_path": str(md_path)}


def _should_promote_research_package(package_payload: dict[str, Any]) -> bool:
    """Check if a free-tier research package should be promoted to paid tier."""
    tier = package_payload.get("tier", "")
    if tier != "free-tier":
        return False

    decision = _text_value(package_payload.get("current_decision", ""))
    return decision in {"deepen_now", "prepare_candidate"}


def _build_research_package_item(package_payload: dict[str, Any]) -> InboxItem:
    candidate_id = _text_value(package_payload.get("candidate_id"))
    title = _text_value(package_payload.get("headline")) or candidate_id or "research-package"
    should_promote = _should_promote_research_package(package_payload)
    summary = " | ".join(
        part
        for part in [
            f"{candidate_id} → {package_payload.get('current_decision') or 'review'}",
            _text_value(package_payload.get("best_expression_today")),
            _text_value(package_payload.get("next_proving_milestone")),
        ]
        if part
    )
    tier_tag = package_payload.get("tier", "")
    tier_label = f"[{tier_tag}] " if tier_tag else ""
    if should_promote:
        action_hint = "Read the dossier. This high-priority opportunity qualifies for promotion to paid tier."
    else:
        action_hint = "Read the dossier before deciding whether to attach this opportunity to a tracked theme or open a dedicated research lane."
    return InboxItem(
        item_id=_inbox_item_id("finbot-package", candidate_id),
        created_at=time.time(),
        title=f"Finbot research package {tier_label}· {title}",
        summary=summary,
        category="research_package",
        severity="warning" if _text_value(package_payload.get("current_decision")) in {"deepen_now", "prepare_candidate"} else "accent",
        source="finbot.opportunity_deepen",
        action_hint=action_hint,
        payload=package_payload,
    )


def render_inbox_markdown(item: InboxItem) -> str:
    top = item.payload.get("priority_target") or {}
    queue_summary = item.payload.get("queue_summary") or {}
    lines = [
        f"# {item.title}",
        "",
        f"- item_id: `{item.item_id}`",
        f"- created_at: `{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.created_at))}`",
        f"- category: `{item.category}`",
        f"- severity: `{item.severity}`",
        f"- source: `{item.source}`",
        "",
        "## Summary",
        item.summary,
        "",
        "## Action Hint",
        item.action_hint,
    ]
    if top:
        lines.extend(
            [
                "",
                "## Priority Target",
                f"- thesis: `{top.get('thesis_title') or top.get('thesis_id') or ''}`",
                f"- target: `{top.get('target_case_id') or top.get('ticker_or_symbol') or ''}`",
                f"- posture: `{top.get('action_state') or top.get('raw_posture') or ''}`",
                f"- validation: `{top.get('validation_state') or ''}`",
                f"- reason: {top.get('reason') or ''}",
            ]
        )
    if queue_summary:
        lines.extend(["", "## Queue Summary"])
        for key, value in sorted(queue_summary.items()):
            lines.append(f"- `{key}`: {value}")
    if item.category in {"theme_radar", "theme_run"}:
        lines.extend(
            [
                "",
                "## Payload",
                "```json",
                json.dumps(item.payload, ensure_ascii=False, indent=2, sort_keys=True),
                "```",
            ]
        )
    if item.category == "deepening_brief":
        payload = item.payload
        lines.extend(
            [
                "",
                "## Deepening Brief",
                f"- candidate: `{payload.get('candidate_id') or ''}`",
                f"- route: `{payload.get('route') or ''}`",
                f"- class: `{payload.get('residual_class') or ''}`",
                f"- next_action: `{payload.get('next_action') or ''}`",
                f"- next_proving_milestone: {payload.get('next_proving_milestone') or 'n/a'}",
                f"- note: {payload.get('note') or ''}",
                "",
                "## Related Themes",
            ]
        )
        for theme in payload.get("related_themes") or []:
            lines.append(
                f"- `{theme.get('title') or theme.get('theme_slug')}` | best={theme.get('best_expression') or 'n/a'} | detail={theme.get('detail_href') or ''}"
            )
        if payload.get("suggested_sources"):
            lines.extend(["", "## Suggested Sources"])
            for row in payload.get("suggested_sources") or []:
                lines.append(f"- {row}")
        if payload.get("research_questions"):
            lines.extend(["", "## Research Questions"])
            for row in payload.get("research_questions") or []:
                lines.append(f"- {row}")
    if item.category == "research_package":
        payload = item.payload
        lines.extend(
            [
                "",
                "## Research Package",
                f"- candidate: `{payload.get('candidate_id') or ''}`",
                f"- decision: `{payload.get('current_decision') or ''}`",
                f"- thesis_status: `{payload.get('thesis_status') or ''}`",
                f"- best_absorption_theme: `{payload.get('best_absorption_theme') or ''}`",
                f"- best_expression_today: {payload.get('best_expression_today') or 'n/a'}",
                f"- why_not_investable_yet: {payload.get('why_not_investable_yet') or 'n/a'}",
                f"- next_proving_milestone: {payload.get('next_proving_milestone') or 'n/a'}",
            ]
        )
        lanes = payload.get("lanes") if isinstance(payload.get("lanes"), dict) else {}
        claim_lane = lanes.get("claim") if isinstance(lanes.get("claim"), dict) else {}
        skeptic_lane = lanes.get("skeptic") if isinstance(lanes.get("skeptic"), dict) else {}
        expression_lane = lanes.get("expression") if isinstance(lanes.get("expression"), dict) else {}
        if claim_lane:
            lines.extend(["", "## Claim Lane"])
            for row in claim_lane.get("core_claims") or []:
                lines.append(f"- {row}")
            for row in claim_lane.get("claim_ledger") or []:
                claim_text = _text_value(row.get("claim"))
                grade = _text_value(row.get("evidence_grade"))
                if claim_text:
                    lines.append(f"- ledger: {claim_text} | grade={grade or 'n/a'}")
                supporting_sources = list(row.get("supporting_sources") or [])
                if supporting_sources:
                    lines.append(
                        "  - sources: "
                        + ", ".join(_text_value(source.get("name")) for source in supporting_sources if _text_value(source.get("name")))
                    )
        if skeptic_lane:
            lines.extend(["", "## Skeptic Lane"])
            if skeptic_lane.get("bear_case"):
                lines.append(f"- bear_case: {skeptic_lane.get('bear_case')}")
            for row in skeptic_lane.get("disconfirming_signals") or []:
                lines.append(f"- {row}")
            for row in skeptic_lane.get("risk_register") or []:
                risk = _text_value(row.get("risk"))
                severity = _text_value(row.get("severity"))
                if risk:
                    lines.append(f"- risk: {risk} | severity={severity or 'n/a'}")
        if expression_lane:
            lines.extend(["", "## Expression Lane"])
            valuation = dict(expression_lane.get("valuation_frame") or {})
            if valuation:
                lines.append(
                    "- valuation: "
                    f"current={_text_value(valuation.get('current_view')) or 'n/a'} | "
                    f"base={_text_value(valuation.get('base_case')) or 'n/a'} | "
                    f"bull={_text_value(valuation.get('bull_case')) or 'n/a'} | "
                    f"bear={_text_value(valuation.get('bear_case')) or 'n/a'}"
                )
            for row in expression_lane.get("ranked_expressions") or []:
                expr = _text_value(row.get("expression"))
                if expr:
                    lines.append(f"- {row.get('rank')}. {expr}")
        if payload.get("source_scorecard"):
            lines.extend(["", "## Source Scorecard"])
            for row in payload.get("source_scorecard") or []:
                lines.append(
                    "- "
                    f"{_text_value(row.get('name'))} | role={_text_value(row.get('contribution_role')) or 'n/a'} | "
                    f"trust={_text_value(row.get('source_trust_tier')) or 'n/a'} | "
                    f"track={_text_value(row.get('track_record_label')) or 'n/a'}"
                )
        if payload.get("forcing_events"):
            lines.extend(["", "## Forcing Events"])
            for row in payload.get("forcing_events") or []:
                lines.append(f"- {row}")
        if payload.get("disconfirming_signals"):
            lines.extend(["", "## Disconfirming Signals"])
            for row in payload.get("disconfirming_signals") or []:
                lines.append(f"- {row}")
        if payload.get("research_gaps"):
            lines.extend(["", "## Research Gaps"])
            for row in payload.get("research_gaps") or []:
                lines.append(f"- {row}")
        if payload.get("markdown_path"):
            lines.extend(["", "## Artifact", f"- dossier: `{payload.get('markdown_path')}`"])
    return "\n".join(lines).strip() + "\n"


def write_inbox_item(item: InboxItem, *, root: Path = DEFAULT_FINBOT_ROOT) -> dict[str, Any]:
    dirs = ensure_inbox_dirs(root)
    json_path = dirs["pending"] / f"{item.item_id}.json"
    md_path = dirs["pending"] / f"{item.item_id}.md"
    _coalesce_pending_duplicates(item, dirs=dirs)
    payload = {
        "item_id": item.item_id,
        "created_at": item.created_at,
        "updated_at": time.time(),
        "title": item.title,
        "summary": item.summary,
        "category": item.category,
        "severity": item.severity,
        "source": item.source,
        "action_hint": item.action_hint,
        "payload": item.payload,
    }
    if json_path.exists():
        existing = json.loads(json_path.read_text(encoding="utf-8"))
        existing_payload = dict(existing)
        existing_payload.pop("updated_at", None)
        candidate_payload = dict(payload)
        candidate_payload.pop("updated_at", None)
        if existing_payload == candidate_payload:
            return {
                "ok": True,
                "created": False,
                "updated": False,
                "item_id": item.item_id,
                "json_path": str(json_path),
                "markdown_path": str(md_path),
                "summary": existing.get("summary") or "",
            }
        json_path.write_text(_json_dumps(payload) + "\n", encoding="utf-8")
        md_path.write_text(render_inbox_markdown(item), encoding="utf-8")
        return {
            "ok": True,
            "created": False,
            "updated": True,
            "item_id": item.item_id,
            "json_path": str(json_path),
            "markdown_path": str(md_path),
            "summary": item.summary,
        }
    json_path.write_text(_json_dumps(payload) + "\n", encoding="utf-8")
    md_path.write_text(render_inbox_markdown(item), encoding="utf-8")
    return {
        "ok": True,
        "created": True,
        "updated": False,
        "item_id": item.item_id,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "summary": item.summary,
    }


def opportunity_deepen(
    *,
    candidate_id: str | None = None,
    finagent_root: Path = DEFAULT_FINAGENT_ROOT,
    python_bin: str = DEFAULT_FINAGENT_PYTHON,
    root: Path = DEFAULT_FINBOT_ROOT,
    force: bool = False,
    max_age_hours: int = DEFAULT_RESEARCH_PACKAGE_MAX_AGE_HOURS,
) -> dict[str, Any]:
    service = DashboardService(load_config())
    snapshot = service.investor_snapshot()
    opportunities = list(snapshot.get("opportunities") or [])
    target = None
    if candidate_id:
        target = next((item for item in opportunities if _text_value(item.get("candidate_id")) == candidate_id), None)
    else:
        target = next(
            (
                item
                for item in opportunities
                if _text_value(item.get("route")) == "opportunity"
                and _text_value(item.get("residual_class")) in {"frontier", "adjacent"}
            ),
            opportunities[0] if opportunities else None,
        )
    if target is None:
        return {"ok": True, "created": False, "reason": "no_opportunity_candidate"}

    candidate_id = _text_value(target.get("candidate_id"))
    latest = _load_latest_research_package(root=root, candidate_id=candidate_id)
    if not force and _package_is_fresh(latest, max_age_hours=max_age_hours):
        return {
            "ok": True,
            "created": False,
            "reason": "fresh_package_exists",
            "candidate_id": candidate_id,
            "latest_json_path": latest.get("json_path") if latest else "",
        }
    previous_payload = latest if latest else None

    bundle = _opportunity_context_bundle(service=service, snapshot=snapshot, candidate_id=candidate_id)
    dirs = _opportunity_dirs(root, candidate_id)
    ts = time.strftime("%Y%m%d_%H%M%S")
    history_dir = dirs["history"] / ts
    history_dir.mkdir(parents=True, exist_ok=True)

    kol_summary: dict[str, Any] | None = None
    suite_slug = f"finbot_{_candidate_slug(candidate_id)}"

    # --- Phase 3: Parallel lane execution ---
    # Stage 1: KOL suite + Claim lane in parallel (independent)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="finbot-lane") as executor:
        def _run_kol() -> dict[str, Any] | None:
            try:
                return _run_kol_suite(
                    finagent_root=finagent_root,
                    python_bin=python_bin,
                    run_root=history_dir / "kol_suite",
                    suite_slug=suite_slug,
                )
            except Exception as exc:
                return {"ok": False, "error": str(exc), "suite_slug": suite_slug}

        def _run_claim() -> dict[str, Any]:
            cs, cp = _build_claim_lane_prompt(bundle=bundle, kol_summary=None)
            return _run_lane_with_retry(lane_slug="claim", system_prompt=cs, prompt=cp)

        kol_future: Future[dict[str, Any] | None] = executor.submit(_run_kol)
        claim_future: Future[dict[str, Any]] = executor.submit(_run_claim)

        kol_summary = kol_future.result()
        claim_result = claim_future.result()
    claim_structured = dict(claim_result.get("structured") or {})

    # Stage 2: Skeptic lane (depends on claim output)
    skeptic_system, skeptic_prompt = _build_skeptic_lane_prompt(bundle=bundle, claim_lane=claim_structured)
    skeptic_result = _run_lane_with_retry(lane_slug="skeptic", system_prompt=skeptic_system, prompt=skeptic_prompt)
    skeptic_structured = dict(skeptic_result.get("structured") or {})

    # Stage 3: Expression lane + Market Truth fetch in parallel
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="finbot-stage3") as executor:
        def _run_expression() -> dict[str, Any]:
            es, ep = _build_expression_lane_prompt(
                bundle=bundle,
                claim_lane=claim_structured,
                skeptic_lane=skeptic_structured,
            )
            return _run_lane_with_retry(lane_slug="expression", system_prompt=es, prompt=ep)

        def _run_market() -> dict[str, Any] | None:
            opp = dict(bundle.get("opportunity") or {})
            ticker = _text_value(
                opp.get("ticker_or_symbol")
                or opp.get("ticker")
                or opp.get("target_case_id")
            )
            if not ticker:
                return None
            inferred = _infer_market_from_ticker(ticker)
            return _fetch_market_truth(
                finagent_root=finagent_root,
                python_bin=python_bin,
                ticker=ticker,
                market=inferred,
            )

        expression_future: Future[dict[str, Any]] = executor.submit(_run_expression)
        market_future: Future[dict[str, Any] | None] = executor.submit(_run_market)

        expression_result = expression_future.result()
        market_truth = market_future.result()
    expression_structured = dict(expression_result.get("structured") or {})
    expression_ranking = _coerce_ranked_expressions(expression_structured.get("ranked_expressions") or [])
    expression_leader = _text_value(expression_structured.get("leader") or (expression_ranking[0]["expression"] if expression_ranking else ""))
    claim_core_claims = _coerce_string_list(claim_structured.get("core_claims") or [])
    claim_supporting_evidence = _coerce_string_list(claim_structured.get("supporting_evidence") or [])
    claim_critical_unknowns = _coerce_string_list(claim_structured.get("critical_unknowns") or [])
    skeptic_thesis_breakers = _coerce_string_list(skeptic_structured.get("thesis_breakers") or [])
    skeptic_timing_risks = _coerce_string_list(skeptic_structured.get("timing_risks") or [])

    # Stage 4: Decision lane (synthesizes all lane outputs)
    decision_system, decision_prompt = _build_decision_lane_prompt(
        bundle=bundle,
        kol_summary=kol_summary,
        claim_lane=claim_structured,
        skeptic_lane=skeptic_structured,
        expression_lane={**expression_structured, "ranked_expressions": expression_ranking},
        market_truth=market_truth,
    )
    llm_result = _ask_coding_plan_dossier(system_prompt=decision_system, prompt=decision_prompt)
    structured = dict(llm_result.get("structured") or {})
    markdown = _text_value(llm_result.get("markdown"))

    related_themes = list(bundle.get("opportunity", {}).get("related_themes") or [])
    related_sources = list(bundle.get("related_sources") or [])
    key_sources = _coerce_string_list(structured.get("key_sources") or bundle.get("opportunity", {}).get("suggested_sources") or [])
    skeptic_disconfirming = _coerce_string_list(skeptic_structured.get("disconfirming_signals") or structured.get("disconfirming_signals") or [])
    expression_comparison_logic = _coerce_string_list(expression_structured.get("comparison_logic") or [])
    claim_ledger = _coerce_claim_ledger(claim_structured.get("claim_ledger") or []) or _default_claim_ledger(
        thesis_name=_text_value(bundle["opportunity"].get("thesis_name")),
        core_claims=claim_core_claims,
        supporting_evidence=claim_supporting_evidence,
        critical_unknowns=claim_critical_unknowns,
    )
    risk_register = _coerce_risk_register(skeptic_structured.get("risk_register") or []) or _default_risk_register(
        thesis_breakers=skeptic_thesis_breakers,
        timing_risks=skeptic_timing_risks,
        disconfirming_signals=skeptic_disconfirming,
    )
    valuation_frame = _coerce_valuation_frame(
        expression_structured.get("valuation_frame") or {},
        market_truth=market_truth,
    ) or _default_valuation_frame(
        leader=expression_leader,
        comparison_logic=expression_comparison_logic,
        ranked_expressions=expression_ranking,
    )
    if market_truth and "market_truth" not in valuation_frame:
        valuation_frame["market_truth"] = market_truth
    source_scorecard = _build_source_scorecard(
        related_sources=related_sources,
        key_sources=key_sources,
    )
    claim_ledger = _enrich_claim_ledger_with_sources(
        claim_ledger=claim_ledger,
        source_scorecard=source_scorecard,
    )
    claim_ledger = _annotate_claim_rows(candidate_id=candidate_id, claim_ledger=claim_ledger)
    claim_objects = _build_claim_objects(
        candidate_id=candidate_id,
        claim_ledger=claim_ledger,
        previous_payload=previous_payload,
        disconfirming_signals=skeptic_disconfirming,
    )
    citation_objects = _build_citation_objects(source_scorecard=source_scorecard)
    claim_citation_edges = _build_claim_citation_edges(
        claim_ledger=claim_ledger,
        claim_objects=claim_objects,
        citation_objects=citation_objects,
    )
    provisional_payload = {
        "current_decision": _text_value(structured.get("current_decision") or bundle["opportunity"].get("brief_next_action") or "deepen_now"),
        "best_expression_today": _text_value(structured.get("best_expression_today") or expression_leader or (related_themes[0].get("best_expression") if related_themes else "")),
        "best_absorption_theme": _text_value(structured.get("best_absorption_theme") or (related_themes[0]["title"] if related_themes else "")),
        "next_proving_milestone": _text_value(structured.get("next_proving_milestone") or bundle["opportunity"].get("brief_next_proving_milestone")),
        "why_not_investable_yet": _text_value(structured.get("why_not_investable_yet") or bundle["opportunity"].get("note")),
        "claim_objects": claim_objects,
        "lanes": {"skeptic": {"risk_register": risk_register}},
    }
    provisional_history = _build_package_history(
        previous_payload=previous_payload,
        current_payload=provisional_payload,
        source_scores={"updates": []},
    )
    source_scores = _update_source_score_ledger(
        root=root,
        candidate_id=candidate_id,
        theme_slugs=_extract_theme_slugs(related_themes),
        source_scorecard=source_scorecard,
        claim_citation_edges=claim_citation_edges,
        claim_objects=claim_objects,
        history=provisional_history,
    )
    score_lookup = _source_score_update_lookup(source_scores)
    source_scorecard = [
        {
            **row,
            **(
                score_lookup.get(_text_value(row.get("source_id") or row.get("name")))
                or {}
            ),
        }
        for row in source_scorecard
    ]
    citation_objects = _build_citation_objects(source_scorecard=source_scorecard, source_scores_lookup=score_lookup)
    lane_summaries = {
        "claim": {
            "core_claims": claim_core_claims,
            "supporting_evidence": claim_supporting_evidence,
            "critical_unknowns": claim_critical_unknowns,
            "key_sources": _coerce_string_list(claim_structured.get("key_sources") or key_sources),
            "absorption_candidates": _coerce_string_list(claim_structured.get("absorption_candidates") or []),
            "claim_ledger": claim_ledger,
            "claim_objects": claim_objects,
        },
        "skeptic": {
            "bear_case": _text_value(skeptic_structured.get("bear_case")),
            "thesis_breakers": skeptic_thesis_breakers,
            "timing_risks": skeptic_timing_risks,
            "competing_paths": _coerce_string_list(skeptic_structured.get("competing_paths") or []),
            "disconfirming_signals": skeptic_disconfirming,
            "risk_register": risk_register,
        },
        "expression": {
            "leader": expression_leader,
            "comparison_logic": expression_comparison_logic,
            "ranked_expressions": expression_ranking[:3],
            "valuation_frame": valuation_frame,
        },
        "source_scorecard": source_scorecard,
        "citation_objects": citation_objects,
    }
    package_payload = {
        "schema_version": DOSSIER_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "headline": _text_value(structured.get("headline") or bundle["opportunity"].get("thesis_name")),
        "thesis_name": _text_value(bundle["opportunity"].get("thesis_name")),
        "current_decision": _text_value(structured.get("current_decision") or bundle["opportunity"].get("brief_next_action") or "deepen_now"),
        "thesis_status": _text_value(structured.get("thesis_status") or "emerging"),
        "best_absorption_theme": _text_value(structured.get("best_absorption_theme") or (related_themes[0]["title"] if related_themes else "")),
        "best_expression_today": _text_value(structured.get("best_expression_today") or expression_leader or (related_themes[0].get("best_expression") if related_themes else "")),
        "why_not_investable_yet": _text_value(structured.get("why_not_investable_yet") or bundle["opportunity"].get("note")),
        "next_proving_milestone": _text_value(structured.get("next_proving_milestone") or bundle["opportunity"].get("brief_next_proving_milestone")),
        "forcing_events": _coerce_string_list(structured.get("forcing_events") or []),
        "disconfirming_signals": _coerce_string_list(structured.get("disconfirming_signals") or []),
        "key_sources": key_sources,
        "research_gaps": _coerce_string_list(structured.get("research_gaps") or []),
        "distance_to_action": _text_value(structured.get("distance_to_action")),
        "blocking_facts": _coerce_string_list(structured.get("blocking_facts") or []),
        "thesis_change_summary": _text_value(structured.get("thesis_change_summary")),
        "lanes": lane_summaries,
        "related_themes": related_themes,
        "related_sources": related_sources,
        "source_scorecard": source_scorecard,
        "source_scores": source_scores,
        "claim_objects": claim_objects,
        "citation_objects": citation_objects,
        "claim_citation_edges": claim_citation_edges,
        "planning_doc_reader_href": bundle.get("planning_doc_reader_href"),
        "generated_at": time.time(),
        "provider": llm_result.get("provider"),
        "preset": llm_result.get("preset"),
        "latency_ms": llm_result.get("latency_ms"),
        "note": _text_value(bundle["opportunity"].get("note")),
        "route": _text_value(bundle["opportunity"].get("route")),
        "residual_class": _text_value(bundle["opportunity"].get("residual_class")),
    }
    package_payload["intelligence_requirements"] = _build_intelligence_requirements(
        next_proving_milestone=_text_value(package_payload.get("next_proving_milestone")),
        blocking_facts=list(package_payload.get("blocking_facts") or []),
        research_gaps=list(package_payload.get("research_gaps") or []),
        key_sources=list(package_payload.get("key_sources") or []),
    )
    package_payload["history"] = _build_package_history(
        previous_payload=previous_payload,
        current_payload=package_payload,
        source_scores=source_scores,
    )
    lane_summaries["history"] = package_payload["history"]
    context_payload = {
        "candidate_id": candidate_id,
        "generated_at": package_payload["generated_at"],
        "bundle": bundle,
        "kol_suite": kol_summary,
        "lanes": {
            "claim": claim_structured,
            "skeptic": skeptic_structured,
            "expression": {**expression_structured, "ranked_expressions": expression_ranking},
            "decision": structured,
        },
    }

    tier_tag = _get_finbot_tier_tag()
    package_payload["tier"] = tier_tag

    json_path = history_dir / "research_package.json"
    md_path = history_dir / "research_package.md"
    context_path = history_dir / "research_context.json"
    lanes_dir = history_dir / "lanes"
    lane_artifacts = {
        "claim": _write_lane_artifacts(lanes_dir=lanes_dir, lane_slug="claim", lane_result=claim_result),
        "skeptic": _write_lane_artifacts(lanes_dir=lanes_dir, lane_slug="skeptic", lane_result=skeptic_result),
        "expression": _write_lane_artifacts(lanes_dir=lanes_dir, lane_slug="expression", lane_result=expression_result),
        "decision": _write_lane_artifacts(lanes_dir=lanes_dir, lane_slug="decision", lane_result=llm_result),
    }
    package_payload["lane_artifacts"] = lane_artifacts
    json_path.write_text(_json_dumps(package_payload) + "\n", encoding="utf-8")
    md_path.write_text(_compose_research_package_markdown(markdown=markdown, lane_summaries=lane_summaries), encoding="utf-8")
    context_path.write_text(_json_dumps(context_payload) + "\n", encoding="utf-8")

    latest_payload = {**package_payload, "json_path": str(json_path), "markdown_path": str(md_path), "context_path": str(context_path)}
    dirs["latest_json"].write_text(_json_dumps(latest_payload) + "\n", encoding="utf-8")
    dirs["latest_md"].write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    dirs["latest_context"].write_text(_json_dumps(context_payload) + "\n", encoding="utf-8")

    package_item = _build_research_package_item({**latest_payload, "logical_key": candidate_id})
    inbox_result = write_inbox_item(package_item, root=root)
    return {
        "ok": True,
        "created": bool(inbox_result.get("created") or inbox_result.get("updated")),
        "candidate_id": candidate_id,
        "package": latest_payload,
        "inbox_item": inbox_result,
        "kol_suite": kol_summary,
    }


def _run_market_screen(
    *,
    finagent_root: Path,
    python_bin: str,
    market: str = "CN",
    strategy: str = "value",
    limit: int = 10,
    all_markets: bool = False,
) -> dict[str, Any]:
    """Run finagent market-screen CLI and return parsed results."""
    args = ["market-screen", "--strategy", strategy, "--limit", str(limit)]
    if all_markets:
        args.append("--all-markets")
    else:
        args.extend(["--market", market])
    return _run_finagent_json_command(
        finagent_root=finagent_root,
        python_bin=python_bin,
        args=args,
    )


def market_discovery_scout(
    *,
    finagent_root: Path = DEFAULT_FINAGENT_ROOT,
    python_bin: str = DEFAULT_FINAGENT_PYTHON,
    root: Path = DEFAULT_FINBOT_ROOT,
    strategy: str = "value",
    limit: int = 10,
    all_markets: bool = True,
    auto_deepen_top: bool = True,
    max_age_hours: int = DEFAULT_RESEARCH_PACKAGE_MAX_AGE_HOURS,
) -> dict[str, Any]:
    """Discover new opportunities across markets using quantitative screening.

    Unlike watchlist_scout (which only checks known watchlist) and
    theme_radar_scout (which only checks theme catalog), this function
    scans the full market to surface stocks the user hasn't seen yet.
    """
    try:
        screen_result = _run_market_screen(
            finagent_root=finagent_root,
            python_bin=python_bin,
            strategy=strategy,
            limit=limit,
            all_markets=all_markets,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "strategy": strategy}

    candidates = screen_result.get("candidates") or []
    if not candidates:
        return {
            "ok": True,
            "created": False,
            "reason": "no_discovery_candidates",
            "strategy": strategy,
            "scanned_count": screen_result.get("scanned_count", 0),
        }

    # Filter out candidates already in current watchlist/snapshot
    try:
        service = DashboardService(load_config())
        snapshot = service.investor_snapshot()
        existing_ids = {
            str(op.get("candidate_id") or "").lower()
            for theme in snapshot.get("themes", [])
            for op in theme.get("related_opportunities", [])
        }
        existing_tickers = {
            str(op.get("ticker") or op.get("ticker_or_symbol") or "").upper()
            for theme in snapshot.get("themes", [])
            for op in theme.get("related_opportunities", [])
        }
    except Exception:
        existing_ids = set()
        existing_tickers = set()

    new_candidates = [
        c for c in candidates
        if c.get("ticker", "").upper() not in existing_tickers
        and c.get("ticker", "").lower() not in existing_ids
    ]

    if not new_candidates:
        return {
            "ok": True,
            "created": False,
            "reason": "all_candidates_already_tracked",
            "strategy": strategy,
            "scanned_count": screen_result.get("scanned_count", 0),
            "total_candidates": len(candidates),
        }

    # Create inbox item for new discoveries
    discovery_summary = ", ".join(
        f"{c.get('ticker')} ({c.get('name', '?')}, score={c.get('screen_score', 0)})"
        for c in new_candidates[:5]
    )
    item = InboxItem(
        item_id=f"discovery_{strategy}_{time.strftime('%Y%m%d_%H%M%S')}",
        source="market_discovery",
        summary=f"[{strategy}策略] 发现 {len(new_candidates)} 个新机会: {discovery_summary}",
        payload={
            "strategy": strategy,
            "candidates": new_candidates[:limit],
            "screen_metadata": {
                "scanned_count": screen_result.get("scanned_count", 0),
                "passed_filter_count": screen_result.get("passed_filter_count", 0),
                "elapsed_ms": screen_result.get("elapsed_ms", 0),
            },
        },
        priority="medium",
    )
    write_result = write_inbox_item(item, root=root)

    # Optionally auto-deepen the top candidate
    deepen_result: dict[str, Any] | None = None
    if auto_deepen_top and new_candidates:
        top = new_candidates[0]
        top_ticker = top.get("ticker", "")
        top_name = top.get("name", "")
        try:
            deepen_result = opportunity_deepen(
                candidate_id=f"discovery_{top_ticker}",
                finagent_root=finagent_root,
                python_bin=python_bin,
                root=root,
                force=False,
                max_age_hours=max_age_hours,
            )
        except Exception as exc:
            deepen_result = {"ok": False, "error": str(exc), "ticker": top_ticker, "name": top_name}

    return {
        **write_result,
        "strategy": strategy,
        "new_candidates_count": len(new_candidates),
        "top_candidates": new_candidates[:5],
        "deepen_result": deepen_result,
        "scanned_count": screen_result.get("scanned_count", 0),
    }


def watchlist_scout(
    *,
    finagent_root: Path = DEFAULT_FINAGENT_ROOT,
    python_bin: str = DEFAULT_FINAGENT_PYTHON,
    root: Path = DEFAULT_FINBOT_ROOT,
    scope: str = "today",
    limit: int = 8,
) -> dict[str, Any]:
    snapshot = _run_finagent_snapshot(finagent_root=finagent_root, python_bin=python_bin, scope=scope, limit=limit)
    item = _build_watchlist_item(snapshot)
    if item is None:
        return {"ok": True, "created": False, "reason": "no_actionable_watchlist_delta", "scope": scope}
    result = write_inbox_item(item, root=root)
    result["scope"] = scope
    result["priority_target"] = snapshot.get("priority_targets", [])[:1]
    return result


def theme_radar_scout(
    *,
    finagent_root: Path = DEFAULT_FINAGENT_ROOT,
    python_bin: str = DEFAULT_FINAGENT_PYTHON,
    root: Path = DEFAULT_FINBOT_ROOT,
    limit: int = 8,
    auto_deepen: bool = True,
    deepen_max_age_hours: int = DEFAULT_RESEARCH_PACKAGE_MAX_AGE_HOURS,
) -> dict[str, Any]:
    radar = _run_theme_radar_board(finagent_root=finagent_root, python_bin=python_bin, limit=limit)
    inbox = _run_opportunity_inbox(finagent_root=finagent_root, python_bin=python_bin, limit=limit)
    item = _build_theme_radar_item(radar, inbox)
    if item is None:
        return {"ok": True, "created": False, "reason": "no_theme_radar_candidate", "limit": limit}
    result = write_inbox_item(item, root=root)
    top_candidate = (inbox.get("items") or radar.get("items") or [])[:1]
    brief_result: dict[str, Any] | None = None
    if top_candidate:
        try:
            investor_snapshot = DashboardService(load_config()).investor_snapshot()
        except Exception:
            investor_snapshot = {}
        related_themes = [
            theme
            for theme in investor_snapshot.get("themes", [])
            if any(str(op.get("candidate_id") or "") == str(top_candidate[0].get("candidate_id") or "") for op in theme.get("related_opportunities", []))
        ] if investor_snapshot else []
        brief = _build_theme_radar_brief_item(top_candidate[0], related_themes=related_themes)
        if brief is not None:
            brief_result = write_inbox_item(brief, root=root)
    package_result: dict[str, Any] | None = None
    if auto_deepen and top_candidate:
        try:
            package_result = opportunity_deepen(
                candidate_id=_text_value(top_candidate[0].get("candidate_id")),
                finagent_root=finagent_root,
                python_bin=python_bin,
                root=root,
                force=False,
                max_age_hours=deepen_max_age_hours,
            )
        except Exception as exc:
            package_result = {"ok": False, "error": str(exc), "candidate_id": _text_value(top_candidate[0].get("candidate_id"))}
    result["radar_summary"] = radar.get("summary") or {}
    result["top_candidate"] = top_candidate
    result["deepening_brief"] = brief_result
    result["research_package"] = package_result
    return result


def theme_batch_run(
    *,
    finagent_root: Path = DEFAULT_FINAGENT_ROOT,
    python_bin: str = DEFAULT_FINAGENT_PYTHON,
    root: Path = DEFAULT_FINBOT_ROOT,
    catalog_path: Path = DEFAULT_THEME_CATALOG_PATH,
    limit: int = 5,
) -> dict[str, Any]:
    catalog = load_theme_catalog(catalog_path)
    themes = list(catalog.get("themes") or [])[: max(1, int(limit))]
    run_dir = root / "theme_runs" / time.strftime("%Y-%m-%d")
    run_dir.mkdir(parents=True, exist_ok=True)
    created_items: list[dict[str, Any]] = []
    run_results: list[dict[str, Any]] = []
    for theme in themes:
        theme_slug = str(theme.get("theme_slug") or "").strip()
        if not theme_slug:
            continue
        spec_context: dict[str, Any] = {}
        spec_path = (finagent_root / str(theme.get("spec_path"))).resolve()
        if spec_path.exists():
            try:
                import yaml  # type: ignore[import-untyped]

                loaded = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
                if isinstance(loaded, dict):
                    spec_context = dict(loaded.get("theme") or {})
            except Exception:
                spec_context = {}
        theme = {**theme, "spec_context": spec_context}
        run_root = run_dir / theme_slug
        result = _run_finagent_script_json(
            finagent_root=finagent_root,
            python_bin=python_bin,
            script_rel="scripts/run_event_mining_theme_suite.py",
            args=[
                "--run-root",
                str(run_root),
                "--spec",
                str((finagent_root / str(theme.get("spec_path"))).resolve()),
                "--events",
                str((finagent_root / str(theme.get("events_path"))).resolve()),
                "--as-of",
                str(theme.get("as_of") or time.strftime("%Y-%m-%d")),
                "--theme-slug",
                theme_slug,
            ],
            timeout=int(theme.get("timeout_seconds") or 600),
        )
        theme_state = _write_theme_state_snapshot(root=root, theme=theme, result=result)
        if theme_state:
            result = {**result, "theme_state": theme_state}
        run_results.append(result)
        item = _build_theme_run_item(theme, result)
        if item is not None:
            created_items.append(write_inbox_item(item, root=root))
    return {
        "ok": True,
        "theme_count": len(themes),
        "created_items": created_items,
        "runs": [
            {
                "theme_slug": result.get("theme_slug"),
                "recommended_posture": result.get("recommended_posture"),
                "best_expression": (result.get("best_expression") or {}).get("entity"),
                "run_root": result.get("run_root"),
            }
            for result in run_results
        ],
        "catalog_path": str(catalog_path),
    }


# ---------------------------------------------------------------------------
# Strategy rotation & trading-hours awareness
# ---------------------------------------------------------------------------

_DISCOVERY_STRATEGIES = ["value", "momentum", "growth", "contrarian"]

_STRATEGY_COMPLEMENTS = {
    "value": "momentum",
    "momentum": "contrarian",
    "growth": "value",
    "contrarian": "growth",
}


def _pick_discovery_strategy() -> str:
    """Round-robin strategy based on current hour."""
    import datetime
    hour = datetime.datetime.now().hour
    idx = hour % len(_DISCOVERY_STRATEGIES)
    return _DISCOVERY_STRATEGIES[idx]


def _is_any_market_open() -> bool:
    """Check if any major market is currently open (CST timezone).

    CN: 09:30-15:00, HK: 09:30-16:00, US: 21:30-04:00 (next day CST).
    Returns False on weekends.
    """
    import datetime
    now = datetime.datetime.now()
    hour = now.hour
    weekday = now.weekday()
    if weekday >= 5:  # Saturday, Sunday
        return False
    # CN/HK session: 9-16
    if 9 <= hour <= 16:
        return True
    # US session: 21:30-04:00 CST (approx)
    if hour >= 21 or hour <= 4:
        return True
    return False


def daily_work(
    *,
    finagent_root: Path = DEFAULT_FINAGENT_ROOT,
    python_bin: str = DEFAULT_FINAGENT_PYTHON,
    root: Path = DEFAULT_FINBOT_ROOT,
    scope: str = "today",
    limit: int = 8,
    include_source_refresh: bool = True,
    refresh_limit: int = 5,
    include_theme_batch: bool = False,
    include_market_discovery: bool = True,
    discovery_strategy: str = "auto",
    catalog_path: Path = DEFAULT_THEME_CATALOG_PATH,
) -> dict[str, Any]:
    refresh = refresh_dashboard_projection()
    source_refresh: dict[str, Any] | None = None
    if include_source_refresh:
        try:
            source_refresh = _run_finagent_daily_refresh(
                finagent_root=finagent_root,
                python_bin=python_bin,
                limit=refresh_limit,
            )
        except Exception as exc:
            source_refresh = {"ok": False, "error": str(exc), "limit": refresh_limit}
    watchlist = watchlist_scout(finagent_root=finagent_root, python_bin=python_bin, root=root, scope=scope, limit=limit)
    radar = theme_radar_scout(finagent_root=finagent_root, python_bin=python_bin, root=root, limit=limit)
    payload: dict[str, Any] = {
        "ok": True,
        "refresh": refresh,
        "source_refresh": source_refresh,
        "watchlist": watchlist,
        "theme_radar": radar,
        "created_count": int(bool(watchlist.get("created") or watchlist.get("updated"))) + int(bool(radar.get("created") or radar.get("updated"))),
    }
    if radar.get("deepening_brief"):
        payload["created_count"] += int(bool(radar["deepening_brief"].get("created") or radar["deepening_brief"].get("updated")))
    if radar.get("research_package"):
        package_result = radar["research_package"]
        if isinstance(package_result, dict):
            payload["created_count"] += int(bool(package_result.get("created")))
    # --- Market discovery with multi-strategy rotation ---
    if include_market_discovery and _is_any_market_open():
        # Resolve strategy
        primary_strategy = discovery_strategy
        if primary_strategy == "auto":
            primary_strategy = _pick_discovery_strategy()
        # Build strategy list: primary + complement
        strategies_to_run = [primary_strategy]
        complement = _STRATEGY_COMPLEMENTS.get(primary_strategy)
        if complement:
            strategies_to_run.append(complement)
        # Run each strategy
        discovery_results: list[dict[str, Any]] = []
        for strat in strategies_to_run:
            try:
                disc = market_discovery_scout(
                    finagent_root=finagent_root,
                    python_bin=python_bin,
                    root=root,
                    strategy=strat,
                    all_markets=True,
                    auto_deepen_top=False,
                )
                discovery_results.append(disc)
                if disc.get("created"):
                    payload["created_count"] += 1
            except Exception as exc:
                discovery_results.append({"ok": False, "error": str(exc), "strategy": strat})
        payload["market_discovery"] = {
            "strategies_run": strategies_to_run,
            "results": discovery_results,
            "market_open": True,
        }
    elif include_market_discovery:
        payload["market_discovery"] = {
            "ok": True,
            "created": False,
            "reason": "market_closed",
            "market_open": False,
            "strategy": discovery_strategy,
        }
    if include_theme_batch:
        theme_batch = theme_batch_run(
            finagent_root=finagent_root,
            python_bin=python_bin,
            root=root,
            catalog_path=catalog_path,
            limit=limit,
        )
        payload["theme_batch"] = theme_batch
        payload["created_count"] += len(theme_batch.get("created_items") or [])
    return payload


def list_inbox(*, root: Path = DEFAULT_FINBOT_ROOT, limit: int = 20) -> dict[str, Any]:
    dirs = ensure_inbox_dirs(root)
    items: list[dict[str, Any]] = []
    for path in sorted(dirs["pending"].glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["json_path"] = str(path)
        payload["markdown_path"] = str(path.with_suffix(".md"))
        items.append(payload)
    items.sort(key=lambda row: float(row.get("created_at") or 0), reverse=True)
    return {"ok": True, "pending_count": len(items), "items": items[: max(1, int(limit))]}


def ack_inbox_item(item_id: str, *, root: Path = DEFAULT_FINBOT_ROOT) -> dict[str, Any]:
    dirs = ensure_inbox_dirs(root)
    json_path = dirs["pending"] / f"{item_id}.json"
    md_path = dirs["pending"] / f"{item_id}.md"
    if not json_path.exists():
        raise FileNotFoundError(item_id)
    target_json = dirs["archived"] / json_path.name
    target_md = dirs["archived"] / md_path.name
    json_path.replace(target_json)
    if md_path.exists():
        md_path.replace(target_md)
    return {"ok": True, "item_id": item_id, "archived_json": str(target_json), "archived_markdown": str(target_md)}
