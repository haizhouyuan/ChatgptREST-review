"""
Unified LLM Backend for Funnel stages.

Routes to the best available LLM using the user's existing toolchain:
1. Codex CLI — OpenAI Pro membership → GPT-5.2 with thinking=xhigh
2. Gemini CLI — Google One Ultra membership → Gemini 3.1 Preview
3. MiniMax API — separate key (MM2.5, better for orchestration/coding)
4. OpenClaw agent CLI — always available fallback

NO API keys needed for Codex/Gemini — the user's memberships cover CLI access.

Model routing strategy (from user's guidance):
- Deep thinking: Codex (GPT-5.2 xhigh) or Gemini (3.1 Preview) → <60s
- Fast/coding/orchestration: MiniMax MM2.5 → <5s
- Fallback: OpenClaw planning agent → always available
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """LLM provider configuration, auto-detected from system."""

    # Codex CLI (OpenAI Pro membership → GPT-5.2)
    codex_cmd: str = "codex"
    codex_model: str = "gpt-5.2"
    codex_reasoning: str = "xhigh"  # thinking level

    # Gemini CLI (Google One Ultra → 3.1 Preview)
    gemini_cmd: str = "gemini"
    gemini_model: str = "gemini-2.5-pro"

    # MiniMax API (separate key, better for coding/orchestration)
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat/v1"
    minimax_model: str = "MiniMax-M1"
    minimax_env_file: str = str(
        Path.home() / ".openclaw" / "secrets" / "memory-embedding.env"
    )

    # OpenClaw fallback (always available)
    openclaw_cmd: str = "openclaw"
    openclaw_agent: str = "planning"

    # Routing preference
    default_provider: str = ""  # auto-detect

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load config, auto-detect available CLIs and keys."""
        cfg = cls()

        # Auto-load MiniMax key from OpenClaw secrets
        minimax_key = os.environ.get("MINIMAX_API_KEY", "")
        if not minimax_key:
            env_file = Path(cfg.minimax_env_file)
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "API_KEY" in line.split("=", 1)[0]:
                        _, _, val = line.partition("=")
                        minimax_key = val.strip().strip('"').strip("'")
                        break
        cfg.minimax_api_key = minimax_key

        # Auto-detect default provider by checking what's available
        codex_ok = _cli_exists(cfg.codex_cmd)
        gemini_ok = _cli_exists(cfg.gemini_cmd)

        if codex_ok:
            cfg.default_provider = "codex"
        elif gemini_ok:
            cfg.default_provider = "gemini"
        elif cfg.minimax_api_key:
            cfg.default_provider = "minimax"
        else:
            cfg.default_provider = "openclaw"

        return cfg

    def available_providers(self) -> list[str]:
        """List available providers in priority order."""
        providers = []
        if _cli_exists(self.codex_cmd):
            providers.append("codex")
        if _cli_exists(self.gemini_cmd):
            providers.append("gemini")
        if self.minimax_api_key:
            providers.append("minimax")
        providers.append("openclaw")
        return providers


def _cli_exists(cmd: str) -> bool:
    """Check if a CLI command exists on the system."""
    try:
        proc = subprocess.run(
            ["which", cmd], capture_output=True, text=True, timeout=3,
        )
        return proc.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# LLM Call Result
# ---------------------------------------------------------------------------

@dataclass
class LLMResult:
    """Result from an LLM call."""
    text: str = ""
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""
    ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text[:200] + "..." if len(self.text) > 200 else self.text,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "ok": self.ok,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Provider: Codex CLI (OpenAI Pro → GPT-5.2 xhigh)
# ---------------------------------------------------------------------------

