import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Config:
    # 豆瓣
    DOUBAN_USER_ID = os.getenv("DOUBAN_USER_ID", "").strip()
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "600"))

    # SMTP
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    TARGET_EMAIL = os.getenv("TARGET_EMAIL", "")

    # Calibre
    CALIBRE_DB_PATH = os.getenv("CALIBRE_DB_PATH", "")
    CALIBRE_LIBRARY_PATH = os.getenv("CALIBRE_LIBRARY_PATH", "")
    INBOX_DIR = os.getenv("INBOX_DIR", "/tmp/inbox")

    # Z-Lib
    ZLIB_EMAIL = os.getenv("ZLIB_EMAIL", "")
    ZLIB_PASSWORD = os.getenv("ZLIB_PASSWORD", "")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # 本地数据目录
    DATA_DIR = Path(__file__).parent.parent / "data"
    CACHE_DIR = Path(__file__).parent.parent / "cache"

Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
Config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
