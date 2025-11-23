#!/bin/bash
# MAXCAPITAL Bot - Stop Script

set -e

echo "================================"
echo "MAXCAPITAL Bot - Stopping"
echo "================================"

echo "🛑 Stopping services..."
docker-compose down

echo ""
echo "✅ MAXCAPITAL Bot Stopped"
echo ""
echo "To start again: ./scripts/start.sh"
echo ""


