from __future__ import annotations

import csv
import json
import random
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


NOISE_BUCKETS: tuple[tuple[str, str], ...] = (
    ("review_pack", "lower(d.raw_ref) like '%/_review_pack/%'"),
    ("answer_title", "lower(d.title) like 'answer%'"),
    ("answer_path", "lower(d.raw_ref) like '%/answer%.md'"),
    ("manifest_title", "upper(d.title) = 'MANIFEST'"),
    ("changelog_title", "upper(d.title) = 'CHANGELOG'"),
    ("version_title", "upper(d.title) = 'VERSION'"),
    ("generated_images_title", "upper(d.title) = 'GENERATED IMAGES'"),
    (
        "prompt_wrapper_title",
        "d.title like '你是一个严格的%' or d.title like '请严格按以下提示词执行%'",
    ),
)


@dataclass(frozen=True)
class AtomItem:
    item_id: str
    doc_id: str
    atom_id: str
    source: str
    project: str
    title: str
    raw_ref: str
    atom_type: str
    canonical_question: str
    answer_excerpt: str
    status: str
    promotion_status: str
    quality_auto: float
    bucket: str = ""


@dataclass(frozen=True)
class FamilyItem:
    family_id: str
    title_key: str
    member_count: int
    sample_titles: list[str]
    sample_refs: list[str]
    sample_doc_ids: list[str]
    source_mix: list[str]
    version_hint: bool


def _normalize_title_key(title: str) -> str:
    text = (title or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"\b(v|r)\d+\b", "", text)
    text = re.sub(r"[_\-\s]*20\d{2}[-_]\d{2}[-_]\d{2}", "", text)
    text = re.sub(r"[_\-\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _version_hint(title: str, raw_ref: str) -> bool:
    hay = f"{title} {raw_ref}".lower()
    return bool(re.search(r"(^|[_\-\s])(v|r)\d+(\.md|$|[_\-\s])", hay))


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _answer_excerpt(answer: str, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", answer or "").strip()
    return text[:limit]


def inventory_summary(db_path: str | Path) -> dict[str, Any]:
    conn = _connect(db_path)
    cur = conn.cursor()
    summary: dict[str, Any] = {
        "db_path": str(db_path),
        "counts": {},
        "docs_by_source": [],
        "docs_by_source_project": [],
        "atoms_by_source": [],
        "status_by_source": [],
        "promotion_by_source": [],
        "noise_buckets": [],
        "version_family_candidates": [],
    }
    summary["counts"]["documents"] = cur.execute("select count(*) from documents").fetchone()[0]
    summary["counts"]["episodes"] = cur.execute("select count(*) from episodes").fetchone()[0]
    summary["counts"]["atoms"] = cur.execute("select count(*) from atoms").fetchone()[0]
    summary["counts"]["active"] = cur.execute(
        "select count(*) from atoms where promotion_status='active'"
    ).fetchone()[0]
    summary["counts"]["staged"] = cur.execute(
        "select count(*) from atoms where promotion_status='staged'"
    ).fetchone()[0]
    summary["counts"]["candidate"] = cur.execute(
        "select count(*) from atoms where promotion_status='candidate'"
    ).fetchone()[0]
    summary["counts"]["groundedness_audit"] = cur.execute(
        "select count(*) from groundedness_audit"
    ).fetchone()[0]
    summary["counts"]["promotion_audit"] = cur.execute(
        "select count(*) from promotion_audit"
    ).fetchone()[0]

    for row in cur.execute(
        "select source, count(*) as cnt from documents group by source order by cnt desc"
    ):
        summary["docs_by_source"].append({"source": row["source"], "doc_count": row["cnt"]})

    for row in cur.execute(
        """
        select source, project, count(*) as doc_count
        from documents
        group by source, project
        order by doc_count desc, source, project
        """
    ):
        summary["docs_by_source_project"].append(
            {
                "source": row["source"],
                "project": row["project"],
                "doc_count": row["doc_count"],
            }
        )

    for row in cur.execute(
        """
        select d.source, count(*) as atom_count
        from atoms a
        join episodes e on e.episode_id=a.episode_id
        join documents d on d.doc_id=e.doc_id
        group by d.source
        order by atom_count desc, d.source
        """
    ):
        summary["atoms_by_source"].append({"source": row["source"], "atom_count": row["atom_count"]})

    for row in cur.execute(
        """
        select d.source, a.status, count(*) as atom_count
        from atoms a
        join episodes e on e.episode_id=a.episode_id
        join documents d on d.doc_id=e.doc_id
        group by d.source, a.status
        order by d.source, atom_count desc, a.status
        """
    ):
        summary["status_by_source"].append(
            {"source": row["source"], "status": row["status"], "atom_count": row["atom_count"]}
        )

    for row in cur.execute(
        """
        select d.source, a.promotion_status, count(*) as atom_count
        from atoms a
        join episodes e on e.episode_id=a.episode_id
        join documents d on d.doc_id=e.doc_id
        group by d.source, a.promotion_status
        order by d.source, atom_count desc, a.promotion_status
        """
    ):
        summary["promotion_by_source"].append(
            {
                "source": row["source"],
                "promotion_status": row["promotion_status"],
                "atom_count": row["atom_count"],
            }
        )

    for bucket, clause in NOISE_BUCKETS:
        doc_clause = clause.replace("d.", "")
        cnt = cur.execute(f"select count(*) from documents where {doc_clause}").fetchone()[0]
        summary["noise_buckets"].append({"bucket": bucket, "doc_count": cnt})

    family_counts: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "member_count": 0,
            "titles": [],
            "refs": [],
            "doc_ids": [],
            "sources": Counter(),
            "version_hint": False,
        }
    )
    for row in cur.execute("select doc_id, source, title, raw_ref from documents"):
        title_key = _normalize_title_key(row["title"])
        if not title_key:
            continue
        slot = family_counts[title_key]
        slot["member_count"] += 1
        if len(slot["titles"]) < 3:
            slot["titles"].append(row["title"])
        if len(slot["refs"]) < 3:
            slot["refs"].append(row["raw_ref"])
        if len(slot["doc_ids"]) < 3:
            slot["doc_ids"].append(row["doc_id"])
        slot["sources"][row["source"]] += 1
        slot["version_hint"] = slot["version_hint"] or _version_hint(row["title"], row["raw_ref"])

    candidates = [
        {
            "title_key": title_key,
            "member_count": slot["member_count"],
            "sample_titles": slot["titles"],
            "sample_refs": slot["refs"],
            "sample_doc_ids": slot["doc_ids"],
            "source_mix": [f"{source}:{count}" for source, count in slot["sources"].most_common(4)],
            "version_hint": slot["version_hint"],
        }
        for title_key, slot in family_counts.items()
        if slot["member_count"] >= 2
    ]
    candidates.sort(key=lambda item: (-item["member_count"], not item["version_hint"], item["title_key"]))
    summary["version_family_candidates"] = candidates[:200]
    conn.close()
    return summary


