import os
import re
from typing import Optional
import requests
from bs4 import BeautifulSoup
from src.models import BookIntent
from src.searchers.base import BaseSearcher
from src.config import Config

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class AnnasArchiveSearcher(BaseSearcher):
    """
    Priority 2: Anna's Archive (安娜档案)
    去中心化影子图书馆元搜索，整合了 Z-Lib、Libgen、OpenLibrary、读秀等。
    完全免登录，抗封锁能力强。
    """

    @property
    def name(self) -> str:
        return "Anna's Archive"

    def _get_proxies(self):
        proxy = Config.HTTP_PROXY
        return {"http": proxy, "https": proxy} if proxy else None

    def search_and_download(self, intent: BookIntent) -> Optional[str]:
        if not Config.ENABLE_ANNAS_ARCHIVE:
            return None

        query = intent.isbn if intent.isbn else intent.clean_title
        search_url = f"https://annas-archive.org/search?q={requests.utils.quote(query)}&ext=epub"

        print(f"[*] [Anna's Archive] 正在检索: {query} ...")
        try:
            resp = requests.get(search_url, headers=HEADERS, proxies=self._get_proxies(), timeout=15)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.select("a[href^='/md5/']")
            if not links:
                print(f"[-] [Anna's Archive] 未匹配到结果")
                return None

            first_detail_url = "https://annas-archive.org" + links[0]["href"]
            detail_resp = requests.get(first_detail_url, headers=HEADERS, proxies=self._get_proxies(), timeout=15)
            if detail_resp.status_code != 200:
                return None

            detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
            download_links = detail_soup.select("a[href*='/slow_download/'], a[href*='download']")
            if download_links:
                fast_download = download_links[0]["href"]
                if not fast_download.startswith("http"):
                    fast_download = "https://annas-archive.org" + fast_download

                target_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
                print(f"[+] [Anna's Archive] 获取到下载链接，正在下载: {intent.clean_title} ...")
                with requests.get(fast_download, headers=HEADERS, proxies=self._get_proxies(), stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(target_file, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

                if target_file.exists() and target_file.stat().st_size > 1024:
                    print(f"[+] [Anna's Archive] 下载成功: {target_file}")
                    return str(target_file)
        except Exception as e:
            print(f"[*] [Anna's Archive] 检索/解析跳过: {e}")

        return None
