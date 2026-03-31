from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _codex_bin() -> str:
    """Return an executable path for the `codex` CLI.

    systemd user services often run with a minimal PATH, so relying on `codex`
    being discoverable can fail even when the binary exists on disk.

    Resolution order:
    1) env: CHATGPTREST_CODEX_BIN / CODEX_BIN
    2) known wrapper installs under the current user
    3) PATH: shutil.which("codex")
    """

    raw = (os.environ.get("CHATGPTREST_CODEX_BIN") or os.environ.get("CODEX_BIN") or "").strip()
    if raw:
        return raw

    home = Path.home()
    candidates = [
        home / ".home-codex-official" / ".local" / "bin" / "codex",
        home / ".local" / "bin" / "codex",
        home / ".codex" / "bin" / "codex",
    ]
    for cand in candidates:
        try:
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(cand)
        except Exception:
            continue

    found = shutil.which("codex")
    if found:
        return found

    return "codex"


@dataclass(frozen=True)
class CodexExecResult:
    ok: bool
    returncode: int | None
    elapsed_ms: int
    cmd: list[str]
    stderr: str | None = None
    error_type: str | None = None
    error: str | None = None
    output: dict[str, Any] | None = None
    raw_output: str | None = None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(?P<body>[\s\S]*?)\s*```\s*$", re.IGNORECASE)


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


def _summarize_codex_error(stderr: str | None, stdout: str | None, *, limit: int = 2000) -> str:
    for raw in (stderr, stdout):
        text = str(raw or "").strip()
        if not text:
            continue
        marker = "ERROR:"
        if marker in text:
            tail = text.rsplit(marker, 1)[-1].strip()
            if tail:
                return f"ERROR: {tail}"[:limit]
        if len(text) > limit:
            return ("..." + text[-(limit - 3) :]) if limit > 3 else text[-limit:]
        return text
    return "codex exec failed"


def codex_exec_with_schema(
    *,
    prompt: str,
    schema_path: Path,
    out_json: Path,
    model: str | None = None,
    profile: str | None = None,
    timeout_seconds: int = 120,
    cd: Path | None = None,
    sandbox: str = "read-only",
    config_overrides: list[str] | None = None,
    enable_features: list[str] | None = None,
    disable_features: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> CodexExecResult:
    """
    Run `codex exec` with a JSON schema output file.

    This is intentionally a thin wrapper around the existing CLI usage, because the CLI provides the
    `--sandbox read-only` safety boundary. If/when a real Python SDK exists, it can be added behind a
    separate backend without removing the CLI path.
    """
    started_at = time.time()
    out_json.parent.mkdir(parents=True, exist_ok=True)

    cmd = [_codex_bin(), "exec"]
    for feat in enable_features or []:
        feat = str(feat or "").strip()
        if feat:
            cmd.extend(["--enable", feat])
    for feat in disable_features or []:
        feat = str(feat or "").strip()
        if feat:
            cmd.extend(["--disable", feat])
    if str(sandbox or "").strip():
        cmd.extend(["--sandbox", str(sandbox).strip()])
    if cd is not None:
        cmd.extend(["--cd", str(cd)])
    for kv in config_overrides or []:
        kv = str(kv or "").strip()
        if kv:
            cmd.extend(["-c", kv])
    cmd.extend(["--output-schema", str(schema_path), "-o", str(out_json), "-"])
    if model and str(model).strip():
        cmd.extend(["--model", str(model).strip()])
    if profile and str(profile).strip():
        cmd.extend(["--profile", str(profile).strip()])

    try:
        run_kwargs: dict[str, Any] = {
            "input": prompt,
            "text": True,
            "check": False,
            "capture_output": True,
            "timeout": float(max(1, int(timeout_seconds))),
        }
        if env is not None:
            run_kwargs["env"] = env
        p = subprocess.run(cmd, **run_kwargs)
    except Exception as exc:
        return CodexExecResult(
            ok=False,
            returncode=None,
            elapsed_ms=int(round((time.time() - started_at) * 1000)),
            cmd=cmd,
            error_type=type(exc).__name__,
            error=str(exc)[:800],
        )

    elapsed_ms = int(round((time.time() - started_at) * 1000))
    stderr = (p.stderr or "").strip()[:2000]
    if p.returncode != 0:
        err_text = _summarize_codex_error(p.stderr, p.stdout)
        return CodexExecResult(
            ok=False,
            returncode=int(p.returncode),
            elapsed_ms=elapsed_ms,
            cmd=cmd,
            stderr=stderr,
            error=err_text,
        )

    parsed = _read_json(out_json)
    if parsed is None:
        detail = _summarize_codex_error(p.stderr, p.stdout)
        return CodexExecResult(
            ok=False,
            returncode=int(p.returncode),
            elapsed_ms=elapsed_ms,
            cmd=cmd,
            stderr=stderr,
            error_type="ValueError",
            error=f"Failed to parse codex output JSON (missing/invalid out_json); detail={detail}",
        )

    return CodexExecResult(
        ok=True,
        returncode=int(p.returncode),
        elapsed_ms=elapsed_ms,
        cmd=cmd,
        stderr=stderr or None,
        output=parsed,
    )


def codex_resume_last_message_json(
    *,
    prompt: str,
    out_text: Path,
    model: str | None = None,
    profile: str | None = None,
    timeout_seconds: int = 120,
    cwd: Path | None = None,
    all_sessions: bool = False,
    config_overrides: list[str] | None = None,
    enable_features: list[str] | None = None,
    disable_features: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> CodexExecResult:
    """Resume the most recent Codex session in `cwd` and parse the last message as JSON."""
    started_at = time.time()
    out_text.parent.mkdir(parents=True, exist_ok=True)

    cmd = [_codex_bin(), "exec", "resume", "--last"]
    if all_sessions:
        cmd.append("--all")
    for feat in enable_features or []:
        feat = str(feat or "").strip()
        if feat:
            cmd.extend(["--enable", feat])
    for feat in disable_features or []:
        feat = str(feat or "").strip()
        if feat:
            cmd.extend(["--disable", feat])
    for kv in config_overrides or []:
        kv = str(kv or "").strip()
        if kv:
            cmd.extend(["-c", kv])
    if model and str(model).strip():
        cmd.extend(["--model", str(model).strip()])
    if profile and str(profile).strip():
        cmd.extend(["--profile", str(profile).strip()])
    cmd.extend(["-o", str(out_text), "-"])

    try:
        run_kwargs: dict[str, Any] = {
            "input": prompt,
            "text": True,
            "check": False,
            "capture_output": True,
            "timeout": float(max(1, int(timeout_seconds))),
        }
        if cwd is not None:
            run_kwargs["cwd"] = str(cwd)
        if env is not None:
            run_kwargs["env"] = env
        p = subprocess.run(cmd, **run_kwargs)
    except Exception as exc:
        return CodexExecResult(
            ok=False,
            returncode=None,
            elapsed_ms=int(round((time.time() - started_at) * 1000)),
            cmd=cmd,
            error_type=type(exc).__name__,
            error=str(exc)[:800],
        )

    elapsed_ms = int(round((time.time() - started_at) * 1000))
    stderr = (p.stderr or "").strip()[:2000]
    if p.returncode != 0:
        err_text = ((p.stderr or "").strip() or (p.stdout or "").strip() or "codex exec resume failed")[:2000]
        return CodexExecResult(
            ok=False,
            returncode=int(p.returncode),
            elapsed_ms=elapsed_ms,
            cmd=cmd,
            stderr=stderr,
            error=err_text,
        )

    raw_text = _read_text(out_text)
    parsed = _parse_json_text(raw_text)
    if parsed is None:
        return CodexExecResult(
            ok=False,
            returncode=int(p.returncode),
            elapsed_ms=elapsed_ms,
            cmd=cmd,
            stderr=stderr,
            error_type="ValueError",
            error="Failed to parse codex resume output JSON (missing/invalid out_text)",
            raw_output=(raw_text[:4000] if raw_text else None),
        )

    return CodexExecResult(
        ok=True,
        returncode=int(p.returncode),
        elapsed_ms=elapsed_ms,
        cmd=cmd,
        stderr=stderr or None,
        output=parsed,
        raw_output=(raw_text[:4000] if raw_text else None),
    )
