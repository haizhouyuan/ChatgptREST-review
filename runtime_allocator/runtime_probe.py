"""Runtime health probe for Paperclip Skill Agent.

Probes each runtime endpoint to determine availability.
Supports: OpenAI-compatible, Gemini CLI, Ollama.

Usage:
    from runtime_allocator.runtime_probe import probe_all, ProbeResult
    results = probe_all()
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class ProbeResult:
    provider_id: str
    available: bool
    latency_ms: float = 0.0
    error: Optional[str] = None
    error_class: Optional[str] = None
    model_loaded: Optional[str] = None


def probe_openai_compatible(endpoint: str, provider_id: str, timeout: float = 5.0) -> ProbeResult:
    """Probe an OpenAI-compatible /v1/models endpoint."""
    start = time.monotonic()
    try:
        url = endpoint.rstrip("/") + "/models"
        resp = httpx.get(url, timeout=timeout)
        latency = (time.monotonic() - start) * 1000

        if resp.status_code == 200:
            data = resp.json()
            models = [m.get("id", "") for m in data.get("data", [])]
            return ProbeResult(
                provider_id=provider_id,
                available=True,
                latency_ms=latency,
                model_loaded=models[0] if models else None,
            )
        return ProbeResult(
            provider_id=provider_id,
            available=False,
            latency_ms=latency,
            error=f"HTTP {resp.status_code}: {resp.text[:200]}",
        )
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return ProbeResult(
            provider_id=provider_id,
            available=False,
            latency_ms=latency,
            error=str(e)[:200],
            error_class=e.__class__.__name__,
        )


def probe_gemini_cli(timeout: float = 10.0) -> ProbeResult:
    """Probe Gemini CLI availability via `gemini --version`."""
    start = time.monotonic()
    try:
        result = subprocess.run(
            ["gemini", "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        latency = (time.monotonic() - start) * 1000
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0] if result.stdout else "unknown"
            return ProbeResult(
                provider_id="gemini_local",
                available=True,
                latency_ms=latency,
                model_loaded=version,
            )
        return ProbeResult(
            provider_id="gemini_local",
            available=False,
            latency_ms=latency,
            error=f"exit {result.returncode}: {result.stderr[:200]}",
        )
    except FileNotFoundError:
        return ProbeResult(
            provider_id="gemini_local",
            available=False,
            latency_ms=(time.monotonic() - start) * 1000,
            error="gemini CLI not found in PATH",
            error_class="FileNotFoundError",
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(
            provider_id="gemini_local",
            available=False,
            latency_ms=timeout * 1000,
            error="gemini CLI probe timed out",
            error_class="TimeoutError",
        )
    except Exception as e:
        return ProbeResult(
            provider_id="gemini_local",
            available=False,
            latency_ms=(time.monotonic() - start) * 1000,
            error=str(e)[:200],
            error_class=e.__class__.__name__,
        )


def probe_by_protocol(endpoint: str, provider_id: str, protocol: str) -> ProbeResult:
    """Dispatch probe based on protocol type."""
    if protocol == "openai_compatible":
        return probe_openai_compatible(endpoint, provider_id)
    if protocol == "gemini_cli":
        return probe_gemini_cli()
    return ProbeResult(
        provider_id=provider_id,
        available=False,
        error=f"Unknown protocol: {protocol}",
    )


def probe_all(profiles: dict | None = None) -> list[ProbeResult]:
    """Probe all runtimes from profiles. Returns list of ProbeResult."""
    if profiles is None:
        from runtime_allocator.skill_agent import load_profiles
        profiles = load_profiles()

    results = []
    for pid, rt in profiles.get("runtimes", {}).items():
        if not rt.get("enabled", True):
            results.append(ProbeResult(provider_id=pid, available=False, error="disabled"))
            continue
        endpoint = rt.get("endpoint", "")
        protocol = rt.get("protocol", "openai_compatible")
        results.append(probe_by_protocol(endpoint, pid, protocol))
    return results


if __name__ == "__main__":
    results = probe_all()
    for r in results:
        status = "OK" if r.available else "DOWN"
        print(f"  {r.provider_id}: {status} ({r.latency_ms:.0f}ms)", end="")
        if r.error:
            print(f" — {r.error}")
        elif r.model_loaded:
            print(f" — {r.model_loaded}")
        else:
            print()
