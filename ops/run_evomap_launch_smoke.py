#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from ops.run_evomap_telemetry_live_smoke import run_smoke as run_telemetry_smoke

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "evomap_launch_smoke"


def _request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return int(resp.status), body
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {"error": str(exc)}
        return int(exc.code), body


def evaluate_issue_export(body: dict[str, Any]) -> dict[str, Any]:
    summary = body.get("summary") if isinstance(body.get("summary"), dict) else {}
    ok = (
        bool(body.get("ok", False))
        and str(summary.get("read_plane") or "") == "canonical"
        and int(summary.get("object_count") or 0) > 0
    )
    return {
        "ok": ok,
        "read_plane": str(summary.get("read_plane") or ""),
        "object_count": int(summary.get("object_count") or 0),
        "canonical_issue_count": int(summary.get("canonical_issue_count") or 0),
        "coverage_gap_count": int(summary.get("coverage_gap_count") or 0),
    }


def evaluate_planning_recall(body: dict[str, Any]) -> dict[str, Any]:
    hits = list(body.get("hits") or []) if isinstance(body, dict) else []
    sources = body.get("sources") if isinstance(body.get("sources"), dict) else {}
    planning_hits = [hit for hit in hits if str(hit.get("source") or "") == "planning_review_pack"]
    ok = bool(body.get("ok", False)) and int(sources.get("planning_review_pack") or 0) > 0 and bool(planning_hits)
    return {
        "ok": ok,
        "planning_hit_count": int(sources.get("planning_review_pack") or 0),
        "top_hit_source": str(planning_hits[0].get("source") or "") if planning_hits else "",
        "top_hit_artifact_id": str(planning_hits[0].get("artifact_id") or "") if planning_hits else "",
        "source_scope": list(body.get("source_scope") or []),
    }


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    base = args.base_url.rstrip("/")
    api_token = str(os.environ.get(args.api_token_env, "") or "").strip()
    v1_headers = (
        {"Authorization": f"Bearer {api_token}"}
        if api_token
        else None
    )
    if not hasattr(args, "http_timeout_seconds"):
        args.http_timeout_seconds = 60.0
    if not hasattr(args, "visibility_timeout_seconds"):
        args.visibility_timeout_seconds = 35.0
    if not hasattr(args, "poll_interval_seconds"):
        args.poll_interval_seconds = 0.5
    if not hasattr(args, "max_attempts"):
        args.max_attempts = 2
    if not hasattr(args, "retry_sleep_seconds"):
        args.retry_sleep_seconds = 1.0

    telemetry_result = run_telemetry_smoke(args)

    issue_status, issue_body = _request_json(
        method="GET",
        url=f"{base}/v1/issues/canonical/export?{urllib.parse.urlencode({'limit': args.issue_limit})}",
        headers=v1_headers,
    )
    issue_result = {
        "http_status": issue_status,
        "response": issue_body,
        **evaluate_issue_export(issue_body),
    }

    planning_status, planning_body = _request_json(
        method="POST",
        url=f"{base}/v1/advisor/recall",
        payload={
            "query": args.planning_query,
            "top_k": args.planning_top_k,
            "source_scope": ["planning_review"],
        },
        headers=v1_headers,
    )
    planning_result = {
        "http_status": planning_status,
        "response": planning_body,
        **evaluate_planning_recall(planning_body),
    }

    ok = bool(issue_result["ok"] and planning_result["ok"] and telemetry_result.get("ok"))
    return {
        "ok": ok,
        "generated_at": time.time(),
        "base_url": base,
        "issue_domain": issue_result,
        "planning_runtime_pack": planning_result,
        "telemetry_ingest": telemetry_result,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run launch-readiness smoke for issue-domain, planning opt-in, and telemetry canonical ingest.")
    parser.add_argument("--base-url", default="http://127.0.0.1:18711")
    parser.add_argument("--db-path", default="data/evomap_knowledge.db")
    parser.add_argument("--api-key-env", default="OPENMIND_API_KEY")
    parser.add_argument("--api-token-env", default="CHATGPTREST_API_TOKEN")
    parser.add_argument("--trace-id", default="tr-evomap-launch-smoke")
    parser.add_argument("--session-id", default="sess-evomap-launch-smoke")
    parser.add_argument("--event-id", default=f"telemetry-launch-{int(time.time())}")
    parser.add_argument("--task-ref", default="telemetry-p0/launch-smoke")
    parser.add_argument("--source", default="codex")
    parser.add_argument("--agent-name", default="codex")
    parser.add_argument("--artifact-path", default="docs/dev_log/2026-03-11_evomap_launch_smoke_v1.md")
    parser.add_argument("--replay-count", type=int, default=1)
    parser.add_argument("--settle-seconds", type=float, default=0.2)
    parser.add_argument("--http-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--visibility-timeout-seconds", type=float, default=35.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=0.5)
    parser.add_argument("--expect-dedup", action="store_true")
    parser.add_argument("--issue-limit", type=int, default=5)
    parser.add_argument("--planning-query", default="合同 商务 底线")
    parser.add_argument("--planning-top-k", type=int, default=5)
    parser.add_argument("--output-dir", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else DEFAULT_OUTPUT_ROOT / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    )
    try:
        report = run_smoke(args)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        report = {
            "ok": False,
            "http_status": exc.code,
            "error": body,
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        report = {
            "ok": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
    report["output_dir"] = str(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "launch_smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
