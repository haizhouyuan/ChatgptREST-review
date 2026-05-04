# Paperclip Labebe Orchestrator

Orchestrator for **Labebe AI Transformation** (company ID `9ca70186-256c-49f4-8d87-038a94f32acb`), a PECL Stage 2 target company for Labebe DTC, Boss Gallery, commerce decision layer, and claim-safe evidence work.

## Task Types

| Task | Default Provider | Description |
|------|-----------------|-------------|
| `product_review_analysis` | claudekimi | Analyze Amazon/customer reviews for sentiment, themes, complaints |
| `dtc_copy` | minimax | Generate DTC marketing copy (headline, body, CTA, SEO) |
| `boss_gallery_card` | minimax | Generate Boss Gallery product card content |
| `commerce_decision` | claudekimi | Commerce decision layer analysis (pricing, channel fit, risk) |
| `evidence_bundle` | claudekimi | Assemble claim-safe evidence bundles with source attribution |

## Architecture

```
Paperclip API
    |
    v
run_from_paperclip(payload)
    |
    v
LabebeRequest (Pydantic validation)
    |
    v
_route_runtime()  -->  allocator_mvp.allocate()
    |
    v
Stub work function (per task_type)
    |
    v
LabebeResponse  -->  save_result()  -->  ~/.paperclip/labebe_reports/
```

## Usage

### From Paperclip (Python)

```python
from paperclip_labebe.labebe_orchestrator import run_from_paperclip

response = run_from_paperclip({
    "task_type": "dtc_copy",
    "input_content": "Organic cotton baby swaddle, 120x120cm, muslin fabric",
    "product_id": "LABE-SWADDLE-001",
    "output_language": "Chinese",
})
```

### CLI

```bash
# From JSON payload
python -m paperclip_labebe.labebe_orchestrator --payload '{"task_type":"dtc_copy","input_content":"test"}'

# From flags
python -m paperclip_labebe.labebe_orchestrator \
    --task-type product_review_analysis \
    --input-file reviews.txt \
    --product-id B071774PWC \
    --language Chinese

# With provider override
python -m paperclip_labebe.labebe_orchestrator \
    --task-type commerce_decision \
    --input "Should we expand to Amazon Japan?" \
    --provider claudekimi --debug
```

## Runtime Routing

Uses the shared `runtime_allocator/allocator_mvp.py` with task-specific quality tiers:

- **STANDARD** (dtc_copy, boss_gallery_card) -- minimax preferred, can degrade
- **HIGH** (product_review_analysis) -- claudekimi preferred, can degrade
- **CRITICAL** (commerce_decision, evidence_bundle) -- claudekimi pinned, no degradation

## Output

Results are saved to `~/.paperclip/labebe_reports/` as both JSON and Markdown files.

## Status

Current implementation uses **stub work functions** that return structured placeholders. The Paperclip integration skeleton (request/response models, allocator routing, persistence) is complete and ready for real pipeline wiring.
