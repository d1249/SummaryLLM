# Специфика установки на корпоративных ноутбуках

## Обзор

Корпоративные ноутбуки часто имеют ограничения безопасности и специфичные конфигурации, которые влияют на установку и работу SummaryLLM. Этот документ описывает типичные проблемы и их решения.

---

## Типичные ограничения

### 1. Ограничения прав доступа

#### Проблема
- ❌ Нет прав sudo/administrator
- ❌ Нет доступа к системным директориям (`/opt/`, `/usr/local/`)
- ❌ Ограниченный доступ к `/tmp/`
- ❌ Невозможность установки системных пакетов

#### Решение
✅ Используйте только домашнюю директорию:

```bash
# Установка проекта
cd $HOME
git clone <repo-url> SummaryLLM
cd SummaryLLM

# Все рабочие директории в $HOME
export OUT_DIR="$HOME/.digest-out"
export STATE_DIR="$HOME/.digest-state"
export TMPDIR="$HOME/.digest-temp"
export LOG_DIR="$HOME/.digest-logs"

# Создайте директории
mkdir -p "$OUT_DIR" "$STATE_DIR" "$TMPDIR" "$LOG_DIR"
```

### 2. Корпоративные SSL сертификаты

#### Проблема
- 🔒 Корпоративный CA не в системном trust store
- 🔒 MITM прокси с самоподписанными сертификатами
- 🔒 SSL ошибки при подключении к внутренним сервисам

#### Решение A: Установка корпоративного CA

```bash
# 1. Получите корпоративный CA сертификат
# Обычно это файл вида: corporate-root-ca.crt

# 2. Конвертируйте в PEM формат (если нужно)
openssl x509 -inform DER -in corporate-root-ca.crt -out corporate-root-ca.pem

# 3. Скопируйте в проект
mkdir -p $HOME/SummaryLLM/certs
cp corporate-root-ca.pem $HOME/SummaryLLM/certs/

# 4. Настройте config.yaml
nano $HOME/SummaryLLM/digest-core/configs/config.yaml
```

**В config.yaml:**
```yaml
ews:
  endpoint: "https://owa.company.com/EWS/Exchange.asmx"
  verify_ssl: true
  verify_ca: "$HOME/SummaryLLM/certs/corporate-root-ca.pem"
```

#### Решение B: Временный обход (только для тестирования!)

```yaml
ews:
  verify_ssl: false  # ВНИМАНИЕ: Только для тестирования!
```

⚠️ **Не используйте в production!**

#### Решение C: Использование системного CA bundle

```bash
# macOS
export REQUESTS_CA_BUNDLE=/etc/ssl/cert.pem

# Linux (Ubuntu/Debian)
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Linux (CentOS/RHEL)
export REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt
```

### 3. Корпоративный прокси

#### Проблема
- 🌐 Весь трафик идет через корпоративный прокси
- 🌐 Прокси требует аутентификацию
- 🌐 Блокировка определенных доменов

#### Решение

```bash
# Настройка прокси
export http_proxy="http://proxy.company.com:8080"
export https_proxy="http://proxy.company.com:8080"
export no_proxy="localhost,127.0.0.1,.company.com"

# С аутентификацией
export http_proxy="http://username:password@proxy.company.com:8080"
export https_proxy="http://username:password@proxy.company.com:8080"

# Для Git
git config --global http.proxy http://proxy.company.com:8080
git config --global https.proxy http://proxy.company.com:8080

# Для pip (в случае проблем с SSL через прокси)
pip install --proxy http://proxy.company.com:8080 package_name

# Или используйте trusted-host
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org package_name
```

**Добавьте в .env:**
```bash
export http_proxy="http://proxy.company.com:8080"
export https_proxy="http://proxy.company.com:8080"
export no_proxy="localhost,127.0.0.1"
```

### 4. NTLM аутентификация

#### Проблема
- 🔐 Exchange требует NTLM аутентификацию
- 🔐 Нужны доменные учетные данные
- 🔐 Ошибки "Cannot determine NTLM username"

#### Решение

```bash
# Формат 1: Через переменные окружения
export EWS_USER_UPN="user@company.com"        # Email (UPN)
export EWS_USER_LOGIN="user"                   # Логин без домена
export EWS_USER_DOMAIN="COMPANY"               # Домен (uppercase)
export EWS_PASSWORD="your_password"

# Формат 2: В config.yaml
```

