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
# 2. Z-Library 检索 (支持多镜像/备份站点故障自动转移)
# ========================================================
class ZLibEngine:
    session = cffi_requests.Session()
    cookies: Dict[str, str] = {}
    active_domain: Optional[str] = None

    @classmethod
    def get_domains(cls) -> List[str]:
        domains = []
        if cls.active_domain:
            domains.append(cls.active_domain)
        if Config.ZLIB_DOMAIN and Config.ZLIB_DOMAIN not in domains:
            domains.append(Config.ZLIB_DOMAIN)
        for d in Config.ZLIB_BACKUP_DOMAINS:
            if d and d not in domains:
                domains.append(d)
        return domains

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
                resp = cls.session.get(url, cookies=cls.cookies, proxies=cls._get_proxies(), impersonate="chrome120", timeout=20)
                if resp.status_code == 503 and "Checking your browser" in resp.text:
                    if cls._solve_pow(resp.text):
                        continue
                return resp
            except Exception:
                pass
        return None

def search_zlib(intent: BookIntent) -> Optional[str]:
    """通过 Z-Library 检索并流式校验下载 EPUB (支持多备份站点自动切换)"""
    if not Config.ZLIB_USER_ID or not Config.ZLIB_USER_KEY:
        return None

    queries = [intent.isbn] if intent.isbn else []
    if intent.base_title:
        queries.append(f"{intent.base_title} {intent.author or ''}".strip())
        queries.append(intent.base_title)
    if intent.clean_title not in queries:
        queries.append(intent.clean_title)

    domains = ZLibEngine.get_domains()
    for domain_name in domains:
        domain = f"https://{domain_name}"
        cards = []
        domain_failed = False
        for q in queries:
            search_url = f"{domain}/s/{cffi_requests.utils.quote(q)}?extensions%5B0%5D=epub"
            print(f"[*] [Z-Lib ({domain_name})] 正在检索: {q} ...")
            try:
                resp = ZLibEngine._get_page(search_url)
                if resp and resp.status_code == 200:
                    ZLibEngine.active_domain = domain_name
                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.select("z-bookcard")
                    if cards:
                        break
                elif resp and resp.status_code in (403, 502, 503, 504):
                    print(f"[!] [Z-Lib] 站点 {domain_name} 响应码 {resp.status_code}，切换至备份站点...")
                    domain_failed = True
                    break
            except Exception as e:
                print(f"[!] [Z-Lib] 站点 {domain_name} 连接异常: {e}，切换至备份站点...")
                domain_failed = True
                break

        if domain_failed or not cards:
            continue

        selected_href = next((c.get("href") for c in cards if c.get("extension", "").lower() == "epub"), cards[0].get("href"))
        detail_url = f"{domain}{selected_href}"
        detail_resp = ZLibEngine._get_page(detail_url)
        if not detail_resp or detail_resp.status_code != 200:
            continue

        soup = BeautifulSoup(detail_resp.text, "html.parser")
        dl_btn = soup.select_one("a.addDownloadedBook") or soup.select_one('a[href*="/dl/"]')
        if not dl_btn:
            continue

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
                continue

            first = True
            with open(part_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=32768):
                    if first:
                        first = False
                        if not chunk.startswith(b"PK\x03\x04"):  # 校验 EPUB Zip 幻数
                            if part_file.exists():
                                part_file.unlink()
                            break
                    f.write(chunk)

            if part_file.exists() and part_file.stat().st_size > 1024:
                if local_file.exists():
                    local_file.unlink()
                part_file.rename(local_file)
                print(f"[+] [Z-Lib ({domain_name})] 下载成功并落盘: {local_file}")
                return str(local_file)
        except Exception as e:
            print(f"[!] [Z-Lib ({domain_name})] 下载中断: {e}")
            if part_file.exists():
                part_file.unlink()
            continue

    return None

