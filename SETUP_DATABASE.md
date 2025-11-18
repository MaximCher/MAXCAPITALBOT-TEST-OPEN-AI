# Настройка базы данных PostgreSQL

## Быстрая инструкция

### Шаг 1: Убедитесь, что PostgreSQL установлен и запущен

### Шаг 2: Создайте базу данных

Откройте командную строку или psql и выполните:

```bash
# Подключитесь к PostgreSQL
psql -U postgres

# Создайте базу данных
CREATE DATABASE maxcapital_bot;

# Выйдите из psql
\q
```

### Шаг 3: Выполните SQL скрипт для создания таблиц

```bash
# Windows (PowerShell)
psql -U postgres -d maxcapital_bot -f database_schema.sql

# Linux/Mac
psql -U postgres -d maxcapital_bot -f database_schema.sql
```

Или через psql:

```bash
psql -U postgres -d maxcapital_bot
```

Затем скопируйте и вставьте содержимое файла `database_schema.sql` и нажмите Enter.

### Шаг 4: Проверьте, что таблицы созданы

```bash
psql -U postgres -d maxcapital_bot -c "\dt"
```

Должны появиться таблицы:
- bot_users
- bot_sessions
- bot_messages
- service_interests

### Шаг 5: Настройте .env файл

Убедитесь, что в `.env` указаны правильные настройки:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=maxcapital_bot
DB_USER=postgres
DB_PASSWORD=your_password_here
```

---

## Альтернатива: Работа без базы данных

Если вы не хотите использовать PostgreSQL, бот будет работать с JSON файлами для статистики. Просто не указывайте настройки БД в `.env` или убедитесь, что подключение не удается.

Ошибки в логах не критичны - бот продолжит работать, используя JSON файлы (`bot_statistics.json`).

