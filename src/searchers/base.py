from abc import ABC, abstractmethod
from typing import Optional
from src.models import BookIntent

class BaseSearcher(ABC):
    """图书检索与下载源基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def search_and_download(self, intent: BookIntent) -> Optional[str]:
        """
        根据阅读意图检索并下载 EPUB 文件
        成功返回本地 EPUB 文件绝对路径，失败返回 None
        """
        pass
