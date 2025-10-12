# digest-core

Daily corporate communications digest with privacy-first design and LLM-powered action extraction.

## Features

- **EWS Integration**: NTLM authentication, corporate CA trust, incremental sync
- **Privacy-First**: PII masking delegated to LLM Gateway API (no local masking)
- **Idempotent**: T-48h rebuild window for deterministic results
- **Dry-Run Mode**: Test EWS connectivity and normalization without LLM calls
- **Observability**: Prometheus metrics (:9108), health checks (:9109), structured JSON logs
- **Schema Validation**: Strict Pydantic validation for all outputs

## Requirements

- Python 3.11+
- Access to Exchange Web Services (EWS)
- LLM Gateway endpoint

## Quick Start

The easiest way to get started is using the interactive setup script from the project root:

```bash
# From SummaryLLM root directory
./setup.sh

# Or using make
make setup-wizard
```

This will guide you through all configuration steps and generate the necessary files.

## Manual Installation

```bash
# Clone repository
cd digest-core

# Install dependencies with uv
uv sync

# Or using make
make setup
```

## Infrastructure

### Dedicated Machine Setup

For deployment on a dedicated machine with EWS access:

1. **Prerequisites**:
   - Docker/Podman installed
   - Access to EWS endpoint
   - Corporate CA certificate at `/etc/ssl/corp-ca.pem`
   - Directories `/opt/digest/out` and `/opt/digest/.state` (UID 1001)

2. **Build and Run**:
   ```bash
   # Build Docker image
   make docker
   
   # Run container with proper mounts
   docker run -d \
     --name digest-core \
     -e EWS_PASSWORD='your_password' \
     -e LLM_TOKEN='your_token' \
     -v /etc/ssl/corp-ca.pem:/etc/ssl/corp-ca.pem:ro \
     -v /opt/digest/out:/data/out \
     -v /opt/digest/.state:/data/.state \
     -p 9108:9108 \
     -p 9109:9109 \
     digest-core:latest
   ```

3. **Manual Run**:
   ```bash
   docker run -it \
     -e EWS_PASSWORD='your_password' \
     -e LLM_TOKEN='your_token' \
     -v /etc/ssl/corp-ca.pem:/etc/ssl/corp-ca.pem:ro \
     -v /opt/digest/out:/data/out \
     -v /opt/digest/.state:/data/.state \
     -p 9108:9108 \
     -p 9109:9109 \
     digest-core:latest python -m digest_core.cli run
   ```

### Scheduling

#### systemd Timer
Create `/etc/systemd/system/digest-core.service`:
```ini
[Unit]
Description=Digest Core Service
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/docker run --rm \
  -e EWS_PASSWORD=%i \
  -e LLM_TOKEN=%i \
  -v /etc/ssl/corp-ca.pem:/etc/ssl/corp-ca.pem:ro \
  -v /opt/digest/out:/data/out \
  -v /opt/digest/.state:/data/.state \
  digest-core:latest
User=digest
Group=digest
EnvironmentFile=/etc/digest-core.env
```

Create `/etc/systemd/system/digest-core.timer`:
```ini
[Unit]
Description=Run digest-core daily
Requires=digest-core.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable digest-core.timer
sudo systemctl start digest-core.timer
```

#### Cron
Add to crontab:
```bash
# Run daily at 07:30
30 7 * * * /usr/bin/docker run --rm -e EWS_PASSWORD='password' -e LLM_TOKEN='token' -v /etc/ssl/corp-ca.pem:/etc/ssl/corp-ca.pem:ro -v /opt/digest/out:/data/out -v /opt/digest/.state:/data/.state digest-core:latest
```

### Rotation

Run weekly cleanup:
```bash
# Rotate state and artifacts
./scripts/rotate_state.sh

# Or using make
make rotate
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
export EWS_USER_UPN="user@corp.com"
export EWS_ENDPOINT="https://ews.corp.com/EWS/Exchange.asmx"
export LLM_ENDPOINT="https://llm-gw.corp.com/api/v1/chat"
```

Or create `.env` file with these variables.

3. Update `configs/config.yaml` with your settings:
   - EWS endpoint and credentials
   - LLM Gateway endpoint and model
   - Timezone and time window preferences

## Usage

### CLI Examples

#### Basic Commands

```bash
# Run digest for today
python -m digest_core.cli run

# Run for specific date
python -m digest_core.cli run --from-date 2024-01-15

# Custom output directory
python -m digest_core.cli run --out ./my-digests

# Dry-run mode (ingest+normalize only, no LLM calls)
python -m digest_core.cli run --dry-run

# Using make
make run
```

#### Advanced Options

```bash
# Different time window (rolling 24h instead of calendar day)
python -m digest_core.cli run --window rolling_24h

# Custom LLM model
python -m digest_core.cli run --model "gpt-4"

# Multiple sources (if implemented)
python -m digest_core.cli run --sources "ews,mattermost"

# Force rebuild (ignore idempotency)
python -m digest_core.cli run --force

# Verbose output
python -m digest_core.cli run --verbose
```

#### Common Scenarios

**Daily Automated Run:**
```bash
# Add to crontab for daily 8 AM execution
0 8 * * * cd /path/to/digest-core && source ../.env && python -m digest_core.cli run
```

**Historical Digest Generation:**
```bash
# Generate digests for the past week
for date in $(seq -f "2024-01-%02g" 8 14); do
    python -m digest_core.cli run --from-date $date
done
```

**Testing Configuration:**
```bash
# Test EWS connectivity without LLM
python -m digest_core.cli run --dry-run

# Test with different model
python -m digest_core.cli run --model "gpt-3.5-turbo" --dry-run
```

