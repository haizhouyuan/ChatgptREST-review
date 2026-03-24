#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "runner_lane_probe"
HCOM_START_SCRIPT = Path("/vol1/1000/home-yuanhaizhou/.codex2/skills/hcom-agent-teams/scripts/hcom_start.sh")

TOKENS_RE = re.compile(r"tokens used\s*([\d,]+)", re.I)


@dataclass
class ProbeResult:
    lane: str
    ok: bool
    returncode: int
    elapsed_ms: int
    command: list[str]
    summary: str
    parsed_output: Any | None = None
    stdout_excerpt: str | None = None
    stderr_excerpt: str | None = None
    tokens_used: int | None = None
    artifacts: dict[str, str] | None = None


def _now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _excerpt(text: str, *, limit: int = 3000) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[:limit] + f"\n...<truncated {len(raw) - limit} chars>"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parse_jsonish(raw: str) -> Any | None:
    text = str(raw or "").strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.I)
    if fence:
        body = str(fence.group(1) or "").strip()
        try:
            return json.loads(body)
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}\s*$", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _extract_tokens(stdout: str, stderr: str) -> int | None:
    combined = f"{stdout}\n{stderr}"
    match = TOKENS_RE.search(combined)
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except Exception:
        return None


def _run(
    *,
    lane: str,
    cmd: list[str],
    input_text: str | None,
    timeout_seconds: int,
    cwd: Path,
    env: dict[str, str] | None,
    run_dir: Path,
    parse_mode: str,
    extra_artifacts: dict[str, str] | None = None,
) -> ProbeResult:
    started = time.monotonic()
    stdout_path = run_dir / f"{lane}.stdout.log"
    stderr_path = run_dir / f"{lane}.stderr.log"
    try:
        proc = subprocess.run(
            cmd,
            input=input_text,
            text=True,
            capture_output=True,
            cwd=str(cwd),
            env=env,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
        rc = int(proc.returncode)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        rc = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        stderr = (stderr + "\nTIMEOUT").strip()
    elapsed_ms = int(round((time.monotonic() - started) * 1000))
    _write_text(stdout_path, stdout)
    _write_text(stderr_path, stderr)

    parsed: Any | None = None
    summary = ""
    if parse_mode == "json-stdout":
        parsed = _parse_jsonish(stdout)
    elif parse_mode == "json-file":
        out_path = run_dir / f"{lane}.out.json"
        if out_path.exists():
            try:
                parsed = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                parsed = None
    if rc == 0 and parsed is not None:
        summary = "machine-readable output ok"
    elif rc == 0:
        summary = "command succeeded but output is not machine-readable"
    else:
        summary = "command failed"

    artifacts = {
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }
    if extra_artifacts:
        artifacts.update(extra_artifacts)
    return ProbeResult(
        lane=lane,
        ok=(rc == 0 and parsed is not None) if parse_mode.startswith("json") else (rc == 0),
        returncode=rc,
        elapsed_ms=elapsed_ms,
        command=cmd,
        summary=summary,
        parsed_output=parsed,
        stdout_excerpt=_excerpt(stdout),
        stderr_excerpt=_excerpt(stderr),
        tokens_used=_extract_tokens(stdout, stderr),
        artifacts=artifacts,
    )


def probe_codex_ambient(run_dir: Path, prompt: str, timeout_seconds: int) -> ProbeResult:
    out_path = run_dir / "codex_ambient.out.json"
    cmd = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-o",
        str(out_path),
        "-",
    ]
    return _run(
        lane="codex_ambient",
        cmd=cmd,
        input_text=prompt,
        timeout_seconds=timeout_seconds,
        cwd=Path("/tmp"),
        env=None,
        run_dir=run_dir,
        parse_mode="json-file",
        extra_artifacts={"out_json": str(out_path)},
    )


def probe_codex_isolated(run_dir: Path, prompt: str, timeout_seconds: int) -> ProbeResult:
    temp_home = Path(tempfile.mkdtemp(prefix="codex_probe_home_"))
    codex_home = temp_home / ".codex"
    codex_home.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "codex_isolated.out.json"
    env = os.environ.copy()
    env["HOME"] = str(temp_home)
    env["CODEX_HOME"] = str(codex_home)
    cmd = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-o",
        str(out_path),
        "-",
    ]
    result = _run(
        lane="codex_isolated",
        cmd=cmd,
        input_text=prompt,
        timeout_seconds=timeout_seconds,
        cwd=Path("/tmp"),
        env=env,
        run_dir=run_dir,
        parse_mode="json-file",
        extra_artifacts={"out_json": str(out_path), "codex_home": str(codex_home)},
    )
    return result


def probe_codex_auth_only(run_dir: Path, prompt: str, timeout_seconds: int) -> ProbeResult:
    temp_home = Path(tempfile.mkdtemp(prefix="codex_probe_auth_"))
    codex_home = temp_home / ".codex"
    codex_home.mkdir(parents=True, exist_ok=True)
    src_auth = Path.home() / ".codex" / "auth.json"
    if src_auth.exists():
        (codex_home / "auth.json").write_bytes(src_auth.read_bytes())
    out_path = run_dir / "codex_auth_only.out.json"
    env = os.environ.copy()
    env["HOME"] = str(temp_home)
    env["CODEX_HOME"] = str(codex_home)
    cmd = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-o",
        str(out_path),
        "-",
    ]
    result = _run(
        lane="codex_auth_only",
        cmd=cmd,
        input_text=prompt,
        timeout_seconds=timeout_seconds,
        cwd=Path("/tmp"),
        env=env,
        run_dir=run_dir,
        parse_mode="json-file",
        extra_artifacts={"out_json": str(out_path), "codex_home": str(codex_home)},
    )
    return result


