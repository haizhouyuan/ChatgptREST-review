#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chatgptrest.core.completion_contract import (
    get_authoritative_answer_path,
    get_completion_answer_state,
    is_authoritative_answer_ready,
)


DEFAULT_BASE_URL = os.environ.get("CHATGPTREST_BASE_URL") or "http://127.0.0.1:18711"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_json(
    *,
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    hdrs = dict(headers or {})
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method.upper())
    for k, v in hdrs.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            return json.loads(text) if text.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {raw}") from e


@dataclass(frozen=True)
class SmokeQuestion:
    label: str
    question: str


def _build_questions() -> list[SmokeQuestion]:
    cities = [
        "北京",
        "上海",
        "广州",
        "深圳",
        "杭州",
        "成都",
        "重庆",
        "武汉",
        "西安",
        "南京",
        "苏州",
        "天津",
        "长沙",
        "郑州",
        "青岛",
        "厦门",
        "昆明",
        "哈尔滨",
        "乌鲁木齐",
        "拉萨",
    ]
    c1, c2 = random.sample(cities, 2)
    when = random.choice(["今天", "明天", "后天", "这周末"])
    return [
        SmokeQuestion(
            label="weather_degree",
            question=f"{c1}{when}的天气大概多少度？",
        ),
        SmokeQuestion(
            label="weather_compare",
            question=f"{c1}和{c2}{when}哪边更冷一点？",
        ),
        SmokeQuestion(
            label="weather_outfit",
            question=f"我{when}在{c2}出门，穿什么比较合适？简单说两句就行。",
        ),
    ]


def _read_full_answer(*, base_url: str, job_id: str, headers: dict[str, str], max_total_bytes: int = 512_000) -> str:
    offset = 0
    chunks: list[str] = []
    total_bytes = 0
    while True:
        res = _http_json(
            method="GET",
            url=f"{base_url}/v1/jobs/{job_id}/answer?offset={offset}&max_chars=20000",
            headers=headers,
            timeout_seconds=30.0,
        )
        chunk = str(res.get("chunk") or "")
        chunks.append(chunk)
        total_bytes += len(chunk.encode("utf-8", errors="replace"))
        if total_bytes > max_total_bytes:
            chunks.append("\n\n[TRUNCATED: smoke_test max_total_bytes exceeded]\n")
            break
        if bool(res.get("done")):
            break
        next_offset = res.get("next_offset")
        if next_offset is None:
            break
        offset = int(next_offset)
    return "".join(chunks)