def _call_codex(
    prompt: str,
    system: str = "",
    model: str = "gpt-5.2",
    reasoning: str = "xhigh",
    codex_cmd: str = "codex",
) -> LLMResult:
    """
    Call Codex CLI in non-interactive mode.

    Uses: codex exec -m MODEL --skip-git-repo-check PROMPT
    Output is captured via -o FILE.
    """
    import tempfile
    start = time.monotonic()

    full_prompt = prompt
    if system:
        full_prompt = f"[Instructions: {system}]\n\n{prompt}"

    # Write output to temp file to capture it reliably
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
        output_file = tmp.name

    cmd = [
        codex_cmd, "exec",
        "-m", model,
        "--skip-git-repo-check",
        "--ephemeral",          # don't persist session
        "-o", output_file,     # write last message here
        full_prompt[:12000],
    ]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            cwd="/tmp",  # avoid git repo issues
        )
        elapsed = (time.monotonic() - start) * 1000

        # Read output from file
        output_path = Path(output_file)
        text = ""
        if output_path.exists():
            text = output_path.read_text().strip()
            output_path.unlink(missing_ok=True)

        if not text and proc.stdout:
            text = proc.stdout.strip()

        if proc.returncode == 0 and text:
            return LLMResult(
                text=text,
                provider="codex",
                model=f"{model}",
                latency_ms=elapsed,
            )
        else:
            Path(output_file).unlink(missing_ok=True)
            return LLMResult(
                provider="codex", model=model,
                latency_ms=elapsed, ok=False,
                error=(proc.stderr or f"exit {proc.returncode}")[:300],
            )
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        Path(output_file).unlink(missing_ok=True)
        return LLMResult(
            provider="codex", model=model,
            latency_ms=elapsed, ok=False, error="timeout (180s)",
        )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        Path(output_file).unlink(missing_ok=True)
        return LLMResult(
            provider="codex", model=model,
            latency_ms=elapsed, ok=False, error=str(e),
        )


# ---------------------------------------------------------------------------
# Provider: Gemini CLI (Google Ultra → 3.1 Preview)
# ---------------------------------------------------------------------------

def _call_gemini(
    prompt: str,
    system: str = "",
    model: str = "gemini-2.5-pro",
    gemini_cmd: str = "gemini",
) -> LLMResult:
    """
    Call Gemini CLI in non-interactive (headless) mode.

    Uses: gemini -p "PROMPT" --model MODEL
    The -p flag = non-interactive/headless mode.
    """
    start = time.monotonic()

    full_prompt = prompt
    if system:
        full_prompt = f"[Instructions: {system}]\n\n{prompt}"

    cmd = [
        gemini_cmd,
        "-p", full_prompt[:12000],
        "--model", model,
    ]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180,
        )
        elapsed = (time.monotonic() - start) * 1000

        if proc.returncode == 0 and proc.stdout.strip():
            return LLMResult(
                text=proc.stdout.strip(),
                provider="gemini",
                model=model,
                latency_ms=elapsed,
            )
        else:
            return LLMResult(
                provider="gemini", model=model,
                latency_ms=elapsed, ok=False,
                error=(proc.stderr or f"exit {proc.returncode}")[:300],
            )
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        return LLMResult(
            provider="gemini", model=model,
            latency_ms=elapsed, ok=False, error="timeout (180s)",
        )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return LLMResult(
            provider="gemini", model=model,
            latency_ms=elapsed, ok=False, error=str(e),
        )


# ---------------------------------------------------------------------------
# Provider: MiniMax API (MM2.5 for coding/orchestration)
# ---------------------------------------------------------------------------

