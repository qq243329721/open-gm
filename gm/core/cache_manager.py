"""缓存管理器实现

提供内存缓存机制，支持多种淘汰策略（TTL, 文件修改时间, LRU 等）。"""

import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generic, Optional, TypeVar

T = TypeVar('T')


class CacheEntry(Generic[T]):
    """缓存条目包装器"""

    def __init__(
        self,
        key: str,
        value: T,
        invalidation_strategy: 'CacheInvalidationStrategy'
    ):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.invalidation_strategy = invalidation_strategy
        self.access_count = 0
        self.last_accessed = self.created_at

    def is_valid(self) -> bool:
        """检查条目是否依然有效"""
        return self.invalidation_strategy.is_valid(self)

    def access(self) -> None:
        """记录访问记录"""
        self.access_count += 1
        self.last_accessed = time.time()


class CacheInvalidationStrategy(ABC):
    """缓存失效策略接口"""

    @abstractmethod
    def is_valid(self, entry: CacheEntry) -> bool:
        """判断条目是否有效"""
        pass


class TTLInvalidationStrategy(CacheInvalidationStrategy):
    """基于生存时间 (Time To Live) 的失效策略"""

    def __init__(self, ttl_seconds: float):
        if ttl_seconds <= 0:
            raise ValueError("TTL 必须大于 0")
        self.ttl_seconds = ttl_seconds

    def is_valid(self, entry: CacheEntry) -> bool:
        elapsed = time.time() - entry.created_at
        return elapsed < self.ttl_seconds


class FileModificationInvalidationStrategy(CacheInvalidationStrategy):
    """基于文件修改时间的失效策略（当源文件改变时缓存失效）"""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        self.last_known_mtime = self.file_path.stat().st_mtime

    def is_valid(self, entry: CacheEntry) -> bool:
        if not self.file_path.exists():
            return False
        current_mtime = self.file_path.stat().st_mtime
        return current_mtime == self.last_known_mtime


class LRUCacheManager(Generic[T]):
    """LRU (最近最少使用) 缓存管理器"""

    def __init__(self, max_size: int = 100):
        if max_size <= 0:
            raise ValueError("max_size 必须大于 0")
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

    def set(
        self,
        key: str,
        value: T,
        strategy: CacheInvalidationStrategy
    ) -> None:
        """存入缓存"""
        with self._lock:
            # 清理无效条目
            self._evict_invalid_entries()

            # 如果已存在，先删除（用于更新位置）
            if key in self._cache:
                del self._cache[key]

            # 空间检查
            if len(self._cache) >= self.max_size:
                self._evict_lru()

            self._cache[key] = CacheEntry(key, value, strategy)

    def get(self, key: str) -> Optional[T]:
        """获取缓存"""
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            if not entry.is_valid():
                del self._cache[key]
                return None

            entry.access()
            return entry.value

    def delete(self, key: str) -> bool:
        """删除指定键的缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()

    def exists(self, key: str) -> bool:
        """检查是否存在有效缓存"""
        with self._lock:
            if key not in self._cache:
                return False
            entry = self._cache[key]
            if not entry.is_valid():
                del self._cache[key]
                return False
            return True

    def _evict_invalid_entries(self) -> None:
        """驱逐所有由于策略失效的条目"""
        invalid_keys = [
            key for key, entry in self._cache.items()
            if not entry.is_valid()
        ]
        for key in invalid_keys:
            del self._cache[key]

    def _evict_lru(self) -> None:
        """根据访问频率和时间驱逐最不常用的条目"""
        if not self._cache:
            return
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (
                self._cache[k].access_count,
                self._cache[k].last_accessed
            )
        )
        del self._cache[lru_key]


class CacheManager:
    """顶级缓存协调器"""

    def __init__(self):
        self._caches: Dict[str, LRUCacheManager] = {}
        self._lock = threading.RLock()
        self._init_default_caches()

    def _init_default_caches(self) -> None:
        """初始化内置常用缓存"""
        self._caches['worktree_info'] = LRUCacheManager(max_size=100)
        self._caches['symlink_validity'] = LRUCacheManager(max_size=50)
        self._caches['git_status'] = LRUCacheManager(max_size=100)

    def register_cache(self, name: str, max_size: int = 100) -> None:
        """注册新的命名缓存"""
        with self._lock:
            if name not in self._caches:
                self._caches[name] = LRUCacheManager(max_size=max_size)

    def set(
        self,
        cache_name: str,
        key: str,
        value: Any,
        strategy: CacheInvalidationStrategy
    ) -> None:
        """设置命名缓存的值"""
        with self._lock:
            if cache_name not in self._caches:
                self.register_cache(cache_name)
            self._caches[cache_name].set(key, value, strategy)

    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """获取命名缓存的值"""
        with self._lock:
            if cache_name not in self._caches:
                return None
            return self._caches[cache_name].get(key)


_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """获取单例缓存管理器"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager()
    return _global_cache_manager
