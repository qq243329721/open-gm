"""
缓存管理系统模块

提供多种缓存失效策略支持的线程安全缓存管理器。
"""

import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generic, Optional, TypeVar

T = TypeVar('T')


class CacheEntry(Generic[T]):
    """缓存条目

    Attributes:
        key: 缓存键
        value: 缓存值
        created_at: 创建时间戳
        invalidation_strategy: 失效策略
    """

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
        """检查缓存条目是否仍然有效"""
        return self.invalidation_strategy.is_valid(self)

    def access(self) -> None:
        """记录访问"""
        self.access_count += 1
        self.last_accessed = time.time()


class CacheInvalidationStrategy(ABC):
    """缓存失效策略基类"""

    @abstractmethod
    def is_valid(self, entry: CacheEntry) -> bool:
        """检查缓存条目是否有效

        Args:
            entry: 要检查的缓存条目

        Returns:
            True 如果缓存仍然有效，False 如果已失效
        """
        pass


class TTLInvalidationStrategy(CacheInvalidationStrategy):
    """基于 TTL (Time To Live) 的失效策略

    在指定的时间内缓存有效，超时后失效。
    """

    def __init__(self, ttl_seconds: float):
        """初始化 TTL 策略

        Args:
            ttl_seconds: 缓存的生存时间（秒）
        """
        if ttl_seconds <= 0:
            raise ValueError("TTL 必须大于 0")
        self.ttl_seconds = ttl_seconds

    def is_valid(self, entry: CacheEntry) -> bool:
        """检查缓存是否超时"""
        elapsed = time.time() - entry.created_at
        return elapsed < self.ttl_seconds


