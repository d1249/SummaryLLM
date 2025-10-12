<!-- d3d99926-0f91-4ed0-b77d-6cc670d5be5a dda1eacb-6666-422e-87a3-7ef799926dce -->
# Исправить NTLM-аутентификацию для EWS

## Проблема

Текущая реализация использует UPN (`user@corp.com`) для аутентификации в EWS, но для NTLM нужен формат `login@domain`, где `login` - это часть до @ в корп. почте, а `domain` - это домен из корп. почты (например, `corp-domain.ru`).

## Изменения

### 1. Конфигурация (`digest-core/src/digest_core/config.py`)

Изменить `EWSConfig`:

- Добавить поля `user_login: str` и `user_domain: str`
- Сохранить `user_upn` для совместимости (email для primary_smtp_address)
- Добавить метод `get_ntlm_username()` который возвращает `{user_login}@{user_domain}`
- Вычислять домен из `user_upn` если `user_domain` не указан явно
```python
class EWSConfig(BaseModel):
    endpoint: str
    user_upn: str  # email для primary_smtp_address
    user_login: Optional[str] = None  # логин для NTLM
    user_domain: Optional[str] = None  # домен для NTLM
    password_env: str = "EWS_PASSWORD"
    # ... остальные поля
    
    def get_ntlm_username(self) -> str:
        """Получить username для NTLM (login@domain)."""
        if self.user_login and self.user_domain:
            return f"{self.user_login}@{self.user_domain}"
        # Fallback: извлечь из user_upn
        if '@' in self.user_upn:
            return self.user_upn
        raise ValueError("Cannot determine NTLM username")
```


### 2. EWS Ingest (`digest-core/src/digest_core/ingest/ews.py`)

В методе `_connect()` изменить создание credentials:

```python
# Создать credentials с NTLM username (login@domain)
credentials = Credentials(
    username=self.config.get_ntlm_username(),
    password=self.config.get_ews_password()
)
```

### 3. Setup Script (`scripts/setup.sh`)

#### 3.1 Запрос параметров

В функции `collect_ews_config()` изменить последовательность:

```bash
# 1. Запросить логин
prompt_with_default "Введите ваш логин (например, ivanov)" "" "EWS_LOGIN"

# 2. Запросить корпоративную почту
while true; do
    prompt_with_default "Введите корпоративную почту" "" "EWS_USER_UPN"
    if validate_email "$EWS_USER_UPN"; then
        print_success "Валидный email"
        break
    fi
done

# 3. Извлечь домен из почты
EWS_DOMAIN="${EWS_USER_UPN#*@}"
print_info "Домен определён как: $EWS_DOMAIN"

# 4. Запросить EWS endpoint
while true; do
    prompt_with_default "Введите EWS endpoint URL" "https://owa.$EWS_DOMAIN/EWS/Exchange.asmx" "EWS_ENDPOINT"
    if validate_https "$EWS_ENDPOINT"; then
        break
    fi
done

# 5. Запросить пароль
prompt_password "Введите пароль EWS" "EWS_PASSWORD"
```

#### 3.2 Тест подключения NTLM

Добавить функцию `test_ews_ntlm_connection()`:

```bash
test_ews_ntlm_connection() {
    print_info "Тестирование NTLM-подключения к EWS..."
    
    # Создать временный файл с FindItem запросом
    local finditem_xml=$(mktemp)
    cat > "$finditem_xml" << 'SOAP_EOF'
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
  <soap:Body>
    <FindItem Traversal="Shallow" xmlns="http://schemas.microsoft.com/exchange/services/2006/messages">
      <ItemShape>
        <t:BaseShape>IdOnly</t:BaseShape>
      </ItemShape>
      <ParentFolderIds>
        <t:DistinguishedFolderId Id="inbox"/>
      </ParentFolderIds>
    </FindItem>
  </soap:Body>
</soap:Envelope>
SOAP_EOF
    
    # Выполнить NTLM-запрос
    local ntlm_user="${EWS_LOGIN}@${EWS_DOMAIN}"
    local response=$(curl -s --ntlm -u "$ntlm_user:$EWS_PASSWORD" \
        -H 'Content-Type: text/xml; charset=utf-8' \
        -H 'SOAPAction: http://schemas.microsoft.com/exchange/services/2006/messages/FindItem' \
        --data @"$finditem_xml" \
        --max-time 30 \
        "$EWS_ENDPOINT" 2>&1)
    
    rm -f "$finditem_xml"
    
    # Проверить результат
    if echo "$response" | grep -q "ResponseCode"; then
        if echo "$response" | grep -q "NoError"; then
            print_success "NTLM-аутентификация успешна"
            return 0
        elif echo "$response" | grep -q "ErrorAccessDenied"; then
            print_error "Ошибка доступа - проверьте логин/пароль"
            return 1
        else
            print_warning "Получен ответ, но не NoError"
            return 0
        fi
    else
        print_error "Ошибка подключения к EWS"
        print_info "Проверьте endpoint и сетевую доступность"
        return 1
    fi
}
```

Вызвать тест в функции `validate_configuration()`:

```bash
# Test EWS NTLM connectivity
if ! test_ews_ntlm_connection; then
    print_error "NTLM-тест не пройден"
    read -p "Продолжить несмотря на ошибку? [y/N]: " continue_choice
    if [[ ! "$continue_choice" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
```

#### 3.3 Генерация конфигурации

Обновить создание `.env` и `config.yaml`:

В `.env`:

```bash
EWS_LOGIN="$EWS_LOGIN"
EWS_DOMAIN="$EWS_DOMAIN"
EWS_USER_UPN="$EWS_USER_UPN"
```

В `config.yaml`:

```yaml
ews:
  endpoint: "$EWS_ENDPOINT"
  user_upn: "$EWS_USER_UPN"
  user_login: "$EWS_LOGIN"
  user_domain: "$EWS_DOMAIN"
```

### 4. Пример конфигурации (`digest-core/configs/config.example.yaml`)

Обновить пример:

```yaml
ews:
  endpoint: "https://owa.corp-domain.ru/EWS/Exchange.asmx"
  user_upn: "login@corp-domain.ru"
  user_login: "login"
  user_domain: "corp-domain.ru"
  password_env: "EWS_PASSWORD"
```

## Файлы для изменения

1. `digest-core/src/digest_core/config.py` - добавить поля и метод для NTLM username
2. `digest-core/src/digest_core/ingest/ews.py` - использовать NTLM username
3. `scripts/setup.sh` - изменить запрос параметров и добавить NTLM-тест
4. `digest-core/configs/config.example.yaml` - обновить пример

### To-dos

- [ ] Добавить user_login, user_domain и метод get_ntlm_username() в EWSConfig
- [ ] Изменить создание credentials в _connect() на использование get_ntlm_username()
- [ ] Изменить collect_ews_config() для запроса логина, почты и endpoint отдельно, извлечь домен
- [ ] Добавить test_ews_ntlm_connection() с curl --ntlm тестом
- [ ] Вызвать NTLM-тест в validate_configuration()
- [ ] Обновить генерацию .env и config.yaml для сохранения логина и домена
- [ ] Обновить config.example.yaml с новыми полями