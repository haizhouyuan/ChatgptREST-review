#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.advisor.crystallized_learning import (  # noqa: E402
    CRYSTALLIZED_LEARNING_INVALIDATION_SLA,
    CRYSTALLIZED_LEARNING_PROJECTION_MODE,
    INTERACTION_LEARNING_MIN_SUPPORT,
    build_interaction_learning_crystal,
    crystallized_learning_receipt,
)


def _default_memory_db() -> Path:
    raw = os.environ.get("OPENMIND_MEMORY_DB", "").strip() or "~/.openmind/memory.db"
    return Path(raw).expanduser()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _load_learning_payloads(db_path: str | Path) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    rows = conn.execute(
        """
        select record_id, key, value, updated_at, account_id, thread_id, project_id
        from memory_records
        where category='user_correction'
        order by updated_at desc
        """
    ).fetchall()
    latest_by_key: dict[str, sqlite3.Row] = {}
    for row in rows:
        key = str(row["key"] or "").strip()
        if key and key not in latest_by_key:
            latest_by_key[key] = row
    payloads: list[dict[str, Any]] = []
    for row in latest_by_key.values():
        value = json.loads(str(row["value"] or "{}"))
        value["record_id"] = str(row["record_id"] or "")
        value["key"] = str(row["key"] or "")
        value.setdefault("account_id", str(row["account_id"] or ""))
        value.setdefault("thread_id", str(row["thread_id"] or ""))
        value.setdefault("project_id", str(row["project_id"] or ""))
        value["_updated_at"] = str(row["updated_at"] or "")
        payloads.append(value)
    conn.close()
    return payloads


def _min_winner_margin(crystal: dict[str, Any]) -> int:
    support = dict(crystal.get("support") or {})
    margins = [int(dict(item).get("winner_margin") or 0) for item in support.values()]
    return min(margins) if margins else 0


def _risk_posture(crystal: dict[str, Any]) -> str:
    receipt = crystallized_learning_receipt(crystal)
    governance = dict(crystal.get("governance") or {})
    denied_count = len(list(governance.get("denied_preference_keys") or []))
    margin = _min_winner_margin(crystal)
    if denied_count > 0 or margin <= 0:
        return "high"
    if margin == 1:
        return "medium"
    return "low"


