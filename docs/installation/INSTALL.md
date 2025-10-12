# SummaryLLM Installation Guide

Руководство по установке SummaryLLM с различными вариантами настройки.

## Варианты установки

### 1. Полная автоматическая установка (рекомендуется)

**Скрипт:** `install.sh`

```bash
curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/install.sh | bash
```

**Что делает:**
- Клонирует репозиторий
- Проверяет и устанавливает зависимости (Python 3.11+, uv, docker, etc.)
- Запускает интерактивный мастер настройки
- Устанавливает Python зависимости
- Создает конфигурационные файлы

**Опции:**
```bash
# Установка в кастомную директорию
curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/install.sh | bash -s -- --install-dir /opt/summaryllm

# Пропустить установку зависимостей
curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/install.sh | bash -s -- --skip-deps

# Пропустить интерактивную настройку
curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/install.sh | bash -s -- --skip-setup

# Подробный вывод
curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/install.sh | bash -s -- --verbose
```

### 2. Быстрая установка

**Скрипт:** `quick-install.sh`

```bash
curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/quick-install.sh | bash
```

**Что делает:**
- Клонирует репозиторий
- Устанавливает Python зависимости
- Создает шаблоны конфигурационных файлов
- **НЕ** запускает интерактивную настройку

**Когда использовать:**
- Для CI/CD пайплайнов
- Когда нужна быстрая установка без интерактивности
- Для автоматизированных сценариев

### 3. Ручная установка

**Скрипт:** `setup.sh`

```bash
# Если у вас уже есть клон репозитория
./setup.sh
```

**Что делает:**
- Запускает интерактивный мастер настройки
- Создает конфигурационные файлы
- Проверяет подключения

**Когда использовать:**
- Когда репозиторий уже склонирован
- Для повторной настройки
- Для обновления конфигурации

## Сравнение скриптов

| Функция | install.sh | quick-install.sh | setup.sh |
|---------|------------|------------------|----------|
| Клонирование репозитория | ✅ | ✅ | ❌ |
| Проверка зависимостей | ✅ | ❌ | ❌ |
| Установка зависимостей | ✅ | ✅ | ❌ |
| Интерактивная настройка | ✅ | ❌ | ✅ |
| Создание шаблонов | ✅ | ✅ | ✅ |
| Установка Python deps | ✅ | ✅ | ❌ |

## Требования

### Минимальные требования
- Git
- Python 3.11+
- Интернет соединение

### Рекомендуемые зависимости
- `uv` (быстрый Python package manager)
- `docker` (для контейнеризации)
- `curl` (для загрузки скриптов)
- `openssl` (для работы с сертификатами)

### Поддерживаемые системы
- **macOS**: Homebrew для установки зависимостей
- **Ubuntu/Debian**: apt для установки зависимостей
- **CentOS/RHEL**: yum/dnf (требует ручной установки зависимостей)

## После установки

### Проверка установки

```bash
# Перейти в директорию установки
cd ~/SummaryLLM  # или ваша кастомная директория

# Проверить конфигурацию
cd digest-core && make env-check

# Тестовый запуск
python -m digest_core.cli run --dry-run
```

### Первый запуск

```bash
# Активировать окружение
source .env

# Запустить дайджест
cd digest-core
python -m digest_core.cli run
```

## Troubleshooting

### Проблемы с зависимостями

```bash
# Проверить версию Python
python3 --version

# Установить uv вручную
curl -LsSf https://astral.sh/uv/install.sh | sh

# Установить Docker
# macOS: brew install --cask docker
# Ubuntu: sudo apt-get install docker.io
```

### Проблемы с правами доступа

```bash
# Сделать скрипты исполняемыми
chmod +x install.sh quick-install.sh setup.sh

# Проверить права на директорию
ls -la ~/SummaryLLM
```

### Проблемы с сетью

```bash
# Проверить доступность репозитория
curl -I https://github.com/your-org/SummaryLLM

# Проверить DNS
nslookup github.com
```

## Безопасность

### Проверка скриптов

Перед запуском рекомендуется проверить содержимое скриптов:

```bash
# Скачать и просмотреть скрипт
curl -fsSL https://raw.githubusercontent.com/your-org/SummaryLLM/main/install.sh > install.sh
cat install.sh

# Запустить после проверки
bash install.sh
```

### Ограничения

- Скрипты требуют sudo для установки системных зависимостей
- Автоматическая установка может изменить системные настройки
- Рекомендуется запускать в изолированной среде для тестирования

## Альтернативные методы

### Docker

```bash
# Клонировать репозиторий
git clone https://github.com/your-org/SummaryLLM.git
cd SummaryLLM

# Собрать Docker образ
cd digest-core && make docker

# Запустить контейнер
docker run --rm -v $(pwd)/out:/data/out digest-core:latest
```

### Виртуальное окружение

```bash
# Создать виртуальное окружение
python3 -m venv summaryllm-env
source summaryllm-env/bin/activate

# Установить зависимости
pip install -e digest-core/
```

## Поддержка

При возникновении проблем:

1. Проверьте [TROUBLESHOOTING.md](digest-core/TROUBLESHOOTING.md)
2. Запустите диагностику: `cd digest-core && make env-check`
3. Создайте issue в репозитории с подробным описанием проблемы
