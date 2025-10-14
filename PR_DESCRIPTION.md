# PR: LLM JSON Validation, Timezone, Hierarchy & Security Improvements

## 🎯 Обзор

Комплексное улучшение robustness и security системы SummaryLLM:

- ✅ Строгая валидация JSON от LLM с Pydantic
- ✅ Extractive fallback при сбоях LLM
- ✅ Нормализация timezone (запрет naive datetime)
- ✅ Улучшенная логика иерархического режима
- ✅ Маскирование PII (вход/выход)
- ✅ Расширенные детекторы для русского языка
- ✅ Новые Prometheus метрики
- ✅ Юнит-тесты и CI конфигурация

## 📊 Изменения по компонентам

### 1. Конфигурация (`config.py`, `config.example.yaml`)

**Добавлено:**
- `llm.strict_json` (default: true) - строгая валидация JSON
- `llm.max_retries` (default: 3) - retry attempts
- `time.mailbox_tz`, `time.runner_tz`, `time.fail_on_naive` - timezone настройки
- `hierarchical.enable_auto`, `threshold_threads` (40), `threshold_emails` (200)
- `hierarchical.min_threads_to_summarize` (6)
- `masking.enforce_input`, `masking.enforce_output` - PII защита
- `degrade.enable`, `degrade.mode` - фолбэк настройки

### 2. LLM Gateway (`llm/gateway.py`, `llm/models.py`)

**Убрано:**
- ❌ Агрессивный JSON repair (advanced_json_repair, extract_json_from_text)
- ❌ json-repair library зависимость

**Добавлено:**
- ✅ `models.py`: `parse_llm_json()`, `minimal_json_repair()`, `LLMResponse` Pydantic модель
- ✅ Строгая валидация с retry + hints в prompt
- ✅ Минимальный cleanup (только markdown блоки и trim)
- ✅ Исправлены scope ошибки переменных

### 3. Деградация (`llm/degrade.py`)

**Новый модуль:**
- `extractive_fallback()` - rule-based extraction при LLM failure
- `build_digest_with_fallback()` - wrapper с автоматическим фолбэком
- Логика: action_verbs → my_actions, dates → deadlines, high_priority → risks

### 4. Timezone (`ingest/timezone.py`, `ingest/ews.py`)

**Новый модуль:**
- `ensure_tz_aware()` - конвертация naive → aware
- `normalize_email_dates()` - нормализация всех дат
- `get_current_tz_aware()` - текущее время в TZ

**Интегрировано в EWSIngest:**
- Все datetime нормализуются к `mailbox_tz`
- Опция `fail_on_naive` для строгого режима

### 5. Иерархический режим (`hierarchical/processor.py`)

**Обновлена логика:**
- `should_use_hierarchical()` использует `threshold_threads`/`threshold_emails`
- Проверка `min_threads_to_summarize` как minimum requirement
- На 37 тредов/61 письмо - НЕ активируется (< 40 threshold)
- На 45+ тредов - активируется
- Логирование решений

### 6. Маскирование PII (`privacy/masking.py`)

**Новый модуль:**
- Regex patterns: EMAIL, PHONE, CARD, PASSPORT_RU, SNILS
- `mask_text()` - маскирование → `[[REDACT:TYPE]]`
- `assert_no_unmasked_pii()` - валидация отсутствия PII
- `validate_llm_output()` - проверка ответа LLM

**Интегрировано в LLMGateway:**
- `enforce_input_masking` - маскирует перед отправкой
- `enforce_output_masking` - валидирует после получения

### 7. Детекторы для русского (`evidence/signals.py`)

**Расширены patterns:**
- Русские дедлайны: "до 15 января", "к 3 марта", "не позднее 20 декабря"
- Action verbs (40+ слов):
  - Requests: прошу, просьба, можете
  - Requirements: нужно, требуется, должны
  - Approvals: одобрить, согласовать, утвердить
  - Responses: ответить, уточнить
  - Updates: обновить, актуализировать

### 8. Метрики (`observability/metrics.py`)

**Новые счётчики:**
- `llm_json_errors_total` - JSON parsing errors
- `llm_repair_fail_total` - repair failures
- `masking_violations_total{direction}` - PII leakage (input/output)
- `tz_naive_total` - naive datetime encounters
- `degrade_activated_total{reason}` - degradation activations

**Методы:**
- `record_llm_json_error()`, `record_masking_violation(direction)`, etc.

### 9. Тесты

**Добавлено 6 новых test файлов:**
- `test_llm_strict_validation.py` - JSON валидация, repair
- `test_fallback_degrade.py` - extractive fallback
- `test_timezone_normalization.py` - TZ нормализация
- `test_hierarchy_thresholds.py` - иерархические пороги
- `test_masking.py` - PII маскирование
- `test_ru_detectors.py` - русские детекторы

### 10. CI/CD

**Добавлено:**
- `.pre-commit-config.yaml` - black, isort, flake8
- `CI_SETUP.md` - инструкции по setup и примеры GitHub Actions

## ✅ Acceptance Criteria

Все критерии выполнены:

- [x] Все LLM-ответы либо валидируются Pydantic, либо фолбэк
- [x] Naive datetime не проходят (fail_on_naive=true)
- [x] Иерархия НЕ включается на ~37 тредов/61 письмо
- [x] Иерархия включается на ~45+ тредов
- [x] PII не утекает (входная/выходная валидация)
- [x] RU-дедлайны детектируются: "до 3 ноября"
- [x] RU-действия детектируются: "прошу согласовать"
- [x] /metrics экспортирует новые счётчики
- [x] Все pytest тесты зелёные
- [x] Pre-commit hooks настроены

## 📈 Метрики

**Коммиты:** 11  
**Файлов изменено:** ~25  
**Новых тестов:** 6 файлов, 30+ test cases  
**Новых модулей:** 4 (models.py, degrade.py, timezone.py, masking.py)

## 🔒 Security Improvements

1. **PII Protection:**
   - Input masking перед LLM
   - Output validation после LLM
   - Regex для email, phone, cards, passports, SNILS

2. **Strict Validation:**
   - Pydantic models для LLM responses
   - No silent failures - либо валидный JSON, либо extractive fallback

3. **Timezone Safety:**
   - Запрет naive datetime (configurable)
   - Единая нормализация к mailbox_tz

## 🧪 Тестирование

Запустить тесты:

```bash
cd digest-core
pytest tests/test_llm_strict_validation.py \
       tests/test_fallback_degrade.py \
       tests/test_timezone_normalization.py \
       tests/test_hierarchy_thresholds.py \
       tests/test_masking.py \
       tests/test_ru_detectors.py -v
```

## 📝 Breaking Changes

**Минимальные breaking changes:**

1. `EWSIngest.__init__` теперь принимает `time_config` (опционально)
2. `LLMGateway.__init__` новые параметры (с defaults)
3. Конфиг расширен (обратно совместим через defaults)

## 🚀 Deployment

1. Обновить `config.yaml` с новыми секциями (опционально)
2. Установить зависимости: `pip install -r requirements.txt`
3. Запустить тесты: `pytest -v`
4. Deploy as usual

## 👥 Reviewers

@team - пожалуйста review:
- Строгую валидацию JSON (gateway.py)
- Extractive fallback логику (degrade.py)
- PII masking patterns (privacy/masking.py)
- Иерархические пороги (hierarchical/processor.py)

