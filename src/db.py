import json
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from src.config import Config

DB_FILE = Config.DATA_DIR / "readflow.db"

class Database:
    """ReadFlow 单文件 SQLite 存储引擎 (替代分散的 JSON 状态文件)"""

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_FILE, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        """初始化数据库表与索引，并无缝自动迁移原有的 JSON 历史数据"""
        with cls.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT UNIQUE NOT NULL,
                    clean_title TEXT,
                    base_title TEXT,
                    author TEXT,
                    isbn TEXT,
                    source TEXT,
                    status TEXT,
                    matched_by TEXT,
                    size_mb REAL DEFAULT 0.0,
                    recipient TEXT,
                    timestamp INTEGER
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_books_clean ON books(clean_title);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_books_base ON books(base_title);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_books_status ON books(status);")

        cls._auto_migrate_from_json()

    @classmethod
    def _auto_migrate_from_json(cls):
        """无感迁移旧版 history.json 与 book_history.json"""
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM books;")
            if cur.fetchone()[0] > 0:
                return  # 已经有数据，不重复迁移

            legacy_ledger = Config.DATA_DIR / "book_history.json"
            legacy_history = Config.DATA_DIR / "history.json"

            migrated_titles = set()

            if legacy_ledger.exists():
                try:
                    with open(legacy_ledger, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for item in data:
                            title = item.get("title", "").strip()
                            if not title or title in migrated_titles:
                                continue
                            migrated_titles.add(title)
                            cur.execute("""
                                INSERT OR IGNORE INTO books 
                                (title, clean_title, base_title, author, source, status, matched_by, size_mb, recipient, timestamp)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                            """, (
                                title,
                                title,
                                title,
                                item.get("author", "未知"),
                                item.get("source", "douban"),
                                item.get("status", "delivered"),
                                item.get("matched_by", "未知源"),
                                float(item.get("size_mb", 0.0)),
                                item.get("recipient", Config.TARGET_EMAIL),
                                int(item.get("timestamp", time.time()))
                            ))
                except Exception as e:
                    print(f"[*] 迁移 book_history.json 跳过: {e}")

            if legacy_history.exists():
                try:
                    with open(legacy_history, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for title in data:
                            if title and title not in migrated_titles:
                                migrated_titles.add(title)
                                cur.execute("""
                                    INSERT OR IGNORE INTO books 
                                    (title, clean_title, base_title, status, timestamp)
                                    VALUES (?, ?, ?, 'delivered', ?);
                                """, (title, title, title, int(time.time())))
                except Exception as e:
                    print(f"[*] 迁移 history.json 跳过: {e}")

            if migrated_titles:
                conn.commit()
                print(f"[+] 自动完成数据升级: 已将现存 {len(migrated_titles)} 本历史图书无缝导入 SQLite 数据库！")

    @classmethod
    def is_seen(cls, clean_title: str, base_title: Optional[str] = None) -> bool:
        """双向判断书籍是否已经在库中记录过"""
        with cls.get_connection() as conn:
            cur = conn.cursor()
            if base_title and base_title != clean_title:
                cur.execute("""
                    SELECT 1 FROM books 
                    WHERE clean_title = ? OR base_title = ? OR title = ? OR title = ?
                    LIMIT 1;
                """, (clean_title, base_title, clean_title, base_title))
            else:
                cur.execute("SELECT 1 FROM books WHERE clean_title = ? OR title = ? LIMIT 1;", (clean_title, clean_title))
            return cur.fetchone() is not None

    @classmethod
    def record_book(
        cls,
        title: str,
        clean_title: str,
        base_title: str,
        author: Optional[str],
        isbn: Optional[str],
        source: str,
        status: str,
        matched_by: str,
        size_mb: float,
        recipient: str
    ):
        """记录或更新图书交付明细"""
        now = int(time.time())
        with cls.get_connection() as conn:
            conn.execute("""
                INSERT INTO books 
                (title, clean_title, base_title, author, isbn, source, status, matched_by, size_mb, recipient, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(title) DO UPDATE SET
                    clean_title = excluded.clean_title,
                    base_title = excluded.base_title,
                    author = coalesce(excluded.author, books.author),
                    isbn = coalesce(excluded.isbn, books.isbn),
                    status = excluded.status,
                    matched_by = excluded.matched_by,
                    size_mb = excluded.size_mb,
                    recipient = excluded.recipient,
                    timestamp = excluded.timestamp;
            """, (title, clean_title, base_title, author, isbn, source, status, matched_by, size_mb, recipient, now))

    @classmethod
    def get_ledger(cls, query: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        """全字段即时检索图书账本"""
        with cls.get_connection() as conn:
            cur = conn.cursor()
            if query:
                like = f"%{query.strip().lower()}%"
                cur.execute("""
                    SELECT title, author, source, matched_by, size_mb, status, recipient, timestamp
                    FROM books
                    WHERE lower(title) LIKE ? OR lower(coalesce(author, '')) LIKE ? OR lower(coalesce(matched_by, '')) LIKE ?
                    ORDER BY timestamp DESC LIMIT ?;
                """, (like, like, like, limit))
            else:
                cur.execute("""
                    SELECT title, author, source, matched_by, size_mb, status, recipient, timestamp
                    FROM books
                    ORDER BY timestamp DESC LIMIT ?;
                """, (limit,))
            
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    @classmethod
    def get_metrics(cls) -> Dict[str, int]:
        """毫秒级聚合统计指标"""
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM books WHERE status = 'delivered';")
            total_delivered = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM books WHERE source = 'douban';")
            douban_cnt = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM books WHERE source = 'goodreads';")
            goodreads_cnt = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM books WHERE lower(coalesce(matched_by, '')) LIKE '%z-library%';")
            zlib_hits = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM books WHERE lower(coalesce(matched_by, '')) LIKE '%calibre%';")
            calibre_hits = cur.fetchone()[0]

            return {
                "total_delivered": total_delivered,
                "douban_count": douban_cnt,
                "goodreads_count": goodreads_cnt,
                "zlib_hits": zlib_hits,
                "calibre_hits": calibre_hits
            }

    @classmethod
    def get_recent_activity(cls, limit: int = 5) -> List[Dict[str, Any]]:
        return cls.get_ledger(limit=limit)
