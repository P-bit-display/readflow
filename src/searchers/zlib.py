import os
from typing import Optional
from src.models import BookIntent
from src.searchers.base import BaseSearcher
from src.config import Config

class ZLibrarySearcher(BaseSearcher):
    """Priority 1: Z-Library 检索下载引擎"""

    @property
    def name(self) -> str:
        return "Z-Library"

    def _pick_best(self, results, intent: BookIntent):
        candidates = []
        for item in results:
            if item.get("extension", "").lower() != "epub":
                continue

            score = 0
            lang = item.get("language", "").lower()
            if "chinese" in lang or "zh" in lang:
                score += 50

            title = item.get("title", "")
            if intent.clean_title in title:
                score += 30

            # 如果命中作者
            if intent.author and intent.author in item.get("author", ""):
                score += 20

            try:
                year = int(item.get("year", 0))
                score += min(max(year - 2000, 0), 20)
            except Exception:
                pass

            candidates.append((score, item))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1] if candidates else None

    def search_and_download(self, intent: BookIntent) -> Optional[str]:
        if not Config.ZLIB_EMAIL or not Config.ZLIB_PASSWORD:
            return None

        try:
            from zlibrary import Zlibrary
            z = Zlibrary(email=Config.ZLIB_EMAIL, password=Config.ZLIB_PASSWORD)

            # 1. 优先使用 ISBN 精确检索 (借鉴 Readarr 防版本漂移)
            results = []
            if intent.isbn:
                print(f"[*] [Z-Lib] 正在通过 ISBN 精确匹配: {intent.isbn} ...")
                results = z.search(query=intent.isbn, extension="epub")

            # 2. 回退到书名 + 作者联合检索
            if not results:
                query = f"{intent.clean_title} {intent.author}" if intent.author else intent.clean_title
                print(f"[*] [Z-Lib] 正在通过书名检索: {query} ...")
                results = z.search(query=query, extension="epub")

            if not results:
                # 3. 再次宽容回退到纯书名检索
                results = z.search(query=intent.clean_title, extension="epub")

            if not results:
                print(f"[-] [Z-Lib] 未找到《{intent.clean_title}》的可用 EPUB")
                return None

            selected = self._pick_best(results, intent) or results[0]
            clean_filename = selected.get("title", intent.clean_title).replace("/", "_").replace("\\", "_")
            local_save = Config.CACHE_DIR / f"{clean_filename}.epub"

            print(f"[+] [Z-Lib] 找到匹配版本: 《{clean_filename}》，正在下载...")
            z.download_book(selected, save_path=str(local_save))
            if local_save.exists() and local_save.stat().st_size > 0:
                print(f"[+] [Z-Lib] 下载成功: {local_save}")
                return str(local_save)

        except Exception as e:
            print(f"[!] [Z-Lib] 检索下载异常: {e}")

        return None
