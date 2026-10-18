import os
import subprocess
from pathlib import Path
from src.config import Config

class CalibreIngester:
    """Calibre 资产归档与网盘分发"""

    @staticmethod
    def ingest(epub_path: str, book_title: str) -> bool:
        if not epub_path:
            return False

        clean_title = book_title.replace("/", "_").replace("\\", "_")
        target_push_path = f"{Config.NAS_PUSH_DIR}/{clean_title}.epub"

        # 1. 如果 epub 是本地下载的新书，上传到 NAS inbox
        if not epub_path.startswith("/volume1"):
            file_name = os.path.basename(epub_path)
            remote_inbox_path = f"{Config.NAS_INBOX_DIR}/{file_name}"
            print(f"[*] 正在将新书《{clean_title}》上传至 NAS 入库收件箱...")
            try:
                with open(epub_path, "rb") as f:
                    subprocess.run(
                        ["ssh", Config.NAS_SSH_HOST, f"cat > \"{remote_inbox_path}\""],
                        input=f.read(),
                        check=True
                    )
                print(f"[+] 新书已上传至 NAS 收件箱: {remote_inbox_path}")
            except Exception as e:
                print(f"[!] 上传 NAS 收件箱失败: {e}")

            # 拷贝到汉王聚合网盘专用目录
            try:
                cmd = ["ssh", Config.NAS_SSH_HOST, f"cp \"{remote_inbox_path}\" \"{target_push_path}\" && chmod 666 \"{target_push_path}\""]
                subprocess.run(cmd, check=True)
                print(f"[+] 已同步至汉王聚合网盘目录: {target_push_path}")
            except Exception as e:
                print(f"[*] 拷贝至网盘目录跳过: {e}")

            # 触发 Calibre 命令行入库
            try:
                add_cmd = [
                    "ssh", Config.NAS_SSH_HOST,
                    f"/var/packages/ContainerManager/target/usr/bin/docker exec calibre-web "
                    f"calibredb add \"/inbox/{file_name}\" --with-library \"/books\""
                ]
                subprocess.run(add_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print("[+] 已成功导入 Calibre 藏书库！")
            except Exception:
                pass

        else:
            # 书本已在 NAS 上，复制一份到汉王聚合网盘最新推送
            try:
                cmd = ["ssh", Config.NAS_SSH_HOST, f"cp \"{epub_path}\" \"{target_push_path}\" && chmod 666 \"{target_push_path}\""]
                subprocess.run(cmd, check=True)
                print(f"[+] 已同步副本至汉王聚合网盘目录: {target_push_path}")
            except Exception as e:
                print(f"[*] 拷贝至网盘目录跳过: {e}")

        return True
