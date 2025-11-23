# MAXCAPITAL Bot - Setup Guide 🚀

Complete step-by-step guide to set up and deploy MAXCAPITAL Telegram Bot.

## 📋 Prerequisites

Before starting, make sure you have:

- ✅ A server or local machine with Docker installed
- ✅ Telegram account
- ✅ OpenAI account with API access
- ✅ Bitrix24 account with webhook access
- ✅ (Optional) Google Workspace account for Drive integration

## 🔧 Step 1: Create Telegram Bot

1. Open Telegram and find [@BotFather](https://t.me/botfather)

2. Send `/newbot` command

3. Choose a name: `MAXCAPITAL Bot`

4. Choose a username: `maxcapital_assistant_bot` (must end with 'bot')

5. Copy the bot token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

6. **Important**: Find your Manager Chat ID
   - Send a message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your user ID in the response
   - Or use [@userinfobot](https://t.me/userinfobot) to get your ID

## 🔑 Step 2: Get OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/)

2. Sign in or create an account

3. Go to [API Keys](https://platform.openai.com/api-keys)

4. Click "Create new secret key"

5. Copy and save the key (starts with `sk-`)

6. **Important**: Add billing information and set usage limits

## 🏢 Step 3: Configure Bitrix24 Webhook

1. Go to your Bitrix24 portal

2. Navigate to: **Settings** → **Developer resources** → **Other** → **Inbound webhook**

3. Create new webhook with permissions:
   - CRM (read/write)
   - User (read)

4. Copy the webhook URL (looks like: `https://your-domain.bitrix24.com/rest/1/abc123def456/`)

5. The full webhook URL for leads will be: `<YOUR_WEBHOOK_URL>crm.lead.add`

## 🌐 Step 4: Google Drive Setup (Optional)

If you want to sync documents from Google Drive:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)

2. Create a new project or select existing

3. Enable **Google Drive API**

4. Create **Service Account**:
   - Go to IAM & Admin → Service Accounts
   - Create service account
   - Download JSON key file

5. Share your Google Drive folder with the service account email

6. Get folder ID from URL: `https://drive.google.com/drive/folders/<FOLDER_ID>`

7. Save the JSON file as `credentials.json` in project root

## 📁 Step 5: Clone and Configure

```bash
# Clone or extract the project
cd MYBOT

# Create .env file from example
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Fill in your `.env`:

```env
# Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
MANAGER_CHAT_ID=123456789  # Your Telegram ID

# Database (you can keep these defaults)
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=maxcapital_bot
POSTGRES_USER=maxcapital
POSTGRES_PASSWORD=SecurePassword123!  # Change this!

# OpenAI
OPENAI_API_KEY=sk-proj-xxx...  # Your OpenAI key
OPENAI_MODEL=gpt-4-turbo-preview
EMBEDDING_MODEL=text-embedding-3-small

# Bitrix24
BITRIX24_WEBHOOK_URL=https://your-domain.bitrix24.com/rest/1/abc123/crm.lead.add

# Google Drive (optional)
GOOGLE_DRIVE_FOLDER_ID=1abc...xyz  # Your folder ID
GOOGLE_CREDENTIALS_FILE=credentials.json

# Settings
LOG_LEVEL=INFO
DEBUG_MODE=false
```

## 🐳 Step 6: Launch with Docker

### On Linux/Mac:

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Start the bot
./scripts/start.sh

# View logs
docker-compose logs -f bot
```

### On Windows:

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f bot
```

## ✅ Step 7: Test the Bot

### Test Components:

```bash
# Run all tests
docker-compose exec bot python scripts/test_bot.py all

# Test individual components
docker-compose exec bot python scripts/test_bot.py openai
docker-compose exec bot python scripts/test_bot.py bitrix
```

### Test in Telegram:

1. Open your bot in Telegram
2. Send `/start`
3. You should see the welcome message with service buttons
4. Try selecting a service
5. Send test contact data: `Тестов Тест +1234567890`
6. Check if you receive manager notification

## 📚 Step 8: Load Knowledge Base

If using Google Drive:

```bash
# Load documents from Google Drive
docker-compose exec bot python scripts/load_documents.py load

# List loaded documents
docker-compose exec bot python scripts/load_documents.py list

# Test search
docker-compose exec bot python scripts/load_documents.py search "venture capital"
```

Or manually add documents:

```python
# Create a script: scripts/add_sample_doc.py
import asyncio
from src.database import init_db, close_db, get_session
from src.vector_store import VectorStore

async def add_sample_document():
    await init_db()
    
    async for session in get_session():
        vector_store = VectorStore(session)
        
        sample_text = """
        MAXCAPITAL - международная консалтинговая компания.
        
        Мы предлагаем:
        - Венчурные инвестиции в технологические стартапы
        - Консультации для состоятельных клиентов (HNWI)
        - Инвестиции в премиальную недвижимость
        - Криптовалютные стратегии и управление
        - Сопровождение M&A сделок
        - Private Equity инвестиции
        - Помощь в релокации
        - Открытие зарубежных банковских счетов
        """
        
        await vector_store.add_document(
            filename="maxcapital_services.txt",
            content=sample_text,
            file_type="txt"
        )
        
        print("✅ Sample document added")
    
    await close_db()

if __name__ == "__main__":
    asyncio.run(add_sample_document())
```

Run:
```bash
docker-compose exec bot python scripts/add_sample_doc.py
```

## 📊 Step 9: Monitor and Maintain

### View Logs:

```bash
# Real-time logs
docker-compose logs -f bot

# Last 100 lines
docker-compose logs --tail=100 bot
```

### Check Statistics:

```bash
docker-compose exec bot python scripts/test_bot.py stats
```

### Access Database:

```bash
docker-compose exec db psql -U maxcapital -d maxcapital_bot

# Useful queries:
SELECT COUNT(*) FROM user_memory;
SELECT COUNT(*) FROM documents;
SELECT * FROM user_memory ORDER BY created_at DESC LIMIT 5;
```

## 🔄 Step 10: Updates and Maintenance

### Restart Bot:

```bash
docker-compose restart bot
```

### Update Code:

```bash
# Pull new code
git pull  # or update files manually

# Rebuild and restart
docker-compose up -d --build
```

### Backup Database:

```bash
# Backup
docker-compose exec db pg_dump -U maxcapital maxcapital_bot > backup.sql

# Restore
docker-compose exec -T db psql -U maxcapital maxcapital_bot < backup.sql
```

### Clean Restart:

```bash
# Stop everything
docker-compose down

# Remove volumes (WARNING: deletes database)
docker-compose down -v

# Start fresh
docker-compose up -d
```

## 🚨 Troubleshooting

### Bot doesn't respond:

1. Check logs: `docker-compose logs bot`
2. Verify bot token: `echo $TELEGRAM_BOT_TOKEN`
3. Test bot manually: `curl https://api.telegram.org/bot<TOKEN>/getMe`

### Database connection error:

1. Check if database is running: `docker-compose ps`
2. Check database logs: `docker-compose logs db`
3. Verify credentials in `.env`

### OpenAI errors:

1. Verify API key is valid
2. Check billing: https://platform.openai.com/account/billing
3. Check rate limits: https://platform.openai.com/account/rate-limits

### No documents found in search:

1. Check document count: `docker-compose exec bot python scripts/test_bot.py vector`
2. Load documents: `docker-compose exec bot python scripts/load_documents.py load`
3. Check database: `SELECT COUNT(*) FROM documents;`

## 🎉 Success Checklist

- [ ] Bot responds to `/start` command
- [ ] Service selection works
- [ ] Contact form works (parses name and phone)
- [ ] Lead created in Bitrix24
- [ ] Manager receives notification
- [ ] AI responds to questions
- [ ] Vector search finds relevant documents
- [ ] All tests pass

## 📞 Need Help?

If you encounter issues:

1. Check logs: `docker-compose logs -f`
2. Run tests: `docker-compose exec bot python scripts/test_bot.py all`
3. Review configuration in `.env`
4. Check Docker status: `docker-compose ps`

## 🚀 Production Deployment

For production deployment:

1. **Use a VPS/Cloud Server** (AWS, DigitalOcean, etc.)
2. **Set up HTTPS** for webhooks (optional for polling)
3. **Configure firewall** (only expose necessary ports)
4. **Set up monitoring** (Prometheus, Grafana, etc.)
5. **Enable automatic backups**
6. **Use secrets management** (AWS Secrets Manager, etc.)
7. **Set up log aggregation** (ELK stack, CloudWatch, etc.)

## 📝 Next Steps

After successful setup:

1. Customize bot messages in `src/config.py`
2. Add more documents to knowledge base
3. Train AI with company-specific information
4. Set up monitoring and alerts
5. Configure automatic backups
6. Test thoroughly with real users

---

**Congratulations! Your MAXCAPITAL Bot is ready! 🎊**