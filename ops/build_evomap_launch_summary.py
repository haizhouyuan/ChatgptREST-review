#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.planning_runtime_pack_search import resolve_ready_planning_runtime_pack_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "evomap_launch_summary"
DEFAULT_SMOKE_ROOT = REPO_ROOT / "artifacts" / "monitor" / "evomap_launch_smoke"


def _request_json(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "http_status": int(exc.code),
            "error": exc.read().decode("utf-8", errors="replace"),
        }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def _latest_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = sorted(path for path in root.iterdir() if path.is_dir())
    return candidates[-1] if candidates else None


def _query_rows(db_path: str | Path, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _scalar(db_path: str | Path, sql: str, params: tuple[Any, ...] = ()) -> int:
    rows = _query_rows(db_path, sql, params)
    if not rows:
        return 0
    first = rows[0]
    return int(next(iter(first.values())) or 0)


def collect_runtime_health(base_url: str) -> dict[str, Any]:
    result: dict[str, Any] = {"base_url": base_url, "cognitive": {}, "advisor": {}, "ok": False}
    try:
        result["cognitive"] = _request_json(f"{base_url.rstrip('/')}/v2/cognitive/health")
        result["advisor"] = _request_json(f"{base_url.rstrip('/')}/v2/advisor/health")
        result["ok"] = bool(result["cognitive"].get("ok")) and str(result["advisor"].get("status") or "") == "ok"
    except urllib.error.URLError as exc:
        result["error"] = str(exc)
    return result


def collect_canonical_db_stats(db_path: str | Path) -> dict[str, Any]:
    docs_total = _scalar(db_path, "SELECT COUNT(*) FROM documents")
    atoms_total = _scalar(db_path, "SELECT COUNT(*) FROM atoms")
    docs_by_source = _query_rows(
        db_path,
        "SELECT source, COUNT(*) AS count FROM documents GROUP BY source ORDER BY count DESC LIMIT 20",
    )
    atoms_by_promotion = _query_rows(
        db_path,
        "SELECT promotion_status, COUNT(*) AS count FROM atoms GROUP BY promotion_status ORDER BY count DESC",
    )
    planning_by_promotion = _query_rows(
        db_path,
        """
        SELECT a.promotion_status, COUNT(*) AS count
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE d.source = 'planning'
        GROUP BY a.promotion_status
        ORDER BY count DESC
        """,
    )
    activity_by_promotion = _query_rows(
        db_path,
        """
        SELECT promotion_status, COUNT(*) AS count
        FROM atoms
        WHERE canonical_question LIKE 'activity:%'
        GROUP BY promotion_status
        ORDER BY count DESC
        """,
    )
    return {
        "db_path": str(db_path),
        "docs_total": docs_total,
        "atoms_total": atoms_total,
        "docs_by_source": docs_by_source,
        "atoms_by_promotion": atoms_by_promotion,
        "planning_by_promotion": planning_by_promotion,
        "activity_by_promotion": activity_by_promotion,
    }


def collect_planning_runtime_pack_status() -> dict[str, Any]:
    bundle_dir = resolve_ready_planning_runtime_pack_bundle()
    if bundle_dir is None:
        return {
            "ready": False,
            "bundle_dir": "",
            "pack_dir": "",
            "release_checks": {},
            "rollback_runbook": "",
        }

    manifest = _read_json(bundle_dir / "release_bundle_manifest.json")
    pack_dir = Path(str(manifest.get("pack_dir") or ""))
    rollback_runbook = bundle_dir / "rollback_runbook.md"
    return {
        "ready": bool(manifest.get("ready_for_explicit_consumption", False)),
        "bundle_dir": str(bundle_dir),
        "pack_dir": str(pack_dir),
        "release_checks": dict(manifest.get("checks") or {}),
        "scope": dict(manifest.get("scope") or {}),
        "validation_summary": dict(manifest.get("validation_summary") or {}),
        "sensitivity_summary": dict(manifest.get("sensitivity_summary") or {}),
        "observability_summary": dict(manifest.get("observability_summary") or {}),
        "rollback_runbook": str(rollback_runbook),
        "opt_in_contract": {
            "source_scope": ["planning_review"],
            "planning_mode": True,
            "default_retrieval_unchanged": True,
        },
    }


def collect_issue_domain_status(base_url: str) -> dict[str, Any]:
    try:
        body = _request_json(f"{base_url.rstrip('/')}/v1/issues/canonical/export?limit=5")
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc)}
    summary = body.get("summary") if isinstance(body.get("summary"), dict) else {}
    return {
        "ok": bool(body.get("ok")),
        "read_plane": str(summary.get("read_plane") or ""),
        "object_count": int(summary.get("object_count") or 0),
        "canonical_issue_count": int(summary.get("canonical_issue_count") or 0),
        "coverage_gap_count": int(summary.get("coverage_gap_count") or 0),
    }


