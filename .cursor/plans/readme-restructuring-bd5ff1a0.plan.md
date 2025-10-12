<!-- bd5ff1a0-35e1-41af-a645-8269287a9711 e1d30a8d-58cf-4316-9e0f-78d73eb3651a -->
# Реструктуризация документации SummaryLLM

## Цели

- Создать минимальный корневой README с quick start и ссылками
- Оставить краткие инструкции в корневом README для удобства
- Создать отдельные файлы: DEPLOYMENT.md, AUTOMATION.md, MONITORING.md
- Сохранить смешанный формат (русский + английский)

## Изменения

### 1. Корневой README.md

**Структура:**

```markdown
# SummaryLLM
Краткое описание (1-2 предложения)

## Quick Start
./setup.sh - интерактивная настройка
Краткие шаги после настройки (3-4 команды)

## Основные команды
5-7 самых частых команд с кратким описанием

## Структура проекта
Краткое описание директорий

## Документация
Ссылки на:
- digest-core/README.md (детальная документация)
- DEPLOYMENT.md (деплой)
- AUTOMATION.md (автоматизация)
- MONITORING.md (мониторинг)
- digest-core/TROUBLESHOOTING.md

## License
```

**Что убрать:**

- Детальные инструкции по настройке (есть в setup.sh и digest-core/README.md)
- Подробности структуры выходных файлов
- Длинные примеры автоматизации
- Детальные инструкции мониторинга

**Что оставить кратко:**

- Команды для быстрого старта
- 5-7 основных команд CLI
- Ссылки на детальную документацию

### 2. DEPLOYMENT.md (новый файл)

**Содержание из digest-core/README.md:**

- Dedicated Machine Setup (строки 49-89)
- Docker setup (строки 404-418)
- Infrastructure section полностью

**Дополнительно из корневого README:**

- Docker автоматизация (строки 126-135)

### 3. AUTOMATION.md (новый файл)

**Содержание из digest-core/README.md:**

- Scheduling section (строки 90-138)
- Rotation (строки 140-149)

**Дополнительно из корневого README:**

- Настройка cron (строки 111-119)
- Использование systemd (строки 121-123)

### 4. MONITORING.md (новый файл)

**Содержание из digest-core/README.md:**

- Observability section полностью (строки 420-465)

**Дополнительно из корневого README:**

- Мониторинг и отладка (строки 137-151)

### 5. digest-core/README.md

**Улучшения:**

- Добавить TOC (Table of Contents) в начале
- Убрать дублирование с корневым README
- Добавить ссылки на DEPLOYMENT.md, AUTOMATION.md, MONITORING.md
- Улучшить секцию Quick Start
- Убрать детальные инструкции по scheduling (оставить ссылку на AUTOMATION.md)
- Убрать детальные инструкции по infrastructure (оставить ссылку на DEPLOYMENT.md)

**Структура после изменений:**

```markdown
# digest-core
Description
Features

## Quick Start
./setup.sh или make setup

## Requirements
## Configuration
## Usage
  - CLI Examples
  - Output Files
  - Troubleshooting Quick Reference
## Development
  - Testing
  - Linting
## Architecture
## Idempotency
## Privacy & Security

Ссылки на:
- DEPLOYMENT.md - для деплоя
- AUTOMATION.md - для автоматизации
- MONITORING.md - для мониторинга
```

## Файлы для изменения

1. `/Users/ruslan/msc_1/git/SummaryLLM/README.md` - переписать
2. `/Users/ruslan/msc_1/git/SummaryLLM/DEPLOYMENT.md` - создать
3. `/Users/ruslan/msc_1/git/SummaryLLM/AUTOMATION.md` - создать
4. `/Users/ruslan/msc_1/git/SummaryLLM/MONITORING.md` - создать
5. `/Users/ruslan/msc_1/git/SummaryLLM/digest-core/README.md` - обновить

## Принципы

- Сохранить смешанный формат (русский + английский)
- Убрать дублирование деталей, оставить краткие инструкции
- Все детали - в специализированных файлах
- Корневой README должен быть ≤100 строк

### To-dos

- [ ] Переписать корневой README.md: минимизировать до quick start + основные команды + ссылки
- [ ] Создать DEPLOYMENT.md: извлечь инструкции по Docker, systemd, dedicated machine setup
- [ ] Создать AUTOMATION.md: извлечь инструкции по cron, systemd timer, rotation
- [ ] Создать MONITORING.md: извлечь инструкции по Prometheus, health checks, logs
- [ ] Обновить digest-core/README.md: добавить TOC, убрать детали infrastructure/scheduling, добавить ссылки на новые документы