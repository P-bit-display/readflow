import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Config:
    # 意图捕获源
    DOUBAN_USER_ID = os.getenv("DOUBAN_USER_ID", "").strip()
    GOODREADS_USER_ID = os.getenv("GOODREADS_USER_ID", "").strip()
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "600"))

    # SMTP 邮件分发
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    TARGET_EMAIL = os.getenv("TARGET_EMAIL", "")

    # Calibre 资产管理
    CALIBRE_DB_PATH = os.getenv("CALIBRE_DB_PATH", "")
    CALIBRE_LIBRARY_PATH = os.getenv("CALIBRE_LIBRARY_PATH", "")
    CALIBRE_INBOX_DIR = os.getenv("CALIBRE_INBOX_DIR", "")

    # 检索源
    ZLIB_EMAIL = os.getenv("ZLIB_EMAIL", "")
    ZLIB_PASSWORD = os.getenv("ZLIB_PASSWORD", "")
    ENABLE_ANNAS_ARCHIVE = os.getenv("ENABLE_ANNAS_ARCHIVE", "true").lower() == "true"
    ENABLE_LIBGEN = os.getenv("ENABLE_LIBGEN", "true").lower() == "true"

    # 数据与缓存
    DATA_DIR = Path(__file__).parent.parent / "data"
    CACHE_DIR = Path(__file__).parent.parent / "cache"

Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
Config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
