# SummaryLLM

Ежедневный корпоративный дайджест коммуникаций с privacy-first дизайном и извлечением действий на основе LLM.

## Quick Start

### Автоматическая установка (рекомендуется)

```bash
# Полная установка с интерактивной настройкой
curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/install.sh | bash

# Быстрая установка без интерактивной настройки
curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/quick-install.sh | bash

# С опциями (полная установка)
curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/install.sh | bash -s -- --install-dir /opt/summaryllm
```

### Ручная установка

Если у вас уже есть клон репозитория:

```bash
# Запуск интерактивного мастера настройки
./setup.sh

# Или из директории digest-core
cd digest-core && make setup-wizard
```

### После настройки

1. **Активируйте окружение**:
   ```bash
   source .env
   ```

2. **Перейдите в директорию digest-core**:
   ```bash
   cd digest-core
   ```

3. **Установите зависимости**:
   ```bash
   make setup
   ```

4. **Запустите первый дайджест**:
   ```bash
   # Тестовый запуск (без LLM)
   python -m digest_core.cli run --dry-run
   
   # Полный запуск для сегодня
   python -m digest_core.cli run
   ```

## Основные команды

```bash
# Базовый запуск (дайджест за сегодня)
python -m digest_core.cli run

# Для конкретной даты
python -m digest_core.cli run --from-date 2024-01-15

# Dry-run режим (только ingest+normalize, без LLM)
python -m digest_core.cli run --dry-run

# Другая модель LLM
python -m digest_core.cli run --model "gpt-4"

# Кастомная директория вывода
python -m digest_core.cli run --out ./my-digests

# Используя make
make run
```

## Структура проекта

```
SummaryLLM/
├── install.sh           # Полная автоматическая установка
├── quick-install.sh     # Быстрая установка без настройки
├── setup.sh             # Интерактивная настройка
├── digest-core/         # Основное приложение
│   ├── src/            # Исходный код
│   ├── configs/        # Конфигурационные файлы
│   ├── out/            # Результаты дайджестов
│   └── .state/         # Состояние синхронизации
├── INSTALL.md          # Руководство по установке
├── DEPLOYMENT.md       # Руководство по развертыванию
├── AUTOMATION.md       # Руководство по автоматизации
└── MONITORING.md       # Руководство по мониторингу
```

## Документация

- **[INSTALL.md](INSTALL.md)** - Подробное руководство по установке и настройке
- **[digest-core/README.md](digest-core/README.md)** - Детальная документация по настройке и использованию
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Развертывание в Docker, systemd, dedicated machine
- **[AUTOMATION.md](AUTOMATION.md)** - Настройка автоматизации (cron, systemd timer, rotation)
- **[MONITORING.md](MONITORING.md)** - Мониторинг, метрики, health checks, логирование
- **[digest-core/TROUBLESHOOTING.md](digest-core/TROUBLESHOOTING.md)** - Решение проблем и отладка

## License

Internal corporate use only.