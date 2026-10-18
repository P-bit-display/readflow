from abc import ABC, abstractmethod
from typing import List
from src.models import BookIntent

class BaseWatcher(ABC):
    """意图捕获源抽象基类"""
    
    @abstractmethod
    def fetch_wishes(self) -> List[BookIntent]:
        """抓取用户标记为想读的书单"""
        pass
