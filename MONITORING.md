# SummaryLLM Monitoring Guide

Руководство по мониторингу и observability для SummaryLLM.

## Metrics

### Prometheus Metrics

Доступны по адресу `http://localhost:9108/metrics`:

#### LLM Metrics

- `llm_latency_ms`: Гистограмма времени ответа LLM
- `llm_tokens_in_total`: Счетчик входящих токенов
- `llm_tokens_out_total`: Счетчик исходящих токенов
- `llm_requests_total{status}`: Счетчик запросов по статусу

#### Email Processing Metrics

- `emails_total{status}`: Обработка писем по статусу
- `emails_processed_total`: Общее количество обработанных писем
- `emails_failed_total`: Количество неудачно обработанных писем

#### Digest Metrics

- `digest_build_seconds`: Время сборки дайджеста
- `digest_items_total`: Количество элементов в дайджесте
- `runs_total{status}`: Статус запусков (ok/retry/failed)

#### System Metrics

- `memory_usage_bytes`: Использование памяти
- `cpu_usage_percent`: Использование CPU

### Cardinality Limits

Метрики используют контролируемые наборы лейблов для предотвращения высокой кардинальности. Включаются только essential лейблы (model, operation, status).

### Example Queries

```promql
# Среднее время ответа LLM за последний час
rate(llm_latency_ms_sum[1h]) / rate(llm_latency_ms_count[1h])

# Количество успешных запусков за день
increase(runs_total{status="ok"}[24h])

# Использование токенов за последний час
rate(llm_tokens_in_total[1h]) + rate(llm_tokens_out_total[1h])

# Процент успешных обработок писем
rate(emails_total{status="ok"}[1h]) / rate(emails_total[1h]) * 100
```

## Health Checks

### Endpoints

- **Health**: `http://localhost:9109/healthz`
- **Readiness**: `http://localhost:9109/readyz`

### Health Check Response

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "checks": {
    "ews_connectivity": "ok",
    "llm_connectivity": "ok",
    "disk_space": "ok"
  }
}
```

### Custom Health Checks

```bash
#!/bin/bash
# health-check.sh

# Check health endpoint
if curl -f http://localhost:9109/healthz > /dev/null 2>&1; then
    echo "Service is healthy"
else
    echo "Service is unhealthy"
    exit 1
fi

# Check readiness
if curl -f http://localhost:9109/readyz > /dev/null 2>&1; then
    echo "Service is ready"
else
    echo "Service is not ready"
    exit 1
fi
```

## Logging

### Structured JSON Logs

Логи через `structlog` с автоматическим скрытием PII:

```json
{
  "event": "Digest run started",
  "timestamp": "2024-01-15T10:30:00.123456Z",
  "level": "info",
  "trace_id": "abc123-def456",
  "digest_date": "2024-01-15",
  "user_id": "user@corp.com"
}
```

### Log Levels

- **DEBUG**: Детальная отладочная информация
- **INFO**: Общая информация о работе
- **WARNING**: Предупреждения о потенциальных проблемах
- **ERROR**: Ошибки, требующие внимания

### PII Policy

Вся логика маскировки PII (emails, телефоны, имена, SSN, кредитные карты, IP адреса) обрабатывается LLM Gateway API. Локальная маскировка не выполняется. Тела сообщений никогда не логируются.

### Log Configuration

```bash
# Set log level
export DIGEST_LOG_LEVEL=DEBUG

# Enable structured logging
export DIGEST_LOG_FORMAT=json

# Log to file
export DIGEST_LOG_FILE=/var/log/digest-core.log
```

## Monitoring Setup

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'digest-core'
    static_configs:
      - targets: ['localhost:9108']
    scrape_interval: 30s
    metrics_path: /metrics
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "SummaryLLM Dashboard",
    "panels": [
      {
        "title": "LLM Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(llm_latency_ms_sum[5m]) / rate(llm_latency_ms_count[5m])"
          }
        ]
      },
      {
        "title": "Email Processing Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(emails_processed_total[5m])"
          }
        ]
      }
    ]
  }
}
```

