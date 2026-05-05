"""Runtime invoker for Paperclip Skill Agent.

Unified invocation interface for all runtime protocols:
- OpenAI-compatible (claudekimi, minimax, ollama)
- Gemini CLI (gemini_local)
- Process-based (future: local model processes)

Usage:
    from runtime_allocator.runtime_invoker import invoke_llm, InvokeResult
    result = invoke_llm(provider_id="claudekimi", messages=[...], model="mimo-v2.5-pro")
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx


@dataclass
class InvokeResult:
    provider_id: str
    model_name: str
    content: str = ""
    finish_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None
    error_class: Optional[str] = None
    raw_response: Optional[dict] = None


def _resolve_env(template: str) -> str:
    """Resolve ${VAR:default} patterns in endpoint strings."""
    if "${" not in template:
        return template
    import re
    def _replace(m):
        var_spec = m.group(1)
        if ":" in var_spec:
            var_name, default = var_spec.split(":", 1)
        else:
            var_name, default = var_spec, ""
        return os.getenv(var_name, default)
    return re.sub(r"\$\{([^}]+)\}", _replace, template)


def invoke_openai_compatible(
    endpoint: str,
    model: str,
    messages: list[dict],
    provider_id: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: Optional[dict] = None,
    timeout: float = 120.0,
    api_key: Optional[str] = None,
) -> InvokeResult:
    """Invoke an OpenAI-compatible chat completions endpoint."""
    start = time.monotonic()

    url = endpoint.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format

    try:
        resp = httpx.post(url, json=body, headers=headers, timeout=timeout)
        latency = (time.monotonic() - start) * 1000

        if resp.status_code != 200:
            return InvokeResult(
                provider_id=provider_id,
                model_name=model,
                latency_ms=latency,
                error=f"HTTP {resp.status_code}: {resp.text[:500]}",
                error_class=f"HTTP{resp.status_code}",
            )

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        return InvokeResult(
            provider_id=provider_id,
            model_name=model,
            content=message.get("content", ""),
            finish_reason=choice.get("finish_reason", ""),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency,
            raw_response=data,
        )

    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return InvokeResult(
            provider_id=provider_id,
            model_name=model,
            latency_ms=latency,
            error=str(e)[:500],
            error_class=e.__class__.__name__,
        )


def invoke_gemini_cli(
    prompt: str,
    model: str = "gemini-2.5-pro",
    system_prompt: Optional[str] = None,
    timeout: float = 120.0,
) -> InvokeResult:
    """Invoke Gemini CLI for text generation.

    Uses -p (headless) mode with -o text for clean output.
    System prompt is prepended to the user prompt since Gemini CLI
    doesn't have a separate --system-prompt flag.
    """
    start = time.monotonic()

    # Build the full prompt: system instructions + user content
    if system_prompt:
        full_prompt = f"[System Instructions]\n{system_prompt}\n\n[User Request]\n{prompt}"
    else:
        full_prompt = prompt

    # Pass prompt via stdin to avoid process-list exposure of sensitive text.
    cmd = ["gemini", "-p", "-", "-o", "text", "--skip-trust"]
    if model and model != "gemini-2.5-pro":
        cmd.extend(["-m", model])

    try:
        result = subprocess.run(
            cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        latency = (time.monotonic() - start) * 1000

        if result.returncode == 0:
            content = result.stdout.strip()
            # Clean up common Gemini CLI output artifacts
            if content.startswith("```"):
                # Remove markdown code fences if present
                lines = content.split("\n")
                if lines[0].startswith("```") and lines[-1].strip() == "```":
                    content = "\n".join(lines[1:-1]).strip()
            return InvokeResult(
                provider_id="gemini_local",
                model_name=model,
                content=content,
                finish_reason="stop",
                latency_ms=latency,
            )
        return InvokeResult(
            provider_id="gemini_local",
            model_name=model,
            latency_ms=latency,
            error=f"exit {result.returncode}: {result.stderr[:500]}",
            error_class="GeminiCLIError",
        )
    except subprocess.TimeoutExpired:
        return InvokeResult(
            provider_id="gemini_local",
            model_name=model,
            latency_ms=timeout * 1000,
            error="Gemini CLI timed out",
            error_class="TimeoutError",
        )
    except FileNotFoundError:
        return InvokeResult(
            provider_id="gemini_local",
            model_name=model,
            latency_ms=(time.monotonic() - start) * 1000,
            error="gemini CLI not found in PATH",
            error_class="FileNotFoundError",
        )
    except Exception as e:
        return InvokeResult(
            provider_id="gemini_local",
            model_name=model,
            latency_ms=(time.monotonic() - start) * 1000,
            error=str(e)[:500],
            error_class=e.__class__.__name__,
        )


def invoke_llm(
    provider_id: str,
    messages: list[dict],
    model: Optional[str] = None,
    profiles: Optional[dict] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: Optional[dict] = None,
    timeout: float = 120.0,
) -> InvokeResult:
    """Unified LLM invocation. Dispatches based on runtime profile protocol.

    Args:
        provider_id: Runtime provider ID (e.g. "claudekimi", "minimax", "gemini_local")
        messages: OpenAI-format messages list [{"role": ..., "content": ...}]
        model: Override model name (defaults to profile model_name)
        profiles: Runtime profiles dict (loaded from YAML)
        temperature: Sampling temperature
        max_tokens: Max output tokens
        response_format: Optional JSON mode spec
        timeout: Request timeout in seconds

    Returns:
        InvokeResult with content, tokens, latency, or error.
    """
    if profiles is None:
        try:
            from runtime_allocator.skill_agent import load_profiles
        except ImportError:
            from skill_agent import load_profiles
        profiles = load_profiles()

    rt = profiles.get("runtimes", {}).get(provider_id)
    if not rt:
        return InvokeResult(
            provider_id=provider_id,
            model_name=model or "unknown",
            error=f"Unknown provider: {provider_id}",
            error_class="ConfigError",
        )

    endpoint = _resolve_env(rt.get("endpoint", ""))
    protocol = rt.get("protocol", "openai_compatible")
    resolved_model = model or rt.get("model_name", "")

    if protocol == "openai_compatible":
        # Resolve API key from env based on provider
        api_key_env = {
            "claudekimi": "CLAUDEKIMI_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "ollama_gpu0": "",
        }.get(provider_id, "")
        api_key = os.getenv(api_key_env, "") if api_key_env else None

        return invoke_openai_compatible(
            endpoint=endpoint,
            model=resolved_model,
            messages=messages,
            provider_id=provider_id,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
            api_key=api_key,
        )

    if protocol == "gemini_cli":
        # Separate system and user messages for Gemini CLI
        system_parts = []
        user_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                user_parts.append(content)

        system_prompt = "\n\n".join(system_parts) if system_parts else None
        user_prompt = "\n\n".join(user_parts) if user_parts else ""

        return invoke_gemini_cli(
            prompt=user_prompt,
            model=resolved_model,
            system_prompt=system_prompt,
            timeout=timeout,
        )

    return InvokeResult(
        provider_id=provider_id,
        model_name=resolved_model,
        error=f"Unsupported protocol: {protocol}",
        error_class="ConfigError",
    )


if __name__ == "__main__":
    import sys
    provider = sys.argv[1] if len(sys.argv) > 1 else "claudekimi"
    test_messages = [{"role": "user", "content": "Say hello in one word."}]
    result = invoke_llm(provider, test_messages, max_tokens=50)
    if result.error:
        print(f"ERROR [{result.provider_id}]: {result.error}")
    else:
        print(f"OK [{result.provider_id}]: {result.content[:100]}")
        print(f"  tokens: {result.input_tokens}in/{result.output_tokens}out, {result.latency_ms:.0f}ms")
