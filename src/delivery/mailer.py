import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.header import Header
from email import encoders
from src.config import Config

# 大多数邮件服务器的附件最大安全限制 (24MB)
MAX_ATTACHMENT_SIZE = 24 * 1024 * 1024

class BookMailer:
    """电子书邮件分发引擎 (带 RFC 2047 中文编码)"""

    @staticmethod
    def send(file_path: str, book_title: str) -> bool:
        target = Config.TARGET_EMAIL
        if not target or not Config.SMTP_USER or not Config.SMTP_PASSWORD:
            print("[!] 邮件配置不完整，跳过发送")
            return False

        if not os.path.exists(file_path):
            print(f"[!] 附件文件不存在: {file_path}")
            return False

        file_size = os.path.getsize(file_path)
        if file_size > MAX_ATTACHMENT_SIZE:
            print(f"[!] 警告: 文件体积 ({file_size / 1024 / 1024:.2f}MB) 超过邮件上限，转为纯文本提示邮件")
            return BookMailer._send_oversize_notice(book_title, target)

        print(f"[*] 正在将《{book_title}》发送至 {target} ...")
        msg = MIMEMultipart()
        msg["From"] = Config.SMTP_USER
        msg["To"] = target
        msg["Subject"] = Header(f"【ReadFlow】《{book_title}》", "utf-8").encode()

        body = (
            f"你好！您标记想读的书籍《{book_title}》已准备就绪。\n\n"
            f"• 附件为 EPUB 正式版本，在电纸书（汉王/Kindle）或手机上点开附件即可自动加入书架开读。\n"
            f"• 该书籍已同步保存至您的私有 Calibre 藏书库中。"
        )
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with open(file_path, "rb") as f:
            part = MIMEBase("application", "epub+zip")
            part.set_payload(f.read())
        encoders.encode_base64(part)

        # RFC 2047 规范编码，解决 163/QQ 邮箱 noname 乱码
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

    @staticmethod
    def _send_oversize_notice(book_title: str, target: str) -> bool:
        try:
            msg = MIMEText(
                f"您想读的《{book_title}》已成功下载并归档，但由于文件体积大于 25MB 超出邮件服务器限制，"
                f"请直接在您的 Calibre-Web 或本地网盘中下载开读。", 
                "plain", "utf-8"
            )
            msg["From"] = Config.SMTP_USER
            msg["To"] = target
            msg["Subject"] = Header(f"【超大附件提醒】《{book_title}》已入库", "utf-8").encode()
            with smtplib.SMTP_SSL(Config.SMTP_SERVER, Config.SMTP_PORT, timeout=20) as server:
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                server.sendmail(Config.SMTP_USER, [target], msg.as_string())
            return True
        except Exception:
            return False
