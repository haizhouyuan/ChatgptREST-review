# OpenMind Repo Snapshot

Generated: 2026-02-28

## Repository Path
`/vol1/1000/projects/openmind`

## Tree (depth=3)
./.venv/bin/Activate.ps1
./.venv/bin/activate
./.venv/bin/activate.csh
./.venv/bin/activate.fish
./.venv/bin/dotenv
./.venv/bin/f2py
./.venv/bin/fastapi
./.venv/bin/hf
./.venv/bin/httpx
./.venv/bin/isympy
./.venv/bin/jsondiff
./.venv/bin/jsonpatch
./.venv/bin/jsonpointer
./.venv/bin/markdown-it
./.venv/bin/normalizer
./.venv/bin/numpy-config
./.venv/bin/onnxruntime_test
./.venv/bin/pip
./.venv/bin/pip3
./.venv/bin/pip3.11
./.venv/bin/py.test
./.venv/bin/pygmentize
./.venv/bin/pytest
./.venv/bin/ruff
./.venv/bin/tiny-agents
./.venv/bin/tqdm
./.venv/bin/typer
./.venv/bin/uvicorn
./.venv/bin/watchfiles
./.venv/bin/websockets
./.venv/bin/wheel
./.venv/pyvenv.cfg
./README.md
./code review/01_OPENMIND_REPO_SNAPSHOT.md
./openmind.egg-info/PKG-INFO
./openmind.egg-info/SOURCES.txt
./openmind.egg-info/dependency_links.txt
./openmind.egg-info/requires.txt
./openmind.egg-info/top_level.txt
./openmind/__init__.py
./openmind/__pycache__/__init__.cpython-311.pyc
./openmind/advisor/__init__.py
./openmind/contracts/__init__.py
./openmind/evomap/__init__.py
./openmind/integrations/__init__.py
./openmind/kb/__init__.py
./openmind/kernel/__init__.py
./openmind/kernel/artifact_store.py
./openmind/kernel/event_bus.py
./openmind/kernel/policy_engine.py
./openmind/workflows/__init__.py
./pyproject.toml
./tests/__init__.py

## README.md
# OpenMind

Knowledge-centric autonomous task processing system.

## Architecture

```
User Request → Advisor Graph → [Quick Ask | Deep Research | Funnel Graph] → KB ↔ EvoMap
```

## Tech Stack

| Component | Choice |
|-----------|--------|
| Workflow Engine | LangGraph |
| Vector DB | Qdrant |
| Embedding | fastembed |
| Full-text Search | SQLite FTS5 + jieba |
| REST API | FastAPI |
| Observability | TraceEvent EventBus (SQLite) |
| Agent Execution | OpenClaw MCP |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## pyproject.toml
[project]
name = "openmind"
version = "0.1.0"
description = "Knowledge-centric autonomous task processing system"
requires-python = ">=3.11"
dependencies = [
    # Workflow engine
    "langgraph>=1.0.4",
    "langchain-core>=0.3.0",
    # Vector search
    "qdrant-client>=1.7.0",
    "fastembed>=0.7.0",
    # Full-text search (Chinese)
    "jieba>=0.42",
    # REST API
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    # Core
    "pydantic>=2.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.8",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["openmind*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 120
