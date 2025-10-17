# SummaryLLM

Ежедневный корпоративный дайджест коммуникаций с извлечением действий на основе LLM.

## 🛡️ Security & Robustness Guarantees

- **Строгая валидация JSON:** Все LLM-ответы валидируются Pydantic или срабатывает extractive fallback
- **Timezone Safety:** Запрет naive datetime, единая нормализация к mailbox_tz (configurable)
- **Degradation:** Автоматический extractive fallback при сбоях LLM (rule-based extraction)
- **Метрики:** Prometheus счётчики для JSON errors, degradations, TZ issues

## Quick Start

### Автоматическая установка (рекомендуется)

```bash
# Полная установка с интерактивной настройкой (рекомендуется)
curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/digest-core/scripts/install_interactive.sh | bash

# Быстрая установка без интерактивной настройки
curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/digest-core/scripts/quick-install.sh | bash

# С опциями (полная установка)
curl -fsSL https://raw.githubusercontent.com/d1249/SummaryLLM/main/digest-core/scripts/install_interactive.sh | bash -s -- --install-dir /opt/summaryllm
```

#### macOS (Homebrew) — быстрый старт

```bash
# Установка зависимостей
brew update
brew install python@3.11 uv docker openssl curl git

# Временный PATH для одной команды
PATH="$(brew --prefix)/opt/python@3.11/bin:$PATH" digest-core/scripts/install_interactive.sh --auto-brew --add-path

# Явный запуск CLI через 3.11
cd digest-core
python3.11 -m pip install -e .
python3.11 -m digest_core.cli run --dry-run
```

### Ручная установка

Если у вас уже есть клон репозитория:

```bash
# Запуск интерактивного мастера настройки
./digest-core/scripts/setup.sh

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
   ./digest-core/scripts/test_run.sh
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
./digest-core/scripts/fix_installation.sh

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
./digest-core/scripts/setup.sh
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
├── docs/              # Вся документация
│   ├── installation/  # Руководства по установке
│   ├── testing/       # Тестирование ⭐
│   │   └── E2E_TESTING_GUIDE.md  # End-to-End тестирование
│   ├── operations/    # Развертывание, автоматизация, мониторинг
│   ├── development/   # Архитектура, технические детали, код
│   ├── planning/      # Roadmap и планы развития
│   ├── legacy/        # Архив исторических отчётов и записей
│   ├── reference/     # Справочная информация
│   └── troubleshooting/ # Решение проблем
├── digest-core/       # Основное приложение
│   ├── src/          # Исходный код
│   ├── configs/      # Конфигурационные файлы
│   ├── scripts/      # Все утилитарные скрипты (установка, тесты, диагностика)
│   ├── prompts/      # Шаблоны LLM по версиям
│   ├── out/          # Результаты дайджестов
│   └── .state/       # Состояние синхронизации
├── .gitignore        # Корневой gitignore
├── .editorconfig     # Правила форматирования
├── LICENSE           # Лицензия
├── CHANGELOG.md      # История изменений
└── CONTRIBUTING.md   # Гайд для контрибьюторов
```

## Тестирование на отдельном компьютере

### Для тестировщиков: End-to-End тестирование

Если вам нужно установить и протестировать SummaryLLM на отдельном компьютере (в т.ч. корпоративном ноутбуке), следуйте **End-to-End Testing Guide**:

**[🧪 End-to-End Testing Guide](docs/testing/E2E_TESTING_GUIDE.md)** - Полное руководство от установки до отправки результатов

Этот гайд включает:
- ✅ Пошаговую установку на чистой машине
- ✅ Настройку для корпоративных ноутбуков
- ✅ Smoke-тестирование и полный цикл
- ✅ Сбор диагностики и отправку результатов
- ✅ Troubleshooting для типичных проблем

**Быстрая диагностика окружения:**
```bash
# Проверка готовности системы
./digest-core/scripts/doctor.sh
```

### Для разработчиков: Локальное тестирование

```bash
# Автоматический тестовый запуск с диагностикой
cd digest-core && ./scripts/test_run.sh

# Только smoke-тест (без LLM)
python -m digest_core.cli run --dry-run

# Сбор диагностики вручную
./digest-core/scripts/collect_diagnostics.sh
```

### Дополнительная документация по тестированию
- **[📋 Детальный чек-лист](docs/testing/MANUAL_TESTING_CHECKLIST.md)** - Подробное тестирование всех компонентов
- **[📧 Отправка результатов](docs/testing/SEND_RESULTS.md)** - Как отправить результаты через корпоративную почту
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