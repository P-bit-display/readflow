import os
import sqlite3
from pathlib import Path
from src.config import Config

def search_calibre(book_name: str):
    """
    在 Calibre 的 metadata.db 数据库中毫秒级查重
    返回: 匹配的书籍信息字典或 None
    """
    db_path = Config.CALIBRE_DB_PATH
    if not db_path or not os.path.exists(db_path):
        return None

    clean_name = book_name.replace("'", "''").replace("《", "").replace("》", "").strip()
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
            epub_path = None
            if fmt and fmt.upper() == "EPUB" and file_name and Config.CALIBRE_LIBRARY_PATH:
                epub_path = os.path.join(Config.CALIBRE_LIBRARY_PATH, rel_path, f"{file_name}.epub")
                if not os.path.exists(epub_path):
                    epub_path = None

            return {
                "id": book_id,
                "title": title,
                "epub_path": epub_path
            }
    except Exception as e:
        print(f"[!] 查询 Calibre 数据库出错: {e}")

    return None
