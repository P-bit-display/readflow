import os
import shutil
import subprocess
from pathlib import Path
from src.config import Config

class CalibreIngester:
    """Calibre 资产归档与网盘分发：支持远程群晖 NAS 与本地/Docker 书库目录"""

    @staticmethod
    def ingest(epub_path: str, book_title: str) -> bool:
        if not epub_path:
            return False

        clean_title = book_title.replace("/", "_").replace("\\", "_")
        file_name = os.path.basename(epub_path)

        # 场景 A: 远程群晖 NAS 归档模式 (配置了 NAS_SSH_HOST)
        if Config.NAS_SSH_HOST:
            target_push_path = f"{Config.NAS_PUSH_DIR}/{clean_title}.epub" if Config.NAS_PUSH_DIR else ""
            if not epub_path.startswith("/volume1"):
                remote_inbox_path = f"{Config.NAS_INBOX_DIR}/{file_name}" if Config.NAS_INBOX_DIR else f"/tmp/{file_name}"
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

                if target_push_path:
                    try:
                        cmd = ["ssh", Config.NAS_SSH_HOST, f"cp \"{remote_inbox_path}\" \"{target_push_path}\" && chmod 666 \"{target_push_path}\""]
                        subprocess.run(cmd, check=True)
                        print(f"[+] 已同步至网盘目录: {target_push_path}")
                    except Exception as e:
                        print(f"[*] 拷贝至网盘目录跳过: {e}")

                # 触发 Calibre 命令行入库 (若配置)
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
                # 书本已在 NAS 上
                if target_push_path:
                    try:
                        cmd = ["ssh", Config.NAS_SSH_HOST, f"cp \"{epub_path}\" \"{target_push_path}\" && chmod 666 \"{target_push_path}\""]
                        subprocess.run(cmd, check=True)
                        print(f"[+] 已同步副本至网盘目录: {target_push_path}")
                    except Exception as e:
                        print(f"[*] 拷贝至网盘目录跳过: {e}")
            return True

        # 场景 B: 本地/Docker 目录归档模式 (未配置 NAS_SSH_HOST，直接本地复制到 INBOX / PUSH 目录)
        if Config.NAS_INBOX_DIR and os.path.exists(Config.NAS_INBOX_DIR):
            try:
                dest = Path(Config.NAS_INBOX_DIR) / f"{clean_title}.epub"
                shutil.copy2(epub_path, dest)
                print(f"[+] 本地已归档至收件箱: {dest}")
            except Exception as e:
                print(f"[!] 本地收件箱归档跳过: {e}")

        if Config.NAS_PUSH_DIR and os.path.exists(Config.NAS_PUSH_DIR):
            try:
                dest = Path(Config.NAS_PUSH_DIR) / f"{clean_title}.epub"
                shutil.copy2(epub_path, dest)
                print(f"[+] 本地已归档至推送目录: {dest}")
            except Exception as e:
                print(f"[!] 本地推送目录归档跳过: {e}")

        return True
