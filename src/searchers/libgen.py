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

MIRRORS = [
    "https://libgen.is",
    "https://libgen.rs",
    "https://libgen.st",
]

class LibgenSearcher(BaseSearcher):
    """Priority 3: Library Genesis (Libgen) - 外文原版与学术书籍天花板"""

    @property
    def name(self) -> str:
        return "Library Genesis"

    def _get_proxies(self):
        proxy = Config.HTTP_PROXY
        return {"http": proxy, "https": proxy} if proxy else None

    def search_and_download(self, intent: BookIntent) -> Optional[str]:
        if not Config.ENABLE_LIBGEN:
            return None

        query = intent.isbn if intent.isbn else intent.clean_title
        encoded_query = requests.utils.quote(query)

        print(f"[*] [Libgen] 正在检索: {query} ...")
        for mirror in MIRRORS:
            search_url = f"{mirror}/search.php?req={encoded_query}&res=25&column=def"
            try:
                resp = requests.get(search_url, headers=HEADERS, proxies=self._get_proxies(), timeout=12)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                table = soup.find("table", {"class": "c"})
                if not table:
                    continue

                rows = table.find_all("tr")[1:]  # 跳过表头
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) > 8:
                        extension = cols[8].text.strip().lower()
                        if extension == "epub":
                            mirror_link = cols[9].find("a")
                            if mirror_link:
                                download_gateway = mirror_link["href"]
                                gw_resp = requests.get(download_gateway, headers=HEADERS, proxies=self._get_proxies(), timeout=12)
                                if gw_resp.status_code == 200:
                                    gw_soup = BeautifulSoup(gw_resp.text, "html.parser")
                                    get_link = gw_soup.find("a", string=re.compile(r"GET", re.I))
                                    if get_link:
                                        direct_url = get_link["href"]
                                        target_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
                                        print(f"[+] [Libgen] 命中 EPUB，正在下载...")
                                        with requests.get(direct_url, headers=HEADERS, proxies=self._get_proxies(), stream=True, timeout=30) as r:
                                            r.raise_for_status()
                                            with open(target_file, "wb") as f:
                                                for chunk in r.iter_content(chunk_size=8192):
                                                    f.write(chunk)

                                        if target_file.exists() and target_file.stat().st_size > 1024:
                                            print(f"[+] [Libgen] 下载成功: {target_file}")
                                            return str(target_file)
                # 如果这个 mirror 能正常访问但没找到结果，就不用继续重试镜像了
                break
            except Exception as e:
                # 尝试下一个 mirror
                continue

        return None
