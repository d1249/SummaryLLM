<!-- bd5ff1a0-35e1-41af-a645-8269287a9711 98090ceb-eceb-4e00-b5d7-be89f9fafd2a -->
# План наведения порядка в структуре проекта SummaryLLM

## Проблемы текущей структуры

### 1. Отсутствие корневого .gitignore

- В корне нет .gitignore (только в digest-core/)
- Риск коммита чувствительных данных (.env, credentials)
- Нет игнорирования стандартных временных файлов

### 2. Разрозненная документация

```
Текущая структура:
├── README.md (корень)
├── INSTALL.md (корень)
├── DEPLOYMENT.md (корень)
├── AUTOMATION.md (корень)
├── MONITORING.md (корень)
└── digest-core/
    ├── README.md
    ├── TROUBLESHOOTING.md
    └── docs/
        ├── ARCH.md
        ├── BRD.md
        ├── TECH.md
        ├── Bus_Req_v5.md
        ├── Tech_details_v1.md
        └── Outlook_connect_v1.md
```

**Проблемы:**

- Операционные гайды (INSTALL, DEPLOYMENT) в корне
- Технические документы в digest-core/docs/
- Нет единой структуры
- Устаревшие файлы (Bus_Req_v5.md, Tech_details_v1.md)

### 3. Отсутствие стандартных файлов проекта

- Нет LICENSE файла (есть только упоминание)
- Нет CONTRIBUTING.md
- Нет CHANGELOG.md
- Нет CODE_OF_CONDUCT.md

### 4. Скрипты установки в корне

```
├── install.sh
├── quick-install.sh
├── setup.sh
```

Нет выделенной директории для utility скриптов

### 5. Нет .editorconfig

- Отсутствие единых правил форматирования
- Риск несогласованности отступов/переносов строк

## Предлагаемая структура

```
SummaryLLM/
├── .gitignore              # Корневой gitignore
├── .editorconfig           # Правила форматирования
├── LICENSE                 # Лицензия
├── README.md               # Главный README (уже хорош)
├── CHANGELOG.md            # История изменений
├── CONTRIBUTING.md         # Гайд для контрибьюторов
│
├── docs/                   # Вся документация
│   ├── README.md          # Навигация по документации
│   ├── installation/
│   │   ├── INSTALL.md     # Переместить из корня
│   │   └── QUICK_START.md # Краткая инструкция
│   ├── operations/
│   │   ├── DEPLOYMENT.md  # Переместить из корня
│   │   ├── AUTOMATION.md  # Переместить из корня
│   │   └── MONITORING.md  # Переместить из корня
│   ├── development/
│   │   ├── ARCHITECTURE.md # Из digest-core/docs/ARCH.md
│   │   ├── TECHNICAL.md    # Из digest-core/docs/TECH.md
│   │   └── CONTRIBUTING.md # Симлинк на корневой
│   ├── reference/
│   │   ├── BRD.md         # Business requirements
│   │   └── API.md         # API documentation
│   └── troubleshooting/
│       └── TROUBLESHOOTING.md # Из digest-core/
│
├── scripts/                # Utility скрипты
│   ├── install.sh         # Полная установка
│   ├── quick-install.sh   # Быстрая установка
│   └── setup.sh           # Интерактивная настройка
│
└── digest-core/           # Основное приложение
    ├── .gitignore
    ├── README.md          # Техническая документация пакета
    ├── Makefile
    ├── pyproject.toml
    ├── configs/
    ├── docker/
    ├── examples/
    ├── prompts/
    ├── scripts/           # Скрипты разработки
    ├── src/
    └── tests/
```

## Изменения

### 1. Создать корневой .gitignore

```gitignore
# Environment and credentials
.env
.env.*
*.env
credentials.yaml
secrets.yaml

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Project specific
digest-core/out/
digest-core/.state/
*.backup.*
```

### 2. Реорганизовать документацию

**Действия:**

- Создать `docs/` в корне с подкаталогами
- Переместить INSTALL.md → docs/installation/INSTALL.md
- Переместить DEPLOYMENT.md → docs/operations/DEPLOYMENT.md
- Переместить AUTOMATION.md → docs/operations/AUTOMATION.md
- Переместить MONITORING.md → docs/operations/MONITORING.md
- Переместить digest-core/TROUBLESHOOTING.md → docs/troubleshooting/
- Переместить digest-core/docs/ARCH.md → docs/development/ARCHITECTURE.md
- Переместить digest-core/docs/TECH.md → docs/development/TECHNICAL.md
- Переместить digest-core/docs/BRD.md → docs/reference/BRD.md
- Создать docs/README.md с навигацией

**Удалить устаревшие:**

