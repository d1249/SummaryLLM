# PR: fix/regex-cyrillic-evidence + llm-shortcut + tokens-init

## Описание

Исправление критических проблем с кириллическими паттернами, оптимизация LLM вызовов и устранение UnboundLocalError.

## Изменения

### ✅ Безопасные кириллические паттерны
- Переход на `regex` модуль с `\p{IsCyrillic}` Unicode properties
- Устранение небезопасных диапазонов `[я-й]` → использование явных property
- Фолбэк на stdlib `re` с безопасными Unicode ranges
- **Нет больше ошибок "bad character range"**

### ✅ Шорткат LLM при отсутствии evidence
- Пропуск LLM обработки когда `evidence_count == 0`
- Использование `extractive_fallback` для генерации дайджеста
- Установка флагов `partial=true`, `reason='no_evidence'`
- Экономия на LLM затратах и latency

### ✅ Исправление UnboundLocalError
- Инициализация `tokens_in`, `tokens_out` до `try` блока
- Безопасные дефолты (0) при отсутствии usage данных
- Метрики теперь всегда пишутся корректно

## Тесты

- ✅ `test_regex_cyr.py` - валидация кириллических паттернов
- ✅ `test_regex_fallback.py` - проверка фолбэка на stdlib re
- ✅ `test_no_evidence_shortcut.py` - верификация LLM skip
- ✅ `test_gateway_tokens_init.py` - проверка инициализации токенов

Все тесты проходят успешно (10 passed).

## Чеклист

- [x] Нет ошибок "bad character range" в логах
- [x] LLM не вызывается при evidence_count==0, ставится partial=true
- [x] tokens_in/out/cost всегда инициализированы; метрики пишутся
- [x] Все новые тесты зелёные
- [x] Зависимость `regex>=2023.0` добавлена в pyproject.toml
- [x] Атомарные коммиты созданы

## Коммиты

1. `feat(deps): add regex>=2023.0 for safe Unicode property support`
2. `feat(evidence): switch to regex \p{IsCyrillic}; safe hyphen; fallback to std re`
3. `fix(llm): init tokens_in/out/cost before try/finally`
4. `feat(orchestrator): skip llm on empty evidence; partial fallback`
5. `test: add cyrillic/regex, fallback, no-evidence shortcut, tokens-init`

## Инструкции

Ветка `fix/regex-cyrillic-evidence` уже запушена на origin.

Создайте PR вручную через веб-интерфейс GitHub:
https://github.com/d1249/SummaryLLM/pull/new/fix/regex-cyrillic-evidence

Или используйте GitHub CLI после авторизации:
```bash
gh auth login
gh pr create --title "fix: regex cyrillic evidence + llm-shortcut + tokens-init" --body-file PR_DESCRIPTION_FIX.md
```

## Проверка

Запустить тесты:
```bash
cd digest-core
python3 -m pytest tests/test_regex_cyr.py tests/test_gateway_tokens_init.py -v
```

Ожидаемый результат: **10 passed**

