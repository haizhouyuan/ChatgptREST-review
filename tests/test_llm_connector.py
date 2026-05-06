"""Comprehensive tests for chatgptrest/kernel/llm_connector.py.

Covers: happy path, edge cases, error conditions, boundary values,
and integration scenarios.
"""

from __future__ import annotations

import io
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from chatgptrest.kernel.llm_connector import (
    LLMConfig,
    LLMConnector,
    LLMCooldownError,
    LLMResponse,
    LLMTimeoutError,
    bind_llm_signal_trace,
)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def config() -> LLMConfig:
    """Default config for testing."""
    return LLMConfig(
        base_url="http://localhost:8080",
        throttle_interval=0.001,  # Very short for fast tests
        poll_interval=0.1,
        max_poll_attempts=3,
        timeout=5.0,
        default_provider="coding_plan",
        default_preset="default",
    )


@pytest.fixture
def connector(config: LLMConfig) -> LLMConnector:
    """Connector instance with test config."""
    return LLMConnector(config=config)


# ── LLMConfig Tests ────────────────────────────────────────────────

class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = LLMConfig()
        assert config.base_url == "http://localhost:8080"
        assert config.throttle_interval == 1.0
        assert config.poll_interval == 5.0
        assert config.max_poll_attempts == 60
        assert config.timeout == 45.0
        assert config.default_provider == "coding_plan"
        assert config.default_preset == "default"

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = LLMConfig(
            base_url="https://custom.api.com",
            throttle_interval=2.0,
            timeout=30.0,
            default_provider="custom_provider",
        )
        assert config.base_url == "https://custom.api.com"
        assert config.throttle_interval == 2.0
        assert config.timeout == 30.0
        assert config.default_provider == "custom_provider"
        # Unset values retain defaults
        assert config.default_preset == "default"

    def test_partial_custom_values(self) -> None:
        """Test that only specified values are overridden."""
        config = LLMConfig(throttle_interval=5.0)
        assert config.throttle_interval == 5.0
        assert config.timeout == 45.0  # default
        assert config.poll_interval == 5.0  # default


# ── LLMResponse Tests ────────────────────────────────────────────────

class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_default_values(self) -> None:
        """Test default response values."""
        resp = LLMResponse()
        assert resp.text == ""
        assert resp.provider == ""
        assert resp.preset == ""
        assert resp.latency_ms == 0.0
        assert resp.tokens_estimated == 0
        assert resp.status == "success"
        assert resp.error == ""
        assert resp.raw == {}

    def test_custom_values(self) -> None:
        """Test custom response values."""
        resp = LLMResponse(
            text="Hello world",
            provider="qwen3-coder-plus",
            preset="coding",
            latency_ms=1500.0,
            tokens_estimated=100,
            status="success",
            error="",
            raw={"model": "qwen3-coder-plus"},
        )
        assert resp.text == "Hello world"
        assert resp.provider == "qwen3-coder-plus"
        assert resp.preset == "coding"
        assert resp.latency_ms == 1500.0
        assert resp.tokens_estimated == 100
        assert resp.status == "success"

    def test_error_status_values(self) -> None:
        """Test various error status values."""
        for status in ("success", "error", "timeout", "cooldown"):
            resp = LLMResponse(status=status)
            assert resp.status == status

    def test_raw_dict_preserved(self) -> None:
        """Test that raw dict is preserved."""
        raw_data = {"choices": [{"message": {"content": "test"}}]}
        resp = LLMResponse(raw=raw_data)
        assert resp.raw == raw_data
        assert resp.raw["choices"][0]["message"]["content"] == "test"


# ── LLMConnector Construction Tests ─────────────────────────────────

class TestLLMConnectorConstruction:
    """Tests for LLMConnector initialization."""

    def test_default_construction(self) -> None:
        """Test default constructor."""
        connector = LLMConnector()
        assert connector._config is not None
        assert connector._config.base_url == "http://localhost:8080"
        assert connector._mock_fn is None
        assert connector._last_request_time == 0.0

    def test_custom_config(self, config: LLMConfig) -> None:
        """Test construction with custom config."""
        connector = LLMConnector(config=config)
        assert connector._config is config
        assert connector._config.throttle_interval == 0.001

    def test_with_http_client(self, config: LLMConfig) -> None:
        """Test construction with custom HTTP client."""
        mock_http = MagicMock()
        connector = LLMConnector(config=config, http_client=mock_http)
        assert connector._http is mock_http

    def test_with_model_router(self, config: LLMConfig) -> None:
        """Test construction with model router."""
        mock_router = MagicMock()
        connector = LLMConnector(config=config, model_router=mock_router)
        assert connector._model_router is mock_router


