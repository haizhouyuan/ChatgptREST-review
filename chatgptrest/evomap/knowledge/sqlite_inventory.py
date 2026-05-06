"""SQLite inventory ingestion into canonical EvoMap knowledge DB.

This module treats databases as archive-plane source material:
- one Document per SQLite file
- one Episode for the database snapshot
- one Episode per table/view
- one Atom for the database summary
- one Atom per table/view schema+sample profile

The goal is safe, deterministic ingestion of "all databases" without doing
dangerous row-level merges across unrelated authoritative stores.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, Evidence

DB_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__"}
SQLITE_HEADER = b"SQLite format 3\x00"
SENSITIVE_COLUMN_TOKENS = (
    "answer",
    "auth",
    "body",
    "conversation",
    "cookie",
    "credential",
    "error",
    "header",
    "input",
    "message",
    "metadata",
    "output",
    "param",
    "password",
    "prompt",
    "question",
    "raw",
    "response",
    "secret",
    "token",
    "url",
)
SAFE_TEXT_COLUMN_NAMES = {
    "branch",
    "event_type",
    "kind",
    "provider",
    "role",
    "source",
    "state",
    "status",
    "type",
}
STRICT_REDACTION_ROLES = {
    "browser_profile",
    "checkpoint_store",
    "controller_lanes",
    "dedup_store",
    "effects_store",
    "event_bus_store",
    "evomap_canonical",
    "evomap_knowledge",
    "issue_canonical",
    "issue_canonical_legacy",
    "job_store",
    "kb_registry_legacy",
    "kb_search_legacy",
    "mcp_idempotency",
    "memory_store",
}
DEFAULT_ROOTS = [
    Path("/vol1/1000/projects/ChatgptREST"),
    Path("/vol1/maint"),
    Path.home() / ".openmind",
]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _now() -> float:
    return time.time()


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _truncate(text: str, *, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _sanitize_value(value: Any, *, max_chars: int = 240) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {
            "type": "bytes",
            "size": len(value),
            "sha256": hashlib.sha256(value).hexdigest()[:16],
        }
    text = str(value)
    return _truncate(text, limit=max_chars)


def _text_sample_descriptor(text: str) -> dict[str, Any]:
    stripped = text.strip()
    sample_type = "text"
    if stripped.startswith(("{", "[")) and stripped.endswith(("}", "]")):
        sample_type = "json_like"
    elif "://" in stripped:
        sample_type = "url_like"
    elif "\n" in stripped:
        sample_type = "multiline_text"
    return {
        "type": sample_type,
        "length": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "redacted": True,
    }


def _inventory_sample_value(column_name: str, value: Any, *, db_role: str, max_chars: int = 120) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, bytes):
        return _sanitize_value(value, max_chars=max_chars)

    text = str(value)
    normalized = column_name.lower()
    if normalized in SAFE_TEXT_COLUMN_NAMES:
        return _truncate(text, limit=max_chars)
    if db_role in STRICT_REDACTION_ROLES or any(token in normalized for token in SENSITIVE_COLUMN_TOKENS):
        return _text_sample_descriptor(text)
    return _text_sample_descriptor(text)


def _looks_like_sqlite(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            header = fh.read(len(SQLITE_HEADER))
    except OSError:
        return False
    return header == SQLITE_HEADER


def _project_for_path(path: Path) -> str:
    path_str = str(path)
    if path_str.startswith("/vol1/1000/projects/ChatgptREST"):
        return "chatgptrest"
    if path_str.startswith("/vol1/maint"):
        return "maint"
    if path_str.startswith(str(Path.home() / ".openmind")):
        return "openmind_home"
    return "external"


def _database_role(path: Path, *, canonical_target: Path | None = None) -> str:
    path_str = str(path)
    name = path.name
    if canonical_target and path.resolve() == canonical_target.resolve():
        return "evomap_canonical"
    if "backups/evomap_" in path_str:
        return "evomap_backup"
    if name == "jobdb.sqlite3":
        return "job_store"
    if name == "canonical.sqlite3":
        return "issue_canonical"
    if name == "knowledge_v2.sqlite3":
        return "issue_canonical_legacy"
    if name == "kb_search.db":
        return "kb_search_legacy"
    if name == "kb_registry.db":
        return "kb_registry_legacy"
    if name == "memory.db":
        return "memory_store"
    if name == "events.db":
        return "event_bus_store"
    if name == "checkpoint.db":
        return "checkpoint_store"
    if name == "dedup.db":
        return "dedup_store"
    if name == "effects.db":
        return "effects_store"
    if name == "controller_lanes.sqlite3":
        return "controller_lanes"
    if name == "mcp_idempotency.sqlite3":
        return "mcp_idempotency"
    if name == "evomap_knowledge.db":
        return "evomap_knowledge"
    if "chrome-profile" in path_str or "first_party_sets.db" == name or "heavy_ad_intervention_opt_out.db" == name:
        return "browser_profile"
    return "sqlite_database"


@dataclass
class TableInventory:
    name: str
    object_type: str
    row_count: int | None = None
    column_count: int = 0
    columns: list[dict[str, Any]] = field(default_factory=list)
    sql: str = ""
    sample_rows: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class DatabaseInventory:
    path: str
    project: str
    role: str
    size_bytes: int
    mtime: float
    file_hash: str
    table_count: int = 0
    view_count: int = 0
    total_rows: int | None = None
    tables: list[TableInventory] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SqliteInventoryIngestStats:
    discovered: int = 0
    analyzed: int = 0
    ingested_documents: int = 0
    ingested_episodes: int = 0
    ingested_atoms: int = 0
    ingested_evidence: int = 0
    failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_sqlite_databases(roots: Iterable[str | os.PathLike[str] | Path]) -> list[Path]:
    discovered: set[Path] = set()
    for raw_root in roots:
        root = Path(raw_root).expanduser()
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
            for filename in filenames:
                path = Path(dirpath) / filename
                if path.suffix.lower() in DB_SUFFIXES:
                    discovered.add(path.resolve())
    return sorted(discovered)


def filter_sqlite_databases(
    paths: Iterable[str | os.PathLike[str] | Path],
    *,
    exclude_paths: Iterable[str | os.PathLike[str] | Path] = (),
) -> list[Path]:
    excluded = {Path(path).expanduser().resolve() for path in exclude_paths}
    return [
        path
        for path in sorted(Path(raw).expanduser().resolve() for raw in paths)
        if path not in excluded
    ]


def _connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _load_table_inventory(
    conn: sqlite3.Connection,
    *,
    name: str,
    object_type: str,
    sql: str,
    sample_rows: int,
    db_role: str,
) -> TableInventory:
    item = TableInventory(name=name, object_type=object_type, sql=sql or "")
    try:
        item.columns = [
            {
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "notnull": row["notnull"],
                "default": row["dflt_value"],
                "pk": row["pk"],
            }
            for row in conn.execute(f"PRAGMA table_info({_quote_ident(name)})").fetchall()
        ]
        item.column_count = len(item.columns)
    except sqlite3.Error as exc:
        item.errors.append(f"pragma table_info failed: {exc}")

    try:
        item.row_count = int(
            conn.execute(f"SELECT COUNT(*) AS c FROM {_quote_ident(name)}").fetchone()["c"]
        )
    except sqlite3.Error as exc:
        item.errors.append(f"row count failed: {exc}")

    if sample_rows <= 0:
        return item

    try:
        rows = conn.execute(
            f"SELECT * FROM {_quote_ident(name)} LIMIT ?", (sample_rows,)
        ).fetchall()
        for row in rows:
            item.sample_rows.append(
                {
                    key: _inventory_sample_value(key, value, db_role=db_role)
                    for key, value in dict(row).items()
                }
            )
    except sqlite3.Error as exc:
        item.errors.append(f"sample rows failed: {exc}")
    return item


def analyze_sqlite_database(
    path: str | os.PathLike[str] | Path,
    *,
    sample_rows: int = 3,
    canonical_target: str | os.PathLike[str] | Path | None = None,
) -> DatabaseInventory:
    db_path = Path(path).expanduser().resolve()
    stat = db_path.stat()
    fingerprint = _hash(f"{db_path}:{stat.st_size}:{stat.st_mtime_ns}")
    inventory = DatabaseInventory(
        path=str(db_path),
        project=_project_for_path(db_path),
        role=_database_role(
            db_path,
            canonical_target=Path(canonical_target).expanduser().resolve() if canonical_target else None,
        ),
        size_bytes=stat.st_size,
        mtime=stat.st_mtime,
        file_hash=fingerprint,
    )
    if stat.st_size == 0:
        inventory.errors.append("zero-byte sqlite file")
        return inventory
    if not _looks_like_sqlite(db_path):
        inventory.errors.append("not a sqlite database file")
        return inventory

    try:
        conn = _connect_readonly(db_path)
    except sqlite3.Error as exc:
        inventory.errors.append(f"open failed: {exc}")
        return inventory

    try:
        rows = conn.execute(
            """
            SELECT name, type, COALESCE(sql, '') AS sql
            FROM sqlite_master
            WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()
        for row in rows:
            item = _load_table_inventory(
                conn,
                name=row["name"],
                object_type=row["type"],
                sql=row["sql"],
                sample_rows=sample_rows,
                db_role=inventory.role,
            )
            inventory.tables.append(item)
            if item.object_type == "view":
                inventory.view_count += 1
            else:
                inventory.table_count += 1
        row_counts = [item.row_count for item in inventory.tables if item.row_count is not None]
        inventory.total_rows = sum(row_counts) if row_counts else 0
    except sqlite3.Error as exc:
        inventory.errors.append(f"sqlite_master scan failed: {exc}")
    finally:
        conn.close()
    return inventory


