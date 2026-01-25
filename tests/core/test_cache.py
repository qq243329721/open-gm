"""
缓存管理系统测试套件

测试 CacheEntry、CacheInvalidationStrategy 和 CacheManager 的功能。
"""

import time
import tempfile
import threading
from pathlib import Path

import pytest

from gm.core.cache_manager import (
    CacheEntry,
    TTLInvalidationStrategy,
    FileModificationInvalidationStrategy,
    LRUCacheManager,
    CacheManager,
    get_cache_manager,
)


class TestCacheEntry:
    """CacheEntry 类的单元测试"""

    def test_cache_entry_creation(self):
        """测试缓存条目创建"""
        strategy = TTLInvalidationStrategy(ttl_seconds=60)
        entry = CacheEntry(key="test_key", value="test_value", invalidation_strategy=strategy)

        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.access_count == 0
        assert entry.invalidation_strategy == strategy

    def test_cache_entry_access_tracking(self):
        """测试缓存条目访问跟踪"""
        strategy = TTLInvalidationStrategy(ttl_seconds=60)
        entry = CacheEntry(key="test", value="value", invalidation_strategy=strategy)

        assert entry.access_count == 0
        first_access_time = entry.last_accessed

        time.sleep(0.01)
        entry.access()

        assert entry.access_count == 1
        assert entry.last_accessed > first_access_time

        entry.access()
        assert entry.access_count == 2

    def test_cache_entry_is_valid_with_ttl(self):
        """测试 TTL 失效检查"""
        strategy = TTLInvalidationStrategy(ttl_seconds=0.1)
        entry = CacheEntry(key="test", value="value", invalidation_strategy=strategy)

        assert entry.is_valid()
        time.sleep(0.15)
        assert not entry.is_valid()

    def test_cache_entry_is_valid_with_file_modification(self, tmp_path):
        """测试文件修改失效检查"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("original")

        strategy = FileModificationInvalidationStrategy(file_path=test_file)
        entry = CacheEntry(key="test", value="value", invalidation_strategy=strategy)

        assert entry.is_valid()

        # 修改文件
        time.sleep(0.01)
        test_file.write_text("modified")

        assert not entry.is_valid()

    def test_cache_entry_file_deleted(self, tmp_path):
        """测试文件删除时缓存失效"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        strategy = FileModificationInvalidationStrategy(file_path=test_file)
        entry = CacheEntry(key="test", value="value", invalidation_strategy=strategy)

        assert entry.is_valid()

        test_file.unlink()
        assert not entry.is_valid()


class TestTTLInvalidationStrategy:
    """TTL 失效策略的单元测试"""

    def test_ttl_strategy_creation_with_valid_ttl(self):
        """测试创建有效的 TTL 策略"""
        strategy = TTLInvalidationStrategy(ttl_seconds=60)
        assert strategy.ttl_seconds == 60

    def test_ttl_strategy_creation_with_invalid_ttl(self):
        """测试创建无效 TTL 抛出异常"""
        with pytest.raises(ValueError):
            TTLInvalidationStrategy(ttl_seconds=0)

        with pytest.raises(ValueError):
            TTLInvalidationStrategy(ttl_seconds=-1)

    def test_ttl_strategy_is_valid(self):
        """测试 TTL 检查逻辑"""
        strategy = TTLInvalidationStrategy(ttl_seconds=0.05)
        entry = CacheEntry(key="test", value="value", invalidation_strategy=strategy)

        assert strategy.is_valid(entry)
        time.sleep(0.06)
        assert not strategy.is_valid(entry)


class TestFileModificationInvalidationStrategy:
    """文件修改失效策略的单元测试"""

    def test_file_modification_strategy_with_existing_file(self, tmp_path):
        """测试文件存在时策略创建"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        strategy = FileModificationInvalidationStrategy(file_path=test_file)
        assert strategy.file_path == test_file

    def test_file_modification_strategy_with_nonexistent_file(self, tmp_path):
        """测试文件不存在时抛出异常"""
        nonexistent_file = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            FileModificationInvalidationStrategy(file_path=nonexistent_file)

    def test_file_modification_detection(self, tmp_path):
        """测试文件修改检测"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("original")

        strategy = FileModificationInvalidationStrategy(file_path=test_file)
        entry = CacheEntry(key="test", value="value", invalidation_strategy=strategy)

        assert strategy.is_valid(entry)

        # 修改文件内容
        time.sleep(0.01)
        test_file.write_text("modified content")

        assert not strategy.is_valid(entry)


