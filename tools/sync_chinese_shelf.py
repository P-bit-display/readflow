#!/usr/bin/env python3
"""
sync_chinese_shelf.py
---------------------
为 Calibre 书库生成零风险、零额外占用空间的「中文分类书架」（基于 Btrfs/Linux 硬链接 Hardlink）。

特性：
1. 0 额外磁盘占用：基于 os.link (Inode 硬链接)，不复制实际文件数据。
2. 0 风险：完全不修改 00-Calibre 底层文件及 metadata.db，Calibre/Calibre-Web 正常运作。
3. 纯正中文：按「作者/书名.epub」生成清晰规范的中文目录树，便于 Finder、SMB、网盘直读。
4. 智能增量：已链接且未变动的文件瞬间跳过；支持安全字符过滤与长文件名防溢出。
"""

import os
import sys
import sqlite3
import re
import argparse
import time

def sanitize(name: str) -> str:
    """过滤操作系统保留与非法字符"""
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    return name.strip('. ')

def utf8_truncate(s: str, max_bytes: int = 150) -> str:
    """安全截断 UTF-8 字符串，确保不切断多字节汉字"""
    encoded = s.encode('utf-8')
    if len(encoded) <= max_bytes:
        return s
    truncated = encoded[:max_bytes]
    return truncated.decode('utf-8', errors='ignore').rstrip()

def build_shelf(calibre_dir: str, shelf_dir: str, dry_run: bool = False):
    db_path = os.path.join(calibre_dir, 'metadata.db')
    if not os.path.exists(db_path):
        print(f"错误: 找不到 Calibre 数据库: {db_path}")
        sys.exit(1)

    print(f"正在读取 Calibre 数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute('''
        SELECT b.id, b.title, b.path, d.format, d.name,
               coalesce((SELECT group_concat(a.name, ', ') 
                         FROM books_authors_link bal 
                         JOIN authors a ON bal.author = a.id 
                         WHERE bal.book = b.id), '未知作者') as author
        FROM books b
        JOIN data d ON b.id = d.book
        WHERE d.format IN ('EPUB', 'PDF', 'MOBI', 'AZW3')
    ''')
    books = cur.fetchall()
    total = len(books)
    print(f"共发现有效电子书文件: {total} 本")

    if not dry_run:
        os.makedirs(shelf_dir, exist_ok=True)

    created = 0
    skipped = 0
    conflicts = 0
    errors = 0
    seen_paths = set()

    start_time = time.time()

    for idx, (bid, title, rel_path, fmt, fname, author) in enumerate(books, 1):
        ext = fmt.lower()
        src_file = os.path.join(calibre_dir, rel_path, f"{fname}.{ext}")

        if not os.path.exists(src_file):
            errors += 1
            continue

        safe_author = utf8_truncate(sanitize(author), 80) or '未知作者'
        safe_title = utf8_truncate(sanitize(title), 120) or f'无题_{bid}'
        
        target_author_dir = os.path.join(shelf_dir, safe_author)
        target_filename = f"{safe_title}.{ext}"
        target_path = os.path.join(target_author_dir, target_filename)

        # 解决同作者同名书重名冲突
        if target_path in seen_paths:
            conflicts += 1
            target_filename = f"{safe_title}_({bid}).{ext}"
            target_path = os.path.join(target_author_dir, target_filename)
        seen_paths.add(target_path)

        if dry_run:
            if idx <= 10:
                print(f"[DRY-RUN] {src_file} -> {target_path}")
            continue

        os.makedirs(target_author_dir, exist_ok=True)

        # 检查是否已是同一个硬链接
        if os.path.exists(target_path):
            try:
                s_src = os.stat(src_file)
                s_dst = os.stat(target_path)
                if s_src.st_ino == s_dst.st_ino:
                    skipped += 1
                    continue
                else:
                    # 存在同名不同文件，更新或者重命名
                    target_filename = f"{safe_title}_({bid}).{ext}"
                    target_path = os.path.join(target_author_dir, target_filename)
                    if os.path.exists(target_path) and os.stat(src_file).st_ino == os.stat(target_path).st_ino:
                        skipped += 1
                        continue
            except OSError:
                pass

        try:
            if os.path.exists(target_path):
                os.remove(target_path)
            os.link(src_file, target_path)
            created += 1
        except OSError as e:
            print(f"硬链接创建失败: {src_file} -> {target_path}, 错误: {e}")
            errors += 1

        if idx % 5000 == 0:
            elapsed = time.time() - start_time
            print(f"进度: {idx}/{total} ({idx/total*100:.1f}%) | 已创建: {created}, 已跳过: {skipped}, 耗时: {elapsed:.1f}s")

    elapsed = time.time() - start_time
    print("\n" + "="*50)
    print("🎉 中文分类书架同步完成！")
    print(f"• 总书目: {total}")
    print(f"• 新增硬链接: {created}")
    print(f"• 保持原有(增量): {skipped}")
    print(f"• 同名重名消歧: {conflicts}")
    print(f"• 异常/缺失: {errors}")
    print(f"• 总耗时: {elapsed:.2f} 秒")
    print(f"• 书架路径: {shelf_dir}")
    print("="*50)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="为 Calibre 构建纯中文硬链接书架")
    parser.add_argument('--calibre-dir', default='/volume1/homes/placid/Books/00-Calibre', help='Calibre 库根目录')
    parser.add_argument('--shelf-dir', default='/volume1/homes/placid/Books/中文书架', help='中文书架输出目录')
    parser.add_argument('--dry-run', action='store_true', help='试运行，不产生实际文件修改')
    args = parser.parse_args()

    build_shelf(args.calibre_dir, args.shelf_dir, dry_run=args.dry_run)