**Multiple Mailboxes (if configured):**
```bash
# Process different mailboxes by updating config.yaml folders
python -m digest_core.cli run --from-date 2024-01-15
```

### Output Files

#### JSON Structure

The `digest-YYYY-MM-DD.json` file contains structured data with the following schema:

```json
{
  "digest_date": "2024-01-15",
  "generated_at": "2024-01-15T10:30:00Z",
  "trace_id": "abc123-def456",
  "sections": [
    {
      "title": "Мои действия",
      "items": [
        {
          "title": "Утвердить лимиты Q3",
          "owners_masked": ["[[REDACT:NAME;id=9b3e]]"],
          "due": "2024-01-17",
          "evidence_id": "ev:msghash:1024:480",
          "confidence": 0.86,
          "source_ref": {
            "type": "email",
            "msg_id": "urn:ews:...",
            "conversation_id": "conv123"
          }
        }
      ]
    }
  ]
}
```

#### Markdown Format

The `digest-YYYY-MM-DD.md` file provides human-readable output:

```markdown
# Дайджест — 2024-01-15

## Мои действия
- Утвердить лимиты Q3 — до **2024-01-17**. Ответственные: [[REDACT:NAME;id=9b3e]].  
  Источник: письмо «Q3 Budget plan», evidence ev:msghash:1024:480.

## Срочно
- [[REDACT:NAME;id=f1d0]] просит подтвердить SLA инцидента #7842.  
  Источник: «ADP incident update», evidence ev:...
```

#### Evidence References

Each item includes:
- `evidence_id`: Reference to source evidence fragment
- `source_ref`: Message metadata (type, msg_id, conversation_id)
- `confidence`: Extraction confidence score (0-1)
- `owners_masked`: PII-masked responsible parties
- `due`: Optional deadline

### Troubleshooting Quick Reference

#### Empty Digest Issues

**Problem**: Digest is empty despite having emails
```bash
# Check time window settings
grep -A 5 "time:" configs/config.yaml

# Verify lookback hours
grep "lookback_hours" configs/config.yaml

# Test with dry-run to see ingested emails
python -m digest_core.cli run --dry-run
```

**Solutions**:
- Adjust `lookback_hours` in config.yaml
- Change `window` from `calendar_day` to `rolling_24h`
- Check EWS folder permissions

#### Connection Errors

**Problem**: EWS endpoint not reachable
```bash
# Test connectivity
curl -I https://your-ews-endpoint.com/EWS/Exchange.asmx

# Check certificate
openssl s_client -connect your-ews-endpoint.com:443

# Verify CA certificate path
ls -la /etc/ssl/corp-ca.pem
```

**Solutions**:
- Verify EWS endpoint URL
- Check corporate CA certificate
- Test network connectivity
- Verify firewall settings

#### Authentication Issues

**Problem**: EWS authentication fails
```bash
# Check environment variables
echo $EWS_PASSWORD
echo $EWS_USER_UPN

# Test with dry-run
python -m digest_core.cli run --dry-run
```

**Solutions**:
- Verify UPN format (user@domain.com)
- Check password validity
- Ensure account has EWS permissions
- Test with Outlook Web Access

#### Configuration Validation

**Problem**: Configuration errors
```bash
# Run environment check
make env-check

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('configs/config.yaml'))"

# Test configuration loading
python -c "from digest_core.config import Config; print(Config())"
```

**Solutions**:
- Fix YAML syntax errors
- Verify all required fields are present
- Check environment variable names
- Ensure proper indentation

#### LLM Gateway Issues

**Problem**: LLM requests failing
```bash
# Test LLM endpoint
curl -H "Authorization: Bearer $LLM_TOKEN" $LLM_ENDPOINT

# Check token validity
echo $LLM_TOKEN | wc -c

# Test with verbose output
python -m digest_core.cli run --verbose
```

**Solutions**:
- Verify LLM token is valid
- Check endpoint URL format
- Ensure proper headers in config
- Test with different model

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

## Observability

### Metrics

Prometheus metrics available at `http://localhost:9108/metrics`:

- `llm_latency_ms`: LLM request latency histogram
- `llm_tokens_in_total`, `llm_tokens_out_total`: Token usage counters
- `emails_total{status}`: Email processing by status
- `digest_build_seconds`: Total digest build time
- `runs_total{status}`: Run status (ok/retry/failed)

**Cardinality Limits**: Metrics use controlled label sets to prevent high cardinality. Only essential labels are included (model, operation, status).

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

**PII Policy**: All PII masking logic (emails, phone numbers, names, SSNs, credit cards, IP addresses) is handled by the LLM Gateway API. No local masking is performed. Message bodies are never logged.

### Diagnostics

Check environment and connectivity:
```bash
# Run diagnostics
./scripts/print_env.sh

# Or using make
make env-check
```

For empty days, check:
- Time window settings (calendar_day vs rolling_24h)
- Watermark state in `.state` directory
- EWS connectivity and credentials

## Troubleshooting

For common issues and solutions, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Quick diagnostics:
```bash
# Check environment and configuration
./scripts/print_env.sh

# Test dry-run mode
python3 -m digest_core.cli --dry-run
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

To force rebuild, delete existing artifacts or use `--force` flag.

## Privacy & Security

- **PII Masking**: All PII masking (emails, phone numbers, names, SSNs, credit cards, IP addresses) handled by LLM Gateway API
- **No Payload Logging**: Message bodies never logged
- **Corporate CA**: TLS verification with custom CA
- **Non-root Container**: Docker runs as UID 1001
- **Secret Management**: Credentials via ENV only

## License

Internal corporate use only.