**В config.yaml:**
```yaml
ews:
  user_upn: "user@company.com"
  ntlm_username: "COMPANY\\user"  # Windows формат
  # password берется из EWS_PASSWORD env var
```

#### Проверка учетных данных

```bash
# Простой тест с curl
read -s EXCH_PASS
EXCH_USER='user@company.com'

curl --ntlm -u "$EXCH_USER:$EXCH_PASS" \
  -H 'Content-Type: text/xml' \
  -sS -I \
  https://owa.company.com/EWS/Exchange.asmx

# Ожидается: HTTP/1.1 200 OK или 401 (если плохие credentials)
```

### 5. Политики выполнения скриптов (Windows)

#### Проблема
- 📜 PowerShell Execution Policy блокирует скрипты
- 📜 Невозможно запустить .sh скрипты на Windows

#### Решение A: Использование WSL (рекомендуется)

```powershell
# 1. Установите WSL (требуется admin права один раз)
wsl --install

# 2. После установки WSL, работайте в Linux окружении
wsl
cd /mnt/c/Users/YourUsername/SummaryLLM
./digest-core/scripts/doctor.sh
```

#### Решение B: Git Bash

```bash
# Используйте Git Bash вместо PowerShell
# Git Bash включен в Git for Windows

# Запуск скриптов через Git Bash
bash ./digest-core/scripts/doctor.sh
```

### 6. Антивирус и блокировка файлов

#### Проблема
- 🛡️ Антивирус блокирует скачивание/выполнение файлов
- 🛡️ Карантин для Python скриптов
- 🛡️ Блокировка архивов .tar.gz

#### Решение

```bash
# 1. Добавьте проектную директорию в исключения антивируса
# (требуется помощь IT департамента)

# 2. Используйте альтернативные архиваторы
# Вместо tar.gz используйте zip
zip -r diagnostics-$(date +%Y%m%d-%H%M%S).zip diagnostics-dir/

# 3. Временно: сканируйте файлы вручную
clamscan -r $HOME/SummaryLLM
```

---

## Конфигурация для корпоративной среды

### Минимальная безопасная конфигурация

**config.yaml:**
```yaml
ews:
  endpoint: "https://owa.company.com/EWS/Exchange.asmx"
  user_upn: "${EWS_USER_UPN}"  # Из переменных окружения
  ntlm_username: "${EWS_USER_DOMAIN}\\${EWS_USER_LOGIN}"
  verify_ssl: true
  verify_ca: "$HOME/SummaryLLM/certs/corporate-ca.pem"
  folders:
    - "Inbox"
  page_size: 100

llm:
  endpoint: "https://llm-gw.company.com/api/v1/chat"
  model: "Qwen/Qwen3-30B-A3B-Instruct-2507"
  timeout: 600  # 10 минут для корпоративных сетей
  headers:
    Authorization: "Bearer ${LLM_TOKEN}"

time:
  timezone: "Europe/Moscow"
  window: "calendar_day"
  lookback_hours: 24

output:
  formats: ["json", "markdown"]
  base_path: "$HOME/.digest-out"
```

**.env:**
```bash
# EWS Configuration
export EWS_ENDPOINT="https://owa.company.com/EWS/Exchange.asmx"
export EWS_USER_UPN="user@company.com"
export EWS_USER_LOGIN="user"
export EWS_USER_DOMAIN="COMPANY"
export EWS_PASSWORD="***"  # Никогда не коммитьте!

# LLM Configuration
export LLM_ENDPOINT="https://llm-gw.company.com/api/v1/chat"
export LLM_TOKEN="***"  # Никогда не коммитьте!

# Proxy (если нужен)
export http_proxy="http://proxy.company.com:8080"
export https_proxy="http://proxy.company.com:8080"
export no_proxy="localhost,127.0.0.1"

# Output directories
export OUT_DIR="$HOME/.digest-out"
export STATE_DIR="$HOME/.digest-state"
export TMPDIR="$HOME/.digest-temp"

# Защита .env файла
chmod 600 .env
```

---

## Чек-лист для корпоративного ноутбука

### Перед установкой

- [ ] Проверьте доступные права (можно ли использовать `$HOME`?)
- [ ] Получите корпоративный CA сертификат (у IT)
- [ ] Узнайте адрес прокси сервера (если есть)
- [ ] Подтвердите доступ к EWS endpoint
- [ ] Подтвердите доступ к LLM Gateway endpoint
- [ ] Проверьте версию Python (`python3 --version`)

