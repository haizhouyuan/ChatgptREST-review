#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from chatgptrest.core.completion_contract import (
    get_authoritative_answer_path,
    get_completion_answer_state,
    is_research_final,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "release_validation"
DEFAULT_CHATGPTREST_ENV_FILE = Path.home() / ".config" / "chatgptrest" / "chatgptrest.env"

LIVE_SPECS: dict[str, dict[str, str]] = {
    "gemini": {
        "provider": "gemini",
        "kind": "gemini_web.ask",
        "preset": "pro",
        "question": "请用三点说明 ChatgptREST convergence validation 的目标、关键失败信号和回滚策略。",
    },
    "chatgpt": {
        "provider": "chatgpt",
        "kind": "chatgpt_web.ask",
        "preset": "auto",
        "question": "请概括 ChatgptREST convergence validation runner 的用途、关键验证波次，以及失败后必须检查的三个证据点。",
    },
    "qwen": {
        "provider": "qwen",
        "kind": "qwen_web.ask",
        "preset": "deep_thinking",
        "question": "请用三点说明 ChatgptREST convergence validation runner 的用途、关键波次和失败时的回滚原则。",
    },
}
DEFAULT_LIVE_PROVIDERS: tuple[str, ...] = ("gemini", "chatgpt")
POLL_INTERVAL_SECONDS = 10.0
MAX_POLL_INTERVAL_SECONDS = 30.0
DEFAULT_LIVE_MAX_WAIT_SECONDS = 240.0
DEFAULT_LIVE_HARD_MAX_WAIT_SECONDS = 420.0