def analyze_sqlite_databases(
    paths: Iterable[str | os.PathLike[str] | Path],
    *,
    sample_rows: int = 3,
    canonical_target: str | os.PathLike[str] | Path | None = None,
) -> list[DatabaseInventory]:
    return [
        analyze_sqlite_database(path, sample_rows=sample_rows, canonical_target=canonical_target)
        for path in paths
    ]


def _doc_id(inv: DatabaseInventory) -> str:
    return f"doc_sqlite_{_hash(inv.path)}"


def _episode_id(inv: DatabaseInventory, suffix: str) -> str:
    return f"ep_sqlite_{_hash(inv.path + '::' + suffix)}"


def _atom_id(inv: DatabaseInventory, suffix: str) -> str:
    return f"at_sqlite_{_hash(inv.path + '::' + suffix)}"


def _evidence_id(inv: DatabaseInventory, suffix: str) -> str:
    return f"ev_sqlite_{_hash(inv.path + '::' + suffix)}"


def _database_summary_answer(inv: DatabaseInventory) -> str:
    lines = [
        f"Path: {inv.path}",
        f"Project: {inv.project}",
        f"Role: {inv.role}",
        f"Size bytes: {inv.size_bytes}",
        f"Table count: {inv.table_count}",
        f"View count: {inv.view_count}",
        f"Total rows: {inv.total_rows if inv.total_rows is not None else 'unknown'}",
    ]
    if inv.errors:
        lines.append(f"Errors: {'; '.join(inv.errors)}")
    if inv.tables:
        top_tables = sorted(
            inv.tables,
            key=lambda item: (item.row_count if item.row_count is not None else -1, item.name),
            reverse=True,
        )[:8]
        lines.append("Largest objects:")
        for item in top_tables:
            lines.append(
                f"- {item.object_type} {item.name}: rows={item.row_count if item.row_count is not None else 'unknown'}, columns={item.column_count}"
            )
    return "\n".join(lines)