def collect_latest_smoke(smoke_root: Path) -> dict[str, Any] | None:
    latest = _latest_dir(smoke_root)
    if latest is None:
        return None
    report_path = latest / "launch_smoke.json"
    if not report_path.exists():
        return None
    payload = _read_json(report_path)
    payload["report_path"] = str(report_path)
    return payload


def build_summary(*, base_url: str, db_path: str | Path, smoke_root: Path = DEFAULT_SMOKE_ROOT, output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    runtime = collect_runtime_health(base_url)
    canonical_db = collect_canonical_db_stats(db_path)
    planning_pack = collect_planning_runtime_pack_status()
    issue_domain = collect_issue_domain_status(base_url)
    latest_smoke = collect_latest_smoke(smoke_root)

    summary = {
        "generated_at": time.time(),
        "runtime": runtime,
        "canonical_db": canonical_db,
        "planning_runtime_pack": planning_pack,
        "issue_domain": issue_domain,
        "latest_smoke": latest_smoke,
        "launch_flags": {
            "default_retrieval_unchanged": True,
            "planning_review_opt_in_available": planning_pack["ready"],
            "active_knowledge_auto_promotion": False,
            "execution_experience_stays_review_plane": True,
        },
        "rollback": {
            "disable_planning_opt_in": "stop sending source_scope=['planning_review'] or planning_mode=true",
            "clear_bundle_pointer": "unset CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR or point to previous approved bundle",
            "rollback_runbook": planning_pack.get("rollback_runbook", ""),
        },
    }
    (out / "launch_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest_smoke_ok = bool((latest_smoke or {}).get("ok", False)) if latest_smoke else False
    (out / "launch_summary.md").write_text(
        "\n".join(
            [
                "# EvoMap Launch Summary",
                "",
                f"- runtime_ok: `{runtime.get('ok', False)}`",
                f"- canonical_db: `{canonical_db['db_path']}`",
                f"- docs_total: `{canonical_db['docs_total']}`",
                f"- atoms_total: `{canonical_db['atoms_total']}`",
                f"- planning_pack_ready: `{planning_pack['ready']}`",
                f"- issue_domain_ok: `{issue_domain.get('ok', False)}`",
                f"- latest_smoke_ok: `{latest_smoke_ok}`",
                "",
                "## Launch Flags",
                "",
                f"- default_retrieval_unchanged: `{summary['launch_flags']['default_retrieval_unchanged']}`",
                f"- planning_review_opt_in_available: `{summary['launch_flags']['planning_review_opt_in_available']}`",
                f"- active_knowledge_auto_promotion: `{summary['launch_flags']['active_knowledge_auto_promotion']}`",
                f"- execution_experience_stays_review_plane: `{summary['launch_flags']['execution_experience_stays_review_plane']}`",
                "",
                "## Rollback",
                "",
                f"- disable_planning_opt_in: `{summary['rollback']['disable_planning_opt_in']}`",
                f"- clear_bundle_pointer: `{summary['rollback']['clear_bundle_pointer']}`",
                f"- rollback_runbook: `{summary['rollback']['rollback_runbook']}`",
                "",
                "## Runtime Health",
                "",
                f"- cognitive_runtime_ready: `{bool((runtime.get('cognitive') or {}).get('runtime_ready', False))}`",
                f"- advisor_auth_mode: `{str(((runtime.get('advisor') or {}).get('subsystems') or {}).get('auth', {}).get('mode', ''))}`",
                "",
                "## Issue Domain",
                "",
                f"- read_plane: `{issue_domain.get('read_plane', '')}`",
                f"- canonical_issue_count: `{issue_domain.get('canonical_issue_count', 0)}`",
                f"- coverage_gap_count: `{issue_domain.get('coverage_gap_count', 0)}`",
                "",
                "## Planning Runtime Pack",
                "",
                f"- bundle_dir: `{planning_pack.get('bundle_dir', '')}`",
                f"- pack_dir: `{planning_pack.get('pack_dir', '')}`",
                f"- unresolved_flagged_atoms: `{int((planning_pack.get('sensitivity_summary') or {}).get('unresolved_flagged_atoms', 0))}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "output_dir": str(out),
        "summary_path": str(out / "launch_summary.json"),
        "markdown_path": str(out / "launch_summary.md"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build operator-facing EvoMap launch summary artifacts.")
    parser.add_argument("--base-url", default="http://127.0.0.1:18711")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--smoke-root", default=str(DEFAULT_SMOKE_ROOT))
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else DEFAULT_OUTPUT_ROOT / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    )
    result = build_summary(
        base_url=args.base_url,
        db_path=args.db,
        smoke_root=Path(args.smoke_root),
        output_dir=output_dir,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
