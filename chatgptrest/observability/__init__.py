"""Langfuse observability — fail-open, privacy-first, low-overhead.

Provides:
  - get_langfuse() singleton (None if credentials missing)
  - start_request_trace() for root span per API request
  - record_generation() for LLM generation spans
  - Privacy: no prompt/response by default (LANGFUSE_CAPTURE_TEXT=1 to enable)

Credentials loaded from env vars (set via /vol1/maint/MAIN/secrets/credentials.env):
  LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL

Never logs credentials. All Langfuse errors are warn-only (fail-open).
"""

from __future__ import annotations

import logging
import os
import time
import threading
from typing import Any, Optional

from chatgptrest.core.path_resolver import credentials_env_candidates

logger = logging.getLogger(__name__)

# ── B8: Auto-load credentials from env file ──────────────────────

_CREDENTIALS_PATHS = credentials_env_candidates(start=__file__)


def _load_credentials_if_needed():
    """Load Langfuse credentials from env file if not already set.

    Only sets LANGFUSE_* vars that are missing from os.environ.
    Never logs credential values. Fail-open: never raises.
    """
    # Skip only if ALL recognized credential families are fully configured
    langfuse_set = os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")
    feishu_set = os.environ.get("FEISHU_WEBHOOK_SECRET")
    if langfuse_set and feishu_set:
        return  # all credentials already set

    for path in _CREDENTIALS_PATHS:
        if not os.path.isfile(path):
            continue
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    # Load recognized credential keys that aren't already set
                    _CRED_PREFIXES = ("LANGFUSE_", "FEISHU_", "QWEN_", "MINIMAX_")
                    if any(key.startswith(p) for p in _CRED_PREFIXES) and key not in os.environ:
                        os.environ[key] = val
            logger.debug("Loaded credentials from %s", path)
            return
        except Exception as e:
            logger.debug("Failed to read %s: %s", path, e)


_load_credentials_if_needed()

# ── Singleton ─────────────────────────────────────────────────────

_langfuse_instance = None
_langfuse_lock = threading.Lock()
_init_done = False


def get_langfuse():
    """Get Langfuse singleton. Returns None if not configured.

    Thread-safe, idempotent. Never raises on missing config.
    """
    global _langfuse_instance, _init_done

    if _init_done:
        return _langfuse_instance

    with _langfuse_lock:
        if _init_done:
            return _langfuse_instance

        pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        sk = os.environ.get("LANGFUSE_SECRET_KEY", "")
        host = os.environ.get("LANGFUSE_BASE_URL", "")

        if not (pk and sk and host):
            logger.info("Langfuse: disabled (missing credentials)")
            _init_done = True
            return None

        try:
            from langfuse import Langfuse

            _langfuse_instance = Langfuse(
                public_key=pk,
                secret_key=sk,
                host=host,
                timeout=int(os.environ.get("LANGFUSE_TIMEOUT", "15")),
                sample_rate=float(os.environ.get("LANGFUSE_SAMPLE_RATE", "1.0")),
                flush_at=int(os.environ.get("LANGFUSE_FLUSH_AT", "20")),
                flush_interval=float(os.environ.get("LANGFUSE_FLUSH_INTERVAL", "1")),
            )
            logger.info("Langfuse: initialized (host=%s)", host)
        except Exception as e:
            logger.warning("Langfuse: init failed (non-fatal): %s", e)
            _langfuse_instance = None

        _init_done = True
        return _langfuse_instance


def shutdown():
    """Flush and shutdown Langfuse. Call on app shutdown."""
    global _langfuse_instance, _init_done
    if _langfuse_instance:
        try:
            _langfuse_instance.flush()
        except Exception:
            pass
    _langfuse_instance = None
    _init_done = False


# ── Privacy helpers ───────────────────────────────────────────────

def _capture_text_enabled() -> bool:
    """Check if full text capture is enabled."""
    return os.environ.get("LANGFUSE_CAPTURE_TEXT", "0") in ("1", "true", "True")


def _safe_text(text: str, max_len: int = 500) -> Optional[str]:
    """Return text for Langfuse if capture is enabled, else None."""
    if not _capture_text_enabled():
        return None
    if not text:
        return None
    # Truncate to avoid memory issues
    return text[:max_len] + ("..." if len(text) > max_len else "")


def _has_active_trace(lf) -> bool:
    """Return whether Langfuse currently sees an active trace in context."""
    try:
        from opentelemetry import trace as otel_trace_api

        current_span = otel_trace_api.get_current_span()
        return current_span is not otel_trace_api.INVALID_SPAN
    except Exception:
        return False


# ── Request-level tracing ─────────────────────────────────────────

