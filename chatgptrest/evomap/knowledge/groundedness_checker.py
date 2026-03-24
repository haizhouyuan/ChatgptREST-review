"""P2 Groundedness Checker — verify atoms against real system state.

Checks:
1. Path check: Do referenced file/directory paths actually exist?
2. Service check: Do referenced systemd units exist?
3. Staleness check: Has referenced source been modified since valid_from?

Reference: docs/2026-03-07_evomap_system_plan_and_current_state.md
GitHub: ChatgptREST #94
"""

from __future__ import annotations

import ast
import logging
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chatgptrest.evomap.knowledge.db import KnowledgeDB

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern extraction
# ---------------------------------------------------------------------------

# Match absolute paths like /vol1/..., /home/..., /etc/..., /usr/...
_PATH_RE = re.compile(
    r"(?:^|[\s\"'`(,\[])(/(?:vol1|home|etc|usr|var|tmp|opt)/"
    r"[A-Za-z0-9_./-]{3,120})",
    re.MULTILINE,
)

# Match relative Python-style paths like chatgptrest/foo/bar.py
_RELPATH_RE = re.compile(
    r"(?:^|[\s\"'`(,\[])("
    r"(?:chatgptrest|ops|tests|docs)/[A-Za-z0-9_./-]{3,100})",
    re.MULTILINE,
)

# Match systemd unit names like foo.service, bar.timer
_UNIT_RE = re.compile(
    r"\b([a-z][a-z0-9_-]{2,40}\.(?:service|timer))\b"
)

# Match tilde paths like ~/.gemini/...
_TILDE_RE = re.compile(
    r"(?:^|[\s\"'`(,\[])(~/[A-Za-z0-9_./-]{3,120})",
    re.MULTILINE,
)

# Match Python class/function references: ClassName, function_name, module.ClassName
_PY_SYMBOL_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9_]*|[a-z_][a-zA-Z0-9_]*)\b"
)

# Match qualified Python names like chatgptrest.kernel.router.RouteMatcher
_QUALIFIED_NAME_RE = re.compile(
    r"([a-z][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+)"
)


def extract_paths(text: str) -> list[str]:
    """Extract file/directory paths from text."""
    paths = set()
    for m in _PATH_RE.finditer(text):
        p = m.group(1).rstrip(".,;:)]\"'`")
        paths.add(p)
    for m in _TILDE_RE.finditer(text):
        p = m.group(1).rstrip(".,;:)]\"'`")
        paths.add(os.path.expanduser(p))
    return sorted(paths)


def _resolve_project_root(base: str | None = None) -> Path:
    """Resolve the project root for code symbol and relative path checks."""
    candidate = base or os.environ.get("EVOMAP_PROJECT_ROOT")
    if candidate:
        return Path(candidate).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _resolve_project_package_dir(base: str | None = None) -> Path:
    """Resolve the chatgptrest package directory under the configured project root."""
    project_root = _resolve_project_root(base)
    package_dir = project_root / "chatgptrest"
    if package_dir.is_dir():
        return package_dir
    return project_root


def extract_relpaths(text: str, base: str | None = None) -> list[str]:
    """Extract relative project paths and resolve them."""
    project_root = _resolve_project_root(base)
    paths = set()
    for m in _RELPATH_RE.finditer(text):
        rel = m.group(1).rstrip(".,;:)]\"'`")
        paths.add(str(project_root / rel))
    return sorted(paths)


def extract_units(text: str) -> list[str]:
    """Extract systemd unit names from text."""
    return sorted(set(m.group(1) for m in _UNIT_RE.finditer(text)))


_COMMON_WORDS = {
    "the", "and", "or", "not", "for", "while", "class", "import", "from",
    "return", "raise", "self", "true", "false", "none", "def", "if", "else",
    "elif", "try", "except", "finally", "with", "as", "pass", "break", "continue",
    "lambda", "yield", "global", "nonlocal", "assert", "del", "in", "is", "print",
    "use", "used", "using", "contains", "which", "that", "this", "these", "those",
    "will", "would", "could", "should", "have", "has", "had", "been", "being",
    "vol1", "projects", "chatgptrest", "evomap", "knowledge", "test", "answer",
}


