"""
Скрипт для проверки статуса сервера и бота.
"""

import requests
import os
import sys

def check_server():
    """Проверка работы Flask-сервера."""
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code == 200:
            print("✅ Flask-сервер работает")
            print(f"   Ответ: {response.text}")
            return True
        else:
            print(f"❌ Flask-сервер вернул код: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Flask-сервер не отвечает: {e}")
        return False

def check_telegram_token():
    """Проверка наличия TELEGRAM_TOKEN."""
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        print("✅ TELEGRAM_TOKEN установлен")
        print(f"   Токен: {token[:10]}...{token[-5:]}")
        return True
    else:
        print("⚠️  TELEGRAM_TOKEN не установлен (бот не будет работать)")
        return False

def check_bitrix_config():
    """Проверка конфигурации Bitrix24."""
    webhook = os.environ.get("BITRIX_WEBHOOK")
    out_hook = os.environ.get("BITRIX_OUT_HOOK")
    
    if webhook:
        print("✅ BITRIX_WEBHOOK установлен")
    else:
        print("⚠️  BITRIX_WEBHOOK не установлен")
    
    if out_hook:
        print("✅ BITRIX_OUT_HOOK установлен")
    else:
        print("⚠️  BITRIX_OUT_HOOK не установлен")
    
    return webhook is not None

def check_gdrive_config():
    """Проверка конфигурации Google Drive."""
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    folder_id = os.environ.get("DRIVE_ROOT_FOLDER_ID")
    
    if creds:
        if os.path.exists(creds):
            print("✅ GOOGLE_APPLICATION_CREDENTIALS установлен и файл существует")
        else:
            print(f"⚠️  GOOGLE_APPLICATION_CREDENTIALS указан, но файл не найден: {creds}")
    else:
        print("⚠️  GOOGLE_APPLICATION_CREDENTIALS не установлен")
    
    if folder_id:
        print(f"✅ DRIVE_ROOT_FOLDER_ID установлен: {folder_id}")
    else:
        print("ℹ️  DRIVE_ROOT_FOLDER_ID не установлен (поиск по всему Drive)")
    
    return creds is not None and os.path.exists(creds) if creds else False

def test_bitrix_hook():
    """Тестовый запрос к /bitrix_hook."""
    try:
        payload = {
            "name": "Тестовый Пользователь",
            "message": "Тестовое сообщение"
        }
        response = requests.post(
            "http://localhost:8000/bitrix_hook",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Тестовый запрос к /bitrix_hook успешен")
            print(f"   Ответ: {response.json()}")
            return True
        else:
            print(f"❌ Тестовый запрос вернул код: {response.status_code}")
            print(f"   Ответ: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при тестовом запросе: {e}")
        return False

def main():
    print("=" * 50)
    print("Проверка статуса MAXCAPITAL Bot")
    print("=" * 50)
    print()
    
    # Проверки
    server_ok = check_server()
    print()
    
    telegram_ok = check_telegram_token()
    print()
    
    bitrix_ok = check_bitrix_config()
    print()
    
    gdrive_ok = check_gdrive_config()
    print()
    
    if server_ok:
        print("Тестирование /bitrix_hook...")
        test_bitrix_hook()
        print()
    
    print("=" * 50)
    print("Итоги:")
    print(f"  Flask-сервер: {'✅' if server_ok else '❌'}")
    print(f"  Telegram-бот: {'✅' if telegram_ok else '⚠️'}")
    print(f"  Bitrix24: {'✅' if bitrix_ok else '⚠️'}")
    print(f"  Google Drive: {'✅' if gdrive_ok else '⚠️'}")
    print("=" * 50)
    
    if not server_ok:
        print("\n⚠️  Сервер не работает. Убедитесь, что запущен 'python main.py'")
        sys.exit(1)

if __name__ == "__main__":
    main()

