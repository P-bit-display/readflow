import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Config:
    # 意图捕获源 (豆瓣 / Goodreads)
    DOUBAN_USER_ID = os.getenv("DOUBAN_USER_ID", "").strip()
    GOODREADS_USER_ID = os.getenv("GOODREADS_USER_ID", "").strip()
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "600"))

    # 邮件分发目标与凭据
    TARGET_EMAIL = os.getenv("TARGET_EMAIL", "").strip()
    SMTP_SERVER = os.getenv("SMTP_SERVER", "").strip()
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER = os.getenv("SMTP_USER", "").strip()
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()

    # 群晖 NAS / Calibre 配置 (可选)
    NAS_SSH_HOST = os.getenv("NAS_SSH_HOST", "").strip()
    NAS_CALIBRE_ROOT = os.getenv("NAS_CALIBRE_ROOT", "").strip()
    NAS_CALIBRE_DB = os.getenv("NAS_CALIBRE_DB", "").strip()
    NAS_INBOX_DIR = os.getenv("NAS_INBOX_DIR", "").strip()
    NAS_PUSH_DIR = os.getenv("NAS_PUSH_DIR", "").strip()

    # 多检索源与网络
    ZLIB_EMAIL = os.getenv("ZLIB_EMAIL", "").strip()
    ZLIB_PASSWORD = os.getenv("ZLIB_PASSWORD", "").strip()
    ZLIB_USER_ID = os.getenv("ZLIB_USER_ID", "").strip()
    ZLIB_USER_KEY = os.getenv("ZLIB_USER_KEY", "").strip()
    ZLIB_DOMAIN = os.getenv("ZLIB_DOMAIN", "z-library.sk").strip()
    HTTP_PROXY = os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or ""
    ENABLE_ANNAS_ARCHIVE = os.getenv("ENABLE_ANNAS_ARCHIVE", "true").lower() == "true"
    ENABLE_LIBGEN = os.getenv("ENABLE_LIBGEN", "true").lower() == "true"

    # 日志文件路径 (可选)
    LOG_FILE = os.getenv("LOG_FILE", "").strip()

    # 数据与缓存
    DATA_DIR = Path(__file__).parent.parent / "data"
    CACHE_DIR = Path(__file__).parent.parent / "cache"

Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
Config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
