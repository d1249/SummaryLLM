# SummaryLLM

Daily corporate communications digest with privacy-first design and LLM-powered action extraction.

## Quick Start

The easiest way to get started is using the interactive setup script:

```bash
# Run the interactive setup wizard
./setup.sh

# Or from digest-core directory
cd digest-core && make setup-wizard
```

The setup script will:
- Check for required dependencies (Python 3.11+, uv, docker, etc.)
- Guide you through configuring EWS and LLM endpoints
- Validate connectivity and certificates
- Generate `.env` and `config.yaml` files
- Optionally install Python dependencies

## Запуск / Running

### После настройки

После успешного выполнения `./setup.sh` выполните следующие шаги:

1. **Активируйте окружение** (если не сделали это в setup.sh):
   ```bash
   source .env
   ```

2. **Перейдите в директорию digest-core**:
   ```bash
   cd digest-core
   ```

3. **Установите зависимости** (если не сделали в setup.sh):
   ```bash
   make setup
   ```

4. **Проверьте конфигурацию**:
   ```bash
   make env-check
   ```

5. **Запустите первый дайджест**:
   ```bash
   # Тестовый запуск (без LLM)
   python -m digest_core.cli run --dry-run
   
   # Полный запуск для сегодня
   python -m digest_core.cli run
   ```

### Основные команды

```bash
# Базовый запуск (дайджест за сегодня)
python -m digest_core.cli run

# Для конкретной даты
python -m digest_core.cli run --from-date 2024-01-15

# С другим временным окном (последние 24 часа)
python -m digest_core.cli run --window rolling_24h

# Dry-run режим (только ingest+normalize, без LLM)
python -m digest_core.cli run --dry-run

# Другая модель LLM
python -m digest_core.cli run --model "gpt-4"

# Кастомная директория вывода
python -m digest_core.cli run --out ./my-digests

# Используя make
make run
```

### Просмотр результатов

После успешного запуска в директории `digest-core/out/` будут созданы файлы:

- `digest-YYYY-MM-DD.json` - структурированные данные с полной схемой
- `digest-YYYY-MM-DD.md` - человеко-читаемый дайджест (≤400 слов)

**Пример просмотра результатов:**
```bash
# Посмотреть JSON структуру
cat digest-core/out/digest-2024-01-15.json | jq '.'

# Посмотреть Markdown дайджест
cat digest-core/out/digest-2024-01-15.md

# Найти все дайджесты
ls -la digest-core/out/digest-*.md
```

**Структура выходных файлов:**
- Каждый элемент содержит `evidence_id` для ссылки на источник
- `source_ref` указывает на исходное сообщение
- `confidence` показывает уверенность в извлечении (0-1)
- `owners_masked` содержит замаскированные имена ответственных

### Автоматизация

#### Настройка cron для ежедневного запуска

```bash
# Добавить в crontab (запуск каждый день в 8:00)
crontab -e

# Добавить строку:
0 8 * * * cd /path/to/SummaryLLM/digest-core && source ../.env && python -m digest_core.cli run
```

#### Использование systemd (Linux)

Для детальных инструкций по настройке systemd таймера см. [digest-core README](digest-core/README.md#scheduling).

#### Docker автоматизация

```bash
# Ежедневный запуск через Docker
0 8 * * * docker run --rm \
  -e EWS_PASSWORD='password' \
  -e LLM_TOKEN='token' \
  -v /path/to/out:/data/out \
  -v /path/to/.state:/data/.state \
  digest-core:latest
```

### Мониторинг и отладка

```bash
# Проверить метрики Prometheus
curl http://localhost:9108/metrics

# Проверить health check
curl http://localhost:9109/healthz

# Посмотреть логи (если запущено в Docker)
docker logs digest-core-container

# Проверить конфигурацию
cd digest-core && make env-check
```

## Manual Setup

If you prefer manual configuration, see the [digest-core README](digest-core/README.md) for detailed setup instructions.