#!/usr/bin/env python3
import time
from src.config import Config
from src.pipeline import ReadFlowPipeline

def main():
    print("=" * 65)
    print("🚀 ReadFlow: Universal Zero-UI Book Acquisition & Delivery Engine")
    print("=" * 65)
    print(f"• 豆瓣用户: {Config.DOUBAN_USER_ID or '未启用'}")
    print(f"• Goodreads: {Config.GOODREADS_USER_ID or '未启用'}")
    print(f"• 目标邮箱: {Config.TARGET_EMAIL or '未配置'}")
    print(f"• 侦听频率: 每 {Config.CHECK_INTERVAL} 秒检查一次")
    print("=" * 65)

    pipeline = ReadFlowPipeline()

    while True:
        try:
            pipeline.run_once()
        except KeyboardInterrupt:
            print("\n[*] ReadFlow 已安全停止。")
            break
        except Exception as e:
            print(f"[!] 轮询发生未知异常: {e}")

        time.sleep(Config.CHECK_INTERVAL)

if __name__ == "__main__":
    main()
