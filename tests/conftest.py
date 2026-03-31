from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from convergence_fixtures import (  # noqa: E402
    FeishuGatewaySimulator,
    InMemoryAdvisorClient,
    MemoryManagerFixture,
    MockLLMConnector,
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "asyncio: run async tests via the repo-local asyncio runner",
    )


def pytest_pyfunc_call(pyfuncitem: pytest.Function):
    if pyfuncitem.get_closest_marker("asyncio") is None:
        return None
    test_fn = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_fn):
        return None
    kwargs = {
        name: pyfuncitem.funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames
    }
    asyncio.run(test_fn(**kwargs))
    return True


@pytest.fixture(autouse=True)
def _isolate_openmind_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep OpenMind v3 state local to each test run.

    The v3 advisor otherwise defaults to shared ~/.openmind databases and
    startup-side background jobs, which makes tests slow and flaky.
    """
    root = tmp_path / "openmind"
    root.mkdir()

    monkeypatch.setenv("OPENMIND_DB_PATH", str(root / "effects.db"))
    monkeypatch.setenv("OPENMIND_KB_DB", str(root / "kb_registry.db"))
    monkeypatch.setenv("OPENMIND_KB_SEARCH_DB", str(root / "kb_search.db"))
    monkeypatch.setenv("OPENMIND_KB_VEC_DB", str(root / "kb_vectors.db"))
    monkeypatch.setenv("OPENMIND_MEMORY_DB", str(root / "memory.db"))
    monkeypatch.setenv("OPENMIND_EVENTBUS_DB", str(root / "events.db"))
    monkeypatch.setenv("OPENMIND_EVOMAP_DB", str(root / "signals.db"))
    monkeypatch.setenv("OPENMIND_DEDUP_DB", str(root / "dedup.db"))
    monkeypatch.setenv("OPENMIND_CHECKPOINT_DB", str(root / "checkpoint.db"))
    monkeypatch.setenv("OPENMIND_PROJECTS_PATH", str(root / "projects"))
    monkeypatch.setenv("OPENMIND_KB_ARTIFACT_DIR", str(root / "kb"))
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(root / "evomap_knowledge.db"))
    monkeypatch.setenv("OPENMIND_ENABLE_ROUTING_WATCHER", "0")
    monkeypatch.setenv("OPENMIND_ENABLE_EVOMAP_STARTUP_RESCORE", "0")
    monkeypatch.setenv("OPENMIND_ENABLE_EVOMAP_EXTRACTORS", "0")


@pytest.fixture
def mock_llm_connector() -> MockLLMConnector:
    return MockLLMConnector()


@pytest.fixture
def in_memory_advisor_client() -> InMemoryAdvisorClient:
    return InMemoryAdvisorClient()


@pytest.fixture
def feishu_gateway_simulator(monkeypatch: pytest.MonkeyPatch):
    def _make(
        gateway,
        *,
        advisor_client: InMemoryAdvisorClient | None = None,
    ) -> FeishuGatewaySimulator:
        return FeishuGatewaySimulator(
            monkeypatch,
            gateway,
            advisor_client or InMemoryAdvisorClient(),
        )

    return _make


@pytest.fixture
def memory_manager_fixture(tmp_path: Path):
    fixture = MemoryManagerFixture(tmp_path / "fixture_memory.db")
    try:
        yield fixture
    finally:
        fixture.close()
