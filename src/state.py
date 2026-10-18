import time
from typing import Optional, Dict, Any

class SystemState:
    """ReadFlow 全局运行时状态管理"""
    is_syncing: bool = False
    current_book: Optional[str] = None
    current_step: Optional[str] = None
    step_detail: Optional[str] = None
    last_sync_time: float = time.time()
    next_sync_time: float = time.time() + 600
    start_time: float = time.time()
    calibre_count_cache: int = 23945
    last_calibre_check: float = 0

    @classmethod
    def set_active_task(cls, book_name: Optional[str], step: Optional[str], detail: Optional[str] = None):
        cls.current_book = book_name
        cls.current_step = step
        cls.step_detail = detail

    @classmethod
    def clear_active_task(cls):
        cls.current_book = None
        cls.current_step = None
        cls.step_detail = None

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        now = time.time()
        countdown = max(0, int(cls.next_sync_time - now)) if not cls.is_syncing else 0
        return {
            "is_syncing": cls.is_syncing,
            "current_book": cls.current_book,
            "current_step": cls.current_step,
            "step_detail": cls.step_detail,
            "last_sync_time": int(cls.last_sync_time),
            "next_sync_time": int(cls.next_sync_time),
            "countdown_seconds": countdown,
            "uptime_seconds": int(now - cls.start_time),
            "calibre_total": cls.calibre_count_cache
        }