- digest-core/docs/Bus_Req_v5.md (устарело, есть BRD.md)
- digest-core/docs/Tech_details_v1.md (устарело, есть TECH.md)
- digest-core/docs/Outlook_connect_v1.md (устарело или включить в TECHNICAL.md)

### 3. Переместить скрипты установки

```bash
scripts/
├── install.sh
├── quick-install.sh
└── setup.sh
```

### 4. Создать стандартные файлы

**LICENSE:**

```
Internal corporate use only.
Proprietary and confidential.
```

**CHANGELOG.md:**

```markdown
# Changelog

## [Unreleased]

### Added
- One-command installation scripts
- Comprehensive documentation restructure
- Monitoring and observability guides

### Changed
- Documentation organization
- README structure

## [0.1.0] - 2024-01-15

### Added
- Initial release
- EWS integration
- LLM-powered digest generation
```

**CONTRIBUTING.md:**

```markdown
# Contributing Guide

## Development Setup
## Code Style
## Testing
## Pull Request Process
```

### 5. Создать .editorconfig

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.{py,pyi}]
indent_style = space
indent_size = 4

[*.{yaml,yml}]
indent_style = space
indent_size = 2

[*.{sh,bash}]
indent_style = space
indent_size = 2

[*.md]
trim_trailing_whitespace = false
```

### 6. Обновить ссылки

После перемещения файлов обновить все ссылки:

- README.md (корневой)
- digest-core/README.md
- Все MD файлы с перекрестными ссылками

### 7. Улучшить README в корне

Добавить badges и структуру:

```markdown
# SummaryLLM

[![Python 3.11+](badge)]
[![License: Proprietary](badge)]

[Текущее описание...]

## Documentation