class TestLRUCacheManager:
    """LRU 缓存管理器的单元测试"""

    def test_lru_cache_creation_with_valid_size(self):
        """测试创建有效的 LRU 缓存"""
        cache = LRUCacheManager(max_size=100)
        assert cache.max_size == 100
        assert cache.size() == 0

    def test_lru_cache_creation_with_invalid_size(self):
        """测试创建无效大小的缓存抛出异常"""
        with pytest.raises(ValueError):
            LRUCacheManager(max_size=0)

        with pytest.raises(ValueError):
            LRUCacheManager(max_size=-1)

    def test_lru_cache_set_and_get(self):
        """测试缓存设置和获取"""
        cache = LRUCacheManager(max_size=10)
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        cache.set(key="test", value="value", strategy=strategy)
        assert cache.size() == 1
        assert cache.get("test") == "value"

    def test_lru_cache_get_nonexistent_key(self):
        """测试获取不存在的键"""
        cache = LRUCacheManager(max_size=10)
        assert cache.get("nonexistent") is None

    def test_lru_cache_get_expired_entry(self):
        """测试获取已过期的缓存"""
        cache = LRUCacheManager(max_size=10)
        strategy = TTLInvalidationStrategy(ttl_seconds=0.05)

        cache.set(key="test", value="value", strategy=strategy)
        assert cache.get("test") == "value"

        time.sleep(0.06)
        assert cache.get("test") is None

    def test_lru_cache_delete(self):
        """测试缓存删除"""
        cache = LRUCacheManager(max_size=10)
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        cache.set(key="test", value="value", strategy=strategy)
        assert cache.exists("test")

        assert cache.delete("test")
        assert not cache.exists("test")

    def test_lru_cache_delete_nonexistent_key(self):
        """测试删除不存在的键"""
        cache = LRUCacheManager(max_size=10)
        assert not cache.delete("nonexistent")

    def test_lru_cache_clear(self):
        """测试清空缓存"""
        cache = LRUCacheManager(max_size=10)
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        cache.set(key="key1", value="value1", strategy=strategy)
        cache.set(key="key2", value="value2", strategy=strategy)
        assert cache.size() == 2

        cache.clear()
        assert cache.size() == 0

    def test_lru_cache_exists(self):
        """测试缓存存在性检查"""
        cache = LRUCacheManager(max_size=10)
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        cache.set(key="test", value="value", strategy=strategy)
        assert cache.exists("test")
        assert not cache.exists("nonexistent")

    def test_lru_cache_exists_expired_entry(self):
        """测试过期缓存的存在性检查"""
        cache = LRUCacheManager(max_size=10)
        strategy = TTLInvalidationStrategy(ttl_seconds=0.05)

        cache.set(key="test", value="value", strategy=strategy)
        assert cache.exists("test")

        time.sleep(0.06)
        assert not cache.exists("test")

    def test_lru_cache_lru_eviction(self):
        """测试 LRU 淘汰机制"""
        cache = LRUCacheManager(max_size=3)
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        # 添加 3 个条目
        cache.set(key="key1", value="value1", strategy=strategy)
        cache.set(key="key2", value="value2", strategy=strategy)
        cache.set(key="key3", value="value3", strategy=strategy)
        assert cache.size() == 3

        # 访问 key1 和 key3，使 key2 成为最少使用
        cache.get("key1")
        cache.get("key3")

        # 添加第 4 个条目，应该删除 key2（最少使用）
        cache.set(key="key4", value="value4", strategy=strategy)
        assert cache.size() == 3
        assert cache.get("key2") is None
        assert cache.get("key1") == "value1"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_lru_cache_access_count_affects_eviction(self):
        """测试访问次数影响淘汰顺序"""
        cache = LRUCacheManager(max_size=2)
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        cache.set(key="key1", value="value1", strategy=strategy)
        cache.set(key="key2", value="value2", strategy=strategy)

        # 多次访问 key1，增加其访问计数
        for _ in range(5):
            cache.get("key1")

        # 添加第 3 个条目，应该删除 key2（访问次数少）
        cache.set(key="key3", value="value3", strategy=strategy)
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None

    def test_lru_cache_thread_safety(self):
        """测试线程安全性"""
        cache = LRUCacheManager(max_size=100)
        strategy = TTLInvalidationStrategy(ttl_seconds=60)
        results = []
        errors = []

        def worker(thread_id):
            try:
                for i in range(50):
                    key = f"thread_{thread_id}_key_{i}"
                    cache.set(key=key, value=f"value_{i}", strategy=strategy)
                    value = cache.get(key)
                    results.append((thread_id, value))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 250


