# Paperclip Runtime Allocator — Development Makefile

.PHONY: help test test-cov test-integration lint format run service probe

PYTHON := python3
VENV_ACTIVATE := source /vol1/1000/.venv/bin/activate
PORT ?= 8080

help:
	@echo "Available targets:"
	@echo "  test            Run all tests"
	@echo "  test-cov        Run tests with coverage"
	@echo "  test-integration Run integration tests only"
	@echo "  lint            Run ruff linter (if installed)"
	@echo "  format          Run ruff formatter (if installed)"
	@echo "  run             Run the FastAPI service"
	@echo "  service         Run service with uvicorn directly"
	@echo "  probe           Run health probe scheduler"
	@echo "  cli-health      Run CLI health check"
	@echo "  cli-summary     Run CLI summary"
	@echo "  docker-build    Build Docker image"
	@echo "  docker-run      Run Docker container"

test:
	$(VENV_ACTIVATE) && $(PYTHON) -m pytest runtime_allocator/tests -q

test-cov:
	$(VENV_ACTIVATE) && $(PYTHON) -m pytest runtime_allocator/tests --cov=runtime_allocator --cov-report=term-missing

test-integration:
	$(VENV_ACTIVATE) && $(PYTHON) -m pytest runtime_allocator/tests/integration -v

test-concurrency:
	@for i in $$(seq 1 20); do \
		$(VENV_ACTIVATE) && $(PYTHON) -m pytest runtime_allocator/tests/unit/test_runtime_state_concurrency.py -q || exit 1; \
	done

lint:
	-$(VENV_ACTIVATE) && ruff check runtime_allocator/

format:
	-$(VENV_ACTIVATE) && ruff format runtime_allocator/

run:
	$(VENV_ACTIVATE) && PAPERCLIP_PORT=$(PORT) $(PYTHON) -m runtime_allocator.service

service:
	$(VENV_ACTIVATE) && uvicorn runtime_allocator.service:app --host 0.0.0.0 --port $(PORT) --reload

probe:
	$(VENV_ACTIVATE) && $(PYTHON) -m runtime_allocator.probe_scheduler --interval 60

cli-health:
	$(VENV_ACTIVATE) && $(PYTHON) -m runtime_allocator.cli health

cli-summary:
	$(VENV_ACTIVATE) && $(PYTHON) -m runtime_allocator.cli summary

cli-billing:
	$(VENV_ACTIVATE) && $(PYTHON) -m runtime_allocator.cli billing

docker-build:
	docker build -t paperclip-runtime:latest .

docker-run:
	docker run -p $(PORT):8080 -e PAPERCLIP_API_KEYS=dev-key:admin paperclip-runtime:latest
