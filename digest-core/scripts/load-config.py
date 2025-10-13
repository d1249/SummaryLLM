#!/usr/bin/env python3
"""
Скрипт для автоматической загрузки переменных окружения из конфигурации SummaryLLM.
"""
import os
import sys
import yaml
from pathlib import Path


def load_config():
    """Загружает конфигурацию и экспортирует переменные окружения."""
    
    # Переходим в директорию проекта
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    os.chdir(project_dir)
    
    print("=== Загрузка конфигурации SummaryLLM ===")
    print(f"Директория проекта: {project_dir}")
    
    # Ищем конфигурационный файл
    config_files = [
        "configs/config.yaml",
        "configs/config.example.yaml"
    ]
    
    config_file = None
    config_data = None
    
    for file_path in config_files:
        if Path(file_path).exists():
            config_file = file_path
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                print(f"✓ Найден конфигурационный файл: {file_path}")
                break
            except Exception as e:
                print(f"⚠️  Ошибка чтения {file_path}: {e}")
                continue
    
    if not config_data:
        print("✗ Конфигурационный файл не найден или не может быть прочитан")
        print("Создайте файл configs/config.yaml или используйте setup-env.sh")
        return False
    
    # Извлекаем значения из конфигурации
    ews_config = config_data.get('ews', {})
    llm_config = config_data.get('llm', {})
    
    # EWS параметры (используем переменные окружения как fallback)
    ews_endpoint = ews_config.get('endpoint', '') or os.environ.get('EWS_ENDPOINT', '')
    ews_user_upn = ews_config.get('user_upn', '') or os.environ.get('EWS_USER_UPN', '')
    ews_user_login = ews_config.get('user_login', '') or os.environ.get('EWS_USER_LOGIN', '')
    ews_user_domain = ews_config.get('user_domain', '') or os.environ.get('EWS_USER_DOMAIN', '')
    
    # LLM параметры (используем переменные окружения как fallback)
    llm_endpoint = llm_config.get('endpoint', '') or os.environ.get('LLM_ENDPOINT', '')
    
    print("✓ Конфигурация прочитана")
    
    # Проверяем основные параметры
    if not ews_endpoint or not ews_user_upn:
        print("⚠️  Основные параметры EWS не настроены в конфигурации:")
        print(f"   EWS_ENDPOINT: {ews_endpoint or 'НЕ УСТАНОВЛЕН'}")
        print(f"   EWS_USER_UPN: {ews_user_upn or 'НЕ УСТАНОВЛЕН'}")
        print("\nДля настройки запустите: source scripts/setup-env.sh")
        return False
    
    # Экспортируем переменные окружения
    os.environ['EWS_ENDPOINT'] = ews_endpoint
    os.environ['EWS_USER_UPN'] = ews_user_upn
    
    if ews_user_login:
        os.environ['EWS_USER_LOGIN'] = ews_user_login
    
    if ews_user_domain:
        os.environ['EWS_USER_DOMAIN'] = ews_user_domain
    
    if llm_endpoint:
        os.environ['LLM_ENDPOINT'] = llm_endpoint
    
    # Проверяем чувствительные данные
    ews_password = os.environ.get('EWS_PASSWORD', '')
    llm_token = os.environ.get('LLM_TOKEN', '')
    
    print("\n=== Переменные окружения загружены ===")
    print(f"EWS_ENDPOINT: {ews_endpoint}")
    print(f"EWS_USER_UPN: {ews_user_upn}")
    print(f"EWS_USER_LOGIN: {ews_user_login or 'НЕ УСТАНОВЛЕН'}")
    print(f"EWS_USER_DOMAIN: {ews_user_domain or 'НЕ УСТАНОВЛЕН'}")
    print(f"LLM_ENDPOINT: {llm_endpoint or 'НЕ УСТАНОВЛЕН'}")
    print(f"EWS_PASSWORD: {'[УСТАНОВЛЕН]' if ews_password else '[НЕ УСТАНОВЛЕН]'}")
    print(f"LLM_TOKEN: {'[УСТАНОВЛЕН]' if llm_token else '[НЕ УСТАНОВЛЕН]'}")
    
    if not ews_password:
        print("\n⚠️  EWS_PASSWORD не установлен")
        print("Установите пароль: export EWS_PASSWORD='your_password'")
    
    print("\n=== Готово! ===")
    print("Для запуска приложения используйте:")
    print("  python3 -m src.digest_core.cli run --dry-run")
    
    return True


if __name__ == "__main__":
    try:
        success = load_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
