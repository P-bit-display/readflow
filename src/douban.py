import re
import urllib.request
import xml.etree.ElementTree as ET

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_douban_wish_books(user_id: str):
    """
    抓取豆瓣用户的「想读」列表
    返回格式: [{"title": "书名", "link": "https://book.douban.com/subject/xxx/"}, ...]
    """
    if not user_id:
        print("[!] 错误: 未设置 DOUBAN_USER_ID")
        return []

    wish_url = f"https://book.douban.com/people/{user_id}/wish"
    req = urllib.request.Request(wish_url, headers=HEADERS)
    books = []
    seen = set()

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")
            # 匹配书籍条目链接与标题
            matches = re.findall(r'<a href="(https://book\.douban\.com/subject/\d+/)".*?title="(.*?)"', html)
            for link, title in matches:
                title = title.strip()
                if title and title not in seen:
                    seen.add(title)
                    books.append({"title": title, "link": link})
    except Exception as e:
        print(f"[!] 抓取豆瓣想读书单失败: {e}")

    # 尝试从 RSS 补充抓取 (双通道保障)
    rss_url = f"https://www.douban.com/feed/people/{user_id}/interests"
    try:
        rss_req = urllib.request.Request(rss_url, headers=HEADERS)
        with urllib.request.urlopen(rss_req, timeout=15) as resp:
            root = ET.fromstring(resp.read())
            channel = root.find("channel")
            if channel is not None:
                for item in channel.findall("item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    if title_elem is not None and link_elem is not None:
                        t = title_elem.text or ""
                        l = link_elem.text or ""
                        if "book.douban.com" in l or "想读" in t:
                            clean_title = re.sub(r"^(想读|在读|读过)", "", t).strip()
                            clean_title = clean_title.replace("《", "").replace("》", "")
                            if clean_title and clean_title not in seen:
                                seen.add(clean_title)
                                books.append({"title": clean_title, "link": l})
    except Exception:
        pass

    return books