def _looks_like_code_symbol(token: str) -> bool:
    """Heuristic filter for likely Python symbol names."""
    if len(token) < 3 or token.lower() in _COMMON_WORDS:
        return False
    if "_" in token:
        return True
    if token[0].isupper():
        return any(ch.isupper() for ch in token[1:]) or any(ch.isdigit() for ch in token[1:])
    return False


def extract_code_symbols(text: str) -> list[str]:
    """Extract potential Python class/function names from text."""
    symbols = set()

    for m in _QUALIFIED_NAME_RE.finditer(text):
        parts = m.group(1).split(".")
        for part in parts:
            if _looks_like_code_symbol(part):
                symbols.add(part)

    for m in _PY_SYMBOL_RE.finditer(text):
        s = m.group(1)
        if _looks_like_code_symbol(s):
            symbols.add(s)

    return sorted(symbols)


def _get_project_files(base: str | None = None) -> list[str]:
    """Get all Python files in the project."""
    package_dir = _resolve_project_package_dir(base)
    py_files = []
    for root, _, files in os.walk(package_dir):
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return py_files


def check_code_symbols(symbols: list[str], base: str | None = None) -> tuple[float, list[str]]:
    """Check if referenced Python symbols exist in codebase. Returns (score, evidence)."""
    if not symbols:
        return 1.0, ["no_code_symbols_referenced"]

    project_root = _resolve_project_root(base)
    project_dir = _resolve_project_package_dir(base)
    if not project_dir.is_dir():
        return 0.0, [f"project_dir_not_found: {project_dir}"]

    found_symbols: set[str] = set()
    defined_in: dict[str, str] = {}

    for py_file in _get_project_files(str(project_dir)):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content, filename=py_file)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    found_symbols.add(node.name)
                    defined_in[node.name] = os.path.relpath(py_file, project_root)
                elif isinstance(node, ast.FunctionDef):
                    found_symbols.add(node.name)
                    defined_in[node.name] = os.path.relpath(py_file, project_root)
                elif isinstance(node, ast.AsyncFunctionDef):
                    found_symbols.add(node.name)
                    defined_in[node.name] = os.path.relpath(py_file, project_root)
        except Exception:
            pass

    matched = 0
    evidence = []
    for sym in symbols:
        if sym in found_symbols:
            matched += 1
            loc = defined_in.get(sym, "unknown")
            evidence.append(f"✓ {sym} ({loc})")
        else:
            evidence.append(f"✗ {sym}")

    score = matched / len(symbols) if symbols else 1.0
    return score, evidence


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def check_paths_exist(paths: list[str]) -> tuple[float, list[str]]:
    """Check if paths exist on disk. Returns (score, evidence)."""
    if not paths:
        return 1.0, ["no_paths_referenced"]

    found = 0
    evidence = []
    for p in paths:
        if os.path.exists(p):
            found += 1
            evidence.append(f"✓ {p}")
        else:
            evidence.append(f"✗ {p}")

    score = found / len(paths) if paths else 1.0
    return score, evidence


def check_units_exist(units: list[str]) -> tuple[float, list[str]]:
    """Check if systemd units exist. Returns (score, evidence)."""
    if not units:
        return 1.0, ["no_units_referenced"]

    found = 0
    evidence = []
    for unit in units:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "list-unit-files", unit],
                capture_output=True, text=True, timeout=5,
            )
            if unit in result.stdout:
                found += 1
                evidence.append(f"✓ {unit}")
            else:
                # Also check system-level
                result2 = subprocess.run(
                    ["systemctl", "list-unit-files", unit],
                    capture_output=True, text=True, timeout=5,
                )
                if unit in result2.stdout:
                    found += 1
                    evidence.append(f"✓ {unit} (system)")
                else:
                    evidence.append(f"✗ {unit}")
        except Exception:
            evidence.append(f"? {unit} (check failed)")

    score = found / len(units) if units else 1.0
    return score, evidence


