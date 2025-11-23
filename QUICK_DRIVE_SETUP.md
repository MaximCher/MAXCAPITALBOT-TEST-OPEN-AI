# ⚡ Быстрая настройка Google Drive - 5 минут

## 🎯 Что нужно сделать:

### 1️⃣ Создать Service Account (2 минуты)

1. https://console.cloud.google.com/
2. Создать проект "MAXCAPITAL Bot"
3. Включить "Google Drive API"
4. Создать Service Account
5. Скачать JSON ключ → сохранить как `credentials.json`

### 2️⃣ Поделиться папкой (1 минута)

1. Открыть `credentials.json`
2. Найти `"client_email"` (длинный email)
3. Открыть Google Drive: https://drive.google.com/drive/folders/1E6BVTqJCDnJh1FvE1x9Hs6ktmijeYEnG
4. Поделиться → вставить email → права "Читатель"

### 3️⃣ Установить файл (30 секунд)

```powershell
# Переместить credentials.json в папку проекта
Move-Item "$env:USERPROFILE\Downloads\*.json" "credentials.json"
```

### 4️⃣ Загрузить документы (1 минута)

```powershell
# Перезапустить с новым credentials
docker-compose down && docker-compose up -d

# Загрузить все документы
docker-compose exec bot python scripts/load_from_drive.py
```

## ✅ Готово!

Теперь бот знает всё из ваших документов и может использовать это в ответах! 🎉

---

**Подробная инструкция:** см. `GOOGLE_DRIVE_SETUP.md`


