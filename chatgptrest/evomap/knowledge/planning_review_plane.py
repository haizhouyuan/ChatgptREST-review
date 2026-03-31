from __future__ import annotations

import csv
import json
import re
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.groundedness_checker import (
    enforce_promotion_gate,
    extract_paths,
    extract_relpaths,
    extract_units,
)
from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, Document, Edge, Episode, Evidence, PromotionStatus
from chatgptrest.evomap.knowledge.review_experiment import load_review_json

PLANNING_ROOT = Path("/vol1/1000/projects/planning")
DEFAULT_PACKAGE_DIR = Path(
    "/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755"
)
DEFAULT_LINEAGE_DIR = Path(
    "/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/final_v1"
)

AUTO_DROP_TITLE_RE = re.compile(
    r"^(answer|request|runlog_|pro回答_|pro回复|gemini回答|chatgptpro_|summary_|result_|model_spec_)",
    re.I,
)
AUTO_DROP_PATH_TOKENS = (
    "/_review_pack/",
    "/conversation_",
    "/events_",
    "/debug_",
    "/06_会话摘要/",
    "/_kb/index/extracted/",
    "/_kb/packs/",
    "/skills-src/",
)
CONTROLLED_PATH_TOKENS = (
    "/受控资料/",
    "/人员与绩效/",
    "/面试/",
    "/薪酬/",
    "/绩效/",
)
JOB_RE = re.compile(r"job_([0-9a-f]{8,64})", re.I)
VERSION_RE = re.compile(r"(?:^|[_\-\s(])([vr])(\d+(?:\.\d+)?)", re.I)