def check_staleness(paths: list[str], valid_from: float) -> tuple[float, list[str]]:
    """Check if source files modified since atom's valid_from. Returns (score, evidence)."""
    if not paths or valid_from <= 0:
        return 1.0, ["no_staleness_check_needed"]

    checked = 0
    stale = 0
    evidence = []
    for p in paths:
        if os.path.isfile(p):
            try:
                mtime = os.path.getmtime(p)
                checked += 1
                if mtime > valid_from:
                    stale += 1
                    evidence.append(f"⚠ {p} modified after atom creation")
                else:
                    evidence.append(f"✓ {p} unchanged")
            except OSError:
                pass

    if checked == 0:
        return 1.0, ["no_checkable_files"]

    # If many files changed, knowledge may be stale
    score = 1.0 - (stale / checked * 0.5)  # penalize but don't zero out
    return max(0.0, score), evidence


# ---------------------------------------------------------------------------
# Groundedness result
# ---------------------------------------------------------------------------

@dataclass
class GroundednessResult:
    atom_id: str
    path_score: float = 1.0
    service_score: float = 1.0
    staleness_score: float = 1.0
    code_symbol_score: float = 1.0
    overall: float = 1.0
    evidence: list[str] = field(default_factory=list)
    paths_checked: int = 0
    units_checked: int = 0
    code_symbols_checked: int = 0


@dataclass
class P2Stats:
    total: int = 0
    checked: int = 0
    high: int = 0        # ≥ 0.7
    medium: int = 0      # 0.5-0.7
    low: int = 0         # < 0.5
    demoted: int = 0
    elapsed_ms: float = 0.0


@dataclass
class GroundednessAuditRecord:
    audit_id: str = field(default_factory=lambda: f"ga_{uuid.uuid4().hex[:12]}")
    atom_id: str = ""
    timestamp: float = field(default_factory=time.time)
    passed: bool = False
    overall_score: float = 0.0
    path_score: float = 0.0
    service_score: float = 0.0
    staleness_score: float = 0.0
    code_symbol_score: float = 0.0
    evidence_json: str = "[]"

    def to_row(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "atom_id": self.atom_id,
            "timestamp": self.timestamp,
            "passed": 1 if self.passed else 0,
            "overall_score": self.overall_score,
            "path_score": self.path_score,
            "service_score": self.service_score,
            "staleness_score": self.staleness_score,
            "code_symbol_score": self.code_symbol_score,
            "evidence_json": self.evidence_json,
        }


def check_atom_groundedness(
    atom_id: str,
    answer: str,
    valid_from: float,
) -> GroundednessResult:
    """Run all groundedness checks on a single atom."""
    result = GroundednessResult(atom_id=atom_id)

    abs_paths = extract_paths(answer)
    rel_paths = extract_relpaths(answer)
    all_paths = sorted(set(abs_paths + rel_paths))
    units = extract_units(answer)
    code_symbols = extract_code_symbols(answer)

    result.paths_checked = len(all_paths)
    result.units_checked = len(units)
    result.code_symbols_checked = len(code_symbols)

    result.path_score, path_ev = check_paths_exist(all_paths)
    result.service_score, unit_ev = check_units_exist(units)
    result.staleness_score, stale_ev = check_staleness(all_paths, valid_from)
    result.code_symbol_score, code_ev = check_code_symbols(code_symbols)

    result.evidence = path_ev + unit_ev + stale_ev + code_ev

    weights = {
        "path": 0.4 if all_paths else 0.0,
        "service": 0.2 if units else 0.0,
        "staleness": 0.15 if all_paths and valid_from > 0 else 0.0,
        "code_symbol": 0.25 if code_symbols else 0.0,
    }
    total_w = sum(weights.values())
    if total_w > 0:
        result.overall = (
            weights["path"] * result.path_score
            + weights["service"] * result.service_score
            + weights["staleness"] * result.staleness_score
            + weights["code_symbol"] * result.code_symbol_score
        ) / total_w
    else:
        result.overall = 1.0

    return result


