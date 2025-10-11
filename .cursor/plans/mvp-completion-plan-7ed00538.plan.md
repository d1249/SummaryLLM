<!-- 7ed00538-8c5a-4c2f-a817-f1a09c7e54ec c91594b0-6da4-45a6-896b-d854ebdc50c8 -->
# План доведения до MVP (обновлённый)

## Цели

- Закрыть все пробелы до MVP для запуска на отдельной машине с доступом к EWS.
- Подготовить сборку/запуск (скрипты), обновить README.
- Сформировать детальные TDD‑тесты по всем сценариям MVP.
- PII‑политика: e‑mail НЕ маскируем (маскируем телефоны/ФИО/ID/SSN/карты/IP и т. п.).

## 1) Изменения в коде (минимальные)

- PII политика
- Обновить `src/digest_core/normalize/html.py`:
- Удалить применение `self.pii_patterns['email']` (не маскировать e‑mail).
- В denylist‑проверке не считать e‑mail утечкой; оставить проверки телефонов/SSN/карты/имена/IP.
- Обновить тесты, убрав ожидание маскирования e‑mail.
- EWS/Sync
- Сохранить watermark (ISO timestamp) как MVP; fallback на полный интервал при повреждении состояния — задокументировать.
- Idempotency
- Реализовано (T‑48h). Добавить в README, как принудительно пересобрать (удалить артефакты/флаг).
- Observability
- Оставить healthz/readyz (9109) + Prometheus (9108). В README — раздел про ограничение кардинальности меток.

## 2) Обновления документации

- Обновить `docs/BRD.md`, `docs/TECH.md`, `docs/ARCH.md`:
- PII: e‑mail НЕ маскируем (мотивировка).
- TECH: watermark — ISO timestamp; без `SyncFolderItems` в MVP.
- Обновить `README.md`:
- Раздел «Инфраструктура» для выделенной машины: доступ к EWS, монтаж корпоративного CA, пример systemd unit.
- Раздел «Логи и утечки»: e‑mail допустим, телефоны/SSN/карты/имена — маскируются, тела писем не логируются.

## 3) Скрипты (директория `digest-core/scripts/`)

- `build.sh`: сборка пакета/образа, проверка зависимостей.
- `test.sh`: pytest с покрытием; exit 1 при провале.
- `lint.sh`: ruff/black (+ mypy при подключении).
- `smoke.sh`: локальный прогон с `--dry-run`; базовая проверка EWS (если возможно).
- `run-local.sh`: удобный вызов `cli run` с нужными путями out/.state.
- `deploy.sh`: сборка образа, публикация (опционально), пример запуска контейнера с монтированием CA и `.state`.
- `rotate_state.sh`: ротация `.state` и артефактов > 30/90 дней (удаление/архивация по флагу).
- `print_env.sh`: диагностика env (без вывода секретов), проверка наличия CA.

Требования к скриптам: `bash`, `set -euo pipefail`, логирование в stdout, коды возврата 0/1.

## 4) Точечные правки README

- «Быстрый старт на выделенной машине»: где лежит CA, как смонтировать `verify_ca` read‑only; пример Docker run с портами 9108/9109 и монтированием `/data/out`, `/data/.state`.
- «График запуска»: примеры `systemd` unit+timer и cron (07:30 ежедневно).
- «Диагностика»: как открыть `http://host:9109/healthz`, `readyz`, `/metrics`; как разбираться с пустыми днями (окно времени, watermark).
- «Политика PII»: e‑mail не маскируется; остальное маскируется; тела писем не логируются.

## 5) Тесты (TDD)

Создать/обновить в `digest-core/tests/` (+ `tests/fixtures/`).

