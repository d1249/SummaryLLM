<!-- fb392341-125d-4e1f-a2f5-e386e097eecb 1c1e959f-6a6f-41b7-be5e-a0a30e823e77 -->
# Enhance README Documentation with Running Instructions

## Overview

Add comprehensive running instructions to both README.md files to help users understand how to run SummaryLLM after initial setup, including various use cases and troubleshooting.

## Changes to Root README.md

Add new section "Запуск / Running" after "Quick Start":

### Content to add:

- **После настройки** - пошаговая инструкция что делать после `./setup.sh`
- **Основные команды** - примеры запуска для разных сценариев
- **Просмотр результатов** - где найти выходные файлы
- **Примеры использования** - реальные use cases

Sections:

1. После настройки (After Setup)

   - Активация окружения
   - Проверка конфигурации
   - Первый запуск

2. Запуск дайджеста (Running Digest)

   - Для сегодня
   - Для конкретной даты
   - С разными временными окнами
   - Dry-run режим

3. Где найти результаты (Output Location)

   - Структура выходных файлов
   - Формат JSON и Markdown
   - Примеры просмотра

4. Автоматизация (Automation)

   - Настройка cron
   - Ссылка на systemd инструкции

## Changes to digest-core/README.md

Expand "Usage" section with more examples:

### Content to add:

- **Расширенные примеры CLI** - все опции командной строки
- **Различные сценарии** - примеры для разных use cases
- **Troubleshooting** - частые проблемы и решения

Sections:

1. Usage Examples

   - Basic run (today)
   - Specific date
   - Custom time windows
   - Different output directories
   - Dry-run mode
   - Custom model

2. Output Files

   - JSON structure explanation
   - Markdown format
   - Evidence references

3. Common Scenarios

   - Daily automated run
   - Historical digest generation
   - Testing configuration
   - Multiple mailboxes

4. Troubleshooting Quick Reference

   - Empty digest
   - Connection errors
   - Authentication issues
   - Configuration validation

## Implementation Details

### Root README.md Structure

```markdown
# SummaryLLM

## Quick Start
[existing content]

## Запуск / Running

### После настройки
1. Активируйте окружение...
2. Перейдите в директорию digest-core...
3. Запустите первый дайджест...

### Основные команды
[examples]

### Просмотр результатов
[output explanation]

### Автоматизация
[scheduling instructions]

## Manual Setup
[existing content]
```

### digest-core/README.md Additions

- Expand existing "Usage" section
- Add "Output Files" subsection
- Add "Common Scenarios" subsection
- Add quick troubleshooting reference before full TROUBLESHOOTING.md link

## Examples to Include

**Примеры команд:**

```bash
# Базовый запуск (сегодня)
python -m digest_core.cli run

# Для конкретной даты
python -m digest_core.cli run --from-date 2024-01-15

# С другим временным окном
python -m digest_core.cli run --window rolling_24h

# Dry-run (без LLM)
python -m digest_core.cli run --dry-run

# Другая модель
python -m digest_core.cli run --model "gpt-4"
```

**Примеры автоматизации:**

```bash
# Добавить в crontab
0 8 * * * cd /path/to/digest-core && python -m digest_core.cli run
```

## Files to Modify

1. `/Users/ruslan/msc_1/git/SummaryLLM/README.md` - add comprehensive running section
2. `/Users/ruslan/msc_1/git/SummaryLLM/digest-core/README.md` - expand usage section

### To-dos

- [ ] Add comprehensive 'Запуск / Running' section to root README.md with after-setup instructions, basic commands, output location, and automation
- [ ] Expand Usage section in digest-core/README.md with detailed CLI examples, common scenarios, and quick troubleshooting