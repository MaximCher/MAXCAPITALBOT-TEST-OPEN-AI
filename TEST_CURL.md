# Тестовые примеры для API

Примеры curl-запросов для тестирования endpoint `/bitrix_hook`.

## Тест 1: Intent "invest"

```bash
curl -X POST http://localhost:8000/bitrix_hook \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Иван Иванов",
    "phone": "+79001234567",
    "email": "ivan@example.com",
    "message": "Хочу инвестировать 10000 в продукт X",
    "product": "Продукт X"
  }'
```

**Ожидаемый результат:**
- `detected_intent`: `"invest"`
- `contact_id`: ID созданного/обновленного контакта
- `lead_id`: ID созданного лида
- `contact_status`: `"created"` или `"updated"`

**Пример ответа:**
```json
{
  "contact_id": 123,
  "contact_status": "created",
  "lead_id": 456,
  "detected_intent": "invest"
}
```

---

## Тест 2: Intent "documents"

```bash
curl -X POST http://localhost:8000/bitrix_hook \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Петр Петров",
    "phone": "+79007654321",
    "email": "petr@example.com",
    "message": "Нужна презентация проекта"
  }'
```

**Ожидаемый результат:**
- `detected_intent`: `"documents"`
- `contact_id`: ID созданного/обновленного контакта
- `lead_id`: ID созданного лида
- `drive_files`: массив найденных файлов из Google Drive (может быть пустым, если файлы не найдены)
- `contact_status`: `"created"` или `"updated"`

**Пример ответа:**
```json
{
  "contact_id": 124,
  "contact_status": "created",
  "lead_id": 457,
  "detected_intent": "documents",
  "drive_files": [
    {
      "id": "file_id_123",
      "name": "Презентация проекта.pdf",
      "mimeType": "application/pdf",
      "webViewLink": "https://drive.google.com/file/d/.../view"
    }
  ]
}
```

---

## Примечания

- Все запросы должны содержать обязательное поле `name`
- Поле `message` используется для определения intent через `detect_intent()`
- При `detected_intent == "documents"` выполняется поиск файлов в Google Drive через `gdrive_service.find_files_by_name()` в папке, указанной в `DRIVE_ROOT_FOLDER_ID`
- Результаты поиска файлов добавляются в ответ под ключом `drive_files` только если intent равен `"documents"`
- Все события логируются в файл `bot_events.log`:
  - `payload_received` - получен payload
  - `intent_detected` - определен intent
  - `contact_upserted` - контакт создан/обновлен
  - `lead_created` - лид создан
  - `drive_files_found` - найдены файлы в Google Drive

## Telegram Bot

Бот автоматически пересылает все сообщения пользователей на `/bitrix_hook` и отвечает пользователю с информацией о:
- Создании/обновлении контакта
- Создании лида
- Определенном намерении (intent)
- Найденных документах из Google Drive (если intent = "documents")

Для работы бота требуется переменная окружения `TELEGRAM_TOKEN`.

