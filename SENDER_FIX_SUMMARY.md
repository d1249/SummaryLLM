# Исправление AttributeError "'NormalizedMessage' has no attribute 'sender'"

## Проблема
Ошибка `AttributeError: 'NormalizedMessage' has no attribute 'sender'` возникала в actions stage когда код пытался обратиться к `msg.sender`, но в схеме `NormalizedMessage` не было поля `sender`.

## Решение

### 1. Обновлена схема NormalizedMessage
- **ИЗМЕНЕНО**: Переход с `NamedTuple` на `@dataclass(frozen=True)` для поддержки методов
- Добавлены канонические поля для email метаданных:
  - `from_email: str` - основной email отправителя
  - `from_name: Optional[str]` - имя отправителя
  - `to_emails: List[str]` - список получателей
  - `cc_emails: List[str]` - список копий
  - `message_id: str` - ID сообщения
  - `body_norm: str` - нормализованное тело
  - `received_at: datetime` - время получения

- Добавлен alias property `sender` для обратной совместимости:
  ```python
  @property
  def sender(self) -> str:
      """Backward compatibility alias for sender_email."""
      return self.from_email or self.sender_email or ""
  ```

### 2. Обновлен метод _normalize_message
- Заполняются новые канонические поля при создании NormalizedMessage
- Извлекается имя отправителя из EWS сообщения

### 3. Добавлена защита от None в run.py
- Обновлена логика получения sender с fallback:
  ```python
  sender = msg.sender or msg.from_email or msg.sender_email or ""
  ```

### 4. Исправлены вызовы _replace
- Заменены все вызовы `msg._replace()` на создание новых объектов `NormalizedMessage`
- Добавлен импорт `NormalizedMessage` в `run.py`

### 5. Добавлена метрика для мониторинга
- Новая метрика `actions_sender_missing_total` для отслеживания случаев отсутствия sender
- Метод `record_action_sender_missing()` в MetricsCollector

### 6. Добавлены тесты
- Unit тесты для NormalizedMessage sender compatibility
- Integration тесты для actions stage с missing sender
- End-to-end тест для проверки основного фикса

## Результат
- ✅ AttributeError больше не возникает
- ✅ Actions stage работает с отсутствующим sender
- ✅ Обратная совместимость сохранена
- ✅ Добавлена observability для мониторинга
- ✅ Все тесты проходят
- ✅ Dataclass поддерживает методы (в отличие от NamedTuple)

## Файлы изменены
- `digest-core/src/digest_core/ingest/ews.py` - схема NormalizedMessage (NamedTuple → dataclass)
- `digest-core/src/digest_core/run.py` - логика получения sender + исправление _replace
- `digest-core/src/digest_core/observability/metrics.py` - новая метрика
- `digest-core/tests/test_normalized_message_sender.py` - unit тесты
- `digest-core/tests/test_actions_sender_integration.py` - integration тесты
- `digest-core/tests/test_sender_fix_integration.py` - end-to-end тест
