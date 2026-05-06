#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_reviewed_runtime_pack"


def _latest_pack(pack_root: Path) -> Path | None:
    if not pack_root.exists():
        return None
    candidates = sorted([p for p in pack_root.iterdir() if p.is_dir()])
    return candidates[-1] if candidates else None


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def build_samples(*, pack_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    pack = Path(pack_dir)
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    docs = _read_tsv(pack / "docs.tsv")
    atoms = _read_tsv(pack / "atoms.tsv")
    sample_doc = docs[0] if docs else {}
    sample_atom = atoms[0] if atoms else {}
    pack_version = pack.name

    events = [
        {
            "event_type": "planning.runtime_pack.activated",
            "ts": datetime.now(timezone.utc).isoformat(),
            "pack_version": pack_version,
            "pack_type": manifest["pack_type"],
            "scope": manifest["scope"],
        },
        {
            "event_type": "planning.runtime_pack.query",
            "ts": datetime.now(timezone.utc).isoformat(),
            "pack_version": pack_version,
            "query": "104 模组量产导入计划",
            "source": "explicit_planning_pack",
        },
        {
            "event_type": "planning.runtime_pack.hit",
            "ts": datetime.now(timezone.utc).isoformat(),
            "pack_version": pack_version,
            "doc_id": sample_doc.get("doc_id", ""),
            "atom_id": sample_atom.get("atom_id", ""),
            "review_domain": sample_doc.get("review_domain", ""),
            "source_bucket": sample_doc.get("source_bucket", ""),
        },
        {
            "event_type": "planning.runtime_pack.feedback",
            "ts": datetime.now(timezone.utc).isoformat(),
            "pack_version": pack_version,
            "doc_id": sample_doc.get("doc_id", ""),
            "atom_id": sample_atom.get("atom_id", ""),
            "feedback": "accepted",
        },
        {
            "event_type": "planning.runtime_pack.rollback",
            "ts": datetime.now(timezone.utc).isoformat(),
            "from_pack_version": pack_version,
            "to_pack_version": "PREVIOUS_APPROVED_PACK",
            "reason": "quality_regression_or_incident",
        },
    ]

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "usage_event_samples.jsonl").open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    (out / "event_schema.json").write_text(
        json.dumps(
            {
                "event_types": [event["event_type"] for event in events],
                "pack_version_field": "pack_version",
                "identity_fields": ["doc_id", "atom_id"],
                "source_label": "explicit_planning_pack",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "incident_template.md").write_text(
        "\n".join(
            [
                "# Planning Runtime Pack Incident Template",
                "",
                "- pack_version:",
                "- query:",
                "- doc_id:",
                "- atom_id:",
                "- symptom:",
                "- rollback_needed:",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "output_dir": str(out),
        "sample_event_count": len(events),
        "files": [
            str(out / "usage_event_samples.jsonl"),
            str(out / "event_schema.json"),
            str(out / "incident_template.md"),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build offline usage evidence / observability samples for the planning reviewed runtime pack.")
    parser.add_argument("--pack-dir", default="")
    parser.add_argument("--pack-root", default=str(DEFAULT_PACK_ROOT))
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()
    pack_dir = Path(args.pack_dir) if args.pack_dir else _latest_pack(Path(args.pack_root))
    if pack_dir is None or not pack_dir.exists():
        raise SystemExit("No planning reviewed runtime pack found. Pass --pack-dir explicitly.")
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else REPO_ROOT / "artifacts" / "monitor" / "planning_runtime_pack_observability_samples" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    print(json.dumps(build_samples(pack_dir=pack_dir, output_dir=output_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