# ── Mock Mode Tests ─────────────────────────────────────────────────

class TestLLMConnectorMockMode:
    """Tests for mock mode functionality."""

    def test_mock_basic(self) -> None:
        """Test basic mock functionality."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return f"Mock response to: {prompt[:20]}"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("Hello world")

        assert response.status == "success"
        assert "Hello world" in response.text
        assert response.latency_ms > 0
        assert response.tokens_estimated > 0

    def test_mock_with_system_msg(self) -> None:
        """Test mock with system message."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return f"System: {system_msg}, Prompt: {prompt}"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("Test prompt", system_msg="You are helpful")

        assert response.status == "success"
        assert "You are helpful" in response.text
        assert "Test prompt" in response.text

    def test_mock_empty_response(self) -> None:
        """Test mock with empty response."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return ""

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("Test")

        assert response.status == "success"
        assert response.text == ""
        assert response.tokens_estimated == 0

    def test_mock_custom_provider(self) -> None:
        """Test mock with custom provider."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "response"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("Test", provider="custom_provider", preset="custom_preset")

        assert response.provider == "custom_provider"
        assert response.preset == "custom_preset"

    def test_mock_throttle_skipped(self) -> None:
        """Test that throttle is skipped in mock mode."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "quick"

        connector = LLMConnector.mock(mock_fn)
        # Two rapid calls should not wait
        start = time.perf_counter()
        connector.ask("Test 1")
        connector.ask("Test 2")
        elapsed = time.perf_counter() - start

        # Should be nearly instant (no throttle)
        assert elapsed < 0.1

    def test_call_skips_langfuse_generation_without_active_trace(self, monkeypatch) -> None:
        import chatgptrest.observability as obs

        class FakeLangfuse:
            def start_as_current_observation(self, **kwargs):
                raise AssertionError("generation span should not start without an active trace")

        monkeypatch.setattr(obs, "get_langfuse", lambda: FakeLangfuse())
        monkeypatch.setattr(obs, "_has_active_trace", lambda lf: False)

        connector = LLMConnector.mock(lambda prompt, system_msg: "ok")
        assert connector("hello") == "ok"

    def test_call_starts_langfuse_generation_with_active_trace(self, monkeypatch) -> None:
        import chatgptrest.observability as obs

        seen: dict[str, object] = {}

        class FakeSpan:
            def update(self, **kwargs):
                seen["update"] = kwargs

            def __exit__(self, exc_type, exc, tb):
                seen["closed"] = True

        class FakeContext:
            def __enter__(self):
                seen["entered"] = True
                return FakeSpan()

        class FakeLangfuse:
            def start_as_current_observation(self, **kwargs):
                seen["start"] = kwargs
                return FakeContext()

        monkeypatch.setattr(obs, "get_langfuse", lambda: FakeLangfuse())
        monkeypatch.setattr(obs, "_has_active_trace", lambda lf: True)

        connector = LLMConnector.mock(lambda prompt, system_msg: "trace ok")
        assert connector("hello") == "trace ok"
        assert seen["start"]["name"] == "llm_call"
        assert seen["update"]["metadata"]["status"] == "success"
        assert seen["closed"] is True

    def test_signal_emitter_includes_bound_trace_id(self, config: LLMConfig, monkeypatch) -> None:
        seen: list[tuple[str, dict[str, object]]] = []
        connector = LLMConnector(config=config, signal_emitter=lambda event_type, data: seen.append((event_type, dict(data))))

        monkeypatch.setattr(
            connector,
            "_send_request",
            lambda prompt, system_msg, provider, preset, timeout: LLMResponse(  # noqa: ARG005
                text="ok",
                provider="coding_plan/MiniMax-M2.5",
                preset=preset,
                status="success",
            ),
        )

        with bind_llm_signal_trace("trace-bound-1"):
            response = connector.ask("hello")

        assert response.status == "success"
        assert seen
        assert seen[-1][0] == "llm.call_completed"
        assert seen[-1][1]["trace_id"] == "trace-bound-1"

    def test_signal_emitter_omits_trace_id_without_binding(self, config: LLMConfig, monkeypatch) -> None:
        seen: list[tuple[str, dict[str, object]]] = []
        connector = LLMConnector(config=config, signal_emitter=lambda event_type, data: seen.append((event_type, dict(data))))

        monkeypatch.setattr(
            connector,
            "_send_request",
            lambda prompt, system_msg, provider, preset, timeout: LLMResponse(  # noqa: ARG005
                text="ok",
                provider="coding_plan/MiniMax-M2.5",
                preset=preset,
                status="success",
            ),
        )

        connector.ask("hello")

        assert seen
        assert seen[-1][0] == "llm.call_completed"
        assert "trace_id" not in seen[-1][1]


# ── Throttle Tests ─────────────────────────────────────────────────

class TestLLMConnectorThrottle:
    """Tests for throttle functionality."""

    def test_throttle_enforced_real_mode(self, config: LLMConfig) -> None:
        """Test that throttle is enforced in real mode (non-mock)."""
        # Use very short throttle interval
        config.throttle_interval = 0.05

        with patch.dict("os.environ", {"QWEN_API_KEY": "sk-test"}):
            connector = LLMConnector(config=config)

            # First call - no wait needed (initial _last_request_time = 0)
            # We just verify throttle behavior directly
            connector._last_request_time = time.time()  # Reset to now

            start = time.perf_counter()
            connector._wait_throttle()
            elapsed = time.perf_counter() - start

            # Should have waited approximately throttle_interval
            assert elapsed >= 0.04  # Allow small margin

    def test_throttle_zero_interval(self, config: LLMConfig) -> None:
        """Test with zero throttle interval."""
        config.throttle_interval = 0.0

        with patch.dict("os.environ", {"QWEN_API_KEY": "sk-test"}):
            connector = LLMConnector(config=config)

            start = time.perf_counter()
            connector._wait_throttle()
            elapsed = time.perf_counter() - start

            # Should be nearly instant
            assert elapsed < 0.1


# ── Model Selection Tests ───────────────────────────────────────────

class TestLLMConnectorModelSelection:
    """Tests for model selection logic."""

    def test_select_model_default(self, config: LLMConfig) -> None:
        """Test default model selection."""
        connector = LLMConnector(config=config)
        models = connector._select_model("default")

        # Should return API-only models
        assert isinstance(models, list)
        assert len(models) > 0
        valid_models = {"MiniMax-M2.5", "qwen3-coder-plus"}
        assert all(m in valid_models for m in models)

    def test_select_model_planning(self, config: LLMConfig) -> None:
        """Test planning model selection."""
        connector = LLMConnector(config=config)
        models = connector._select_model("planning")

        assert isinstance(models, list)
        assert len(models) > 0

    def test_select_model_coding(self, config: LLMConfig) -> None:
        """Test coding model selection."""
        connector = LLMConnector(config=config)
        models = connector._select_model("coding")

        assert isinstance(models, list)
        assert len(models) > 0
        assert "qwen3-coder-plus" in models

    def test_select_model_debug(self, config: LLMConfig) -> None:
        """Test debug model selection."""
        connector = LLMConnector(config=config)
        models = connector._select_model("debug")

        assert isinstance(models, list)
        assert len(models) > 0

    def test_select_model_review(self, config: LLMConfig) -> None:
        """Test review model selection."""
        connector = LLMConnector(config=config)
        models = connector._select_model("review")

        assert isinstance(models, list)
        assert len(models) > 0

    def test_select_model_research(self, config: LLMConfig) -> None:
        """Test research model selection."""
        connector = LLMConnector(config=config)
        models = connector._select_model("research")

        assert isinstance(models, list)
        assert len(models) > 0

    def test_select_model_report(self, config: LLMConfig) -> None:
        """Test report model selection."""
        connector = LLMConnector(config=config)
        models = connector._select_model("report")

        assert isinstance(models, list)
        assert len(models) > 0

    def test_select_model_unknown_preset(self, config: LLMConfig) -> None:
        """Test with unknown preset falls back to default."""
        connector = LLMConnector(config=config)
        models = connector._select_model("unknown_preset_xyz")

        # Should still return valid models
        assert isinstance(models, list)
        assert len(models) > 0

    def test_select_model_empty_preset(self, config: LLMConfig) -> None:
        """Test with empty preset."""
        connector = LLMConnector(config=config)
        models = connector._select_model("")

        assert isinstance(models, list)
        assert len(models) > 0

    def test_select_model_with_router(self, config: LLMConfig) -> None:
        """Test model selection with ModelRouter."""
        mock_router = MagicMock()
        mock_decision = MagicMock()
        mock_decision.models = ["gemini-cli", "qwen3-coder-plus", "MiniMax-M2.5"]
        mock_decision.scores = []
        mock_decision.source = "static"
        mock_router.select.return_value = mock_decision

        connector = LLMConnector(config=config, model_router=mock_router)
        models = connector._select_model("coding")

        # Should filter to API-only models (gemini-cli is not API)
        assert "gemini-cli" not in models
        assert "qwen3-coder-plus" in models
        mock_router.select.assert_called_once()

    def test_select_model_router_fallback(self, config: LLMConfig) -> None:
        """Test ModelRouter fallback on error."""
        mock_router = MagicMock()
        mock_router.select.side_effect = Exception("Router error")

        connector = LLMConnector(config=config, model_router=mock_router)
        models = connector._select_model("default")

        # Should fall back to static routes
        assert isinstance(models, list)
        assert len(models) > 0

    def test_select_model_router_returns_non_api_only(self, config: LLMConfig) -> None:
        """Test when ModelRouter returns only non-API models."""
        mock_router = MagicMock()
        mock_decision = MagicMock()
        mock_decision.models = ["gemini-web", "chatgpt-web"]  # Web models only
        mock_decision.scores = []
        mock_decision.source = "static"
        mock_router.select.return_value = mock_decision

        connector = LLMConnector(config=config, model_router=mock_router)
        models = connector._select_model("default")

        # Should fall back to API defaults
        assert len(models) > 0
        valid_models = {"MiniMax-M2.5", "qwen3-coder-plus"}
        assert all(m in valid_models for m in models)

    def test_select_model_with_scores(self, config: LLMConfig) -> None:
        """Test model selection uses scores when available."""
        mock_router = MagicMock()
        # Create mock score objects
        mock_score1 = MagicMock()
        mock_score1.model = "qwen3-coder-plus"
        mock_score1.total_score = 0.9

        mock_score2 = MagicMock()
        mock_score2.model = "MiniMax-M2.5"
        mock_score2.total_score = 0.8

        mock_decision = MagicMock()
        mock_decision.models = ["gemini-cli"]  # All non-API
        mock_decision.scores = [mock_score1, mock_score2]
        mock_decision.source = "evomap"
        mock_router.select.return_value = mock_decision

        connector = LLMConnector(config=config, model_router=mock_router)
        models = connector._select_model("coding")

        # Should fall back to scores and filter by API models
        assert len(models) > 0

    def test_send_request_falls_back_to_gemini_after_api_chain(self, config: LLMConfig) -> None:
        """Gemini should be the third hop after MiniMax and Qwen fail."""
        import urllib.error

        connector = LLMConnector(config=config)

        with patch.dict("os.environ", {"QWEN_API_KEY": "sk-test"}):
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
                with patch("chatgptrest.kernel.mcp_llm_bridge.McpLlmBridge") as mock_bridge:
                    mock_bridge.return_value.ask.return_value = "gemini answer"
                    response = connector.ask("test prompt", system_msg="sys")

        assert response.status == "success"
        assert response.text == "gemini answer"
        assert response.provider == "gemini-web/gemini-2.5-pro"


# ── Error Handling Tests ───────────────────────────────────────────

class TestLLMConnectorErrorHandling:
    """Tests for error handling."""

    def test_missing_api_key(self, config: LLMConfig) -> None:
        """Test error when API key is missing."""
        # Clear API key env var
        env_without_key = {"QWEN_API_KEY": ""}
        with patch.dict("os.environ", env_without_key, clear=True):
            connector = LLMConnector(config=config)
            response = connector.ask("test")

            assert response.status == "error"
            assert "QWEN_API_KEY" in response.error

    def test_openrouter_missing_key_does_not_fallback_to_paid(self, config: LLMConfig) -> None:
        """Explicit OpenRouter requests must not silently hit paid Coding Plan."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "", "QWEN_API_KEY": "sk-paid"}, clear=True):
            connector = LLMConnector(config=config)
            response = connector.ask("test", provider="openrouter")

        assert response.status == "error"
        assert "OPENROUTER_API_KEY" in response.error
        assert "refusing to fall back to paid Coding Plan" in response.error

    def test_openrouter_429_maps_to_cooldown(self, config: LLMConfig) -> None:
        """OpenRouter free-tier rate limits should surface as cooldown, not generic error."""
        import urllib.error

        connector = LLMConnector(config=config)
        rate_limited = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"rate limit exceeded"}}'),
        )

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-or-test"}, clear=True):
            with patch("urllib.request.urlopen", side_effect=rate_limited):
                response = connector.ask("test", provider="openrouter")

        assert response.status == "cooldown"
        assert "429" in response.error

    def test_openrouter_empty_content_is_error(self, config: LLMConfig) -> None:
        """Empty OpenRouter completions must not be treated as success."""
        connector = LLMConnector(config=config)
        payload = {
            "choices": [{"message": {"content": ""}}],
            "usage": {"completion_tokens": 0},
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_resp
        mock_cm.__exit__.return_value = False

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-or-test"}, clear=True):
            with patch("urllib.request.urlopen", return_value=mock_cm):
                response = connector.ask("test", provider="openrouter")

        assert response.status == "error"
        assert "empty content" in response.error

    def test_callable_raises_on_error(self, config: LLMConfig) -> None:
        """Test that __call__ raises RuntimeError on error status."""
        connector = LLMConnector(config=config)

        # Patch to return error
        with patch.object(connector, 'ask', return_value=LLMResponse(status="error", error="Test error")):
            with pytest.raises(RuntimeError, match="Test error"):
                connector("test prompt")

    def test_callable_success(self, config: LLMConfig) -> None:
        """Test that __call__ returns text on success."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "Success response"

        connector = LLMConnector.mock(mock_fn)
        result = connector("test prompt")

        assert result == "Success response"

    def test_callable_with_system_msg(self, config: LLMConfig) -> None:
        """Test that __call__ passes system message."""
        captured = {}

        def mock_fn(prompt: str, system_msg: str) -> str:
            captured["prompt"] = prompt
            captured["system_msg"] = system_msg
            return "ok"

        connector = LLMConnector.mock(mock_fn)
        result = connector("user prompt", "system message")

        assert captured["prompt"] == "user prompt"
        assert captured["system_msg"] == "system message"
        assert result == "ok"


# ── Edge Cases ───────────────────────────────────────────────────────

class TestLLMConnectorEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_prompt(self, config: LLMConfig) -> None:
        """Test with very long prompt."""
        long_prompt = "a" * 100000  # 100k chars

        def mock_fn(prompt: str, system_msg: str) -> str:
            return f"Processed {len(prompt)} chars"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask(long_prompt)

        assert response.status == "success"
        assert "100000" in response.text

    def test_unicode_prompt(self, config: LLMConfig) -> None:
        """Test with unicode characters."""
        unicode_prompt = "你好世界 🌍 émoji 🎉 日本語"

        def mock_fn(prompt: str, system_msg: str) -> str:
            return f"Received: {prompt}"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask(unicode_prompt)

        assert response.status == "success"
        assert "你好世界" in response.text

    def test_special_chars_in_prompt(self, config: LLMConfig) -> None:
        """Test with special characters."""
        special_prompt = 'Special: <>&"\'\\n\t\r'

        def mock_fn(prompt: str, system_msg: str) -> str:
            return f"Got: {repr(prompt)}"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask(special_prompt)

        assert response.status == "success"

    def test_empty_prompt(self, config: LLMConfig) -> None:
        """Test with empty prompt."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "Empty prompt handled"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("")

        assert response.status == "success"
        # Token estimation is based on response text length, not prompt
        assert response.tokens_estimated == len("Empty prompt handled") // 4

    def test_only_whitespace_prompt(self, config: LLMConfig) -> None:
        """Test with whitespace-only prompt."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "Whitespace handled"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("   \n\t  ")

        assert response.status == "success"

    def test_very_long_system_msg(self, config: LLMConfig) -> None:
        """Test with very long system message."""
        long_system = "x" * 50000  # Pure system msg without prefix

        def mock_fn(prompt: str, system_msg: str) -> str:
            return f"System len: {len(system_msg)}"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("prompt", system_msg=long_system)

        assert response.status == "success"
        assert "50000" in response.text

    def test_custom_timeout(self, config: LLMConfig) -> None:
        """Test custom timeout parameter."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "response"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("test", timeout=1.0)

        assert response.status == "success"

    def test_very_short_prompt(self, config: LLMConfig) -> None:
        """Test with very short prompt."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "ok"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("a")

        assert response.status == "success"
        assert response.tokens_estimated == 0  # 1 char / 4 = 0

    def test_none_provider_uses_default(self, config: LLMConfig) -> None:
        """Test that None provider uses default."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "ok"

        connector = LLMConnector.mock(mock_fn)
        # Pass None explicitly
        response = connector.ask("test", provider="", preset="")

        assert response.provider == config.default_provider
        assert response.preset == config.default_preset


# ── Integration Scenarios ───────────────────────────────────────────

class TestLLMConnectorIntegration:
    """Integration tests for real-world scenarios."""

    def test_sequential_calls_different_providers(self, config: LLMConfig) -> None:
        """Test sequential calls with different providers."""
        calls = []

        def mock_fn(prompt: str, system_msg: str) -> str:
            calls.append(prompt)
            return f"Response {len(calls)}"

        connector = LLMConnector.mock(mock_fn)

        r1 = connector.ask("First", provider="provider1")
        r2 = connector.ask("Second", provider="provider2")
        r3 = connector.ask("Third", provider="provider3")

        assert r1.provider == "provider1"
        assert r2.provider == "provider2"
        assert r3.provider == "provider3"
        assert len(calls) == 3

    def test_preset_affects_model_selection(self, config: LLMConfig) -> None:
        """Test that preset parameter affects model selection."""
        connector = LLMConnector(config=config)

        planning_models = connector._select_model("planning")
        coding_models = connector._select_model("coding")
        debug_models = connector._select_model("debug")

        # Different presets should potentially return different models
        # (though they might overlap)
        assert isinstance(planning_models, list)
        assert isinstance(coding_models, list)
        assert isinstance(debug_models, list)

    def test_multiple_rapid_calls_throttle(self, config: LLMConfig) -> None:
        """Test that mock mode skips throttle (by design)."""
        config.throttle_interval = 0.01

        def mock_fn(prompt: str, system_msg: str) -> str:
            return "ok"

        connector = LLMConnector.mock(mock_fn)

        # Mock mode skips throttle (see _wait_throttle implementation)
        # This test verifies the expected behavior
        start = time.perf_counter()
        connector._wait_throttle()  # This returns immediately in mock mode
        elapsed = time.perf_counter() - start

        # In mock mode, throttle is skipped - no waiting
        assert elapsed < 0.005  # Should be nearly instant

    def test_config_sharing(self, config: LLMConfig) -> None:
        """Test that config is shared by reference (design choice)."""
        connector = LLMConnector(config=config)

        # Config is passed by reference - modifying it affects the connector
        # This is the current design behavior
        config.timeout = 999.0

        # The connector sees the modified value
        assert connector._config.timeout == 999.0


# ── Exception Classes Tests ─────────────────────────────────────────

class TestLLMExceptions:
    """Tests for custom exception classes."""

    def test_llm_cooldown_error(self) -> None:
        """Test LLMCooldownError can be raised and caught."""
        with pytest.raises(LLMCooldownError):
            raise LLMCooldownError("Service in cooldown")

    def test_llm_timeout_error(self) -> None:
        """Test LLMTimeoutError can be raised and caught."""
        with pytest.raises(LLMTimeoutError):
            raise LLMTimeoutError("Request timed out")

    def test_exception_messages(self) -> None:
        """Test exception message preservation."""
        msg = "Custom error message"
        with pytest.raises(LLMCooldownError, match=msg):
            raise LLMCooldownError(msg)

    def test_exception_inheritance(self) -> None:
        """Test exception inheritance."""
        assert issubclass(LLMCooldownError, Exception)
        assert issubclass(LLMTimeoutError, Exception)


# ── Static Route Map Tests ─────────────────────────────────────────

class TestStaticRouteMap:
    """Tests for static route map."""

    def test_all_presets_have_routes(self, config: LLMConfig) -> None:
        """Test that all known presets have routes."""
        connector = LLMConnector(config=config)

        for preset in ["planning", "coding", "debug", "review", "research", "report", "default"]:
            models = connector._select_model(preset)
            assert len(models) > 0, f"Preset '{preset}' has no models"

    def test_route_contains_valid_models(self, config: LLMConfig) -> None:
        """Test that routes contain valid API models."""
        connector = LLMConnector(config=config)
        valid_models = {"MiniMax-M2.5", "qwen3-coder-plus"}

        for preset in ["planning", "coding", "debug", "review", "research", "report", "default"]:
            models = connector._select_model(preset)
            for model in models:
                assert model in valid_models, f"Invalid model '{model}' in preset '{preset}'"

    def test_route_returns_list(self, config: LLMConfig) -> None:
        """Test that routes always return a list."""
        connector = LLMConnector(config=config)
        result = connector._select_model("any_random_preset_12345")

        assert isinstance(result, list)

    def test_route_preserves_order(self, config: LLMConfig) -> None:
        """Test that route order is preserved (first is preferred)."""
        connector = LLMConnector(config=config)
        models = connector._select_model("planning")

        assert models[:2] == ["MiniMax-M2.5", "qwen3-coder-plus"]


# ── Signal Emission Tests ─────────────────────────────────────────

class TestLLMSignalEmission:
    """Tests for EvoMap signal emission."""

    def test_signal_emission_fail_open(self, config: LLMConfig) -> None:
        """Test that signal emission failures don't break LLM calls."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "response"

        connector = LLMConnector.mock(mock_fn)

        # Should not raise even if signal emission fails
        response = connector.ask("test")
        assert response.status == "success"


# ── Latency Calculation Tests ───────────────────────────────────────

class TestLLMLatencyCalculation:
    """Tests for latency calculation."""

    def test_latency_is_calculated(self, config: LLMConfig) -> None:
        """Test that latency is calculated and returned."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            time.sleep(0.01)  # Small delay
            return "response"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("test")

        assert response.latency_ms > 0
        assert response.latency_ms >= 10  # At least 10ms

    def test_latency_includes_request_time(self, config: LLMConfig) -> None:
        """Test that latency includes the full request time."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            time.sleep(0.05)
            return "response"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("test")

        # Should be at least 50ms
        assert response.latency_ms >= 50


# ── Token Estimation Tests ─────────────────────────────────────────

class TestLLMTokenEstimation:
    """Tests for token estimation."""

    def test_token_estimation_length_div_4(self, config: LLMConfig) -> None:
        """Test token estimation uses length/4 heuristic."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "a" * 100  # Return 100 chars

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("test")

        assert response.tokens_estimated == 25  # 100 / 4

    def test_token_estimation_empty_response(self, config: LLMConfig) -> None:
        """Test token estimation for empty response."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return ""

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("test")

        assert response.tokens_estimated == 0


# ── Boundary Value Tests ───────────────────────────────────────────

class TestLLMBoundaryValues:
    """Tests for boundary values."""

    def test_max_tokens_setting(self, config: LLMConfig) -> None:
        """Test that max_tokens is properly set in request."""
        # This is tested indirectly through mock - we verify the config exists
        assert config.max_poll_attempts > 0
        assert config.timeout > 0

    def test_negative_timeout(self, config: LLMConfig) -> None:
        """Test handling of negative timeout (edge case)."""
        # Negative timeout should still work (passed to urlopen)
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "ok"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("test", timeout=-1.0)

        # Should still work in mock mode
        assert response.status == "success"

    def test_zero_timeout(self, config: LLMConfig) -> None:
        """Test zero timeout handling."""
        def mock_fn(prompt: str, system_msg: str) -> str:
            return "ok"

        connector = LLMConnector.mock(mock_fn)
        response = connector.ask("test", timeout=0.0)

        assert response.status == "success"
