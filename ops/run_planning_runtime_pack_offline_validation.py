#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_reviewed_runtime_pack"
DEFAULT_SPEC_PATH = REPO_ROOT / "ops" / "data" / "planning_runtime_pack_golden_queries_v1.json"


def _latest_pack(pack_root: Path) -> Path | None:
    if not pack_root.exists():
        return None
    candidates = sorted([p for p in pack_root.iterdir() if p.is_dir()])
    return candidates[-1] if candidates else None


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _tokenize(text: str) -> list[str]:
    parts = re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", text.lower())
    return [part for part in parts if part]


def _score_doc(query_tokens: list[str], title: str, review_domain: str, source_bucket: str) -> int:
    haystack = f"{title} {review_domain} {source_bucket}"
    hay_tokens = Counter(_tokenize(haystack))
    return sum(1 for token in query_tokens if token in hay_tokens)


def run_validation(
    *,
    pack_dir: str | Path,
    spec_path: str | Path = DEFAULT_SPEC_PATH,
    output_dir: str | Path,
    top_k: int = 5,
) -> dict[str, Any]:
    pack = Path(pack_dir)
    docs = _read_tsv(pack / "docs.tsv")
    atoms = _read_tsv(pack / "atoms.tsv")
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))

    cases: list[dict[str, Any]] = []
    for query_spec in spec["queries"]:
        query = str(query_spec["query"])
        query_tokens = _tokenize(query)
        ranked_docs = sorted(
            docs,
            key=lambda row: (
                -_score_doc(query_tokens, row.get("title", ""), row.get("review_domain", ""), row.get("source_bucket", "")),
                row.get("review_domain", ""),
                row.get("source_bucket", ""),
                row.get("doc_id", ""),
            ),
        )[:top_k]
        top_domains = {row.get("review_domain", "") for row in ranked_docs}
        top_buckets = {row.get("source_bucket", "") for row in ranked_docs}
        top_titles = " ".join(row.get("title", "") for row in ranked_docs)
        top_atom_count = sum(1 for atom in atoms if atom["doc_id"] in {row["doc_id"] for row in ranked_docs})
        domain_hit = bool(set(query_spec["expected_review_domains"]) & top_domains)
        bucket_hit = bool(set(query_spec["expected_source_buckets"]) & top_buckets)
        token_hit = any(token in top_titles for token in query_spec["expected_title_tokens"])
        cases.append(
            {
                "query_id": query_spec["query_id"],
                "query": query,
                "domain_hit": domain_hit,
                "bucket_hit": bucket_hit,
                "token_hit": token_hit,
                "top_docs": [
                    {
                        "doc_id": row["doc_id"],
                        "title": row["title"],
                        "review_domain": row["review_domain"],
                        "source_bucket": row["source_bucket"],
                    }
                    for row in ranked_docs
                ],
                "top_atom_count": top_atom_count,
            }
        )

    summary = {
        "pack_dir": str(pack),
        "spec_path": str(spec_path),
        "docs": len(docs),
        "atoms": len(atoms),
        "query_count": len(cases),
        "domain_hits": sum(1 for case in cases if case["domain_hit"]),
        "bucket_hits": sum(1 for case in cases if case["bucket_hit"]),
        "token_hits": sum(1 for case in cases if case["token_hit"]),
        "ok": all(case["domain_hit"] and case["bucket_hit"] and case["token_hit"] for case in cases),
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "README.md").write_text(
        "\n".join(
            [
                "# Planning Runtime Pack Offline Validation",
                "",
                f"- `pack_dir`: `{pack}`",
                f"- `query_count`: `{summary['query_count']}`",
                f"- `domain_hits`: `{summary['domain_hits']}`",
                f"- `bucket_hits`: `{summary['bucket_hits']}`",
                f"- `token_hits`: `{summary['token_hits']}`",
                f"- `ok`: `{summary['ok']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": summary["ok"],
        "output_dir": str(out),
        "summary_path": str(out / "summary.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a lightweight offline golden-query validation against the planning reviewed runtime pack.")
    parser.add_argument("--pack-dir", default="")
    parser.add_argument("--pack-root", default=str(DEFAULT_PACK_ROOT))
    parser.add_argument("--spec", default=str(DEFAULT_SPEC_PATH))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    pack_dir = Path(args.pack_dir) if args.pack_dir else _latest_pack(Path(args.pack_root))
    if pack_dir is None or not pack_dir.exists():
        raise SystemExit("No planning reviewed runtime pack found. Pass --pack-dir explicitly.")
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else REPO_ROOT / "artifacts" / "monitor" / "planning_runtime_pack_validation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    print(
        json.dumps(
            run_validation(
                pack_dir=pack_dir,
                spec_path=args.spec,
                output_dir=output_dir,
                top_k=args.top_k,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
