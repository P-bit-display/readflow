#!/usr/bin/env python3
import asyncio
import time
from aiohttp import web
from src.config import Config
from src.pipeline import ReadFlowPipeline
import src.web.server as web_server

async def background_sync_task(pipeline: ReadFlowPipeline):
    loop = asyncio.get_running_loop()
    while True:
        try:
            # run pipeline.run_once() in thread pool so it never blocks the async web event loop
            await loop.run_in_executor(None, pipeline.run_once)
        except Exception as e:
            print(f"[!] 轮询发生未知异常: {e}")

        interval = max(Config.CHECK_INTERVAL, 10)
        await asyncio.sleep(interval)

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

    pipeline = ReadFlowPipeline()
    web_server.pipeline_instance = pipeline

    # Start aiohttp WebUI server
    app = web_server.create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8765)
    await site.start()
    print("✅ WebUI 仪表盘已就绪: http://0.0.0.0:8765")

    # Start background recurring sync task
    sync_task = asyncio.create_task(background_sync_task(pipeline))

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