def _table_summary_answer(inv: DatabaseInventory, table: TableInventory) -> str:
    column_bits = []
    for column in table.columns[:24]:
        bit = f"{column['name']}:{column['type'] or 'TEXT'}"
        if column.get("pk"):
            bit += " PK"
        column_bits.append(bit)
    lines = [
        f"Database: {inv.path}",
        f"Project: {inv.project}",
        f"Role: {inv.role}",
        f"Object: {table.object_type} {table.name}",
        f"Rows: {table.row_count if table.row_count is not None else 'unknown'}",
        f"Columns: {', '.join(column_bits) if column_bits else 'unknown'}",
    ]
    if table.sql:
        lines.append("DDL:")
        lines.append(_truncate(table.sql, limit=1200))
    if table.sample_rows:
        lines.append("Sample rows:")
        lines.append(json.dumps(table.sample_rows, ensure_ascii=False, indent=2, sort_keys=True))
    if table.errors:
        lines.append(f"Errors: {'; '.join(table.errors)}")
    return "\n".join(lines)


def ingest_sqlite_inventory(
    db: KnowledgeDB,
    inventories: Iterable[DatabaseInventory],
) -> SqliteInventoryIngestStats:
    stats = SqliteInventoryIngestStats()
    for inv in inventories:
        stats.analyzed += 1
        doc = Document(
            doc_id=_doc_id(inv),
            source="sqlite_inventory",
            project=inv.project,
            raw_ref=inv.path,
            title=Path(inv.path).name,
            created_at=inv.mtime,
            updated_at=inv.mtime,
            hash=inv.file_hash,
            meta_json=json.dumps(
                {
                    "role": inv.role,
                    "size_bytes": inv.size_bytes,
                    "table_count": inv.table_count,
                    "view_count": inv.view_count,
                    "total_rows": inv.total_rows,
                    "errors": inv.errors,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        db.put_document(doc)
        stats.ingested_documents += 1

        db_ep = Episode(
            episode_id=_episode_id(inv, "database"),
            doc_id=doc.doc_id,
            episode_type="sqlite_database",
            title=f"SQLite database inventory for {Path(inv.path).name}",
            summary=f"{inv.role} tables={inv.table_count} views={inv.view_count} rows={inv.total_rows}",
            start_ref=inv.path,
            end_ref=inv.path,
            time_start=inv.mtime,
            time_end=inv.mtime,
            source_ext=json.dumps(
                {
                    "role": inv.role,
                    "size_bytes": inv.size_bytes,
                    "errors": inv.errors,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        db.put_episode(db_ep)
        stats.ingested_episodes += 1

        db_atom = Atom(
            atom_id=_atom_id(inv, "database"),
            episode_id=db_ep.episode_id,
            atom_type="decision",
            question=f"What does SQLite database {inv.path} contain?",
            answer=_database_summary_answer(inv),
            canonical_question=f"sqlite database inventory: {inv.path}",
            intent="inventory",
            format="plain",
            applicability=json.dumps(
                {
                    "scope": "archive",
                    "project": inv.project,
                    "role": inv.role,
                    "path": inv.path,
                    "source": "sqlite_inventory",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            stability="versioned",
            status="candidate",
            valid_from=inv.mtime,
            promotion_status="staged",
            promotion_reason="sqlite_inventory",
        )
        db.put_atom(db_atom)
        stats.ingested_atoms += 1
        db.put_evidence(
            Evidence(
                evidence_id=_evidence_id(inv, "database"),
                atom_id=db_atom.atom_id,
                doc_id=doc.doc_id,
                span_ref=inv.path,
                excerpt=_truncate(_database_summary_answer(inv), limit=1600),
                excerpt_hash=_hash(_database_summary_answer(inv)),
                evidence_role="supports",
                weight=1.0,
            )
        )
        stats.ingested_evidence += 1

        for table in inv.tables:
            ep = Episode(
                episode_id=_episode_id(inv, table.name),
                doc_id=doc.doc_id,
                episode_type="sqlite_table",
                title=f"{table.object_type} {table.name}",
                summary=f"rows={table.row_count if table.row_count is not None else 'unknown'} cols={table.column_count}",
                start_ref=f"{inv.path}::{table.name}",
                end_ref=f"{inv.path}::{table.name}",
                time_start=inv.mtime,
                time_end=inv.mtime,
                source_ext=json.dumps(
                    {
                        "object_type": table.object_type,
                        "row_count": table.row_count,
                        "column_count": table.column_count,
                        "errors": table.errors,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
            db.put_episode(ep)
            stats.ingested_episodes += 1

            answer = _table_summary_answer(inv, table)
            atom = Atom(
                atom_id=_atom_id(inv, table.name),
                episode_id=ep.episode_id,
                atom_type="qa",
                question=f"What is the schema and content profile of {table.object_type} {table.name} in {inv.path}?",
                answer=answer,
                canonical_question=f"sqlite table inventory: {inv.path}::{table.name}",
                intent="inventory",
                format="plain",
                applicability=json.dumps(
                    {
                        "scope": "archive",
                        "project": inv.project,
                        "role": inv.role,
                        "path": inv.path,
                        "table": table.name,
                        "object_type": table.object_type,
                        "source": "sqlite_inventory",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                stability="versioned",
                status="candidate",
                valid_from=inv.mtime,
                promotion_status="staged",
                promotion_reason="sqlite_inventory",
            )
            db.put_atom(atom)
            stats.ingested_atoms += 1
            db.put_evidence(
                Evidence(
                    evidence_id=_evidence_id(inv, table.name),
                    atom_id=atom.atom_id,
                    doc_id=doc.doc_id,
                    span_ref=f"{inv.path}::{table.name}",
                    excerpt=_truncate(answer, limit=2000),
                    excerpt_hash=_hash(answer),
                    evidence_role="supports",
                    weight=1.0,
                )
            )
            stats.ingested_evidence += 1
    db.commit()
    return stats


def inventories_to_markdown(
    inventories: Iterable[DatabaseInventory],
    *,
    stats: SqliteInventoryIngestStats | None = None,
) -> str:
    inventories = list(inventories)
    lines = ["# SQLite Inventory Ingest Report", ""]
    if stats is not None:
        lines.extend(
            [
                "## Stats",
                "",
                f"- discovered: {stats.discovered}",
                f"- analyzed: {stats.analyzed}",
                f"- documents: {stats.ingested_documents}",
                f"- episodes: {stats.ingested_episodes}",
                f"- atoms: {stats.ingested_atoms}",
                f"- evidence: {stats.ingested_evidence}",
                f"- failures: {stats.failures}",
                "",
            ]
        )
    lines.extend(["## Databases", ""])
    for inv in inventories:
        lines.append(f"### {inv.path}")
        lines.append(f"- project: {inv.project}")
        lines.append(f"- role: {inv.role}")
        lines.append(f"- size_bytes: {inv.size_bytes}")
        lines.append(f"- tables: {inv.table_count}")
        lines.append(f"- views: {inv.view_count}")
        lines.append(f"- total_rows: {inv.total_rows}")
        if inv.errors:
            lines.append(f"- errors: {'; '.join(inv.errors)}")
        top_tables = sorted(
            inv.tables,
            key=lambda item: (item.row_count if item.row_count is not None else -1, item.name),
            reverse=True,
        )[:6]
        if top_tables:
            lines.append("- top_objects:")
            for item in top_tables:
                lines.append(
                    f"  - {item.object_type} {item.name}: rows={item.row_count if item.row_count is not None else 'unknown'}, columns={item.column_count}"
                )
        lines.append("")
    return "\n".join(lines).strip() + "\n"
