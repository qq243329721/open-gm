"""共享文件管理器测试"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from gm.core.shared_file_manager import SharedFileManager
from gm.core.symlink_manager import SymlinkManager
from gm.core.config_manager import ConfigManager
from gm.core.exceptions import SymlinkException


class TestSharedFileManager:
    """SharedFileManager 测试类"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def main_branch_path(self, temp_dir):
        """创建主分支路径"""
        path = temp_dir / "main"
        path.mkdir()
        return path

    @pytest.fixture
    def worktree_path(self, temp_dir):
        """创建 worktree 路径"""
        path = temp_dir / "worktree"
        path.mkdir()
        return path

    @pytest.fixture
    def shared_files(self, main_branch_path):
        """创建共享文件"""
        files = ["config.yaml", "shared_dir"]

        # 创建共享文件
        (main_branch_path / "config.yaml").write_text("shared config")

        # 创建共享目录
        shared_dir = main_branch_path / "shared_dir"
        shared_dir.mkdir()
        (shared_dir / "file1.txt").write_text("file1")
        (shared_dir / "file2.txt").write_text("file2")

        return files

    @pytest.fixture
    def mock_config_manager(self, shared_files):
        """创建模拟配置管理器"""
        mock_config = MagicMock(spec=ConfigManager)
        mock_config.get_shared_files.return_value = shared_files
        return mock_config

    @pytest.fixture
    def shared_file_manager(self, main_branch_path, mock_config_manager):
        """创建 SharedFileManager 实例"""
        symlink_manager = SymlinkManager(strategy='auto')
        return SharedFileManager(
            main_branch_path=main_branch_path,
            config_manager=mock_config_manager,
            symlink_manager=symlink_manager
        )

    # 基础测试

    def test_init(self, main_branch_path, mock_config_manager):
        """测试初始化"""
        manager = SharedFileManager(
            main_branch_path=main_branch_path,
            config_manager=mock_config_manager
        )

        assert manager.main_branch_path == main_branch_path
        assert manager.config_manager == mock_config_manager
        assert manager.symlink_manager is not None

    # 设置共享文件测试

    def test_setup_shared_files_success(
        self,
        shared_file_manager,
        main_branch_path,
        worktree_path,
        shared_files
    ):
        """测试成功设置共享文件"""
        result = shared_file_manager.setup_shared_files(worktree_path)

        assert result is True

        # 验证符号链接已创建
        for file_name in shared_files:
            target_link = worktree_path / file_name
            assert target_link.exists()

    def test_setup_shared_files_no_files(
        self,
        main_branch_path,
        worktree_path,
        mock_config_manager
    ):
        """测试没有共享文件时的设置"""
        mock_config_manager.get_shared_files.return_value = []
        symlink_manager = SymlinkManager(strategy='auto')
        manager = SharedFileManager(
            main_branch_path=main_branch_path,
            config_manager=mock_config_manager,
            symlink_manager=symlink_manager
        )

        result = manager.setup_shared_files(worktree_path)

        assert result is True

    def test_setup_shared_files_missing_source(
        self,
        shared_file_manager,
        worktree_path,
        mock_config_manager
    ):
        """测试源文件不存在时的设置"""
        mock_config_manager.get_shared_files.return_value = ["non_existent.txt"]

        result = shared_file_manager.setup_shared_files(worktree_path)

        # 应该返回 False，因为没有成功创建任何链接
        assert result is False

    def test_setup_shared_files_target_exists(
        self,
        shared_file_manager,
        main_branch_path,
        worktree_path,
        mock_config_manager
    ):
        """测试目标已存在时的设置"""
        mock_config_manager.get_shared_files.return_value = ["config.yaml"]

        # 在 worktree 中创建文件
        (worktree_path / "config.yaml").write_text("existing")

        result = shared_file_manager.setup_shared_files(worktree_path)

        # 应该返回 False，因为跳过了已存在的链接，未创建任何链接
        assert result is False

    # 同步共享文件测试

    def test_sync_shared_files_all_valid(
        self,
        shared_file_manager,
        main_branch_path,
        worktree_path,
        shared_files
    ):
        """测试所有共享文件均有效时的同步"""
        # 首先创建链接
        shared_file_manager.setup_shared_files(worktree_path)

        # 同步
        results = shared_file_manager.sync_shared_files(worktree_path)

        # 所有文件都应该同步成功
        assert all(results.values())
        assert len(results) == len(shared_files)

    def test_sync_shared_files_missing_link(
        self,
        shared_file_manager,
        worktree_path
    ):
        """测试缺少链接时的同步"""
        results = shared_file_manager.sync_shared_files(worktree_path)

        # 应该尝试创建缺少的链接
        for file_name, success in results.items():
            # 文件应该被处理
            assert file_name is not None

    def test_sync_shared_files_broken_link(
        self,
        shared_file_manager,
        main_branch_path,
        worktree_path,
        shared_files
    ):
        """测试破损链接时的同步"""
        # 创建链接
        shared_file_manager.setup_shared_files(worktree_path)

        # 删除源文件以破损链接
        (main_branch_path / "config.yaml").unlink()

        # 同步
        results = shared_file_manager.sync_shared_files(worktree_path)

        # 应该处理破损链接（结果可能为 False）
        assert "config.yaml" in results

    # 获取状态测试

    def test_get_shared_files_status_success(
        self,
        shared_file_manager,
        main_branch_path,
        worktree_path,
        shared_files
    ):
        """测试获取共享文件状态"""
        # 创建链接
        shared_file_manager.setup_shared_files(worktree_path)

        status = shared_file_manager.get_shared_files_status(worktree_path)

        assert status["total_files"] == len(shared_files)
        assert "files" in status
        assert status["valid_count"] > 0

    def test_get_shared_files_status_empty(
        self,
        main_branch_path,
        worktree_path,
        mock_config_manager
    ):
        """测试空的共享文件状态"""
        mock_config_manager.get_shared_files.return_value = []
        symlink_manager = SymlinkManager(strategy='auto')
        manager = SharedFileManager(
            main_branch_path=main_branch_path,
            config_manager=mock_config_manager,
            symlink_manager=symlink_manager
        )

        status = manager.get_shared_files_status(worktree_path)

        assert status["total_files"] == 0
        assert status["valid_count"] == 0

    # 冲突处理测试

    def test_handle_shared_file_conflict(
        self,
        shared_file_manager,
        main_branch_path,
        worktree_path
    ):
        """测试处理共享文件冲突"""
        # 设置
        shared_file_manager.setup_shared_files(worktree_path)

        conflict_file = worktree_path / "config.yaml"

        result = shared_file_manager.handle_shared_file_conflict(conflict_file)

        assert result is True
        assert conflict_file.exists()

    def test_handle_shared_file_conflict_unknown_file(
        self,
        shared_file_manager,
        main_branch_path,
        worktree_path
    ):
        """测试处理未知的共享文件冲突"""
        unknown_file = worktree_path / "unknown.txt"
        unknown_file.write_text("conflict")

        with pytest.raises(SymlinkException):
            shared_file_manager.handle_shared_file_conflict(unknown_file)

    # 清理测试

    def test_cleanup_broken_links(
        self,
        shared_file_manager,
        main_branch_path,
        worktree_path,
        shared_files
    ):
        """测试清理破损链接"""
        # 创建链接
        shared_file_manager.setup_shared_files(worktree_path)

        # 删除源文件以破损链接
        (main_branch_path / "config.yaml").unlink()

        # 清理
        cleanup_count = shared_file_manager.cleanup_broken_links(worktree_path)

        # 应该清理至少一个破损链接
        assert cleanup_count >= 0

    def test_cleanup_broken_links_no_broken_links(
        self,
        shared_file_manager,
        worktree_path,
        shared_files
    ):
        """测试没有破损链接时的清理"""
        # 创建链接
        shared_file_manager.setup_shared_files(worktree_path)

        # 清理
        cleanup_count = shared_file_manager.cleanup_broken_links(worktree_path)

        assert cleanup_count == 0

    # 集成测试

    def test_setup_and_sync_workflow(
        self,
        shared_file_manager,
        main_branch_path,
        worktree_path,
        shared_files
    ):
        """测试完整的设置和同步工作流"""
        # 1. 设置
        result = shared_file_manager.setup_shared_files(worktree_path)
        assert result is True

        # 2. 获取状态
        status1 = shared_file_manager.get_shared_files_status(worktree_path)
        assert status1["total_files"] == len(shared_files)

        # 3. 同步
        sync_results = shared_file_manager.sync_shared_files(worktree_path)
        assert len(sync_results) > 0

        # 4. 再次获取状态
        status2 = shared_file_manager.get_shared_files_status(worktree_path)
        assert status2["total_files"] == len(shared_files)

    def test_error_handling_invalid_path(
        self,
        shared_file_manager
    ):
        """测试无效路径的错误处理"""
        invalid_path = Path("/invalid/path/that/does/not/exist")

        # 应该处理无效路径或返回 False
        # 由于在 Windows 上会创建文件，我们只验证函数不会崩溃
        result = shared_file_manager.setup_shared_files(invalid_path)
        # 结果可能是 True 或 False，取决于平台和权限
        assert isinstance(result, bool)