def write_inventory_artifacts(summary: dict[str, Any], output_dir: str | Path, stamp: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    summary_path = out / f"summary_{stamp}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written.append(summary_path)

    source_path = out / f"source_breakdown_{stamp}.csv"
    with source_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["source", "project", "doc_count"])
        writer.writeheader()
        writer.writerows(summary["docs_by_source_project"])
    written.append(source_path)

    noise_path = out / f"noise_buckets_{stamp}.csv"
    with noise_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["bucket", "doc_count"])
        writer.writeheader()
        writer.writerows(summary["noise_buckets"])
    written.append(noise_path)

    family_path = out / f"version_family_candidates_{stamp}.csv"
    with family_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["title_key", "member_count", "version_hint", "source_mix", "sample_titles", "sample_refs"],
        )
        writer.writeheader()
        for row in summary["version_family_candidates"]:
            writer.writerow(
                {
                    "title_key": row["title_key"],
                    "member_count": row["member_count"],
                    "version_hint": row["version_hint"],
                    "source_mix": " | ".join(row["source_mix"]),
                    "sample_titles": " | ".join(row["sample_titles"]),
                    "sample_refs": " | ".join(row["sample_refs"]),
                }
            )
    written.append(family_path)
    return written


def _fetch_atoms_for_where(
    conn: sqlite3.Connection,
    where_clause: str,
    params: tuple[Any, ...],
    *,
    limit: int,
) -> list[AtomItem]:
    rows = conn.execute(
        f"""
        select d.doc_id, d.source, d.project, d.title, d.raw_ref,
               a.atom_id, a.atom_type, a.canonical_question, a.answer,
               a.status, a.promotion_status, a.quality_auto
        from atoms a
        join episodes e on e.episode_id=a.episode_id
        join documents d on d.doc_id=e.doc_id
        where {where_clause}
        order by coalesce(a.quality_auto, 0) desc, a.atom_id
        limit ?
        """,
        params + (limit,),
    ).fetchall()
    items: list[AtomItem] = []
    for row in rows:
        item_id = f"{row['doc_id']}::{row['atom_id']}"
        items.append(
            AtomItem(
                item_id=item_id,
                doc_id=row["doc_id"],
                atom_id=row["atom_id"],
                source=row["source"],
                project=row["project"],
                title=row["title"],
                raw_ref=row["raw_ref"],
                atom_type=row["atom_type"],
                canonical_question=row["canonical_question"] or "",
                answer_excerpt=_answer_excerpt(row["answer"]),
                status=row["status"] or "",
                promotion_status=row["promotion_status"] or "",
                quality_auto=float(row["quality_auto"] or 0.0),
            )
        )
    return items


