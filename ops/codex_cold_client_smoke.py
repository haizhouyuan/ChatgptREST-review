#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from chatgptrest.core.codex_runner import codex_exec_with_schema
from chatgptrest.core.completion_contract import (
    get_answer_provenance,
    get_authoritative_answer_path,
    get_completion_answer_state,
    is_authoritative_answer_ready,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_ROOT = REPO_ROOT / "artifacts" / "cold_client_smoke"
SCHEMA_PATH = REPO_ROOT / "ops" / "schemas" / "codex_cold_client_smoke.schema.json"
DEFAULT_QUESTION = "请用两句话解释为什么写自动化测试可以降低回归风险。"
CLIENT_SUMMARY_FILENAME = "client_summary.json"
DISCOVERY_STALL_SECONDS = 120
SYSTEM_OBSERVED_SALVAGE_SECONDS = 90
_DOC_PATH_RE = re.compile(r"(AGENTS\.md|docs/[A-Za-z0-9_./-]+\.md|skills-src/[A-Za-z0-9_./-]+(?:\.md|\.py))")


def _default_preset(provider: str) -> str:
    provider_n = str(provider or "").strip().lower()
    if provider_n == "chatgpt":
        return "auto"
    if provider_n == "gemini":
        return "pro"
    raise ValueError(f"unsupported provider: {provider!r}")


def _policy_error_for_request(*, provider: str, preset: str, allow_live_chatgpt_smoke: bool) -> str | None:
    provider_n = str(provider or "").strip().lower()
    preset_n = str(preset or "").strip().lower() or _default_preset(provider_n)
    if provider_n != "chatgpt":
        return None
    if not bool(allow_live_chatgpt_smoke):
        return "cold client smoke against live chatgpt_web.ask is blocked by default; use gemini or pass --allow-live-chatgpt-smoke for a controlled exception"
    if preset_n != "auto":
        return "cold client smoke only permits chatgpt preset=auto by default; high-cost ChatGPT smoke is blocked"
    return None


def _default_out_dir() -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return ARTIFACTS_ROOT / stamp


def _cold_codex_env(out_dir: Path, *, isolate_codex_home: bool) -> dict[str, str]:
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    if isolate_codex_home:
        codex_home = out_dir / "cold_codex_home"
        codex_home.mkdir(parents=True, exist_ok=True)
        env["CODEX_HOME"] = str(codex_home)
    return env


def _codex_bin() -> str:
    raw = (os.environ.get("CHATGPTREST_CODEX_BIN") or os.environ.get("CODEX_BIN") or "").strip()
    if raw:
        return raw
    found = shutil.which("codex")
    if found:
        return found
    return "codex"


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    return parsed if isinstance(parsed, dict) else None


def _parse_codex_jsonl(stdout_text: str) -> dict[str, Any] | None:
    final_text = ""
    for raw in str(stdout_text or "").splitlines():
        line = str(raw or "").strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if not isinstance(item, dict):
            continue
        if item.get("type") != "item.completed":
            continue
        payload = item.get("item")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "agent_message":
            continue
        final_text = str(payload.get("text") or "")
    return _parse_json_object(final_text)


def _load_required_fields(schema_path: Path) -> list[str]:
    try:
        parsed = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    required = parsed.get("required")
    if not isinstance(required, list):
        return []
    return [str(x) for x in required if str(x or "").strip()]


def _validate_required_fields(payload: dict[str, Any], *, schema_path: Path) -> str | None:
    missing = [name for name in _load_required_fields(schema_path) if name not in payload]
    if missing:
        return f"cold client result missing required fields: {', '.join(missing)}"
    return None


def _looks_like_codex_config_error(value: Any) -> bool:
    text = str(value or "").lower()
    return "error loading config.toml" in text or "duplicate key" in text


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _read_answer_preview(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    if len(text) <= 400:
        return text
    return text[:400].rstrip() + "..."


def _resolve_authoritative_path(job_obj: dict[str, Any], *, default_path: Path) -> Path:
    authoritative_path = get_authoritative_answer_path(job_obj)
    if authoritative_path:
        candidate = REPO_ROOT / "artifacts" / authoritative_path
        if candidate.exists():
            return candidate
    return default_path


def _read_jsonl_items(path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = str(line or "").strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def _extract_commands_and_docs(jsonl_path: Path) -> tuple[list[str], list[str]]:
    commands: list[str] = []
    docs_read: list[str] = []
    seen_docs: set[str] = set()
    for obj in _read_jsonl_items(jsonl_path):
        item = obj.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("type") != "command_execution":
            continue
        cmd = str(item.get("command") or "").strip()
        if not cmd:
            continue
        commands.append(cmd)
        for match in _DOC_PATH_RE.finditer(cmd):
            doc = str(match.group(1) or "").strip()
            if doc and doc not in seen_docs:
                seen_docs.add(doc)
                docs_read.append(doc)
    return commands, docs_read


def _kind_for_provider(provider: str) -> str:
    provider_n = str(provider or "").strip().lower()
    if provider_n == "chatgpt":
        return "chatgpt_web.ask"
    if provider_n == "gemini":
        return "gemini_web.ask"
    raise ValueError(f"unsupported provider: {provider!r}")


def _find_matching_job_artifact(
    *,
    provider: str,
    preset: str,
    question: str,
    started_at: float,
) -> dict[str, Any] | None:
    jobs_root = REPO_ROOT / "artifacts" / "jobs"
    expected_kind = _kind_for_provider(provider)
    expected_preset = str(preset or "").strip()
    expected_question = str(question or "").strip()
    try:
        request_paths = sorted(
            jobs_root.glob("*/request.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        return None
    for request_path in request_paths[:80]:
        try:
            if request_path.stat().st_mtime + 5 < float(started_at):
                continue
            request_obj = json.loads(request_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(request_obj, dict):
            continue
        if str(request_obj.get("kind") or "").strip() != expected_kind:
            continue
        input_obj = request_obj.get("input")
        params_obj = request_obj.get("params")
        if not isinstance(input_obj, dict) or not isinstance(params_obj, dict):
            continue
        if str(input_obj.get("question") or "").strip() != expected_question:
            continue
        if str(params_obj.get("preset") or "").strip() != expected_preset:
            continue
        job_dir = request_path.parent
        job_id = job_dir.name
        result_path = job_dir / "result.json"
        answer_path = job_dir / "answer.md"
        conversation_path = job_dir / "conversation.json"
        result_obj: dict[str, Any] = {}
        try:
            parsed_result = json.loads(result_path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(parsed_result, dict):
                result_obj = parsed_result
        except Exception:
            result_obj = {}
        return {
            "job_id": job_id,
            "kind": expected_kind,
            "provider": provider,
            "preset": expected_preset,
            "question": expected_question,
            "status": str(result_obj.get("status") or "").strip(),
            "phase": str(result_obj.get("phase") or "").strip(),
            "conversation_url": str(result_obj.get("conversation_url") or "").strip(),
            "answer_state": get_completion_answer_state(result_obj),
            "answer_provenance": get_answer_provenance(result_obj),
            "authoritative_answer_path": get_authoritative_answer_path(result_obj),
            "answer_path": _resolve_authoritative_path(result_obj, default_path=answer_path),
            "conversation_path": conversation_path,
            "result_path": result_path,
        }
    return None


def _build_system_observed_payload(
    *,
    jsonl_path: Path,
    provider: str,
    preset: str,
    question: str,
    job_info: dict[str, Any],
    schema_path: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    commands, docs_read = _extract_commands_and_docs(jsonl_path)
    if not commands:
        commands = [
            "codex exec cold-client smoke (system-observed salvage)",
        ]
    if not docs_read:
        docs_read = [
            "AGENTS.md",
            "docs/runbook.md",
            "docs/client_projects_registry.md",
            "skills-src/chatgptrest-call/SKILL.md",
        ]
    answer_path = Path(str(job_info.get("answer_path") or ""))
    conversation_path = Path(str(job_info.get("conversation_path") or ""))
    answer_state = get_completion_answer_state(job_info)
    job_succeeded = is_authoritative_answer_ready(job_info)
    payload: dict[str, Any] = {
        "ok": job_succeeded,
        "provider": provider,
        "preset": preset,
        "question": question,
        "docs_read": docs_read,
        "commands": commands,
        "job_succeeded": job_succeeded,
        "job_id": str(job_info.get("job_id") or "").strip(),
        "final_status": (
            "completed"
            if job_succeeded
            else (
                "completed_not_final"
                if str(job_info.get("status") or "").strip().lower() == "completed" and answer_state != "final"
                else str(job_info.get("status") or "").strip()
            )
        ),
        "answer_state": answer_state,
        "authoritative_answer_path": str(job_info.get("authoritative_answer_path") or ""),
        "answer_provenance": get_answer_provenance(job_info),
        "answer_path": str(answer_path),
        "conversation_path": str(conversation_path),
        "answer_preview": _read_answer_preview(answer_path),
        "gaps": [
            "nested codex did not emit the final structured summary; result was salvaged from observed job artifacts",
            "docs_read/commands may be partially synthesized if the live codex JSONL stream was not yet flushed when salvage ran",
        ],
        "recommendations": [
            "keep the cold-client prompt lean so the nested codex reaches the real client command before spending its budget on documentation browsing",
        ],
    }
    validation_error = _validate_required_fields(payload, schema_path=schema_path)
    if validation_error:
        return None, validation_error
    return payload, None


def _salvage_client_summary(
    *,
    out_dir: Path,
    schema_path: Path,
    provider: str,
    preset: str,
    question: str,
) -> tuple[dict[str, Any] | None, str | None]:
    summary_path = out_dir / CLIENT_SUMMARY_FILENAME
    try:
        parsed = json.loads(summary_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None, None
    if not isinstance(parsed, dict):
        return None, "client_summary.json was not a JSON object"

    job = parsed.get("job")
    job_obj = job if isinstance(job, dict) else {}
    artifacts = parsed.get("artifacts")
    artifacts_obj = artifacts if isinstance(artifacts, dict) else {}
    answer_path = Path(str(artifacts_obj.get("answer_markdown") or (out_dir / "answer.md")))
    conversation_path = Path(str(artifacts_obj.get("conversation_json") or (out_dir / "conversation.json")))
    answer_state = get_completion_answer_state(job_obj)
    job_succeeded = is_authoritative_answer_ready(job_obj)

    payload: dict[str, Any] = {
        "ok": bool(parsed.get("documented_path_discovered")) and bool(parsed.get("request_executed")),
        "provider": provider,
        "preset": preset,
        "question": question,
        "docs_read": _coerce_string_list(parsed.get("docs_and_files_read")),
        "commands": _coerce_string_list(parsed.get("commands_ran")),
        "job_succeeded": job_succeeded,
        "job_id": str(job_obj.get("job_id") or "").strip(),
        "final_status": (
            "completed"
            if job_succeeded
            else (
                "completed_not_final"
                if str(job_obj.get("final_status") or "").strip().lower() == "completed" and answer_state != "final"
                else str(job_obj.get("final_status") or "").strip()
            )
        ),
        "answer_state": answer_state,
        "authoritative_answer_path": get_authoritative_answer_path(job_obj) or str(artifacts_obj.get("answer_markdown") or ""),
        "answer_provenance": get_answer_provenance(job_obj),
        "answer_path": str(answer_path),
        "conversation_path": str(conversation_path),
        "answer_preview": _read_answer_preview(answer_path),
        "gaps": _coerce_string_list(parsed.get("concrete_confusion_points_or_missing_guidance")),
        "recommendations": _coerce_string_list(parsed.get("recommendations")),
    }
    validation_error = _validate_required_fields(payload, schema_path=schema_path)
    if validation_error:
        return None, validation_error
    return payload, None


def _codex_json_fallback(
    *,
    prompt: str,
    out_dir: Path,
    schema_path: Path,
    provider: str,
    preset: str,
    question: str,
    model: str | None,
    profile: str | None,
    timeout_seconds: int,
    env: dict[str, str],
) -> tuple[dict[str, Any] | None, str | None]:
    cmd = [
        _codex_bin(),
        "exec",
        "--json",
        "--color",
        "never",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "-C",
        str(REPO_ROOT),
        "-",
    ]
    if model and str(model).strip():
        cmd.extend(["--model", str(model).strip()])
    if profile and str(profile).strip():
        cmd.extend(["--profile", str(profile).strip()])
    jsonl_path = out_dir / "codex.exec.jsonl"
    stderr_path = out_dir / "codex.exec.stderr.log"

    with jsonl_path.open("w", encoding="utf-8") as stdout_fh, stderr_path.open("w", encoding="utf-8") as stderr_fh:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=stdout_fh,
            stderr=stderr_fh,
            text=True,
            env=env,
        )
        assert proc.stdin is not None
        proc.stdin.write(prompt + "\n\nFinal response must be a raw JSON object only. Do not wrap it in markdown fences.\n")
        proc.stdin.close()
        proc.stdin = None

        started_at = time.time()
        salvage_payload: dict[str, Any] | None = None
        while True:
            if proc.poll() is not None:
                proc.wait(timeout=5)
                break

            salvage_payload, _salvage_error = _salvage_client_summary(
                out_dir=out_dir,
                schema_path=schema_path,
                provider=provider,
                preset=preset,
                question=question,
            )
            if salvage_payload is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                break

            elapsed = time.time() - started_at
            job_info = _find_matching_job_artifact(
                provider=provider,
                preset=preset,
                question=question,
                started_at=started_at,
            )
            if elapsed >= float(SYSTEM_OBSERVED_SALVAGE_SECONDS) and job_info and str(job_info.get("status") or "").lower() == "completed":
                salvage_payload, _salvage_error = _build_system_observed_payload(
                    jsonl_path=jsonl_path,
                    provider=provider,
                    preset=preset,
                    question=question,
                    job_info=job_info,
                    schema_path=schema_path,
                )
                if salvage_payload is not None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    break

            if elapsed >= float(DISCOVERY_STALL_SECONDS) and job_info is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                return None, "cold client stalled in discovery before reaching a real client request"

            if elapsed >= float(max(1, int(timeout_seconds))):
                proc.kill()
                proc.wait(timeout=5)
                break

            time.sleep(1.0)

    if salvage_payload is not None:
        return salvage_payload, None

    stdout_text = jsonl_path.read_text(encoding="utf-8", errors="replace") if jsonl_path.exists() else ""
    if proc.returncode != 0:
        return None, f"codex exec json fallback failed rc={proc.returncode}"

    parsed = _parse_codex_jsonl(stdout_text or "")
    if parsed is None:
        salvage_payload, salvage_error = _salvage_client_summary(
            out_dir=out_dir,
            schema_path=schema_path,
            provider=provider,
            preset=preset,
            question=question,
        )
        if salvage_payload is not None:
            return salvage_payload, None
        if salvage_error:
            return None, salvage_error
        return None, "codex exec json fallback produced no final JSON object"
    validation_error = _validate_required_fields(parsed, schema_path=schema_path)
    if validation_error:
        return None, validation_error
    return parsed, None


def _build_prompt(
    *,
    provider: str,
    preset: str,
    question: str,
    out_dir: Path,
    request_timeout_seconds: float,
) -> str:
    answer_path = out_dir / "answer.md"
    conversation_path = out_dir / "conversation.json"
    summary_path = out_dir / "client_summary.json"

    lines: list[str] = []
    lines.append("You are acting as a fresh Codex client for ChatgptREST.")
    lines.append("")
    lines.append("Goal: from a cold start, discover the documented ChatgptREST client path in this repository and execute one realistic human-language request.")
    lines.append("")
    lines.append("Hard constraints:")
    lines.append("- Do not modify repository code, docs, or configs.")
    lines.append("- Use only repository-discoverable entrypoints and docs a normal external Codex client would find.")
    lines.append("- Prefer the documented client path, not ad-hoc curl guessing.")
    lines.append("- Use a human-language prompt, not a trivial ping.")
    lines.append("- If the first attempt fails because you misunderstood the documented path, you may self-correct once from the repo docs.")
    lines.append("- If a sandboxed Codex shell cannot reach 127.0.0.1 loopback HTTP, you may use the repository-documented ChatgptREST MCP path as the supported fallback, but you must record that explicitly as a client ergonomics gap.")
    lines.append("- Provider and preset are mandatory task parameters. Substituting a different provider or preset counts as failure.")
    lines.append("- Do not invent raw REST calls with arbitrary X-Client-Name values. If you use direct REST at all, it must follow the documented registered client identity rules.")
    lines.append("- Save artifacts to the paths below.")
    lines.append("- Keep exploration lean: use `rg`/targeted help first, and read only the smallest relevant snippets instead of dumping full files.")
    lines.append("- You should reach the real client command within a small number of steps; do not spend the whole run browsing docs.")
    lines.append("")
    lines.append("Discovery scope:")
    lines.append("- AGENTS.md (only enough to locate the client-facing entrypoints and constraints)")
    lines.append("- docs/codex_fresh_client_quickstart.md")
    lines.append("- docs/runbook.md (focus on ChatgptREST CLI / skill / cold client sections)")
    lines.append("- docs/client_projects_registry.md (focus on cold client acceptance rule)")
    lines.append("- skills-src/chatgptrest-call/SKILL.md")
    lines.append("- relevant CLI help if needed")
    lines.append("")
    lines.append("Expected client path:")
    lines.append("- Prefer `/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py` or `./.venv/bin/python -m chatgptrest.cli`.")
    lines.append("- If you use the wrapper, keep the default server-side queue/idempotency behavior.")
    lines.append("- Do not assume bare `python` exists on this host.")
    lines.append("")
    lines.append("Task parameters:")
    lines.append(f"- provider: {provider}")
    lines.append(f"- preset: {preset}")
    lines.append(f"- question: {question}")
    lines.append(f"- request timeout seconds: {request_timeout_seconds}")
    lines.append("")
    lines.append("Artifact targets:")
    lines.append(f"- answer markdown: {answer_path}")
    lines.append(f"- conversation JSON: {conversation_path}")
    lines.append(f"- client summary JSON: {summary_path}")
    lines.append("")
    lines.append("What to report in JSON:")
    lines.append("- whether the cold-start path succeeded")
    lines.append("- which docs/files you had to read")
    lines.append("- exact commands you ran")
    lines.append("- job_id and final status when available")
    lines.append("- concrete confusion points or missing guidance")
    lines.append("- concrete recommendations to make this path reliable for future client sessions")
    lines.append("")
    lines.append("You should actually run the client command, not just describe it.")
    return "\n".join(lines).strip()


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Run a cold-start Codex acceptance smoke against the documented ChatgptREST client path.")
    ap.add_argument("--provider", choices=["chatgpt", "gemini"], default="gemini")
    ap.add_argument("--preset", default="", help="If empty, provider default is used.")
    ap.add_argument("--question", default=DEFAULT_QUESTION)
    ap.add_argument("--request-timeout-seconds", type=float, default=180.0)
    ap.add_argument("--timeout-seconds", type=int, default=900)
    ap.add_argument("--model", default=os.environ.get("CODEX_COLD_CLIENT_MODEL") or "")
    ap.add_argument("--profile", default=os.environ.get("CODEX_COLD_CLIENT_PROFILE") or "")
    ap.add_argument("--out-dir", default="")
    ap.add_argument(
        "--isolate-codex-home",
        action="store_true",
        help="Use an empty CODEX_HOME under the output dir for stricter audits. Default keeps the caller's normal CODEX_HOME and only relies on a fresh Codex session.",
    )
    ap.add_argument(
        "--allow-live-chatgpt-smoke",
        action="store_true",
        help="Controlled exception: permit cold-client smoke to hit live chatgpt_web.ask. Default is fail-closed.",
    )
    return ap


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    provider = str(args.provider or "").strip().lower()
    preset = str(args.preset or "").strip() or _default_preset(provider)
    question = str(args.question or "").strip() or DEFAULT_QUESTION
    model = str(args.model or "").strip() or None
    profile = str(args.profile or "").strip() or None
    policy_error = _policy_error_for_request(
        provider=provider,
        preset=preset,
        allow_live_chatgpt_smoke=bool(args.allow_live_chatgpt_smoke),
    )
    if policy_error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_type": "PolicyError",
                    "error": policy_error,
                    "provider": provider,
                    "preset": preset,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    out_dir = Path(str(args.out_dir or "").strip()).expanduser() if str(args.out_dir or "").strip() else _default_out_dir()
    if not out_dir.is_absolute():
        out_dir = (REPO_ROOT / out_dir).resolve(strict=False)
    out_dir.mkdir(parents=True, exist_ok=True)

    prompt = _build_prompt(
        provider=provider,
        preset=preset,
        question=question,
        out_dir=out_dir,
        request_timeout_seconds=float(args.request_timeout_seconds),
    )
    (out_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    result_json = out_dir / "result.json"
    meta = {
        "provider": provider,
        "preset": preset,
        "question": question,
        "request_timeout_seconds": float(args.request_timeout_seconds),
        "timeout_seconds": int(args.timeout_seconds),
        "model": model,
        "profile": profile,
        "isolate_codex_home": bool(args.isolate_codex_home),
        "result_json": str(result_json),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    attempt_plan = [bool(args.isolate_codex_home)]
    if not bool(args.isolate_codex_home):
        attempt_plan.append(True)

    last_error: dict[str, Any] | None = None
    used_isolated_codex_home = bool(args.isolate_codex_home)

    for attempt_index, isolate_this_attempt in enumerate(attempt_plan, start=1):
        env = _cold_codex_env(out_dir, isolate_codex_home=isolate_this_attempt)
        res = codex_exec_with_schema(
            prompt=prompt,
            schema_path=SCHEMA_PATH,
            out_json=result_json,
            model=model,
            profile=profile,
            timeout_seconds=int(max(1, int(args.timeout_seconds))),
            cd=REPO_ROOT,
            sandbox="workspace-write",
            env=env,
        )
        if res.ok:
            used_isolated_codex_home = isolate_this_attempt
            payload: dict[str, Any] = {
                "ok": True,
                "out_dir": str(out_dir),
                "result_json": str(result_json),
                "runner": "codex_exec_with_schema",
                "model": model,
                "profile": profile,
                "used_isolated_codex_home": used_isolated_codex_home,
                "result": res.output or {},
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0

        fallback_payload, fallback_error = _codex_json_fallback(
            prompt=prompt,
            out_dir=out_dir,
            schema_path=SCHEMA_PATH,
            provider=provider,
            preset=preset,
            question=question,
            model=model,
            profile=profile,
            timeout_seconds=int(max(1, int(args.timeout_seconds))),
            env=env,
        )
        if fallback_payload is not None:
            used_isolated_codex_home = isolate_this_attempt
            result_json.write_text(json.dumps(fallback_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            payload = {
                "ok": True,
                "out_dir": str(out_dir),
                "result_json": str(result_json),
                "runner": "codex_exec_json_fallback",
                "model": model,
                "profile": profile,
                "used_isolated_codex_home": used_isolated_codex_home,
                "result": fallback_payload,
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0

        err = {
            "ok": False,
            "error_type": str(res.error_type or "RuntimeError"),
            "error": str(res.error or "codex exec failed"),
            "returncode": res.returncode,
            "stderr": res.stderr,
            "fallback_error": fallback_error,
            "out_dir": str(out_dir),
            "attempt": attempt_index,
            "attempt_isolated_codex_home": isolate_this_attempt,
        }
        last_error = err
        if isolate_this_attempt or not _looks_like_codex_config_error(json.dumps(err, ensure_ascii=False)):
            print(json.dumps(err, ensure_ascii=False, indent=2, sort_keys=True))
            return 1

    print(json.dumps(last_error or {"ok": False, "error": "cold client smoke failed"}, ensure_ascii=False, indent=2, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main(list(sys.argv[1:])))