def _run_command(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path = REPO_ROOT,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parse_json_maybe(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def _env_file_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = str(os.environ.get("CHATGPTREST_ENV_FILE") or "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.append(DEFAULT_CHATGPTREST_ENV_FILE)
    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def _discover_live_env() -> tuple[dict[str, str], dict[str, Any]]:
    env = os.environ.copy()
    discovery: dict[str, Any] = {
        "api_token_source": "",
        "ops_token_source": "",
        "env_file": "",
        "checked_env_files": [str(path) for path in _env_file_candidates()],
    }
    if str(env.get("CHATGPTREST_API_TOKEN") or "").strip():
        discovery["api_token_source"] = "process_env"
    if str(env.get("CHATGPTREST_OPS_TOKEN") or "").strip():
        discovery["ops_token_source"] = "process_env"
    if discovery["api_token_source"] and discovery["ops_token_source"]:
        return env, discovery

    for candidate in _env_file_candidates():
        if not candidate.exists():
            continue
        try:
            file_values = _parse_env_file(candidate)
        except OSError:
            continue
        for key, value in file_values.items():
            env.setdefault(key, value)
        discovery["env_file"] = str(candidate)
        if not discovery["api_token_source"] and str(env.get("CHATGPTREST_API_TOKEN") or "").strip():
            discovery["api_token_source"] = f"env_file:{candidate}"
        if not discovery["ops_token_source"] and str(env.get("CHATGPTREST_OPS_TOKEN") or "").strip():
            discovery["ops_token_source"] = f"env_file:{candidate}"
        if discovery["api_token_source"] and discovery["ops_token_source"]:
            break
    return env, discovery


def _selected_live_specs(env: dict[str, str]) -> list[dict[str, str]]:
    raw = str(env.get("CHATGPTREST_CONVERGENCE_LIVE_PROVIDERS") or "").strip()
    names = [item.strip() for item in raw.split(",") if item.strip()] if raw else list(DEFAULT_LIVE_PROVIDERS)
    selected: list[dict[str, str]] = []
    for name in names:
        spec = LIVE_SPECS.get(name)
        if spec is not None:
            selected.append(spec)
    return selected


def _extract_provider_disabled(obj: dict[str, Any] | None) -> bool:
    detail = (obj or {}).get("body", {}).get("detail", {})
    return str(detail.get("error") or "").strip() == "provider_disabled"


def _extract_job_id(obj: dict[str, Any] | None) -> str:
    if not isinstance(obj, dict):
        return ""
    for key in ("job", "submit"):
        value = obj.get(key)
        if isinstance(value, dict) and str(value.get("job_id") or "").strip():
            return str(value["job_id"]).strip()
    if str(obj.get("job_id") or "").strip():
        return str(obj["job_id"]).strip()
    return ""


def _classify_outcome(
    *,
    submit_obj: dict[str, Any] | None,
    get_obj: dict[str, Any] | None,
    events_obj: dict[str, Any] | None,
    answer_obj: dict[str, Any] | None,
) -> tuple[str, bool, bool]:
    if _extract_provider_disabled(submit_obj):
        return ("provider_disabled", True, False)

    job = {}
    if isinstance(get_obj, dict):
        job = get_obj

    status = str(job.get("status") or "").strip()
    answer_state = get_completion_answer_state(job)
    answer_chunk = ""
    if isinstance(answer_obj, dict):
        answer = answer_obj.get("chunk") if isinstance(answer_obj.get("chunk"), str) else ""
        answer_chunk = answer
    if status == "completed" and is_research_final(job) and answer_chunk:
        return ("completed", True, True)
    if status == "completed" and answer_state != "final":
        return ("completed_not_final", False, False)

    export_path = str(job.get("conversation_export_path") or "").strip()
    authoritative_path = get_authoritative_answer_path(job) or ""
    events = events_obj.get("events") if isinstance(events_obj, dict) else []
    has_export_event = any(
        isinstance(item, dict) and str(item.get("type") or "").strip() == "conversation_exported"
        for item in (events if isinstance(events, list) else [])
    )
    if status == "in_progress" and (export_path or authoritative_path or has_export_event):
        return ("exported_pending_wait", True, False)

    phase = str(job.get("phase") or "").strip()
    prompt_sent_at = _float_value(job.get("prompt_sent_at"))
    conversation_url = str(job.get("conversation_url") or "").strip()
    if status == "in_progress" and phase == "wait" and (prompt_sent_at or conversation_url):
        return ("wait_handoff_pending", True, False)

    if status:
        return (status, False, False)

    if submit_obj:
        return ("error", False, False)
    return ("unknown", False, False)


def _float_value(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    return out if out > 0 else 0.0


def _poll_delay_seconds(job_obj: dict[str, Any] | None) -> float:
    retry_after = _float_value((job_obj or {}).get("retry_after_seconds"))
    if retry_after:
        return min(max(retry_after + 1.0, POLL_INTERVAL_SECONDS), MAX_POLL_INTERVAL_SECONDS)
    estimated_wait = _float_value((job_obj or {}).get("estimated_wait_seconds"))
    if estimated_wait:
        return min(max(estimated_wait / 6.0, POLL_INTERVAL_SECONDS), MAX_POLL_INTERVAL_SECONDS)
    return POLL_INTERVAL_SECONDS


def _live_wait_budget_seconds(
    *,
    env: dict[str, str],
    submit_obj: dict[str, Any] | None,
    get_obj: dict[str, Any] | None,
) -> float:
    configured = _float_value(env.get("CHATGPTREST_CONVERGENCE_LIVE_MAX_WAIT_SECONDS"))
    hard_cap = _float_value(env.get("CHATGPTREST_CONVERGENCE_LIVE_HARD_MAX_WAIT_SECONDS"))
    if not configured:
        configured = DEFAULT_LIVE_MAX_WAIT_SECONDS
    if not hard_cap:
        hard_cap = DEFAULT_LIVE_HARD_MAX_WAIT_SECONDS
    estimate = max(
        _float_value((submit_obj or {}).get("estimated_wait_seconds")),
        _float_value((get_obj or {}).get("estimated_wait_seconds")),
        _float_value((get_obj or {}).get("retry_after_seconds")),
    )
    if estimate:
        return min(max(configured, estimate + 30.0), hard_cap)
    return configured


def _has_export_signal(get_obj: dict[str, Any] | None, events_obj: dict[str, Any] | None) -> bool:
    export_path = str((get_obj or {}).get("conversation_export_path") or "").strip()
    authoritative_path = get_authoritative_answer_path(get_obj) or ""
    events = events_obj.get("events") if isinstance(events_obj, dict) else []
    has_export_event = any(
        isinstance(item, dict) and str(item.get("type") or "").strip() == "conversation_exported"
        for item in (events if isinstance(events, list) else [])
    )
    return bool(export_path or authoritative_path or has_export_event)


def _has_wait_handoff_signal(get_obj: dict[str, Any] | None) -> bool:
    job = get_obj or {}
    status = str(job.get("status") or "").strip()
    phase = str(job.get("phase") or "").strip()
    prompt_sent_at = _float_value(job.get("prompt_sent_at"))
    conversation_url = str(job.get("conversation_url") or "").strip()
    return status == "in_progress" and phase == "wait" and bool(prompt_sent_at or conversation_url)


def _cli_submit_cmd(
    *,
    python_bin: str,
    provider: str,
    kind: str,
    preset: str,
    question: str,
) -> list[str]:
    return [
        python_bin,
        "-m",
        "chatgptrest.cli",
        "--request-timeout-seconds",
        "30",
        "--output",
        "json",
        "jobs",
        "submit",
        "--kind",
        kind,
        "--idempotency-key",
        f"convergence-live-{provider}-{int(time.time())}",
        "--question",
        question,
        "--preset",
        preset,
    ]


def _cli_get_cmd(*, python_bin: str, job_id: str, subcmd: str) -> list[str]:
    return [
        python_bin,
        "-m",
        "chatgptrest.cli",
        "--output",
        "json",
        "jobs",
        subcmd,
        job_id,
    ]


def _cli_answer_cmd(*, python_bin: str, job_id: str) -> list[str]:
    return [
        python_bin,
        "-m",
        "chatgptrest.cli",
        "--output",
        "json",
        "jobs",
        "answer",
        job_id,
        "--max-chars",
        "4000",
    ]


def run_live_matrix(
    *,
    output_dir: str | Path,
    python_bin: str = sys.executable,
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    live_env, discovery = _discover_live_env()
    api_token = str(live_env.get("CHATGPTREST_API_TOKEN") or "").strip()
    summary: dict[str, Any] = {
        "ok": False,
        "skipped": False,
        "providers": [],
        "output_dir": str(out),
        "discovery": discovery,
        "provider_order": [spec["provider"] for spec in _selected_live_specs(live_env)],
    }
    if not api_token:
        summary["skipped"] = True
        summary["reason"] = "missing_api_token"
        _write_text(out / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        return summary

    any_completed = False
    any_handoff = False
    unexpected_failures = 0
    for spec in _selected_live_specs(live_env):
        provider = spec["provider"]
        cmd_env = live_env.copy()
        cmd_env["CHATGPTREST_API_TOKEN"] = api_token
        submit_cmd = _cli_submit_cmd(
            python_bin=python_bin,
            provider=provider,
            kind=spec["kind"],
            preset=spec["preset"],
            question=spec["question"],
        )
        submit_proc = _run_command(submit_cmd, env=cmd_env)
        raw_submit_text = submit_proc.stdout or submit_proc.stderr or ""
        submit_path = out / f"{provider}_submit.json"
        _write_text(submit_path, raw_submit_text)
        submit_obj = _parse_json_maybe(raw_submit_text)
        job_id = _extract_job_id(submit_obj)

        get_obj = None
        events_obj = None
        answer_obj = None
        poll_attempts = 0
        max_wait_seconds = 0.0
        if job_id:
            max_wait_seconds = _live_wait_budget_seconds(env=cmd_env, submit_obj=submit_obj, get_obj=None)
            deadline = time.monotonic() + max_wait_seconds
            while True:
                poll_attempts += 1
                get_proc = _run_command(
                    _cli_get_cmd(python_bin=python_bin, job_id=job_id, subcmd="get"),
                    env=cmd_env,
                )
                get_text = get_proc.stdout or get_proc.stderr or ""
                _write_text(out / f"{provider}_get.json", get_text)
                get_obj = _parse_json_maybe(get_text)

                events_proc = _run_command(
                    _cli_get_cmd(python_bin=python_bin, job_id=job_id, subcmd="events"),
                    env=cmd_env,
                )
                events_text = events_proc.stdout or events_proc.stderr or ""
                _write_text(out / f"{provider}_events.json", events_text)
                events_obj = _parse_json_maybe(events_text)

                status = str((get_obj or {}).get("status") or "").strip()
                max_wait_seconds = _live_wait_budget_seconds(
                    env=cmd_env,
                    submit_obj=submit_obj,
                    get_obj=get_obj,
                )
                if (
                    status == "completed"
                    or _has_export_signal(get_obj, events_obj)
                    or _has_wait_handoff_signal(get_obj)
                ):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(_poll_delay_seconds(get_obj), remaining))

            if str((get_obj or {}).get("status") or "").strip() == "completed" and is_research_final(get_obj):
                answer_proc = _run_command(
                    _cli_answer_cmd(python_bin=python_bin, job_id=job_id),
                    env=cmd_env,
                )
                answer_text = answer_proc.stdout or answer_proc.stderr or ""
                _write_text(out / f"{provider}_answer.json", answer_text)
                answer_outer = _parse_json_maybe(answer_text)
                if isinstance(answer_outer, dict) and isinstance(answer_outer.get("answer"), dict):
                    answer_obj = answer_outer.get("answer")
                else:
                    answer_obj = answer_outer

        outcome, acceptable, completed = _classify_outcome(
            submit_obj=submit_obj,
            get_obj=get_obj,
            events_obj=events_obj,
            answer_obj=answer_obj,
        )
        if completed:
            any_completed = True
        if acceptable and outcome in {"exported_pending_wait", "wait_handoff_pending"}:
            any_handoff = True
        if not acceptable:
            unexpected_failures += 1

        provider_summary = {
            "provider": provider,
            "kind": spec["kind"],
            "returncode": int(submit_proc.returncode),
            "job_id": job_id,
            "outcome": outcome,
            "acceptable": acceptable,
            "completed": completed,
            "submit_path": str(submit_path),
            "poll_attempts": poll_attempts,
            "max_wait_seconds": max_wait_seconds,
        }
        summary["providers"].append(provider_summary)

    summary["ok"] = unexpected_failures == 0 and (bool(any_completed) or bool(any_handoff))
    summary["any_completed"] = any_completed
    summary["any_handoff"] = any_handoff
    summary["unexpected_failures"] = unexpected_failures
    _write_text(out / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main() -> int:
    output_dir = (
        Path(sys.argv[1])
        if len(sys.argv) > 1 and str(sys.argv[1]).strip()
        else DEFAULT_OUTPUT_ROOT / "convergence_live_matrix"
    )
    summary = run_live_matrix(output_dir=output_dir)
    print(json.dumps(summary, ensure_ascii=False))
    if summary.get("skipped"):
        return 0
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