def build_atom_pack(
    db_path: str | Path,
    strata: list[dict[str, Any]],
    *,
    seed: int,
    pack_id: str,
) -> dict[str, Any]:
    conn = _connect(db_path)
    rng = random.Random(seed)
    items: list[AtomItem] = []
    for stratum in strata:
        source = stratum["source"]
        project = stratum.get("project")
        limit = int(stratum["count"])
        min_quality = float(stratum.get("min_quality", 0.0))
        where = ["d.source = ?", "coalesce(a.quality_auto, 0) >= ?"]
        params: list[Any] = [source, min_quality]
        if project is not None:
            where.append("d.project = ?")
            params.append(project)
        pool = _fetch_atoms_for_where(conn, " and ".join(where), tuple(params), limit=max(limit * 4, limit))
        rng.shuffle(pool)
        seen: set[str] = set()
        picked: list[AtomItem] = []
        for item in pool:
            if item.item_id in seen:
                continue
            seen.add(item.item_id)
            picked.append(item)
            if len(picked) >= limit:
                break
        items.extend(sorted(picked, key=lambda item: item.item_id))
    conn.close()
    payload = {
        "pack_id": pack_id,
        "pack_type": "atom_review",
        "seed": seed,
        "items": [asdict(item) for item in items],
    }
    return payload


def build_noise_pack(
    db_path: str | Path,
    *,
    limit_per_bucket: int,
    seed: int,
    pack_id: str,
) -> dict[str, Any]:
    conn = _connect(db_path)
    rng = random.Random(seed)
    items: list[AtomItem] = []
    for bucket, clause in NOISE_BUCKETS:
        rows = conn.execute(
            f"""
            select d.doc_id, d.source, d.project, d.title, d.raw_ref,
                   a.atom_id, a.atom_type, a.canonical_question, a.answer,
                   a.status, a.promotion_status, a.quality_auto
            from atoms a
            join episodes e on e.episode_id=a.episode_id
            join documents d on d.doc_id=e.doc_id
            where {clause}
            order by coalesce(a.quality_auto, 0) desc, a.atom_id
            limit ?
            """,
            (max(limit_per_bucket * 4, limit_per_bucket),),
        ).fetchall()
        pool = list(rows)
        rng.shuffle(pool)
        count = 0
        for row in pool:
            items.append(
                AtomItem(
                    item_id=f"{row['doc_id']}::{row['atom_id']}",
                    doc_id=row["doc_id"],
                    atom_id=row["atom_id"],
                    source=row["source"],
                    project=row["project"],
                    title=row["title"],
                    raw_ref=row["raw_ref"],
                    atom_type=row["atom_type"],
                    canonical_question=row["canonical_question"] or "",
                    answer_excerpt=_answer_excerpt(row["answer"]),
                    status=row["status"] or "",
                    promotion_status=row["promotion_status"] or "",
                    quality_auto=float(row["quality_auto"] or 0.0),
                    bucket=bucket,
                )
            )
            count += 1
            if count >= limit_per_bucket:
                break
    conn.close()
    return {
        "pack_id": pack_id,
        "pack_type": "noise_review",
        "seed": seed,
        "items": [asdict(item) for item in items],
    }


