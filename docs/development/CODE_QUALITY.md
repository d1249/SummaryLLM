# Code Quality and Development Standards

Стандарты качества кода и инструменты для обеспечения консистентности в SummaryLLM.

## Обзор системы качества кода

### Принципы качества

- **Consistency** - единообразие стиля и подхода
- **Readability** - читаемость и понятность кода
- **Maintainability** - лёгкость поддержки и развития
- **Security** - безопасность и отсутствие уязвимостей
- **Performance** - производительность и эффективность

### Инструменты качества

1. **Linting** - ruff, flake8
2. **Formatting** - black, isort
3. **Type Checking** - mypy
4. **Security** - bandit, detect-secrets
5. **Complexity** - radon
6. **Documentation** - pydocstyle

## Pre-commit Hooks Setup

### Установка pre-commit

```bash
# Установка pre-commit
pip install pre-commit

# Установка hooks
pre-commit install

# Установка hooks для всех репозиториев
pre-commit install --install-hooks
```

### Конфигурация .pre-commit-config.yaml

```yaml
# .pre-commit-config.yaml
repos:
  # Ruff - быстрый линтер и форматтер
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  # Black - форматтер кода
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.11

  # isort - сортировка импортов
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: [--profile, black]

  # mypy - статическая типизация
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-python-dateutil]
        args: [--ignore-missing-imports, --no-strict-optional]

  # bandit - безопасность
  - repo: https://github.com/pycqa/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-r, src/, -f, json, -o, bandit-report.json]
        exclude: tests/

  # detect-secrets - поиск секретов
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]

  # pydocstyle - стиль документации
  - repo: https://github.com/pycqa/pydocstyle
    rev: 6.3.0
    hooks:
      - id: pydocstyle
        args: [--convention=google]

  # radon - сложность кода
  - repo: https://github.com/xenon-dark/radon-pre-commit
    rev: v0.1.0
    hooks:
      - id: radon-cc
        args: [--min, B, --show-complexity]
      - id: radon-mi
        args: [--min, B]

  # Общие проверки
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-toml
      - id: check-xml
      - id: check-added-large-files
        args: [--maxkb=1000]
      - id: check-merge-conflict
      - id: debug-statements
      - id: check-docstring-first
```

## Ruff Configuration

### pyproject.toml

```toml
[tool.ruff]
# Настройки ruff
target-version = "py311"
line-length = 88
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "ARG", # flake8-unused-arguments
    "SIM", # flake8-simplify
    "TCH", # flake8-type-checking
    "PTH", # flake8-use-pathlib
    "ERA", # eradicate
    "PL",  # pylint
    "RUF", # ruff-specific rules
]
ignore = [
    "E501",   # line too long (handled by black)
    "B008",   # do not perform function calls in argument defaults
    "C901",   # too complex
    "PLR0913", # too many arguments
    "PLR0915", # too many statements
]

[tool.ruff.per-file-ignores]
"tests/**/*" = ["PLR2004", "S101", "ARG", "FBT"]
"scripts/**/*" = ["T201"]

[tool.ruff.isort]
known-first-party = ["digest_core"]
force-sort-within-sections = true
```

## Black Configuration

### pyproject.toml

```toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''
```

## MyPy Configuration

### pyproject.toml

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
show_error_codes = true

# Исключения
[[tool.mypy.overrides]]
module = [
    "exchangelib.*",
    "sentence_transformers.*",
    "faiss.*",
]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

## Bandit Security Configuration

### .bandit

```ini
[bandit]
exclude_dirs = /tests,/venv,/.venv
skips = B101,B601
tests = B201,B301,B401,B501,B601
```

### Примеры использования

```python
# Пример безопасного кода
import os
import subprocess
from typing import List

def safe_system_call(command: List[str]) -> str:
    """Безопасный вызов системной команды."""
    # B602: subprocess call with shell=False (безопасно)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        shell=False  # Важно: shell=False
    )
    return result.stdout

def get_environment_variable(name: str) -> str:
    """Безопасное получение переменной окружения."""
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Environment variable {name} not set")
    return value

# Пример небезопасного кода (будет обнаружен bandit)
def unsafe_system_call(command: str) -> str:
    """Небезопасный вызов системной команды."""
    # B602: subprocess call with shell=True (небезопасно)
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout
```

## Detect-secrets Configuration

### .secrets.baseline

