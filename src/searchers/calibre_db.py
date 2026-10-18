import os
import sqlite3
import subprocess
from typing import Optional
from src.models import BookIntent
from src.searchers.base import BaseSearcher
from src.config import Config

class CalibreSearcher(BaseSearcher):
    """
    Priority 0: Calibre 藏书库查重 (支持本地与群晖 NAS 远程查重)
    """

    @property
    def name(self) -> str:
        return "Calibre Library"

    def _query_db(self, title_query: str) -> Optional[tuple]:
        if not Config.NAS_CALIBRE_DB:
            return None

        safe_title = title_query.replace("'", "''")
        sql = (
            f"SELECT b.id, b.title, b.path, d.name, d.format "
            f"FROM books b "
            f"LEFT JOIN data d ON b.id = d.book AND UPPER(d.format) = 'EPUB' "
            f"WHERE b.title LIKE '%{safe_title}%' "
            f"ORDER BY (d.format IS NOT NULL) DESC, b.id DESC LIMIT 1;"
        )

        # 模式 1: 远程 SSH NAS 查重
        if Config.NAS_SSH_HOST:
            cmd = ["ssh", "-o", "ConnectTimeout=5", Config.NAS_SSH_HOST, f"sqlite3 -separator '|||' \"{Config.NAS_CALIBRE_DB}\""]
            try:
                res = subprocess.run(cmd, input=sql, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
                line = res.stdout.strip()
                if line:
                    parts = line.split("|||")
                    if len(parts) >= 5 and parts[4].upper() == "EPUB":
                        return parts[1], parts[2], parts[3]
            except Exception as e:
                print(f"[!] 查询 Calibre NAS 出错: {e}")
            return None

        # 模式 2: 本地 / Docker 挂载 SQLite 查重
        if os.path.exists(Config.NAS_CALIBRE_DB):
            try:
                with sqlite3.connect(Config.NAS_CALIBRE_DB, timeout=5) as conn:
                    cur = conn.cursor()
                    cur.execute(sql)
                    row = cur.fetchone()
                    if row and len(row) >= 5 and row[4] and row[4].upper() == "EPUB":
                        return row[1], row[2], row[3]
            except Exception as e:
                print(f"[!] 查询本地 Calibre 出错: {e}")

        return None

    def search_and_download(self, intent: BookIntent) -> Optional[str]:
        if not Config.NAS_CALIBRE_DB:
            return None

        # 1. 精确匹配 clean_title
        match = self._query_db(intent.clean_title)
        
        # 2. 若未命中，降级尝试主书名 base_title
        if not match and intent.base_title and intent.base_title != intent.clean_title:
            match = self._query_db(intent.base_title)

        if not match:
            return None

        matched_title, rel_path, file_name = match
        epub_rel = f"{rel_path}/{file_name}.epub"

        # 远程 NAS 磁盘存在性校验
        if Config.NAS_SSH_HOST:
            nas_epub_path = f"{Config.NAS_CALIBRE_ROOT}/{epub_rel}"
            verify_cmd = ["ssh", "-o", "ConnectTimeout=5", Config.NAS_SSH_HOST, f"test -s \"{nas_epub_path}\""]
            try:
                check = subprocess.run(verify_cmd, timeout=8)
                if check.returncode == 0:
                    print(f"[+] [Calibre 查重命中] 《{matched_title}》在书库中已存在: {nas_epub_path}")
                    return nas_epub_path
                else:
                    print(f"[!] [Calibre 记录失真] 数据库收录《{matched_title}》，但物理磁盘文件不存在，跳过走在线源下载。")
            except Exception:
                pass
            return None

        # 本地磁盘存在性校验
        if Config.NAS_CALIBRE_ROOT:
            local_epub_path = os.path.join(Config.NAS_CALIBRE_ROOT, epub_rel)
            if os.path.exists(local_epub_path) and os.path.getsize(local_epub_path) > 0:
                print(f"[+] [Calibre 查重命中] 《{matched_title}》在本地书库中已存在: {local_epub_path}")
                return local_epub_path

        return None
