"""Hook 管理系统

提供事件钩子注册和触发机制。"""

from collections import defaultdict
from typing import Callable, Dict, List, Any

from gm.core.logger import get_logger

logger = get_logger("hook_manager")


class HookManager:
    """钩子管理器"""
    
    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)

    def register_hook(self, event: str, callback: Callable) -> None:
        """注册钩子回调"""
        self._hooks[event].append(callback)
        logger.debug(f"Hook registered: {event}")
    
    def trigger_hook(self, event: str, *args, **kwargs) -> None:
        """触发钩子"""
        callbacks = self._hooks.get(event, [])
        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook execution failed for {event}: {e}")

    def emit_hook(self, event: str, *args, **kwargs) -> None:
        """触发钩子（别名）"""
        self.trigger_hook(event, *args, **kwargs)


class WorktreeEvents:
    """Worktree 相关事件定义"""
    BEFORE_CREATE = "worktree.before_create"
    AFTER_CREATE = "worktree.after_create"
    BEFORE_REMOVE = "worktree.before_remove"
    AFTER_REMOVE = "worktree.after_remove"
    BEFORE_SYNC = "worktree.before_sync"
    AFTER_SYNC = "worktree.after_sync"
    STATUS_CHANGED = "worktree.status_changed"
