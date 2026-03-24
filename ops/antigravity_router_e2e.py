#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = (os.environ.get("CHATGPTREST_BASE_URL") or "http://127.0.0.1:18711").rstrip("/")


def _ts() -> float:
    return time.time()


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug(raw: str) -> str:
    out = []
    for ch in str(raw or "").strip().lower():
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    text = "".join(out).strip("-_.")
    return text or "case"


def _http_json(
    *,
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
) -> tuple[int, dict[str, Any], str]:
    payload = None
    req_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url=url, data=payload, method=str(method).upper())
    for k, v in req_headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            obj = json.loads(raw) if raw.strip() else {}
            if not isinstance(obj, dict):
                obj = {"_raw": raw}
            return int(getattr(resp, "status", 200) or 200), obj, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            obj = json.loads(raw) if raw.strip() else {}
            if not isinstance(obj, dict):
                obj = {"_raw": raw}
        except Exception:
            obj = {"_raw": raw}
        return int(exc.code), obj, raw


def _fetch_answer(*, base_url: str, headers: dict[str, str], job_id: str, max_chars: int = 200_000) -> str:
    offset = 0
    out: list[str] = []
    total = 0
    while True:
        qs = urllib.parse.urlencode({"offset": int(offset), "max_chars": 20_000})
        code, obj, _ = _http_json(
            method="GET",
            url=f"{base_url}/v1/jobs/{urllib.parse.quote(job_id)}/answer?{qs}",
            headers=headers,
            timeout_seconds=20.0,
        )
        if code >= 400:
            break
        chunk = str(obj.get("chunk") or "")
        out.append(chunk)
        total += len(chunk)
        if total >= max_chars:
            break
        if bool(obj.get("done")):
            break
        nxt = obj.get("next_offset")
        if nxt is None:
            break
        try:
            offset = int(nxt)
        except Exception:
            break
    return "".join(out)


def _wait_job(
    *,
    base_url: str,
    headers: dict[str, str],
    job_id: str,
    max_wait_seconds: int,
    poll_seconds: int,
) -> dict[str, Any]:
    started = _ts()
    deadline = started + float(max(10, int(max_wait_seconds)))
    last: dict[str, Any] = {"job_id": job_id, "status": "in_progress"}
    while _ts() < deadline:
        qs = urllib.parse.urlencode(
            {
                "timeout_seconds": 90,
                "poll_seconds": max(1, int(poll_seconds)),
                "auto_wait_cooldown": 1,
            }
        )
        code, obj, _ = _http_json(
            method="GET",
            url=f"{base_url}/v1/jobs/{urllib.parse.quote(job_id)}/wait?{qs}",
            headers=headers,
            timeout_seconds=120.0,
        )
        if code >= 400:
            last = {"status": "error", "error": obj, "http_status": code, "job_id": job_id}
            time.sleep(max(1.0, float(poll_seconds)))
            continue
        last = obj
        st = str(obj.get("status") or "").strip().lower()
        if st in {"completed", "error", "canceled", "blocked", "cooldown", "needs_followup"}:
            break
        time.sleep(max(1.0, float(poll_seconds)))
    last["wait_elapsed_seconds"] = round(_ts() - started, 3)
    if str(last.get("status") or "").strip().lower() in {"queued", "in_progress", ""}:
        last["status"] = "timeout"
    return last


def _cancel_job(*, base_url: str, headers: dict[str, str], job_id: str, reason: str) -> tuple[int, dict[str, Any]]:
    hdr = dict(headers)
    hdr["X-Cancel-Reason"] = str(reason).strip() or "antigravity_timeout"
    code, obj, _ = _http_json(
        method="POST",
        url=f"{base_url}/v1/jobs/{urllib.parse.quote(job_id)}/cancel",
        headers=hdr,
        timeout_seconds=20.0,
    )
    return code, obj


@dataclass(frozen=True)
class Case:
    case_id: str
    kind: str  # advisor | direct
    title: str
    question: str
    expected_route: str | None = None
    expected_kind: str | None = None
    agent_options: dict[str, Any] | None = None
    direct_kind: str | None = None
    direct_params: dict[str, Any] | None = None


