import os
import smtplib
import json
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.header import Header
from email import encoders
from src.config import Config

# 大多数邮件服务器的附件最大安全限制 (25MB)
MAX_ATTACHMENT_SIZE = 24 * 1024 * 1024

def send_book_email(file_path: str, book_title: str, recipient_email: str = None) -> bool:
    """
    通过 SMTP 发送带 EPUB 附件的邮件。
    使用 RFC 2047 Base64 编码，彻底解决网易 163、QQ 邮箱等将中文附件显示为 noname 的问题。
    """
    target = recipient_email or Config.TARGET_EMAIL
    if not target or not Config.SMTP_USER or not Config.SMTP_PASSWORD:
        print("[!] 邮件配置不完整，跳过发送")
        return False

    if not os.path.exists(file_path):
        print(f"[!] 附件文件不存在: {file_path}")
        return False

    file_size = os.path.getsize(file_path)
    if file_size > MAX_ATTACHMENT_SIZE:
        print(f"[!] 警告: 文件体积 ({file_size / 1024 / 1024:.2f}MB) 超过邮件上限，转为纯文本提示")
        # 发送超限纯文本通知
        return _send_oversize_notice(book_title, target)

    print(f"[*] 正在将《{book_title}》发送至 {target} ...")
    msg = MIMEMultipart()
    msg["From"] = Config.SMTP_USER
    msg["To"] = target
    msg["Subject"] = Header(f"【Douban2Reader 图书推送】《{book_title}》", "utf-8").encode()

    body = f"你好！您在豆瓣标记想读的书籍《{book_title}》已准备就绪，附件为 EPUB 版本，请在阅读设备查收。"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # 打包附件并做兼容性编码
    with open(file_path, "rb") as f:
        part = MIMEBase("application", "epub+zip")
        part.set_payload(f.read())
    encoders.encode_base64(part)

    basename = os.path.basename(file_path)
    encoded_name = Header(basename, "utf-8").encode()
    part.add_header("Content-Disposition", f'attachment; filename="{encoded_name}"')
    part.add_header("Content-Type", "application/epub+zip", name=("utf-8", "", basename))
    msg.attach(part)

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

        print(f"[+] 邮件已成功发送至 {target}！")
        return True
    except Exception as e:
        print(f"[!] 邮件发送失败: {e}")
        return False


def _send_oversize_notice(book_title: str, target: str):
    try:
        msg = MIMEText(f"您想读的《{book_title}》已下载完成，但由于体积大于 25MB，无法通过邮件发送，已存入您的本地/NAS 书库目录中。", "plain", "utf-8")
        msg["From"] = Config.SMTP_USER
        msg["To"] = target
        msg["Subject"] = Header(f"【文件过大提醒】《{book_title}》", "utf-8").encode()
        with smtplib.SMTP_SSL(Config.SMTP_SERVER, Config.SMTP_PORT, timeout=20) as server:
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.sendmail(Config.SMTP_USER, [target], msg.as_string())
        return True
    except Exception:
        return False


def notify_telegram(message: str):
    """向配置的 Telegram 群组/私聊推送运行通知"""
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return

    try:
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = json.dumps({"chat_id": Config.TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[*] Telegram 通知发送失败: {e}")
