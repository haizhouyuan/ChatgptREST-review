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
DEFAULT_REVIEW_SPEC_PATH = REPO_ROOT / "ops" / "data" / "planning_runtime_pack_sensitivity_review_v1.json"

SENSITIVE_TOKENS = [
    "受控资料",
    "薪酬",
    "绩效",
    "面试",
    "身份证",
    "手机号",
    "电话",
    "合同",
    "脱敏",
    "个人信息",
]


def _latest_pack(pack_root: Path) -> Path | None:
    if not pack_root.exists():
        return None
    candidates = sorted([p for p in pack_root.iterdir() if p.is_dir()])
    return candidates[-1] if candidates else None


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _load_review_spec(path: str | Path) -> dict[str, Any]:
    spec_path = Path(path)
    if not spec_path.exists():
        return {}
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {spec_path}")


def _approved_ids(entries: list[dict[str, Any]], key: str) -> set[str]:
    approved: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("disposition") or "") != "approved_for_internal_opt_in":
            continue
        value = str(entry.get(key) or "").strip()
        if value:
            approved.add(value)
    return approved


def audit_pack(
    *,
    pack_dir: str | Path,
    output_dir: str | Path,
    review_spec_path: str | Path = DEFAULT_REVIEW_SPEC_PATH,
) -> dict[str, Any]:
    pack = Path(pack_dir)
    docs = _read_tsv(pack / "docs.tsv")
    atoms = _read_tsv(pack / "atoms.tsv")
    review_spec = _load_review_spec(review_spec_path)
    approved_doc_ids = _approved_ids(list(review_spec.get("docs") or []), "doc_id")
    approved_atom_ids = _approved_ids(list(review_spec.get("atoms") or []), "atom_id")

    flagged_docs: list[dict[str, Any]] = []
    flagged_atoms: list[dict[str, Any]] = []

    for row in docs:
        haystack = " ".join([row.get("title", ""), row.get("raw_ref", ""), row.get("review_domain", ""), row.get("source_bucket", "")])
        hits = [token for token in SENSITIVE_TOKENS if token in haystack]
        if hits:
            flagged_docs.append(
                {
                    "doc_id": row["doc_id"],
                    "title": row.get("title", ""),
                    "raw_ref": row.get("raw_ref", ""),
                    "hits": hits,
                }
            )

    for row in atoms:
        haystack = " ".join([row.get("question", ""), row.get("canonical_question", "")])
        hits = [token for token in SENSITIVE_TOKENS if token in haystack]
        if hits:
            flagged_atoms.append(
                {
                    "doc_id": row["doc_id"],
                    "atom_id": row["atom_id"],
                    "hits": hits,
                }
            )

    approved_flagged_docs = [item for item in flagged_docs if item["doc_id"] in approved_doc_ids]
    unresolved_flagged_docs = [item for item in flagged_docs if item["doc_id"] not in approved_doc_ids]
    approved_flagged_atoms = [item for item in flagged_atoms if item["atom_id"] in approved_atom_ids]
    unresolved_flagged_atoms = [item for item in flagged_atoms if item["atom_id"] not in approved_atom_ids]

    summary = {
        "pack_dir": str(pack),
        "review_spec_path": str(review_spec_path),
        "doc_count": len(docs),
        "atom_count": len(atoms),
        "flagged_docs": len(flagged_docs),
        "flagged_atoms": len(flagged_atoms),
        "approved_flagged_docs": len(approved_flagged_docs),
        "approved_flagged_atoms": len(approved_flagged_atoms),
        "unresolved_flagged_docs": len(unresolved_flagged_docs),
        "unresolved_flagged_atoms": len(unresolved_flagged_atoms),
        "ok": len(unresolved_flagged_docs) == 0 and len(unresolved_flagged_atoms) == 0,
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "flagged_docs.json").write_text(json.dumps(flagged_docs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "flagged_atoms.json").write_text(json.dumps(flagged_atoms, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "approved_flagged_docs.json").write_text(
        json.dumps(approved_flagged_docs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "approved_flagged_atoms.json").write_text(
        json.dumps(approved_flagged_atoms, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "unresolved_flagged_docs.json").write_text(
        json.dumps(unresolved_flagged_docs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "unresolved_flagged_atoms.json").write_text(
        json.dumps(unresolved_flagged_atoms, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": summary["ok"],
        "output_dir": str(out),
        "summary_path": str(out / "summary.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a lightweight sensitivity/content-safety audit against a planning reviewed runtime pack.")
    parser.add_argument("--pack-dir", default="")
    parser.add_argument("--pack-root", default=str(DEFAULT_PACK_ROOT))
    parser.add_argument("--review-spec", default=str(DEFAULT_REVIEW_SPEC_PATH))
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    pack_dir = Path(args.pack_dir) if args.pack_dir else _latest_pack(Path(args.pack_root))
    if pack_dir is None or not pack_dir.exists():
        raise SystemExit("No planning reviewed runtime pack found. Pass --pack-dir explicitly.")
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else REPO_ROOT / "artifacts" / "monitor" / "planning_runtime_pack_sensitivity_audit" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    print(
        json.dumps(
            audit_pack(
                pack_dir=pack_dir,
                output_dir=output_dir,
                review_spec_path=args.review_spec,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
