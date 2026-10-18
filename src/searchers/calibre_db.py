import os
import sqlite3
from typing import Optional
from src.models import BookIntent
from src.searchers.base import BaseSearcher
from src.config import Config

class CalibreSearcher(BaseSearcher):
    """Priority 0: 本地 Calibre 藏书库查重"""

    @property
    def name(self) -> str:
        return "Calibre Local Library"

    def search_and_download(self, intent: BookIntent) -> Optional[str]:
        db_path = Config.CALIBRE_DB_PATH
        if not db_path or not os.path.exists(db_path):
            return None

        clean_name = intent.clean_title.replace("'", "''")
        # 优先通过书名 + EPUB 格式匹配
        sql = (
            f"SELECT b.id, b.title, b.path, d.name, d.format "
            f"FROM books b "
            f"LEFT JOIN data d ON b.id = d.book AND UPPER(d.format) = 'EPUB' "
            f"WHERE b.title LIKE '%{clean_name}%' "
            f"ORDER BY (d.format IS NOT NULL) DESC, b.id DESC LIMIT 1;"
        )

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            conn.close()

            if row:
                book_id, title, rel_path, file_name, fmt = row
                if fmt and fmt.upper() == "EPUB" and file_name and Config.CALIBRE_LIBRARY_PATH:
                    epub_path = os.path.join(Config.CALIBRE_LIBRARY_PATH, rel_path, f"{file_name}.epub")
                    if os.path.exists(epub_path):
                        print(f"[+] Calibre 库中已收藏此书: 《{title}》 -> {epub_path}")
                        return epub_path
        except Exception as e:
            print(f"[!] 查询 Calibre 数据库出错: {e}")

        return None
