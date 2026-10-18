import json
import time
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
        # 1. 意图捕获源 (仅保留豆瓣与 Goodreads)
        self.watchers = []
        if Config.DOUBAN_USER_ID:
            self.watchers.append(DoubanWatcher(Config.DOUBAN_USER_ID))
        if Config.GOODREADS_USER_ID:
            self.watchers.append(GoodreadsWatcher(Config.GOODREADS_USER_ID))

        # 2. 瀑布流多检索源
        self.searchers = [
            CalibreSearcher(),      # 优先查重自建库
            ZLibrarySearcher(),     # 主源 1: Z-Lib
            AnnasArchiveSearcher(), # 主源 2: Anna's Archive 元搜索
            LibgenSearcher()        # 主源 3: Libgen 原版/学术兜底
        ]

    def _load_history(self) -> Set[str]:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception:
                return set()
        return set()

    def _save_history(self, history: Set[str]):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(history), f, ensure_ascii=False, indent=2)

    def process_intent(self, intent: BookIntent) -> bool:
        print(f"\n========================================================")
        print(f"[*] 发现新想读书籍: {intent}")

        downloaded_epub = None
        # 瀑布流搜索
        for searcher in self.searchers:
            try:
                result = searcher.search_and_download(intent)
                if result and Path(result).exists():
                    downloaded_epub = result
                    print(f"[+] 成功通过 [{searcher.name}] 命中资源: {downloaded_epub}")
                    break
            except Exception as e:
                print(f"[!] 检索源 [{searcher.name}] 执行跳过: {e}")

        if not downloaded_epub:
            print(f"[-] 所有检索源均未找到《{intent.clean_title}》的可用 EPUB。")
            return False

        # 交付阶段 1: 归档入库 Calibre
        CalibreIngester.ingest(downloaded_epub, intent.clean_title)

        # 交付阶段 2: 邮件静默分发 (收到邮件即知成功，无干扰无弹窗)
        BookMailer.send(downloaded_epub, intent.clean_title)

        return True

    def run_once(self):
        history = self._load_history()
        all_intents: List[BookIntent] = []

        # 抓取所有意图源
        for watcher in self.watchers:
            wishes = watcher.fetch_wishes()
            all_intents.extend(wishes)

        if not all_intents:
            return

        # 首次启动：记录已有书目避免全量刷屏
        if not HISTORY_FILE.exists():
            initial_titles = {intent.clean_title for intent in all_intents}
            print(f"[*] 首次运行初始化: 已记录现存 {len(initial_titles)} 本书籍为已知状态。")
            self._save_history(initial_titles)
            return

        # 识别新增书籍
        for intent in all_intents:
            key = intent.clean_title
            if key not in history:
                success = self.process_intent(intent)
                if success:
                    history.add(key)
                    self._save_history(history)
                time.sleep(3)