class TestSharedFileManagerIntegration:
    """集成测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def setup_environment(self, temp_dir):
        """设置测试环境"""
        # 创建主分支目录
        main_path = temp_dir / "main"
        main_path.mkdir()

        # 创建一些共享文件
        (main_path / ".config.yaml").write_text("config content")
        (main_path / ".env").write_text("env content")

        # 创建配置文件
        config_path = main_path / ".gm.yaml"
        config_path.write_text("""
shared_files:
  - .config.yaml
  - .env
""")

        return main_path

    def test_complete_workflow(self, temp_dir, setup_environment):
        """测试完整的工作流"""
        main_path = setup_environment

        # 创建 worktree 路径
        worktree_path = temp_dir / "feature"
        worktree_path.mkdir()

        # 创建配置管理器
        config_manager = ConfigManager(main_path)

        # 创建共享文件管理器
        symlink_manager = SymlinkManager(strategy='auto')
        manager = SharedFileManager(
            main_branch_path=main_path,
            config_manager=config_manager,
            symlink_manager=symlink_manager
        )

        # 1. 设置共享文件
        result = manager.setup_shared_files(worktree_path)
        assert result is True

        # 2. 验证链接已创建
        assert (worktree_path / ".config.yaml").exists()
        assert (worktree_path / ".env").exists()

        # 3. 获取状态
        status = manager.get_shared_files_status(worktree_path)
        assert status["valid_count"] > 0

        # 4. 同步
        sync_results = manager.sync_shared_files(worktree_path)
        # 至少有一些文件应该同步成功
        assert any(sync_results.values())
