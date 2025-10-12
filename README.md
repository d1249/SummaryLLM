# SummaryLLM

Ежедневный корпоративный дайджест коммуникаций с privacy-first дизайном и извлечением действий на основе LLM.

## Quick Start

### Автоматическая установка (рекомендуется)

```bash
# Полная установка с интерактивной настройкой (рекомендуется)
curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/scripts/install_interactive.sh | bash

# Быстрая установка без интерактивной настройки
curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/scripts/quick-install.sh | bash

# С опциями (полная установка)
curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/scripts/install_interactive.sh | bash -s -- --install-dir /opt/summaryllm
```

#### macOS (Homebrew) — быстрый старт

```bash
# Установка зависимостей
brew update
brew install python@3.11 uv docker openssl curl git

# Временный PATH для одной команды
PATH="$(brew --prefix)/opt/python@3.11/bin:$PATH" scripts/install_interactive.sh --auto-brew --add-path

# Явный запуск CLI через 3.11
cd digest-core
python3.11 -m pip install -e .
python3.11 -m digest_core.cli run --dry-run
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

Скрипт установки автоматически создаёт виртуальное окружение в `digest-core/.venv`.

1. **Активируйте виртуальное окружение**:
   ```bash
   source digest-core/.venv/bin/activate
   ```

2. **Загрузите переменные окружения**:
   ```bash
   source .env
   ```

3. **Перейдите в директорию digest-core**:
   ```bash
   cd digest-core
   ```

4. **Запустите первый дайджест**:
   ```bash
   # Тестовый запуск (без LLM)
   python -m digest_core.cli run --dry-run
   
   # Полный запуск для сегодня
   python -m digest_core.cli run
   
   # Автоматический тестовый запуск с диагностикой
   ./scripts/test_run.sh
   ```

**Альтернатива**: Запуск без активации venv:
```bash
source .env
cd digest-core
.venv/bin/python -m digest_core.cli run --dry-run
```

## Устранение проблем при установке

### Ошибки TLS/SSL сертификатов

Если при установке возникает ошибка `invalid peer certificate: UnknownIssuer`:

```bash
# Используйте trusted-host для обхода проблем с корпоративными сертификатами
cd digest-core
source .venv/bin/activate
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .
```

### Отсутствует venv

Если виртуальное окружение не создано:

```bash
# Запустите скрипт диагностики
./scripts/fix_installation.sh

# Или создайте вручную
cd digest-core
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### Устаревшая конфигурация

Если получаете ошибку `Cannot determine NTLM username`:

```bash
# Обновите репозиторий
git pull

# Пересоздайте конфигурацию
./scripts/setup.sh
```

## Основные команды

```bash
# Базовый запуск (дайджест за сегодня)
python -m digest_core.cli run

# Для конкретной даты
python -m digest_core.cli run --from-date 2025-09-30

# Dry-run режим (только ingest+normalize, без LLM)
python -m digest_core.cli run --dry-run

# Другая модель LLM
python -m digest_core.cli run --model "Qwen/Qwen3-30B-A3B-Instruct-2507"

# Кастомная директория вывода
python -m digest_core.cli run --out ./my-digests

# Используя make
make run
```

## Структура проекта

```
SummaryLLM/
├── scripts/            # Utility скрипты
│   ├── install.sh     # Полная автоматическая установка
│   ├── quick-install.sh # Быстрая установка без настройки
│   └── setup.sh       # Интерактивная настройка
├── docs/              # Вся документация
│   ├── installation/  # Руководства по установке
│   ├── operations/    # Развертывание, автоматизация, мониторинг
│   ├── development/   # Архитектура, технические детали, код
│   ├── planning/      # Roadmap и планы развития
│   ├── reference/     # Справочная информация
│   └── troubleshooting/ # Решение проблем
├── digest-core/       # Основное приложение
│   ├── src/          # Исходный код
│   ├── configs/      # Конфигурационные файлы
│   ├── out/          # Результаты дайджестов
│   └── .state/       # Состояние синхронизации
├── .gitignore        # Корневой gitignore
├── .editorconfig     # Правила форматирования
├── LICENSE           # Лицензия
├── CHANGELOG.md      # История изменений
└── CONTRIBUTING.md   # Гайд для контрибьюторов
```

## Тестирование

Для тестирования приложения на корпоративном ноутбуке:

### Быстрый старт тестирования
```bash
# Автоматический тестовый запуск с диагностикой
./scripts/test_run.sh

# Ручной запуск с автоматическим сбором логов
python -m digest_core.cli run --collect-logs --log-level DEBUG

# Только диагностика системы
python -m digest_core.cli diagnose
```

### Документация по тестированию
- **[📋 Чек-лист тестирования](digest-core/docs/testing/MANUAL_TESTING_CHECKLIST.md)** - Пошаговое руководство по тестированию
- **[📧 Отправка результатов](digest-core/docs/testing/SEND_RESULTS.md)** - Как отправить результаты через корпоративную почту
- **[🔍 Сбор диагностики](digest-core/scripts/collect_diagnostics.sh)** - Автоматический сбор логов и метрик

## Документация

- **[📚 Полная документация](docs/README.md)** - Навигация по всей документации
- **[🚀 Quick Start](docs/installation/QUICK_START.md)** - Быстрый старт за 5 минут
- **[🔧 Installation Guide](docs/installation/INSTALL.md)** - Подробное руководство по установке
- **[🐳 Deployment](docs/operations/DEPLOYMENT.md)** - Развертывание в Docker, systemd, dedicated machine
- **[⏰ Automation](docs/operations/AUTOMATION.md)** - Настройка автоматизации (cron, systemd timer, rotation)
- **[📊 Monitoring](docs/operations/MONITORING.md)** - Мониторинг, метрики, health checks, логирование
- **[🚨 Troubleshooting](docs/troubleshooting/TROUBLESHOOTING.md)** - Решение проблем и отладка

## License

Internal corporate use only.