class RequestTrace:
    """Wrapper for a Langfuse request-level trace/span.

    Fail-open: all methods are no-op if Langfuse is None.

    Usage::

        trace = start_request_trace(
            name="advisor",
            user_id="u123",
            trace_id="tr_001",
            tags=["research"],
            metadata={"route": "deep_research"},
        )
        gen = trace.generation("llm_call", model="qwen3-coder-plus")
        gen.end(output_meta={"tokens": 500}, status="success")
        trace.end()
    """

    def __init__(self, lf, trace_id: str, root_span):
        self._lf = lf
        self._trace_id = trace_id
        self._root = root_span
        self._start = time.perf_counter()

    @property
    def trace_id(self) -> str:
        return self._trace_id

    def generation(
        self,
        name: str,
        *,
        model: str = "",
        model_parameters: dict | None = None,
        metadata: dict | None = None,
    ) -> "GenerationSpan":
        """Create a generation span for an LLM call."""
        if not self._root:
            return GenerationSpan(None)
        try:
            gen = self._root.start_as_current_observation(
                name=name,
                as_type="generation",
                model=model,
                model_parameters=model_parameters or {},
                input=None,  # privacy-first
                metadata=metadata or {},
                end_on_exit=False,
            )
            return GenerationSpan(gen.__enter__())
        except Exception as e:
            logger.warning("Langfuse generation failed: %s", e)
            return GenerationSpan(None)

    def span(self, name: str, metadata: dict | None = None) -> "SubSpan":
        """Create a child span (e.g., for tool calls, KB search)."""
        if not self._root:
            return SubSpan(None)
        try:
            sp = self._root.start_as_current_observation(
                name=name,
                as_type="span",
                input=None,
                metadata=metadata or {},
                end_on_exit=False,
            )
            return SubSpan(sp.__enter__())
        except Exception as e:
            logger.warning("Langfuse span failed: %s", e)
            return SubSpan(None)

    def update(self, **kwargs):
        """Update trace metadata."""
        if self._lf and _has_active_trace(self._lf):
            try:
                self._lf.update_current_trace(**kwargs)
            except Exception:
                pass

    def end(self):
        """End the root span."""
        if self._root:
            try:
                elapsed = (time.perf_counter() - self._start) * 1000
                self._root.update(
                    output={"latency_ms": round(elapsed)},
                )
                self._root.__exit__(None, None, None)
            except Exception:
                pass
        if self._lf:
            try:
                self._lf.flush()
            except Exception:
                pass


class GenerationSpan:
    """Wrapper for a Langfuse generation observation."""

    def __init__(self, obs):
        self._obs = obs
        self._start = time.perf_counter()

    def end(
        self,
        *,
        output_meta: dict | None = None,
        status: str = "success",
        usage: dict | None = None,
        error: str = "",
    ):
        if not self._obs:
            return
        try:
            elapsed = (time.perf_counter() - self._start) * 1000
            update_kwargs: dict[str, Any] = {
                "output": output_meta or {"status": status},
                "metadata": {"latency_ms": round(elapsed), "status": status},
            }
            if usage:
                update_kwargs["usage_details"] = usage
            if error:
                update_kwargs["metadata"]["error"] = error[:200]
                update_kwargs["level"] = "ERROR"
            self._obs.update(**update_kwargs)
            self._obs.__exit__(None, None, None)
        except Exception:
            pass


class SubSpan:
    """Wrapper for a Langfuse child span."""

    def __init__(self, obs):
        self._obs = obs
        self._start = time.perf_counter()

    def end(self, output: dict | None = None):
        if not self._obs:
            return
        try:
            elapsed = (time.perf_counter() - self._start) * 1000
            self._obs.update(
                output=output or {"latency_ms": round(elapsed)},
            )
            self._obs.__exit__(None, None, None)
        except Exception:
            pass


# No-op trace for when Langfuse is disabled
_NOOP_TRACE = RequestTrace(None, "", None)


def start_request_trace(
    *,
    name: str = "request",
    user_id: str = "",
    session_id: str = "",
    trace_id: str = "",
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> RequestTrace:
    """Start a request-level trace. Returns no-op if Langfuse disabled.

    Creates a root span and updates the trace with user/session info.
    """
    lf = get_langfuse()
    if not lf:
        return _NOOP_TRACE

    try:
        if not trace_id:
            trace_id = lf.create_trace_id(seed=f"req-{int(time.time())}")

        root = lf.start_as_current_observation(
            trace_context={"trace_id": trace_id},
            name=name,
            as_type="span",
            input=None,  # privacy-first
            end_on_exit=False,
        )
        root_span = root.__enter__()

        if _has_active_trace(lf):
            lf.update_current_trace(
                name=name,
                user_id=user_id or "anonymous",
                session_id=session_id or trace_id,
                tags=tags or ["openmind"],
                metadata=metadata or {},
            )

        return RequestTrace(lf, trace_id, root_span)
    except Exception as e:
        logger.warning("Langfuse trace start failed (non-fatal): %s", e)
        return _NOOP_TRACE