def build_family_pack(db_path: str | Path, *, limit: int, seed: int, pack_id: str) -> dict[str, Any]:
    summary = inventory_summary(db_path)
    rng = random.Random(seed)
    candidates = list(summary["version_family_candidates"])
    rng.shuffle(candidates)
    picked = sorted(
        candidates[:limit],
        key=lambda item: (-item["member_count"], item["title_key"]),
    )
    items = [
        asdict(
            FamilyItem(
                family_id=f"family::{item['title_key']}",
                title_key=item["title_key"],
                member_count=int(item["member_count"]),
                sample_titles=list(item["sample_titles"]),
                sample_refs=list(item["sample_refs"]),
                sample_doc_ids=list(item["sample_doc_ids"]),
                source_mix=list(item["source_mix"]),
                version_hint=bool(item["version_hint"]),
            )
        )
        for item in picked
    ]
    return {
        "pack_id": pack_id,
        "pack_type": "family_review",
        "seed": seed,
        "items": items,
    }


def write_review_pack(pack: dict[str, Any], output_dir: str | Path) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pack_id = str(pack["pack_id"])
    json_path = out / f"{pack_id}.json"
    json_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prompt_path = out / f"{pack_id}_prompt.txt"
    prompt = (
        "Review the attached pack and return JSON only. "
        "Use decision values service_candidate, review_queue, archive_only, reject_noise. "
        "For family packs, also fill version_relation as singleton, latest, supersedes_prior, "
        "supplement, conflict, or needs_family_review. "
        "Do not invent missing facts. "
        "Pack JSON follows:\n\n"
        + json.dumps(pack, ensure_ascii=False, indent=2)
        + "\n"
    )
    prompt_path.write_text(prompt, encoding="utf-8")
    return [json_path, prompt_path]


def load_review_json(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8", errors="replace").strip()
    if text.startswith("```"):
        text = re.sub(r"^```json\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(text):
            if ch not in "{[":
                continue
            try:
                obj, _ = decoder.raw_decode(text[idx:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
        raise


def _item_key(item: dict[str, Any]) -> str:
    return str(item.get("item_id") or item.get("family_id") or "")


def compare_review_outputs(gold: dict[str, Any], lane: dict[str, Any]) -> dict[str, Any]:
    gold_items = {_item_key(item): item for item in gold["items"] if _item_key(item)}
    lane_items = {_item_key(item): item for item in lane["items"] if _item_key(item)}
    shared_ids = sorted(set(gold_items) & set(lane_items))
    if not shared_ids:
        raise ValueError("no shared review items between gold and lane outputs")

    decision_matches = 0
    lesson_matches = 0
    version_matches = 0
    service_tp = service_fp = reject_tp = reject_fn = 0
    disagreements: list[dict[str, Any]] = []

    for item_id in shared_ids:
        gold_item = gold_items[item_id]
        lane_item = lane_items[item_id]
        gold_decision = gold_item.get("decision", "")
        lane_decision = lane_item.get("decision", "")
        if gold_decision == lane_decision:
            decision_matches += 1
        else:
            disagreements.append(
                {
                    "item_id": item_id,
                    "gold_decision": gold_decision,
                    "lane_decision": lane_decision,
                    "gold_reason": gold_item.get("reason", ""),
                    "lane_reason": lane_item.get("reason", ""),
                }
            )

        if bool(gold_item.get("lesson_candidate")) == bool(lane_item.get("lesson_candidate")):
            lesson_matches += 1

        if gold_item.get("version_relation") == lane_item.get("version_relation"):
            version_matches += 1

        if lane_decision == "service_candidate":
            if gold_decision == "service_candidate":
                service_tp += 1
            else:
                service_fp += 1
        if gold_decision == "reject_noise":
            if lane_decision == "reject_noise":
                reject_tp += 1
            else:
                reject_fn += 1

    schema_valid = all("decision" in item and "reason" in item for item in lane["items"])
    decision_accuracy = decision_matches / len(shared_ids)
    lesson_accuracy = lesson_matches / len(shared_ids)
    version_accuracy = version_matches / len(shared_ids)
    service_precision = service_tp / max(service_tp + service_fp, 1)
    reject_recall = reject_tp / max(reject_tp + reject_fn, 1)

    return {
        "gold_pack_id": gold.get("pack_id"),
        "lane_pack_id": lane.get("pack_id"),
        "shared_items": len(shared_ids),
        "schema_valid": schema_valid,
        "decision_accuracy": round(decision_accuracy, 4),
        "lesson_accuracy": round(lesson_accuracy, 4),
        "version_accuracy": round(version_accuracy, 4),
        "service_candidate_precision": round(service_precision, 4),
        "reject_noise_recall": round(reject_recall, 4),
        "decision_distribution": Counter(item.get("decision", "") for item in lane["items"]),
        "disagreements": disagreements[:25],
    }
