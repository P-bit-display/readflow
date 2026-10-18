import os
import json
import time
import asyncio
import subprocess
from pathlib import Path
from aiohttp import web
from src.config import Config
from src.state import SystemState
from src.pipeline import ReadFlowPipeline
from src.models import BookIntent

STATIC_DIR = Path(__file__).parent / "static"
LOG_FILE = Path("/Users/placid/.hermes/logs/douban-sync.log")
ENV_FILE = Path(__file__).parent.parent.parent / ".env"

pipeline_instance = None

def get_pipeline():
    global pipeline_instance
    if pipeline_instance is None:
        pipeline_instance = ReadFlowPipeline()
    return pipeline_instance

async def handle_index(request):
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return web.FileResponse(index_file)
    return web.Response(text="ReadFlow WebUI: index.html not found", status=404)

async def handle_get_status(request):
    p = get_pipeline()
    ledger = p.load_ledger()
    state = SystemState.to_dict()
    
    douban_cnt = sum(1 for b in ledger if b.get("source") == "douban")
    goodreads_cnt = sum(1 for b in ledger if b.get("source") == "goodreads")
    zlib_cnt = sum(1 for b in ledger if "z-library" in str(b.get("matched_by", "")).lower())
    calibre_cnt = sum(1 for b in ledger if "calibre" in str(b.get("matched_by", "")).lower())

    return web.json_response({
        "daemon": {
            "status": "online",
            "pid": os.getpid(),
            "uptime_seconds": state["uptime_seconds"],
            "port": 8765
        },
        "telemetry": state,
        "metrics": {
            "total_delivered": len(ledger),
            "calibre_total": state["calibre_total"],
            "douban_count": douban_cnt,
            "goodreads_count": goodreads_cnt,
            "zlib_hits": zlib_cnt,
            "calibre_hits": calibre_cnt
        },
        "recent_activity": ledger[:5]
    })

async def handle_get_history(request):
    q = request.query.get("q", "").strip().lower()
    p = get_pipeline()
    ledger = p.load_ledger()
    if q:
        ledger = [
            b for b in ledger
            if q in b.get("title", "").lower() 
            or q in b.get("author", "").lower()
            or q in b.get("matched_by", "").lower()
        ]
    return web.json_response({"history": ledger})

async def handle_get_config(request):
    # 读取当前最新配置，安全脱敏
    conf = {
        "DOUBAN_USER_ID": os.getenv("DOUBAN_USER_ID", "151885595"),
        "GOODREADS_USER_ID": os.getenv("GOODREADS_USER_ID", "205766400"),
        "CHECK_INTERVAL_SECONDS": int(os.getenv("CHECK_INTERVAL_SECONDS", "600")),
        "TARGET_EMAIL": os.getenv("TARGET_EMAIL", "placid.dang@163.com"),
        "NAS_SSH_HOST": os.getenv("NAS_SSH_HOST", "nas"),
        "NAS_CALIBRE_ROOT": os.getenv("NAS_CALIBRE_ROOT", "/volume1/homes/placid/Books/00-Calibre"),
        "NAS_CALIBRE_DB": os.getenv("NAS_CALIBRE_DB", "/volume1/homes/placid/Books/00-Calibre/metadata.db"),
        "NAS_INBOX_DIR": os.getenv("NAS_INBOX_DIR", "/volume1/homes/placid/Books/05-inbox"),
        "NAS_PUSH_DIR": os.getenv("NAS_PUSH_DIR", "/volume1/homes/placid/Books/05-inbox/最新推送"),
        "ZLIB_EMAIL": os.getenv("ZLIB_EMAIL", "placid.dang@outlook.com"),
        "ZLIB_PASSWORD_MASKED": "••••••••" if os.getenv("ZLIB_PASSWORD") else "",
        "ZLIB_USER_ID": os.getenv("ZLIB_USER_ID", "11136248"),
        "ZLIB_USER_KEY": os.getenv("ZLIB_USER_KEY", "a7835d4e628fa93baffdec32c6d7e831"),
        "ZLIB_DOMAIN": os.getenv("ZLIB_DOMAIN", "z-library.sk"),
        "HTTP_PROXY": os.getenv("HTTP_PROXY", "http://127.0.0.1:7897"),
        "ENABLE_ANNAS_ARCHIVE": os.getenv("ENABLE_ANNAS_ARCHIVE", "true").lower() == "true",
        "ENABLE_LIBGEN": os.getenv("ENABLE_LIBGEN", "true").lower() == "true"
    }
    return web.json_response(conf)

