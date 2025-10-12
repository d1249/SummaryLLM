<!-- d3d99926-0f91-4ed0-b77d-6cc670d5be5a cc808bf1-b742-458e-bbdd-aec66060fc90 -->
# Автоматическое создание venv при установке

## Цель

Создавать виртуальное окружение `.venv` в директории `digest-core` автоматически при установке, устанавливать в него зависимости и настроить все скрипты для работы с этим venv.

## Преимущества

1. Изолированное окружение, не зависящее от системного Python
2. Упрощение процесса - пользователю не нужно думать о создании venv
3. Единообразие - все используют одну и ту же структуру
4. Отказ от зависимости от `uv` (опционально используем, но не требуем)

## Изменения

### 1. `scripts/setup.sh` - Добавить создание venv

После функции `check_dependencies`, добавить новую функцию `setup_venv()`:

```bash
setup_venv() {
    print_step "Настройка виртуального окружения Python"
    
    local venv_path="$DIGEST_CORE_DIR/.venv"
    
    # Проверить, существует ли уже venv
    if [[ -d "$venv_path" ]]; then
        print_info "Виртуальное окружение уже существует: $venv_path"
        read -p "Пересоздать venv? [y/N]: " recreate
        if [[ "$recreate" =~ ^[Yy]$ ]]; then
            print_info "Удаление старого venv..."
            rm -rf "$venv_path"
        else
            print_success "Используем существующее виртуальное окружение"
            return 0
        fi
    fi
    
    # Создать venv
    print_info "Создание виртуального окружения в $venv_path..."
    if [[ -n "$FOUND_PYTHON" ]]; then
        "$FOUND_PYTHON" -m venv "$venv_path"
    else
        python3 -m venv "$venv_path"
    fi
    
    if [[ $? -eq 0 ]]; then
        print_success "Виртуальное окружение создано"
    else
        print_error "Не удалось создать виртуальное окружение"
        exit 1
    fi
    
    # Обновить pip в venv
    print_info "Обновление pip в виртуальном окружении..."
    "$venv_path/bin/pip" install --upgrade pip setuptools wheel
    
    print_success "Виртуальное окружение готово"
}
```

Обновить функцию `show_summary()` для установки зависимостей в venv:

```bash
# Заменить блок установки зависимостей
if [[ "$install_deps" =~ ^[Yy]$ ]]; then
    print_info "Установка Python зависимостей в venv..."
    cd "$DIGEST_CORE_DIR"
    
    local venv_path="$DIGEST_CORE_DIR/.venv"
    if [[ ! -d "$venv_path" ]]; then
        print_error "Виртуальное окружение не найдено"
        exit 1
    fi
    
    # Установить зависимости в venv
    print_info "Установка зависимостей через pip..."
    "$venv_path/bin/pip" install -e .
    
    if [[ $? -eq 0 ]]; then
        print_success "Зависимости установлены успешно"
    else
        print_error "Ошибка установки зависимостей"
    fi
fi
```

Обновить `main()` - добавить вызов `setup_venv()` после `check_dependencies`:

```bash
main() {
    # ... существующий код ...
    
    # Run setup steps
    check_dependencies
    setup_venv  # <-- добавить эту строку
    backup_configs
    # ... остальное без изменений ...
}
```

Обновить инструкции в `show_summary()`:

```bash
echo "1. Активировать виртуальное окружение:"
echo "   source digest-core/.venv/bin/activate"
echo "2. Или использовать напрямую:"
echo "   digest-core/.venv/bin/python -m digest_core.cli run --dry-run"
echo "3. Загрузить переменные окружения:"
echo "   source .env"
```

### 2. `scripts/install.sh` - Добавить создание venv

Обновить функцию `install_python_deps()`:

