# Paperclip Runtime Allocator

Deterministic LLM routing with fallback, quota management, health probes,
and policy-driven provider selection.

## Quick Start

```bash
# Install dependencies
pip install fastapi uvicorn prometheus-client pydantic pyyaml httpx pytest
pip install pydantic-settings

# Run tests
make test

# Run the service
make run

# Run health probe scheduler
make probe
```

## Service Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | - | Service health |
| `/v1/health/providers` | GET | API key | Per-provider health |
| `/metrics` | GET | - | Prometheus metrics |
| `/v1/execute` | POST | API key | Execute task with fallback |
| `/v1/preflight` | POST | API key | Pre-execution safety check |
| `/v1/closeout` | POST | API key | Post-execution validation |
| `/v1/summary` | GET | Admin | Runtime state summary |
| `/v1/billing/daily` | GET | API key | Daily cost attribution |
| `/v1/billing/alerts` | GET | API key | Budget alerts |

## Configuration

All settings use `PAPERCLIP_` prefix:

```bash
PAPERCLIP_PORT=8080
PAPERCLIP_API_KEYS="dev-key:admin,prod-key:user"
PAPERCLIP_RATE_LIMIT_RPS=10
PAPERCLIP_WEBHOOK_URL="https://example.com/webhook"
PAPERCLIP_PROBE_INTERVAL_SECONDS=0  # background probes disabled by default
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Client    │────▶│   Service    │────▶│  PreflightGate  │
└─────────────┘     └──────────────┘     └─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ execute_with_fallback
                    │  - allocate()   │
                    │  - invoke_llm() │
                    │  - fallback     │
                    └─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  CloseoutGate   │
                    │  - webhook      │
                    └─────────────────┘
```

## Testing

```bash
make test              # All tests
make test-cov          # With coverage
make test-integration  # Integration tests
make test-concurrency  # 20x concurrency stress
```

## Docker

```bash
make docker-build
make docker-run PORT=8080
```

## CLI

```bash
python -m runtime_allocator.cli health
python -m runtime_allocator.cli summary
python -m runtime_allocator.cli billing --company-id acme
python -m runtime_allocator.cli audit --output /tmp/audit.ndjson
python -m runtime_allocator.cli cleanup --retention-days 30
python -m runtime_allocator.cli probe --provider-id minimax
python -m runtime_allocator.cli probe --provider-id custom --endpoint http://localhost:8000/v1 --protocol openai_compatible
```
