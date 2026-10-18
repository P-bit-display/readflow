import json
import time
import os
from pathlib import Path
from typing import List, Set
from src.config import Config
from src.models import BookIntent
from src.watchers.douban import DoubanWatcher
from src.watchers.goodreads import GoodreadsWatcher
from src.searchers.calibre_db import CalibreSearcher
from src.searchers.zlib import ZLibrarySearcher
from src.searchers.annas import AnnasArchiveSearcher
from src.searchers.libgen import LibgenSearcher
from src.delivery.calibre_ingest import CalibreIngester
from src.delivery.mailer import BookMailer

HISTORY_FILE = Config.DATA_DIR / "history.json"

class ReadFlowPipeline:
    def __init__(self):
        # 1. 意图捕获源 (纯粹无感：仅保留豆瓣与 Goodreads)
        self.watchers = []
        if Config.DOUBAN_USER_ID:
            self.watchers.append(DoubanWatcher(Config.DOUBAN_USER_ID))
        if Config.GOODREADS_USER_ID:
            self.watchers.append(GoodreadsWatcher(Config.GOODREADS_USER_ID))

        # 2. 瀑布流多检索源
        self.searchers = [
            CalibreSearcher(),      # 优先查重群晖 NAS 自建库
            ZLibrarySearcher(),     # 主力源 1: Z-Lib (带 0.05s SHA-1 PoW 算力破解与分块校验)
            AnnasArchiveSearcher(), # 主力源 2: Anna's Archive 元搜索
            LibgenSearcher()        # 兜底源 3: Library Genesis 外文/学术源
        ]

    def _load_history(self) -> Set[str]:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data) if isinstance(data, list) else set()
            except Exception as e:
                print(f"[!] 读取历史记录异常，自动降级安全容错: {e}")
                return set()
        return set()

    def _save_history(self, history: Set[str]):
        """原子写入历史记录，防止断电或强制杀进程导致 JSON 损坏"""
        tmp_file = Config.DATA_DIR / "history.json.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(sorted(list(history)), f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, HISTORY_FILE)
        except Exception as e:
            print(f"[!] 保存历史记录异常: {e}")

    def _clean_old_cache(self, days: int = 7):
        """定期清理本地下载缓存，避免长期运行占满磁盘"""
        now = time.time()
        cutoff = now - (days * 86400)
        try:
            for item in Config.CACHE_DIR.glob("*"):
                if item.is_file() and item.stat().st_mtime < cutoff:
                    item.unlink()
        except Exception:
            pass

    def process_intent(self, intent: BookIntent) -> bool:
        print(f"\n========================================================")
        print(f"[*] 发现新想读书籍: {intent}")

        downloaded_epub = None
        # 瀑布流检索链
        for searcher in self.searchers:
            try:
                result = searcher.search_and_download(intent)
                if result and Path(result).exists():
                    downloaded_epub = result
                    print(f"[+] 成功通过 [{searcher.name}] 命中资源: {downloaded_epub}")
                    break
            except Exception as e:
                print(f"[!] 检索源 [{searcher.name}] 执行异常跳过: {e}")

        if not downloaded_epub:
            print(f"[-] 所有检索源均未找到《{intent.clean_title}》的可用 EPUB。")
            return False

        # 交付阶段 1: 资产归档入库 Calibre
        CalibreIngester.ingest(downloaded_epub, intent.clean_title)

        # 交付阶段 2: 邮件静默分发 (收到邮件即知成功，无干扰弹窗)
        BookMailer.send(downloaded_epub, intent.clean_title)

        return True

    def run_once(self):
        history = self._load_history()
        all_intents: List[BookIntent] = []

        # 抓取所有意图源
        for watcher in self.watchers:
            try:
                wishes = watcher.fetch_wishes()
                all_intents.extend(wishes)
            except Exception as e:
                print(f"[!] 意图源抓取跳过: {e}")

        if not all_intents:
            return

        # 首次启动初始化记录，避免全量重下刷屏
        if not HISTORY_FILE.exists():
            initial_titles = set()
            for intent in all_intents:
                initial_titles.add(intent.clean_title)
                if intent.base_title:
                    initial_titles.add(intent.base_title)
            print(f"[*] 首次运行初始化: 已记录现存 {len(initial_titles)} 本书籍为已知状态。")
            self._save_history(initial_titles)
            return

        # 智能识别新增书籍 (支持 base_title 与 clean_title 双向去重)
        for intent in all_intents:
            is_new = (intent.clean_title not in history) and (intent.base_title not in history)
            if is_new:
                success = self.process_intent(intent)
                if success:
                    history.add(intent.clean_title)
                    if intent.base_title:
                        history.add(intent.base_title)
                    self._save_history(history)
                time.sleep(3)

        # 维护缓存目录
        self._clean_old_cache(days=7)
