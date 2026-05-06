import os
import threading

from chatgpt_web_mcp.env import _env_int_range
from chatgpt_web_mcp.proxy import _proxy_env_for_subprocess, _without_proxy_env


def test_without_proxy_env_overlapping_is_safe(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://example-proxy:7890")
    monkeypatch.setenv("HTTPS_PROXY", "http://example-proxy:7890")
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")

    t1_entered = threading.Event()
    t2_entered = threading.Event()
    t1_exited = threading.Event()
    t2_checked = threading.Event()
    errors: list[BaseException] = []

    def worker1() -> None:
        try:
            with _without_proxy_env():
                assert "HTTP_PROXY" not in os.environ
                t1_entered.set()
                assert t2_entered.wait(2)
            t1_exited.set()
            assert t2_checked.wait(2)
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)
            t1_entered.set()
            t1_exited.set()
            t2_checked.set()

    def worker2() -> None:
        try:
            with _without_proxy_env():
                assert "HTTP_PROXY" not in os.environ
                t2_entered.set()
                assert t1_entered.wait(2)

                # Ensure worker1 exits while worker2 is still inside.
                assert t1_exited.wait(2)

                # Proxy env must remain suppressed until the last context exits.
                assert "HTTP_PROXY" not in os.environ

                # Subprocesses should still see the baseline proxy env.
                sub_env = _proxy_env_for_subprocess()
                assert sub_env.get("HTTP_PROXY") == "http://example-proxy:7890"
                assert sub_env.get("NO_PROXY") == "localhost,127.0.0.1"

                t2_checked.set()
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)
            t2_entered.set()
            t2_checked.set()

    th1 = threading.Thread(target=worker1, daemon=True)
    th2 = threading.Thread(target=worker2, daemon=True)
    th1.start()
    th2.start()
    th1.join(5)
    th2.join(5)

    assert not th1.is_alive()
    assert not th2.is_alive()
    if errors:
        raise errors[0]

    assert os.environ.get("HTTP_PROXY") == "http://example-proxy:7890"
    assert os.environ.get("NO_PROXY") == "localhost,127.0.0.1"


def test_env_int_range_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("TEST_RANGE", "abc")
    assert _env_int_range("TEST_RANGE", 10, 20) == (10, 20)

    monkeypatch.setenv("TEST_RANGE", "100,xyz")
    assert _env_int_range("TEST_RANGE", 10, 20) == (10, 20)

    monkeypatch.setenv("TEST_RANGE", "30,5")
    assert _env_int_range("TEST_RANGE", 10, 20) == (5, 30)

    monkeypatch.setenv("TEST_RANGE", "7")
    assert _env_int_range("TEST_RANGE", 10, 20) == (7, 7)
