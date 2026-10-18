import os
import re
import time
import hashlib
import sqlite3
import subprocess
from typing import Optional, Tuple, Dict
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from src.config import Config
from src.models import BookIntent

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ========================================================
# 1. Calibre 本地/NAS 藏书库检索
# ========================================================
def search_calibre(intent: BookIntent) -> Optional[str]:
    """优先查重 Calibre 书库 (自适应本地 SQLite / NAS SSH 远程)"""
    if not Config.NAS_CALIBRE_DB:
        return None

    def query_sql(title_query: str):
        safe_title = title_query.replace("'", "''")
        # 严格精确匹配：1. 全字完全匹配 ➔ 2. 副标题与版本前缀匹配
        sql = (
            f"SELECT b.id, b.title, b.path, d.name, d.format "
            f"FROM books b "
            f"LEFT JOIN data d ON b.id = d.book AND UPPER(d.format) = 'EPUB' "
            f"WHERE b.title = '{safe_title}' "
            f"   OR b.title LIKE '{safe_title}:%' "
            f"   OR b.title LIKE '{safe_title}：%' "
            f"   OR b.title LIKE '{safe_title} (%' "
            f"   OR b.title LIKE '{safe_title}（%' "
            f"   OR b.title LIKE '{safe_title}——%' "
            f"   OR b.title LIKE '{safe_title} - %' "
            f"ORDER BY (b.title = '{safe_title}') DESC, (d.format IS NOT NULL) DESC, b.id DESC LIMIT 1;"
        )
        # 远程 NAS 模式
        if Config.NAS_SSH_HOST:
            cmd = ["ssh", "-o", "ConnectTimeout=5", Config.NAS_SSH_HOST, f"sqlite3 -separator '|||' \"{Config.NAS_CALIBRE_DB}\""]
            try:
                res = subprocess.run(cmd, input=sql, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
                line = res.stdout.strip()
                if line:
                    parts = line.split("|||")
                    if len(parts) >= 5 and parts[4].upper() == "EPUB":
                        return parts[1], parts[2], parts[3]
            except Exception:
                pass
            return None

        # 本地 SQLite 模式
        if os.path.exists(Config.NAS_CALIBRE_DB):
            try:
                with sqlite3.connect(Config.NAS_CALIBRE_DB, timeout=5) as conn:
                    cur = conn.cursor()
                    cur.execute(sql)
                    row = cur.fetchone()
                    if row and len(row) >= 5 and row[4] and row[4].upper() == "EPUB":
                        return row[1], row[2], row[3]
            except Exception:
                pass
        return None

    match = query_sql(intent.clean_title) or (query_sql(intent.base_title) if intent.base_title else None)
    if not match:
        return None

    matched_title, rel_path, file_name = match
    epub_rel = f"{rel_path}/{file_name}.epub"

    # 磁盘存在性校验
    if Config.NAS_SSH_HOST:
        nas_path = f"{Config.NAS_CALIBRE_ROOT}/{epub_rel}"
        check = subprocess.run(["ssh", "-o", "ConnectTimeout=5", Config.NAS_SSH_HOST, f"test -s \"{nas_path}\""], timeout=8)
        if check.returncode == 0:
            print(f"[+] [Calibre 查重命中] 《{matched_title}》在私有书库中已收录: {nas_path}")
            return nas_path
    elif Config.NAS_CALIBRE_ROOT:
        local_path = os.path.join(Config.NAS_CALIBRE_ROOT, epub_rel)
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            print(f"[+] [Calibre 查重命中] 《{matched_title}》在本地书库中已收录: {local_path}")
            return local_path

    return None

# ========================================================
# 2. Z-Library 检索与客户端 PoW 应答
# ========================================================
class ZLibEngine:
    session = cffi_requests.Session()
    cookies: Dict[str, str] = {}

    @classmethod
    def _init_cookies(cls):
        if Config.ZLIB_USER_ID and Config.ZLIB_USER_KEY:
            cls.cookies["remix_userid"] = Config.ZLIB_USER_ID
            cls.cookies["remix_userkey"] = Config.ZLIB_USER_KEY

    @classmethod
    def _get_proxies(cls):
        p = Config.HTTP_PROXY
        return {"http": p, "https": p} if p else None

    @classmethod
    def _solve_pow(cls, html: str) -> bool:
        """客户端快速计算 SHA-1 PoW 挑战应答"""
        try:
            m = re.search(r"['\"]([0-9A-Fa-f]{40})['\"]", html) or re.search(r"c\s*=\s*['\"]([0-9A-Fa-f]{30,64})['\"]", html)
            if not m:
                return False
            c = m.group(1)
            n1 = int(c[0], 16)
            t0 = time.time()
            for i in range(10000000):
                h = hashlib.sha1((c + str(i)).encode("utf-8")).digest()
                if h[n1] == 0xb0 and h[n1 + 1] == 0x0b:
                    cls.cookies["c_token"] = c + str(i)
                    cls.cookies["c_time"] = f"{time.time() - t0:.3f}"
                    return True
        except Exception:
            pass
        return False

    @classmethod
    def _get_page(cls, url: str) -> Optional[cffi_requests.Response]:
        cls._init_cookies()
        for _ in range(2):
            try:
                resp = cls.session.get(url, cookies=cls.cookies, proxies=cls._get_proxies(), impersonate="chrome120", timeout=25)
                if resp.status_code == 503 and "Checking your browser" in resp.text:
                    if cls._solve_pow(resp.text):
                        continue
                return resp
            except Exception:
                pass
        return None

def search_zlib(intent: BookIntent) -> Optional[str]:
    """通过 Z-Library 检索并流式校验下载 EPUB"""
    if not Config.ZLIB_USER_ID or not Config.ZLIB_USER_KEY:
        return None

    domain = f"https://{Config.ZLIB_DOMAIN}"
    queries = [intent.isbn] if intent.isbn else []
    if intent.base_title:
        queries.append(f"{intent.base_title} {intent.author or ''}".strip())
        queries.append(intent.base_title)
    if intent.clean_title not in queries:
        queries.append(intent.clean_title)

    cards = []
    for q in queries:
        search_url = f"{domain}/s/{cffi_requests.utils.quote(q)}?extensions%5B0%5D=epub"
        print(f"[*] [Z-Lib] 正在检索: {q} ...")
        resp = ZLibEngine._get_page(search_url)
        if resp and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("z-bookcard")
            if cards:
                break

    if not cards:
        return None

    selected_href = next((c.get("href") for c in cards if c.get("extension", "").lower() == "epub"), cards[0].get("href"))
    detail_url = f"{domain}{selected_href}"
    detail_resp = ZLibEngine._get_page(detail_url)
    if not detail_resp or detail_resp.status_code != 200:
        return None

    soup = BeautifulSoup(detail_resp.text, "html.parser")
    dl_btn = soup.select_one("a.addDownloadedBook") or soup.select_one('a[href*="/dl/"]')
    if not dl_btn:
        return None

    dl_path = dl_btn.get("href")
    dl_url = f"{domain}{dl_path}" if dl_path.startswith("/") else dl_path

    local_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
    part_file = Config.CACHE_DIR / f"{intent.clean_title}.epub.part"

    try:
        r = ZLibEngine.session.get(
            dl_url,
            cookies=ZLibEngine.cookies,
            proxies=ZLibEngine._get_proxies(),
            impersonate="chrome120",
            timeout=(45, 300),
            stream=True
        )
        if r.status_code != 200:
            return None

        first = True
        with open(part_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=32768):
                if first:
                    first = False
                    if not chunk.startswith(b"PK\x03\x04"):  # 校验 EPUB Zip 幻数
                        if part_file.exists():
                            part_file.unlink()
                        return None
                f.write(chunk)

        if part_file.exists() and part_file.stat().st_size > 1024:
            if local_file.exists():
                local_file.unlink()
            part_file.rename(local_file)
            print(f"[+] [Z-Lib] 下载成功并落盘: {local_file}")
            return str(local_file)
    except Exception as e:
        print(f"[!] [Z-Lib] 下载中断: {e}")
        if part_file.exists():
            part_file.unlink()
    return None

# ========================================================
# 3. Anna's Archive (安娜档案元搜索)
# ========================================================
def search_annas(intent: BookIntent) -> Optional[str]:
    if not Config.ENABLE_ANNAS_ARCHIVE:
        return None

    proxy = Config.HTTP_PROXY
    proxies = {"http": proxy, "https": proxy} if proxy else None
    query = intent.isbn or intent.clean_title
    search_url = f"https://annas-archive.org/search?q={requests.utils.quote(query)}&ext=epub"

    print(f"[*] [Anna's Archive] 正在检索: {query} ...")
    try:
        resp = requests.get(search_url, headers=HEADERS, proxies=proxies, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.select("a[href^='/md5/']")
            if links:
                detail_url = "https://annas-archive.org" + links[0]["href"]
                d_resp = requests.get(detail_url, headers=HEADERS, proxies=proxies, timeout=15)
                if d_resp.status_code == 200:
                    d_soup = BeautifulSoup(d_resp.text, "html.parser")
                    dl_links = d_soup.select("a[href*='/slow_download/'], a[href*='download']")
                    if dl_links:
                        dl = dl_links[0]["href"]
                        dl_url = dl if dl.startswith("http") else "https://annas-archive.org" + dl
                        target_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
                        with requests.get(dl_url, headers=HEADERS, proxies=proxies, timeout=60, stream=True) as r:
                            if r.status_code == 200:
                                with open(target_file, "wb") as f:
                                    for c in r.iter_content(32768):
                                        f.write(c)
                                if target_file.exists() and target_file.stat().st_size > 1024:
                                    print(f"[+] [Anna's Archive] 下载成功: {target_file}")
                                    return str(target_file)
    except Exception:
        pass
    return None

# ========================================================
# 4. Library Genesis (Libgen 学术/外文兜底)
# ========================================================
def search_libgen(intent: BookIntent) -> Optional[str]:
    if not Config.ENABLE_LIBGEN:
        return None

    proxy = Config.HTTP_PROXY
    proxies = {"http": proxy, "https": proxy} if proxy else None
    query = intent.isbn or intent.clean_title
    mirrors = ["https://libgen.is", "https://libgen.rs", "https://libgen.st"]

    print(f"[*] [Libgen] 正在检索: {query} ...")
    for mirror in mirrors:
        try:
            url = f"{mirror}/search.php?req={requests.utils.quote(query)}&res=25&column=def"
            resp = requests.get(url, headers=HEADERS, proxies=proxies, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                table = soup.find("table", {"class": "c"})
                if table:
                    for row in table.find_all("tr")[1:]:
                        cols = row.find_all("td")
                        if len(cols) > 8 and cols[8].text.strip().lower() == "epub":
                            a_tag = cols[9].find("a")
                            if a_tag:
                                gw_resp = requests.get(a_tag["href"], headers=HEADERS, proxies=proxies, timeout=12)
                                if gw_resp.status_code == 200:
                                    gw_soup = BeautifulSoup(gw_resp.text, "html.parser")
                                    dl_a = gw_soup.find("h2").find("a") if gw_soup.find("h2") else None
                                    if dl_a:
                                        target_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
                                        with requests.get(dl_a["href"], headers=HEADERS, proxies=proxies, timeout=60, stream=True) as r:
                                            with open(target_file, "wb") as f:
                                                for c in r.iter_content(32768):
                                                    f.write(c)
                                        if target_file.exists() and target_file.stat().st_size > 1024:
                                            print(f"[+] [Libgen] 下载成功: {target_file}")
                                            return str(target_file)
        except Exception:
            continue
    return None

# ========================================================
# 5. 级联责任链 (瀑布流执行入口)
# ========================================================
def cascade_search(intent: BookIntent) -> Tuple[Optional[str], Optional[str]]:
    """
    瀑布流执行链：
    Priority 0: Calibre 藏书库查重
    Priority 1: Z-Library
    Priority 2: Anna's Archive
    Priority 3: Library Genesis
    """
    # 0. Calibre
    if res := search_calibre(intent):
        return res, "Calibre Library"

    # 1. Z-Lib
    if res := search_zlib(intent):
        return res, "Z-Library"

    # 2. Anna's Archive
    if res := search_annas(intent):
        return res, "Anna's Archive"

    # 3. Libgen
    if res := search_libgen(intent):
        return res, "Library Genesis"

    return None, None
