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
        """清洗书名，去除副标题符号与书名号"""
        t = self.title.replace("《", "").replace("》", "").strip()
        # 去除常见副标题破折号之后的部分（用于提升搜索宽容度）
        return t

    def __str__(self):
        auth_info = f" - {self.author}" if self.author else ""
        isbn_info = f" (ISBN: {self.isbn})" if self.isbn else ""
        return f"《{self.clean_title}》{auth_info}{isbn_info} [{self.source}]"
