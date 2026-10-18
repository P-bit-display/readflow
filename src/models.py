import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class BookIntent:
    """标准图书阅读意图实体"""
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    source: str = "douban"  # douban / goodreads
    source_url: Optional[str] = None

    @property
    def clean_title(self) -> str:
        """清洗书名，去除特殊书名号与文件名非法字符"""
        t = self.title.replace("《", "").replace("》", "").strip()
        t = re.sub(r'[\\/*?:"<>|]', "", t).strip()
        return t

    @property
    def base_title(self) -> str:
        """提取核心主书名（去除系列后缀、副标题、括号说明），用于高鲁棒性查重与模糊搜索"""
        t = self.clean_title
        # 去除 (The Empyrean, #3.5) 或 （原书第3版） 等括号附加信息
        t = re.sub(r'[\(（].*?[\)）]', '', t).strip()
        # 去除常见副标题分隔符
        for sep in [':', '：', '——', ' - ']:
            if sep in t:
                parts = t.split(sep)
                if parts[0].strip():
                    t = parts[0].strip()
                    break
        return t if t else self.clean_title

    def __str__(self):
        auth_info = f" - {self.author}" if self.author else ""
        isbn_info = f" (ISBN: {self.isbn})" if self.isbn else ""
        return f"《{self.clean_title}》{auth_info}{isbn_info} [{self.source}]"
