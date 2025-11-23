# MAXCAPITAL Bot - Configuration Checker
# Проверяет правильность заполнения .env

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "MAXCAPITAL Bot - Проверка .env" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

if (-not (Test-Path .env)) {
    Write-Host "❌ Файл .env не найден!" -ForegroundColor Red
    Write-Host "`nСоздайте его одним из способов:" -ForegroundColor Yellow
    Write-Host "  1. Интерактивно: .\setup_env.ps1" -ForegroundColor White
    Write-Host "  2. Вручную: copy TEST.env .env && notepad .env`n" -ForegroundColor White
    exit 1
}

Write-Host "✅ Файл .env найден`n" -ForegroundColor Green

# Читаем переменные
$env_content = Get-Content .env -Raw
$errors = @()
$warnings = @()

# Проверка обязательных полей
$required = @{
    "TELEGRAM_BOT_TOKEN" = "Токен Telegram бота"
    "MANAGER_CHAT_ID" = "Telegram ID менеджера"
    "POSTGRES_PASSWORD" = "Пароль базы данных"
    "OPENAI_API_KEY" = "OpenAI API ключ"
    "BITRIX24_WEBHOOK_URL" = "Bitrix24 webhook URL"
}

foreach ($key in $required.Keys) {
    $pattern = "$key=(.+)"
    if ($env_content -match $pattern) {
        $value = $matches[1].Trim()
        
        # Проверка на пустое значение
        if ([string]::IsNullOrWhiteSpace($value)) {
            $errors += "❌ $key не заполнен"
        }
        # Проверка на placeholder значения
        elseif ($value -like "*REPLACE*" -or $value -like "*your*" -or $value -like "*example*") {
            $errors += "❌ $key содержит placeholder: $value"
        }
        # Специфичные проверки
        elseif ($key -eq "TELEGRAM_BOT_TOKEN" -and -not ($value -match "^\d+:[A-Za-z0-9_-]+$")) {
            $errors += "❌ $key имеет неверный формат (должен быть: 123456789:ABCdef...)"
        }
        elseif ($key -eq "OPENAI_API_KEY" -and -not ($value -match "^sk-")) {
            $errors += "❌ $key должен начинаться с 'sk-'"
        }
        elseif ($key -eq "POSTGRES_PASSWORD" -and $value.Length -lt 6) {
            $warnings += "⚠️  $key слишком короткий (минимум 6 символов)"
        }
        else {
            $masked = $value.Substring(0, [Math]::Min(15, $value.Length)) + "..."
            Write-Host "✅ $key`: $masked" -ForegroundColor Green
        }
    }
    else {
        $errors += "❌ $key отсутствует в файле"
    }
}

# Вывод результатов
Write-Host ""
if ($errors.Count -gt 0) {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Red
    Write-Host "ОШИБКИ:" -ForegroundColor Red
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    Write-Host ""
}

if ($warnings.Count -gt 0) {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
    Write-Host "ПРЕДУПРЕЖДЕНИЯ:" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
    $warnings | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
    Write-Host ""
}

if ($errors.Count -eq 0 -and $warnings.Count -eq 0) {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host "✅ Конфигурация корректна!" -ForegroundColor Green
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host "`nЗапустите бота:" -ForegroundColor Cyan
    Write-Host "  docker-compose up -d`n" -ForegroundColor Yellow
    exit 0
}
else {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Red
    Write-Host "Исправьте ошибки в .env файле:" -ForegroundColor Red
    Write-Host "  notepad .env" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Red
    exit 1
}


