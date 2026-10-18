import time
import json
import shutil
from pathlib import Path
from src.config import Config
from src.douban import fetch_douban_wish_books
from src.calibre import search_calibre
from src.searcher import download_from_zlibrary
from src.notifier import send_book_email, notify_telegram

HISTORY_FILE = Config.DATA_DIR / "history.json"

def load_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_history(history_set):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(history_set), f, ensure_ascii=False, indent=2)

def process_one_book(book_name: str):
    print(f"\n==================================================")
    print(f"[*] 开始处理豆瓣想图书籍: 《{book_name}》")

    epub_file = None

    # 1. 优先查重 Calibre 书库
    calibre_match = search_calibre(book_name)
    if calibre_match and calibre_match.get("epub_path"):
        print(f"[+] Calibre 库中已存在该书: {calibre_match['title']}")
        epub_file = calibre_match["epub_path"]
    else:
        # 2. 库中没有，去 Z-Library 抓取
        print(f"[-] Calibre 库中未收录，从下载源检索...")
        downloaded = download_from_zlibrary(book_name)
        if downloaded:
            epub_file = downloaded
            # 若配置了 inbox，将下载的书复制一份过去供 Calibre-Web 自动导入
            if Config.INBOX_DIR and Path(Config.INBOX_DIR).exists():
                shutil.copy(downloaded, Config.INBOX_DIR)
                print(f"[+] 已复制至自动入库目录: {Config.INBOX_DIR}")

    # 3. 邮件分发与通知
    if epub_file and Path(epub_file).exists():
        success = send_book_email(epub_file, book_name)
        msg = f"🎉 豆瓣想读书籍《{book_name}》已就绪并成功通过邮件发送！" if success else f"⚠️ 《{book_name}》已就绪，但邮件发送失败。"
        notify_telegram(msg)
        return True
    else:
        msg = f"❌ 未能成功获取豆瓣想读《{book_name}》的电子书文件。"
        print(msg)
        notify_telegram(msg)
        return False


def run_cycle():
    print(f"[*] [{time.strftime('%Y-%m-%d %H:%M:%S')}] 正在检查豆瓣用户 [{Config.DOUBAN_USER_ID}] 的「想读」书单...")
    books = fetch_douban_wish_books(Config.DOUBAN_USER_ID)
    if not books:
        print("[-] 未获取到书籍。")
        return

    history = load_history()
    book_titles = [b["title"] for b in books]

    # 首次启动：记录已有书目避免全量刷屏
    if not HISTORY_FILE.exists():
        print(f"[*] 首次运行：已将现有的 {len(book_titles)} 本书籍记录为初始状态。")
        save_history(set(book_titles))
        return

    # 找出新增
    new_books = [t for t in book_titles if t not in history]
    if not new_books:
        print("[+] 暂无新增想读书籍。")
        return

    print(f"[!] 发现 {len(new_books)} 本新增想读: {new_books}")
    for title in new_books:
        process_one_book(title)
        history.add(title)
        save_history(history)
        time.sleep(3)


def main():
    print("=" * 60)
    print("🚀 Douban2Reader 豆瓣想读自动化图书流已启动！")
    print(f"• 豆瓣用户: {Config.DOUBAN_USER_ID}")
    print(f"• 推送邮箱: {Config.TARGET_EMAIL}")
    print(f"• 侦听频率: 每 {Config.CHECK_INTERVAL} 秒")
    print("=" * 60)

    while True:
        try:
            run_cycle()
        except Exception as e:
            print(f"[!] 轮询发生异常: {e}")
        time.sleep(Config.CHECK_INTERVAL)

if __name__ == "__main__":
    main()