class FileModificationInvalidationStrategy(CacheInvalidationStrategy):
    """基于文件修改时间的失效策略

    当文件被修改时，基于该文件的缓存失效。
    """

    def __init__(self, file_path: Path):
        """初始化文件修改策略

        Args:
            file_path: 要监视的文件路径
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        self.last_known_mtime = self.file_path.stat().st_mtime

    def is_valid(self, entry: CacheEntry) -> bool:
        """检查文件是否被修改"""
        if not self.file_path.exists():
            return False

        current_mtime = self.file_path.stat().st_mtime
        return current_mtime == self.last_known_mtime


class LRUCacheManager(Generic[T]):
    """线程安全的 LRU 缓存管理器

    支持多个缓存类型，使用 LRU (Least Recently Used) 策略进行淘汰。

    Attributes:
        max_size: 缓存的最大条目数
    """

    def __init__(self, max_size: int = 100):
        """初始化缓存管理器

        Args:
            max_size: 缓存的最大条目数，默认 100
        """
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
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            strategy: 失效策略
        """
        with self._lock:
            # 删除无效的缓存条目
            self._evict_invalid_entries()

            # 如果已存在，先删除旧的
            if key in self._cache:
                del self._cache[key]

            # 如果缓存已满，删除最少使用的条目
            if len(self._cache) >= self.max_size:
                self._evict_lru()

            # 添加新条目
            entry = CacheEntry(key, value, strategy)
            self._cache[key] = entry

    def get(self, key: str) -> Optional[T]:
        """获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，或 None 如果缓存不存在或已失效
        """
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # 检查缓存是否有效
            if not entry.is_valid():
                del self._cache[key]
                return None

            # 记录访问
            entry.access()
            return entry.value

    def delete(self, key: str) -> bool:
        """删除缓存

        Args:
            key: 缓存键

        Returns:
            True 如果缓存存在且被删除，False 如果缓存不存在
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()

    def exists(self, key: str) -> bool:
        """检查缓存是否存在且有效

        Args:
            key: 缓存键

        Returns:
            True 如果缓存存在且有效，False 否则
        """
        with self._lock:
            if key not in self._cache:
                return False

            entry = self._cache[key]
            if not entry.is_valid():
                del self._cache[key]
                return False

            return True

    def size(self) -> int:
        """获取当前缓存数量"""
        with self._lock:
            return len(self._cache)

    def _evict_invalid_entries(self) -> None:
        """删除所有无效的缓存条目"""
        invalid_keys = [
            key for key, entry in self._cache.items()
            if not entry.is_valid()
        ]
        for key in invalid_keys:
            del self._cache[key]

    def _evict_lru(self) -> None:
        """删除最少使用的缓存条目"""
        if not self._cache:
            return

        # 找到最少使用的条目（访问次数最少，最后访问时间最早）
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (
                self._cache[k].access_count,
                self._cache[k].last_accessed
            )
        )
        del self._cache[lru_key]


class CacheManager:
    """全局缓存管理器

    支持配置多个不同的缓存存储，每个都使用不同的失效策略。
    """

    def __init__(self):
        """初始化全局缓存管理器"""
        self._caches: Dict[str, LRUCacheManager] = {}
        self._lock = threading.RLock()
        self._init_default_caches()

    def _init_default_caches(self) -> None:
        """初始化默认的缓存存储"""
        # worktree_info: 5 分钟 TTL
        self._caches['worktree_info'] = LRUCacheManager(max_size=100)

        # symlink_validity: 1 分钟 TTL
        self._caches['symlink_validity'] = LRUCacheManager(max_size=50)

        # git_status: 2 分钟 TTL
        self._caches['git_status'] = LRUCacheManager(max_size=100)

    def register_cache(self, name: str, max_size: int = 100) -> None:
        """注册一个新的缓存存储

        Args:
            name: 缓存存储的名称
            max_size: 缓存的最大条目数
        """
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
        """设置缓存值

        Args:
            cache_name: 缓存存储的名称
            key: 缓存键
            value: 缓存值
            strategy: 失效策略
        """
        with self._lock:
            if cache_name not in self._caches:
                self.register_cache(cache_name)
            self._caches[cache_name].set(key, value, strategy)

    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """获取缓存值

        Args:
            cache_name: 缓存存储的名称
            key: 缓存键

        Returns:
            缓存值，或 None 如果缓存不存在或已失效
        """
        with self._lock:
            if cache_name not in self._caches:
                return None
            return self._caches[cache_name].get(key)

    def delete(self, cache_name: str, key: str) -> bool:
        """删除缓存

        Args:
            cache_name: 缓存存储的名称
            key: 缓存键

        Returns:
            True 如果缓存存在且被删除，False 如果缓存不存在
        """
        with self._lock:
            if cache_name not in self._caches:
                return False
            return self._caches[cache_name].delete(key)

    def clear(self, cache_name: str = None) -> None:
        """清空缓存

        Args:
            cache_name: 缓存存储的名称，如果为 None 则清空所有缓存
        """
        with self._lock:
            if cache_name is None:
                for cache in self._caches.values():
                    cache.clear()
            elif cache_name in self._caches:
                self._caches[cache_name].clear()

    def exists(self, cache_name: str, key: str) -> bool:
        """检查缓存是否存在且有效

        Args:
            cache_name: 缓存存储的名称
            key: 缓存键

        Returns:
            True 如果缓存存在且有效，False 否则
        """
        with self._lock:
            if cache_name not in self._caches:
                return False
            return self._caches[cache_name].exists(key)

    def get_cache_info(self, cache_name: str) -> Optional[Dict[str, int]]:
        """获取缓存存储的信息

        Args:
            cache_name: 缓存存储的名称

        Returns:
            包含 size 和 max_size 的字典，或 None 如果缓存存储不存在
        """
        with self._lock:
            if cache_name not in self._caches:
                return None
            cache = self._caches[cache_name]
            return {
                'size': cache.size(),
                'max_size': cache.max_size
            }

    def get_all_cache_names(self) -> list:
        """获取所有缓存存储的名称

        Returns:
            缓存存储名称的列表
        """
        with self._lock:
            return list(self._caches.keys())


# 全局缓存管理器实例
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例

    Returns:
        全局 CacheManager 实例
    """
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager()
    return _global_cache_manager
