"""Tests for chatgptrest.api.client_ip — CIDR-validated client IP extraction."""
from __future__ import annotations

import os
from unittest import mock

import pytest
from starlette.testclient import TestClient

from chatgptrest.api.client_ip import (
    _ip_in_trusted,
    _trusted_cidrs,
    get_client_ip,
)


class _FakeClient:
    def __init__(self, host: str):
        self.host = host


class _FakeRequest:
    def __init__(self, *, client_host: str, xff: str = ""):
        self.client = _FakeClient(client_host)
        self._headers: dict[str, str] = {}
        if xff:
            self._headers["x-forwarded-for"] = xff

    @property
    def headers(self):
        return self._headers


class TestGetClientIp:
    def setup_method(self):
        _trusted_cidrs.cache_clear()

    def test_no_proxy_config_returns_direct(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHATGPTREST_TRUSTED_PROXY_CIDRS", None)
            _trusted_cidrs.cache_clear()
            req = _FakeRequest(client_host="1.2.3.4", xff="5.5.5.5, 6.6.6.6")
            assert get_client_ip(req) == "1.2.3.4"

    def test_direct_not_trusted_returns_direct(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}):
            _trusted_cidrs.cache_clear()
            req = _FakeRequest(client_host="1.2.3.4", xff="5.5.5.5")
            assert get_client_ip(req) == "1.2.3.4"

    def test_rightmost_trusted_removal(self) -> None:
        """XFF: [spoofed, real_client, proxy1] → should return real_client."""
        with mock.patch.dict(os.environ, {"CHATGPTREST_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}):
            _trusted_cidrs.cache_clear()
            req = _FakeRequest(
                client_host="10.0.0.1",  # direct is trusted proxy
                xff="9.9.9.9, 2.2.2.2, 10.0.0.5",  # →rightmost non-trusted is 2.2.2.2
            )
            assert get_client_ip(req) == "2.2.2.2"

    def test_all_trusted_returns_direct(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}):
            _trusted_cidrs.cache_clear()
            req = _FakeRequest(
                client_host="10.0.0.1",
                xff="10.0.0.2, 10.0.0.3",
            )
            assert get_client_ip(req) == "10.0.0.1"

    def test_malformed_xff_tokens_skipped(self) -> None:
        """Malformed IPs in XFF should be silently skipped."""
        with mock.patch.dict(os.environ, {"CHATGPTREST_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}):
            _trusted_cidrs.cache_clear()
            req = _FakeRequest(
                client_host="10.0.0.1",
                xff="not-an-ip, 1.2.3.4, 10.0.0.5",
            )
            assert get_client_ip(req) == "1.2.3.4"

    def test_empty_xff_returns_direct(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}):
            _trusted_cidrs.cache_clear()
            req = _FakeRequest(client_host="10.0.0.1", xff="")
            assert get_client_ip(req) == "10.0.0.1"


class TestTrustedCidrs:
    def setup_method(self):
        _trusted_cidrs.cache_clear()

    def test_empty_returns_empty(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHATGPTREST_TRUSTED_PROXY_CIDRS", None)
            assert _trusted_cidrs() == ()

    def test_multiple_cidrs(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_TRUSTED_PROXY_CIDRS": "10.0.0.0/8, 172.16.0.0/12"}):
            result = _trusted_cidrs()
            assert len(result) == 2

    def test_malformed_cidr_skipped(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_TRUSTED_PROXY_CIDRS": "not-a-cidr, 10.0.0.0/8"}):
            result = _trusted_cidrs()
            assert len(result) == 1


class TestIpInTrusted:
    def setup_method(self):
        _trusted_cidrs.cache_clear()

    def test_in_range(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}):
            _trusted_cidrs.cache_clear()
            assert _ip_in_trusted("10.0.0.1") is True

    def test_not_in_range(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}):
            _trusted_cidrs.cache_clear()
            assert _ip_in_trusted("1.2.3.4") is False

    def test_malformed_ip(self) -> None:
        with mock.patch.dict(os.environ, {"CHATGPTREST_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}):
            _trusted_cidrs.cache_clear()
            assert _ip_in_trusted("not-an-ip") is False