- `tests/test_pii_policy.py`
- Не маскируем e‑mail: given `alice@corp.com` → e‑mail на месте.
- Маскируем телефоны/SSN/карты/имена: позитив/негатив.
- Denylist: после маскинга не остаются телефоны/SSN/карты/имена/IP.
- `tests/test_ews_ingest.py` (mock/monkeypatch `exchangelib`)
- NTLM+UPN, `autodiscover=False`.
- TLS: `BaseProtocol.SSL_CONTEXT` с CA; используется `service_endpoint`.
- Окна: `calendar_day` и `rolling_24h` (UTC корректности).
- Watermark: ISO → сдвиг окна; битый → полный интервал.
- Пагинация: несколько страниц → полный сбор.
- `tests/test_idempotency.py`
- Артефакты < 48ч → skip; > 48ч → rebuild.
- `tests/test_selector.py`
- Плюсы/минусы → скоринг и сортировка; фильтрация OOO/DSN; соблюдение бюджета токенов.
- `tests/test_evidence_split.py`
- Разрез по абзацам/предложениям; лимит 12; оценка токенов ≈ 1.3×слов; общий бюджет ≤ 3000.
- `tests/test_llm_gateway.py`
- Invalid JSON → 1 retrial с «Return strict JSON…» → success.
- Пустые `sections` при сильных сигналах → quality retry (1 попытка).
- Считывание `tokens_in/out` из headers/usage + запись в метрики.
- `tests/test_markdown_json_assemble.py`
- Markdown ≤ 400 слов; строки «Источник: …, evidence …» на айтемах.
- JSON соответствует схеме; `schema_version`, `prompt_version` присутствуют.
- Пустой день: `sections=[]`, сообщение «За период релевантных действий не найдено.»
- `tests/test_observability.py`
- `/healthz` → 200 healthy; `/readyz` → 200 ready.
- `/metrics` содержит ключевые метрики; нет высокой кардинальности.
- `tests/test_cli.py`
- Позитивный путь → код 0.
- `--dry-run` → код 2; LLM/assemble не вызываются (проверка логов/метрик).
- `tests/snapshots/` — снапшоты md/json для регресса.

Фикстуры: `tests/fixtures/emails/` — 30+ писем (EN/RU, OOO/DSN, длинные треды, инлайн‑картинки, дисклеймеры). Конфиги YAML под разные окна.

## 6) Скрипты сборки и CI

- Makefile: добавить таргеты `package` (сборка дистрибутива при необходимости) и `ci` (`lint && test`).
- В `scripts/`: реализовать `build.sh`, `test.sh`, `lint.sh`, `smoke.sh`, `run-local.sh`, `deploy.sh`, `rotate_state.sh`, `print_env.sh`.
- Пример `systemd` unit/timer; `EnvironmentFile=/etc/digest-core.env` с `EWS_PASSWORD`, `LLM_TOKEN`.

## 7) План выката на выделенную машину

- Подготовка: Docker/Podman; доступ к EWS; CA в `/etc/ssl/corp-ca.pem`; каталоги `/opt/digest/out`, `/opt/digest/.state` (UID 1001).
- Сборка и запуск: `make docker`; затем `docker run … -e EWS_PASSWORD=… -e LLM_TOKEN=… -v /etc/ssl/corp-ca.pem:/etc/ssl/corp-ca.pem:ro -v /opt/digest/out:/data/out -v /opt/digest/.state:/data/.state -p 9108:9108 -p 9109:9109 digest-core:latest`.
- Мониторинг: проверка `/healthz`, `/readyz`, `/metrics`.
- Расписание: systemd timer или cron (пример в README).
- Ротация: `scripts/rotate_state.sh` еженедельно (30/14/90 дней).

## 8) Критерии приёмки (DoD)

- Один валидный JSON + MD ≤ 400 слов; каждый item с `evidence_id` и `source_ref.msg_id`.
- Метрики на `:9108`, health на `:9109`.
- Пустые дни корректны (не ошибка).
- Повторный запуск за ту же дату идемпотентен (T‑48h).
- Тела писем/секреты не логируются; e‑mail не маскируется; телефоны/SSN/карты/имена — маскированы.

## Порядок выполнения

1) PII‑правка в коде и тестах (e‑mail не маскируем).
2) Обновление BRD/TECH/ARCH и README.
3) Добавление скриптов в `scripts/` и Makefile таргетов.
4) Расширение тестов (TDD) и прогон до зелёного.
5) Финальные smoke/health/metrics на выделенной машине.
6) Настройка расписания (systemd/cron) и ротации.

### To-dos

- [ ] Add schema_version/prompt_version to Digest schema; update run.py
- [ ] Implement SyncFolderItems/SyncState with safe reinit and TLS fix
- [ ] Harden HTML→text, PII masking, 200KB truncate, denylist check
- [ ] Stabilize thread keys and evidence split with token budget
- [ ] Implement scoring, service-mail filtering, top-K selection
- [ ] Add quality retry, tokens usage/cost budget, metrics
- [ ] Implement T-48h rebuild, watermark, retention housekeeping
- [ ] Add healthz/readyz endpoints and validate metrics labels
- [ ] Extend CLI flags, finalize Docker, add README and examples
- [ ] Add masking/normalize/EWS tests, fixtures, snapshots, leakage