```json
{
  "version": "1.4.0",
  "plugins_used": [
    {
      "name": "ArtifactoryDetector"
    },
    {
      "name": "AWSKeyDetector"
    },
    {
      "name": "AzureStorageKeyDetector"
    },
    {
      "name": "Base64HighEntropyString",
      "limit": 4.5
    },
    {
      "name": "BasicAuthDetector"
    },
    {
      "name": "CloudantDetector"
    },
    {
      "name": "DiscordBotTokenDetector"
    },
    {
      "name": "GitHubTokenDetector"
    },
    {
      "name": "HexHighEntropyString",
      "limit": 3.0
    },
    {
      "name": "IbmCloudIamDetector"
    },
    {
      "name": "IbmCosHmacDetector"
    },
    {
      "name": "JwtTokenDetector"
    },
    {
      "name": "KeywordDetector",
      "keyword_exclude": ""
    },
    {
      "name": "MailchimpDetector"
    },
    {
      "name": "NpmDetector"
    },
    {
      "name": "PrivateKeyDetector"
    },
    {
      "name": "SendGridDetector"
    },
    {
      "name": "SlackDetector"
    },
    {
      "name": "SoftlayerDetector"
    },
    {
      "name": "SquareOAuthDetector"
    },
    {
      "name": "StripeDetector"
    },
    {
      "name": "TwilioKeyDetector"
    }
  ],
  "filters_used": [
    {
      "path": "detect_secrets.filters.allowlist.is_line_allowlisted"
    },
    {
      "path": "detect_secrets.filters.common.is_baseline_file"
    },
    {
      "path": "detect_secrets.filters.common.is_ignored_due_to_verification_policies",
      "min_level": 2
    },
    {
      "path": "detect_secrets.filters.heuristic.is_indirect_reference"
    },
    {
      "path": "detect_secrets.filters.heuristic.is_likely_id_string"
    },
    {
      "path": "detect_secrets.filters.heuristic.is_lock_file"
    },
    {
      "path": "detect_secrets.filters.heuristic.is_not_alphanumeric_string"
    },
    {
      "path": "detect_secrets.filters.heuristic.is_potential_uuid"
    },
    {
      "path": "detect_secrets.filters.heuristic.is_prefixed_with_dollar_sign"
    },
    {
      "path": "detect_secrets.filters.heuristic.is_sequential_string"
    },
    {
      "path": "detect_secrets.filters.heuristic.is_swagger_file"
    },
    {
      "path": "detect_secrets.filters.heuristic.is_templated_secret"
    }
  ],
  "results": {},
  "generated_at": "2024-01-15T10:00:00Z"
}
```

## Pydocstyle Configuration

### pyproject.toml

```toml
[tool.pydocstyle]
convention = "google"
add-ignore = ["D100", "D104"]
```

### Примеры документации

```python
def process_email_message(
    message: Dict[str, Any], 
    config: Config
) -> ProcessedMessage:
    """Process a single email message.
    
    Args:
        message: Raw email message dictionary containing msg_id, subject, body, etc.
        config: Configuration object with processing settings.
        
    Returns:
        ProcessedMessage object with normalized content and metadata.
        
    Raises:
        ValidationError: If message format is invalid.
        ProcessingError: If message processing fails.
        
    Example:
        >>> message = {"msg_id": "123", "subject": "Test", "body": "Hello"}
        >>> config = Config()
        >>> processed = process_email_message(message, config)
        >>> print(processed.normalized_body)
        Hello
    """
    pass

class EmailProcessor:
    """Processor for email messages.
    
    This class handles the normalization and processing of email messages
    from various sources (EWS, IMAP, etc.).
    
    Attributes:
        config: Configuration object for processing settings.
        normalizer: HTML normalizer instance.
        quote_cleaner: Quote cleaner instance.
        
    Example:
        >>> processor = EmailProcessor(config)
        >>> processed = processor.process(messages)
    """
    
    def __init__(self, config: Config):
        """Initialize email processor.
        
        Args:
            config: Configuration object with processing settings.
        """
        self.config = config
        self.normalizer = HTMLNormalizer()
        self.quote_cleaner = QuoteCleaner()
```

## Radon Complexity Analysis

### Конфигурация

```toml
[tool.radon]
exclude = "tests/*,venv/*,.venv/*"
show_complexity = true
min = "B"
max = "F"
no_assert = false
```

### Примеры анализа сложности

```python
# Простая функция (A - низкая сложность)
def get_user_email(user_id: str) -> str:
    """Get user email by ID."""
    return f"{user_id}@corp.com"

# Средняя сложность (B)
def process_message(message: Dict[str, Any]) -> ProcessedMessage:
    """Process message with moderate complexity."""
    if not message:
        raise ValueError("Message cannot be empty")
    
    if message.get("type") == "email":
        return process_email(message)
    elif message.get("type") == "chat":
        return process_chat(message)
    else:
        raise ValueError(f"Unknown message type: {message.get('type')}")

# Высокая сложность (C - требует рефакторинга)
def complex_processing_logic(data: List[Dict]) -> List[Dict]:
    """Complex processing logic that should be refactored."""
    results = []
    for item in data:
        if item.get("type") == "email":
            if item.get("priority") == "high":
                if item.get("sender") in VIP_USERS:
                    if item.get("subject").startswith("URGENT"):
                        # Слишком много вложенных условий
                        results.append(process_urgent_vip_email(item))
                    else:
                        results.append(process_vip_email(item))
                else:
                    results.append(process_high_priority_email(item))
            else:
                results.append(process_normal_email(item))
        elif item.get("type") == "chat":
            # Ещё больше логики...
            pass
    return results
```