def build_crystallized_learning_governance_report(
    *,
    db_path: str | Path,
    sample_size: int = 10,
) -> dict[str, Any]:
    payloads = _load_learning_payloads(db_path)
    crystals: list[dict[str, Any]] = []
    for payload in payloads:
        crystal = build_interaction_learning_crystal(payload)
        if crystal is not None:
            crystals.append(crystal)

    active_by_key: dict[str, int] = {}
    total_superseded = 0
    total_denied = 0
    medium_or_higher = 0
    samples: list[dict[str, Any]] = []
    for crystal in crystals:
        stable_preferences = dict(crystal.get("stable_preferences") or {})
        governance = dict(crystal.get("governance") or {})
        supersession = dict(crystal.get("supersession") or {})
        receipt = crystallized_learning_receipt(crystal)
        risk = _risk_posture(crystal)
        if risk in {"medium", "high"}:
            medium_or_higher += 1
        total_superseded += int(supersession.get("superseded_count") or 0)
        denied_keys = list(governance.get("denied_preference_keys") or [])
        total_denied += len(denied_keys)
        for key in stable_preferences:
            active_by_key[key] = active_by_key.get(key, 0) + 1
        samples.append(
            {
                "crystal_id": str(crystal.get("crystal_id") or "").strip(),
                "source_key": str(crystal.get("source_key") or "").strip(),
                "project_id": str(dict(crystal.get("scope") or {}).get("project_id") or "").strip(),
                "stable_preferences": stable_preferences,
                "support": dict(crystal.get("support") or {}),
                "projection_mode": str(receipt.get("projection_mode") or "").strip(),
                "superseded_count": int(receipt.get("superseded_count") or 0),
                "denied_preference_keys": denied_keys,
                "winner_margin_min": _min_winner_margin(crystal),
                "risk_posture": risk,
            }
        )
    samples.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(str(item.get("risk_posture") or ""), 9),
            int(item.get("winner_margin_min") or 0),
            -int(item.get("superseded_count") or 0),
            str(item.get("source_key") or ""),
        )
    )
    sample_rows = samples[: max(1, int(sample_size or 1))] if samples else []
    reviewed_count = len(sample_rows)
    false_positive_count = sum(1 for item in sample_rows if str(item.get("risk_posture") or "") == "high")
    return {
        "memory_db": str(db_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "projection_mode": CRYSTALLIZED_LEARNING_PROJECTION_MODE,
        "support_threshold": INTERACTION_LEARNING_MIN_SUPPORT,
        "invalidation_sla": CRYSTALLIZED_LEARNING_INVALIDATION_SLA,
        "records_scanned": len(payloads),
        "crystal_generation": {
            "active_crystal_count": len(crystals),
            "no_crystal_record_count": max(0, len(payloads) - len(crystals)),
            "shadow_projection_count": len(crystals),
            "shadow_projection_ratio": round(len(crystals) / len(payloads), 6) if payloads else 0.0,
        },
        "governance": {
            "active_crystals_by_key": active_by_key,
            "superseded_candidate_count": total_superseded,
            "denied_preference_occurrences": total_denied,
            "medium_or_higher_risk_crystal_count": medium_or_higher,
        },
        "manual_review": {
            "sample_size": reviewed_count,
            "false_positive_count": false_positive_count,
            "false_positive_rate": round(false_positive_count / reviewed_count, 6) if reviewed_count else 0.0,
            "notes": (
                "No active crystals found in the scanned memory DB."
                if not sample_rows
                else "Flagged high-risk samples require shadow-only handling before wider reuse."
            ),
        },
        "samples": sample_rows,
    }


def write_crystallized_learning_governance_artifacts(
    summary: dict[str, Any],
    output_dir: str | Path,
    stamp: str,
) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / f"crystallized_learning_governance_{stamp}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_path = out / f"crystallized_learning_governance_{stamp}.md"
    report_lines = [
        "# Crystallized Learning Governance Report",
        "",
        f"- `memory_db`: `{summary['memory_db']}`",
        f"- `projection_mode`: `{summary['projection_mode']}`",
        f"- `support_threshold`: `{summary['support_threshold']}`",
        f"- `invalidation_sla`: `{summary['invalidation_sla']}`",
        f"- `records_scanned`: `{summary['records_scanned']}`",
        f"- `active_crystal_count`: `{summary['crystal_generation']['active_crystal_count']}`",
        f"- `shadow_projection_ratio`: `{summary['crystal_generation']['shadow_projection_ratio']}`",
        f"- `superseded_candidate_count`: `{summary['governance']['superseded_candidate_count']}`",
        f"- `denied_preference_occurrences`: `{summary['governance']['denied_preference_occurrences']}`",
        f"- `manual_review_false_positive_rate`: `{summary['manual_review']['false_positive_rate']}`",
        "",
        "## Active crystals by key",
        "",
    ]
    if summary["governance"]["active_crystals_by_key"]:
        for key, count in sorted(summary["governance"]["active_crystals_by_key"].items()):
            report_lines.append(f"- `{key}`: `{count}`")
    else:
        report_lines.append("- none")
    report_lines.extend(["", "## Notes", "", f"- {summary['manual_review']['notes']}"])
    report_path.write_text("\n".join(report_lines).strip() + "\n", encoding="utf-8")

    sample_path = out / f"crystallized_learning_manual_review_{stamp}.md"
    sample_lines = [
        "# Crystallized Learning Manual Review Sample",
        "",
        f"- sample_size: `{summary['manual_review']['sample_size']}`",
        f"- false_positive_count: `{summary['manual_review']['false_positive_count']}`",
        f"- false_positive_rate: `{summary['manual_review']['false_positive_rate']}`",
        "",
    ]
    if not summary["samples"]:
        sample_lines.append("- No active crystals found in the scanned memory DB.")
    else:
        for sample in summary["samples"]:
            sample_lines.extend(
                [
                    f"## {sample['crystal_id'] or sample['source_key']}",
                    "",
                    f"- `source_key`: `{sample['source_key']}`",
                    f"- `project_id`: `{sample['project_id']}`",
                    f"- `projection_mode`: `{sample['projection_mode']}`",
                    f"- `risk_posture`: `{sample['risk_posture']}`",
                    f"- `winner_margin_min`: `{sample['winner_margin_min']}`",
                    f"- `superseded_count`: `{sample['superseded_count']}`",
                    f"- `stable_preferences`: `{json.dumps(sample['stable_preferences'], ensure_ascii=False, sort_keys=True)}`",
                    f"- `denied_preference_keys`: `{json.dumps(sample['denied_preference_keys'], ensure_ascii=False)}`",
                    "",
                ]
            )
    sample_path.write_text("\n".join(sample_lines).strip() + "\n", encoding="utf-8")
    return [summary_path, report_path, sample_path]


def main() -> int:
    parser = argparse.ArgumentParser(description="Report crystallized-learning governance state.")
    parser.add_argument("--memory-db", default=str(_default_memory_db()), help="Path to OPENMIND memory DB")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "artifacts" / "monitor" / "crystallized_learning_governance"),
        help="Directory to write governance artifacts",
    )
    parser.add_argument("--stamp", default="", help="Artifact stamp override (UTC-like token)")
    parser.add_argument("--sample-size", type=int, default=10, help="Number of manual-review samples to include")
    args = parser.parse_args()

    summary = build_crystallized_learning_governance_report(
        db_path=args.memory_db,
        sample_size=max(1, int(args.sample_size or 1)),
    )
    stamp = args.stamp.strip() or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    written = write_crystallized_learning_governance_artifacts(summary, args.output_dir, stamp)
    print(json.dumps({"ok": True, "artifacts": [str(path) for path in written]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