async def handle_update_config(request):
    try:
        data = await request.json()
        env_lines = []
        
        # 读取现有 .env 保留注释，更新值
        current_env = {}
        if ENV_FILE.exists():
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str and not line_str.startswith("#") and "=" in line_str:
                        k, v = line_str.split("=", 1)
                        current_env[k.strip()] = v.strip()

        # 更新传入的字段
        for k, v in data.items():
            if k == "ZLIB_PASSWORD_MASKED":
                continue
            if k == "ZLIB_PASSWORD" and not v:
                continue
            if isinstance(v, bool):
                current_env[k] = "true" if v else "false"
            else:
                current_env[k] = str(v).strip()

        # 重新生成规范的 .env 文本
        new_content = [
            "# ========================================================",
            "# ReadFlow 生产环境统一配置 (由 WebUI 自动管理保存)",
            "# ========================================================",
            "",
            "# 1. 意图捕获源",
            f"DOUBAN_USER_ID={current_env.get('DOUBAN_USER_ID', '151885595')}",
            f"GOODREADS_USER_ID={current_env.get('GOODREADS_USER_ID', '205766400')}",
            f"CHECK_INTERVAL_SECONDS={current_env.get('CHECK_INTERVAL_SECONDS', '600')}",
            "",
            "# 2. 邮件分发目标",
            f"TARGET_EMAIL={current_env.get('TARGET_EMAIL', 'placid.dang@163.com')}",
            "",
            "# 3. 群晖 NAS 配置",
            f"NAS_SSH_HOST={current_env.get('NAS_SSH_HOST', 'nas')}",
            f"NAS_CALIBRE_ROOT={current_env.get('NAS_CALIBRE_ROOT', '/volume1/homes/placid/Books/00-Calibre')}",
            f"NAS_CALIBRE_DB={current_env.get('NAS_CALIBRE_DB', '/volume1/homes/placid/Books/00-Calibre/metadata.db')}",
            f"NAS_INBOX_DIR={current_env.get('NAS_INBOX_DIR', '/volume1/homes/placid/Books/05-inbox')}",
            f"NAS_PUSH_DIR={current_env.get('NAS_PUSH_DIR', '/volume1/homes/placid/Books/05-inbox/最新推送')}",
            "",
            "# 4. Z-Library 与检索凭据",
            f"ZLIB_EMAIL={current_env.get('ZLIB_EMAIL', '')}",
            f"ZLIB_PASSWORD={current_env.get('ZLIB_PASSWORD', '')}",
            f"ZLIB_USER_ID={current_env.get('ZLIB_USER_ID', '')}",
            f"ZLIB_USER_KEY={current_env.get('ZLIB_USER_KEY', '')}",
            f"ZLIB_DOMAIN={current_env.get('ZLIB_DOMAIN', 'z-library.sk')}",
            f"HTTP_PROXY={current_env.get('HTTP_PROXY', 'http://127.0.0.1:7897')}",
            f"ENABLE_ANNAS_ARCHIVE={current_env.get('ENABLE_ANNAS_ARCHIVE', 'true')}",
            f"ENABLE_LIBGEN={current_env.get('ENABLE_LIBGEN', 'true')}",
            ""
        ]

        tmp_env = ENV_FILE.with_suffix(".tmp")
        with open(tmp_env, "w", encoding="utf-8") as f:
            f.write("\n".join(new_content))
        os.replace(tmp_env, ENV_FILE)

        # 内存同步加载
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE, override=True)

        return web.json_response({"status": "ok", "message": "配置已安全更新并原子保存！"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def handle_trigger_sync(request):
    if SystemState.is_syncing:
        return web.json_response({"status": "busy", "message": "当前已有同步任务正在进行中！"})
    
    loop = asyncio.get_event_loop()
    p = get_pipeline()
    # 异步在线程池中触发，不阻塞 WebUI 响应
    loop.run_in_executor(None, p.run_once)
    return web.json_response({"status": "started", "message": "已触发全量巡检同步任务！"})

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
        p = get_pipeline()
        loop.run_in_executor(None, p.process_intent, intent)
        return web.json_response({"status": "started", "message": f"已提交即时找书任务《{title}》，后台正在检索并投递！"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def handle_get_logs(request):
    lines = []
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                lines = [l.rstrip() for l in all_lines[-120:]]
        except Exception as e:
            lines = [f"[!] 读取日志错误: {e}"]
    return web.json_response({"logs": lines})

async def handle_restart_service(request):
    try:
        uid = os.getuid()
        cmd = f"launchctl kickstart -k gui/{uid}/ai.hermes.douban-sync"
        subprocess.Popen(cmd, shell=True)
        return web.json_response({"status": "restarting", "message": "服务重启信号已下发！"})
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
    app.router.add_get("/api/logs", handle_get_logs)
    app.router.add_post("/api/restart", handle_restart_service)
    
    if (STATIC_DIR).exists():
        app.router.add_static("/static", STATIC_DIR)
    return app
