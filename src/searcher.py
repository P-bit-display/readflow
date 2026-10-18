import os
from pathlib import Path
from src.config import Config

def pick_best_candidate(results, book_name):
    """加权筛选算法：优先选择中文、epub 格式、大小合适、年份较新的版本"""
    candidates = []
    for item in results:
        ext = item.get("extension", "").lower()
        if ext != "epub":
            continue

        score = 0
        lang = item.get("language", "").lower()
        if "chinese" in lang or "zh" in lang:
            score += 50

        # 精确匹配标题
        title = item.get("title", "")
        if book_name in title:
            score += 30

        try:
            year = int(item.get("year", 0))
            score += min(max(year - 2000, 0), 25)
        except Exception:
            pass

        candidates.append((score, item))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1] if candidates else None


def download_from_zlibrary(book_name: str) -> str:
    """通过 Z-Library 检索并下载目标书籍"""
    if not Config.ZLIB_EMAIL or not Config.ZLIB_PASSWORD:
        print("[!] 尚未配置 ZLIB_EMAIL 和 ZLIB_PASSWORD，跳过自动下载")
        return None

    try:
        from zlibrary import Zlibrary
        z = Zlibrary(email=Config.ZLIB_EMAIL, password=Config.ZLIB_PASSWORD)
        print(f"[*] 正在从 Z-Library 检索《{book_name}》...")
        results = z.search(query=book_name, extension="epub")
        if not results:
            print(f"[-] Z-Library 未找到《{book_name}》的 EPUB 版本")
            return None

        best = pick_best_candidate(results, book_name) or results[0]
        title = best.get("title", book_name).replace("/", "_").replace("\\", "_")
        target_path = Config.CACHE_DIR / f"{title}.epub"

        print(f"[+] 找到最佳版本: 《{title}》，开始下载...")
        z.download_book(best, save_path=str(target_path))
        print(f"[+] 下载完成: {target_path}")
        return str(target_path)

    except Exception as e:
        print(f"[!] Z-Library 下载异常: {e}")
        return None
