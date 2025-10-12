# SummaryLLM Automation Guide

Руководство по автоматизации запуска SummaryLLM.

## Scheduling Options

### systemd Timer (Recommended)

#### Service Configuration

Создайте `/etc/systemd/system/digest-core.service`:

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

#### Timer Configuration

Создайте `/etc/systemd/system/digest-core.timer`:

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

#### Enable and Start

```bash
sudo systemctl enable digest-core.timer
sudo systemctl start digest-core.timer
```

### Cron

#### Basic Daily Schedule

```bash
# Добавить в crontab (запуск каждый день в 8:00)
crontab -e

# Добавить строку:
0 8 * * * cd /path/to/SummaryLLM/digest-core && source ../.env && python -m digest_core.cli run
```

#### Docker with Cron

```bash
# Run daily at 07:30
30 7 * * * /usr/bin/docker run --rm -e EWS_PASSWORD='password' -e LLM_TOKEN='token' -v /etc/ssl/corp-ca.pem:/etc/ssl/corp-ca.pem:ro -v /opt/digest/out:/data/out -v /opt/digest/.state:/data/.state digest-core:latest
```

#### Advanced Cron Examples

```bash
# Каждый день в 8:00
0 8 * * * /path/to/digest-core/run-daily.sh

# Каждый рабочий день в 7:30
30 7 * * 1-5 /path/to/digest-core/run-daily.sh

# Каждые 6 часов
0 */6 * * * /path/to/digest-core/run-daily.sh

# С логированием
0 8 * * * /path/to/digest-core/run-daily.sh >> /var/log/digest-core.log 2>&1
```

## State Management

### Rotation

Еженедельная очистка состояния:

```bash
# Rotate state and artifacts
./scripts/rotate_state.sh

# Or using make
make rotate
```

### Manual State Management

```bash
# Очистить состояние (принудительный пересбор)
rm -rf .state/ews.syncstate

# Очистить старые артефакты
find out/ -name "digest-*.json" -mtime +30 -delete
find out/ -name "digest-*.md" -mtime +30 -delete
```

## Advanced Automation

### Multi-Mailbox Processing

```bash
#!/bin/bash
# process-multiple-mailboxes.sh

MAILBOXES=("user1@corp.com" "user2@corp.com" "user3@corp.com")

for mailbox in "${MAILBOXES[@]}"; do
    echo "Processing $mailbox..."
    EWS_USER_UPN="$mailbox" python -m digest_core.cli run --out "./out/$mailbox"
done
```

### Historical Processing

```bash
#!/bin/bash
# generate-historical.sh

START_DATE="2024-01-01"
END_DATE="2024-01-31"

current_date="$START_DATE"
while [[ "$current_date" <= "$END_DATE" ]]; do
    echo "Processing $current_date..."
    python -m digest_core.cli run --from-date "$current_date"
    current_date=$(date -d "$current_date + 1 day" +%Y-%m-%d)
done
```

### Error Handling

```bash
#!/bin/bash
# run-with-retry.sh

MAX_RETRIES=3
RETRY_DELAY=300

for i in $(seq 1 $MAX_RETRIES); do
    echo "Attempt $i of $MAX_RETRIES"
    
    if python -m digest_core.cli run; then
        echo "Success!"
        exit 0
    else
        echo "Failed, retrying in $RETRY_DELAY seconds..."
        sleep $RETRY_DELAY
    fi
done

echo "All retries failed"
exit 1
```

## Monitoring Integration

### Health Checks

```bash
#!/bin/bash
# health-check.sh

# Check if service is running
if ! systemctl is-active --quiet digest-core.timer; then
    echo "digest-core.timer is not active"
    systemctl start digest-core.timer
fi

# Check last run
LAST_RUN=$(systemctl show digest-core.timer --property=LastTriggerUSec)
echo "Last run: $LAST_RUN"
```

### Alerting

```bash
#!/bin/bash
# alert-on-failure.sh

if ! python -m digest_core.cli run; then
    # Send alert (example with curl)
    curl -X POST "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK" \
         -H 'Content-type: application/json' \
         --data '{"text":"SummaryLLM digest generation failed"}'
fi
```

## Configuration Management

### Environment Files

```bash
# /etc/digest-core.env
EWS_PASSWORD=your_password
EWS_USER_UPN=user@corp.com
EWS_ENDPOINT=https://ews.corp.com/EWS/Exchange.asmx
LLM_TOKEN=your_token
LLM_ENDPOINT=https://llm-gw.corp.com/api/v1/chat
```

### Configuration Validation

```bash
#!/bin/bash
# validate-config.sh

# Check environment variables
required_vars=("EWS_PASSWORD" "EWS_USER_UPN" "EWS_ENDPOINT" "LLM_TOKEN" "LLM_ENDPOINT")

for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "Error: $var is not set"
        exit 1
    fi
done

echo "All required variables are set"
```

## Best Practices

### Security

- Используйте systemd timer вместо cron для лучшей безопасности
- Храните credentials в отдельном файле с ограниченными правами
- Регулярно ротируйте пароли и токены

### Reliability

- Настройте retry logic для сетевых ошибок
- Мониторьте размер логов и состояние диска
- Используйте health checks для проверки работоспособности

### Performance

- Настройте правильные временные окна для обработки
- Мониторьте использование ресурсов
- Оптимизируйте частоту запуска под нагрузку

## See Also

- [DEPLOYMENT.md](DEPLOYMENT.md) - Настройка развертывания
- [MONITORING.md](MONITORING.md) - Мониторинг и observability
- [digest-core/TROUBLESHOOTING.md](digest-core/TROUBLESHOOTING.md) - Детальное troubleshooting
