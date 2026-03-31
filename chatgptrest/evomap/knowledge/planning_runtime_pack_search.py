from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_read_db_path
from chatgptrest.evomap.knowledge.retrieval import RetrievalConfig

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RELEASE_BUNDLE_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_runtime_pack_release_bundle"
PLANNING_REVIEW_SCOPE = "planning_review"
PLANNING_REVIEW_SOURCE = "planning_review_pack"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _resolve_path(raw: str | Path, *, base: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _latest_ready_bundle(root: Path) -> Path | None:
    if not root.exists():
        return None
    for candidate in sorted((path for path in root.iterdir() if path.is_dir()), reverse=True):
        manifest_path = candidate / "release_bundle_manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = _read_json(manifest_path)
        except Exception:
            continue
        if bool(manifest.get("ready_for_explicit_consumption", False)):
            return candidate
    return None


def resolve_ready_planning_runtime_pack_bundle(bundle_dir: str | Path = "") -> Path | None:
    if bundle_dir:
        candidate = Path(bundle_dir)
        manifest_path = candidate / "release_bundle_manifest.json"
        if manifest_path.exists() and bool(_read_json(manifest_path).get("ready_for_explicit_consumption", False)):
            return candidate
        return None

    env_bundle_dir = os.environ.get("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR", "").strip()
    if env_bundle_dir:
        return resolve_ready_planning_runtime_pack_bundle(env_bundle_dir)

    env_bundle_root = os.environ.get("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_ROOT", "").strip()
    root = Path(env_bundle_root) if env_bundle_root else DEFAULT_RELEASE_BUNDLE_ROOT
    return _latest_ready_bundle(root)


def _tokenize(text: str) -> list[str]:
    parts = re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", text.lower())
    return [part for part in parts if part]


def _score(query_tokens: list[str], *parts: str) -> int:
    haystack = " ".join(parts).lower()
    return sum(1 for token in query_tokens if token and token in haystack)


def _fetch_pack_rows(pack_dir: Path) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], set[str]]:
    docs = {row["doc_id"]: row for row in _read_tsv(pack_dir / "docs.tsv")}
    atoms = _read_tsv(pack_dir / "atoms.tsv")
    retrieval_pack = _read_json(pack_dir / "retrieval_pack.json")
    allowed_atom_ids = set(str(item) for item in retrieval_pack.get("atom_ids", []))
    return docs, atoms, allowed_atom_ids


def _fetch_db_rows(db_path: str | Path, atom_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not atom_ids:
        return {}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in atom_ids)
    rows = conn.execute(
        f"""
        SELECT
            a.atom_id,
            a.question,
            a.answer,
            a.atom_type,
            a.quality_auto,
            a.groundedness,
            a.status,
            a.stability,
            a.promotion_status,
            e.doc_id,
            d.title,
            d.raw_ref,
            COALESCE(json_extract(d.meta_json, '$.planning_review.review_domain'), '') AS review_domain,
            COALESCE(json_extract(d.meta_json, '$.planning_review.source_bucket'), '') AS source_bucket
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE a.atom_id IN ({placeholders})
        """,
        atom_ids,
    ).fetchall()
    conn.close()
    return {str(row["atom_id"]): dict(row) for row in rows}


def _passes_runtime_gate(row: dict[str, Any], cfg: RetrievalConfig) -> bool:
    if str(row.get("promotion_status") or "") not in cfg.allowed_promotion_status:
        return False
    if str(row.get("stability") or "") in cfg.exclude_stability:
        return False
    if float(row.get("quality_auto") or 0.0) < cfg.min_quality:
        return False
    groundedness = row.get("groundedness")
    if groundedness is not None and float(groundedness or 0.0) < 0.5:
        return False
    return True


def search_planning_runtime_pack(
    query: str,
    *,
    top_k: int = 5,
    bundle_dir: str | Path = "",
    db_path: str | Path = "",
) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    bundle = resolve_ready_planning_runtime_pack_bundle(bundle_dir)
    if bundle is None:
        return []

    manifest = _read_json(bundle / "release_bundle_manifest.json")
    if not bool(manifest.get("ready_for_explicit_consumption", False)):
        return []

    pack_dir = _resolve_path(str(manifest.get("pack_dir") or ""), base=REPO_ROOT)
    if not pack_dir.exists():
        return []

    docs, atoms, allowed_atom_ids = _fetch_pack_rows(pack_dir)
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    ranked_atoms: list[dict[str, Any]] = []
    for atom in atoms:
        atom_id = str(atom.get("atom_id") or "")
        doc_id = str(atom.get("doc_id") or "")
        if atom_id not in allowed_atom_ids or doc_id not in docs:
            continue
        doc = docs[doc_id]
        score = _score(
            query_tokens,
            str(atom.get("question") or ""),
            str(atom.get("canonical_question") or ""),
            str(doc.get("title") or ""),
            str(doc.get("review_domain") or ""),
            str(doc.get("source_bucket") or ""),
        )
        if score <= 0:
            continue
        ranked_atoms.append(
            {
                "score": score,
                "atom_id": atom_id,
                "doc_id": doc_id,
                "doc": doc,
            }
        )

    if not ranked_atoms:
        return []

    ranked_atoms.sort(
        key=lambda item: (
            -int(item["score"]),
            str(item["doc"].get("review_domain") or ""),
            str(item["doc"].get("doc_id") or ""),
            str(item["atom_id"]),
        )
    )
    candidate_rows = ranked_atoms[: max(top_k * 4, top_k)]
    evomap_db = db_path or resolve_evomap_knowledge_read_db_path()
    if evomap_db is None:
        return []

    db_rows = _fetch_db_rows(evomap_db, [str(item["atom_id"]) for item in candidate_rows])
    cfg = RetrievalConfig(result_limit=top_k)
    doc_counts: dict[str, int] = {}
    results: list[dict[str, Any]] = []
    total_tokens = max(len(set(query_tokens)), 1)
    pack_version = pack_dir.name
    for item in candidate_rows:
        row = db_rows.get(str(item["atom_id"]))
        if not row or not _passes_runtime_gate(row, cfg):
            continue
        doc_id = str(row.get("doc_id") or item["doc_id"])
        current = doc_counts.get(doc_id, 0)
        if current >= cfg.max_per_episode:
            continue
        doc_counts[doc_id] = current + 1
        relevance = min(1.0, float(item["score"]) / total_tokens)
        quality = float(row.get("quality_auto") or 0.0)
        final_score = round(relevance * max(quality, cfg.min_quality), 4)
        results.append(
            {
                "artifact_id": str(row.get("atom_id") or item["atom_id"]),
                "title": str(row.get("title") or item["doc"].get("title") or row.get("question") or "")[:120],
                "snippet": str(row.get("answer") or "")[:500],
                "score": final_score,
                "content_type": str(row.get("atom_type") or "planning_runtime_atom"),
                "quality_score": round(quality, 3),
                "source": PLANNING_REVIEW_SOURCE,
                "planning_pack_meta": {
                    "doc_id": doc_id,
                    "review_domain": str(row.get("review_domain") or item["doc"].get("review_domain") or ""),
                    "source_bucket": str(row.get("source_bucket") or item["doc"].get("source_bucket") or ""),
                    "pack_version": pack_version,
                    "bundle_dir": str(bundle),
                    "pack_dir": str(pack_dir),
                    "selection_score": int(item["score"]),
                    "relevance": round(relevance, 3),
                    "promotion_status": str(row.get("promotion_status") or ""),
                    "groundedness": float(row.get("groundedness") or 0.0),
                },
            }
        )
        if len(results) >= top_k:
            break
    return results
