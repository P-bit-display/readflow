import os
import re
import time
import hashlib
from typing import Optional, Dict
from bs4 import BeautifulSoup
from curl_cffi import requests
from src.models import BookIntent
from src.searchers.base import BaseSearcher
from src.config import Config

class ZLibrarySearcher(BaseSearcher):
    """
    Priority 1: Z-Library 检索下载引擎
    鲁棒性强化：
    1. 自动破解 Z-Library 前端 JavaScript PoW (Proof-of-Work) 人机盾 (0.05秒算力解题)
    2. 携带用户 remix 凭证保持持久登录态
    3. 支持 ISBN 精确匹配 + 书名/主书名/作者联合多重降级检索
    4. 采用分块流式写入 (.part 机制) + PK\x03\x04 幻数校验，彻底杜绝半包断流与假伪 EPUB
    """

    @property
    def name(self) -> str:
        return "Z-Library"

    def __init__(self):
        self.session = requests.Session()
        self.cookies: Dict[str, str] = {}
        if Config.ZLIB_USER_ID and Config.ZLIB_USER_KEY:
            self.cookies["remix_userid"] = Config.ZLIB_USER_ID
            self.cookies["remix_userkey"] = Config.ZLIB_USER_KEY

    def _get_proxies(self):
        proxy = Config.HTTP_PROXY
        return {"http": proxy, "https": proxy}

    def _solve_pow_challenge(self, html: str) -> bool:
        """从 503 页面中提取 c 字符串并计算 SHA-1 PoW 破解防爬盾"""
        try:
            m = re.search(r"['\"]([0-9A-Fa-f]{40})['\"]", html)
            if not m:
                m = re.search(r"c\s*=\s*['\"]([0-9A-Fa-f]{30,64})['\"]", html)
            if not m:
                return False

            c = m.group(1)
            n1 = int(c[0], 16)
            start_t = time.time()
            for i in range(10000000):
                h = hashlib.sha1((c + str(i)).encode("utf-8")).digest()
                if h[n1] == 0xb0 and h[n1 + 1] == 0x0b:
                    elapsed = time.time() - start_t
                    self.cookies["c_token"] = c + str(i)
                    self.cookies["c_time"] = f"{elapsed:.3f}"
                    return True
        except Exception as e:
            print(f"[!] 破解 Z-Library PoW 挑战异常: {e}")
        return False

    def _fetch_page(self, url: str) -> Optional[requests.Response]:
        """发起请求，若遇到 503 Challenge 自动计算并重试"""
        for _ in range(2):
            try:
                resp = self.session.get(
                    url,
                    cookies=self.cookies,
                    proxies=self._get_proxies(),
                    impersonate="chrome120",
                    timeout=25
                )
                if resp.status_code == 503 and "Checking your browser" in resp.text:
                    if self._solve_pow_challenge(resp.text):
                        continue
                return resp
            except Exception as e:
                print(f"[!] 请求 Z-Lib 出错 ({url}): {e}")
        return None

    def search_and_download(self, intent: BookIntent) -> Optional[str]:
        if not self.cookies.get("remix_userid"):
            return None

        domain = f"https://{Config.ZLIB_DOMAIN}"
        
        # 多级检索序列：1. ISBN -> 2. 主书名+作者 -> 3. 主书名 -> 4. 原始标题
        queries = []
        if intent.isbn:
            queries.append(intent.isbn)
        if intent.base_title:
            queries.append(f"{intent.base_title} {intent.author or ''}".strip())
            queries.append(intent.base_title)
        if intent.clean_title not in queries:
            queries.append(intent.clean_title)

        cards = []
        for q in queries:
            search_url = f"{domain}/s/{requests.utils.quote(q)}?extensions%5B0%5D=epub"
            print(f"[*] [Z-Lib] 正在发起检索: {q} ...")
            resp = self._fetch_page(search_url)
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("z-bookcard")
                if cards:
                    break

        if not cards:
            print(f"[-] [Z-Lib] 未找到《{intent.clean_title}》的匹配条目")
            return None

        # 优先匹配指定为 epub 的卡片
        selected_href = None
        for card in cards:
            ext = card.get("extension", "").lower()
            if ext == "epub":
                selected_href = card.get("href")
                break

        if not selected_href:
            selected_href = cards[0].get("href")

        detail_url = f"{domain}{selected_href}"
        print(f"[+] [Z-Lib] 命中书目详情页，正在解析下载链接: {detail_url} ...")
        detail_resp = self._fetch_page(detail_url)
        if not detail_resp or detail_resp.status_code != 200:
            return None

        detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
        dl_btn = detail_soup.select_one("a.addDownloadedBook") or detail_soup.select_one('a[href*="/dl/"]')
        if not dl_btn:
            print(f"[-] [Z-Lib] 未在详情页找到下载按钮")
            return None

        dl_path = dl_btn.get("href")
        dl_url = f"{domain}{dl_path}" if dl_path.startswith("/") else dl_path

        local_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
        part_file = Config.CACHE_DIR / f"{intent.clean_title}.epub.part"

        print(f"[+] [Z-Lib] 正在全自动流式下载 EPUB: 《{intent.clean_title}》 ...")
        try:
            with self.session.get(
                dl_url,
                cookies=self.cookies,
                proxies=self._get_proxies(),
                impersonate="chrome120",
                timeout=(15, 300),
                stream=True,
                allow_redirects=True
            ) as dl_resp:
                if dl_resp.status_code != 200:
                    print(f"[!] [Z-Lib] 下载请求返回状态码: {dl_resp.status_code}")
                    return None

                first_chunk = True
                with open(part_file, "wb") as f:
                    for chunk in dl_resp.iter_content(chunk_size=32768):
                        if first_chunk:
                            first_chunk = False
                            # 校验 EPUB 文件的 Zip 规范幻数 (PK\x03\x04)
                            if not chunk.startswith(b"PK\x03\x04"):
                                print(f"[!] [Z-Lib] 拦截：下载内容非有效 EPUB 格式（可能是 HTML 防护或限制页）")
                                if part_file.exists():
                                    part_file.unlink()
                                return None
                        f.write(chunk)

                if part_file.exists() and part_file.stat().st_size > 1024:
                    if local_file.exists():
                        local_file.unlink()
                    part_file.rename(local_file)
                    file_mb = local_file.stat().st_size / 1024 / 1024
                    print(f"[+] [Z-Lib] 下载成功并校验落盘: {local_file} (体积: {file_mb:.2f} MB)")
                    return str(local_file)
        except Exception as e:
            print(f"[!] [Z-Lib] 下载流异常: {e}")
            if part_file.exists():
                part_file.unlink()

        return None
