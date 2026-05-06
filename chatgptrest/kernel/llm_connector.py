"""LLM Connector — abstraction over ChatgptREST HTTP API.

Handles:
  - 61-second throttle queue (ChatgptREST rate limit)
  - Poll-wait for completion
  - Chunked answer reassembly
  - Cooldown/blocked state detection
  - Timeout configuration
  - Mock mode for testing

This is the ONLY module that makes actual LLM calls.
All graph nodes use this connector instead of raw HTTP.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_llm_signal_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("llm_signal_trace_id", default="")

DEFAULT_API_MODEL_CHAIN: tuple[str, ...] = (
    "MiniMax-M2.5",
    "qwen3-coder-plus",
)


@contextlib.contextmanager
def bind_llm_signal_trace(trace_id: str):
    """Bind a request trace to downstream LLM telemetry emission.

    This keeps the external call surface unchanged while allowing graph-level
    execution paths to attach a stable business trace_id to llm.call_* events.
    """

    token = _llm_signal_trace_id.set(str(trace_id or "").strip())
    try:
        yield
    finally:
        _llm_signal_trace_id.reset(token)


# ── Configuration ─────────────────────────────────────────────────

@dataclass
class LLMConfig:
    """Configuration for the LLM connector."""
    base_url: str = "http://localhost:8080"
    throttle_interval: float = 1.0     # 1s between requests (Coding Plan API is fast)
    poll_interval: float = 5.0         # seconds between poll attempts (legacy)
    max_poll_attempts: int = 60
    timeout: float = 45.0              # 45s timeout (API responds in seconds)
    default_provider: str = "coding_plan"
    default_preset: str = "default"


# ── Response Models ───────────────────────────────────────────────

@dataclass
class LLMResponse:
    """Response from an LLM call."""
    text: str = ""
    provider: str = ""
    preset: str = ""
    latency_ms: float = 0.0
    tokens_estimated: int = 0
    status: str = "success"  # "success" | "error" | "timeout" | "cooldown"
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class LLMCooldownError(Exception):
    """Raised when the LLM service is in cooldown/blocked state."""
    pass


class LLMTimeoutError(Exception):
    """Raised when the LLM request times out."""
    pass


# ── Connector ─────────────────────────────────────────────────────

class LLMConnector:
    """Abstraction over ChatgptREST HTTP API.

    Usage::

        connector = LLMConnector(config=LLMConfig())
        response = connector.ask("What is the capital of France?")

        # With specific provider/preset
        response = connector.ask(
            "Analyze this", provider="chatgpt", preset="pro"
        )

        # Mock mode for testing
        connector = LLMConnector.mock(lambda p, s: "mock answer")
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        *,
        http_client: Any = None,
        model_router: Any = None,
        routing_fabric: Any = None,
        signal_emitter: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._config = config or LLMConfig()
        self._http = http_client
        self._last_request_time: float = 0.0
        self._mock_fn: Callable | None = None
        self._model_router = model_router  # ModelRouter instance (optional)
        self._routing_fabric = routing_fabric
        self._signal_emitter = signal_emitter

    @classmethod
    def mock(cls, fn: Callable[[str, str], str]) -> "LLMConnector":
        """Create a mock connector for testing."""
        conn = cls()
        conn._mock_fn = fn
        return conn

    def ask(
        self,
        prompt: str,
        *,
        system_msg: str = "",
        provider: str = "",
        preset: str = "",
        timeout: float | None = None,
    ) -> LLMResponse:
        """Send a prompt to the LLM and return the response.

        Handles throttling, polling, and error detection.
        """
        start = time.perf_counter()
        provider = provider or self._config.default_provider
        preset = preset or self._config.default_preset
        signal_trace_id = _llm_signal_trace_id.get().strip()

        # Mock mode (no throttle needed)
        if self._mock_fn:
            text = self._mock_fn(prompt, system_msg)
            elapsed = (time.perf_counter() - start) * 1000
            return LLMResponse(
                text=text,
                provider=provider,
                preset=preset,
                latency_ms=elapsed,
                tokens_estimated=len(text) // 4,
                status="success",
            )

        # Throttle (real mode only — P1-2 fix)
        self._wait_throttle()

        # Make request
        try:
            response = self._send_request(
                prompt, system_msg, provider, preset,
                timeout=timeout or self._config.timeout,
            )
            elapsed = (time.perf_counter() - start) * 1000
            response.latency_ms = elapsed
            signal_payload = {
                "model": response.provider or provider, "preset": preset,
                "latency_ms": int(elapsed), "status": "success",
                "tokens_est": response.tokens_estimated,
            }
            if signal_trace_id:
                signal_payload["trace_id"] = signal_trace_id
            self._emit_llm_signal("llm.call_completed", signal_payload)
            return response

        except LLMCooldownError as e:
            elapsed = (time.perf_counter() - start) * 1000
            signal_payload = {
                "model": provider, "error": "cooldown", "latency_ms": int(elapsed),
                "error_category": "rate_limit_429",
            }
            if signal_trace_id:
                signal_payload["trace_id"] = signal_trace_id
            self._emit_llm_signal("llm.call_failed", signal_payload)
            return LLMResponse(
                status="cooldown",
                error=str(e),
                provider=provider,
                preset=preset,
                latency_ms=elapsed,
            )
        except LLMTimeoutError as e:
            elapsed = (time.perf_counter() - start) * 1000
            signal_payload = {
                "model": provider, "error": "timeout", "latency_ms": int(elapsed),
                "error_category": "timeout",
            }
            if signal_trace_id:
                signal_payload["trace_id"] = signal_trace_id
            self._emit_llm_signal("llm.call_failed", signal_payload)
            return LLMResponse(
                status="timeout",
                error=str(e),
                provider=provider,
                preset=preset,
                latency_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("LLM request failed: %s", e)
            signal_payload = {
                "model": provider, "error": str(e)[:100], "latency_ms": int(elapsed),
                "error_category": self._classify_error(e),
            }
            if signal_trace_id:
                signal_payload["trace_id"] = signal_trace_id
            self._emit_llm_signal("llm.call_failed", signal_payload)
            return LLMResponse(
                status="error",
                error=str(e),
                provider=provider,
                preset=preset,
                latency_ms=elapsed,
            )

    def _emit_llm_signal(self, signal_type: str, data: dict) -> None:
        """Emit EvoMap signal for LLM observability. Fail-open."""
        if not self._signal_emitter:
            return
        try:
            self._signal_emitter(signal_type, dict(data))
        except Exception:
            pass

    def attach_routing_fabric(self, routing_fabric: Any) -> None:
        self._routing_fabric = routing_fabric

    def set_signal_emitter(self, signal_emitter: Callable[[str, dict[str, Any]], None] | None) -> None:
        self._signal_emitter = signal_emitter

    @staticmethod
    def _classify_error(exc: Exception) -> str:
        """Classify an exception into error_category for CircuitBreaker.

        Maps Python exceptions to the categories consumed by
        CircuitBreaker._INFRA_ERRORS / _FATAL_ERRORS.
        """
        import urllib.error
        if isinstance(exc, urllib.error.HTTPError):
            code = exc.code
            if code in (401, 403):
                return "auth_error"
            elif code == 429:
                return "rate_limit_429"
            elif code == 500:
                return "provider_500"
            elif code == 502:
                return "provider_502"
            elif code == 503:
                return "provider_503"
            elif code == 504:
                return "provider_504"
            elif code == 529:
                # Anthropic/MiniMax overloaded
                return "provider_503"
            elif code == 402:
                # Billing/quota exhausted
                return "auth_error"
            return "unknown"
        if isinstance(exc, (urllib.error.URLError, ConnectionError, OSError)):
            # TimeoutError is subclass of OSError — check it first
            if isinstance(exc, TimeoutError):
                return "timeout"
            return "connection_error"
        # Check error string for known patterns
        err_str = str(exc).lower()
        if "auth" in err_str or "401" in err_str or "403" in err_str:
            return "auth_error"
        if "timeout" in err_str:
            return "timeout"
        if "connection" in err_str:
            return "connection_error"
        if "overloaded" in err_str or "529" in err_str:
            return "provider_503"
        if "billing" in err_str or "quota" in err_str or "insufficient" in err_str:
            return "auth_error"
        return "unknown"

    def _wait_throttle(self) -> None:
        """Wait for throttle interval since last request."""
        if self._mock_fn:
            return  # Skip throttle in mock mode (P1-2 fix)
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._config.throttle_interval:
            wait = self._config.throttle_interval - elapsed
            logger.debug("Throttling: waiting %.1fs", wait)
            time.sleep(wait)
        self._last_request_time = time.time()

    # ── Intent-to-Model Routing ────────────────────────────────────

    # Static fallback map (used when ModelRouter is not available)
    # API-only fallback order shared by direct Coding Plan callers.
    _STATIC_ROUTE_MAP: dict[str, list[str]] = {
        "planning":  list(DEFAULT_API_MODEL_CHAIN),
        "coding":    list(DEFAULT_API_MODEL_CHAIN),
        "debug":     list(DEFAULT_API_MODEL_CHAIN),
        "review":    list(DEFAULT_API_MODEL_CHAIN),
        "research":  list(DEFAULT_API_MODEL_CHAIN),
        "report":    list(DEFAULT_API_MODEL_CHAIN),
        "default":   list(DEFAULT_API_MODEL_CHAIN),
    }

    def _select_model(self, preset: str) -> list[str]:
        """Select model chain based on preset/intent.

        Uses ModelRouter (three-source fusion) when available,
        then falls back to RoutingFabric, then static route map.

        IMPORTANT: This connector can only call Coding Plan API models.
        Web/CLI MCP models are filtered out — they need MCP invocation
        which happens at the graph/orchestrator level, not here.
        """
        # API-only models that work with Coding Plan API.
        API_MODELS = set(DEFAULT_API_MODEL_CHAIN)

        if self._routing_fabric:
            try:
                from chatgptrest.kernel.routing import RouteRequest

                route = self._routing_fabric.resolve(RouteRequest(task_type=preset or "default"))
                api_only = route.api_only()
                if api_only:
                    logger.debug("RoutingFabric api_only: %s", api_only)
                    return api_only
            except Exception as e:
                logger.warning("RoutingFabric failed, falling back: %s", e)

        # Use ModelRouter if available
        if self._model_router:
            try:
                decision = self._model_router.select(preset or "default")
                if decision.models:
                    # Filter to API-only models for this connector
                    api_models = [m for m in decision.models if m in API_MODELS]
                    if not api_models:
                        # All selected models are web/CLI — fall back to API defaults
                        api_models = [s.model for s in sorted(
                            [s for s in decision.scores if s.model in API_MODELS],
                            key=lambda s: s.total_score, reverse=True,
                        )][:3]
                        if not api_models:
                            api_models = list(DEFAULT_API_MODEL_CHAIN)
                    logger.debug(
                        "ModelRouter selected: %s (api-filtered from %s) [%s]",
                        api_models, decision.models, decision.source,
                    )
                    return api_models
            except Exception as e:
                logger.warning("ModelRouter failed, falling back to static: %s", e)

        # Static fallback — also filter to API-only
        preset_lower = (preset or "").lower()
        for key in self._STATIC_ROUTE_MAP:
            if key in preset_lower:
                chain = self._STATIC_ROUTE_MAP[key]
                api_chain = [m for m in chain if m in API_MODELS]
                return api_chain or list(DEFAULT_API_MODEL_CHAIN)
        default = self._STATIC_ROUTE_MAP["default"]
        api_default = [m for m in default if m in API_MODELS]
        return api_default or list(DEFAULT_API_MODEL_CHAIN)

    def _send_request(
        self,
        prompt: str,
        system_msg: str,
        provider: str,
        preset: str,
        timeout: float,
    ) -> LLMResponse:
        """Send request to LLM API (Coding Plan, OpenRouter, or fallback chain).

        Provider selection:
        - "openrouter": OpenRouter API (free tier)
        - "coding_plan": Alibaba Coding Plan (default, paid)
        - any other value: falls back to Coding Plan chain
        """
        import json
        import urllib.request
        import urllib.error

        if provider == "openrouter":
            return self._send_openrouter_request(
                prompt=prompt,
                system_msg=system_msg,
                preset=preset,
                timeout=timeout,
            )

        # Default: Coding Plan chain (existing behavior)
        base_url = os.environ.get(
            "QWEN_BASE_URL",
            "https://coding.dashscope.aliyuncs.com/v1",
        )
        api_key = os.environ.get("QWEN_API_KEY", "")

        if not api_key:
            raise RuntimeError(
                "QWEN_API_KEY not set. "
                "Set it to your sk-sp-* key for Coding Plan access."
            )

        models = self._select_model(preset)
        last_error = ""

        for model in models:
            # Build OpenAI chat completions payload
            messages = []
            if system_msg:
                messages.append({"role": "system", "content": system_msg})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 8192,
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            url = f"{base_url}/chat/completions"
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=req_data, headers=headers, method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    result = json.loads(resp.read())

                # Extract response text
                choices = result.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "")
                else:
                    text = ""

                usage = result.get("usage", {})
                return LLMResponse(
                    text=text,
                    provider=f"coding_plan/{model}",
                    preset=preset,
                    tokens_estimated=usage.get("completion_tokens", len(text) // 4),
                    status="success",
                    raw=result,
                )

            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:300]
                last_error = f"{model}: HTTP {e.code} — {body}"
                logger.warning("Model %s failed: %s", model, last_error)

                # 401/403: auth failure, don't retry other models on same provider
                if e.code in (401, 403):
                    raise LLMCooldownError(
                        f"Auth failed for {model}: {last_error}"
                    )
                # 429/5xx: try fallback
                continue

            except urllib.error.URLError as e:
                last_error = f"{model}: connection error — {e.reason}"
                logger.warning("Model %s unreachable: %s", model, last_error)
                continue

            except Exception as e:
                last_error = f"{model}: {e}"
                logger.warning("Model %s error: %s", model, last_error)
                continue

        gemini_response = self._send_gemini_fallback(
            prompt=prompt,
            system_msg=system_msg,
            preset=preset,
            timeout=timeout,
        )
        if gemini_response is not None:
            return gemini_response

        # All Coding Plan models failed — try MiniMax Anthropic direct
        minimax_key = os.environ.get("MINIMAX_API_KEY", "")
        minimax_url = os.environ.get(
            "MINIMAX_ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic"
        )
        if minimax_key:
            try:
                messages_a = []
                if system_msg:
                    messages_a.append({"role": "user", "content": f"[System] {system_msg}"})
                messages_a.append({"role": "user", "content": prompt})

                payload_a = {
                    "model": "MiniMax-M2.5",
                    "max_tokens": 8192,
                    "messages": messages_a,
                }
                headers_a = {
                    "Content-Type": "application/json",
                    "x-api-key": minimax_key,
                    "anthropic-version": "2023-06-01",
                }
                url_a = f"{minimax_url}/v1/messages"
                req_a = urllib.request.Request(
                    url_a, data=json.dumps(payload_a).encode("utf-8"),
                    headers=headers_a, method="POST",
                )
                with urllib.request.urlopen(req_a, timeout=timeout) as resp_a:
                    result_a = json.loads(resp_a.read())

                # Anthropic response format: {"content": [{"type": "text", "text": "..."}]}
                content = result_a.get("content", [])
                text = ""
                for block in content:
                    if block.get("type") == "text":
                        text += block.get("text", "")

                return LLMResponse(
                    text=text,
                    provider="minimax_anthropic/MiniMax-M2.5",
                    preset=preset,
                    tokens_estimated=len(text) // 4,
                    status="success",
                    raw=result_a,
                )
            except Exception as e:
                last_error = f"MiniMax-Anthropic: {e}"
                logger.warning("MiniMax Anthropic fallback failed: %s", e)

        # All providers failed
        raise RuntimeError(f"All models failed. Last error: {last_error}")

    def _send_openrouter_request(
        self,
        *,
        prompt: str,
        system_msg: str,
        preset: str,
        timeout: float,
    ) -> LLMResponse:
        """Send request to OpenRouter API (free tier).

        Uses OPENROUTER_API_KEY and OPENROUTER_BASE_URL env vars.
        Default model: nvidia/nemotron-3-super-120b-a12b:free
        """
        import json
        import urllib.request
        import urllib.error

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        base_url = os.environ.get(
            "OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1",
        )
        model = os.environ.get(
            "OPENROUTER_DEFAULT_MODEL",
            "nvidia/nemotron-3-super-120b-a12b:free",
        )

        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not set. "
                "OpenRouter was requested explicitly, so refusing to fall back to paid Coding Plan."
            )

        messages = []
        if system_msg:
            messages.append({"role": "system", "content": system_msg})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 4096,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://chatgptrest.local",
            "X-Title": "ChatgptREST finbotfree",
        }

        url = f"{base_url}/chat/completions"
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=req_data, headers=headers, method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read())

            choices = result.get("choices", [])
            message = choices[0].get("message", {}) if choices else {}
            content = message.get("content")
            if isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        text_part = block.get("text")
                        if isinstance(text_part, str):
                            parts.append(text_part)
                text = "".join(parts)
            elif isinstance(content, str):
                text = content
            else:
                text = ""

            if not text.strip():
                raise RuntimeError(f"OpenRouter returned empty content for model {model}")

            usage = result.get("usage", {})
            return LLMResponse(
                text=text,
                provider=f"openrouter/{model}",
                preset=preset,
                tokens_estimated=usage.get("completion_tokens", len(text) // 4),
                status="success",
                raw=result,
            )

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            error_msg = f"OpenRouter HTTP {e.code}: {body}"
            logger.warning("OpenRouter failed: %s", error_msg)
            if e.code == 429:
                raise LLMCooldownError(error_msg)
            if e.code in (401, 403):
                raise LLMCooldownError(f"Auth failed for OpenRouter: {error_msg}")
            raise RuntimeError(error_msg)

        except urllib.error.URLError as e:
            error_msg = f"OpenRouter connection error: {e.reason}"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        except Exception as e:
            error_msg = f"OpenRouter error: {e}"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

    def _send_gemini_fallback(
        self,
        *,
        prompt: str,
        system_msg: str,
        preset: str,
        timeout: float,
    ) -> LLMResponse | None:
        """Try Gemini after the Coding Plan API chain is exhausted."""
        try:
            from chatgptrest.kernel.mcp_llm_bridge import McpLlmBridge

            bridge = McpLlmBridge(timeout=max(1, int(timeout)))
            text = bridge.ask("gemini-web", prompt, system_msg)
            if not text.strip():
                return None
            return LLMResponse(
                text=text,
                provider="gemini-web/gemini-2.5-pro",
                preset=preset,
                tokens_estimated=len(text) // 4,
                status="success",
                raw={"fallback": "gemini-web"},
            )
        except Exception as e:
            logger.warning("Gemini fallback failed: %s", e)
            return None

    # ── Convenience ───────────────────────────────────────────────

    def __call__(self, prompt: str, system_msg: str = "") -> str:
        """Callable interface for compatibility with graph nodes.

        Raises RuntimeError on failure (P1 fix: don't silently degrade).
        Instruments with Langfuse generation span if available.
        """
        # Start Langfuse generation span
        gen_span = None
        try:
            from chatgptrest.observability import _has_active_trace, get_langfuse
            lf = get_langfuse()
            if lf and _has_active_trace(lf):
                gen_span = lf.start_as_current_observation(
                    name="llm_call",
                    as_type="generation",
                    model=self._select_model(self._config.default_preset)[0],
                    model_parameters={"max_tokens": 8192},
                    input=None,  # privacy-first
                    end_on_exit=False,
                ).__enter__()
        except Exception:
            pass

        response = self.ask(prompt, system_msg=system_msg)

        # End Langfuse generation span
        if gen_span:
            try:
                gen_span.update(
                    output=None,  # privacy-first
                    metadata={
                        "status": response.status,
                        "latency_ms": round(response.latency_ms),
                        "provider": response.provider,
                        "preset": response.preset,
                    },
                    usage_details={
                        "input": len(prompt) // 4,  # rough estimate
                        "output": response.tokens_estimated,
                    },
                    **({"level": "ERROR"} if response.status != "success" else {}),
                )
                gen_span.__exit__(None, None, None)
            except Exception:
                pass

        if response.status != "success":
            raise RuntimeError(
                f"LLM call failed (status={response.status}): {response.error}"
            )
        return response.text