def _advisor_cases(base_topic: str) -> list[Case]:
    return [
        Case(
            case_id="advisor_chatgpt_thinking",
            kind="advisor",
            title="Advisor -> chatgpt_pro (thinking_heavy)",
            question=f"{base_topic}。请给出工程落地路径，不需要联网检索。",
            expected_route="chatgpt_pro",
            expected_kind="chatgpt_web.ask",
            agent_options={"preset": "thinking_heavy"},
        ),
        Case(
            case_id="advisor_chatgpt_pro_extended",
            kind="advisor",
            title="Advisor -> chatgpt_pro (pro_extended)",
            question=f"{base_topic}。重点输出可实施方案与回滚触发条件。",
            expected_route="chatgpt_pro",
            expected_kind="chatgpt_web.ask",
            agent_options={"preset": "pro_extended"},
        ),
        Case(
            case_id="advisor_deep_research",
            kind="advisor",
            title="Advisor -> deep_research",
            question="请调研 EvoMap 在 Codex 自净化能力上的最新公开实践，附来源引用与对比。",
            expected_route="deep_research",
            expected_kind="chatgpt_web.ask",
            agent_options={"preset": "thinking_heavy"},
        ),
        Case(
            case_id="advisor_pro_then_dr_then_pro",
            kind="advisor",
            title="Advisor -> pro_then_dr_then_pro",
            question="先给 EvoMap+Codex 自净化架构方案，再做联网调研并回到工程决策与实施顺序。",
            expected_route="pro_then_dr_then_pro",
            expected_kind="chatgpt_web.ask",
            agent_options={"preset": "thinking_heavy"},
        ),
        Case(
            case_id="advisor_gemini_pro",
            kind="advisor",
            title="Advisor -> gemini",
            question=f"{base_topic}。请走 Gemini 作为主通道输出工程可执行方案。",
            expected_route="gemini",
            expected_kind="gemini_web.ask",
            agent_options={"preset": "pro"},
        ),
        Case(
            case_id="advisor_crosscheck",
            kind="advisor",
            title="Advisor -> pro_gemini_crosscheck",
            question=f"{base_topic}。请进行多模型交叉验证并给出冲突消解表。",
            expected_route="pro_gemini_crosscheck",
            expected_kind="chatgpt_web.ask",
            agent_options={"preset": "thinking_heavy"},
        ),
    ]


def _direct_cases(base_topic: str) -> list[Case]:
    return [
        Case(
            case_id="direct_chatgpt_thinking_heavy",
            kind="direct",
            title="Direct chatgpt_web.ask thinking_heavy",
            question=base_topic,
            expected_kind="chatgpt_web.ask",
            direct_kind="chatgpt_web.ask",
            direct_params={"preset": "thinking_heavy"},
        ),
        Case(
            case_id="direct_chatgpt_pro_extended",
            kind="direct",
            title="Direct chatgpt_web.ask pro_extended",
            question=base_topic,
            expected_kind="chatgpt_web.ask",
            direct_kind="chatgpt_web.ask",
            direct_params={"preset": "pro_extended"},
        ),
        Case(
            case_id="direct_chatgpt_deep_research",
            kind="direct",
            title="Direct chatgpt_web.ask deep_research",
            question=f"{base_topic}。请附来源引用。",
            expected_kind="chatgpt_web.ask",
            direct_kind="chatgpt_web.ask",
            direct_params={"preset": "thinking_heavy", "deep_research": True},
        ),
        Case(
            case_id="direct_gemini_pro",
            kind="direct",
            title="Direct gemini_web.ask pro",
            question=base_topic,
            expected_kind="gemini_web.ask",
            direct_kind="gemini_web.ask",
            direct_params={"preset": "pro"},
        ),
        Case(
            case_id="direct_gemini_deep_think",
            kind="direct",
            title="Direct gemini_web.ask deep_think",
            question=base_topic,
            expected_kind="gemini_web.ask",
            direct_kind="gemini_web.ask",
            direct_params={"preset": "deep_think"},
        ),
    ]