## Makefile для качества кода

### digest-core/Makefile

```makefile
.PHONY: lint format type-check security test quality

# Линтинг
lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

# Форматирование
format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

# Проверка типов
type-check:
	mypy src/

# Безопасность
security:
	bandit -r src/ -f json -o bandit-report.json
	detect-secrets scan --baseline .secrets.baseline

# Документация
docs-check:
	pydocstyle src/

# Сложность кода
complexity:
	radon cc src/ --min B
	radon mi src/ --min B

# Полная проверка качества
quality: lint type-check security docs-check complexity

# Автоисправление
fix: format
	ruff check --fix src/ tests/

# Тестирование
test:
	pytest tests/ -v --cov=src --cov-report=term-missing

# Полная проверка
ci: quality test
```

## GitHub Actions для качества

### .github/workflows/quality.yml

```yaml
name: Code Quality

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install uv
        cd digest-core
        uv sync --dev
    
    - name: Run linting
      run: |
        cd digest-core
        make lint
    
    - name: Run type checking
      run: |
        cd digest-core
        make type-check
    
    - name: Run security checks
      run: |
        cd digest-core
        make security
    
    - name: Check documentation
      run: |
        cd digest-core
        make docs-check
    
    - name: Check complexity
      run: |
        cd digest-core
        make complexity
    
    - name: Run tests
      run: |
        cd digest-core
        make test
```

## IDE Configuration

### VS Code Settings

```json
{
  "python.defaultInterpreterPath": "./digest-core/.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "black",
  "python.sortImports.args": ["--profile", "black"],
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "python.analysis.typeCheckingMode": "strict",
  "python.analysis.autoImportCompletions": true
}
```

### PyCharm Configuration

1. **File → Settings → Tools → External Tools**
2. Добавить ruff, black, mypy как external tools
3. **File → Settings → Inspections → Python**
4. Включить все проверки качества кода

## Best Practices

### Стиль кода

```python
# ✅ Хорошо
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def process_messages(
    messages: List[Dict[str, Any]], 
    config: Config,
    output_dir: Optional[Path] = None
) -> List[ProcessedMessage]:
    """Process list of messages with configuration.
    
    Args:
        messages: List of message dictionaries to process.
        config: Configuration object with processing settings.
        output_dir: Optional output directory for results.
        
    Returns:
        List of processed message objects.
    """
    if not messages:
        logger.warning("No messages to process")
        return []
    
    results = []
    for message in messages:
        try:
            processed = process_single_message(message, config)
            results.append(processed)
        except Exception as e:
            logger.error(f"Failed to process message {message.get('id')}: {e}")
            continue
    
    return results

# ❌ Плохо
def processMessages(messages, config, outputDir=None):
    if len(messages) == 0:
        return []
    results = []
    for msg in messages:
        try:
            p = processSingleMessage(msg, config)
            results.append(p)
        except:
            pass
    return results
```

### Обработка ошибок

```python
# ✅ Хорошо
from typing import Union
import logging

logger = logging.getLogger(__name__)

def safe_divide(a: float, b: float) -> Union[float, None]:
    """Safely divide two numbers.
    
    Args:
        a: Dividend.
        b: Divisor.
        
    Returns:
        Result of division or None if division by zero.
    """
    try:
        return a / b
    except ZeroDivisionError:
        logger.warning(f"Division by zero: {a} / {b}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in division: {e}")
        return None

# ❌ Плохо
def divide(a, b):
    try:
        return a / b
    except:
        return None
```

### Типизация

```python
# ✅ Хорошо
from typing import Protocol, TypeVar, Generic
from dataclasses import dataclass

T = TypeVar('T')

class Processor(Protocol[T]):
    """Protocol for message processors."""
    
    def process(self, data: T) -> T:
        """Process data and return result."""
        ...

@dataclass
class MessageConfig:
    """Configuration for message processing."""
    max_length: int = 1000
    preserve_formatting: bool = True
    remove_quotes: bool = True

# ❌ Плохо
def process(data):
    return data
```

---

**Итог:** Эта система качества кода обеспечивает консистентность, безопасность и поддерживаемость кода SummaryLLM через автоматизированные проверки и чёткие стандарты разработки.
