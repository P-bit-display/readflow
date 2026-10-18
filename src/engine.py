import time
import os
import asyncio
import subprocess
from pathlib import Path
from typing import Optional
from src.config import Config
from src.models import BookIntent
from src.state import SystemState
from src.db import Database
from src.watchers import fetch_all_wishes
from src.searchers import cascade_search
from src.delivery import send_email, ingest_to_calibre

class ReadFlowEngine:
    """ReadFlow 微内核调度引擎"""

    @classmethod
    def refresh_calibre_count(cls):
        now = time.time()
        if now - SystemState.last_calibre_check > 300:
            SystemState.last_calibre_check = now
            if Config.NAS_SSH_HOST and Config.NAS_CALIBRE_DB:
                try:
                    cmd = ["ssh", "-o", "ConnectTimeout=3", Config.NAS_SSH_HOST, f"sqlite3 \"{Config.NAS_CALIBRE_DB}\" 'SELECT count(*) FROM books;'"]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, timeout=5)
                    val = res.stdout.strip()
                    if val.isdigit():
                        SystemState.calibre_count_cache = int(val)
                except Exception:
                    pass

    @classmethod
    def process_intent(cls, intent: BookIntent) -> bool:
        """端到端处理单本图书意图：多源瀑布检索 ➔ 资产归档 ➔ 邮件直推 ➔ SQLite 记账"""
        print(f"\n{'=' * 60}\n[*] 处理新阅读意图: {intent}\n{'=' * 60}")
        SystemState.set_active_task(intent.clean_title, "多源检索中", f"正在检索《{intent.clean_title}》...")

        # 1. 瀑布流多源检索
        epub_path, hit_source = cascade_search(intent)

        # 校验文件有效性（兼容远程 NAS /volume1 绝对路径与本地文件系统）
        is_valid = bool(epub_path and (epub_path.startswith("/volume1") or Path(epub_path).exists()))
        if not is_valid:
            SystemState.set_active_task(intent.clean_title, "检索未命中", "全网与自建库均未找到可用 EPUB")
            print(f"[-] 所有检索源均未找到《{intent.clean_title}》")
            Database.record_book(
                title=intent.title,
                clean_title=intent.clean_title,
                base_title=intent.base_title,
                author=intent.author,
                isbn=intent.isbn,
                source=intent.source,
                status="failed",
                matched_by="未命中",
                size_mb=0.0,
                recipient=Config.TARGET_EMAIL
            )
            time.sleep(3)
            if not SystemState.is_syncing:
                SystemState.clear_active_task()
            return False

        # 2. 资产入库
        SystemState.set_active_task(intent.clean_title, "私有书库归档", "正在入库 Calibre 与网盘目录...")
        ingest_to_calibre(epub_path, intent.clean_title)

        # 3. 邮件投递
        SystemState.set_active_task(intent.clean_title, "静默邮件投递", f"正在发送至 {Config.TARGET_EMAIL} ...")
        mail_ok = send_email(epub_path, intent.clean_title, Config.TARGET_EMAIL)

        # 4. SQLite 持久化
        file_size_mb = 1.0
        if epub_path and not epub_path.startswith("/volume1") and Path(epub_path).exists():
            file_size_mb = round(Path(epub_path).stat().st_size / (1024 * 1024), 2)
        Database.record_book(
            title=intent.title,
            clean_title=intent.clean_title,
            base_title=intent.base_title,
            author=intent.author,
            isbn=intent.isbn,
            source=intent.source,
            status="delivered" if mail_ok else "ingested_only",
            matched_by=hit_source or "未知源",
            size_mb=file_size_mb,
            recipient=Config.TARGET_EMAIL
        )

        SystemState.set_active_task(intent.clean_title, "交付完成", f"已成功推送到 {Config.TARGET_EMAIL}")
        time.sleep(3)
        if not SystemState.is_syncing:
            SystemState.clear_active_task()
        return True

    @classmethod
    def run_cycle(cls):
        """单次全量轮询周期"""
        SystemState.is_syncing = True
        SystemState.set_active_task(None, "正在巡检", "正在检查豆瓣与 Goodreads 待读动态...")
        cls.refresh_calibre_count()

        try:
            wishes = fetch_all_wishes()
            if not wishes:
                return

            for intent in wishes:
                # 借助 SQLite 快速双向排重，已处理图书直接跳过
                if not Database.is_seen(intent.clean_title, intent.base_title):
                    success = cls.process_intent(intent)
                    time.sleep(3)  # 温和间隔
        finally:
            SystemState.is_syncing = False
            SystemState.clear_active_task()
            SystemState.last_sync_time = time.time()
            SystemState.next_sync_time = time.time() + Config.CHECK_INTERVAL

    @classmethod
    async def background_loop(cls):
        """异步后台守护轮询任务"""
        loop = asyncio.get_running_loop()
        while True:
            try:
                await loop.run_in_executor(None, cls.run_cycle)
            except Exception as e:
                print(f"[!] 巡检异常: {e}")

            interval = max(Config.CHECK_INTERVAL, 10)
            await asyncio.sleep(interval)
