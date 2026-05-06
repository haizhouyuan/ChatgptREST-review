#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chatgptrest.ops_shared.infra import atomic_write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MONITOR_DIR = REPO_ROOT / "artifacts" / "monitor" / "maint_daemon"
DEFAULT_REPORTS_ROOT = REPO_ROOT / "artifacts" / "monitor" / "reports" / "maint_daemon_jsonl_cleanup"
DAY_RE = re.compile(r"^maint_(\d{8})\.jsonl$")


@dataclass(frozen=True)
class MaintJsonlFile:
    path: Path
    day: datetime
    size_bytes: int

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def day_key(self) -> str:
        return self.day.strftime("%Y%m%d")

    @property
    def day_iso(self) -> str:
        return self.day.date().isoformat()


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fmt_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    units = ["KiB", "MiB", "GiB", "TiB"]
    value = float(size)
    for unit in units:
        value /= 1024.0
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}"
    return f"{size} B"


def _gib_bytes(value: float) -> int:
    return int(float(value) * (1024**3))


def _parse_file(path: Path) -> MaintJsonlFile | None:
    m = DAY_RE.match(path.name)
    if not m:
        return None
    day = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=UTC)
    return MaintJsonlFile(path=path, day=day, size_bytes=int(path.stat().st_size))


def _list_files(monitor_dir: Path) -> list[MaintJsonlFile]:
    out: list[MaintJsonlFile] = []
    for path in sorted(monitor_dir.glob("maint_*.jsonl")):
        item = _parse_file(path)
        if item is not None:
            out.append(item)
    return sorted(out, key=lambda item: item.day, reverse=True)


def _sample_bytes(path: Path, *, max_bytes: int) -> bytes:
    max_bytes = max(1024, int(max_bytes))
    data = path.read_bytes() if path.stat().st_size <= max_bytes else path.open("rb").read(max_bytes)
    nl = data.rfind(b"\n")
    if nl > 0:
        data = data[: nl + 1]
    return data


def _gzip_ratio(data: bytes) -> float:
    if not data:
        return 1.0
    compressed = gzip.compress(data, compresslevel=6)
    return len(compressed) / max(1, len(data))


