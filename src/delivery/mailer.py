import os
import subprocess
from src.config import Config

class BookMailer:
    """静默邮件分发引擎：通过群晖 NAS 走 Gmail 465 SSL 极速发信，彻底解决 noname 乱码"""

    @staticmethod
    def send(epub_path: str, book_title: str) -> bool:
        target = Config.TARGET_EMAIL
        if not target:
            return False

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

        print(f"[*] 正在通过 NAS Gmail SMTP 将《{book_title}》发送至 {target} ...")
        cmd = [
            "ssh", Config.NAS_SSH_HOST,
            f"python3 /volume1/homes/placid/Books/send_book_mail.py \"{remote_path}\" \"{book_title}\" \"{target}\""
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
