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

class LibgenSearcher(BaseSearcher):
    """Priority 3: Library Genesis (Libgen) - 外文原版与学术书籍天花板"""

    @property
    def name(self) -> str:
        return "Library Genesis"

    def search_and_download(self, intent: BookIntent) -> Optional[str]:
        if not Config.ENABLE_LIBGEN:
            return None

        # 如果是纯中文且没有 ISBN，Libgen 命中率较低，直接跳过节约时间
        query = intent.isbn if intent.isbn else intent.clean_title
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://libgen.is/search.php?req={encoded_query}&res=25&column=def"

        print(f"[*] [Libgen] 正在检索: {query} ...")
        try:
            req = urllib.request.Request(search_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8")
                soup = BeautifulSoup(html, "html.parser")
                
                # 寻找扩展名为 epub 的行
                table = soup.find("table", {"class": "c"})
                if not table:
                    return None

                rows = table.find_all("tr")[1:]  # 跳过表头
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) > 8:
                        extension = cols[8].text.strip().lower()
                        if extension == "epub":
                            # 镜像下载列 (Mirrors)
                            mirror_link = cols[9].find("a")
                            if mirror_link:
                                download_gateway = mirror_link["href"]
                                # 访问网关获取真实直接下载地址
                                gw_req = urllib.request.Request(download_gateway, headers=HEADERS)
                                with urllib.request.urlopen(gw_req, timeout=15) as gw_resp:
                                    gw_soup = BeautifulSoup(gw_resp.read().decode("utf-8"), "html.parser")
                                    get_link = gw_soup.find("a", string=re.compile(r"GET", re.I))
                                    if get_link:
                                        direct_url = get_link["href"]
                                        target_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
                                        print(f"[+] [Libgen] 命中 EPUB，正在下载...")
                                        urllib.request.urlretrieve(direct_url, str(target_file))
                                        if target_file.exists() and target_file.stat().st_size > 1024:
                                            print(f"[+] [Libgen] 下载成功: {target_file}")
                                            return str(target_file)
        except Exception as e:
            print(f"[*] [Libgen] 检索跳过: {e}")

        return None
