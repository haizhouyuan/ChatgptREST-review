#!/usr/bin/env python3
"""Migrate Planning Runtime Pack atoms into the EvoMap Knowledge DB.

P0 Fix for the data plane disconnect discovered in the 2026-04-02 audit:
  - Pack atoms use `at_c_<hash>_<n>_<n>` format IDs
  - EvoMap DB uses `at_<uuid>` format IDs
  - Result: search_planning_runtime_pack() always returns [] because
    _fetch_db_rows() can't find any pack atoms in the DB

This script:
  1. Reads docs.tsv + atoms.tsv from the latest ready release bundle
  2. Creates proper Document → Episode → Atom records in the EvoMap DB
  3. Tags documents with planning_review metadata
  4. Sets promotion_status='active' and groundedness=1.0 (pack was review-approved)
  5. Preserves the original pack atom_id so the pack search can find them

Usage:
  # Dry run (default): show what would be ingested without modifying DB
  python scripts/migrate_planning_pack_to_evomap_db.py

  # Execute the migration
  python scripts/migrate_planning_pack_to_evomap_db.py --execute

  # Use a specific bundle directory
  python scripts/migrate_planning_pack_to_evomap_db.py --execute --bundle-dir /path/to/bundle
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import sys
import time
import uuid
from pathlib import Path

# Ensure project root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import (
    Atom,
    AtomStatus,
    Document,
    Episode,
    EpisodeType,
    PromotionStatus,
    Stability,
)
from chatgptrest.evomap.knowledge.planning_runtime_pack_search import (
    resolve_ready_planning_runtime_pack_bundle,
    _read_json,
    _read_tsv,
    _resolve_path,
    REPO_ROOT as PACK_REPO_ROOT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("migrate_planning_pack")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex}"


def load_pack_data(bundle_dir: Path) -> tuple[dict, list[dict], list[str]]:
    """Load docs, atoms, and allowed atom_ids from the pack bundle."""
    manifest = _read_json(bundle_dir / "release_bundle_manifest.json")
    pack_dir = _resolve_path(str(manifest.get("pack_dir") or ""), base=PACK_REPO_ROOT)
    if not pack_dir.exists():
        raise FileNotFoundError(f"Pack dir not found: {pack_dir}")

    docs_path = pack_dir / "docs.tsv"
    atoms_path = pack_dir / "atoms.tsv"
    retrieval_path = pack_dir / "retrieval_pack.json"

    docs = {row["doc_id"]: row for row in _read_tsv(docs_path)}
    atoms = list(_read_tsv(atoms_path))
    allowed_ids = list(set(str(i) for i in _read_json(retrieval_path).get("atom_ids", [])))

    logger.info("Pack data loaded: %d docs, %d atoms, %d allowed", len(docs), len(atoms), len(allowed_ids))
    return docs, atoms, allowed_ids


def build_records(
    docs: dict[str, dict],
    atoms: list[dict],
    allowed_ids: list[str],
    *,
    pack_version: str,
) -> tuple[list[Document], list[Episode], list[Atom]]:
    """Build EvoMap Document → Episode → Atom records from pack data."""
    now = time.time()
    doc_records: list[Document] = []
    ep_records: list[Episode] = []
    atom_records: list[Atom] = []

    allowed_set = set(allowed_ids)
    seen_doc_ids: set[str] = set()
    seen_ep_ids: dict[str, str] = {}  # pack doc_id → episode_id

    for atom_row in atoms:
        atom_id = str(atom_row.get("atom_id") or "")
        if atom_id not in allowed_set:
            continue

        doc_id = str(atom_row.get("doc_id") or "")
        if not doc_id or doc_id not in docs:
            continue

        doc_data = docs[doc_id]

        # Create Document record (once per doc_id)
        if doc_id not in seen_doc_ids:
            seen_doc_ids.add(doc_id)
            doc = Document(
                doc_id=doc_id,
                source="planning_review_pack",
                project="planning",
                raw_ref=str(doc_data.get("raw_ref") or ""),
                title=str(doc_data.get("title") or ""),
                created_at=now,
                updated_at=now,
                hash=_hash(json.dumps(doc_data, ensure_ascii=False, sort_keys=True)),
                meta_json=json.dumps(
                    {
                        "planning_review": {
                            "review_domain": str(doc_data.get("review_domain") or ""),
                            "source_bucket": str(doc_data.get("source_bucket") or ""),
                            "document_role": str(doc_data.get("document_role") or ""),
                            "final_bucket": str(doc_data.get("final_bucket") or ""),
                            "service_readiness": str(doc_data.get("service_readiness") or ""),
                            "is_latest_output": str(doc_data.get("is_latest_output") or "0"),
                            "pack_version": pack_version,
                            "migrated_from": "planning_runtime_pack_tsv",
                            "migrated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                        }
                    },
                    ensure_ascii=False,
                ),
            )
            doc_records.append(doc)

        # Create Episode record (one per doc, groups all atoms from that doc)
        if doc_id not in seen_ep_ids:
            ep_id = _new_id("ep_prp_")
            seen_ep_ids[doc_id] = ep_id
            ep = Episode(
                episode_id=ep_id,
                doc_id=doc_id,
                episode_type=EpisodeType.MD_SECTION.value,
                title=str(doc_data.get("title") or ""),
                summary=f"Planning review pack atoms for: {doc_data.get('title', doc_id)}",
                time_start=now,
                time_end=now,
            )
            ep_records.append(ep)

        ep_id = seen_ep_ids[doc_id]

        # Create Atom record — using the original pack atom_id
        question = str(atom_row.get("question") or "")
        answer = str(atom_row.get("answer") or "")
        canonical = str(atom_row.get("canonical_question") or question)

        atom = Atom(
            atom_id=atom_id,  # Preserve original pack ID
            episode_id=ep_id,
            atom_type=str(atom_row.get("atom_type") or "qa"),
            question=question,
            answer=answer,
            canonical_question=canonical,
            stability=Stability.VERSIONED.value,
            status=AtomStatus.SCORED.value,
            valid_from=now,
            quality_auto=0.6,  # Conservative default for review-approved content
            value_auto=0.6,
            groundedness=1.0,  # Pack was review-approved
            confidence=0.8,
            source_quality=0.7,
            promotion_status=PromotionStatus.ACTIVE.value,
            promotion_reason=f"migrated from planning_runtime_pack {pack_version}",
            is_chain_head=1,
        )
        atom.compute_hash()
        atom_records.append(atom)

    logger.info(
        "Built records: %d documents, %d episodes, %d atoms",
        len(doc_records), len(ep_records), len(atom_records),
    )
    return doc_records, ep_records, atom_records


def check_existing(db: KnowledgeDB, atom_ids: list[str]) -> tuple[int, int]:
    """Check how many atom_ids already exist in the DB."""
    conn = db.connect()
    existing = 0
    missing = 0
    for aid in atom_ids:
        row = conn.execute("SELECT 1 FROM atoms WHERE atom_id = ?", (aid,)).fetchone()
        if row:
            existing += 1
        else:
            missing += 1
    return existing, missing


def execute_migration(
    db: KnowledgeDB,
    doc_records: list[Document],
    ep_records: list[Episode],
    atom_records: list[Atom],
) -> dict:
    """Insert records into the DB, skipping any that already exist."""
    stats = {
        "docs_inserted": 0,
        "docs_skipped": 0,
        "episodes_inserted": 0,
        "episodes_skipped": 0,
        "atoms_inserted": 0,
        "atoms_skipped": 0,
    }

    for doc in doc_records:
        if db.put_document_if_absent(doc):
            stats["docs_inserted"] += 1
        else:
            stats["docs_skipped"] += 1

    for ep in ep_records:
        if db.put_episode_if_absent(ep):
            stats["episodes_inserted"] += 1
        else:
            stats["episodes_skipped"] += 1

    for atom in atom_records:
        if db.put_atom_if_absent(atom):
            stats["atoms_inserted"] += 1
        else:
            stats["atoms_skipped"] += 1

    db.commit()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate planning pack atoms to EvoMap DB")
    parser.add_argument("--execute", action="store_true", help="Execute migration (default: dry run)")
    parser.add_argument("--bundle-dir", type=str, default="", help="Specific bundle dir to use")
    parser.add_argument("--db-path", type=str, default="", help="EvoMap DB path (default: auto-resolve)")
    args = parser.parse_args()

    # Resolve bundle
    bundle = resolve_ready_planning_runtime_pack_bundle(args.bundle_dir)
    if bundle is None:
        logger.error("No ready planning runtime pack bundle found")
        sys.exit(1)
    logger.info("Using bundle: %s", bundle)

    manifest = _read_json(bundle / "release_bundle_manifest.json")
    pack_dir_str = str(manifest.get("pack_dir") or "")
    pack_version = Path(pack_dir_str).name if pack_dir_str else "unknown"
    logger.info("Pack version: %s", pack_version)

    # Load pack data
    docs, atoms, allowed_ids = load_pack_data(bundle)

    # Build EvoMap records
    doc_records, ep_records, atom_records = build_records(
        docs, atoms, allowed_ids, pack_version=pack_version,
    )

    if not atom_records:
        logger.warning("No atoms to migrate")
        sys.exit(0)

    # Open DB
    db_path = args.db_path or resolve_evomap_knowledge_runtime_db_path()
    logger.info("EvoMap DB: %s", db_path)
    db = KnowledgeDB(db_path)
    db.init_schema()

    # Check existing state
    existing, missing = check_existing(db, [a.atom_id for a in atom_records])
    logger.info("Pre-migration check: %d already in DB, %d missing", existing, missing)

    if not args.execute:
        logger.info("=== DRY RUN ===")
        logger.info("Would insert: %d documents, %d episodes, %d atoms", len(doc_records), len(ep_records), len(atom_records))
        logger.info("Sample doc: %s", doc_records[0].to_row() if doc_records else "none")
        logger.info("Sample atom: %s", atom_records[0].atom_id if atom_records else "none")
        logger.info("Run with --execute to apply")
        return

    # Execute
    stats = execute_migration(db, doc_records, ep_records, atom_records)
    logger.info("Migration complete: %s", json.dumps(stats, indent=2))

    # Verify
    ver_existing, ver_missing = check_existing(db, [a.atom_id for a in atom_records])
    logger.info("Post-migration verify: %d in DB, %d still missing", ver_existing, ver_missing)

    if ver_missing > 0:
        logger.error("VERIFICATION FAILED: %d atoms still missing after migration", ver_missing)
        sys.exit(1)
    else:
        logger.info("✅ All %d atoms verified in DB", ver_existing)

    db.close()


if __name__ == "__main__":
    main()
