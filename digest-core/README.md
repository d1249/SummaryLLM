# digest-core

Daily corporate communications digest with privacy-first design and LLM-powered action extraction.

## Features

- **EWS Integration**: NTLM authentication, corporate CA trust, incremental sync
- **Privacy-First**: PII masking before LLM processing with `[[REDACT:TYPE]]` markers
- **Idempotent**: T-48h rebuild window for deterministic results
- **Observability**: Prometheus metrics (:9108), health checks (:9109), structured JSON logs
- **Schema Validation**: Strict Pydantic validation for all outputs

## Requirements

- Python 3.11+
- Access to Exchange Web Services (EWS)
- LLM Gateway endpoint

## Installation

```bash
# Clone repository
cd digest-core

# Install dependencies
pip install -e .

# Or using make
make setup
```

## Configuration

1. Copy example configuration:
```bash
cp configs/config.example.yaml configs/config.yaml
```

2. Set environment variables:
```bash
export EWS_PASSWORD="your_ews_password"
export LLM_TOKEN="your_llm_token"
```

Or create `.env` file (see `.env.example`).

3. Update `configs/config.yaml` with your settings:
   - EWS endpoint and credentials
   - LLM Gateway endpoint and model
   - Timezone and time window preferences

## Usage

### CLI

```bash
# Run digest for today
python -m digest_core.cli run

# Run for specific date
python -m digest_core.cli run --from-date 2024-01-15

# Custom output directory
python -m digest_core.cli run --out ./my-digests

# Dry-run mode (ingest+normalize only)
python -m digest_core.cli run --dry-run

# Using make
make run
```

### Docker

```bash
# Build image
make docker

# Run container
docker run --rm \
  -e EWS_PASSWORD=$EWS_PASSWORD \
  -e LLM_TOKEN=$LLM_TOKEN \
  -v $(pwd)/out:/data/out \
  -p 9108:9108 \
  -p 9109:9109 \
  digest-core:latest
```

## Output

The digest generates two files per run:

- `digest-YYYY-MM-DD.json`: Structured data with full schema validation
- `digest-YYYY-MM-DD.md`: Human-readable summary (≤400 words, Russian locale)

Each item includes:
- `evidence_id`: Reference to source evidence
- `source_ref`: Message metadata (type, msg_id, conversation_id)
- `confidence`: Score between 0-1
- `owners_masked`: PII-masked responsible parties
- `due`: Optional deadline

## Observability

### Metrics

Prometheus metrics available at `http://localhost:9108/metrics`:

- `llm_latency_ms`: LLM request latency histogram
- `llm_tokens_in_total`, `llm_tokens_out_total`: Token usage counters
- `emails_total{status}`: Email processing by status
- `digest_build_seconds`: Total digest build time
- `runs_total{status}`: Run status (ok/retry/failed)

### Health Checks

- Health: `http://localhost:9109/healthz`
- Readiness: `http://localhost:9109/readyz`

### Logs

Structured JSON logs via `structlog` with automatic PII redaction:

```json
{
  "event": "Digest run started",
  "timestamp": "2024-01-15T10:30:00.123456Z",
  "level": "info",
  "trace_id": "abc123-def456",
  "digest_date": "2024-01-15"
}
```

## Development

### Testing

```bash
# Run tests
make test

# Run with coverage
pytest --cov=digest_core tests/
```

### Linting

```bash
# Check code style
make lint

# Auto-format
make format
```

## Architecture

```
EWS → normalize → thread → evidence split → context select
  → LLM Gateway (with PII masking) → validate → assemble (JSON/MD)
  → metrics + logs
```

See `docs/ARCH.md` for detailed architecture documentation.

## Idempotency

Runs are idempotent per `(user_id, digest_date)` with a T-48h rebuild window:
- If artifacts exist and are <48h old: skip rebuild
- If artifacts are >48h old or missing: rebuild

## Privacy & Security

- **PII Masking**: Emails, phones, names, IDs masked before LLM
- **No Payload Logging**: Message bodies never logged
- **Corporate CA**: TLS verification with custom CA
- **Non-root Container**: Docker runs as UID 1001
- **Secret Management**: Credentials via ENV only

## License

Internal corporate use only.