def _sha256(path: Path, *, max_bytes: int) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        remaining = max(1, int(max_bytes))
        while remaining > 0:
            chunk = f.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run maint_daemon/maint_*.jsonl cleanup planning.")
    parser.add_argument("--monitor-dir", default=str(DEFAULT_MONITOR_DIR))
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT))
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--protected-files", type=int, default=2)
    parser.add_argument("--hot-raw-files", type=int, default=3)
    parser.add_argument("--warm-window-days", type=int, default=14)
    parser.add_argument("--sample-limit", type=int, default=6)
    parser.add_argument("--sample-bytes-per-file", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--summary-estimate-bytes", type=int, default=256 * 1024)
    parser.add_argument("--soft-budget-gib", type=float, default=15.0)
    parser.add_argument("--hard-budget-gib", type=float, default=25.0)
    parser.add_argument("--head-sha-bytes", type=int, default=1024 * 1024)
    return parser


def _classify_actions(
    files: list[MaintJsonlFile],
    *,
    protected_files: int,
    hot_raw_files: int,
    warm_window_days: int,
    now_utc: datetime,
) -> list[dict[str, Any]]:
    protected_count = max(0, int(protected_files))
    hot_raw_count = max(0, int(hot_raw_files))
    warm_days = max(0, int(warm_window_days))

    protected_names = {item.name for item in files[:protected_count]}
    hot_candidates = [item for item in files if item.name not in protected_names]
    hot_raw_names = {item.name for item in hot_candidates[:hot_raw_count]}

    rows: list[dict[str, Any]] = []
    for item in files:
        age_days = int((now_utc.date() - item.day.date()).days)
        is_protected = item.name in protected_names
        if is_protected:
            action = "protected"
            tier = "protected_live_window"
        elif item.name in hot_raw_names:
            action = "keep_raw"
            tier = "hot_raw_window"
        elif age_days <= warm_days:
            action = "compress"
            tier = "warm_compressed_window"
        else:
            action = "summarize_only"
            tier = "cold_summary_only_window"
        rows.append(
            {
                "file_name": item.name,
                "file_path": str(item.path),
                "file_day": item.day_key,
                "file_day_iso": item.day_iso,
                "age_days": age_days,
                "size_bytes": item.size_bytes,
                "size_human": _fmt_bytes(item.size_bytes),
                "action": action,
                "tier": tier,
                "protected": is_protected,
            }
        )
    return rows


def _compression_sample(
    rows: list[dict[str, Any]],
    *,
    sample_limit: int,
    sample_bytes_per_file: int,
    head_sha_bytes: int,
) -> dict[str, Any]:
    candidates = [row for row in rows if row["action"] == "compress"]
    sample_population = "compress"
    if not candidates:
        candidates = [row for row in rows if row["action"] == "summarize_only"]
        sample_population = "summarize_only"
    candidates = sorted(candidates, key=lambda row: int(row["size_bytes"]), reverse=True)
    sampled: list[dict[str, Any]] = []
    total_sample_bytes = 0
    total_compressed_bytes = 0
    for row in candidates[: max(0, int(sample_limit))]:
        path = Path(str(row["file_path"]))
        raw = _sample_bytes(path, max_bytes=int(sample_bytes_per_file))
        ratio = _gzip_ratio(raw)
        compressed_bytes = int(math.ceil(len(raw) * ratio))
        total_sample_bytes += len(raw)
        total_compressed_bytes += compressed_bytes
        sampled.append(
            {
                "file_name": row["file_name"],
                "file_day": row["file_day"],
                "source_size_bytes": int(row["size_bytes"]),
                "sample_size_bytes": len(raw),
                "sample_sha256": _sha256(path, max_bytes=int(head_sha_bytes)),
                "compressed_sample_bytes": compressed_bytes,
                "observed_ratio": ratio,
            }
        )
    observed_ratio = (
        float(total_compressed_bytes) / float(total_sample_bytes) if total_sample_bytes > 0 else 0.15
    )
    return {
        "sampled_files": sampled,
        "sample_population": sample_population,
        "sample_limit": int(sample_limit),
        "sample_bytes_per_file": int(sample_bytes_per_file),
        "observed_ratio": observed_ratio,
        "total_sample_bytes": total_sample_bytes,
        "total_compressed_sample_bytes": total_compressed_bytes,
    }


def _budget_projection(
    rows: list[dict[str, Any]],
    *,
    observed_ratio: float,
    summary_estimate_bytes: int,
    soft_budget_gib: float,
    hard_budget_gib: float,
) -> dict[str, Any]:
    current_total = sum(int(row["size_bytes"]) for row in rows)
    projected_total = 0
    projected_rows: list[dict[str, Any]] = []
    keep_raw = []
    would_compress = []
    would_summarize = []
    for row in rows:
        action = str(row["action"])
        size_bytes = int(row["size_bytes"])
        projected_bytes = size_bytes
        if action == "compress":
            projected_bytes = int(math.ceil(size_bytes * float(observed_ratio)))
            would_compress.append(row["file_name"])
        elif action == "summarize_only":
            projected_bytes = min(size_bytes, int(summary_estimate_bytes))
            would_summarize.append(row["file_name"])
        else:
            keep_raw.append(row["file_name"])
        projected_total += projected_bytes
        projected_rows.append(
            {
                **row,
                "projected_bytes": projected_bytes,
                "projected_human": _fmt_bytes(projected_bytes),
                "estimated_savings_bytes": max(0, size_bytes - projected_bytes),
            }
        )
    soft_budget_bytes = _gib_bytes(float(soft_budget_gib))
    hard_budget_bytes = _gib_bytes(float(hard_budget_gib))
    return {
        "current_total_bytes": current_total,
        "current_total_human": _fmt_bytes(current_total),
        "projected_total_bytes": projected_total,
        "projected_total_human": _fmt_bytes(projected_total),
        "estimated_savings_bytes": max(0, current_total - projected_total),
        "estimated_savings_human": _fmt_bytes(max(0, current_total - projected_total)),
        "soft_budget_bytes": soft_budget_bytes,
        "soft_budget_human": _fmt_bytes(soft_budget_bytes),
        "hard_budget_bytes": hard_budget_bytes,
        "hard_budget_human": _fmt_bytes(hard_budget_bytes),
        "soft_budget_pass": projected_total <= soft_budget_bytes,
        "hard_budget_pass": projected_total <= hard_budget_bytes,
        "keep_raw_files": keep_raw,
        "would_compress_files": would_compress,
        "would_summarize_only_files": would_summarize,
        "rows": projected_rows,
    }


def _inventory_markdown(rows: list[dict[str, Any]], *, now_utc: datetime) -> str:
    lines = [
        "# maint_daemon JSONL Inventory",
        "",
        f"Generated at: `{_iso(now_utc)}`",
        "",
        "| File | Day | Age(days) | Size | Action | Tier |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['file_name']}` | `{row['file_day']}` | `{row['age_days']}` | `{row['size_human']}` | `{row['action']}` | `{row['tier']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def _plan_markdown(plan: dict[str, Any], sample: dict[str, Any], *, now_utc: datetime) -> str:
    lines = [
        "# maint_daemon JSONL Dry Run Plan",
        "",
        f"Generated at: `{_iso(now_utc)}`",
        "",
        "## Budget",
        "",
        f"- current: `{plan['current_total_human']}`",
        f"- projected: `{plan['projected_total_human']}`",
        f"- estimated savings: `{plan['estimated_savings_human']}`",
        f"- soft budget: `{plan['soft_budget_human']}` pass=`{plan['soft_budget_pass']}`",
        f"- hard budget: `{plan['hard_budget_human']}` pass=`{plan['hard_budget_pass']}`",
        "",
        "## Compression Sample",
        "",
        f"- sample population: `{sample.get('sample_population')}`",
        f"- observed ratio: `{sample['observed_ratio']:.4f}`",
        f"- sampled files: `{len(sample['sampled_files'])}`",
        f"- total sample bytes: `{_fmt_bytes(int(sample['total_sample_bytes']))}`",
        "",
        "## Planned Actions",
        "",
        f"- keep raw: `{len(plan['keep_raw_files'])}`",
        f"- would compress: `{len(plan['would_compress_files'])}`",
        f"- would summarize-only: `{len(plan['would_summarize_only_files'])}`",
        "",
    ]
    if plan["would_compress_files"]:
        lines.extend(["### Would Compress", ""])
        for name in plan["would_compress_files"]:
            lines.append(f"- `{name}`")
        lines.append("")
    if plan["would_summarize_only_files"]:
        lines.extend(["### Would Summarize Only", ""])
        for name in plan["would_summarize_only_files"]:
            lines.append(f"- `{name}`")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now_utc = _now_utc()
    monitor_dir = Path(str(args.monitor_dir)).expanduser()
    reports_root = Path(str(args.reports_root)).expanduser()
    timestamp = str(args.timestamp or "").strip() or now_utc.strftime("%Y%m%dT%H%M%SZ")
    out_dir = reports_root / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    files = _list_files(monitor_dir)
    rows = _classify_actions(
        files,
        protected_files=int(args.protected_files),
        hot_raw_files=int(args.hot_raw_files),
        warm_window_days=int(args.warm_window_days),
        now_utc=now_utc,
    )
    sample = _compression_sample(
        rows,
        sample_limit=int(args.sample_limit),
        sample_bytes_per_file=int(args.sample_bytes_per_file),
        head_sha_bytes=int(args.head_sha_bytes),
    )
    plan = _budget_projection(
        rows,
        observed_ratio=float(sample["observed_ratio"]),
        summary_estimate_bytes=int(args.summary_estimate_bytes),
        soft_budget_gib=float(args.soft_budget_gib),
        hard_budget_gib=float(args.hard_budget_gib),
    )

    inventory_payload = {
        "generated_at": _iso(now_utc),
        "monitor_dir": str(monitor_dir),
        "file_count": len(rows),
        "rows": rows,
    }
    sample_payload = {
        "generated_at": _iso(now_utc),
        "monitor_dir": str(monitor_dir),
        **sample,
    }
    plan_payload = {
        "generated_at": _iso(now_utc),
        "monitor_dir": str(monitor_dir),
        "timestamp": timestamp,
        "projection_mode": "dry_run_only",
        "summary_estimate_bytes": int(args.summary_estimate_bytes),
        "protected_files": int(args.protected_files),
        "hot_raw_files": int(args.hot_raw_files),
        "warm_window_days": int(args.warm_window_days),
        "observed_ratio": float(sample["observed_ratio"]),
        **{k: v for k, v in plan.items() if k != "rows"},
        "rows": plan["rows"],
        "output_dir": str(out_dir),
    }

    atomic_write_json(out_dir / "inventory_before.json", inventory_payload)
    atomic_write_json(out_dir / "compression_sample.json", sample_payload)
    atomic_write_json(out_dir / "dry_run_plan.json", plan_payload)
    _write_text(out_dir / "inventory_before.md", _inventory_markdown(rows, now_utc=now_utc))
    _write_text(out_dir / "dry_run_plan.md", _plan_markdown(plan, sample, now_utc=now_utc))

    print(json.dumps({"ok": True, "output_dir": str(out_dir), "file_count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