### Во время установки

- [ ] Используйте `$HOME` для всех путей
- [ ] Настройте прокси перед клонированием
- [ ] Установите корпоративный CA сертификат
- [ ] Используйте `--trusted-host` для pip (если нужно)
- [ ] Создайте `.env` с правами 600

### После установки

- [ ] Запустите `./digest-core/scripts/doctor.sh`
- [ ] Проверьте подключение к EWS (dry-run)
- [ ] Проверьте все рабочие директории
- [ ] Убедитесь, что логи создаются
- [ ] Проверьте, что архивы диагностики можно создать

---

## Типичные ОС корпоративных ноутбуков

### Windows 10/11

**Особенности:**
- Чаще всего с ограничениями admin прав
- Антивирус Windows Defender или корпоративный
- Execution Policy для PowerShell
- Путь к домашней директории: `C:\Users\Username`

**Рекомендация:**
- Используйте WSL2 (Ubuntu)
- Работайте в Linux окружении

**Установка WSL:**
```powershell
# В PowerShell с admin правами (один раз)
wsl --install
```

### macOS

**Особенности:**
- Обычно меньше ограничений
- Homebrew для установки зависимостей
- Keychain для хранения секретов
- Gatekeeper для проверки подписей

**Рекомендация:**
- Используйте Homebrew
- Python через `python3` (не `python`)

**Установка зависимостей:**
```bash
brew update
brew install python@3.11 git
```

### Linux (Ubuntu/RHEL)

**Особенности:**
- Часто с ограниченными правами sudo
- SELinux или AppArmor
- Различные дистрибутивы с разными package managers

**Рекомендация:**
- Используйте user-local установки
- Python venv обязателен
- Проверьте SELinux policies

---

## Troubleshooting

### Не удается установить Python пакеты

```bash
# Проблема: SSL ошибки при pip install
pip install --trusted-host pypi.org \
            --trusted-host files.pythonhosted.org \
            -e .

# Или через прокси:
pip install --proxy http://proxy.company.com:8080 -e .
```

### Не удается клонировать репозиторий

```bash
# Проблема: SSL ошибки при git clone

# Решение 1: Настройте прокси
git config --global http.proxy http://proxy.company.com:8080

# Решение 2: Используйте SSH вместо HTTPS (если доступно)
git clone git@github.com:user/SummaryLLM.git

# Решение 3: Временно отключите SSL verify (не рекомендуется!)
git config --global http.sslVerify false
git clone https://...
git config --global http.sslVerify true  # Включите обратно!
```

### EWS подключение не работает

```bash
# Проверьте доступность endpoint
curl -I https://owa.company.com/EWS/Exchange.asmx

# Проверьте NTLM аутентификацию
curl --ntlm -u "user@company.com:password" \
     -I https://owa.company.com/EWS/Exchange.asmx

# Если SSL ошибка - добавьте --cacert
curl --cacert ~/certs/corporate-ca.pem \
     --ntlm -u "user@company.com:password" \
     -I https://owa.company.com/EWS/Exchange.asmx
```

---

## Получение помощи от IT

Если нужна помощь корпоративного IT:

### Запросите:
1. ✉️ Корпоративный CA сертификат (root CA certificate)
2. 🌐 Адрес и порт прокси сервера
3. 🔐 Подтверждение доступа к EWS endpoint для вашей учетной записи
4. 📦 Разрешения на установку Python пакетов
5. 📂 Подтверждение, что можно использовать `$HOME` для проектов

### Предоставьте им:
- Название проекта: SummaryLLM
- Цель: Тестирование email digest системы
- Требуемые подключения:
  - `owa.company.com:443` (EWS)
  - `llm-gw.company.com:443` (LLM Gateway)
  - `pypi.org:443` (для установки Python пакетов)
- Требуемые права: чтение/запись в `$HOME`

---

## См. также

- [E2E Testing Guide](../E2E_TESTING_GUIDE.md) - основной гайд по установке
- [Troubleshooting Guide](../../troubleshooting/TROUBLESHOOTING.md) - решение проблем
- [Пример успешного отчета](./successful_test_report.md)
- [Пример отчета с проблемами](./failed_test_report.md)


