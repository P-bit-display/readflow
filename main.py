#!/usr/bin/env python3
import asyncio
from aiohttp import web
from src.config import Config
from src.db import Database
from src.engine import ReadFlowEngine
from src.web.server import create_app

async def main():
    print("=" * 65)
    print("🚀 ReadFlow: Universal Zero-UI Book Acquisition & Delivery Engine")
    print("=" * 65)
    print(f"• 豆瓣用户: {Config.DOUBAN_USER_ID or '未启用'}")
    print(f"• Goodreads: {Config.GOODREADS_USER_ID or '未启用'}")
    print(f"• 目标邮箱: {Config.TARGET_EMAIL or '未配置'}")
    print(f"• 侦听频率: 每 {Config.CHECK_INTERVAL} 秒检查一次")
    print("• 控制面板: http://0.0.0.0:8765")
    print("=" * 65)

    # 1. 初始化 SQLite 单文件数据库并完成旧数据无缝迁移
    Database.init_db()

    # 2. 启动 aiohttp WebUI 仪表盘
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8765)
    await site.start()
    print("✅ WebUI 仪表盘已就绪: http://0.0.0.0:8765")

    # 3. 启动后台异步静默巡查任务
    sync_task = asyncio.create_task(ReadFlowEngine.background_loop())

    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] ReadFlow 已安全停止。")
