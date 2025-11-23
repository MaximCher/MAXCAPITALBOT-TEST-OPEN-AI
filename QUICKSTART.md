# MAXCAPITAL Bot - Quick Start ⚡

Get your bot running in 5 minutes!

## 🎯 Minimum Requirements

1. **Docker** installed on your system
2. **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
3. **OpenAI API Key** from [OpenAI Platform](https://platform.openai.com/)
4. **Bitrix24 Webhook URL** from your Bitrix24 account

## ⚡ Quick Setup

### 1. Configure Environment

Create `.env` file:

```bash
# Copy example
cp .env.example .env

# Edit with your credentials (use any text editor)
notepad .env   # Windows
nano .env      # Linux/Mac
```

**Minimum required configuration:**

```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
MANAGER_CHAT_ID=your_telegram_user_id
OPENAI_API_KEY=your_openai_api_key
BITRIX24_WEBHOOK_URL=https://your-domain.bitrix24.com/rest/1/webhook/crm.lead.add
POSTGRES_PASSWORD=ChangeThisToSecurePassword123!
```

### 2. Start the Bot

**On Windows:**
```bash
docker-compose up -d
docker-compose logs -f bot
```

**On Linux/Mac:**
```bash
./scripts/start.sh
```

### 3. Test the Bot

Open your bot in Telegram and send: `/start`

You should see the welcome message! 🎉

## 🧪 Quick Test

Run automated tests:

```bash
docker-compose exec bot python scripts/test_bot.py all
```

## 📚 Add Sample Knowledge

```bash
# Create sample document
docker-compose exec bot python -c "
import asyncio
from src.database import init_db, close_db, get_session
from src.vector_store import VectorStore

async def add_sample():
    await init_db()
    async for session in get_session():
        vs = VectorStore(session)
        await vs.add_document(
            filename='sample.txt',
            content='MAXCAPITAL предоставляет премиальные консалтинговые услуги в области venture capital, M&A, real estate, crypto investments, и HNWI consultations.'
        )
        print('✅ Sample document added')
    await close_db()

asyncio.run(add_sample())
"
```

## 🎮 Bot Commands

- `/start` - Start the bot
- `/help` - Show help
- `/services` - Browse services
- `/cancel` - Cancel current action

## 🔍 Troubleshooting

### Bot not starting?

```bash
# Check logs
docker-compose logs bot

# Check all services
docker-compose ps
```

### Connection issues?

```bash
# Restart services
docker-compose restart

# Or full restart
docker-compose down
docker-compose up -d
```

## 📖 Full Documentation

For detailed setup and configuration, see:
- **SETUP_GUIDE.md** - Complete setup instructions
- **README.md** - Full documentation

## 🚀 What's Next?

1. ✅ Bot is running
2. 📚 Load your documents (see SETUP_GUIDE.md)
3. 🎨 Customize messages in `src/config.py`
4. 📊 Monitor with `docker-compose logs -f`

---

**Need help? Check SETUP_GUIDE.md for detailed troubleshooting!**

