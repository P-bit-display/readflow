import os
import sys
import json
import time
import asyncio
import subprocess
from pathlib import Path
from aiohttp import web
from dotenv import load_dotenv
from src.config import Config
from src.state import SystemState
from src.db import Database
from src.models import BookIntent
from src.engine import ReadFlowEngine

STATIC_DIR = Path(__file__).parent / "static"
ENV_FILE = Path(__file__).parent.parent.parent / ".env"

def get_log_file() -> Path:
    """智能查找运行日志路径"""
    if Config.LOG_FILE and Path(Config.LOG_FILE).exists():
        return Path(Config.LOG_FILE)
    for c in [
        Path(__file__).parent.parent.parent / "logs" / "readflow.log",
        Path.home() / ".hermes" / "logs" / "douban-sync.log",
        Path.home() / ".readflow" / "logs" / "readflow.log",
    ]:
        if c.exists():
            return c
    return Path(__file__).parent.parent.parent / "logs" / "readflow.log"

async def handle_index(request):
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return web.FileResponse(index_file)
    return web.Response(text="ReadFlow WebUI: index.html not found", status=404)

async def handle_get_status(request):
    state = SystemState.to_dict()
    metrics = Database.get_metrics()
    recent = Database.get_recent_activity(5)

    return web.json_response({
        "daemon": {
            "status": "online",
            "pid": os.getpid(),
            "uptime_seconds": state["uptime_seconds"],
            "port": 8765
        },
        "telemetry": state,
        "metrics": {
            "total_delivered": metrics["total_delivered"],
            "calibre_total": state["calibre_total"],
            "douban_count": metrics["douban_count"],
            "goodreads_count": metrics["goodreads_count"],
            "zlib_hits": metrics["zlib_hits"],
            "calibre_hits": metrics["calibre_hits"]
        },
        "recent_activity": recent
    })

async def handle_get_history(request):
    q = request.query.get("q", "").strip()
    return web.json_response({"history": Database.get_ledger(query=q)})

async def handle_get_config(request):
    return web.json_response({
        "DOUBAN_USER_ID": os.getenv("DOUBAN_USER_ID", ""),
        "GOODREADS_USER_ID": os.getenv("GOODREADS_USER_ID", ""),
        "BANGUMI_USER_ID": os.getenv("BANGUMI_USER_ID", ""),
        "CUSTOM_RSS_URLS": os.getenv("CUSTOM_RSS_URLS", ""),
        "WEBHOOK_TOKEN": os.getenv("WEBHOOK_TOKEN", ""),
        "CHECK_INTERVAL_SECONDS": int(os.getenv("CHECK_INTERVAL_SECONDS", "600")),
        "TARGET_EMAIL": os.getenv("TARGET_EMAIL", ""),
        "SMTP_SERVER": os.getenv("SMTP_SERVER", ""),
        "SMTP_PORT": int(os.getenv("SMTP_PORT", "465")),
        "SMTP_USER": os.getenv("SMTP_USER", ""),
        "SMTP_PASSWORD_MASKED": "••••••••" if os.getenv("SMTP_PASSWORD") else "",
        "NAS_SSH_HOST": os.getenv("NAS_SSH_HOST", ""),
        "NAS_CALIBRE_ROOT": os.getenv("NAS_CALIBRE_ROOT", ""),
        "NAS_CALIBRE_DB": os.getenv("NAS_CALIBRE_DB", ""),
        "NAS_INBOX_DIR": os.getenv("NAS_INBOX_DIR", ""),
        "NAS_PUSH_DIR": os.getenv("NAS_PUSH_DIR", ""),
        "ZLIB_EMAIL": os.getenv("ZLIB_EMAIL", ""),
        "ZLIB_PASSWORD_MASKED": "••••••••" if os.getenv("ZLIB_PASSWORD") else "",
        "ZLIB_USER_ID": os.getenv("ZLIB_USER_ID", ""),
        "ZLIB_USER_KEY": os.getenv("ZLIB_USER_KEY", ""),
        "ZLIB_DOMAIN": os.getenv("ZLIB_DOMAIN", "z-library.sk"),
        "ZLIB_BACKUP_DOMAINS": os.getenv("ZLIB_BACKUP_DOMAINS", "z-lib.gs,z-library.do,z-lib.is,singlelogin.re,z-lib.id,1lib.sk"),
        "HTTP_PROXY": os.getenv("HTTP_PROXY", ""),
        "ENABLE_ANNAS_ARCHIVE": os.getenv("ENABLE_ANNAS_ARCHIVE", "true").lower() == "true",
        "ENABLE_LIBGEN": os.getenv("ENABLE_LIBGEN", "true").lower() == "true",
        "ENABLE_STANDARD_EBOOKS": os.getenv("ENABLE_STANDARD_EBOOKS", "true").lower() == "true",
        "ENABLE_GUTENBERG": os.getenv("ENABLE_GUTENBERG", "true").lower() == "true"
    })