def probe_gemini_ambient(run_dir: Path, prompt: str, timeout_seconds: int) -> ProbeResult:
    cmd = ["gemini", "-p", prompt, "--model", "gemini-2.5-pro"]
    return _run(
        lane="gemini_ambient",
        cmd=cmd,
        input_text=None,
        timeout_seconds=timeout_seconds,
        cwd=Path("/tmp"),
        env=None,
        run_dir=run_dir,
        parse_mode="json-stdout",
    )


def probe_gemini_no_mcp(run_dir: Path, prompt: str, timeout_seconds: int) -> ProbeResult:
    cmd = ["gemini", "-p", prompt, "--model", "gemini-2.5-pro", "--allowed-mcp-server-names", ""]
    return _run(
        lane="gemini_no_mcp",
        cmd=cmd,
        input_text=None,
        timeout_seconds=timeout_seconds,
        cwd=Path("/tmp"),
        env=None,
        run_dir=run_dir,
        parse_mode="json-stdout",
    )


def probe_claudeminmax(run_dir: Path, prompt: str, timeout_seconds: int) -> ProbeResult:
    cmd = ["claudeminmax", "-p", prompt, "--output-format", "json"]
    return _run(
        lane="claudeminmax",
        cmd=cmd,
        input_text=None,
        timeout_seconds=timeout_seconds,
        cwd=Path("/tmp"),
        env=None,
        run_dir=run_dir,
        parse_mode="json-stdout",
    )


def probe_hcom_start(run_dir: Path, timeout_seconds: int) -> ProbeResult:
    raw_path = run_dir / "hcom_start.raw.txt"
    cmd = ["bash", str(HCOM_START_SCRIPT), "--raw-out", str(raw_path)]
    return _run(
        lane="hcom_start",
        cmd=cmd,
        input_text=None,
        timeout_seconds=timeout_seconds,
        cwd=Path("/tmp"),
        env=None,
        run_dir=run_dir,
        parse_mode="json-stdout",
        extra_artifacts={"raw_output": str(raw_path)},
    )


def build_summary(results: list[ProbeResult], prompt: str, run_dir: Path) -> dict[str, Any]:
    lanes = {res.lane: asdict(res) for res in results}
    verdicts: list[str] = []
    codex_ambient = lanes.get("codex_ambient", {})
    if codex_ambient.get("ok") and codex_ambient.get("tokens_used"):
        verdicts.append("codex ambient lane works but is too heavy for microtasks")
    codex_isolated = lanes.get("codex_isolated", {})
    if not codex_isolated.get("ok") and "401" in str(codex_isolated.get("stderr_excerpt") or ""):
        verdicts.append("codex clean lane needs isolated auth bootstrap, not empty CODEX_HOME")
    codex_auth_only = lanes.get("codex_auth_only", {})
    if codex_auth_only.get("ok"):
        verdicts.append("codex auth-only lane is the right batch baseline: auth kept, MCP/config stripped")
    gemini_ambient = lanes.get("gemini_ambient", {})
    if "glm_router" in str(gemini_ambient.get("stderr_excerpt") or ""):
        verdicts.append("gemini ambient lane works but needs a clean MCP allowlist/profile")
    gemini_no_mcp = lanes.get("gemini_no_mcp", {})
    if gemini_no_mcp.get("ok"):
        verdicts.append("gemini no-MCP lane is the right cheap secondary-review baseline")
    claude = lanes.get("claudeminmax", {})
    if claude.get("ok"):
        verdicts.append("claudeminmax is the best current detached batch lane")
    hcom = lanes.get("hcom_start", {})
    hcom_text = json.dumps(hcom.get("parsed_output") or {}, ensure_ascii=False)
    if not hcom.get("ok") and ("hooks installed" in hcom_text or "notify hook" in str(hcom.get("stdout_excerpt") or "")):
        verdicts.append("hcom start is not idempotent on this machine because Codex notify hook is already occupied")
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "prompt": prompt,
        "run_dir": str(run_dir),
        "results": lanes,
        "verdicts": verdicts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Codex/Gemini/Claude/hcom batch lanes and write a unified JSON summary.")
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--prompt",
        default='Return exactly this JSON: {"ok":true,"mode":"runner_probe"}',
    )
    args = parser.parse_args()

    run_dir = Path(args.artifact_root).expanduser() / _now_tag()
    run_dir.mkdir(parents=True, exist_ok=True)

    results = [
        probe_codex_ambient(run_dir, args.prompt, args.timeout_seconds),
        probe_codex_isolated(run_dir, args.prompt, args.timeout_seconds),
        probe_codex_auth_only(run_dir, args.prompt, args.timeout_seconds),
        probe_gemini_ambient(run_dir, args.prompt, args.timeout_seconds),
        probe_gemini_no_mcp(run_dir, args.prompt, args.timeout_seconds),
        probe_claudeminmax(run_dir, args.prompt, args.timeout_seconds),
        probe_hcom_start(run_dir, args.timeout_seconds),
    ]
    summary = build_summary(results, args.prompt, run_dir)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "summary_path": str(summary_path), "run_dir": str(run_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
