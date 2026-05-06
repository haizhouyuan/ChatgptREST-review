from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import (
    Atom,
    AtomStatus,
    Document,
    Edge,
    Entity,
    Evidence,
    Episode,
    PromotionStatus,
)


def default_db_path() -> str:
    return resolve_evomap_knowledge_runtime_db_path()


def _hash16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _ts() -> float:
    return time.time()


def _stringify(value: Any) -> str:
    if value in (None, "", [], {}, ()):
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load_bundle(bundle_dir: str | Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = Path(bundle_dir)
    manifest = _read_json(root / "MANIFEST.json")
    case_matrix = _read_json(root / "case_matrix.json")
    tool_versions = _read_json(root / "tool_versions.json")
    summary = _read_json(root / "summary.json")
    return manifest, case_matrix, tool_versions, summary


def _bundle_doc_id(validation_id: str) -> str:
    return f"doc_skill_suite_bundle_{_hash16(validation_id)}"


def _case_doc_id(validation_id: str, case_id: str) -> str:
    return f"doc_skill_suite_case_{_hash16(f'{validation_id}:{case_id}')}"


def _suite_entity_id(suite: str) -> str:
    return f"ent_skill_suite_{_hash16(suite)}"


def _capture_doc_id(validation_id: str, capture_id: str) -> str:
    return f"doc_skill_suite_capture_{_hash16(f'{validation_id}:{capture_id}')}"


def _bundle_summary_answer(manifest: dict[str, Any], summary: dict[str, Any]) -> str:
    repo = manifest.get("repo") or {}
    return (
        f"Validation bundle {manifest['validation_id']} covers {summary.get('case_count', 0)} skill-suite cases. "
        f"{summary.get('cases_matching_expectation', 0)} cases matched expectation, "
        f"{summary.get('cases_with_missing_paths', 0)} cases had missing paths, "
        f"and the repo head was {repo.get('git_head', '') or 'unknown'}."
    )


def _case_summary_answer(case: dict[str, Any]) -> str:
    passed_checks = sum(1 for item in case.get("checks", []) if item.get("passed"))
    total_checks = len(case.get("checks", []))
    missing_required = [item["path"] for item in case.get("required_files", []) if not item.get("passed")]
    missing_paths = list(case.get("missing_paths") or [])
    fragments = [
        f"Case {case['case_id']} validates suite {case.get('suite', '')} variant {case.get('variant', '')}.",
        f"Expected outcome is {case.get('expected_outcome', 'pass')}.",
        f"Checks passed: {passed_checks}/{total_checks}.",
        f"checks_ok={case.get('checks_ok')}, verdict_matches_expectation={case.get('verdict_matches_expectation')}.",
    ]
    if missing_required:
        fragments.append(f"Missing required files: {', '.join(missing_required[:5])}.")
    if missing_paths:
        fragments.append(f"Missing source paths: {', '.join(missing_paths[:5])}.")
    warning_ids = [item.get("id", "") for item in case.get("checks", []) if not item.get("passed")]
    if warning_ids:
        fragments.append(f"Failed checks: {', '.join(warning_ids[:6])}.")
    return " ".join(fragment for fragment in fragments if fragment)


def _evidence_excerpt(record: dict[str, Any]) -> str:
    parts = [
        f"alias={record.get('alias', '')}",
        f"role={record.get('role', '')}",
        f"path={record.get('materialized_path', record.get('source_path', ''))}",
        f"sha256={record.get('sha256', '')}",
        f"bytes={record.get('size_bytes', 0)}",
    ]
    return " | ".join(part for part in parts if part)


def import_validation_bundle(
    *,
    db_path: str | Path,
    bundle_dir: str | Path,
    promotion_status: str = PromotionStatus.STAGED.value,
) -> dict[str, Any]:
    manifest, case_matrix, tool_versions, summary = _load_bundle(bundle_dir)
    bundle_root = Path(bundle_dir)
    validation_id = str(manifest["validation_id"])
    now = _ts()

    db = KnowledgeDB(str(db_path))
    db.init_schema()

    bundle_doc_id = _bundle_doc_id(validation_id)
    bundle_episode_id = f"ep_{bundle_doc_id}"
    bundle_atom_id = f"at_{bundle_doc_id}"
    db.put_document(
        Document(
            doc_id=bundle_doc_id,
            source="skill_suite_review_plane",
            project=manifest.get("repo", {}).get("root", "ChatgptREST"),
            raw_ref=f"skill-suite://bundle/{validation_id}",
            title=f"Skill suite validation bundle {validation_id}",
            created_at=now,
            updated_at=now,
            meta_json=json.dumps(
                {
                    "bundle_root": str(bundle_root),
                    "summary": summary,
                    "governance": manifest.get("governance", {}),
                    "rubric": manifest.get("rubric", {}),
                },
                ensure_ascii=False,
            ),
        ),
    )
    db.put_episode(
        Episode(
            episode_id=bundle_episode_id,
            doc_id=bundle_doc_id,
            episode_type="skill_suite_validation",
            title=f"Skill suite validation bundle {validation_id}",
            summary=str(bundle_root),
            start_ref=str(bundle_root / "MANIFEST.json"),
            end_ref=str(bundle_root / "case_matrix.json"),
            time_start=now,
            time_end=now,
            source_ext=json.dumps({"kind": "validation_bundle"}, ensure_ascii=False),
        ),
    )
    db.put_atom(
        Atom(
            atom_id=bundle_atom_id,
            episode_id=bundle_episode_id,
            atom_type="decision",
            question=f"What does skill-suite validation bundle {validation_id} show?",
            answer=_bundle_summary_answer(manifest, summary),
            canonical_question=f"skill suite validation bundle {validation_id}",
            applicability=json.dumps(
                {"source": "skill_suite_review_plane", "kind": "validation_bundle", "validation_id": validation_id},
                ensure_ascii=False,
            ),
            status=AtomStatus.PUBLISHED.value,
            stability="versioned",
            quality_auto=0.9 if summary.get("cases_matching_expectation", 0) == summary.get("case_count", 0) else 0.65,
            value_auto=0.82,
            source_quality=0.88,
            promotion_status=promotion_status,
            promotion_reason="skill_suite_review_plane",
            valid_from=now,
        ),
    )

    bundle_evidence_paths = [
        bundle_root / "MANIFEST.json",
        bundle_root / "case_matrix.json",
        bundle_root / "summary.json",
        bundle_root / "tool_versions.json",
        bundle_root / "bundle_validation.json",
    ]
    evidence_rows = 0
    for path in bundle_evidence_paths:
        if not path.exists():
            continue
        db.put_evidence(
            Evidence(
                evidence_id=f"ev_{_hash16(f'{bundle_atom_id}:{path.name}')}",
                atom_id=bundle_atom_id,
                doc_id=bundle_doc_id,
                span_ref=path.name,
                excerpt=f"path={path} | sha256={_hash16(path.read_text(encoding='utf-8', errors='ignore'))}",
                excerpt_hash=_hash16(path.read_text(encoding="utf-8", errors="ignore")),
                evidence_role="supports",
                weight=1.0,
            ),
        )
        evidence_rows += 1

    suite_names = sorted({str(case.get("suite") or "") for case in case_matrix.get("cases", []) if case.get("suite")})
    for suite in suite_names:
        ent_id = _suite_entity_id(suite)
        db.put_entity(
            Entity(
                entity_id=ent_id,
                entity_type="skill_suite",
                name=suite,
                normalized_name=suite.lower(),
            ),
        )
        db.put_edge(
            Edge(
                from_id=bundle_doc_id,
                to_id=ent_id,
                edge_type="COVERS_SUITE",
                from_kind="document",
                to_kind="entity",
                meta_json=json.dumps({"validation_id": validation_id}, ensure_ascii=False),
            ),
        )

    case_docs = 0
    for case in case_matrix.get("cases", []):
        case_id = str(case["case_id"])
        case_doc_id = _case_doc_id(validation_id, case_id)
        case_episode_id = f"ep_{case_doc_id}"
        case_atom_id = f"at_{case_doc_id}"
        db.put_document(
            Document(
                doc_id=case_doc_id,
                source="skill_suite_review_plane",
                project=manifest.get("repo", {}).get("root", "ChatgptREST"),
                raw_ref=f"skill-suite://case/{validation_id}/{case_id}",
                title=f"Skill suite case {case_id}",
                created_at=now,
                updated_at=now,
                meta_json=json.dumps(
                    {
                        "validation_id": validation_id,
                        "suite": case.get("suite"),
                        "variant": case.get("variant"),
                        "classification": case.get("classification"),
                        "expected_outcome": case.get("expected_outcome"),
                        "checks_ok": case.get("checks_ok"),
                        "verdict_matches_expectation": case.get("verdict_matches_expectation"),
                        "missing_paths": case.get("missing_paths"),
                        "notes": case.get("notes", ""),
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        db.put_episode(
            Episode(
                episode_id=case_episode_id,
                doc_id=case_doc_id,
                episode_type="skill_suite_validation_case",
                title=f"Skill suite case {case_id}",
                summary=f"{case.get('suite', '')}/{case.get('variant', '')}",
                start_ref=str(bundle_root / "case_matrix.json"),
                end_ref=str(bundle_root / "case_matrix.json"),
                time_start=now,
                time_end=now,
                source_ext=json.dumps({"kind": "validation_case"}, ensure_ascii=False),
            ),
        )
        db.put_atom(
            Atom(
                atom_id=case_atom_id,
                episode_id=case_episode_id,
                atom_type="lesson",
                question=f"What does skill-suite validation case {case_id} demonstrate?",
                answer=_case_summary_answer(case),
                canonical_question=f"skill suite case {case_id}",
                applicability=json.dumps(
                    {
                        "source": "skill_suite_review_plane",
                        "kind": "validation_case",
                        "validation_id": validation_id,
                        "suite": case.get("suite", ""),
                        "variant": case.get("variant", ""),
                    },
                    ensure_ascii=False,
                ),
                status=AtomStatus.PUBLISHED.value,
                stability="versioned",
                quality_auto=0.88 if case.get("checks_ok") else 0.58,
                value_auto=0.8 if case.get("verdict_matches_expectation") else 0.55,
                source_quality=0.86,
                promotion_status=promotion_status,
                promotion_reason="skill_suite_review_plane",
                valid_from=now,
            ),
        )
        db.put_edge(
            Edge(
                from_id=case_doc_id,
                to_id=bundle_doc_id,
                edge_type="PART_OF_VALIDATION_BUNDLE",
                from_kind="document",
                to_kind="document",
                meta_json=json.dumps({"validation_id": validation_id}, ensure_ascii=False),
            ),
        )
        if case.get("suite"):
            db.put_edge(
                Edge(
                    from_id=case_doc_id,
                    to_id=_suite_entity_id(str(case["suite"])),
                    edge_type="VALIDATES_SUITE",
                    from_kind="document",
                    to_kind="entity",
                    meta_json=json.dumps({"variant": case.get("variant", "")}, ensure_ascii=False),
                ),
            )
        for group in ("inputs", "artifacts"):
            role = "input" if group == "inputs" else "artifact"
            for record in case.get(group, []):
                excerpt = _evidence_excerpt(record)
                evidence_key = f"{case_atom_id}:{record.get('alias', '')}:{record.get('sha256', '')}"
                db.put_evidence(
                    Evidence(
                        evidence_id=f"ev_{_hash16(evidence_key)}",
                        atom_id=case_atom_id,
                        doc_id=case_doc_id,
                        span_ref=record.get("alias", ""),
                        excerpt=excerpt,
                        excerpt_hash=_hash16(excerpt),
                        evidence_role=role,
                        weight=1.0 if role == "artifact" else 0.8,
                    ),
                )
                evidence_rows += 1
        case_docs += 1

    for capture in tool_versions.get("captures", []):
        capture_id = str(capture["id"])
        capture_doc_id = _capture_doc_id(validation_id, capture_id)
        db.put_document(
            Document(
                doc_id=capture_doc_id,
                source="skill_suite_review_plane",
                project=manifest.get("repo", {}).get("root", "ChatgptREST"),
                raw_ref=f"skill-suite://capture/{validation_id}/{capture_id}",
                title=f"Skill suite capture {capture_id}",
                created_at=now,
                updated_at=now,
                meta_json=json.dumps(capture, ensure_ascii=False),
            ),
        )
        db.put_edge(
            Edge(
                from_id=capture_doc_id,
                to_id=bundle_doc_id,
                edge_type="CAPTURED_IN_VALIDATION_BUNDLE",
                from_kind="document",
                to_kind="document",
                meta_json=json.dumps({"capture_id": capture_id}, ensure_ascii=False),
            ),
        )
    db.commit()
    stats = db.stats()
    db.close()
    return {
        "ok": True,
        "validation_id": validation_id,
        "bundle_doc_id": bundle_doc_id,
        "case_docs": case_docs,
        "suite_entities": len(suite_names),
        "evidence_rows": evidence_rows,
        "db_stats": stats,
        "db_path": str(db_path),
    }