### Alerting Rules

```yaml
# alerting.yml
groups:
  - name: digest-core
    rules:
      - alert: DigestRunFailed
        expr: increase(runs_total{status="failed"}[1h]) > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Digest run failed"
          
      - alert: HighLLMLatency
        expr: rate(llm_latency_ms_sum[5m]) / rate(llm_latency_ms_count[5m]) > 30000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High LLM response time"
          
      - alert: LowEmailProcessing
        expr: rate(emails_processed_total[1h]) < 1
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Low email processing rate"
```

## Diagnostics

### Environment Check

```bash
# Run diagnostics
./scripts/print_env.sh

# Or using make
make env-check
```

### Manual Diagnostics

```bash
# Check Prometheus metrics
curl http://localhost:9108/metrics

# Check specific metrics
curl http://localhost:9108/metrics | grep digest_

# Check health
curl http://localhost:9109/healthz

# Check readiness
curl http://localhost:9109/readyz
```

### Log Analysis

```bash
# Enable debug logging
DIGEST_LOG_LEVEL=DEBUG python -m digest_core.cli run --dry-run 2>&1 | tee debug.log

# Check structured logs
cat debug.log | jq .

# Filter by trace_id
cat debug.log | jq 'select(.trace_id == "abc123-def456")'

# Count errors
cat debug.log | jq 'select(.level == "error")' | wc -l
```

## Performance Monitoring

### Resource Usage

```bash
# Monitor memory usage
docker stats digest-core

# Check disk usage
du -sh /opt/digest/out
du -sh /opt/digest/.state

# Monitor network
netstat -i
```

### Performance Metrics

- **Memory Usage**: Мониторинг использования RAM
- **CPU Usage**: Нагрузка на процессор
- **Disk I/O**: Операции чтения/записи
- **Network I/O**: Сетевой трафик

### Optimization Tips

- Уменьшите `lookback_hours` в config для снижения нагрузки
- Увеличьте `page_size` для EWS пагинации
- Мониторьте время ответа LLM Gateway
- Настройте правильные таймауты

## Troubleshooting

### Common Issues

#### Empty Digest

```bash
# Check time window settings
grep -A 5 "time:" configs/config.yaml

# Verify lookback hours
grep "lookback_hours" configs/config.yaml

# Test with dry-run
python -m digest_core.cli run --dry-run
```

#### High Memory Usage

```bash
# Check memory metrics
curl http://localhost:9108/metrics | grep memory_usage

# Monitor with htop
htop

# Check Docker stats
docker stats digest-core
```

#### Slow Processing

```bash
# Check LLM latency
curl http://localhost:9108/metrics | grep llm_latency

# Monitor network connectivity
ping ews.corp.com
ping llm-gw.corp.com
```

## Integration Examples

### Slack Notifications

```bash
#!/bin/bash
# slack-notify.sh

if ! python -m digest_core.cli run; then
    curl -X POST "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK" \
         -H 'Content-type: application/json' \
         --data '{
           "text": "SummaryLLM digest generation failed",
           "attachments": [{
             "color": "danger",
             "fields": [{
               "title": "Error",
               "value": "Check logs for details"
             }]
           }]
         }'
fi
```

### Email Alerts

```bash
#!/bin/bash
# email-alert.sh

if ! python -m digest_core.cli run; then
    echo "SummaryLLM digest generation failed" | mail -s "Digest Alert" admin@corp.com
fi
```

## See Also

- [DEPLOYMENT.md](DEPLOYMENT.md) - Настройка развертывания
- [AUTOMATION.md](AUTOMATION.md) - Настройка автоматизации
- [digest-core/TROUBLESHOOTING.md](digest-core/TROUBLESHOOTING.md) - Детальное troubleshooting
