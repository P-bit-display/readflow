import os
import shutil
import smtplib
import subprocess
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.header import Header
from email import encoders
from src.config import Config

MAX_ATTACH_SIZE = 24 * 1024 * 1024  # 24MB 阈值防爆

def send_email(epub_path: str, book_title: str, target: str) -> bool:
    """邮件静默分发：优先标准 SMTP 本地直发，带群晖 NAS 远程协同兼容"""
    if not target or not epub_path:
        return False

    # 优先使用配置的标准 SMTP
    if Config.SMTP_SERVER and Config.SMTP_USER and Config.SMTP_PASSWORD:
        return _send_local_smtp(epub_path, book_title, target)

    # 远程 NAS 协同发信
    if Config.NAS_SSH_HOST:
        return _send_via_nas(epub_path, book_title, target)

    print("[!] 尚未配置 SMTP 或 NAS 发信通道，跳过邮件推送。")
    return False

def _send_local_smtp(epub_path: str, book_title: str, target: str) -> bool:
    if not os.path.exists(epub_path):
        return False

    file_size = os.path.getsize(epub_path)
    msg = MIMEMultipart()
    msg["From"] = Config.SMTP_USER
    msg["To"] = target
    msg["Subject"] = Header(f"【ReadFlow 图书推送】《{book_title}》", "utf-8").encode()

    if file_size > MAX_ATTACH_SIZE:
        size_mb = file_size / (1024 * 1024)
        body = f"你好！您想读的书籍《{book_title}》已准备就绪。\n\n⚠️ 提示：该书体积为 {size_mb:.1f} MB（超出邮箱附件 25MB 上限），已存入私有云书库。"
        msg.attach(MIMEText(body, "plain", "utf-8"))
    else:
        body = f"你好！您想读的书籍《{book_title}》已准备就绪，附件为最新 EPUB 版本，请在阅读设备查收。"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with open(epub_path, "rb") as f:
            part = MIMEBase("application", "epub+zip")
            part.set_payload(f.read())
        encoders.encode_base64(part)

        # RFC 2047 双重 Base64 编码，彻底消灭 noname 乱码
        basename = os.path.basename(epub_path)
        encoded_name = Header(basename, "utf-8").encode()
        part.add_header("Content-Disposition", f'attachment; filename="{encoded_name}"')
        part.add_header("Content-Type", "application/epub+zip", name=("utf-8", "", basename))
        msg.attach(part)

    print(f"[*] 正在通过 SMTP ({Config.SMTP_SERVER}:{Config.SMTP_PORT}) 发送《{book_title}》至 {target} ...")
    try:
        if Config.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(Config.SMTP_SERVER, Config.SMTP_PORT, timeout=30) as server:
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                server.sendmail(Config.SMTP_USER, [target], msg.as_string())
        else:
            with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                server.sendmail(Config.SMTP_USER, [target], msg.as_string())
        print(f"[+] 邮件已成功送达 {target}！")
        return True
    except Exception as e:
        print(f"[!] SMTP 邮件发送失败: {e}")
        return False

def _send_via_nas(epub_path: str, book_title: str, target: str) -> bool:
    remote_path = epub_path
    if not epub_path.startswith("/volume1"):
        file_name = os.path.basename(epub_path)
        remote_path = f"/tmp/{file_name}"
        try:
            with open(epub_path, "rb") as f:
                subprocess.run(["ssh", Config.NAS_SSH_HOST, f"cat > \"{remote_path}\""], input=f.read(), check=True)
        except Exception as e:
            print(f"[!] 上传发信临时文件失败: {e}")
            return False

    remote_script = os.getenv("NAS_MAILER_SCRIPT") or (str(Path(Config.NAS_CALIBRE_ROOT).parent / "send_book_mail.py") if Config.NAS_CALIBRE_ROOT else "~/Books/send_book_mail.py")
    cmd = ["ssh", Config.NAS_SSH_HOST, f"python3 \"{remote_script}\" \"{remote_path}\" \"{book_title}\" \"{target}\""]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=35)
        if res.returncode == 0:
            print(f"[+] 邮件已成功发送至 {target}！")
            return True
        else:
            print(f"[!] 邮件发送报错: {res.stderr}")
            return False
    except Exception as e:
        print(f"[!] 邮件发送异常: {e}")
        return False

def ingest_to_calibre(epub_path: str, book_title: str) -> bool:
    """数字资产入库：自动同步至 Calibre-Web 入库收件箱与最新推送网盘"""
    if not epub_path:
        return False

    clean_title = book_title.replace("/", "_").replace("\\", "_")
    file_name = os.path.basename(epub_path)

    # 1. 远程 NAS 模式
    if Config.NAS_SSH_HOST:
        target_push_path = f"{Config.NAS_PUSH_DIR}/{clean_title}.epub" if Config.NAS_PUSH_DIR else ""
        if not epub_path.startswith("/volume1"):
            remote_inbox_path = f"{Config.NAS_INBOX_DIR}/{file_name}" if Config.NAS_INBOX_DIR else f"/tmp/{file_name}"
            try:
                with open(epub_path, "rb") as f:
                    subprocess.run(["ssh", Config.NAS_SSH_HOST, f"cat > \"{remote_inbox_path}\""], input=f.read(), check=True)
                print(f"[+] 新书已上传至 NAS 入库收件箱: {remote_inbox_path}")
            except Exception as e:
                print(f"[!] 上传 NAS 收件箱跳过: {e}")

            if target_push_path:
                try:
                    subprocess.run(["ssh", Config.NAS_SSH_HOST, f"cp \"{remote_inbox_path}\" \"{target_push_path}\" && chmod 666 \"{target_push_path}\""], check=True)
                    print(f"[+] 已同步至网盘目录: {target_push_path}")
                except Exception:
                    pass

            # 触发 Calibre 命令行直接入库
            try:
                cmd = ["ssh", Config.NAS_SSH_HOST, f"/var/packages/ContainerManager/target/usr/bin/docker exec calibre-web calibredb add \"/inbox/{file_name}\" --with-library \"/books\""]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print("[+] 已触发 Calibre 库容刷新！")
            except Exception:
                pass
        else:
            if target_push_path:
                try:
                    subprocess.run(["ssh", Config.NAS_SSH_HOST, f"cp \"{epub_path}\" \"{target_push_path}\" && chmod 666 \"{target_push_path}\""], check=True)
                    print(f"[+] 已同步副本至网盘目录: {target_push_path}")
                except Exception:
                    pass
        return True

    # 2. 本地 / Docker 目录模式
    if Config.NAS_INBOX_DIR and os.path.exists(Config.NAS_INBOX_DIR):
        try:
            shutil.copy2(epub_path, Path(Config.NAS_INBOX_DIR) / f"{clean_title}.epub")
            print(f"[+] 本地已归档至收件箱目录")
        except Exception:
            pass

    if Config.NAS_PUSH_DIR and os.path.exists(Config.NAS_PUSH_DIR):
        try:
            shutil.copy2(epub_path, Path(Config.NAS_PUSH_DIR) / f"{clean_title}.epub")
            print(f"[+] 本地已归档至推送目录")
        except Exception:
            pass

    return True