```bash
install_python_deps() {
    print_step "Установка Python зависимостей"

    if [[ -d "digest-core" ]]; then
        cd digest-core
        
        local venv_path=".venv"
        
        # Создать venv если не существует
        if [[ ! -d "$venv_path" ]]; then
            print_info "Создание виртуального окружения..."
            if [[ -n "$PYTHON_BIN" ]]; then
                "$PYTHON_BIN" -m venv "$venv_path"
            else
                python3 -m venv "$venv_path"
            fi
            
            if [[ $? -ne 0 ]]; then
                print_error "Не удалось создать виртуальное окружение"
                cd ..
                return 1
            fi
            
            print_success "Виртуальное окружение создано"
        else
            print_info "Виртуальное окружение уже существует"
        fi
        
        # Обновить pip
        print_info "Обновление pip..."
        "$venv_path/bin/pip" install --upgrade pip setuptools wheel > /dev/null 2>&1
        
        # Установить зависимости
        print_info "Установка зависимостей через pip..."
        "$venv_path/bin/pip" install -e .
        
        if [[ $? -eq 0 ]]; then
            print_success "Зависимости установлены в venv"
        else
            print_error "Ошибка установки зависимостей"
        fi

        cd ..
    else
        print_error "digest-core directory not found"
        exit 1
    fi
}
```

Обновить `show_next_steps()`:

```bash
echo "2. Активировать виртуальное окружение:"
echo "   source digest-core/.venv/bin/activate"
echo "   # или использовать напрямую: digest-core/.venv/bin/python"
echo
echo "3. Загрузить переменные окружения:"
echo "   source .env"
echo
echo "4. Запустить тестовый прогон:"
echo "   cd digest-core"
echo "   ../.venv/bin/python -m digest_core.cli run --dry-run"
```

### 3. Обновить `digest-core/scripts/py.sh` - использовать venv

Изменить скрипт для автоматического использования venv:

```bash
#!/bin/bash
# Запуск Python с автоматическим определением окружения

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="$PROJECT_DIR/.venv"

# Если venv существует, использовать его
if [[ -f "$VENV_PATH/bin/python" ]]; then
    PYTHON_BIN="$VENV_PATH/bin/python"
    echo "Используется venv: $VENV_PATH" >&2
elif command -v uv >/dev/null 2>&1; then
    # Fallback на uv run
    exec uv run python "$@"
else
    # Fallback на системный Python
    PYTHON_BIN="python3"
    echo "Используется системный Python (venv не найден)" >&2
fi

# Установить PYTHONPATH
export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"

# Запустить Python
exec "$PYTHON_BIN" "$@"
```

### 4. Добавить `.venv` в `.gitignore`

Убедиться, что в корне проекта и в `digest-core/.gitignore` есть:

```
.venv/
venv/
```

### 5. Обновить документацию

В `digest-core/README.md` добавить информацию о venv:

````markdown
## Установка

После запуска `scripts/setup.sh`, виртуальное окружение создаётся автоматически в `digest-core/.venv`.

### Активация окружения

```bash
source digest-core/.venv/bin/activate
````

### Запуск без активации

```bash
digest-core/.venv/bin/python -m digest_core.cli run
```

```

## Файлы для изменения

1. `scripts/setup.sh` - добавить `setup_venv()`, обновить установку зависимостей и инструкции
2. `scripts/install.sh` - обновить `install_python_deps()` и `show_next_steps()`
3. `digest-core/scripts/py.sh` - автоматически использовать venv если существует
4. `.gitignore` и `digest-core/.gitignore` - добавить `.venv/`
5. `digest-core/README.md` - обновить документацию (опционально)

## Обратная совместимость

Изменения сохраняют обратную совместимость:

- Если venv не существует, используется fallback на uv или системный Python
- Существующие установки продолжат работать
- Новые установки получат venv автоматически

### To-dos

- [ ] Добавить user_login, user_domain и метод get_ntlm_username() в EWSConfig
- [ ] Изменить создание credentials в _connect() на использование get_ntlm_username()
- [ ] Изменить collect_ews_config() для запроса логина, почты и endpoint отдельно, извлечь домен
- [ ] Добавить test_ews_ntlm_connection() с curl --ntlm тестом
- [ ] Вызвать NTLM-тест в validate_configuration()
- [ ] Обновить генерацию .env и config.yaml для сохранения логина и домена
- [ ] Обновить config.example.yaml с новыми полями