async def handle_update_config(request):
    try:
        data = await request.json()
        current_env = {}
        if ENV_FILE.exists():
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str and not line_str.startswith("#") and "=" in line_str:
                        k, v = line_str.split("=", 1)
                        current_env[k.strip()] = v.strip()

        for k, v in data.items():
            if k in ("ZLIB_PASSWORD_MASKED", "SMTP_PASSWORD_MASKED"):
                continue
            if k in ("ZLIB_PASSWORD", "SMTP_PASSWORD") and not v:
                continue
            if isinstance(v, bool):
                current_env[k] = "true" if v else "false"
            else:
                current_env[k] = str(v).strip()

        new_content = [
            "# ========================================================",
            "# ReadFlow 生产环境统一配置 (由 WebUI 自动管理保存)",
            "# ========================================================",
            "",
            "# 1. 意图捕获源 (豆瓣 / Goodreads / Bangumi / 自定义 RSS / Webhook)",
            f"DOUBAN_USER_ID={current_env.get('DOUBAN_USER_ID', '')}",
            f"GOODREADS_USER_ID={current_env.get('GOODREADS_USER_ID', '')}",
            f"BANGUMI_USER_ID={current_env.get('BANGUMI_USER_ID', '')}",
            f"CUSTOM_RSS_URLS={current_env.get('CUSTOM_RSS_URLS', '')}",
            f"WEBHOOK_TOKEN={current_env.get('WEBHOOK_TOKEN', '')}",
            f"CHECK_INTERVAL_SECONDS={current_env.get('CHECK_INTERVAL_SECONDS', '600')}",
            "",
            "# 2. 邮件分发与推送配置",
            f"TARGET_EMAIL={current_env.get('TARGET_EMAIL', '')}",
            f"SMTP_SERVER={current_env.get('SMTP_SERVER', '')}",
            f"SMTP_PORT={current_env.get('SMTP_PORT', '465')}",
            f"SMTP_USER={current_env.get('SMTP_USER', '')}",
            f"SMTP_PASSWORD={current_env.get('SMTP_PASSWORD', '')}",
            "",
            "# 3. 群晖 NAS / 本地 Calibre 书库配置 (可选)",
            f"NAS_SSH_HOST={current_env.get('NAS_SSH_HOST', '')}",
            f"NAS_CALIBRE_ROOT={current_env.get('NAS_CALIBRE_ROOT', '')}",
            f"NAS_CALIBRE_DB={current_env.get('NAS_CALIBRE_DB', '')}",
            f"NAS_INBOX_DIR={current_env.get('NAS_INBOX_DIR', '')}",
            f"NAS_PUSH_DIR={current_env.get('NAS_PUSH_DIR', '')}",
            "",
            "# 4. 多书源检索凭据与备份网络",
            f"ZLIB_EMAIL={current_env.get('ZLIB_EMAIL', '')}",
            f"ZLIB_PASSWORD={current_env.get('ZLIB_PASSWORD', '')}",
            f"ZLIB_USER_ID={current_env.get('ZLIB_USER_ID', '')}",
            f"ZLIB_USER_KEY={current_env.get('ZLIB_USER_KEY', '')}",
            f"ZLIB_DOMAIN={current_env.get('ZLIB_DOMAIN', 'z-library.sk')}",
            f"ZLIB_BACKUP_DOMAINS={current_env.get('ZLIB_BACKUP_DOMAINS', 'z-lib.gs,z-library.do,z-lib.is,singlelogin.re,z-lib.id,1lib.sk')}",
            f"HTTP_PROXY={current_env.get('HTTP_PROXY', '')}",
            f"ENABLE_ANNAS_ARCHIVE={current_env.get('ENABLE_ANNAS_ARCHIVE', 'true')}",
            f"ENABLE_LIBGEN={current_env.get('ENABLE_LIBGEN', 'true')}",
            f"ENABLE_STANDARD_EBOOKS={current_env.get('ENABLE_STANDARD_EBOOKS', 'true')}",
            f"ENABLE_GUTENBERG={current_env.get('ENABLE_GUTENBERG', 'true')}",
            ""
        ]

        tmp_env = ENV_FILE.with_suffix(".tmp")
        with open(tmp_env, "w", encoding="utf-8") as f:
            f.write("\n".join(new_content))
        os.replace(tmp_env, ENV_FILE)

        load_dotenv(dotenv_path=ENV_FILE, override=True)
        return web.json_response({"status": "success", "message": "配置已安全更新并即时热生效！"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def handle_trigger_sync(request):
    try:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, ReadFlowEngine.run_cycle)
        return web.json_response({"status": "triggered", "message": "已立即下发同步意图检查任务！"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def handle_instant_search(request):
    try:
        data = await request.json()
        title = data.get("title", "").strip()
        author = data.get("author", "").strip() or None
        isbn = data.get("isbn", "").strip() or None
        if not title:
            return web.json_response({"status": "error", "message": "书名不能为空！"}, status=400)

        intent = BookIntent(title=title, author=author, isbn=isbn, source="manual")
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, ReadFlowEngine.process_intent, intent)
        return web.json_response({"status": "started", "message": f"已提交即时找书任务《{title}》，后台正在检索并投递！"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def handle_webhook_intent(request):
    """通用 Webhook / iOS 快捷指令意图接收入口"""
    try:
        title = ""
        author = None
        isbn = None
        token = ""

        if request.method == "POST":
            if request.content_type == "application/json":
                data = await request.json()
                title = data.get("title", "").strip()
                author = data.get("author", "").strip() or None
                isbn = data.get("isbn", "").strip() or None
                token = data.get("token", "").strip()
            else:
                post_data = await request.post()
                title = post_data.get("title", "").strip()
                author = post_data.get("author", "").strip() or None
                isbn = post_data.get("isbn", "").strip() or None
                token = post_data.get("token", "").strip()
        else:
            title = request.query.get("title", "").strip()
            author = request.query.get("author", "").strip() or None
            isbn = request.query.get("isbn", "").strip() or None
            token = request.query.get("token", "").strip()

        # Token 校验 (若配置了 WEBHOOK_TOKEN)
        expected_token = os.getenv("WEBHOOK_TOKEN", "").strip()
        if expected_token and token != expected_token:
            return web.json_response({"status": "error", "message": "鉴权失败：Token 无效或未提供！"}, status=401)

        if not title:
            return web.json_response({"status": "error", "message": "缺少必填参数: title (书名)"}, status=400)

        intent = BookIntent(title=title, author=author, isbn=isbn, source="webhook")
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, ReadFlowEngine.process_intent, intent)
        return web.json_response({
            "status": "queued",
            "message": f"已接收《{title}》即时阅读意图，后台已启动多源瀑布流检索与交付！",
            "book": title,
            "author": author
        })
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def handle_get_logs(request):
    lines = []
    log_path = get_log_file()
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [l.rstrip() for l in f.readlines()[-120:]]
        except Exception as e:
            lines = [f"[!] 读取日志错误: {e}"]
    else:
        lines = [f"[*] 暂无日志文件或日志路径为: {log_path}"]
    return web.json_response({"logs": lines})

async def handle_restart_service(request):
    try:
        service_name = os.getenv("LAUNCHD_SERVICE", "ai.hermes.douban-sync")
        async def delayed_restart():
            await asyncio.sleep(1)
            if sys.platform == "darwin" and hasattr(os, "getuid"):
                uid = os.getuid()
                res = subprocess.run(f"launchctl kickstart -k gui/{uid}/{service_name}", shell=True)
                if res.returncode == 0:
                    return
            os._exit(0)

        asyncio.create_task(delayed_restart())
        return web.json_response({"status": "restarting", "message": "服务重启信号已下发，后台正在重新载入！"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

def create_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/status", handle_get_status)
    app.router.add_get("/api/history", handle_get_history)
    app.router.add_get("/api/config", handle_get_config)
    app.router.add_post("/api/config", handle_update_config)
    app.router.add_post("/api/sync", handle_trigger_sync)
    app.router.add_post("/api/search_book", handle_instant_search)
    app.router.add_post("/api/webhook/intent", handle_webhook_intent)
    app.router.add_get("/api/webhook/intent", handle_webhook_intent)
    app.router.add_get("/api/logs", handle_get_logs)
    app.router.add_post("/api/restart", handle_restart_service)
    
    if STATIC_DIR.exists():
        app.router.add_static("/static", STATIC_DIR)
    return app
