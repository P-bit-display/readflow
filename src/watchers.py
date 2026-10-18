import re
import urllib.request
import warnings
from typing import List, Set
import requests
import feedparser
from bs4 import BeautifulSoup
from src.config import Config
from src.models import BookIntent

warnings.filterwarnings("ignore", category=UserWarning, module="requests")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_douban_wishes(user_id: str) -> List[BookIntent]:
    """抓取豆瓣个人想读书单（网页流优先，官方 RSS 动态流容灾保底）"""
    if not user_id:
        return []
    
    intents: List[BookIntent] = []
    seen: Set[str] = set()

    # 1. 网页想读流
    html_url = f"https://book.douban.com/people/{user_id}/wish"
    try:
        req = urllib.request.Request(html_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            soup = BeautifulSoup(resp.read().decode("utf-8"), "html.parser")
            for item in soup.select(".interest-list .subject-item"):
                title_tag = item.select_one(".info h2 a")
                if not title_tag:
                    continue
                title = title_tag.get("title", "").strip() or title_tag.get_text(strip=True)
                pub_tag = item.select_one(".info .pub")
                author = pub_tag.get_text(strip=True).split("/")[0].strip() if pub_tag else None

                if title and title.lower() not in seen:
                    seen.add(title.lower())
                    intents.append(BookIntent(title=title, author=author, source="douban"))
    except Exception as e:
        print(f"[*] 豆瓣网页抓取受限或超时，自动切换至 RSS 容灾流: {e}")

    # 2. 官方 RSS 容灾流
    rss_url = f"https://www.douban.com/feed/people/{user_id}/interests"
    try:
        req = urllib.request.Request(rss_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            feed = feedparser.parse(resp.read())
            for entry in feed.entries:
                raw_title = entry.get("title", "").strip()
                if raw_title.startswith("想读"):
                    book_title = raw_title[2:].strip()
                    if book_title and book_title.lower() not in seen:
                        seen.add(book_title.lower())
                        intents.append(BookIntent(title=book_title, source="douban"))
    except Exception as e:
        print(f"[!] 豆瓣 RSS 容灾流拉取异常: {e}")

    return intents

def fetch_goodreads_wishes(user_id: str) -> List[BookIntent]:
    """抓取 Goodreads 个人 Want to Read 动态流"""
    if not user_id:
        return []

    intents: List[BookIntent] = []
    seen: Set[str] = set()
    proxy = Config.HTTP_PROXY
    proxies = {"http": proxy, "https": proxy} if proxy else None

    # 1. 实时动态流
    updates_url = f"https://www.goodreads.com/user/updates_rss/{user_id}"
    try:
        resp = requests.get(updates_url, headers=HEADERS, proxies=proxies, timeout=25)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.text)
            for entry in feed.entries:
                raw_title = entry.get("title", "")
                desc = entry.get("description", "")
                if "wants to read" in raw_title.lower():
                    m_book = re.search(r'class="bookTitle"[^>]*href="([^"]+)">([^<]+)<', desc)
                    m_author = re.search(r'class="authorName"[^>]*>([^<]+)<', desc)
                    book_title = m_book.group(2).strip() if m_book else None
                    if not book_title:
                        m_title = re.search(r"wants to read ['\"]?(.*?)['\"]?$", raw_title.strip())
                        book_title = m_title.group(1).strip() if m_title else None
                    book_author = m_author.group(1).strip() if m_author else None

                    if book_title and book_title.lower() not in seen:
                        seen.add(book_title.lower())
                        intents.append(BookIntent(title=book_title, author=book_author, source="goodreads"))
    except Exception as e:
        print(f"[!] Goodreads 实时流拉取异常: {e}")

    # 2. 货架流保底
    shelf_url = f"https://www.goodreads.com/review/list_rss/{user_id}?shelf=to-read"
    try:
        resp = requests.get(shelf_url, headers=HEADERS, proxies=proxies, timeout=25)
        if resp.status_code == 200:
            feed = feedparser.parse(resp.text)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                author = entry.get("author_name")
                isbn = entry.get("isbn")
                if title and title.lower() not in seen:
                    seen.add(title.lower())
                    intents.append(BookIntent(title=title, author=author, isbn=isbn, source="goodreads"))
    except Exception as e:
        print(f"[!] Goodreads 货架流拉取异常: {e}")

    return intents

def fetch_all_wishes() -> List[BookIntent]:
    """聚合获取所有配置源的待读书目"""
    all_wishes = []
    if Config.DOUBAN_USER_ID:
        all_wishes.extend(fetch_douban_wishes(Config.DOUBAN_USER_ID))
    if Config.GOODREADS_USER_ID:
        all_wishes.extend(fetch_goodreads_wishes(Config.GOODREADS_USER_ID))
    return all_wishes