def enforce_promotion_gate(
    db: KnowledgeDB,
    atom_id: str,
    threshold: float = 0.7,
    *,
    commit: bool = True,
) -> tuple[bool, GroundednessAuditRecord]:
    """Enforce groundedness gate before promotion to active.

    Runs check_atom_groundedness() and either:
    - Returns (True, audit_record) if groundedness passes (>= threshold)
    - Returns (False, audit_record) if groundedness fails

    The audit record is written to the groundedness_audit table.
    """
    import json
    conn = db.connect()

    row = conn.execute(
        "SELECT answer, valid_from FROM atoms WHERE atom_id = ?",
        (atom_id,),
    ).fetchone()

    if not row:
        record = GroundednessAuditRecord(
            atom_id=atom_id,
            passed=False,
            evidence_json=json.dumps(["atom_not_found"]),
        )
        return False, record

    answer, valid_from = row[0], row[1]

    result = check_atom_groundedness(atom_id, answer, valid_from)

    passed = result.overall >= threshold

    record = GroundednessAuditRecord(
        atom_id=atom_id,
        passed=passed,
        overall_score=result.overall,
        path_score=result.path_score,
        service_score=result.service_score,
        staleness_score=result.staleness_score,
        code_symbol_score=result.code_symbol_score,
        evidence_json=json.dumps(result.evidence),
    )

    conn.execute(
        """INSERT OR REPLACE INTO groundedness_audit
           (audit_id, atom_id, timestamp, passed, overall_score,
            path_score, service_score, staleness_score, code_symbol_score, evidence_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.audit_id, record.atom_id, record.timestamp,
            1 if record.passed else 0, record.overall_score,
            record.path_score, record.service_score, record.staleness_score,
            record.code_symbol_score, record.evidence_json,
        ),
    )
    if commit:
        conn.commit()

    return passed, record


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_p2_groundedness(db: KnowledgeDB) -> P2Stats:
    """Run P2 groundedness checks on atoms that may become runtime-visible."""
    conn = db.connect()
    stats = P2Stats()
    t0 = time.time()

    rows = conn.execute(
        "SELECT atom_id, answer, valid_from FROM atoms "
        "WHERE promotion_status IN ('candidate', 'staged')"
    ).fetchall()
    stats.total = len(rows)

    updates = []
    demotions = []

    for row in rows:
        atom_id, answer, valid_from = row[0], row[1], row[2]
        result = check_atom_groundedness(atom_id, answer, valid_from)
        stats.checked += 1

        if result.overall >= 0.7:
            stats.high += 1
        elif result.overall >= 0.5:
            stats.medium += 1
        else:
            stats.low += 1
            demotions.append((atom_id, result.overall))

        # Update groundedness score in DB
        updates.append((result.overall, atom_id))

    # Apply updates
    if updates:
        conn.executemany(
            "UPDATE atoms SET groundedness = ? WHERE atom_id = ?",
            updates,
        )

    # Demote low-scoring atoms
    if demotions:
        for atom_id, score in demotions:
            conn.execute(
                "UPDATE atoms SET promotion_status = 'staged', "
                "promotion_reason = 'low_groundedness' "
                "WHERE atom_id = ?",
                (atom_id,),
            )
        stats.demoted = len(demotions)

    conn.commit()

    stats.elapsed_ms = (time.time() - t0) * 1000
    logger.info(
        "P2 groundedness: total=%d, checked=%d, high=%d, medium=%d, "
        "low=%d, demoted=%d (%.0fms)",
        stats.total, stats.checked, stats.high, stats.medium,
        stats.low, stats.demoted, stats.elapsed_ms,
    )
    return stats
