from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from chatgptrest.core.codex_runner import codex_exec_with_schema

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_ROOT = _REPO_ROOT / "artifacts" / "controller_coding_agent"
_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(?P<body>[\s\S]*?)\s*```\s*$", re.IGNORECASE)
_DEFAULT_EXECUTOR_TIMEOUT_FLOOR_SECONDS = {
    "claude": 900,
    "codex": 300,
}
_TIMEOUT_FLOOR_ENV_BY_FAMILY = {
    "claude": "CHATGPTREST_CODING_AGENT_MIN_TIMEOUT_CLAUDE_SECONDS",
    "codex": "CHATGPTREST_CODING_AGENT_MIN_TIMEOUT_CODEX_SECONDS",
}


@dataclass(frozen=True)
class CodingAgentExecutorSpec:
    executor_id: str
    family: str
    command: str
    mode: str
    description: str
    default_model: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        resolved = _resolve_command_path(executor_id=self.executor_id, command=self.command)
        ready = bool(resolved)
        return {
            "executor_id": self.executor_id,
            "family": self.family,
            "command": self.command,
            "resolved_command": resolved,
            "ready": ready,
            "mode": self.mode,
            "description": self.description,
            "default_model": self.default_model,
        }


@dataclass(frozen=True)
class CodingAgentResolvedExecutor:
    executor_id: str
    family: str
    mode: str
    command: str
    ready: bool
    request_source: str
    resolution_reason: str
    requested_executor: str = ""
    requested_family: str = ""
    requested_model: str = ""
    requested_effort: str = ""
    defaulted: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "executor_id": self.executor_id,
            "family": self.family,
            "mode": self.mode,
            "command": self.command,
            "ready": self.ready,
            "request_source": self.request_source,
            "resolution_reason": self.resolution_reason,
            "requested_executor": self.requested_executor,
            "requested_family": self.requested_family,
            "requested_model": self.requested_model,
            "requested_effort": self.requested_effort,
            "defaulted": self.defaulted,
        }


@dataclass(frozen=True)
class CodingAgentRunResult:
    ok: bool
    executor_id: str
    family: str
    mode: str
    answer: str
    summary: str
    elapsed_ms: int
    artifact_dir: str
    artifact_path: str
    raw_output_path: str = ""
    stderr_path: str = ""
    model_used: str = ""
    error: str = ""
    parsed_output: dict[str, Any] | None = None


_EXECUTOR_SPECS: dict[str, CodingAgentExecutorSpec] = {
    "codex": CodingAgentExecutorSpec(
        executor_id="codex",
        family="codex",
        command="codex",
        mode="codex_exec",
        description="Codex ambient CLI lane",
    ),
    "codex2": CodingAgentExecutorSpec(
        executor_id="codex2",
        family="codex",
        command="codex2",
        mode="codex_exec",
        description="Codex2 isolated wrapper lane",
    ),
    "claudeminmax": CodingAgentExecutorSpec(
        executor_id="claudeminmax",
        family="claude",
        command="claudeminmax",
        mode="claude_print",
        description="Claude wrapper lane on MiniMax-backed endpoint",
        default_model="sonnet",
    ),
    "claudegac": CodingAgentExecutorSpec(
        executor_id="claudegac",
        family="claude",
        command="claudegac",
        mode="claude_print",
        description="Claude G AC wrapper lane",
        default_model="opus",
    ),
}

_EXECUTOR_ALIASES = {
    "claude": "claudeminmax",
    "claude-code": "claudeminmax",
    "claude_code": "claudeminmax",
    "claude_minimax": "claudeminmax",
    "gac": "claudegac",
    "claude_gac": "claudegac",
    "codex-cli": "codex",
}

_DEFAULT_EXECUTOR_ORDER = ("codex", "codex2", "claudeminmax", "claudegac")
_DEFAULT_EXECUTOR_ORDER_BY_FAMILY = {
    "claude": ("claudeminmax", "claudegac"),
    "codex": ("codex", "codex2"),
}

_EXECUTOR_ENV_OVERRIDES = {
    "codex": ("CHATGPTREST_CODEX_BIN",),
    "codex2": ("CHATGPTREST_CODEX2_BIN",),
    "claudeminmax": ("CC_CLI", "CHATGPTREST_CLAUDEMINMAX_BIN"),
    "claudegac": ("CHATGPTREST_CLAUDEGAC_BIN",),
}


def available_coding_agent_executors() -> dict[str, dict[str, Any]]:
    return {
        executor_id: spec.to_public_dict()
        for executor_id, spec in _EXECUTOR_SPECS.items()
    }


def _executor_candidate_commands(executor_id: str, command: str) -> list[str]:
    candidates: list[str] = []

    def _append(value: str) -> None:
        text = str(value or "").strip()
        if text and text not in candidates:
            candidates.append(text)

    for env_name in _EXECUTOR_ENV_OVERRIDES.get(str(executor_id or "").strip(), ()):
        _append(os.environ.get(env_name, ""))
    _append(command)
    home = Path.home()
    _append(str(home / ".local" / "bin" / command))
    _append(str(home / "local" / "node" / "bin" / command))
    nvm_root = home / ".nvm" / "versions" / "node"
    if nvm_root.exists():
        for node_dir in sorted(nvm_root.iterdir(), reverse=True):
            _append(str(node_dir / "bin" / command))
    return candidates


def _resolve_command_path(*, executor_id: str, command: str) -> str:
    for candidate in _executor_candidate_commands(executor_id, command):
        if not candidate:
            continue
        if os.path.isabs(candidate):
            if Path(candidate).exists():
                return candidate
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return ""


def _command_ready(*, executor_id: str, command: str) -> bool:
    return bool(_resolve_command_path(executor_id=executor_id, command=command))


def _canonical_executor_id(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    return _EXECUTOR_ALIASES.get(raw, raw)


def _canonical_family(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in {"claude", "claude_code", "claudeminmax", "claudegac"}:
        return "claude"
    if raw in {"codex", "codex2"}:
        return "codex"
    return ""


def resolve_coding_agent_executor(
    *,
    requested_executor: Any = "",
    requested_family: Any = "",
    requested_model: Any = "",
    requested_effort: Any = "",
    request_source: str = "",
) -> CodingAgentResolvedExecutor | None:
    executor_id = _canonical_executor_id(requested_executor)
    family = _canonical_family(requested_family)
    defaulted = False
    reason = ""
    if executor_id and executor_id in _EXECUTOR_SPECS:
        spec = _EXECUTOR_SPECS[executor_id]
        reason = "explicit_executor"
    else:
        if family:
            ordered_candidates = list(_DEFAULT_EXECUTOR_ORDER_BY_FAMILY.get(family, ()))
            ready_reason = "family_default_ready_order"
            fallback_reason = "family_default_fallback_order"
        else:
            ordered_candidates = list(_DEFAULT_EXECUTOR_ORDER)
            ready_reason = "planning_default_ready_order"
            fallback_reason = "planning_default_fallback_order"
        spec = None
        for candidate in ordered_candidates:
            current = _EXECUTOR_SPECS.get(candidate)
            if current is None:
                continue
            if spec is None:
                spec = current
            if _command_ready(executor_id=current.executor_id, command=current.command):
                spec = current
                reason = ready_reason
                break
        if not reason:
            reason = fallback_reason
        executor_id = str(spec.executor_id if spec is not None else "")
        defaulted = True
    if spec is None:
        return None
    resolved_command = _resolve_command_path(executor_id=spec.executor_id, command=spec.command)
    ready = bool(resolved_command)
    return CodingAgentResolvedExecutor(
        executor_id=spec.executor_id,
        family=spec.family,
        mode=spec.mode,
        command=resolved_command or spec.command,
        ready=ready,
        request_source=request_source or "task_intake.context",
        resolution_reason=reason,
        requested_executor=_canonical_executor_id(requested_executor),
        requested_family=family,
        requested_model=str(requested_model or "").strip(),
        requested_effort=str(requested_effort or "").strip(),
        defaulted=defaulted,
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_json_text(raw: str | None) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    match = _JSON_FENCE_RE.match(text)
    if match:
        text = str(match.group("body") or "").strip()
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            parsed_obj, _end = decoder.raw_decode(text[idx:])
        except Exception:
            continue
        if isinstance(parsed_obj, dict):
            return parsed_obj
    return None


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["answer", "summary"],
        "additionalProperties": False,
    }


def _extract_answer_summary(parsed: Mapping[str, Any] | None) -> tuple[str, str]:
    payload = dict(parsed or {})
    answer = str(payload.get("answer") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    if answer or summary:
        return answer, summary
    structured = dict(payload.get("structured_output") or {})
    return (
        str(structured.get("answer") or "").strip(),
        str(structured.get("summary") or "").strip(),
    )


def _coerce_process_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def _executor_timeout_floor_seconds(resolved: CodingAgentResolvedExecutor) -> int:
    family = str(resolved.family or "").strip().lower()
    floor = int(_DEFAULT_EXECUTOR_TIMEOUT_FLOOR_SECONDS.get(family, 300))
    env_name = _TIMEOUT_FLOOR_ENV_BY_FAMILY.get(family)
    if env_name:
        raw = str(os.environ.get(env_name) or "").strip()
        if raw:
            try:
                floor = max(1, int(raw))
            except Exception:
                pass
    return max(1, floor)


def _effective_timeout_seconds(*, resolved: CodingAgentResolvedExecutor, requested_timeout_seconds: int) -> int:
    requested = max(1, int(requested_timeout_seconds))
    return max(requested, _executor_timeout_floor_seconds(resolved))


def _build_prompt(*, question: str, stable_context: Mapping[str, Any], resolved: CodingAgentResolvedExecutor) -> str:
    scenario_pack = dict(stable_context.get("scenario_pack") or {})
    task_intake = dict(stable_context.get("task_intake") or {})
    files = [str(item).strip() for item in list(stable_context.get("files") or []) if str(item).strip()]
    required_sections = list(dict(scenario_pack.get("acceptance") or {}).get("required_sections") or [])
    lines = [
        "You are executing a planning task inside ChatgptREST.",
        "Return JSON only with keys `answer` and `summary`.",
        "The `answer` field must be markdown and directly satisfy the request.",
        "The `summary` field may be an empty string when no shorter summary is useful.",
        "Do not mention internal executor/runtime details in the answer.",
    ]
    if required_sections and required_sections != ["answer"]:
        lines.append("Expected answer sections: " + ", ".join(str(item) for item in required_sections))
    if files:
        lines.append("Relevant local files that may be read if needed:")
        lines.extend(f"- {path}" for path in files[:12])
    if objective := str(task_intake.get("objective") or question).strip():
        lines.append("Task:")
        lines.append(objective)
    if scenario := str(scenario_pack.get("profile") or "").strip():
        lines.append(f"Scenario profile: {scenario}")
    lines.append(f"Preferred executor: {resolved.executor_id}")
    return "\n\n".join(line for line in lines if line)


def run_coding_agent_executor(
    *,
    resolved: CodingAgentResolvedExecutor,
    question: str,
    stable_context: Mapping[str, Any],
    trace_id: str = "",
    timeout_seconds: int = 300,
) -> CodingAgentRunResult:
    started = time.perf_counter()
    effective_timeout_seconds = _effective_timeout_seconds(
        resolved=resolved,
        requested_timeout_seconds=timeout_seconds,
    )
    run_tag = (str(trace_id or "").strip() or f"coding_{uuid.uuid4().hex[:12]}").replace("/", "_")
    artifact_dir = _ARTIFACT_ROOT / run_tag
    artifact_dir.mkdir(parents=True, exist_ok=True)
    request_path = artifact_dir / "request.json"
    result_path = artifact_dir / "result.json"
    stdout_path = artifact_dir / "stdout.txt"
    stderr_path = artifact_dir / "stderr.txt"
    prompt_path = artifact_dir / "prompt.txt"
    prompt = _build_prompt(question=question, stable_context=stable_context, resolved=resolved)
    prompt_path.write_text(prompt, encoding="utf-8")
    _write_json(
        request_path,
        {
            "question": question,
            "resolved_executor": resolved.to_public_dict(),
            "scenario_pack": dict(stable_context.get("scenario_pack") or {}),
            "task_intake": dict(stable_context.get("task_intake") or {}),
            "files": list(stable_context.get("files") or []),
            "requested_timeout_seconds": int(timeout_seconds),
            "effective_timeout_seconds": int(effective_timeout_seconds),
        },
    )
    if not resolved.ready:
        payload = {
            "ok": False,
            "error": f"executor_not_ready:{resolved.executor_id}",
        }
        _write_json(result_path, payload)
        return CodingAgentRunResult(
            ok=False,
            executor_id=resolved.executor_id,
            family=resolved.family,
            mode=resolved.mode,
            answer="",
            summary="",
            elapsed_ms=int(round((time.perf_counter() - started) * 1000)),
            artifact_dir=str(artifact_dir),
            artifact_path=str(result_path),
            raw_output_path=str(stdout_path),
            stderr_path=str(stderr_path),
            error=str(payload["error"]),
            parsed_output=payload,
        )

    parsed: dict[str, Any] | None = None
    error = ""
    model_used = resolved.requested_model
    if resolved.mode == "codex_exec":
        schema_path = artifact_dir / "response.schema.json"
        schema_path.write_text(json.dumps(_response_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        out_json = artifact_dir / "codex.out.json"
        env = os.environ.copy()
        env["CHATGPTREST_CODEX_BIN"] = resolved.command
        exec_result = codex_exec_with_schema(
            prompt=prompt,
            schema_path=schema_path,
            out_json=out_json,
            model=resolved.requested_model or None,
            timeout_seconds=effective_timeout_seconds,
            cd=Path(str(stable_context.get("cwd") or _REPO_ROOT)),
            sandbox="read-only",
            env=env,
        )
        parsed = dict(exec_result.output or {}) if exec_result.ok and isinstance(exec_result.output, dict) else None
        stdout_path.write_text(str(exec_result.raw_output or ""), encoding="utf-8")
        stderr_path.write_text(str(exec_result.stderr or exec_result.error or ""), encoding="utf-8")
        if not exec_result.ok:
            error = str(exec_result.error or exec_result.error_type or "codex_exec_failed")
    else:
        schema_arg = json.dumps(_response_schema(), ensure_ascii=False)
        cmd = [
            resolved.command,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--json-schema",
            schema_arg,
            "--permission-mode",
            "bypassPermissions",
            "--add-dir",
            str(stable_context.get("cwd") or _REPO_ROOT),
        ]
        if resolved.requested_model:
            cmd.extend(["--model", resolved.requested_model])
        if resolved.requested_effort:
            cmd.extend(["--effort", resolved.requested_effort])
        try:
            proc = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                cwd=str(stable_context.get("cwd") or _REPO_ROOT),
                timeout=effective_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            partial_stdout = _coerce_process_text(exc.stdout)
            partial_stderr = _coerce_process_text(exc.stderr)
            timeout_message = (
                f"Coding-agent executor `{resolved.executor_id}` timed out after "
                f"{effective_timeout_seconds} seconds."
            )
            stdout_path.write_text(partial_stdout, encoding="utf-8")
            stderr_payload = partial_stderr.strip()
            if stderr_payload:
                stderr_payload = stderr_payload + "\n\n" + timeout_message
            else:
                stderr_payload = timeout_message
            stderr_path.write_text(stderr_payload, encoding="utf-8")
            parsed = _parse_json_text(partial_stdout)
            error = f"executor_timeout_after_{effective_timeout_seconds}s"
        else:
            stdout_path.write_text(str(proc.stdout or ""), encoding="utf-8")
            stderr_path.write_text(str(proc.stderr or ""), encoding="utf-8")
            parsed = _parse_json_text(proc.stdout or "")
            if proc.returncode != 0:
                error = f"executor_rc_{proc.returncode}"
            elif parsed is None:
                error = "invalid_executor_json_output"
    answer, summary = _extract_answer_summary(parsed)
    ok = bool(answer) and not error
    payload = {
        "ok": ok,
        "executor_id": resolved.executor_id,
        "family": resolved.family,
        "mode": resolved.mode,
        "answer": answer,
        "summary": summary,
        "model_used": model_used,
        "requested_timeout_seconds": int(timeout_seconds),
        "effective_timeout_seconds": int(effective_timeout_seconds),
        "elapsed_ms": int(round((time.perf_counter() - started) * 1000)),
        "error": error or None,
        "parsed_output": parsed,
    }
    _write_json(result_path, payload)
    return CodingAgentRunResult(
        ok=ok,
        executor_id=resolved.executor_id,
        family=resolved.family,
        mode=resolved.mode,
        answer=answer,
        summary=summary,
        elapsed_ms=int(round((time.perf_counter() - started) * 1000)),
        artifact_dir=str(artifact_dir),
        artifact_path=str(result_path),
        raw_output_path=str(stdout_path),
        stderr_path=str(stderr_path),
        model_used=model_used,
        error=error,
        parsed_output=parsed,
    )