def _policy_error_for_args(*, preset: str, allow_live_chatgpt_smoke: bool) -> dict[str, Any] | None:
    resolved_preset = str(preset or "").strip().lower() or "auto"
    if resolved_preset != "auto":
        return {
            "ok": False,
            "error_type": "PolicyError",
            "message": "ops/smoke_test_chatgpt_auto.py only permits preset=auto; high-cost ChatGPT smoke is blocked",
        }
    if not bool(allow_live_chatgpt_smoke):
        return {
            "ok": False,
            "error_type": "PolicyError",
            "message": "live ChatGPT smoke is blocked by default; use gemini/qwen smoke paths or pass --allow-live-chatgpt-smoke for a controlled exception",
        }
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Human-like smoke test for ChatgptREST via auto preset (avoid obvious scripted pings).")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--preset", default="auto", help="Executor preset: auto|pro_extended|thinking_heavy (default: auto)")
    ap.add_argument("--timeout-seconds", type=int, default=240)
    ap.add_argument("--max-wait-seconds", type=int, default=480)
    ap.add_argument("--poll-seconds", type=float, default=4.0)
    ap.add_argument("--sleep-between", type=float, default=15.0, help="Client-side sleep between jobs (server may also throttle).")
    ap.add_argument("--log-jsonl", default="", help="Optional jsonl log path.")
    ap.add_argument(
        "--allow-live-chatgpt-smoke",
        action="store_true",
        help="Controlled exception: permit this script to hit live chatgpt_web.ask. Default is fail-closed.",
    )
    args = ap.parse_args(argv)

    policy_error = _policy_error_for_args(
        preset=str(args.preset or ""),
        allow_live_chatgpt_smoke=bool(args.allow_live_chatgpt_smoke),
    )
    if policy_error is not None:
        print(json.dumps(policy_error, ensure_ascii=False), file=sys.stderr)
        return 2

    base_url = str(args.base_url).rstrip("/")
    token = os.environ.get("CHATGPTREST_API_TOKEN") or ""
    headers: dict[str, str] = {}
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"

    # Health check
    _http_json(method="GET", url=f"{base_url}/healthz", headers=headers, timeout_seconds=10.0)

    log_path = str(args.log_jsonl).strip()
    log_f = None
    if log_path:
        p = Path(log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        log_f = p.open("a", encoding="utf-8")

    def _log(obj: dict[str, Any]) -> None:
        line = json.dumps(obj, ensure_ascii=False)
        if log_f:
            log_f.write(line + "\n")
            log_f.flush()
        else:
            print(line, flush=True)

    ok_count = 0
    for i in range(max(1, int(args.count))):
        q = random.choice(_build_questions())
        idem = f"smoke:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:{os.getpid()}:{i}"
        payload = {
            "kind": "chatgpt_web.ask",
            "input": {"question": q.question},
            "params": {
                "preset": str(args.preset).strip().lower(),
                "timeout_seconds": int(args.timeout_seconds),
                "max_wait_seconds": int(args.max_wait_seconds),
                "min_chars": 20,
                "answer_format": "markdown",
            },
            "client": {"name": "smoke_test_chatgpt_auto", "label": q.label},
        }
        started = time.time()
        job = _http_json(
            method="POST",
            url=f"{base_url}/v1/jobs",
            body=payload,
            headers={**headers, "Idempotency-Key": idem},
            timeout_seconds=15.0,
        )
        job_id = str(job.get("job_id") or "")
        if not job_id:
            raise RuntimeError(f"missing job_id in response: {job}")

        status = str(job.get("status") or "")
        last = job
        deadline = started + float(max(30, int(args.max_wait_seconds)))
        while time.time() < deadline and status not in {"completed", "error", "canceled", "blocked", "cooldown", "needs_followup"}:
            time.sleep(max(0.2, float(args.poll_seconds)))
            last = _http_json(method="GET", url=f"{base_url}/v1/jobs/{job_id}", headers=headers, timeout_seconds=15.0)
            status = str(last.get("status") or "")

        elapsed = round(time.time() - started, 3)
        answer_preview = str(last.get("preview") or "")
        answer_state = get_completion_answer_state(last)
        record: dict[str, Any] = {
            "ts": _now_iso(),
            "job_id": job_id,
            "status": status,
            "elapsed_seconds": elapsed,
            "label": q.label,
            "question_chars": len(q.question),
            "answer_preview_chars": len(answer_preview),
            "conversation_url": last.get("conversation_url"),
            "retry_after_seconds": last.get("retry_after_seconds"),
            "reason_type": last.get("reason_type"),
            "reason": last.get("reason"),
            "answer_state": answer_state,
            "authoritative_answer_path": get_authoritative_answer_path(last),
        }
        if status == "completed" and is_authoritative_answer_ready(last):
            try:
                answer = _read_full_answer(base_url=base_url, job_id=job_id, headers=headers)
                record["answer_chars"] = len(answer)
                record["answer_head"] = answer[:200]
                ok_count += 1
            except Exception as exc:
                record["answer_read_error"] = str(exc)
        elif status == "completed":
            record["finality_status"] = "completed_not_final"
        _log(record)

        if i + 1 < int(args.count):
            time.sleep(max(0.0, float(args.sleep_between)))

    if log_f:
        log_f.close()
    return 0 if ok_count > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
