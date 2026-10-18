import re
import urllib.request
from typing import List
from bs4 import BeautifulSoup
from src.models import BookIntent
from src.watchers.base import BaseWatcher

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class DoubanWatcher(BaseWatcher):
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.wish_url = f"https://book.douban.com/people/{user_id}/wish"

    def fetch_wishes(self) -> List[BookIntent]:
        if not self.user_id:
            return []

        intents = []
        seen = set()

        try:
            req = urllib.request.Request(self.wish_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8")
                soup = BeautifulSoup(html, "html.parser")
                
                # 解析豆瓣想读条目列表
                items = soup.select(".interest-list .subject-item")
                for item in items:
                    title_tag = item.select_one(".info h2 a")
                    if not title_tag:
                        continue
                    title = title_tag.get("title", "").strip() or title_tag.get_text(strip=True)
                    link = title_tag.get("href", "")

                    # 提取作者
                    pub_tag = item.select_one(".info .pub")
                    author = None
                    if pub_tag:
                        pub_text = pub_tag.get_text(strip=True)
                        parts = pub_text.split("/")
                        if parts:
                            author = parts[0].strip()

                    if title and title not in seen:
                        seen.add(title)
                        intents.append(BookIntent(
                            title=title,
                            author=author,
                            source="douban",
                            source_url=link
                        ))
        except Exception as e:
            print(f"[!] 豆瓣想读书单抓取异常: {e}")

        return intents
