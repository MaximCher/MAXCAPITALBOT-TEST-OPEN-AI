# MAXCAPITAL Telegram Bot 🤖

Production-ready Telegram bot for MAXCAPITAL consulting and investment company.

## 🎯 Features

- **AI-Powered Consultation** - OpenAI GPT-4 integration with RAG (Retrieval-Augmented Generation)
- **Vector Database** - PostgreSQL with pgvector for semantic document search
- **User Memory** - Persistent conversation history and user profiles
- **CRM Integration** - Automatic lead creation in Bitrix24
- **Document Management** - Google Drive integration for knowledge base
- **Manager Notifications** - Real-time notifications to managers
- **Premium UX** - Beautiful interface with inline keyboards and structured flow

## 🏗 Architecture

### Tech Stack

- **Python 3.11+** - Modern async Python
- **aiogram 3.x** - Telegram Bot framework
- **PostgreSQL + pgvector** - Database with vector search
- **SQLAlchemy 2.0** - Async ORM
- **OpenAI API** - GPT-4 and embeddings
- **Docker + docker-compose** - Containerization
- **structlog** - Structured logging

### Project Structure

```
MYBOT/
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── bot.py               # Bot setup
│   ├── config.py            # Configuration
│   ├── database.py          # Database connection
│   ├── logger.py            # Logging setup
│   ├── ai_agent.py          # OpenAI agent
│   ├── vector_store.py      # Vector DB operations
│   ├── bitrix.py            # Bitrix24 integration
│   ├── google_drive_loader.py # Google Drive loader
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user_memory.py   # User model
│   │   └── documents.py     # Document model
│   └── handlers/
│       ├── __init__.py
│       ├── start.py         # /start command
│       ├── services.py      # Service selection
│       ├── lead.py          # Lead creation
│       └── chat.py          # AI conversations
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── init.sql                 # Database initialization
├── .env.example
└── README.md
```

## 🚀 Quick Start

### 1. Prerequisites

- Docker and Docker Compose
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- OpenAI API Key
- Bitrix24 Webhook URL
- (Optional) Google Drive credentials

### 2. Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
MANAGER_CHAT_ID=your_manager_chat_id

# PostgreSQL
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=maxcapital_bot
POSTGRES_USER=maxcapital
POSTGRES_PASSWORD=your_secure_password

# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4-turbo-preview
EMBEDDING_MODEL=text-embedding-3-small

# Bitrix24
BITRIX24_WEBHOOK_URL=https://your-domain.bitrix24.com/rest/1/webhook/crm.lead.add

# Google Drive (optional)
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
GOOGLE_CREDENTIALS_FILE=credentials.json

# App Settings
LOG_LEVEL=INFO
DEBUG_MODE=false
```

### 3. Run with Docker

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f bot

# Stop
docker-compose down
```

### 4. Run Locally (Development)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Make sure PostgreSQL is running with pgvector
# Update .env with local database credentials

# Run the bot
python -m src.main
```

## 📚 Usage

### For Users

1. Start the bot: `/start`
2. Choose a service from the menu
3. Provide your contact information (Name + Phone)
4. Get AI-powered consultation
5. Manager will contact you

### For Administrators

#### Load Documents to Vector Store

Create a script to load documents from Google Drive:

```python
# scripts/load_documents.py
import asyncio
from src.database import init_db, get_session
from src.google_drive_loader import GoogleDriveLoader
from src.vector_store import VectorStore

async def load_documents():
    await init_db()
    
    async for session in get_session():
        loader = GoogleDriveLoader()
        vector_store = VectorStore(session)
        
        # Load all documents from Google Drive
        documents = await loader.load_all_documents()
        
        for doc in documents:
            await vector_store.add_document(
                filename=doc['filename'],
                content=doc['content'],
                file_type=doc['file_type'],
                file_size=doc['file_size'],
                drive_file_id=doc['drive_file_id']
            )
        
        print(f"Loaded {len(documents)} documents")

if __name__ == "__main__":
    asyncio.run(load_documents())