# ========================================================
# 3. Standard Ebooks (公版经典高品质排版)
# ========================================================
def search_standard_ebooks(intent: BookIntent) -> Optional[str]:
    """通过 Standard Ebooks 检索公版高品质制作电子书"""
    if not Config.ENABLE_STANDARD_EBOOKS:
        return None

    q = intent.base_title or intent.clean_title
    if not any(ord(c) < 128 for c in q):
        return None

    proxy = Config.HTTP_PROXY
    proxies = {"http": proxy, "https": proxy} if proxy else None
    search_url = f"https://standardebooks.org/ebooks?query={requests.utils.quote(q)}"

    print(f"[*] [Standard Ebooks] 正在检索: {q} ...")
    try:
        resp = requests.get(search_url, headers=HEADERS, proxies=proxies, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            book_links = soup.select("a[property='schema:url']")
            if book_links:
                detail_path = book_links[0].get("href")
                detail_url = f"https://standardebooks.org{detail_path}" if detail_path.startswith("/") else detail_path
                d_resp = requests.get(detail_url, headers=HEADERS, proxies=proxies, timeout=12)
                if d_resp.status_code == 200:
                    d_soup = BeautifulSoup(d_resp.text, "html.parser")
                    epub_a = d_soup.select_one("a[href$='.epub']")
                    if epub_a:
                        epub_href = epub_a.get("href")
                        dl_url = f"https://standardebooks.org{epub_href}" if epub_href.startswith("/") else epub_href
                        target_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
                        with requests.get(dl_url, headers=HEADERS, proxies=proxies, timeout=60, stream=True) as r:
                            if r.status_code == 200:
                                with open(target_file, "wb") as f:
                                    for c in r.iter_content(32768):
                                        f.write(c)
                                if target_file.exists() and target_file.stat().st_size > 1024:
                                    print(f"[+] [Standard Ebooks] 下载成功: {target_file}")
                                    return str(target_file)
    except Exception:
        pass
    return None

# ========================================================
# 4. Project Gutenberg (古腾堡世界名著计划)
# ========================================================
def search_gutenberg(intent: BookIntent) -> Optional[str]:
    """通过 Project Gutenberg 古腾堡计划检索公版世界名著"""
    if not Config.ENABLE_GUTENBERG:
        return None

    q = intent.base_title or intent.clean_title
    if not any(ord(c) < 128 for c in q):
        return None

    proxy = Config.HTTP_PROXY
    proxies = {"http": proxy, "https": proxy} if proxy else None
    search_url = f"https://www.gutenberg.org/ebooks/search/?query={requests.utils.quote(q)}"

    print(f"[*] [Project Gutenberg] 正在检索: {q} ...")
    try:
        resp = requests.get(search_url, headers=HEADERS, proxies=proxies, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            first_book = soup.select_one("li.booklink a.link")
            if first_book and first_book.get("href"):
                m = re.search(r"/ebooks/(\d+)", first_book["href"])
                if m:
                    book_id = m.group(1)
                    for ext in [f"{book_id}.epub3.images", f"{book_id}.epub.images", f"{book_id}.epub.noimages"]:
                        dl_url = f"https://www.gutenberg.org/ebooks/{ext}"
                        try:
                            target_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
                            with requests.get(dl_url, headers=HEADERS, proxies=proxies, timeout=60, stream=True, allow_redirects=True) as r:
                                if r.status_code == 200:
                                    first = True
                                    with open(target_file, "wb") as f:
                                        for c in r.iter_content(32768):
                                            if first:
                                                first = False
                                                if not c.startswith(b"PK\x03\x04"):
                                                    break
                                            f.write(c)
                                    if target_file.exists() and target_file.stat().st_size > 1024:
                                        print(f"[+] [Project Gutenberg] 下载成功: {target_file}")
                                        return str(target_file)
                        except Exception:
                            continue
    except Exception:
        pass
    return None

# ========================================================
# 5. Anna's Archive (安娜档案多镜像聚合搜索)
# ========================================================
def search_annas(intent: BookIntent) -> Optional[str]:
    if not Config.ENABLE_ANNAS_ARCHIVE:
        return None

    proxy = Config.HTTP_PROXY
    proxies = {"http": proxy, "https": proxy} if proxy else None
    query = intent.isbn or intent.clean_title
    mirrors = ["https://annas-archive.org", "https://annas-archive.li", "https://annas-archive.se", "https://annas-archive.pm"]

    for base_url in mirrors:
        search_url = f"{base_url}/search?q={requests.utils.quote(query)}&ext=epub"
        print(f"[*] [Anna's Archive ({base_url})] 正在检索: {query} ...")
        try:
            resp = requests.get(search_url, headers=HEADERS, proxies=proxies, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.select("a[href^='/md5/']")
                if links:
                    detail_url = base_url + links[0]["href"]
                    d_resp = requests.get(detail_url, headers=HEADERS, proxies=proxies, timeout=15)
                    if d_resp.status_code == 200:
                        d_soup = BeautifulSoup(d_resp.text, "html.parser")
                        dl_links = d_soup.select("a[href*='/slow_download/'], a[href*='download']")
                        if dl_links:
                            dl = dl_links[0]["href"]
                            dl_url = dl if dl.startswith("http") else base_url + dl
                            target_file = Config.CACHE_DIR / f"{intent.clean_title}.epub"
                            with requests.get(dl_url, headers=HEADERS, proxies=proxies, timeout=60, stream=True) as r:
                                if r.status_code == 200:
                                    first = True
                                    with open(target_file, "wb") as f:
                                        for c in r.iter_content(32768):
                                            if first:
                                                first = False
                                                if not c.startswith(b"PK\x03\x04"):
                                                    break
                                            f.write(c)
                                    if target_file.exists() and target_file.stat().st_size > 1024:
                                        print(f"[+] [Anna's Archive] 下载成功: {target_file}")
                                        return str(target_file)
        except Exception:
            continue
    return None

# ========================================================
# 6. Library Genesis (Libgen 学术/外文多镜像兜底)
# ========================================================
def search_libgen(intent: BookIntent) -> Optional[str]:
    if not Config.ENABLE_LIBGEN:
        return None

    proxy = Config.HTTP_PROXY
    proxies = {"http": proxy, "https": proxy} if proxy else None
    query = intent.isbn or intent.clean_title
    mirrors = ["https://libgen.is", "https://libgen.rs", "https://libgen.st", "https://libgen.li"]

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
# 7. 级联责任链 (瀑布流执行入口)
# ========================================================
def cascade_search(intent: BookIntent) -> Tuple[Optional[str], Optional[str]]:
    """
    全源瀑布流执行链：
    Priority 0: Calibre 藏书库查重 (0ms 搬运)
    Priority 1: Z-Library (多镜像故障自动转移 + 50ms PoW)
    Priority 2: Standard Ebooks (高品质制作公版经典)
    Priority 3: Project Gutenberg (古腾堡世界名著计划)
    Priority 4: Anna's Archive (安娜档案多镜像聚合)
    Priority 5: Library Genesis (创世纪学术外文图书馆)
    """
    # 0. Calibre 私有库查重
    if res := search_calibre(intent):
        return res, "Calibre Library"

    # 1. Z-Lib 主站与备份镜像
    if res := search_zlib(intent):
        domain = ZLibEngine.active_domain or "Z-Library"
        return res, f"Z-Library ({domain})"

    # 2. Standard Ebooks 公版经典
    if res := search_standard_ebooks(intent):
        return res, "Standard Ebooks"

    # 3. Project Gutenberg 古腾堡
    if res := search_gutenberg(intent):
        return res, "Project Gutenberg"

    # 4. Anna's Archive
    if res := search_annas(intent):
        return res, "Anna's Archive"

    # 5. Libgen
    if res := search_libgen(intent):
        return res, "Library Genesis"

    return None, None
