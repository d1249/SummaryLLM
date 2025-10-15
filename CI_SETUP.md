# CI/CD Setup Instructions

## Pre-commit Hooks

Установка pre-commit hooks для автоматической проверки кода:

```bash
# Установить pre-commit
pip install pre-commit

# Установить hooks
pre-commit install

# Запустить вручную на всех файлах
pre-commit run --all-files
```

## Запуск тестов

```bash
cd digest-core

# Установить зависимости для тестов
pip install pytest pytest-cov

# Запустить все тесты
pytest -v

# Запустить с coverage
pytest --cov=src/digest_core --cov-report=html

# Запустить только новые тесты
pytest tests/test_llm_strict_validation.py \
       tests/test_fallback_degrade.py \
       tests/test_timezone_normalization.py \
       tests/test_hierarchy_thresholds.py \
       tests/test_masking.py \
       tests/test_ru_detectors.py -v
```

## Линтинг

```bash
# Форматирование с black
black digest-core/src digest-core/tests --line-length=100

# Импорты с isort
isort digest-core/src digest-core/tests --profile=black

# Проверка с flake8
flake8 digest-core/src digest-core/tests --max-line-length=100 --extend-ignore=E203
```

## GitHub Actions (пример)

Создайте `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        cd digest-core
        pip install -e .
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        cd digest-core
        pytest -v --cov=src/digest_core --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./digest-core/coverage.xml

  lint:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"
    
    - name: Install dependencies
      run: |
        pip install black isort flake8
    
    - name: Run black
      run: black --check digest-core/src digest-core/tests --line-length=100
    
    - name: Run isort
      run: isort --check digest-core/src digest-core/tests --profile=black
    
    - name: Run flake8
      run: flake8 digest-core/src digest-core/tests --max-line-length=100 --extend-ignore=E203
```

## Docker CI

```bash
# Build and test in Docker
docker build -t summaryllm:test -f digest-core/docker/Dockerfile .
docker run --rm summaryllm:test pytest -v
```

## Acceptance Criteria Checklist

✅ Все LLM-ответы валидируются Pydantic или срабатывает фолбэк  
✅ Naive datetime не проходят валидацию (fail_on_naive=true)  
✅ Иерархия не включается на ~37 тредов/61 письмо  
✅ PII не утекает в LLM (входная/выходная валидация)  
✅ RU-дедлайны/действия детектируются  
✅ /healthz и /metrics доступны  
✅ Все pytest тесты зелёные  
✅ Линтер/форматтер проходит

