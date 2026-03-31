from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import sqlite3


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_run_multiwriter_smoke_writes_all_rows(tmp_path: Path) -> None:
    module = _load_module(
        Path("ops/run_evomap_multiwriter_smoke.py").resolve(),
        "test_evomap_multiwriter_smoke_run",
    )
    db_path = tmp_path / "multiwriter.db"

    summary = module.run_multiwriter_smoke(
        db_path=str(db_path),
        workers=2,
        writes_per_worker=5,
    )

    assert summary.total_attempted == 10
    assert summary.total_succeeded == 10
    assert summary.locked_errors == 0
    assert summary.error_count == 0

    conn = sqlite3.connect(str(db_path))
    try:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        atom_count = conn.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]
        assert doc_count == 10
        assert atom_count == 10
    finally:
        conn.close()


def test_multiwriter_smoke_cli_writes_report(tmp_path: Path) -> None:
    module = _load_module(
        Path("ops/run_evomap_multiwriter_smoke.py").resolve(),
        "test_evomap_multiwriter_smoke_cli",
    )
    db_path = tmp_path / "multiwriter.db"
    report_path = tmp_path / "report.json"
    argv = [
        "run_evomap_multiwriter_smoke.py",
        "--db",
        str(db_path),
        "--workers",
        "2",
        "--writes-per-worker",
        "3",
        "--report-json",
        str(report_path),
    ]

    old_argv = sys.argv[:]
    try:
        sys.argv = argv
        rc = module.main()
    finally:
        sys.argv = old_argv

    assert rc == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["workers"] == 2
    assert report["writes_per_worker"] == 3
    assert report["locked_errors"] == 0
    assert report["total_succeeded"] == 6