def _build_headers(*, token: str, client_name: str, client_instance: str, request_id: str) -> dict[str, str]:
    headers = {
        "X-Client-Name": client_name,
        "X-Client-Instance": client_instance,
        "X-Request-ID": request_id,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _run_case(
    *,
    case: Case,
    idx: int,
    base_url: str,
    token: str,
    client_name: str,
    client_instance: str,
    max_wait_seconds: int,
    poll_seconds: int,
    cancel_on_timeout: bool,
) -> dict[str, Any]:
    request_id = f"antigravity-{_slug(case.case_id)}-{idx}-{uuid.uuid4().hex[:8]}"
    headers = _build_headers(token=token, client_name=client_name, client_instance=client_instance, request_id=request_id)
    started = _ts()
    record: dict[str, Any] = {
        "case_id": case.case_id,
        "title": case.title,
        "kind": case.kind,
        "request_id": request_id,
        "started_at": _iso_now(),
        "expected_route": case.expected_route,
        "expected_kind": case.expected_kind,
        "question": case.question,
    }

    if case.kind == "advisor":
        body = {
            "raw_question": case.question,
            "execute": True,
            "force": True,
            "context": {
                "project": "openclaw",
                "goal": "给 Codex 配上 EvoMap，实现自净化闭环",
                "constraints": "可回滚、可观测、可审计",
                "environment": "ChatgptREST + Codex + OpenClaw",
                "acceptance": "产出 owner/next_owner/ETA/blocker/evidence_path 与 CLI 方案",
            },
            "agent_options": dict(case.agent_options or {}),
        }
        code, obj, raw = _http_json(
            method="POST",
            url=f"{base_url}/v1/advisor/advise",
            body=body,
            headers=headers,
            timeout_seconds=45.0,
        )
        record["submit_http_status"] = code
        record["submit_body"] = obj if obj else {"_raw": raw}
        if code >= 400:
            record["final_status"] = "submit_error"
            record["elapsed_seconds"] = round(_ts() - started, 3)
            return record
        record["route"] = str(obj.get("route") or "")
        record["provider"] = str(obj.get("provider") or "")
        record["job_kind"] = str(obj.get("kind") or "")
        record["submit_status"] = str(obj.get("status") or "")
        job_id = str(obj.get("job_id") or "").strip()
    else:
        if not case.direct_kind:
            record["final_status"] = "invalid_case"
            record["elapsed_seconds"] = round(_ts() - started, 3)
            return record
        idem = f"antigravity:{case.case_id}:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}:{uuid.uuid4().hex[:10]}"
        body = {
            "kind": case.direct_kind,
            "input": {"question": case.question},
            "params": dict(case.direct_params or {}),
            "client": {"name": client_name, "case_id": case.case_id},
        }
        code, obj, raw = _http_json(
            method="POST",
            url=f"{base_url}/v1/jobs",
            body=body,
            headers={**headers, "Idempotency-Key": idem},
            timeout_seconds=30.0,
        )
        record["submit_http_status"] = code
        record["submit_body"] = obj if obj else {"_raw": raw}
        if code >= 400:
            record["final_status"] = "submit_error"
            record["elapsed_seconds"] = round(_ts() - started, 3)
            return record
        record["job_kind"] = str(obj.get("kind") or case.direct_kind)
        record["submit_status"] = str(obj.get("status") or "")
        job_id = str(obj.get("job_id") or "").strip()

    record["job_id"] = job_id
    if not job_id:
        record["final_status"] = "submit_missing_job_id"
        record["elapsed_seconds"] = round(_ts() - started, 3)
        return record

    waited = _wait_job(
        base_url=base_url,
        headers=headers,
        job_id=job_id,
        max_wait_seconds=max_wait_seconds,
        poll_seconds=poll_seconds,
    )
    record["wait"] = waited
    status = str(waited.get("status") or "").strip().lower()
    record["wait_status"] = status

    if status == "timeout" and cancel_on_timeout:
        cancel_code, cancel_obj = _cancel_job(
            base_url=base_url,
            headers=headers,
            job_id=job_id,
            reason=f"antigravity_timeout:{case.case_id}",
        )
        record["cancel_http_status"] = cancel_code
        record["cancel_body"] = cancel_obj

    if status == "completed":
        answer = _fetch_answer(base_url=base_url, headers=headers, job_id=job_id)
        record["answer_chars"] = len(answer)
        record["answer_head"] = answer[:500]

    checks: dict[str, Any] = {}
    if case.expected_route:
        checks["route_match"] = (str(record.get("route") or "") == str(case.expected_route))
    if case.expected_kind:
        checks["kind_match"] = (str(record.get("job_kind") or "") == str(case.expected_kind))
    record["checks"] = checks
    record["final_status"] = status
    record["elapsed_seconds"] = round(_ts() - started, 3)
    return record


def _write_summary(*, out_dir: Path, records: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    lines.append("# Antigravity Router E2E Summary")
    lines.append("")
    lines.append(f"- generated_at: `{_iso_now()}`")
    lines.append(f"- total_cases: `{len(records)}`")
    lines.append("")

    completed = sum(1 for r in records if str(r.get("final_status") or "") == "completed")
    submit_err = sum(1 for r in records if str(r.get("final_status") or "") == "submit_error")
    timeout = sum(1 for r in records if str(r.get("final_status") or "") == "timeout")
    lines.append(f"- completed: `{completed}`")
    lines.append(f"- submit_error: `{submit_err}`")
    lines.append(f"- timeout: `{timeout}`")
    lines.append("")
    lines.append("| case_id | kind | route | job_kind | final_status | answer_chars |")
    lines.append("|---|---|---|---|---:|---:|")
    for r in records:
        lines.append(
            "| {case_id} | {kind} | {route} | {job_kind} | {final_status} | {answer_chars} |".format(
                case_id=str(r.get("case_id") or ""),
                kind=str(r.get("kind") or ""),
                route=str(r.get("route") or ""),
                job_kind=str(r.get("job_kind") or ""),
                final_status=str(r.get("final_status") or ""),
                answer_chars=int(r.get("answer_chars") or 0),
            )
        )
    (out_dir / "summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Antigravity full E2E router matrix for advisor/direct ask paths.")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--client-name", default=os.environ.get("CHATGPTREST_CLIENT_NAME", "chatgptrestctl"))
    ap.add_argument("--client-instance", default=os.environ.get("CHATGPTREST_CLIENT_INSTANCE", f"antigravity-e2e-{os.getpid()}"))
    ap.add_argument("--api-token", default=os.environ.get("CHATGPTREST_API_TOKEN", ""))
    ap.add_argument("--max-wait-seconds", type=int, default=1200)
    ap.add_argument("--poll-seconds", type=int, default=15)
    ap.add_argument("--include-direct-matrix", action="store_true")
    ap.add_argument(
        "--cases",
        default="",
        help="Comma-separated case_id allowlist. Empty means run all selected matrices.",
    )
    ap.add_argument("--cancel-on-timeout", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir", default="")
    ap.add_argument(
        "--topic",
        default="请分析如何给 Codex 配上 EvoMap，让代理具备自净化（异常检测→策略修复→证据回灌）闭环，并给出可执行 CLI 与回滚方案",
    )
    args = ap.parse_args(argv)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir).expanduser() if str(args.out_dir).strip() else (REPO_ROOT / "artifacts" / "monitor" / "antigravity_router_e2e" / stamp)
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = _advisor_cases(str(args.topic))
    if bool(args.include_direct_matrix):
        cases.extend(_direct_cases(str(args.topic)))
    raw_cases = str(args.cases or "").strip()
    if raw_cases:
        wanted = {x.strip() for x in raw_cases.split(",") if x.strip()}
        cases = [c for c in cases if c.case_id in wanted]
    if not cases:
        print(json.dumps({"ok": False, "error": "no_cases_selected"}, ensure_ascii=False))
        return 2

    if args.dry_run:
        payload = {
            "base_url": str(args.base_url).rstrip("/"),
            "client_name": str(args.client_name),
            "client_instance": str(args.client_instance),
            "total_cases": len(cases),
            "cases": [c.__dict__ for c in cases],
            "out_dir": str(out_dir),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    records: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        rec = _run_case(
            case=case,
            idx=idx,
            base_url=str(args.base_url).rstrip("/"),
            token=str(args.api_token or "").strip(),
            client_name=str(args.client_name).strip(),
            client_instance=str(args.client_instance).strip(),
            max_wait_seconds=int(args.max_wait_seconds),
            poll_seconds=int(args.poll_seconds),
            cancel_on_timeout=bool(args.cancel_on_timeout),
        )
        records.append(rec)
        case_path = out_dir / "cases" / f"{idx:02d}_{_slug(case.case_id)}.json"
        case_path.parent.mkdir(parents=True, exist_ok=True)
        case_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"idx": idx, "case_id": case.case_id, "final_status": rec.get("final_status"), "job_id": rec.get("job_id")}, ensure_ascii=False))

    (out_dir / "result.json").write_text(json.dumps({"generated_at": _iso_now(), "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(out_dir=out_dir, records=records)
    print(json.dumps({"ok": True, "out_dir": str(out_dir), "total_cases": len(records)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