- 📚 [Full Documentation](docs/README.md)
- 🚀 [Quick Start](docs/installation/QUICK_START.md)
- 🔧 [Installation Guide](docs/installation/INSTALL.md)
- 🐳 [Deployment](docs/operations/DEPLOYMENT.md)
- 📊 [Monitoring](docs/operations/MONITORING.md)
```

## Порядок выполнения

1. Создать корневой .gitignore
2. Создать структуру docs/ с подкаталогами
3. Переместить все MD файлы в docs/
4. Создать docs/README.md с навигацией
5. Переместить скрипты в scripts/
6. Создать LICENSE, CHANGELOG.md, CONTRIBUTING.md
7. Создать .editorconfig
8. Обновить все ссылки в MD файлах
9. Обновить корневой README.md
10. Удалить устаревшие файлы

## Файлы для создания

1. `.gitignore` (корень)
2. `.editorconfig`
3. `LICENSE`
4. `CHANGELOG.md`
5. `CONTRIBUTING.md`
6. `docs/README.md`
7. `docs/installation/QUICK_START.md`

## Файлы для перемещения

1. `INSTALL.md` → `docs/installation/INSTALL.md`
2. `DEPLOYMENT.md` → `docs/operations/DEPLOYMENT.md`
3. `AUTOMATION.md` → `docs/operations/AUTOMATION.md`
4. `MONITORING.md` → `docs/operations/MONITORING.md`
5. `digest-core/TROUBLESHOOTING.md` → `docs/troubleshooting/TROUBLESHOOTING.md`
6. `digest-core/docs/ARCH.md` → `docs/development/ARCHITECTURE.md`
7. `digest-core/docs/TECH.md` → `docs/development/TECHNICAL.md`
8. `digest-core/docs/BRD.md` → `docs/reference/BRD.md`
9. `install.sh` → `scripts/install.sh`
10. `quick-install.sh` → `scripts/quick-install.sh`
11. `setup.sh` → `scripts/setup.sh`

## Детальный анализ "устаревших" файлов

### Bus_Req_v5.md vs BRD.md - Сравнительный анализ

**Bus_Req_v5.md (405 строк) содержит:**

- 📋 Полную дорожную карту развития (MVP → LVL5)
- 🎯 Детальные DoD для каждого уровня
- 📊 Операционализированные метрики качества (P/R/F1 ≥ 0.85/0.80)
- 🔐 Детальную политику приватности для DM
- 🤖 Планы интеграции Mattermost (LVL3-5)
- 📈 KPI и продуктовые метрики
- 🚨 Риски и меры митигации
- 📅 План внедрения по этапам
- 🔍 Спецификацию API вывода (JSON)
- ✅ DoD чек-листы для всех уровней

**BRD.md (85 строк) содержит:**

- Только MVP требования
- Базовые DoD
- Упрощенные критерии приёмки
- Политику данных (хранение 30 дней)

**ВЫВОД:** Bus_Req_v5.md НЕ устарел - это расширенная версия с roadmap!

**Действия:**

1. Переименовать `Bus_Req_v5.md` → `BRD_FULL.md` или `ROADMAP.md`
2. Сохранить `BRD.md` как краткую версию для MVP
3. Создать `docs/planning/ROADMAP.md` с содержимым Bus_Req_v5.md
4. Извлечь из Bus_Req_v5.md:

   - Метрики качества → дополнить MONITORING.md
   - План интеграции MM → создать `docs/planning/MATTERMOST_INTEGRATION.md`
   - KPI → создать `docs/reference/KPI.md`

### Tech_details_v1.md vs TECH.md - Сравнительный анализ

**Tech_details_v1.md (502 строки) содержит:**

- 📦 Детальную структуру репозитория с примерами кода
- 🔧 Полный Dockerfile multi-stage
- 🐍 Примеры Python кода (CLI, Gateway Client, Pydantic схемы)
- 📝 Детальные промпты и LLM-практики
- 🧪 Стратегию тестирования (pytest-snapshot, leakage-тесты, invariance-тесты)
- 🔐 Pre-commit hooks (ruff, black, isort, mypy, detect-secrets, bandit)
- 📊 Roadmap до LVL3 (недельный план)
- 📋 Минимальный Makefile
- 📄 Пример Markdown-выхода
- 🐳 Cron setup примеры

**TECH.md (176 строк) содержит:**

- Стек технологий
- Конфигурацию (ключи YAML)
- Схему JSON
- Промпты (краткое описание)
- Наблюдаемость
- CLI флаги
- Тесты/снапшоты (краткое)

**ВЫВОД:** Tech_details_v1.md содержит КРИТИЧЕСКУЮ информацию для разработки!

**Действия:**

1. НЕ удалять Tech_details_v1.md
2. Переименовать → `IMPLEMENTATION_GUIDE.md`
3. Извлечь из Tech_details_v1.md:

   - Примеры кода → создать `docs/development/CODE_EXAMPLES.md`
   - Тестирование → дополнить `docs/development/TESTING.md`
   - Pre-commit hooks → создать `docs/development/CODE_QUALITY.md`
   - Roadmap → переместить в `docs/planning/DEVELOPMENT_ROADMAP.md`

### Outlook_connect_v1.md - Анализ

**Содержит (125 строк):**

- 🔐 Детали NTLM аутентификации
- 📋 Форматы учётных данных (UPN vs Domain\Username)
- 🔍 Команды проверки соединения (curl примеры)
- 📚 Примеры использования exchangelib
- 🔄 Контроль состояния и инкрементальность (SyncState)
- 🛡️ Безопасность и политика
- 🚨 Диагностика и fallback сценарии

**ВЫВОД:** Содержит практическую информацию для troubleshooting!

**Действия:**

1. НЕ удалять
2. Переместить → `docs/troubleshooting/EWS_CONNECTION.md`
3. Добавить ссылку из TROUBLESHOOTING.md

## Новые документы для создания

### 1. docs/planning/ROADMAP.md

Из Bus_Req_v5.md:

- MVP → LVL5 план развития
- Интеграция Mattermost
- Добавление DM
- Mattermost-бот
- Детальные DoD для каждого уровня

### 2. docs/planning/MATTERMOST_INTEGRATION.md

Из Bus_Req_v5.md (LVL3-5):

- Подключение публичных чатов
- Добавление личных сообщений (DM)
- Политика приватности для DM
- Журнал согласий
- Продуктивизация в виде бота

### 3. docs/reference/KPI.md

Из Bus_Req_v5.md:

- Покрытие значимых писем/сообщений ≥ 90%
- Точность Action Items ≥ 80%
- Время генерации (T90) ≤ 60/90 сек
- SLA доставки бота ≥ 95%
- Пользовательская оценка ≥ 4/5

### 4. docs/reference/QUALITY_METRICS.md

Из Bus_Req_v5.md:

- Метрики качества AI
- Gold-сеты и разметка
- Precision/Recall/F1 целевые значения
- Citation fidelity
- Hallucination flags
- Regression-гейтинг

### 5. docs/development/IMPLEMENTATION_GUIDE.md

Из Tech_details_v1.md:

- Детальная структура репозитория
- Примеры кода компонентов
- LLM Gateway Client
- Pydantic схемы
- Dockerfile multi-stage

### 6. docs/development/CODE_EXAMPLES.md

- CLI примеры
- Gateway Client
- Pydantic модели
- Промпты

### 7. docs/development/TESTING.md

Из Tech_details_v1.md:

- pytest + pytest-snapshot
- Контрактные тесты
- Leakage-тесты
- Invariance-тесты
- Pre-commit hooks

### 8. docs/development/CODE_QUALITY.md

- Pre-commit hooks setup
- ruff, black, isort
- mypy configuration
- detect-secrets
- bandit security checks

### 9. docs/planning/DEVELOPMENT_ROADMAP.md

Из Tech_details_v1.md:

- Неделя 1: скелет, EWS ingest
- Неделя 2: LLM Gateway, промпты
- Неделя 3: Evidence Split, context diet
- Неделя 4: LVL3 - эмбеддинги, MM

### 10. docs/troubleshooting/EWS_CONNECTION.md

Из Outlook_connect_v1.md:

- NTLM аутентификация
- Форматы credentials
- Проверка соединения
- Диагностика

### 11. docs/reference/COST_MANAGEMENT.md

Из Bus_Req_v5.md:

- Стоимость и деградации
- Фолбэки при превышении бюджета
- Метрики стоимости
- Алерты

## Обновленная структура docs/

```
docs/
├── README.md                    # Навигация по всей документации
│
├── installation/
│   ├── INSTALL.md              # Из корня
│   └── QUICK_START.md          # Новый
│
├── operations/
│   ├── DEPLOYMENT.md           # Из корня
│   ├── AUTOMATION.md           # Из корня
│   └── MONITORING.md           # Из корня (+ дополнить метриками качества)
│
├── development/
│   ├── ARCHITECTURE.md         # Из digest-core/docs/ARCH.md
│   ├── TECHNICAL.md            # Из digest-core/docs/TECH.md
│   ├── IMPLEMENTATION_GUIDE.md # Из Tech_details_v1.md
│   ├── CODE_EXAMPLES.md        # Извлечь из Tech_details_v1.md
│   ├── TESTING.md              # Извлечь из Tech_details_v1.md
│   ├── CODE_QUALITY.md         # Извлечь из Tech_details_v1.md
│   └── CONTRIBUTING.md         # Симлинк на корневой
│
├── planning/
│   ├── ROADMAP.md              # Из Bus_Req_v5.md
│   ├── MATTERMOST_INTEGRATION.md # Извлечь из Bus_Req_v5.md
│   └── DEVELOPMENT_ROADMAP.md  # Извлечь из Tech_details_v1.md
│
├── reference/
│   ├── BRD.md                  # Из digest-core/docs/BRD.md (краткая версия MVP)
│   ├── BRD_FULL.md             # Из Bus_Req_v5.md (полная версия)
│   ├── KPI.md                  # Извлечь из Bus_Req_v5.md
│   ├── QUALITY_METRICS.md      # Извлечь из Bus_Req_v5.md
│   ├── COST_MANAGEMENT.md      # Извлечь из Bus_Req_v5.md
│   └── API.md                  # Новый (API documentation)
│
└── troubleshooting/
    ├── TROUBLESHOOTING.md      # Из digest-core/
    └── EWS_CONNECTION.md       # Из Outlook_connect_v1.md
