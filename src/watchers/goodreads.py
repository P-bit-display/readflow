import os
import re
import warnings
from typing import List
import requests
import feedparser
from src.models import BookIntent
from src.watchers.base import BaseWatcher

# 压制 requests 的 dependency warning 避免终端混淆
warnings.filterwarnings("ignore", category=UserWarning, module="requests")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class GoodreadsWatcher(BaseWatcher):
    def __init__(self, user_id: str):
        self.user_id = str(user_id).strip()
        # 1. 实时动态流 (wants to read 立即触发，无 CDN 延迟)
        self.updates_rss_url = f"https://www.goodreads.com/user/updates_rss/{self.user_id}"
        # 2. 货架归档 RSS (带 5-15 分钟 CDN 缓存)
        self.shelf_rss_url = f"https://www.goodreads.com/review/list_rss/{self.user_id}?shelf=to-read"

    def _fetch_feed(self, url: str):
        try:
            proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or "http://127.0.0.1:7897"
            proxies = {"http": proxy, "https": proxy}
            resp = requests.get(url, headers=HEADERS, proxies=proxies, timeout=25)
            if resp.status_code == 200:
                return feedparser.parse(resp.text)
            else:
                print(f"[!] Goodreads RSS ({url}) 状态码异常: {resp.status_code}")
                return None
        except Exception as e:
            print(f"[!] Goodreads RSS ({url}) 请求失败: {e}")
            return None

    def fetch_wishes(self) -> List[BookIntent]:
        if not self.user_id:
            return []

        intents: List[BookIntent] = []
        seen_titles = set()

        # 优先解析实时动态流 (updates_rss)
        updates_feed = self._fetch_feed(self.updates_rss_url)
        if updates_feed and updates_feed.entries:
            for entry in updates_feed.entries:
                raw_title = entry.get("title", "")
                desc = entry.get("description", "")

                # 仅捕获 "wants to read"
                if "wants to read" in raw_title.lower():
                    m_book = re.search(r'class="bookTitle"[^>]*href="([^"]+)">([^<]+)<', desc)
                    m_author = re.search(r'class="authorName"[^>]*>([^<]+)<', desc)

                    if m_book:
                        book_title = m_book.group(2).strip()
                        book_link = f"https://www.goodreads.com{m_book.group(1)}"
                    else:
                        m_title = re.search(r"wants to read ['\"]?(.*?)['\"]?$", raw_title.strip())
                        book_title = m_title.group(1).strip() if m_title else raw_title.strip()
                        book_link = entry.get("link")

                    book_author = m_author.group(1).strip() if m_author else None

                    if book_title and book_title.lower() not in seen_titles:
                        seen_titles.add(book_title.lower())
                        intents.append(BookIntent(
                            title=book_title,
                            author=book_author,
                            source="goodreads",
                            source_url=book_link
                        ))

        # 辅助解析货架流 (shelf_rss)
        shelf_feed = self._fetch_feed(self.shelf_rss_url)
        if shelf_feed and shelf_feed.entries:
            for entry in shelf_feed.entries:
                title = entry.get("title", "").strip()
                author = entry.get("author_name", None)
                link = entry.get("link", None)
                isbn = entry.get("isbn", None)

                if title and title.lower() not in seen_titles:
                    seen_titles.add(title.lower())
                    intents.append(BookIntent(
                        title=title,
                        author=author,
                        isbn=isbn,
                        source="goodreads",
                        source_url=link
                    ))

        return intents
