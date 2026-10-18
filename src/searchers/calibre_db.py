import os
import subprocess
from typing import Optional
from src.models import BookIntent
from src.searchers.base import BaseSearcher
from src.config import Config

class CalibreSearcher(BaseSearcher):
    """
    Priority 0: 群晖 NAS Calibre 藏书库查重 (2.39 万本)
    鲁棒性强化：
    1. SQL 通过 stdin 管道输入，杜绝 Shell 元字符与注入异常
    2. 支持主标题 (base_title) 与全标题双层模糊匹配
    3. 查询出路径后自动远程检验实体文件存在性，杜绝空指针/假死链
    """

    @property
    def name(self) -> str:
        return "Calibre Library (NAS)"

    def _query_db(self, title_query: str) -> Optional[tuple]:
        safe_title = title_query.replace("'", "''")
        sql = (
            f"SELECT b.id, b.title, b.path, d.name, d.format "
            f"FROM books b "
            f"LEFT JOIN data d ON b.id = d.book AND UPPER(d.format) = 'EPUB' "
            f"WHERE b.title LIKE '%{safe_title}%' "
            f"ORDER BY (d.format IS NOT NULL) DESC, b.id DESC LIMIT 1;\n"
        )
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

    def search_and_download(self, intent: BookIntent) -> Optional[str]:
        # 1. 精确匹配 clean_title
        match = self._query_db(intent.clean_title)
        
        # 2. 若未命中，降级尝试主书名 base_title
        if not match and intent.base_title and intent.base_title != intent.clean_title:
            match = self._query_db(intent.base_title)

        if not match:
            return None

        matched_title, rel_path, file_name = match
        nas_epub_path = f"{Config.NAS_CALIBRE_ROOT}/{rel_path}/{file_name}.epub"

        # 3. 校验实体文件在 NAS 磁盘上是否真实存在且可读
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
