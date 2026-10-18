import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Config:
    # 意图捕获源
    DOUBAN_USER_ID = os.getenv("DOUBAN_USER_ID", "151885595").strip()
    GOODREADS_USER_ID = os.getenv("GOODREADS_USER_ID", "").strip()
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "600"))

    # 邮件分发目标
    TARGET_EMAIL = os.getenv("TARGET_EMAIL", "placid.dang@163.com")

    # 群晖 NAS 配置
    NAS_SSH_HOST = os.getenv("NAS_SSH_HOST", "nas")
    NAS_CALIBRE_ROOT = os.getenv("NAS_CALIBRE_ROOT", "/volume1/homes/placid/Books/00-Calibre")
    NAS_CALIBRE_DB = os.getenv("NAS_CALIBRE_DB", "/volume1/homes/placid/Books/00-Calibre/metadata.db")
    NAS_INBOX_DIR = os.getenv("NAS_INBOX_DIR", "/volume1/homes/placid/Books/05-inbox")
    NAS_PUSH_DIR = os.getenv("NAS_PUSH_DIR", "/volume1/homes/placid/Books/05-inbox/最新推送")

    # 检索源
    ZLIB_EMAIL = os.getenv("ZLIB_EMAIL", "")
    ZLIB_PASSWORD = os.getenv("ZLIB_PASSWORD", "")
    ZLIB_USER_ID = os.getenv("ZLIB_USER_ID", "11136248").strip()
    ZLIB_USER_KEY = os.getenv("ZLIB_USER_KEY", "a7835d4e628fa93baffdec32c6d7e831").strip()
    ZLIB_DOMAIN = os.getenv("ZLIB_DOMAIN", "z-library.sk").strip()
    HTTP_PROXY = os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or "http://127.0.0.1:7897"
    ENABLE_ANNAS_ARCHIVE = os.getenv("ENABLE_ANNAS_ARCHIVE", "true").lower() == "true"
    ENABLE_LIBGEN = os.getenv("ENABLE_LIBGEN", "true").lower() == "true"

    # 数据与缓存
    DATA_DIR = Path(__file__).parent.parent / "data"
    CACHE_DIR = Path(__file__).parent.parent / "cache"

Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
Config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
