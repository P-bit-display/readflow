import urllib.request
import urllib.parse
import re
from typing import Optional
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

    def search_and_download(self, intent: BookIntent) -> Optional[str]:
        if not Config.ENABLE_ANNAS_ARCHIVE:
            return None

        # 优先检索 ISBN，若无则使用书名
        query = intent.isbn if intent.isbn else intent.clean_title
        encoded_query = urllib.parse.quote(query)
        # 仅限定 epub 格式
        search_url = f"https://annas-archive.org/search?q={encoded_query}&ext=epub"

        print(f"[*] [Anna's Archive] 正在检索: {query} ...")
        try:
            req = urllib.request.Request(search_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8")
                soup = BeautifulSoup(html, "html.parser")

                # 解析结果列表里的第一个下载链接
                links = soup.select("a[href^='/md5/']")
                if not links:
                    print(f"[-] [Anna's Archive] 未匹配到结果")
                    return None

                first_detail_url = "https://annas-archive.org" + links[0]["href"]
                # 访问详情页获取实际高速镜像
                detail_req = urllib.request.Request(first_detail_url, headers=HEADERS)
                with urllib.request.urlopen(detail_req, timeout=20) as detail_resp:
                    detail_html = detail_resp.read().decode("utf-8")
                    detail_soup = BeautifulSoup(detail_html, "html.parser")
                    download_links = detail_soup.select("a[href*='/slow_download/'], a[href*='download']")
                    
                    if download_links:
                        fast_download = download_links[0]["href"]
                        if not fast_download.startswith("http"):
                            fast_download = "https://annas-archive.org" + fast_download
                        
                        target_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
                        print(f"[+] [Anna's Archive] 获取到下载链接，正在下载: {intent.clean_title} ...")
                        urllib.request.urlretrieve(fast_download, str(target_file))
                        if target_file.exists() and target_file.stat().st_size > 1024:
                            print(f"[+] [Anna's Archive] 下载成功: {target_file}")
                            return str(target_file)
        except Exception as e:
            print(f"[*] [Anna's Archive] 检索/解析跳过: {e}")

        return None
