# MAXCAPITAL Bot - Environment Setup Script
# Этот скрипт поможет правильно настроить .env файл

Write-Host "================================" -ForegroundColor Cyan
Write-Host "MAXCAPITAL Bot - Настройка .env" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# Проверяем существование .env
if (Test-Path .env) {
    Write-Host "[!] Файл .env уже существует." -ForegroundColor Yellow
    $overwrite = Read-Host "Хотите пересоздать? (y/n)"
    if ($overwrite -ne "y") {
        Write-Host "`nИспользуем существующий .env" -ForegroundColor Green
        Write-Host "Редактируйте его вручную: notepad .env`n" -ForegroundColor Yellow
        exit
    }
}

Write-Host "`n[1/5] Telegram Bot Configuration" -ForegroundColor Green
Write-Host "Получите токен от @BotFather в Telegram"
$botToken = Read-Host "Введите TELEGRAM_BOT_TOKEN"

Write-Host "`n[2/5] Manager Telegram ID" -ForegroundColor Green
Write-Host "Получите ваш ID от @userinfobot"
$managerId = Read-Host "Введите MANAGER_CHAT_ID"

Write-Host "`n[3/5] Database Password" -ForegroundColor Green
Write-Host "Придумайте надежный пароль (только латинские буквы и цифры)"
$dbPassword = Read-Host "Введите POSTGRES_PASSWORD"
if ([string]::IsNullOrWhiteSpace($dbPassword)) {
    $dbPassword = "MaxCapital2024"
    Write-Host "Используем пароль по умолчанию: MaxCapital2024" -ForegroundColor Yellow
}

Write-Host "`n[4/5] OpenAI API Key" -ForegroundColor Green
Write-Host "Получите ключ на https://platform.openai.com/api-keys"
$openaiKey = Read-Host "Введите OPENAI_API_KEY"

Write-Host "`n[5/5] Bitrix24 Webhook URL" -ForegroundColor Green
Write-Host "Формат: https://domain.bitrix24.com/rest/1/key/crm.lead.add"
$bitrixUrl = Read-Host "Введите BITRIX24_WEBHOOK_URL"

# Создаем .env файл
$envContent = @"
# MAXCAPITAL Bot Configuration
# Сгенерировано: $(Get-Date)

# ====================================
# TELEGRAM BOT
# ====================================
TELEGRAM_BOT_TOKEN=$botToken
MANAGER_CHAT_ID=$managerId

# ====================================
# DATABASE
# ====================================
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=maxcapital_bot
POSTGRES_USER=maxcapital
POSTGRES_PASSWORD=$dbPassword

# ====================================
# OPENAI API
# ====================================
OPENAI_API_KEY=$openaiKey
OPENAI_MODEL=gpt-4-turbo-preview
EMBEDDING_MODEL=text-embedding-3-small

# ====================================
# BITRIX24 CRM
# ====================================
BITRIX24_WEBHOOK_URL=$bitrixUrl

# ====================================
# GOOGLE DRIVE (OPTIONAL)
# ====================================
GOOGLE_DRIVE_FOLDER_ID=
GOOGLE_CREDENTIALS_FILE=credentials.json

# ====================================
# APP SETTINGS
# ====================================
LOG_LEVEL=INFO
DEBUG_MODE=false
"@

# Сохраняем файл
$envContent | Out-File -FilePath .env -Encoding UTF8 -NoNewline

Write-Host "`n================================" -ForegroundColor Green
Write-Host "✅ Файл .env успешно создан!" -ForegroundColor Green
Write-Host "================================`n" -ForegroundColor Green

Write-Host "Проверьте содержимое:" -ForegroundColor Cyan
Write-Host "  notepad .env`n" -ForegroundColor Yellow

Write-Host "Запустите бота:" -ForegroundColor Cyan
Write-Host "  docker-compose up -d`n" -ForegroundColor Yellow

Write-Host "Проверьте логи:" -ForegroundColor Cyan
Write-Host "  docker-compose logs -f bot`n" -ForegroundColor Yellow