class TestCacheManager:
    """全局缓存管理器的单元测试"""

    def test_cache_manager_creation(self):
        """测试缓存管理器创建"""
        manager = CacheManager()
        assert manager is not None
        assert len(manager.get_all_cache_names()) > 0

    def test_cache_manager_default_caches(self):
        """测试默认缓存的初始化"""
        manager = CacheManager()
        cache_names = manager.get_all_cache_names()

        assert "worktree_info" in cache_names
        assert "symlink_validity" in cache_names
        assert "git_status" in cache_names

    def test_cache_manager_register_cache(self):
        """测试注册新缓存"""
        manager = CacheManager()
        initial_count = len(manager.get_all_cache_names())

        manager.register_cache("custom_cache", max_size=50)
        assert len(manager.get_all_cache_names()) == initial_count + 1
        assert "custom_cache" in manager.get_all_cache_names()

    def test_cache_manager_register_duplicate_cache(self):
        """测试重复注册缓存不会创建副本"""
        manager = CacheManager()
        initial_count = len(manager.get_all_cache_names())

        manager.register_cache("custom_cache", max_size=50)
        manager.register_cache("custom_cache", max_size=100)

        assert len(manager.get_all_cache_names()) == initial_count + 1

    def test_cache_manager_set_and_get(self):
        """测试缓存管理器的设置和获取"""
        manager = CacheManager()
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        manager.set("worktree_info", "key1", "value1", strategy)
        assert manager.get("worktree_info", "key1") == "value1"

    def test_cache_manager_get_nonexistent_cache(self):
        """测试获取不存在的缓存"""
        manager = CacheManager()
        assert manager.get("nonexistent_cache", "key") is None

    def test_cache_manager_delete(self):
        """测试缓存删除"""
        manager = CacheManager()
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        manager.set("worktree_info", "key1", "value1", strategy)
        assert manager.exists("worktree_info", "key1")

        assert manager.delete("worktree_info", "key1")
        assert not manager.exists("worktree_info", "key1")

    def test_cache_manager_delete_nonexistent_key(self):
        """测试删除不存在的键"""
        manager = CacheManager()
        assert not manager.delete("worktree_info", "nonexistent")

    def test_cache_manager_delete_nonexistent_cache(self):
        """测试删除不存在的缓存存储中的键"""
        manager = CacheManager()
        assert not manager.delete("nonexistent_cache", "key")

    def test_cache_manager_clear_specific_cache(self):
        """测试清空特定缓存"""
        manager = CacheManager()
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        manager.set("worktree_info", "key1", "value1", strategy)
        manager.set("git_status", "key2", "value2", strategy)

        manager.clear("worktree_info")
        assert not manager.exists("worktree_info", "key1")
        assert manager.exists("git_status", "key2")

    def test_cache_manager_clear_all_caches(self):
        """测试清空所有缓存"""
        manager = CacheManager()
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        manager.set("worktree_info", "key1", "value1", strategy)
        manager.set("git_status", "key2", "value2", strategy)

        manager.clear()
        assert not manager.exists("worktree_info", "key1")
        assert not manager.exists("git_status", "key2")

    def test_cache_manager_exists(self):
        """测试缓存存在性检查"""
        manager = CacheManager()
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        manager.set("worktree_info", "key1", "value1", strategy)
        assert manager.exists("worktree_info", "key1")
        assert not manager.exists("worktree_info", "nonexistent")

    def test_cache_manager_get_cache_info(self):
        """测试获取缓存信息"""
        manager = CacheManager()
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        manager.set("worktree_info", "key1", "value1", strategy)
        manager.set("worktree_info", "key2", "value2", strategy)

        info = manager.get_cache_info("worktree_info")
        assert info is not None
        assert info["size"] == 2
        assert info["max_size"] > 0

    def test_cache_manager_get_cache_info_nonexistent(self):
        """测试获取不存在的缓存信息"""
        manager = CacheManager()
        info = manager.get_cache_info("nonexistent_cache")
        assert info is None

    def test_cache_manager_thread_safety(self):
        """测试管理器的线程安全性"""
        manager = CacheManager()
        strategy = TTLInvalidationStrategy(ttl_seconds=60)
        errors = []

        def worker(thread_id):
            try:
                for i in range(20):
                    cache_name = f"cache_{thread_id % 3}"
                    key = f"key_{i}"
                    manager.set(cache_name, key, f"value_{i}", strategy)
                    manager.get(cache_name, key)
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestGetCacheManager:
    """全局缓存管理器单例的测试"""

    def test_get_cache_manager_singleton(self):
        """测试 get_cache_manager 返回单例"""
        manager1 = get_cache_manager()
        manager2 = get_cache_manager()
        assert manager1 is manager2

    def test_get_cache_manager_functionality(self):
        """测试通过 get_cache_manager 获取的管理器功能"""
        manager = get_cache_manager()
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        manager.set("test_cache", "key", "value", strategy)
        assert manager.get("test_cache", "key") == "value"


