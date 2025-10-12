<!-- 2db9b741-2b0a-4dd3-93b1-e4efc50dca47 449eeea3-e4d1-4467-97d7-417d7c0a0e20 -->
# Улучшения установщика и документации (Homebrew, Python 3.11+)

## Цели

- Надёжно находить и использовать Python 3.11+ без необходимости менять системный `python3`.
- Добавить опциональную автоустановку недостающих компонентов через Homebrew (и apt), а также чёткие инструкции, если автоустановка отключена.
- Обновить документацию с готовыми командами для macOS (Homebrew).

## Изменения в скриптах

### 1) `scripts/install.sh`

- Добавить флаги:
  - `--auto-brew`/`-y`: автоматически устанавливать недостающие зависимости через Homebrew (без вопросов).
  - `--auto-apt`: аналогично для apt.
  - `--python {3.11|3.12}`: пожелание версии, если доступно несколько.
  - `--non-interactive`: отключить любые `read -p`; падать с чёткими инструкциями или действовать согласно автофлагам.
  - `--add-path`: автоматически добавлять PATH для установленного `python@3.11` в `~/.zshrc`.
- Логика выбора интерпретатора:
  - Ввести функцию `find_python`:
    - искать по приоритету: `python3.12`, `python3.11`, затем `python3` (и проверять версию ≥ 3.11).
    - если не найдено подходящее — при `--auto-brew` установить `python@3.11`; иначе вывести точные команды `brew install python@3.11` и инструкции по PATH.
  - Экспортировать переменную `PYTHON_BIN` и использовать её в установке зависимостей: `"$PYTHON_BIN" -m pip install -e .` и при запуске CLI-примеров.
- Улучшить сообщения об установке зависимостей:
  - Если Homebrew доступен, но автофлаг не задан — печатать готовые команды для ручной установки: `brew install python@3.11 uv docker openssl curl git`.
  - После установки `python@3.11` предлагать:
    - временный PATH для текущей команды: `PATH="$(brew --prefix)/opt/python@3.11/bin:$PATH" ...`
    - постоянный: `echo 'export PATH="$(brew --prefix)/opt/python@3.11/bin:$PATH"' >> ~/.zshrc && exec zsh -l` (выполнять автоматически при `--add-path`).
- Сделать установку зависимостей через brew/apt неинтерактивной при соответствующих флагах; оставить существующий интерактивный путь как дефолт.
- В конце «Next Steps» дописать примеры запуска с явным `python3.11` и через временный PATH.

Пример фрагмента (сокращённо) для `find_python` и использования `PYTHON_BIN`:

```bash
find_python() {
  local requested="$1" # может быть пустым
  local candidates=()
  if [[ -n "$requested" ]]; then
    candidates=("python${requested}" "python${requested%.*}" )
  fi
  candidates+=(python3.12 python3.11 python3)
  for bin in "${candidates[@]}"; do
    if command -v "$bin" >/dev/null 2>&1; then
      local v=$($bin --version | awk '{print $2}')
      local major=${v%%.*}; local minor=${v#*.}; minor=${minor%%.*}
      if [[ $major -gt 3 || ($major -eq 3 && $minor -ge 11) ]]; then
        echo "$bin"; return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN=$(find_python "$PYTHON_REQUESTED") || PYTHON_BIN=""
if [[ -z "$PYTHON_BIN" ]]; then
  # при --auto-brew пытаемся установить python@3.11 и снова ищем
  # иначе печатаем инструкции brew install + PATH
fi

# далее: используем "$PYTHON_BIN" везде
"$PYTHON_BIN" -m pip install -e .
```

### 2) Новый скрипт (опционально): `scripts/doctor.sh`

- Диагностика окружения: версии git/python/uv/docker/openssl/curl, доступность Homebrew.
- Печать «что не так» и точных команд для исправления (brew/apt).

## Обновления документации

### 3) `README.md` и `docs/installation/INSTALL.md`

- Добавить раздел «macOS (Homebrew) — быстрый старт» с готовыми командами:
  - Проверка версии Python и путей:
    ```bash
    python3 --version
    which -a python3 python3.11
    ```

  - Установка зависимостей:
    ```bash
    brew update
    brew install python@3.11 uv docker openssl curl git
    ```

  - Добавление PATH (временный и постоянный варианты):
    ```bash
    export PATH="$(brew --prefix)/opt/python@3.11/bin:$PATH"
    echo 'export PATH="$(brew --prefix)/opt/python@3.11/bin:$PATH"' >> ~/.zshrc && exec zsh -l
    ```

  - Запуск установщика без смены системного `python3` (временный PATH):
    ```bash
    PATH="$(brew --prefix)/opt/python@3.11/bin:$PATH" scripts/install.sh --auto-brew --add-path
    ```

  - Явный запуск CLI через 3.11:
    ```bash
    cd digest-core
    python3.11 -m pip install -e .
    python3.11 -m digest_core.cli run --dry-run
    ```

- Объяснить флаги `--auto-brew`, `--non-interactive`, `--add-path`, `--python`.

### 4) `digest-core/README.md` и `docs/installation/QUICK_START.md`

- Пометка «Требуется Python 3.11+» с краткими способами его получить через Homebrew и как запускать через `python3.11`.

## Неприменяемые изменения

- Код `digest-core/src/` менять не требуется: достаточно корректного выбора интерпретатора и путей на уровне установщика/доков.

## Риски и совместимость

- Не ломаем текущий интерактивный путь: новые флаги лишь добавляют авто-режим.
- На macOS без Homebrew — печатаем инструкции, не пытаемся устанавливать самостоятельно.
- На Linux оставляем apt-ветку, добавляя зеркальные автофлаги.

### To-dos

- [ ] Добавить новые флаги (--auto-brew, --auto-apt, --python, --non-interactive, --add-path)
- [ ] Реализовать find_python и везде использовать PYTHON_BIN в install.sh
- [ ] Реализовать автоустановку недостающих зависимостей через Homebrew/apt
- [ ] Вывести инструкции PATH и поддержать --add-path в install.sh
- [ ] Расширить блок Next Steps с явным python3.11 и PATH
- [ ] Обновить README.md и INSTALL.md: раздел macOS/Homebrew, команды, флаги
- [ ] Обновить digest-core/README.md и QUICK_START.md: Python 3.11+
- [ ] Добавить scripts/doctor.sh для диагностики окружения (опционально)