def _call_minimax(
    prompt: str,
    system: str = "",
    model: str = "MiniMax-M1",
    api_key: str = "",
    base_url: str = "https://api.minimax.chat/v1",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> LLMResult:
    """Call MiniMax API (OpenAI-compatible endpoint)."""
    import urllib.request

    start = time.monotonic()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        elapsed = (time.monotonic() - start) * 1000
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return LLMResult(
            text=choice["message"]["content"],
            provider="minimax",
            model=model,
            latency_ms=elapsed,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return LLMResult(
            provider="minimax", model=model,
            latency_ms=elapsed, ok=False, error=str(e),
        )


# ---------------------------------------------------------------------------
# Provider: OpenClaw agent CLI (always available)
# ---------------------------------------------------------------------------

def _call_openclaw(
    prompt: str,
    system: str = "",
    agent: str = "planning",
    openclaw_cmd: str = "openclaw",
) -> LLMResult:
    """Call an OpenClaw agent via CLI."""
    start = time.monotonic()

    full_prompt = prompt
    if system:
        full_prompt = f"[System: {system}]\n\n{prompt}"

    cmd = [
        openclaw_cmd, "agent",
        "--agent", agent,
        "-m", full_prompt[:8000],
        "--json",
    ]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
        elapsed = (time.monotonic() - start) * 1000

        if proc.returncode == 0:
            try:
                data = json.loads(proc.stdout)
                text = data.get("reply", data.get("message", proc.stdout))
            except json.JSONDecodeError:
                text = proc.stdout
            return LLMResult(
                text=str(text),
                provider="openclaw",
                model=f"agent:{agent}",
                latency_ms=elapsed,
            )
        else:
            return LLMResult(
                provider="openclaw", model=f"agent:{agent}",
                latency_ms=elapsed, ok=False,
                error=proc.stderr[:500] if proc.stderr else f"exit {proc.returncode}",
            )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return LLMResult(
            provider="openclaw", model=f"agent:{agent}",
            latency_ms=elapsed, ok=False, error=str(e),
        )


# ---------------------------------------------------------------------------
# Unified LLM Call
# ---------------------------------------------------------------------------

# Speed tiers for model routing
TIER_FAST = "fast"      # <5s: triage, classification → MiniMax
TIER_DEEP = "deep"      # <60s: analysis, option generation → Codex/Gemini
TIER_REASON = "reason"  # <180s: pre-mortem, complex reasoning → Codex xhigh


def llm_call(
    prompt: str,
    *,
    system: str = "",
    tier: str = TIER_DEEP,
    provider: str = "",  # Override auto-detection
    config: LLMConfig | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> LLMResult:
    """
    Unified LLM call with automatic model routing.

    Routing:
      TIER_FAST → MiniMax API (MM2.5, fast, good for coding)
      TIER_DEEP → Codex CLI (GPT-5.2 xhigh) or Gemini CLI (3.1 Preview)
      TIER_REASON → Codex CLI (GPT-5.2 xhigh) — deepest thinking
    """
    if config is None:
        config = LLMConfig.from_env()

    # Choose provider based on tier
    if not provider:
        if tier == TIER_FAST and config.minimax_api_key:
            provider = "minimax"
        else:
            provider = config.default_provider

    # Build fallback chain
    providers_to_try = [provider]
    for p in config.available_providers():
        if p not in providers_to_try:
            providers_to_try.append(p)

    for prov in providers_to_try:
        result: LLMResult | None = None

        if prov == "codex":
            result = _call_codex(
                prompt, system=system,
                model=config.codex_model,
                reasoning=config.codex_reasoning,
                codex_cmd=config.codex_cmd,
            )

        elif prov == "gemini":
            model = config.gemini_model
            result = _call_gemini(
                prompt, system=system,
                model=model,
                gemini_cmd=config.gemini_cmd,
            )

        elif prov == "minimax" and config.minimax_api_key:
            result = _call_minimax(
                prompt, system=system,
                model=config.minimax_model,
                api_key=config.minimax_api_key,
                base_url=config.minimax_base_url,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        elif prov == "openclaw":
            result = _call_openclaw(
                prompt, system=system,
                agent=config.openclaw_agent,
                openclaw_cmd=config.openclaw_cmd,
            )

        if result and result.ok:
            logger.info(
                f"LLM call [{tier}] → {result.provider}/{result.model} "
                f"({result.latency_ms:.0f}ms)"
            )
            return result
        elif result:
            logger.warning(
                f"LLM call [{tier}] {prov} failed: {result.error[:100]}. "
                f"Trying next..."
            )

    # All failed
    return LLMResult(
        ok=False,
        error=f"All providers failed: {providers_to_try}",
        provider="none",
    )
