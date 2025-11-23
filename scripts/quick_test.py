"""
MAXCAPITAL Bot - Quick Test & Setup Helper
Simple interactive script to verify configuration
"""

import os
import sys
from pathlib import Path

def check_file(filepath, description):
    """Check if file exists"""
    exists = os.path.exists(filepath)
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {filepath}")
    return exists

def check_env_var(var_name, required=True):
    """Check if environment variable is set"""
    value = os.getenv(var_name)
    has_value = bool(value)
    
    if required:
        status = "✅" if has_value else "❌"
        masked = f"{value[:10]}..." if has_value and len(value) > 10 else value
    else:
        status = "⚠️" if not has_value else "✅"
        masked = f"{value[:10]}..." if has_value and len(value) > 10 else "not set"
    
    print(f"{status} {var_name}: {masked}")
    return has_value if required else True

def main():
    """Run quick configuration check"""
    print("="*60)
    print("MAXCAPITAL Bot - Configuration Check")
    print("="*60)
    print()
    
    # Check files
    print("📁 Required Files:")
    files_ok = all([
        check_file(".env", ".env file"),
        check_file("docker-compose.yml", "docker-compose.yml"),
        check_file("requirements.txt", "requirements.txt"),
        check_file("src/main.py", "main.py"),
    ])
    print()
    
    # Load .env if exists
    if os.path.exists(".env"):
        from dotenv import load_dotenv
        load_dotenv()
    
    # Check environment variables
    print("🔑 Environment Variables:")
    env_ok = all([
        check_env_var("TELEGRAM_BOT_TOKEN"),
        check_env_var("MANAGER_CHAT_ID"),
        check_env_var("OPENAI_API_KEY"),
        check_env_var("BITRIX24_WEBHOOK_URL"),
        check_env_var("POSTGRES_PASSWORD"),
    ])
    print()
    
    print("📝 Optional Configuration:")
    check_env_var("GOOGLE_DRIVE_FOLDER_ID", required=False)
    check_env_var("GOOGLE_CREDENTIALS_FILE", required=False)
    print()
    
    # Check Docker
    print("🐳 Docker:")
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ Docker installed: {result.stdout.strip()}")
            docker_ok = True
        else:
            print("❌ Docker not found")
            docker_ok = False
    except FileNotFoundError:
        print("❌ Docker not found")
        docker_ok = False
    print()
    
    # Summary
    print("="*60)
    print("Summary:")
    print("="*60)
    
    if files_ok and env_ok and docker_ok:
        print("✅ All checks passed! You're ready to start the bot.")
        print()
        print("Next steps:")
        print("  1. Start bot: docker-compose up -d")
        print("  2. View logs: docker-compose logs -f bot")
        print("  3. Test bot: Send /start to your bot in Telegram")
        print()
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print()
        if not files_ok:
            print("Missing files. Make sure you're in the project directory.")
        if not env_ok:
            print("Missing environment variables. Edit .env file.")
        if not docker_ok:
            print("Docker not found. Please install Docker first.")
        print()
        print("See SETUP_GUIDE.md for detailed instructions.")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