```

Run:
```bash
python scripts/load_documents.py
```

## 🎨 Services

The bot offers the following services:

- 🚀 **Venture Capital** - Startup investments
- 💎 **HNWI Consultations** - High-net-worth individuals
- 🏛 **Real Estate** - Premium property investments
- ₿ **Crypto** - Cryptocurrency strategies
- 🤝 **M&A** - Mergers and acquisitions
- 📊 **Private Equity** - Private investments
- 🌍 **Relocation Support** - International relocation
- 💳 **Foreign Bank Cards** - International banking

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from BotFather | Yes |
| `MANAGER_CHAT_ID` | Telegram ID or group ID for notifications | Yes |
| `POSTGRES_*` | PostgreSQL connection settings | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `BITRIX24_WEBHOOK_URL` | Bitrix24 webhook for lead creation | Yes |
| `GOOGLE_DRIVE_FOLDER_ID` | Google Drive folder ID | No |
| `LOG_LEVEL` | Logging level (INFO, DEBUG, WARNING) | No |

### Database Schema

The bot uses two main tables:

#### `user_memory`
- Stores user profiles and conversation history
- Includes: user_id, full_name, phone, selected_service, conversation_history (JSONB)

#### `documents`
- Stores documents with vector embeddings for RAG
- Includes: id, filename, content_text, embedding (vector(1536)), metadata

## 📊 Monitoring

### Logs

Logs are stored in `logs/maxcapital_bot.log` and output to console.

View logs:
```bash
# Docker
docker-compose logs -f bot

# Local
tail -f logs/maxcapital_bot.log
```

### Database

Connect to PostgreSQL:
```bash
docker-compose exec db psql -U maxcapital -d maxcapital_bot
```

Check statistics:
```sql
-- Count users
SELECT COUNT(*) FROM user_memory;

-- Count documents
SELECT COUNT(*) FROM documents;

-- Recent leads
SELECT user_id, full_name, phone, selected_service, created_at 
FROM user_memory 
ORDER BY created_at DESC 
LIMIT 10;
```

## 🧪 Testing

### Test Bot Commands

1. `/start` - Should show welcome message with service buttons
2. Select a service - Should ask for contact data
3. Send "Иванов Иван +41791234567" - Should create lead and enable consultation
4. Send a question - Should get AI response with RAG context

### Test Components

```python
# Test OpenAI connection
from src.ai_agent import AIAgent
agent = AIAgent()
response = await agent.generate_answer("Test question", [], None)

# Test Bitrix24 connection
from src.bitrix import BitrixClient
client = BitrixClient()
result = await client.test_connection()

# Test vector search
from src.vector_store import VectorStore
store = VectorStore(session)
results = await store.search("venture capital", limit=3)
```

## 🔒 Security

- Store sensitive credentials in `.env` (never commit to git)
- Use strong PostgreSQL passwords
- Restrict Docker ports (only expose what's needed)
- Use HTTPS for webhooks
- Validate user input
- Rate limit API calls

## 📈 Performance

- Database connection pooling
- Async operations throughout
- Vector search optimization with IVFFlat index
- Conversation history limited to last 20 messages
- Document chunking for large files

## 🐛 Troubleshooting

### Bot doesn't start

- Check `.env` configuration
- Verify bot token is valid
- Check database connection
- View logs: `docker-compose logs bot`

### Database connection fails

- Ensure PostgreSQL is running: `docker-compose ps`
- Check credentials in `.env`
- Verify network connectivity

### OpenAI API errors

- Check API key validity
- Verify API quota and billing
- Check rate limits

### Vector search returns no results

- Ensure documents are loaded: `SELECT COUNT(*) FROM documents;`
- Check embedding dimension (should be 1536)
- Lower similarity threshold in search

## 🤝 Contributing

This is a proprietary bot for MAXCAPITAL. For issues or improvements, contact the development team.

## 📞 Support

- **Website**: https://maxcapital.ch/
- **Contacts**: https://maxcapital.ch/contacts

## 📝 License

© 2025 MAXCAPITAL. All rights reserved.

---

**Built with ❤️ for MAXCAPITAL**


