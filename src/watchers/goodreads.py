import urllib.request
from typing import List
import feedparser
from src.models import BookIntent
from src.watchers.base import BaseWatcher

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class GoodreadsWatcher(BaseWatcher):
    def __init__(self, user_id: str):
        self.user_id = user_id
        # Goodreads 标准公开 Want to Read RSS 地址
        self.rss_url = f"https://www.goodreads.com/review/list_rss/{user_id}?shelf=to-read"

    def fetch_wishes(self) -> List[BookIntent]:
        if not self.user_id:
            return []

        intents = []
        try:
            req = urllib.request.Request(self.rss_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                feed = feedparser.parse(resp.read())
                for entry in feed.entries:
                    title = entry.get("title", "").strip()
                    author = entry.get("author_name", None)
                    link = entry.get("link", None)
                    isbn = entry.get("isbn", None)

                    if title:
                        intents.append(BookIntent(
                            title=title,
                            author=author,
                            isbn=isbn,
                            source="goodreads",
                            source_url=link
                        ))
        except Exception as e:
            print(f"[!] Goodreads 想读书单抓取异常: {e}")

        return intents
