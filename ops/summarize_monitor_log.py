from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = (line or "").strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        if isinstance(obj, dict):
            items.append(obj)
    return items


def _fmt_counts(d: dict[str, int]) -> str:
    if not d:
        return "(none)"
    return ", ".join([f"{k}={d[k]}" for k in sorted(d.keys())])


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize ops/monitor_chatgptrest.py JSONL output into a Markdown report.")
    ap.add_argument("--in", dest="in_path", required=True, help="Input JSONL file path.")
    ap.add_argument("--out", dest="out_path", required=True, help="Output Markdown file path.")
    args = ap.parse_args()

    in_path = Path(str(args.in_path)).expanduser()
    out_path = Path(str(args.out_path)).expanduser()
    if not in_path.exists():
        raise SystemExit(f"input not found: {in_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    items = _read_jsonl(in_path)

    started = None
    finished = None
    blocked_true = 0
    blocked_false = 0
    mihomo_last = None
    db_connect_errors = 0
    jobs_summaries: list[dict[str, Any]] = []
    job_event_type_counts: dict[str, int] = {}

    for obj in items:
        t = obj.get("type")
        if t == "monitor_started":
            started = obj.get("ts")
        elif t == "monitor_finished":
            finished = obj.get("ts")
        elif t == "jobs_summary":
            s = obj.get("summary")
            if isinstance(s, dict):
                jobs_summaries.append(s)
        elif t == "chatgptmcp_blocked_state":
            if bool(obj.get("blocked")):
                blocked_true += 1
            else:
                blocked_false += 1
        elif t == "mihomo_delay_last":
            mihomo_last = obj.get("record")
        elif t == "db_connect_error":
            db_connect_errors += 1
        elif t == "job_event":
            et = str(obj.get("event_type") or "").strip()
            if et:
                job_event_type_counts[et] = job_event_type_counts.get(et, 0) + 1

    max_status: dict[str, int] = {}
    last_status: dict[str, Any] = {}
    if jobs_summaries:
        last_status = jobs_summaries[-1]
    for s in jobs_summaries:
        for k, v in s.items():
            try:
                vv = int(v)
            except Exception:
                continue
            max_status[str(k)] = max(max_status.get(str(k), 0), vv)

    top_event_types = sorted(job_event_type_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]

    md: list[str] = []
    md.append("# ChatgptREST Soak Summary")
    md.append("")
    md.append(f"- log: `{in_path.as_posix()}`")
    md.append(f"- started: {started}")
    md.append(f"- finished: {finished}")
    md.append("")
    md.append("## Jobs (max over run)")
    md.append(f"- {_fmt_counts(max_status)}")
    md.append("")
    md.append("## Jobs (last sample)")
    md.append(f"- {json.dumps(last_status, ensure_ascii=False) if last_status else '(none)'}")
    md.append("")
    md.append("## Blocked state samples")
    md.append(f"- blocked=true: {blocked_true}")
    md.append(f"- blocked=false: {blocked_false}")
    md.append("")
    md.append("## Mihomo last record")
    md.append("```json")
    md.append(json.dumps(mihomo_last, ensure_ascii=False, indent=2) if mihomo_last is not None else "null")
    md.append("```")
    md.append("")
    md.append("## Monitor errors")
    md.append(f"- db_connect_error: {db_connect_errors}")
    md.append("")
    md.append("## Top job event types")
    if not top_event_types:
        md.append("- (none)")
    else:
        for k, v in top_event_types:
            md.append(f"- {k}: {v}")

    out_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
