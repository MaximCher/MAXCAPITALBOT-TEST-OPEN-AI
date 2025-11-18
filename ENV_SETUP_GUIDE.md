# Руководство по настройке файла .env

Это руководство поможет вам правильно заполнить файл `.env` для работы MAXCAPITAL Bot.

## Шаг 1: Создайте файл .env

Скопируйте файл `env.example` в `.env`:

```bash
# Windows (PowerShell)
Copy-Item env.example .env

# Linux/Mac
cp env.example .env
```

## Шаг 2: Заполните обязательные переменные

### 1. Telegram Bot Token (ОБЯЗАТЕЛЬНО)

**Переменная:** `TELEGRAM_TOKEN`

**Как получить:**
1. Откройте Telegram и найдите бота [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Следуйте инструкциям: укажите имя и username для бота
4. BotFather выдаст вам токен вида: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
5. Скопируйте токен и вставьте в `.env`

**Пример:**
```
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

---

### 2. OpenAI API Key (ОБЯЗАТЕЛЬНО)

**Переменная:** `OPENAI_API_KEY`

**Как получить:**
1. Зарегистрируйтесь на [platform.openai.com](https://platform.openai.com)
2. Перейдите в раздел API Keys
3. Нажмите "Create new secret key"
4. Скопируйте ключ (он показывается только один раз!)
5. Вставьте в `.env`

**Пример:**
```
OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

**Дополнительно:** Вы можете выбрать модель (опционально):
```
OPENAI_MODEL=gpt-4o-mini  # По умолчанию (самая дешевая)
# Или используйте:
# OPENAI_MODEL=gpt-3.5-turbo  # Быстрее и дешевле
# OPENAI_MODEL=gpt-4  # Более умная, но дороже
```

---

### 3. Bitrix24 Webhooks (ОБЯЗАТЕЛЬНО)

**Переменные:** `BITRIX_WEBHOOK` и `BITRIX_OUT_HOOK`

**Как получить:**

#### BITRIX_WEBHOOK (для создания контактов и лидов):
1. Войдите в ваш Bitrix24
2. Перейдите в **Настройки** → **Разработчикам** → **Другое** → **Входящий вебхук**
3. Нажмите "Добавить вебхук"
4. Выберите права доступа:
   - ✅ CRM (crm) - полный доступ
   - ✅ Задачи и проекты (task) - если нужно
5. Скопируйте URL вебхука (выглядит как: `https://your-domain.bitrix24.ru/rest/1/abc123def456/`)
6. Вставьте в `.env` как `BITRIX_WEBHOOK`

#### BITRIX_OUT_HOOK (для отправки сообщений в чаты):
1. В том же разделе выберите **Исходящий вебхук**
2. Нажмите "Добавить вебхук"
3. Выберите права доступа:
   - ✅ Мессенджеры (im) - полный доступ
4. Скопируйте URL вебхука
5. Вставьте в `.env` как `BITRIX_OUT_HOOK`

**Пример:**
```
BITRIX_WEBHOOK=https://your-company.bitrix24.ru/rest/1/abc123def456ghi789/
BITRIX_OUT_HOOK=https://your-company.bitrix24.ru/rest/1/xyz789uvw456rst123/
```

**Примечание:** Замените `your-company` на ваш домен Bitrix24.

---

### 4. Google Drive Service Account (ОБЯЗАТЕЛЬНО для работы с документами)

**Переменная:** `GOOGLE_APPLICATION_CREDENTIALS`

**Как настроить:**

1. **Создайте проект в Google Cloud Console:**
   - Перейдите на [console.cloud.google.com](https://console.cloud.google.com)
   - Создайте новый проект или выберите существующий

2. **Включите Google Drive API:**
   - В меню выберите "APIs & Services" → "Library"
   - Найдите "Google Drive API" и нажмите "Enable"

3. **Создайте Service Account:**
   - Перейдите в "APIs & Services" → "Credentials"
   - Нажмите "Create Credentials" → "Service Account"
   - Заполните имя (например, "maxcapital-bot")
   - Нажмите "Create and Continue"
   - Роль можно оставить пустой или выбрать "Editor"
   - Нажмите "Done"

4. **Создайте ключ:**
   - Найдите созданный Service Account в списке
   - Нажмите на него → вкладка "Keys"
   - Нажмите "Add Key" → "Create new key"
   - Выберите формат JSON
   - Скачайте файл

5. **Разрешите доступ к Google Drive:**
   - Откройте скачанный JSON файл
   - Найдите поле `client_email` (выглядит как `maxcapital-bot@project-id.iam.gserviceaccount.com`)
   - Откройте Google Drive
   - Найдите папку, к которой нужен доступ
   - Правой кнопкой → "Настроить доступ"
   - Добавьте email из `client_email` с правами "Редактор" или "Читатель"

6. **Сохраните файл и укажите путь:**
   - Поместите JSON файл в папку проекта (например, `credentials/service-account.json`)
   - Укажите путь в `.env`

**Пример:**
```
GOOGLE_APPLICATION_CREDENTIALS=credentials/service-account.json
# Или абсолютный путь:
# GOOGLE_APPLICATION_CREDENTIALS=C:\Projects\MAXCAPITALBOT\credentials\service-account.json
```

**Дополнительно:** Укажите ID папок Google Drive (опционально):
```
DRIVE_ROOT_FOLDER_ID=1a2b3c4d5e6f7g8h9i0j  # Корневая папка для поиска
DRIVE_MATERIALS_FOLDER_ID=1x2y3z4a5b6c7d8e9f  # Папка с материалами для клиентов
DRIVE_INFO_FOLDER_ID=1m2n3o4p5q6r7s8t9u0v  # Папка с информацией для бота
```

**Как найти ID папки:**
- Откройте папку в Google Drive
- URL будет выглядеть как: `https://drive.google.com/drive/folders/1a2b3c4d5e6f7g8h9i0j`
- ID папки - это часть после `/folders/`

---

## Шаг 3: Заполните опциональные переменные

### Bitrix24 Manager Assignment (ОПЦИОНАЛЬНО)

Если вы хотите автоматически назначать менеджеров на лиды:

```
B24_DEFAULT_MANAGER_ID=123  # ID менеджера по умолчанию
```

**Как найти ID менеджера:**
1. В Bitrix24 перейдите в "Сотрудники"
2. Откройте профиль нужного сотрудника
3. В URL будет ID: `https://your-domain.bitrix24.ru/company/personal/user/123/`
4. Число `123` - это ID менеджера

**Дополнительно:** Можно назначить разных менеджеров по типам запросов:
```
B24_MANAGER_INVEST=123      # Менеджер для инвестиционных запросов
B24_MANAGER_DOCUMENTS=456  # Менеджер для запросов документов
B24_MANAGER_CONSULT=789    # Менеджер для консультаций
B24_MANAGER_SUPPORT=101    # Менеджер для поддержки
```

**Диалог Bitrix24 (опционально):**
```
B24_DEFAULT_DIALOG=chat1  # ID диалога для отправки сообщений (по умолчанию: chat1)
```

---

### Server Configuration (ОПЦИОНАЛЬНО)

Эти настройки нужны только если бот должен быть доступен извне (для webhook'ов):

```
PUBLIC_URL=https://your-domain.com  # Полный публичный URL
# ИЛИ используйте:
PUBLIC_HOSTNAME=your-domain.com     # Хостнейм
PUBLIC_SCHEME=https                 # Протокол (http или https)
```

**Если бот работает локально или в закрытой сети, эти настройки не нужны.**

---

### PostgreSQL Database Configuration (ОПЦИОНАЛЬНО)

Эти настройки нужны для сохранения статистики в базе данных:

```
DB_HOST=localhost          # Хост базы данных
DB_PORT=5432              # Порт PostgreSQL (по умолчанию 5432)
DB_NAME=maxcapital_bot    # Имя базы данных
DB_USER=postgres          # Пользователь базы данных
DB_PASSWORD=your_password # Пароль пользователя
DB_MIN_CONN=1             # Минимальное количество соединений в пуле
DB_MAX_CONN=10            # Максимальное количество соединений в пуле
```

**Как настроить:**
1. Установите PostgreSQL (если еще не установлен)
2. Создайте базу данных:
   ```sql
   CREATE DATABASE maxcapital_bot;
   ```
3. Выполните SQL скрипт для создания таблиц:
   ```bash
   psql -U postgres -d maxcapital_bot -f database_schema.sql
   ```
4. Заполните данные подключения в `.env`

**Примечание:** Если база данных не настроена, бот будет работать, но статистика будет сохраняться только в JSON файл.

---

## Пример полного файла .env

```env
# Telegram Bot Configuration
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# OpenAI Configuration
OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
OPENAI_MODEL=gpt-4o-mini

# Bitrix24 Configuration
BITRIX_WEBHOOK=https://your-company.bitrix24.ru/rest/1/abc123def456ghi789/
BITRIX_OUT_HOOK=https://your-company.bitrix24.ru/rest/1/xyz789uvw456rst123/
B24_DEFAULT_DIALOG=chat1
B24_DEFAULT_MANAGER_ID=123

# Google Drive Configuration
GOOGLE_APPLICATION_CREDENTIALS=credentials/service-account.json
DRIVE_ROOT_FOLDER_ID=1a2b3c4d5e6f7g8h9i0j
DRIVE_MATERIALS_FOLDER_ID=1x2y3z4a5b6c7d8e9f
DRIVE_INFO_FOLDER_ID=1m2n3o4p5q6r7s8t9u0v

# PostgreSQL Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=maxcapital_bot
DB_USER=postgres
DB_PASSWORD=your_secure_password_here
DB_MIN_CONN=1
DB_MAX_CONN=10

# Server Configuration (опционально, только для публичного доступа)
# PUBLIC_URL=https://your-domain.com
# PUBLIC_HOSTNAME=your-domain.com
# PUBLIC_SCHEME=https
```

---

## Проверка настроек

После заполнения `.env` файла проверьте:

1. **Файл существует:** Убедитесь, что файл `.env` находится в корне проекта
2. **Нет лишних пробелов:** Убедитесь, что после `=` нет пробелов (правильно: `KEY=value`, неправильно: `KEY= value`)
3. **Кавычки не нужны:** Не используйте кавычки вокруг значений (правильно: `KEY=value`, неправильно: `KEY="value"`)
4. **Комментарии:** Строки, начинающиеся с `#`, игнорируются

---

## Безопасность

⚠️ **ВАЖНО:**
- Никогда не коммитьте файл `.env` в Git (он уже в `.gitignore`)
- Не передавайте токены и ключи третьим лицам
- Регулярно обновляйте токены и ключи
- Используйте сильные пароли для базы данных

---

## Решение проблем

### Бот не запускается
- Проверьте, что все обязательные переменные заполнены
- Убедитесь, что нет синтаксических ошибок в `.env`
- Проверьте логи в `bot_events.log`

### Ошибки подключения к Bitrix24
- Проверьте правильность URL вебхуков
- Убедитесь, что вебхуки не истекли (они имеют срок действия)
- Проверьте права доступа вебхуков

### Ошибки Google Drive
- Проверьте путь к JSON файлу
- Убедитесь, что Service Account имеет доступ к папкам
- Проверьте, что Google Drive API включен

### Ошибки базы данных
- Проверьте, что PostgreSQL запущен
- Убедитесь, что база данных создана
- Проверьте правильность логина и пароля
- Убедитесь, что выполнены SQL скрипты из `database_schema.sql`

---

## Дополнительная помощь

Если у вас возникли проблемы:
1. Проверьте логи в файле `bot_events.log`
2. Убедитесь, что все зависимости установлены: `pip install -r requirements.txt`
3. Проверьте версию Python: `python --version` (нужна 3.8+)


