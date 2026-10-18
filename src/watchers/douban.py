import re
import urllib.request
from typing import List
import feedparser
from bs4 import BeautifulSoup
from src.models import BookIntent
from src.watchers.base import BaseWatcher

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class DoubanWatcher(BaseWatcher):
    """
    豆瓣想读捕获器：
    双轨监听架构：
    1. HTML 网页流 (带作者、出版信息与详尽元数据)
    2. 官方 RSS 动态流 (https://www.douban.com/feed/people/{uid}/interests，免受反爬干扰，高容灾保底)
    """

    def __init__(self, user_id: str):
        self.user_id = str(user_id).strip()
        self.html_url = f"https://book.douban.com/people/{self.user_id}/wish"
        self.rss_url = f"https://www.douban.com/feed/people/{self.user_id}/interests"

    def fetch_wishes(self) -> List[BookIntent]:
        if not self.user_id:
            return []

        intents: List[BookIntent] = []
        seen = set()

        # 1. 主通道：抓取网页想读书单
        try:
            req = urllib.request.Request(self.html_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8")
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select(".interest-list .subject-item")
                for item in items:
                    title_tag = item.select_one(".info h2 a")
                    if not title_tag:
                        continue
                    title = title_tag.get("title", "").strip() or title_tag.get_text(strip=True)
                    link = title_tag.get("href", "")

                    pub_tag = item.select_one(".info .pub")
                    author = None
                    if pub_tag:
                        pub_text = pub_tag.get_text(strip=True)
                        parts = pub_text.split("/")
                        if parts:
                            author = parts[0].strip()

                    if title and title.lower() not in seen:
                        seen.add(title.lower())
                        intents.append(BookIntent(
                            title=title,
                            author=author,
                            source="douban",
                            source_url=link
                        ))
        except Exception as e:
            print(f"[*] 豆瓣网页抓取受限或超时，自动切换至 RSS 容灾流: {e}")

        # 2. 保底容灾通道：抓取官方 RSS 动态
        try:
            req = urllib.request.Request(self.rss_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                feed = feedparser.parse(resp.read())
                for entry in feed.entries:
                    raw_title = entry.get("title", "").strip()
                    # 仅过滤“想读”图书动态，过滤“想看”电影/剧集
                    if raw_title.startswith("想读"):
                        book_title = raw_title[2:].strip()
                        if book_title and book_title.lower() not in seen:
                            seen.add(book_title.lower())
                            intents.append(BookIntent(
                                title=book_title,
                                source="douban",
                                source_url=entry.get("link")
                            ))
        except Exception as e:
            print(f"[!] 豆瓣 RSS 容灾流拉取异常: {e}")

        return intents