@dataclass(frozen=True)
class PlanningDocRow:
    doc_id: str
    source: str
    project: str
    raw_ref: str
    title: str
    created_at: float
    updated_at: float
    avg_quality: float
    atom_count: int


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _hash16(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _path_after_planning(raw_ref: str) -> str:
    marker = "/planning/"
    if marker in raw_ref:
        return raw_ref.split(marker, 1)[1]
    return raw_ref


def _source_bucket(raw_ref: str) -> str:
    ref = raw_ref.lower()
    if "/99_最新产物/" in ref:
        return "planning_latest_output"
    if "/outputs/" in ref:
        return "planning_outputs"
    if "/_review_pack/" in ref:
        return "planning_review_pack"
    if "/_kb/" in ref:
        return "planning_kb"
    if "/skills-src/" in ref:
        return "planning_skills"
    if "/aios/" in ref:
        return "planning_aios"
    if "/十五五规划/" in ref:
        return "planning_strategy"
    if "/预算/" in ref:
        return "planning_budget"
    if any(token in ref for token in CONTROLLED_PATH_TOKENS):
        return "planning_controlled"
    return "planning_misc"


def _review_domain(raw_ref: str) -> str:
    ref = raw_ref.lower()
    if "104关节模组" in ref:
        return "business_104"
    if "60系列" in ref or "60关节模组" in ref:
        return "business_60"
    if "减速器开发" in ref:
        return "reducer"
    if "十五五规划" in ref:
        return "strategy"
    if "/预算/" in ref:
        return "budget"
    if "两轮车车身业务" in ref:
        return "twowheel"
    if "/_kb/" in ref or "/skills-src/" in ref or "/aios/" in ref:
        return "governance"
    return "misc"


def _auto_drop_service_candidate(title: str, raw_ref: str) -> tuple[bool, str]:
    ref = raw_ref.lower()
    if AUTO_DROP_TITLE_RE.search(title.strip()):
        return True, "title_pattern"
    if any(token in ref for token in AUTO_DROP_PATH_TOKENS):
        return True, "path_pattern"
    if ref.endswith("/readme.md"):
        return True, "readme"
    return False, ""


def _maybe_controlled(raw_ref: str, title: str) -> bool:
    ref = raw_ref.lower()
    title_l = title.lower()
    return any(token in ref for token in CONTROLLED_PATH_TOKENS) or "脱敏" in title_l


def _version_score(text: str) -> tuple[int, float]:
    match = VERSION_RE.search(text)
    if not match:
        return (0, -1.0)
    prefix = 1 if match.group(1).lower() == "v" else 0
    try:
        numeric = float(match.group(2))
    except Exception:
        numeric = -1.0
    return (prefix, numeric)


def _pick_current_latest(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    ranked = sorted(
        rows,
        key=lambda row: (
            _version_score(f"{row['title']} {row['raw_ref']}"),
            float(row.get("updated_at") or 0.0),
            float(row.get("avg_quality") or 0.0),
            row["doc_id"],
        ),
        reverse=True,
    )
    return str(ranked[0]["doc_id"])


def _guess_provider(path_or_title: str) -> str:
    text = path_or_title.lower()
    if "gemini" in text:
        return "gemini"
    if "claude" in text:
        return "claude"
    if "chatgpt" in text or "pro回答" in text or "pro回复" in text:
        return "chatgpt"
    return "unknown"


def _longest_family_match(raw_ref: str, family_rows: list[dict[str, str]]) -> dict[str, str] | None:
    rel = _path_after_planning(raw_ref)
    best: dict[str, str] | None = None
    best_len = -1
    for row in family_rows:
        scope = (row.get("path_scope") or "").strip()
        if not scope:
            continue
        if rel.startswith(scope) and len(scope) > best_len:
            best = row
            best_len = len(scope)
    return best


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def load_planning_docs(db_path: str | Path) -> list[PlanningDocRow]:
    conn = _connect(db_path)
    rows = conn.execute(
        """
        SELECT
            d.doc_id,
            d.source,
            d.project,
            d.raw_ref,
            d.title,
            d.created_at,
            d.updated_at,
            COALESCE(AVG(a.quality_auto), 0.0) AS avg_quality,
            COUNT(a.atom_id) AS atom_count
        FROM documents d
        LEFT JOIN episodes e ON e.doc_id = d.doc_id
        LEFT JOIN atoms a ON a.episode_id = e.episode_id
        WHERE d.source = 'planning'
        GROUP BY d.doc_id, d.source, d.project, d.raw_ref, d.title, d.created_at, d.updated_at
        ORDER BY d.raw_ref
        """
    ).fetchall()
    conn.close()
    return [
        PlanningDocRow(
            doc_id=row["doc_id"],
            source=row["source"],
            project=row["project"],
            raw_ref=row["raw_ref"],
            title=row["title"],
            created_at=float(row["created_at"] or 0.0),
            updated_at=float(row["updated_at"] or 0.0),
            avg_quality=float(row["avg_quality"] or 0.0),
            atom_count=int(row["atom_count"] or 0),
        )
        for row in rows
    ]


def _seed_lookup(package_dir: Path, filename: str) -> set[str]:
    rows = _read_tsv(package_dir / filename)
    return {row["raw_ref"] for row in rows}


def build_snapshot(
    *,
    db_path: str | Path,
    package_dir: Path = DEFAULT_PACKAGE_DIR,
    lineage_dir: Path = DEFAULT_LINEAGE_DIR,
    output_dir: Path,
) -> dict[str, Any]:
    planning_docs = load_planning_docs(db_path)
    family_rows = _read_tsv(lineage_dir / "planning_lineage_family_registry.tsv")
    mapping_rows = _read_tsv(lineage_dir / "planning_evomap_mapping_candidates.tsv")
    mapping_by_family = {row["family_id"]: row for row in mapping_rows}
    curated_edges = _read_tsv(lineage_dir / "planning_lineage_edges.tsv")

    review_seed = _seed_lookup(package_dir, "planning_review_plane_seed.tsv")
    service_seed = _seed_lookup(package_dir, "planning_service_candidate_seed.tsv")
    archive_seed = _seed_lookup(package_dir, "planning_archive_only_seed.tsv")

    document_role_rows: list[dict[str, Any]] = []
    family_members: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    review_pack_members: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    model_run_members: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    latest_output_rows: list[dict[str, Any]] = []
    allow_candidates: list[dict[str, Any]] = []
    drop_candidates: list[dict[str, Any]] = []

    for doc in planning_docs:
        family = _longest_family_match(doc.raw_ref, family_rows)
        family_id = family["family_id"] if family else ""
        source_bucket = _source_bucket(doc.raw_ref)
        domain = _review_domain(doc.raw_ref)
        is_controlled = _maybe_controlled(doc.raw_ref, doc.title)
        auto_drop, drop_reason = _auto_drop_service_candidate(doc.title, doc.raw_ref)
        is_latest_output = source_bucket in {"planning_latest_output", "planning_outputs"}
        review_pack_id = ""
        if "/_review_pack/" in doc.raw_ref.lower():
            root = doc.raw_ref.split("/_review_pack/", 1)[0] + "/_review_pack"
            review_pack_id = f"plpack_{_hash16(root)}"
        job_match = JOB_RE.search(f"{doc.raw_ref} {doc.title}")
        model_run_id = f"plrun_{job_match.group(1)}" if job_match else ""

        if is_controlled:
            role = "controlled"
            reason = "controlled_path"
        elif auto_drop:
            role = "archive_only"
            reason = f"service_seed_auto_drop:{drop_reason}" if doc.raw_ref in service_seed else f"auto_drop:{drop_reason}"
        elif doc.raw_ref in archive_seed:
            role = "archive_only"
            reason = "archive_seed"
        elif doc.raw_ref in service_seed:
            role = "service_candidate"
            reason = "service_seed"
        elif doc.raw_ref in review_seed:
            role = "review_plane"
            reason = "review_seed"
        else:
            target_bucket = (mapping_by_family.get(family_id) or {}).get("target_bucket", "")
            if target_bucket == "archive_only":
                role = "archive_only"
                reason = "family_mapping_archive"
            else:
                role = "review_plane"
                reason = "default_review_plane"

        row = {
            "doc_id": doc.doc_id,
            "source": doc.source,
            "project": doc.project,
            "title": doc.title,
            "raw_ref": doc.raw_ref,
            "source_bucket": source_bucket,
            "review_domain": domain,
            "family_id": family_id,
            "document_role": role,
            "role_reason": reason,
            "avg_quality": f"{doc.avg_quality:.3f}",
            "atom_count": str(doc.atom_count),
            "created_at": f"{doc.created_at:.3f}",
            "updated_at": f"{doc.updated_at:.3f}",
            "is_latest_output": "1" if is_latest_output else "0",
            "review_pack_id": review_pack_id,
            "model_run_id": model_run_id,
        }
        document_role_rows.append(row)

        if family_id:
            family_members[family_id].append(row)
        if review_pack_id:
            review_pack_members[review_pack_id].append(row)
        if model_run_id:
            model_run_members[model_run_id].append(row)
        if is_latest_output:
            latest_output_rows.append(
                {
                    "doc_id": doc.doc_id,
                    "family_id": family_id,
                    "title": doc.title,
                    "raw_ref": doc.raw_ref,
                    "source_bucket": source_bucket,
                    "avg_quality": f"{doc.avg_quality:.3f}",
                    "updated_at": f"{doc.updated_at:.3f}",
                }
            )
        if role == "service_candidate":
            allow_candidates.append(row)
        elif role in {"archive_only", "controlled"}:
            drop_candidates.append(row)

    version_family_rows: list[dict[str, Any]] = []
    for family in family_rows:
        members = family_members.get(family["family_id"], [])
        latest_members = [row for row in members if row["is_latest_output"] == "1"]
        latest_doc_id = _pick_current_latest(latest_members or members)
        version_family_rows.append(
            {
                "family_id": family["family_id"],
                "domain": family.get("domain", ""),
                "path_scope": family.get("path_scope", ""),
                "family_kind": family.get("family_kind", ""),
                "initial_evomap_bucket": family.get("initial_evomap_bucket", ""),
                "target_bucket": (mapping_by_family.get(family["family_id"]) or {}).get("target_bucket", ""),
                "notes": family.get("notes", ""),
                "doc_count": str(len(members)),
                "current_latest_doc_id": latest_doc_id,
            }
        )

    review_pack_rows: list[dict[str, Any]] = []
    for review_pack_id, members in sorted(review_pack_members.items()):
        sample = members[0]
        ref = sample["raw_ref"]
        root = ref.split("/_review_pack/", 1)[0] + "/_review_pack"
        flags = {
            "contains_request": any("request" in (m["title"] + m["raw_ref"]).lower() for m in members),
            "contains_summary": any("summary" in (m["title"] + m["raw_ref"]).lower() for m in members),
            "contains_result": any("result" in (m["title"] + m["raw_ref"]).lower() for m in members),
            "contains_model_records": any(m["model_run_id"] for m in members),
        }
        review_pack_rows.append(
            {
                "review_pack_id": review_pack_id,
                "pack_root": root,
                "family_id": sample["family_id"],
                "review_domain": sample["review_domain"],
                "doc_count": str(len(members)),
                "contains_request": "1" if flags["contains_request"] else "0",
                "contains_summary": "1" if flags["contains_summary"] else "0",
                "contains_result": "1" if flags["contains_result"] else "0",
                "contains_model_records": "1" if flags["contains_model_records"] else "0",
            }
        )

    model_run_rows: list[dict[str, Any]] = []
    for model_run_id, members in sorted(model_run_members.items()):
        sample = members[0]
        ref_candidates = [m["raw_ref"] for m in members]
        title_candidates = [m["title"] for m in members]
        joined = " ".join(ref_candidates + title_candidates)
        provider = _guess_provider(joined)
        model_run_rows.append(
            {
                "model_run_id": model_run_id,
                "family_id": sample["family_id"],
                "review_domain": sample["review_domain"],
                "provider": provider,
                "job_ref": model_run_id.replace("plrun_", "job_"),
                "doc_count": str(len(members)),
                "sample_ref": ref_candidates[0],
            }
        )

    # Stronger ordering for reviewer workload: stable latest outputs first.
    def _candidate_rank(row: dict[str, str]) -> tuple[Any, ...]:
        return (
            row["review_domain"] not in {"business_104", "strategy", "budget", "reducer", "business_60", "governance"},
            row["source_bucket"] != "planning_latest_output",
            row["source_bucket"] != "planning_outputs",
            -float(row["avg_quality"]),
            row["raw_ref"],
        )

    allow_candidates.sort(key=_candidate_rank)

    quotas = {
        "business_104": 40,
        "strategy": 22,
        "budget": 10,
        "reducer": 16,
        "business_60": 12,
        "twowheel": 8,
        "governance": 12,
        "misc": 10,
    }
    picked_review_rows: list[dict[str, str]] = []
    quota_counts: Counter[str] = Counter()
    for row in allow_candidates:
        domain = row["review_domain"]
        if quota_counts[domain] < quotas.get(domain, 0):
            picked_review_rows.append(row)
            quota_counts[domain] += 1
    remaining = [row for row in allow_candidates if row not in picked_review_rows]
    for row in remaining:
        if len(picked_review_rows) >= 120:
            break
        picked_review_rows.append(row)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_tsv(
        out / "document_role.tsv",
        document_role_rows,
        [
            "doc_id",
            "source",
            "project",
            "title",
            "raw_ref",
            "source_bucket",
            "review_domain",
            "family_id",
            "document_role",
            "role_reason",
            "avg_quality",
            "atom_count",
            "created_at",
            "updated_at",
            "is_latest_output",
            "review_pack_id",
            "model_run_id",
        ],
    )
    _write_tsv(
        out / "version_family.tsv",
        version_family_rows,
        [
            "family_id",
            "domain",
            "path_scope",
            "family_kind",
            "initial_evomap_bucket",
            "target_bucket",
            "notes",
            "doc_count",
            "current_latest_doc_id",
        ],
    )
    _write_tsv(
        out / "lineage_edge.tsv",
        curated_edges,
        ["relation_type", "src_family_id", "dst_family_id", "evidence"],
    )
    _write_tsv(
        out / "review_pack.tsv",
        review_pack_rows,
        [
            "review_pack_id",
            "pack_root",
            "family_id",
            "review_domain",
            "doc_count",
            "contains_request",
            "contains_summary",
            "contains_result",
            "contains_model_records",
        ],
    )
    _write_tsv(
        out / "model_run.tsv",
        model_run_rows,
        [
            "model_run_id",
            "family_id",
            "review_domain",
            "provider",
            "job_ref",
            "doc_count",
            "sample_ref",
        ],
    )
    _write_tsv(
        out / "latest_output.tsv",
        latest_output_rows,
        ["doc_id", "family_id", "title", "raw_ref", "source_bucket", "avg_quality", "updated_at"],
    )
    _write_tsv(
        out / "bootstrap_active_allow_candidates.tsv",
        allow_candidates,
        [
            "doc_id",
            "source",
            "project",
            "title",
            "raw_ref",
            "source_bucket",
            "review_domain",
            "family_id",
            "document_role",
            "role_reason",
            "avg_quality",
            "atom_count",
            "created_at",
            "updated_at",
            "is_latest_output",
            "review_pack_id",
            "model_run_id",
        ],
    )
    _write_tsv(
        out / "bootstrap_active_drop_candidates.tsv",
        drop_candidates,
        [
            "doc_id",
            "source",
            "project",
            "title",
            "raw_ref",
            "source_bucket",
            "review_domain",
            "family_id",
            "document_role",
            "role_reason",
            "avg_quality",
            "atom_count",
            "created_at",
            "updated_at",
            "is_latest_output",
            "review_pack_id",
            "model_run_id",
        ],
    )

    summary = {
        "db_path": str(db_path),
        "package_dir": str(package_dir),
        "lineage_dir": str(lineage_dir),
        "output_dir": str(out),
        "planning_docs": len(planning_docs),
        "document_roles": Counter(row["document_role"] for row in document_role_rows),
        "review_domains": Counter(row["review_domain"] for row in allow_candidates),
        "families": len(version_family_rows),
        "review_packs": len(review_pack_rows),
        "model_runs": len(model_run_rows),
        "latest_outputs": len(latest_output_rows),
        "allow_candidates": len(allow_candidates),
        "drop_candidates": len(drop_candidates),
        "review_pack_selection": len(picked_review_rows),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Return selection for downstream pack building.
    return {
        "summary": summary,
        "picked_review_rows": picked_review_rows,
    }


def _fetch_top_atom_context(conn: sqlite3.Connection, doc_id: str, limit: int = 2) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT a.atom_id, a.atom_type, a.canonical_question, a.answer, a.quality_auto
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        WHERE e.doc_id = ?
        ORDER BY COALESCE(a.quality_auto, 0) DESC, a.atom_id
        LIMIT ?
        """,
        (doc_id, limit),
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        text = re.sub(r"\s+", " ", row["answer"] or "").strip()
        items.append(
            {
                "atom_id": row["atom_id"],
                "atom_type": row["atom_type"],
                "canonical_question": row["canonical_question"] or "",
                "answer_excerpt": text[:320],
                "quality_auto": float(row["quality_auto"] or 0.0),
            }
        )
    return items


def build_service_review_pack(
    *,
    db_path: str | Path,
    snapshot_dir: Path,
    pack_id: str = "planning_service_review_pack_v1",
) -> dict[str, Any]:
    conn = _connect(db_path)
    rows = _read_tsv(snapshot_dir / "bootstrap_active_allow_candidates.tsv")
    selected_ids = {row["doc_id"] for row in rows}
    selection_rows = {row["doc_id"]: row for row in rows}
    # Use the first 120 highest-value candidates from the snapshot summary selection order.
    preview_rows = _read_tsv(snapshot_dir / "document_role.tsv")
    picked = [
        row for row in preview_rows
        if row["doc_id"] in selected_ids and row["document_role"] == "service_candidate"
    ]
    picked.sort(
        key=lambda row: (
            row["review_domain"] not in {"business_104", "strategy", "budget", "reducer", "business_60", "governance"},
            row["source_bucket"] != "planning_latest_output",
            row["source_bucket"] != "planning_outputs",
            -float(row["avg_quality"]),
            row["raw_ref"],
        )
    )
    picked = picked[:120]

    items: list[dict[str, Any]] = []
    for row in picked:
        item = dict(selection_rows.get(row["doc_id"], row))
        item["top_atoms"] = _fetch_top_atom_context(conn, row["doc_id"], limit=2)
        items.append(item)
    conn.close()

    pack = {
        "pack_id": pack_id,
        "pack_type": "planning_service_candidate_review",
        "instructions": {
            "decision_values": [
                "service_candidate",
                "lesson",
                "procedure",
                "correction",
                "review_only",
                "archive_only",
                "controlled",
                "reject_noise",
            ],
            "fields": ["doc_id", "decision", "service_readiness", "note"],
            "rules": [
                "Prefer service_candidate only for stable, reusable, context-independent deliverables.",
                "Use review_only for historically useful but not directly service-ready material.",
                "Use reject_noise for wrappers, runlogs, job artifacts, and thin chat replies.",
                "Do not invent facts outside the provided metadata and top atom excerpts.",
            ],
        },
        "items": items,
    }
    (snapshot_dir / f"{pack_id}.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prompt = (
        "Review this planning service-candidate pack. Return JSON only with shape:\n"
        "{\n"
        '  "pack_id": "' + pack_id + '",\n'
        '  "items": [{"doc_id":"...","decision":"service_candidate|lesson|procedure|correction|review_only|archive_only|controlled|reject_noise","service_readiness":"high|medium|low","note":"..."}]\n'
        "}\n"
        "Do not add prose. If unsure, choose review_only.\n\n"
        + json.dumps(pack, ensure_ascii=False, indent=2)
    )
    (snapshot_dir / f"{pack_id}_prompt.txt").write_text(prompt, encoding="utf-8")
    return pack


def normalize_decision(value: str) -> str:
    text = (value or "").strip().lower()
    aliases = {
        "keep": "service_candidate",
        "accept": "service_candidate",
        "procedure_candidate": "procedure",
        "lesson_candidate": "lesson",
        "correction_candidate": "correction",
        "archive": "archive_only",
        "noise": "reject_noise",
        "reject": "reject_noise",
    }
    return aliases.get(text, text or "review_only")


def _normalize_service_readiness(value: Any) -> str:
    if isinstance(value, (int, float)):
        score = float(value)
        if score >= 0.75:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"
    text = str(value or "").strip().lower()
    if text in {"high", "medium", "low"}:
        return text
    try:
        return _normalize_service_readiness(float(text))
    except Exception:
        return "medium"


def _extract_review_payload(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(payload, list):
        return {"items": payload}
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload

    for key in ("response", "text", "output", "message", "result"):
        raw = payload.get(key) if isinstance(payload, dict) else None
        if not raw or not isinstance(raw, str):
            continue
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text)
        try:
            nested = json.loads(text)
            if isinstance(nested, dict) and isinstance(nested.get("items"), list):
                return nested
            if isinstance(nested, list):
                return {"items": nested}
        except Exception:
            pass
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(text):
            if ch not in "{[":
                continue
            try:
                nested, _ = decoder.raw_decode(text[idx:])
            except Exception:
                continue
            if isinstance(nested, dict) and isinstance(nested.get("items"), list):
                return nested
            if isinstance(nested, list):
                return {"items": nested}
    return payload


def merge_review_outputs(
    *,
    snapshot_dir: Path,
    review_json_paths: list[Path],
    output_path: Path,
) -> dict[str, Any]:
    by_doc: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in review_json_paths:
        payload = _extract_review_payload(load_review_json(path))
        for item in payload.get("items", []):
            doc_id = str(item.get("doc_id") or "").strip()
            if not doc_id:
                continue
            by_doc[doc_id].append(
                {
                    "reviewer": path.stem,
                    "decision": normalize_decision(str(item.get("decision") or "")),
                    "service_readiness": _normalize_service_readiness(item.get("service_readiness")),
                    "note": str(item.get("note") or "").strip(),
                }
            )

    roles = {row["doc_id"]: row for row in _read_tsv(snapshot_dir / "document_role.tsv")}
    merged_rows: list[dict[str, Any]] = []
    for doc_id, reviews in sorted(by_doc.items()):
        decisions = Counter(review["decision"] for review in reviews)
        winner = decisions.most_common(1)[0][0]
        if len(decisions) > 1 and decisions.most_common(1)[0][1] == 1:
            keepish = {"service_candidate", "lesson", "procedure", "correction"}
            if any(dec in keepish for dec in decisions) and any(dec in {"archive_only", "reject_noise"} for dec in decisions):
                winner = "review_only"
        readiness = Counter(review["service_readiness"] for review in reviews).most_common(1)[0][0]
        merged_rows.append(
            {
                "doc_id": doc_id,
                "title": roles.get(doc_id, {}).get("title", ""),
                "raw_ref": roles.get(doc_id, {}).get("raw_ref", ""),
                "family_id": roles.get(doc_id, {}).get("family_id", ""),
                "review_domain": roles.get(doc_id, {}).get("review_domain", ""),
                "source_bucket": roles.get(doc_id, {}).get("source_bucket", ""),
                "avg_quality": roles.get(doc_id, {}).get("avg_quality", "0.000"),
                "final_bucket": winner,
                "service_readiness": readiness,
                "reviewers": json.dumps(reviews, ensure_ascii=False),
            }
        )

    _write_tsv(
        output_path,
        merged_rows,
        [
            "doc_id",
            "title",
            "raw_ref",
            "family_id",
            "review_domain",
            "source_bucket",
            "avg_quality",
            "final_bucket",
            "service_readiness",
            "reviewers",
        ],
    )
    allow_rows = [row for row in merged_rows if row["final_bucket"] in {"service_candidate", "lesson", "procedure", "correction"}]
    _write_tsv(
        output_path.with_name("bootstrap_active_allowlist.tsv"),
        allow_rows,
        [
            "doc_id",
            "title",
            "raw_ref",
            "family_id",
            "review_domain",
            "source_bucket",
            "avg_quality",
            "final_bucket",
            "service_readiness",
            "reviewers",
        ],
    )
    summary = {
        "review_outputs": [str(path) for path in review_json_paths],
        "reviewed_docs": len(merged_rows),
        "allowlist_docs": len(allow_rows),
        "by_bucket": Counter(row["final_bucket"] for row in merged_rows),
    }
    output_path.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _load_meta(meta_json: str) -> dict[str, Any]:
    try:
        value = json.loads(meta_json or "{}")
        if isinstance(value, dict):
            return value
    except Exception:
        pass
    return {}


def _has_runtime_grounding_anchors(answer: str) -> bool:
    text = answer or ""
    return bool(extract_paths(text) or extract_relpaths(text) or extract_units(text))


def import_review_plane(
    *,
    db_path: str | Path,
    snapshot_dir: Path,
    review_decisions_path: Path | None = None,
) -> dict[str, Any]:
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    conn = db.connect()
    document_rows = _read_tsv(snapshot_dir / "document_role.tsv")
    family_rows = _read_tsv(snapshot_dir / "version_family.tsv")
    edge_rows = _read_tsv(snapshot_dir / "lineage_edge.tsv")
    review_pack_rows = _read_tsv(snapshot_dir / "review_pack.tsv")
    model_run_rows = _read_tsv(snapshot_dir / "model_run.tsv")
    latest_rows = _read_tsv(snapshot_dir / "latest_output.tsv")
    decision_rows = _read_tsv(review_decisions_path) if review_decisions_path and review_decisions_path.exists() else []
    decisions_by_doc = {row["doc_id"]: row for row in decision_rows}

    updated_docs = 0
    for row in document_rows:
        current = conn.execute("SELECT meta_json FROM documents WHERE doc_id = ?", (row["doc_id"],)).fetchone()
        if not current:
            continue
        meta = _load_meta(current["meta_json"])
        meta["planning_review"] = {
            "document_role": row["document_role"],
            "source_bucket": row["source_bucket"],
            "review_domain": row["review_domain"],
            "family_id": row["family_id"],
            "is_latest_output": row["is_latest_output"] == "1",
            "review_pack_id": row["review_pack_id"],
            "model_run_id": row["model_run_id"],
            "role_reason": row["role_reason"],
            "imported_at": time.time(),
        }
        decision = decisions_by_doc.get(row["doc_id"])
        if decision:
            meta["planning_review"]["decision"] = {
                "final_bucket": decision["final_bucket"],
                "service_readiness": decision["service_readiness"],
                "reviewers": json.loads(decision["reviewers"] or "[]"),
            }
        conn.execute(
            "UPDATE documents SET meta_json = ?, updated_at = ? WHERE doc_id = ?",
            (json.dumps(meta, ensure_ascii=False), time.time(), row["doc_id"]),
        )
        updated_docs += 1

    imported_family_docs = 0
    imported_review_pack_docs = 0
    imported_model_run_docs = 0
    imported_decision_docs = 0

    for row in family_rows:
        doc_id = f"doc_planning_family_{row['family_id']}"
        ep_id = f"ep_planning_family_{row['family_id']}"
        atom_id = f"at_planning_family_{row['family_id']}"
        db.put_document(
            Document(
                doc_id=doc_id,
                source="planning_review_plane",
                project="planning",
                raw_ref=f"planning://family/{row['family_id']}",
                title=f"Planning family {row['family_id']}",
                created_at=time.time(),
                updated_at=time.time(),
                meta_json=json.dumps(row, ensure_ascii=False),
            )
        )
        db.put_episode(
            Episode(
                episode_id=ep_id,
                doc_id=doc_id,
                episode_type="planning_review_plane",
                title=f"Family profile {row['family_id']}",
                summary=row.get("notes", ""),
                start_ref=row["path_scope"],
                end_ref=row["path_scope"],
                time_start=time.time(),
                time_end=time.time(),
                source_ext=json.dumps({"kind": "version_family"}, ensure_ascii=False),
            )
        )
        db.put_atom(
            Atom(
                atom_id=atom_id,
                episode_id=ep_id,
                atom_type="decision",
                question=f"What does planning family {row['family_id']} cover?",
                answer=(
                    f"Family {row['family_id']} ({row['domain']}) covers scope {row['path_scope']} "
                    f"with {row['doc_count']} docs. Current latest doc: {row['current_latest_doc_id']}."
                ),
                canonical_question=f"planning family {row['family_id']}",
                applicability=json.dumps({"source": "planning_review_plane", "kind": "version_family"}),
                status=AtomStatus.PUBLISHED.value,
                stability="versioned",
                quality_auto=0.85,
                value_auto=0.72,
                promotion_status=PromotionStatus.ARCHIVED.value,
                promotion_reason="planning_review_plane",
                valid_from=time.time(),
            )
        )
        imported_family_docs += 1

    for row in review_pack_rows:
        doc_id = f"doc_{row['review_pack_id']}"
        ep_id = f"ep_{row['review_pack_id']}"
        atom_id = f"at_{row['review_pack_id']}"
        db.put_document(
            Document(
                doc_id=doc_id,
                source="planning_review_plane",
                project="planning",
                raw_ref=f"planning://review_pack/{row['review_pack_id']}",
                title=f"Planning review pack {row['review_pack_id']}",
                created_at=time.time(),
                updated_at=time.time(),
                meta_json=json.dumps(row, ensure_ascii=False),
            )
        )
        db.put_episode(
            Episode(
                episode_id=ep_id,
                doc_id=doc_id,
                episode_type="planning_review_plane",
                title=f"Review pack {row['review_pack_id']}",
                summary=row["pack_root"],
                start_ref=row["pack_root"],
                end_ref=row["pack_root"],
                time_start=time.time(),
                time_end=time.time(),
                source_ext=json.dumps({"kind": "review_pack"}, ensure_ascii=False),
            )
        )
        db.put_atom(
            Atom(
                atom_id=atom_id,
                episode_id=ep_id,
                atom_type="procedure",
                question=f"What is review pack {row['review_pack_id']}?",
                answer=(
                    f"Review pack root {row['pack_root']} for family {row['family_id']} "
                    f"contains {row['doc_count']} docs."
                ),
                canonical_question=f"planning review pack {row['review_pack_id']}",
                applicability=json.dumps({"source": "planning_review_plane", "kind": "review_pack"}),
                status=AtomStatus.PUBLISHED.value,
                stability="versioned",
                quality_auto=0.78,
                value_auto=0.62,
                promotion_status=PromotionStatus.ARCHIVED.value,
                promotion_reason="planning_review_plane",
                valid_from=time.time(),
            )
        )
        imported_review_pack_docs += 1

    for row in model_run_rows:
        doc_id = f"doc_{row['model_run_id']}"
        ep_id = f"ep_{row['model_run_id']}"
        atom_id = f"at_{row['model_run_id']}"
        db.put_document(
            Document(
                doc_id=doc_id,
                source="planning_review_plane",
                project="planning",
                raw_ref=f"planning://model_run/{row['model_run_id']}",
                title=f"Planning model run {row['model_run_id']}",
                created_at=time.time(),
                updated_at=time.time(),
                meta_json=json.dumps(row, ensure_ascii=False),
            )
        )
        db.put_episode(
            Episode(
                episode_id=ep_id,
                doc_id=doc_id,
                episode_type="planning_review_plane",
                title=f"Model run {row['model_run_id']}",
                summary=row["sample_ref"],
                start_ref=row["job_ref"],
                end_ref=row["sample_ref"],
                time_start=time.time(),
                time_end=time.time(),
                source_ext=json.dumps({"kind": "model_run"}, ensure_ascii=False),
            )
        )
        db.put_atom(
            Atom(
                atom_id=atom_id,
                episode_id=ep_id,
                atom_type="decision",
                question=f"What is model run {row['model_run_id']}?",
                answer=(
                    f"Model run {row['model_run_id']} uses provider {row['provider']} and "
                    f"is associated with family {row['family_id']}."
                ),
                canonical_question=f"planning model run {row['model_run_id']}",
                applicability=json.dumps({"source": "planning_review_plane", "kind": "model_run"}),
                status=AtomStatus.PUBLISHED.value,
                stability="versioned",
                quality_auto=0.74,
                value_auto=0.55,
                promotion_status=PromotionStatus.ARCHIVED.value,
                promotion_reason="planning_review_plane",
                valid_from=time.time(),
            )
        )
        imported_model_run_docs += 1

    for row in latest_rows:
        if not row["family_id"]:
            continue
        family_doc_id = f"doc_planning_family_{row['family_id']}"
        db.put_edge(
            Edge(
                from_id=row["doc_id"],
                to_id=family_doc_id,
                edge_type="IS_LATEST_OF",
                from_kind="document",
                to_kind="document",
                meta_json=json.dumps({"source_bucket": row["source_bucket"]}, ensure_ascii=False),
            )
        )

    for row in edge_rows:
        db.put_edge(
            Edge(
                from_id=f"doc_planning_family_{row['src_family_id']}",
                to_id=f"doc_planning_family_{row['dst_family_id']}",
                edge_type=row["relation_type"],
                from_kind="document",
                to_kind="document",
                meta_json=json.dumps({"evidence": row.get("evidence", "")}, ensure_ascii=False),
            )
        )

    for row in document_rows:
        if row["family_id"]:
            db.put_edge(
                Edge(
                    from_id=row["doc_id"],
                    to_id=f"doc_planning_family_{row['family_id']}",
                    edge_type="BELONGS_TO_FAMILY",
                    from_kind="document",
                    to_kind="document",
                    meta_json=json.dumps({"source_bucket": row["source_bucket"]}, ensure_ascii=False),
                )
            )
        if row["review_pack_id"]:
            db.put_edge(
                Edge(
                    from_id=row["doc_id"],
                    to_id=f"doc_{row['review_pack_id']}",
                    edge_type="REVIEWED_IN",
                    from_kind="document",
                    to_kind="document",
                    meta_json=json.dumps({}, ensure_ascii=False),
                )
            )
        if row["model_run_id"]:
            db.put_edge(
                Edge(
                    from_id=row["doc_id"],
                    to_id=f"doc_{row['model_run_id']}",
                    edge_type="GENERATED_BY_MODEL_RUN",
                    from_kind="document",
                    to_kind="document",
                    meta_json=json.dumps({}, ensure_ascii=False),
                )
            )

    for row in decision_rows:
        doc_id = f"doc_planning_review_decision_{row['doc_id']}"
        ep_id = f"ep_planning_review_decision_{row['doc_id']}"
        atom_id = f"at_planning_review_decision_{row['doc_id']}"
        db.put_document(
            Document(
                doc_id=doc_id,
                source="planning_review_plane",
                project="planning",
                raw_ref=f"planning://review_decision/{row['doc_id']}",
                title=f"Planning review decision {row['doc_id']}",
                created_at=time.time(),
                updated_at=time.time(),
                meta_json=json.dumps(row, ensure_ascii=False),
            )
        )
        db.put_episode(
            Episode(
                episode_id=ep_id,
                doc_id=doc_id,
                episode_type="planning_review_plane",
                title=f"Review decision {row['doc_id']}",
                summary=row["final_bucket"],
                start_ref=row["raw_ref"],
                end_ref=row["raw_ref"],
                time_start=time.time(),
                time_end=time.time(),
                source_ext=json.dumps({"kind": "review_decision"}, ensure_ascii=False),
            )
        )
        db.put_atom(
            Atom(
                atom_id=atom_id,
                episode_id=ep_id,
                atom_type="decision",
                question=f"What is the review decision for planning doc {row['doc_id']}?",
                answer=(
                    f"Planning doc {row['doc_id']} is classified as {row['final_bucket']} "
                    f"with service_readiness={row['service_readiness']}."
                ),
                canonical_question=f"planning review decision {row['doc_id']}",
                applicability=json.dumps({"source": "planning_review_plane", "kind": "review_decision"}),
                status=AtomStatus.PUBLISHED.value,
                stability="versioned",
                quality_auto=0.83,
                value_auto=0.67,
                promotion_status=PromotionStatus.ARCHIVED.value,
                promotion_reason="planning_review_plane",
                valid_from=time.time(),
            )
        )
        db.put_edge(
            Edge(
                from_id=row["doc_id"],
                to_id=doc_id,
                edge_type="REVIEW_DECIDED",
                from_kind="document",
                to_kind="document",
                meta_json=json.dumps({"final_bucket": row["final_bucket"]}, ensure_ascii=False),
            )
        )
        imported_decision_docs += 1

    conn.commit()
    summary = {
        "updated_docs": updated_docs,
        "imported_family_docs": imported_family_docs,
        "imported_review_pack_docs": imported_review_pack_docs,
        "imported_model_run_docs": imported_model_run_docs,
        "imported_decision_docs": imported_decision_docs,
    }
    (snapshot_dir / "import_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def apply_bootstrap_allowlist(
    *,
    db_path: str | Path,
    allowlist_path: Path,
    output_dir: Path,
    min_atom_quality: float = 0.58,
    per_doc_limit: int = 2,
    groundedness_threshold: float = 0.6,
) -> dict[str, Any]:
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    conn = db.connect()
    allow_rows = _read_tsv(allowlist_path)
    promoted_rows: list[dict[str, Any]] = []
    deferred_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    reconciled_out_rows: list[dict[str, Any]] = []

    allow_doc_ids = {row["doc_id"] for row in allow_rows}
    stale_rows = conn.execute(
        """
        SELECT e.doc_id, a.atom_id, a.atom_type, a.quality_auto, a.promotion_status
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE d.source = 'planning'
          AND a.promotion_status IN (?, ?)
          AND a.promotion_reason LIKE 'planning_bootstrap%'
        """,
        (PromotionStatus.ACTIVE.value, PromotionStatus.CANDIDATE.value),
    ).fetchall()
    for atom in stale_rows:
        if atom["doc_id"] in allow_doc_ids:
            continue
        conn.execute(
            "UPDATE atoms SET promotion_status = ?, promotion_reason = ? WHERE atom_id = ?",
            (
                PromotionStatus.STAGED.value,
                "planning_bootstrap_reconciled_out",
                atom["atom_id"],
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO promotion_audit
            (audit_id, atom_id, from_status, to_status, reason, actor, groundedness_result, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"pa_{_hash16(atom['atom_id'] + ':reconciled_out')}",
                atom["atom_id"],
                atom["promotion_status"],
                PromotionStatus.STAGED.value,
                "planning_bootstrap_reconciled_out",
                "planning_review_plane",
                json.dumps({"mode": "reconcile_out"}, ensure_ascii=False),
                time.time(),
            ),
        )
        reconciled_out_rows.append(
            {
                "doc_id": atom["doc_id"],
                "atom_id": atom["atom_id"],
                "atom_type": atom["atom_type"],
                "quality_auto": f"{float(atom['quality_auto'] or 0.0):.3f}",
                "from_status": atom["promotion_status"] or "",
                "to_status": PromotionStatus.STAGED.value,
                "reason": "removed_from_allowlist",
            }
        )

    for row in allow_rows:
        doc_id = row["doc_id"]
        bucket = row["final_bucket"]
        atoms = conn.execute(
            """
            SELECT a.atom_id, a.atom_type, a.canonical_question, a.answer, a.quality_auto, a.promotion_status
            FROM atoms a
            JOIN episodes e ON e.episode_id = a.episode_id
            WHERE e.doc_id = ?
              AND COALESCE(a.quality_auto, 0) >= ?
              AND COALESCE(a.canonical_question, '') != ''
            ORDER BY COALESCE(a.quality_auto, 0) DESC, a.atom_id
            LIMIT ?
            """,
            (doc_id, min_atom_quality, per_doc_limit),
        ).fetchall()
        for atom in atoms:
            old_status = atom["promotion_status"] or PromotionStatus.STAGED.value
            if old_status != PromotionStatus.CANDIDATE.value:
                conn.execute(
                    "UPDATE atoms SET promotion_status = ?, promotion_reason = ? WHERE atom_id = ?",
                    (
                        PromotionStatus.CANDIDATE.value,
                        f"planning_bootstrap:{bucket}",
                        atom["atom_id"],
                    ),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO promotion_audit
                    (audit_id, atom_id, from_status, to_status, reason, actor, groundedness_result, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"pa_{_hash16(atom['atom_id'] + ':candidate')}",
                        atom["atom_id"],
                        old_status,
                        PromotionStatus.CANDIDATE.value,
                        f"planning_bootstrap:{bucket}",
                        "planning_review_plane",
                        "",
                        time.time(),
                    ),
                )
            candidate_row = {
                "doc_id": doc_id,
                "atom_id": atom["atom_id"],
                "atom_type": atom["atom_type"],
                "quality_auto": f"{float(atom['quality_auto'] or 0.0):.3f}",
                "target_bucket": bucket,
                "result": "candidate",
            }
            candidate_rows.append(candidate_row)
            if bucket != "service_candidate":
                deferred_rows.append({**candidate_row, "reason": "non_service_bucket"})
                continue
            if not _has_runtime_grounding_anchors(atom["answer"] or ""):
                conn.execute(
                    "UPDATE atoms SET promotion_status = ?, promotion_reason = ?, groundedness = ? WHERE atom_id = ?",
                    (
                        PromotionStatus.CANDIDATE.value,
                        f"planning_bootstrap:{bucket}",
                        0.0,
                        atom["atom_id"],
                    ),
                )
                deferred_rows.append(
                    {
                        **candidate_row,
                        "reason": "groundedness_unknown_no_runtime_anchors",
                        "groundedness": "unknown",
                    }
                )
                continue
            passed, audit = enforce_promotion_gate(db, atom["atom_id"], threshold=groundedness_threshold, commit=False)
            if passed:
                conn.execute(
                    "UPDATE atoms SET promotion_status = ?, promotion_reason = ?, groundedness = ? WHERE atom_id = ?",
                    (
                        PromotionStatus.ACTIVE.value,
                        "planning_bootstrap_active",
                        audit.overall_score,
                        atom["atom_id"],
                    ),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO promotion_audit
                    (audit_id, atom_id, from_status, to_status, reason, actor, groundedness_result, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"pa_{_hash16(atom['atom_id'] + ':active')}",
                        atom["atom_id"],
                        PromotionStatus.CANDIDATE.value,
                        PromotionStatus.ACTIVE.value,
                        "planning_bootstrap_active",
                        "planning_review_plane",
                        json.dumps({"overall_score": audit.overall_score}, ensure_ascii=False),
                        time.time(),
                    ),
                )
                promoted_rows.append(
                    {
                        "doc_id": doc_id,
                        "atom_id": atom["atom_id"],
                        "atom_type": atom["atom_type"],
                        "quality_auto": f"{float(atom['quality_auto'] or 0.0):.3f}",
                        "groundedness": f"{audit.overall_score:.3f}",
                        "target_bucket": bucket,
                        "promotion_status": PromotionStatus.ACTIVE.value,
                    }
                )
            else:
                deferred_rows.append(
                    {
                        **candidate_row,
                        "reason": f"groundedness<{groundedness_threshold:.2f}",
                        "groundedness": f"{audit.overall_score:.3f}",
                    }
                )

    conn.commit()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_tsv(
        output_dir / "bootstrap_active_atom_candidates.tsv",
        candidate_rows,
        ["doc_id", "atom_id", "atom_type", "quality_auto", "target_bucket", "result"],
    )
    _write_tsv(
        output_dir / "bootstrap_active_promoted.tsv",
        promoted_rows,
        ["doc_id", "atom_id", "atom_type", "quality_auto", "groundedness", "target_bucket", "promotion_status"],
    )
    _write_tsv(
        output_dir / "bootstrap_active_deferred.tsv",
        deferred_rows,
        ["doc_id", "atom_id", "atom_type", "quality_auto", "target_bucket", "result", "reason", "groundedness"],
    )
    _write_tsv(
        output_dir / "bootstrap_active_reconciled_out.tsv",
        reconciled_out_rows,
        ["doc_id", "atom_id", "atom_type", "quality_auto", "from_status", "to_status", "reason"],
    )
    summary = {
        "allowlist_docs": len(allow_rows),
        "reconciled_out_atoms": len(reconciled_out_rows),
        "candidate_atoms": len(candidate_rows),
        "promoted_atoms": len(promoted_rows),
        "deferred_atoms": len(deferred_rows),
        "min_atom_quality": min_atom_quality,
        "groundedness_threshold": groundedness_threshold,
    }
    (output_dir / "bootstrap_active_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def default_db_path() -> str:
    return resolve_evomap_knowledge_runtime_db_path()
