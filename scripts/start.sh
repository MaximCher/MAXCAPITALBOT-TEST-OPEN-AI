#!/bin/bash
# MAXCAPITAL Bot - Startup Script

set -e

echo "================================"
echo "MAXCAPITAL Bot - Starting"
echo "================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    echo "Please start Docker and try again"
    exit 1
fi

# Build and start services
echo "🔨 Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

echo "⏳ Waiting for database to be ready..."
sleep 5

# Check service health
echo "🔍 Checking service status..."
docker-compose ps

echo ""
echo "================================"
echo "✅ MAXCAPITAL Bot Started!"
echo "================================"
echo ""
echo "📋 Useful commands:"
echo "  View logs:    docker-compose logs -f bot"
echo "  Stop bot:     docker-compose down"
echo "  Restart:      docker-compose restart bot"
echo "  Shell:        docker-compose exec bot bash"
echo ""
echo "🧪 Testing:"
echo "  Test bot:     docker-compose exec bot python scripts/test_bot.py all"
echo "  Load docs:    docker-compose exec bot python scripts/load_documents.py load"
echo ""


