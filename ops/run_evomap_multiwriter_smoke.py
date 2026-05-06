"""EvoMap multi-writer smoke for KnowledgeDB lock hardening.

Runs a narrow concurrent write workload against a dedicated sqlite DB and
reports whether writes complete without surfacing `database is locked`.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode


@dataclass
class WorkerResult:
    worker_id: int
    writes_attempted: int
    writes_succeeded: int
    errors: list[str]
    elapsed_ms: int


@dataclass
class SmokeSummary:
    db_path: str
    workers: int
    writes_per_worker: int
    total_attempted: int
    total_succeeded: int
    error_count: int
    locked_errors: int
    elapsed_ms: int
    worker_results: list[WorkerResult]


def _seed_one(db: KnowledgeDB, worker_id: int, seq: int) -> None:
    suffix = f"w{worker_id:02d}_{seq:04d}"
    doc = Document(
        doc_id=f"doc_{suffix}",
        source="multiwriter_smoke",
        project="ChatgptREST",
        raw_ref=suffix,
    )
    ep = Episode(
        episode_id=f"ep_{suffix}",
        doc_id=doc.doc_id,
        episode_type="ops",
        title=f"multiwriter {suffix}",
    )
    atom = Atom(
        atom_id=f"at_{suffix}",
        episode_id=ep.episode_id,
        question=f"What happened in {suffix}?",
        canonical_question=f"multiwriter {suffix}?",
        answer=f"worker {worker_id} wrote sequence {seq}",
        promotion_status="staged",
        valid_from=time.time(),
    )
    db.put_document(doc)
    db.put_episode(ep)
    db.put_atom(atom)
    db.commit()


def _worker_run(db_path: str, worker_id: int, writes_per_worker: int) -> WorkerResult:
    started = time.time()
    db = KnowledgeDB(db_path=db_path)
    db.connect()
    db.init_schema()
    succeeded = 0
    errors: list[str] = []

    try:
        for seq in range(writes_per_worker):
            try:
                _seed_one(db, worker_id, seq)
                succeeded += 1
            except Exception as exc:  # pragma: no cover - exercised in smoke
                errors.append(str(exc))
    finally:
        db.close()

    return WorkerResult(
        worker_id=worker_id,
        writes_attempted=writes_per_worker,
        writes_succeeded=succeeded,
        errors=errors,
        elapsed_ms=int((time.time() - started) * 1000),
    )


def run_multiwriter_smoke(
    *,
    db_path: str,
    workers: int = 4,
    writes_per_worker: int = 25,
) -> SmokeSummary:
    started = time.time()
    resolved_db = str(Path(db_path).expanduser().resolve())
    Path(resolved_db).parent.mkdir(parents=True, exist_ok=True)

    results: list[WorkerResult] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_worker_run, resolved_db, worker_id, writes_per_worker)
            for worker_id in range(workers)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item.worker_id)
    total_attempted = sum(item.writes_attempted for item in results)
    total_succeeded = sum(item.writes_succeeded for item in results)
    all_errors = [error for item in results for error in item.errors]
    locked_errors = sum(1 for error in all_errors if "database is locked" in error.lower())

    return SmokeSummary(
        db_path=resolved_db,
        workers=workers,
        writes_per_worker=writes_per_worker,
        total_attempted=total_attempted,
        total_succeeded=total_succeeded,
        error_count=len(all_errors),
        locked_errors=locked_errors,
        elapsed_ms=int((time.time() - started) * 1000),
        worker_results=results,
    )


def _default_db_path() -> str:
    fd, path = tempfile.mkstemp(prefix="evomap_multiwriter_", suffix=".db")
    os.close(fd)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EvoMap KnowledgeDB multi-writer smoke")
    parser.add_argument("--db", default="", help="Path to dedicated smoke DB (default: temp file)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--writes-per-worker", type=int, default=25)
    parser.add_argument("--report-json", default="", help="Optional JSON report path")
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="Keep the generated temp DB instead of removing it after the run",
    )
    args = parser.parse_args()

    created_temp = not args.db
    db_path = args.db or _default_db_path()
    summary = run_multiwriter_smoke(
        db_path=db_path,
        workers=args.workers,
        writes_per_worker=args.writes_per_worker,
    )

    payload = asdict(summary)
    if args.report_json:
        report_path = Path(args.report_json).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if created_temp and not args.keep_db:
        try:
            Path(db_path).unlink(missing_ok=True)
        except OSError:
            pass

    return 0 if summary.locked_errors == 0 and summary.total_succeeded == summary.total_attempted else 1


if __name__ == "__main__":
    raise SystemExit(main())
