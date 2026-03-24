#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def _write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def export_queues(*, input_tsv: str | Path, output_dir: str | Path) -> dict[str, Any]:
    fieldnames, rows = _read_tsv(Path(input_tsv))
    by_state: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    by_action: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    by_action_counter: Counter[str] = Counter()
    for row in rows:
        state = str(row.get("suggested_governance_state") or "unknown").strip() or "unknown"
        action = str(row.get("suggested_governance_action") or "unknown").strip() or "unknown"
        by_state[state].append(row)
        by_action[action].append(row)
        by_action_counter[action] += 1

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    queue_files: dict[str, dict[str, Any]] = {}
    for state, state_rows in sorted(by_state.items()):
        json_path = out / f"{state}.json"
        tsv_path = out / f"{state}.tsv"
        json_path.write_text(json.dumps(state_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _write_tsv(tsv_path, state_rows, fieldnames)
        queue_files[state] = {
            "rows": len(state_rows),
            "json_path": str(json_path),
            "tsv_path": str(tsv_path),
        }

    action_dir = out / "by_action"
    action_dir.mkdir(parents=True, exist_ok=True)
    action_files: dict[str, dict[str, Any]] = {}
    for action, action_rows in sorted(by_action.items()):
        json_path = action_dir / f"{action}.json"
        tsv_path = action_dir / f"{action}.tsv"
        json_path.write_text(json.dumps(action_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _write_tsv(tsv_path, action_rows, fieldnames)
        action_files[action] = {
            "rows": len(action_rows),
            "json_path": str(json_path),
            "tsv_path": str(tsv_path),
        }

    summary = {
        "ok": True,
        "input_tsv": str(input_tsv),
        "output_dir": str(out),
        "total_rows": len(rows),
        "by_state": {key: len(by_state[key]) for key in sorted(by_state)},
        "by_action": {key: int(by_action_counter[key]) for key in sorted(by_action_counter)},
        "queue_files": queue_files,
        "action_files": action_files,
    }
    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Split execution experience decision scaffold into governance queue files.")
    parser.add_argument("--input-tsv", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    result = export_queues(input_tsv=args.input_tsv, output_dir=args.output_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
