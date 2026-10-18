import os
import shutil
import subprocess
from pathlib import Path
from src.config import Config

class CalibreIngester:
    """Calibre 资产归档处理器"""

    @staticmethod
    def ingest(epub_path: str, book_title: str) -> bool:
        """将 EPUB 文件归档到 Calibre 书库目录或 inbox 收件箱"""
        if not epub_path or not os.path.exists(epub_path):
            return False

        # 方式 1: 放入 Calibre-Web 自动导入收件箱
        if Config.CALIBRE_INBOX_DIR and os.path.exists(Config.CALIBRE_INBOX_DIR):
            target_inbox = Path(Config.CALIBRE_INBOX_DIR) / os.path.basename(epub_path)
            shutil.copy(epub_path, str(target_inbox))
            print(f"[+] [Calibre 资产归档] 已复制至收件箱: {target_inbox}")

        # 方式 2: 如果本地有 calibredb 命令行，直接执行实时添加
        if shutil.which("calibredb") and Config.CALIBRE_LIBRARY_PATH:
            try:
                cmd = ["calibredb", "add", epub_path, "--with-library", Config.CALIBRE_LIBRARY_PATH]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode == 0:
                    print(f"[+] [Calibre 资产归档] 已通过 calibredb 成功入库！")
                    return True
            except Exception as e:
                print(f"[*] calibredb 命令行执行跳过: {e}")

        return True
