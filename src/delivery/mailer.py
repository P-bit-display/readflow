import os
from pathlib import Path
import smtplib
import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.header import Header
from email import encoders
from src.config import Config

MAX_ATTACH_SIZE = 24 * 1024 * 1024  # 24MB 阈值（避开 25MB Base64 膨胀超限）

class BookMailer:
    """静默邮件分发引擎：支持标准 SMTP 本地直发与群晖 NAS 远程协同发信，带 RFC 2047 规范编码"""

    @classmethod
    def send(cls, epub_path: str, book_title: str) -> bool:
        target = Config.TARGET_EMAIL
        if not target:
            print("[!] 未配置 TARGET_EMAIL，跳过邮件推送。")
            return False

        # 优先使用配置的标准 SMTP 发送
        if Config.SMTP_SERVER and Config.SMTP_USER and Config.SMTP_PASSWORD:
            return cls._send_local_smtp(epub_path, book_title, target)

        # 兼容群晖 NAS 远程发信（若配置了 NAS_SSH_HOST）
        if Config.NAS_SSH_HOST:
            return cls._send_via_nas(epub_path, book_title, target)

        print("[!] 尚未配置 SMTP 凭据或 NAS 发信通道，跳过邮件发送。")
        return False

    @staticmethod
    def _send_local_smtp(epub_path: str, book_title: str, target: str) -> bool:
        if not os.path.exists(epub_path):
            print(f"[!] 待发送文件不存在: {epub_path}")
            return False

        file_size = os.path.getsize(epub_path)
        msg = MIMEMultipart()
        msg["From"] = Config.SMTP_USER
        msg["To"] = target
        msg["Subject"] = Header(f"【ReadFlow 图书推送】《{book_title}》", "utf-8").encode()

        if file_size > MAX_ATTACH_SIZE:
            size_mb = file_size / (1024 * 1024)
            body = (
                f"你好！您想读的书籍《{book_title}》已准备就绪并完成入库。\n\n"
                f"⚠️ 提示：该书体积为 {size_mb:.1f} MB（超出邮箱附件 25MB 上限），已存入您的本地/私有云书库。\n"
                f"请在阅读器网盘或本地目录直接开读。"
            )
            msg.attach(MIMEText(body, "plain", "utf-8"))
        else:
            body = f"你好！您想读的书籍《{book_title}》已准备就绪，附件为最新 EPUB 版本，请在阅读设备查收。"
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with open(epub_path, "rb") as f:
                part = MIMEBase("application", "epub+zip")
                part.set_payload(f.read())
            encoders.encode_base64(part)

            # 遵循 RFC 2047 双重编码，彻底解决中文附件名在 163/QQ/Kindle/汉王显示为 noname
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

            print(f"[+] 邮件已成功发送至 {target}！")
            return True
        except Exception as e:
            print(f"[!] SMTP 邮件发送失败: {e}")
            return False

    @staticmethod
    def _send_via_nas(epub_path: str, book_title: str, target: str) -> bool:
        # 如果 epub_path 是本地文件，先传到 NAS 临时目录发信
        remote_path = epub_path
        if not epub_path.startswith("/volume1"):
            file_name = os.path.basename(epub_path)
            remote_path = f"/tmp/{file_name}"
            try:
                with open(epub_path, "rb") as f:
                    subprocess.run(
                        ["ssh", Config.NAS_SSH_HOST, f"cat > \"{remote_path}\""],
                        input=f.read(),
                        check=True
                    )
            except Exception as e:
                print(f"[!] 上传发信临时文件失败: {e}")
                return False

        remote_script = os.getenv("NAS_MAILER_SCRIPT")
        if not remote_script:
            if Config.NAS_CALIBRE_ROOT:
                remote_script = str(Path(Config.NAS_CALIBRE_ROOT).parent / "send_book_mail.py")
            else:
                remote_script = "~/Books/send_book_mail.py"

        cmd = [
            "ssh", Config.NAS_SSH_HOST,
            f"python3 \"{remote_script}\" \"{remote_path}\" \"{book_title}\" \"{target}\""
        ]
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
