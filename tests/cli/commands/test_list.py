"""GM list 命令的单元测试"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from gm.cli.commands.list import ListCommand, WorktreeInfo
from gm.core.exceptions import GitException, ConfigException


class TestWorktreeInfo:
    """WorktreeInfo 测试类"""

    def test_worktree_info_creation(self):
        """测试 WorktreeInfo 创建"""
        info = WorktreeInfo("/path/to/worktree", "feature/test", is_active=False)
        assert info.path == "/path/to/worktree"
        assert info.branch == "feature/test"
        assert info.is_active is False
        assert info.status == "clean"

    def test_worktree_info_active(self):
        """测试活跃 worktree"""
        info = WorktreeInfo("/path/to/.gm", "main", is_active=True)
        assert info.is_active is True
        assert info.status == "active"

    def test_worktree_info_to_dict(self):
        """测试转换为字典"""
        info = WorktreeInfo("/path/to/worktree", "feature/test")
        result = info.to_dict()
        assert result["path"] == "/path/to/worktree"
        assert result["branch"] == "feature/test"
        assert result["is_active"] is False


class TestListCommand:
    """列表命令测试类"""

    @pytest.fixture
    def temp_git_repo(self):
        """创建临时 git 仓库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            # 初始化 git 仓库
            import subprocess
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)

            # 创建初始提交
            test_file = repo_path / "README.md"
            test_file.write_text("# Test Repo\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

            # 创建 .gm 目录和配置文件
            gm_dir = repo_path / ".gm"
            gm_dir.mkdir()

            # 创建配置文件
            config_file = repo_path / ".gm.yaml"
            config_file.write_text("initialized: true\nmain_branch: main\n")

            yield repo_path

    def test_list_command_initialization(self, temp_git_repo):
        """测试列表命令初始化"""
        cmd = ListCommand(temp_git_repo)
        assert cmd.project_path == temp_git_repo
        assert cmd.worktrees == []

    def test_validate_project_success(self, temp_git_repo):
        """测试项目验证成功"""
        cmd = ListCommand(temp_git_repo)
        assert cmd.validate_project() is True

    def test_validate_project_not_git_repo(self, tmp_path):
        """测试非 git 仓库项目验证失败"""
        cmd = ListCommand(tmp_path)
        with pytest.raises(GitException):
            cmd.validate_project()

    def test_validate_project_not_initialized(self, tmp_path):
        """测试未初始化项目验证失败"""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        cmd = ListCommand(tmp_path)
        with pytest.raises(ConfigException):
            cmd.validate_project()

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_get_worktree_list_empty(self, mock_load_config, mock_get_worktree_list, temp_git_repo):
        """测试获取空 worktree 列表"""
        mock_get_worktree_list.return_value = []
        mock_load_config.return_value = {"main_branch": "main"}

        cmd = ListCommand(temp_git_repo)
        result = cmd.get_worktree_list()

        assert result == []
        assert cmd.worktrees == []

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_get_worktree_list_single(self, mock_load_config, mock_get_worktree_list, temp_git_repo):
        """测试获取单个 worktree"""
        gm_dir = temp_git_repo / ".gm"
        worktree_data = [
            {
                "path": str(temp_git_repo),
                "branch": "main",
            }
        ]
        mock_get_worktree_list.return_value = worktree_data
        mock_load_config.return_value = {"main_branch": "main"}

        cmd = ListCommand(temp_git_repo)
        result = cmd.get_worktree_list()

        assert len(result) == 1
        assert result[0].branch == "main"
        assert result[0].is_active is True

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_get_worktree_list_multiple(self, mock_load_config, mock_get_worktree_list, temp_git_repo):
        """测试获取多个 worktree"""
        feature_dir = temp_git_repo / ".gm" / "feature-test"
        feature_dir.mkdir(parents=True, exist_ok=True)

        worktree_data = [
            {"path": str(temp_git_repo), "branch": "main"},
            {"path": str(feature_dir), "branch": "feature/test"},
        ]
        mock_get_worktree_list.return_value = worktree_data
        mock_load_config.return_value = {"main_branch": "main"}

        cmd = ListCommand(temp_git_repo)
        result = cmd.get_worktree_list()

        assert len(result) == 2
        assert result[0].branch == "main"
        assert result[1].branch == "feature/test"

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_format_simple_output_empty(self, mock_load_config, mock_get_worktree_list, temp_git_repo):
        """测试简洁模式输出为空"""
        mock_get_worktree_list.return_value = []
        mock_load_config.return_value = {"main_branch": "main"}

        cmd = ListCommand(temp_git_repo)
        cmd.get_worktree_list()
        output = cmd.format_simple_output()

        assert "没有 worktree" in output

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.GitClient.has_uncommitted_changes")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_format_simple_output_with_worktrees(self, mock_load_config, mock_has_changes, mock_get_worktree_list, temp_git_repo):
        """测试简洁模式输出有 worktree"""
        worktree_data = [
            {"path": str(temp_git_repo), "branch": "main"},
        ]
        mock_get_worktree_list.return_value = worktree_data
        mock_load_config.return_value = {"main_branch": "main"}
        mock_has_changes.return_value = False

        cmd = ListCommand(temp_git_repo)
        cmd.get_worktree_list()
        output = cmd.format_simple_output()

        assert "BRANCH" in output
        assert "STATUS" in output
        assert "PATH" in output
        assert "main" in output

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_format_detailed_output_empty(self, mock_load_config, mock_get_worktree_list, temp_git_repo):
        """测试详细模式输出为空"""
        mock_get_worktree_list.return_value = []
        mock_load_config.return_value = {"main_branch": "main"}

        cmd = ListCommand(temp_git_repo)
        cmd.get_worktree_list()
        output = cmd.format_detailed_output()

        assert "没有 worktree" in output

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.GitClient.has_uncommitted_changes")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_format_detailed_output_with_worktrees(self, mock_load_config, mock_has_changes, mock_get_worktree_list, temp_git_repo):
        """测试详细模式输出有 worktree"""
        worktree_data = [
            {"path": str(temp_git_repo), "branch": "main"},
        ]
        mock_get_worktree_list.return_value = worktree_data
        mock_load_config.return_value = {"main_branch": "main"}
        mock_has_changes.return_value = False

        cmd = ListCommand(temp_git_repo)
        cmd.get_worktree_list()
        output = cmd.format_detailed_output()

        assert "Worktree" in output
        assert "分支" in output
        assert "状态" in output
        assert "路径" in output

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_worktree_status_clean(self, mock_load_config, mock_get_worktree_list, temp_git_repo):
        """测试 worktree 状态为 clean"""
        gm_dir = temp_git_repo / ".gm"
        feature_dir = gm_dir / "feature-test"
        feature_dir.mkdir(parents=True, exist_ok=True)

        worktree_data = [
            {"path": str(feature_dir), "branch": "feature/test"},
        ]
        mock_get_worktree_list.return_value = worktree_data
        mock_load_config.return_value = {"main_branch": "main"}

        with patch("gm.cli.commands.list.GitClient.has_uncommitted_changes", return_value=False):
            cmd = ListCommand(temp_git_repo)
            cmd.get_worktree_list()

            assert cmd.worktrees[0].is_dirty is False
            assert cmd.worktrees[0].status == "clean"

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_worktree_status_dirty(self, mock_load_config, mock_get_worktree_list, temp_git_repo):
        """测试 worktree 状态为 dirty"""
        gm_dir = temp_git_repo / ".gm"
        feature_dir = gm_dir / "feature-test"
        feature_dir.mkdir(parents=True, exist_ok=True)

        worktree_data = [
            {"path": str(feature_dir), "branch": "feature/test"},
        ]
        mock_get_worktree_list.return_value = worktree_data
        mock_load_config.return_value = {"main_branch": "main"}

        with patch("gm.cli.commands.list.GitClient.has_uncommitted_changes", return_value=True):
            cmd = ListCommand(temp_git_repo)
            cmd.get_worktree_list()

            assert cmd.worktrees[0].is_dirty is True
            assert cmd.worktrees[0].status == "dirty"

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_execute_simple_mode(self, mock_load_config, mock_get_worktree_list, temp_git_repo):
        """测试执行简洁模式"""
        worktree_data = [
            {"path": str(temp_git_repo), "branch": "main"},
        ]
        mock_get_worktree_list.return_value = worktree_data
        mock_load_config.return_value = {"main_branch": "main"}

        with patch("gm.cli.commands.list.GitClient.has_uncommitted_changes", return_value=False):
            with patch("click.echo") as mock_echo:
                cmd = ListCommand(temp_git_repo)
                cmd.execute(verbose=False)

                mock_echo.assert_called_once()
                output = mock_echo.call_args[0][0]
                assert "BRANCH" in output
                assert "STATUS" in output

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_execute_detailed_mode(self, mock_load_config, mock_get_worktree_list, temp_git_repo):
        """测试执行详细模式"""
        worktree_data = [
            {"path": str(temp_git_repo), "branch": "main"},
        ]
        mock_get_worktree_list.return_value = worktree_data
        mock_load_config.return_value = {"main_branch": "main"}

        with patch("gm.cli.commands.list.GitClient.has_uncommitted_changes", return_value=False):
            with patch("click.echo") as mock_echo:
                cmd = ListCommand(temp_git_repo)
                cmd.execute(verbose=True)

                mock_echo.assert_called_once()
                output = mock_echo.call_args[0][0]
                assert "Worktree" in output
                assert "分支" in output

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_execute_not_initialized(self, mock_load_config, mock_get_worktree_list, tmp_path):
        """测试执行未初始化的项目"""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        cmd = ListCommand(tmp_path)
        with pytest.raises(Exception):
            cmd.execute(verbose=False)

    def test_collect_worktree_info_nonexistent(self, temp_git_repo):
        """测试收集不存在的 worktree 信息"""
        info = WorktreeInfo("/nonexistent/path", "feature/test")

        cmd = ListCommand(temp_git_repo)
        cmd._collect_worktree_info(info)

        assert info.status == "orphaned"

    @patch("gm.cli.commands.list.GitClient.get_worktree_list")
    @patch("gm.cli.commands.list.GitClient.get_commit_info")
    @patch("gm.cli.commands.list.ConfigManager.load_config")
    def test_collect_commit_info(self, mock_load_config, mock_get_commit_info, mock_get_worktree_list, temp_git_repo):
        """测试收集提交信息"""
        gm_dir = temp_git_repo / ".gm"
        feature_dir = gm_dir / "feature-test"
        feature_dir.mkdir(parents=True, exist_ok=True)

        worktree_data = [
            {"path": str(feature_dir), "branch": "feature/test"},
        ]
        mock_get_worktree_list.return_value = worktree_data
        mock_load_config.return_value = {"main_branch": "main"}
        mock_get_commit_info.return_value = "abc1234|Update UI|John Doe|2 hours ago"

        with patch("gm.cli.commands.list.GitClient.has_uncommitted_changes", return_value=False):
            cmd = ListCommand(temp_git_repo)
            cmd.get_worktree_list()

            assert cmd.worktrees[0].last_commit_hash == "abc1234"
            assert cmd.worktrees[0].last_commit_message == "Update UI"
            assert cmd.worktrees[0].last_commit_author == "John Doe"