class TestCacheIntegration:
    """缓存系统集成测试"""

    def test_mixed_ttl_and_file_strategies(self, tmp_path):
        """测试混合使用 TTL 和文件修改策略"""
        cache = LRUCacheManager(max_size=100)
        test_file = tmp_path / "config.yaml"
        test_file.write_text("config")

        ttl_strategy = TTLInvalidationStrategy(ttl_seconds=60)
        file_strategy = FileModificationInvalidationStrategy(file_path=test_file)

        cache.set("ttl_key", "ttl_value", ttl_strategy)
        cache.set("file_key", "file_value", file_strategy)

        assert cache.get("ttl_key") == "ttl_value"
        assert cache.get("file_key") == "file_value"

        # 修改文件，file_key 应该失效
        time.sleep(0.01)
        test_file.write_text("modified")

        assert cache.get("ttl_key") == "ttl_value"  # TTL 仍然有效
        assert cache.get("file_key") is None  # 文件失效

    def test_worktree_cache_scenario(self):
        """测试 worktree 缓存场景"""
        manager = CacheManager()
        strategy = TTLInvalidationStrategy(ttl_seconds=5 * 60)  # 5 分钟

        # 缓存分支列表
        branch_list = ["main", "develop", "feature/new-feature"]
        manager.set("worktree_info", "branch_list", branch_list, strategy)

        # 缓存 worktree 列表
        worktree_list = [
            {"branch": "main", "path": "/path/to/main"},
            {"branch": "develop", "path": "/path/to/develop"},
        ]
        manager.set("worktree_info", "worktree_list", worktree_list, strategy)

        # 验证缓存
        assert manager.get("worktree_info", "branch_list") == branch_list
        assert manager.get("worktree_info", "worktree_list") == worktree_list

    def test_git_status_cache_scenario(self):
        """测试 Git 状态缓存场景"""
        manager = CacheManager()
        strategy = TTLInvalidationStrategy(ttl_seconds=2 * 60)  # 2 分钟

        # 缓存 Git 状态
        git_status = {
            "branch": "feature/cache-system",
            "modified_files": ["gm/core/cache_manager.py"],
            "staged_files": [],
            "untracked_files": [],
        }
        manager.set("git_status", "main", git_status, strategy)

        # 验证缓存
        cached_status = manager.get("git_status", "main")
        assert cached_status == git_status
        assert cached_status["branch"] == "feature/cache-system"

    def test_cache_performance_metrics(self):
        """测试缓存性能指标"""
        cache = LRUCacheManager(max_size=1000)
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        # 添加 100 个条目
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}", strategy)

        # 执行缓存命中和未命中
        hits = 0
        misses = 0

        for i in range(100):
            if cache.get(f"key_{i}") is not None:
                hits += 1
            else:
                misses += 1

        for i in range(100, 110):
            if cache.get(f"key_{i}") is not None:
                hits += 1
            else:
                misses += 1

        assert hits == 100
        assert misses == 10
        hit_rate = hits / (hits + misses) * 100
        assert hit_rate > 89.0 and hit_rate < 91.0  # 允许浮点数误差

    def test_cache_memory_usage_simulation(self):
        """测试缓存内存使用"""
        cache = LRUCacheManager(max_size=10)
        strategy = TTLInvalidationStrategy(ttl_seconds=60)

        # 填充缓存到最大容量
        for i in range(10):
            cache.set(f"key_{i}", f"value_{i}" * 1000, strategy)

        assert cache.size() == 10

        # 添加更多条目，应该触发 LRU 淘汰
        for i in range(10, 20):
            cache.set(f"key_{i}", f"value_{i}" * 1000, strategy)

        # 缓存大小不应该超过最大值
        assert cache.size() == 10