```

## Файлы для НЕ удаления (сохранить и переработать)

1. `digest-core/docs/Bus_Req_v5.md` → разбить на ROADMAP.md, MATTERMOST_INTEGRATION.md, KPI.md, QUALITY_METRICS.md
2. `digest-core/docs/Tech_details_v1.md` → разбить на IMPLEMENTATION_GUIDE.md, CODE_EXAMPLES.md, TESTING.md, CODE_QUALITY.md
3. `digest-core/docs/Outlook_connect_v1.md` → переместить в troubleshooting/EWS_CONNECTION.md

## Обновленный список TODO

1. Создать корневой .gitignore
2. Создать структуру docs/ с подкаталогами
3. **АНАЛИЗ**: Детально изучить Bus_Req_v5.md и извлечь информацию
4. **АНАЛИЗ**: Детально изучить Tech_details_v1.md и извлечь информацию
5. **АНАЛИЗ**: Изучить Outlook_connect_v1.md
6. Создать новые документы из извлеченной информации
7. Переместить существующие MD файлы в docs/
8. Создать docs/README.md с навигацией
9. Переместить скрипты в scripts/
10. Создать LICENSE, CHANGELOG.md, CONTRIBUTING.md
11. Создать .editorconfig
12. Обновить все ссылки в MD файлах
13. Обновить корневой README.md
14. Дополнить MONITORING.md метриками качества из Bus_Req_v5.md

## Файлы для обновления (ссылки)

1. `README.md` (корень)
2. `digest-core/README.md`
3. Все перемещенные MD файлы с внутренними ссылками
4. `MONITORING.md` - дополнить метриками качества AI

### To-dos

- [ ] Переписать корневой README.md: минимизировать до quick start + основные команды + ссылки
- [ ] Создать DEPLOYMENT.md: извлечь инструкции по Docker, systemd, dedicated machine setup
- [ ] Создать AUTOMATION.md: извлечь инструкции по cron, systemd timer, rotation
- [ ] Создать MONITORING.md: извлечь инструкции по Prometheus, health checks, logs
- [ ] Обновить digest-core/README.md: добавить TOC, убрать детали infrastructure/scheduling, добавить ссылки на новые документы