#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_openmind_kb_search_db_path, resolve_openmind_kb_vector_db_path
from chatgptrest.kb.hub import KBHub


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "kb_hybrid_runtime_probe"


def _db_count(path: Path, table: str) -> int:
    if not path.exists():
        return 0
    conn = sqlite3.connect(str(path))
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def _systemctl_show(unit: str) -> list[str]:
    proc = subprocess.run(
        ["systemctl", "--user", "show", unit, "-p", "FragmentPath", "-p", "ExecStart", "-p", "Environment"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return lines


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_probe(*, output_root: Path, query: str, top_k: int) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    kb_search = Path(resolve_openmind_kb_search_db_path())
    kb_vector = Path(resolve_openmind_kb_vector_db_path())
    hub = KBHub(db_path=kb_search, vec_db_path=kb_vector)
    embedder = hub._get_embedder()
    hits = hub.search(query, top_k=top_k)
    payload = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python_executable": sys.executable,
        "service_runtime": {
            "api": _systemctl_show("chatgptrest-api.service"),
            "mcp": _systemctl_show("chatgptrest-mcp.service"),
        },
        "paths": {
            "kb_search_db": str(kb_search),
            "kb_vector_db": str(kb_vector),
        },
        "counts": {
            "kb_fts": _db_count(kb_search, "kb_fts"),
            "kb_fts_meta": _db_count(kb_search, "kb_fts_meta"),
            "kb_vectors": _db_count(kb_vector, "vectors"),
        },
        "embedder_ready": embedder is not None,
        "query": query,
        "top_k": top_k,
        "vec_enabled_hits": sum(1 for hit in hits if float(hit.vec_score or 0.0) > 0.0),
        "hits": [
            {
                "artifact_id": hit.artifact_id,
                "title": hit.title,
                "score": hit.score,
                "fts_score": hit.fts_score,
                "vec_score": hit.vec_score,
                "source_path": hit.source_path,
            }
            for hit in hits
        ],
    }
    _write_json(run_dir / "summary.json", payload)
    (run_dir / "README.md").write_text(
        "\n".join(
            [
                "# KB Hybrid Runtime Probe",
                "",
                f"- `python_executable`: `{payload['python_executable']}`",
                f"- `kb_search_db`: `{kb_search}`",
                f"- `kb_vector_db`: `{kb_vector}`",
                f"- `kb_fts`: `{payload['counts']['kb_fts']}`",
                f"- `kb_vectors`: `{payload['counts']['kb_vectors']}`",
                f"- `embedder_ready`: `{payload['embedder_ready']}`",
                f"- `vec_enabled_hits`: `{payload['vec_enabled_hits']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture live KB hybrid runtime evidence under the repo .venv.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--query", default="planning 项目")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    payload = run_probe(output_root=Path(args.output_root), query=args.query, top_k=args.top_k)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
