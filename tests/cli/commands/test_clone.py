"""GM clone 命令的单元测试"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import pytest

from gm.cli.commands.clone import CloneCommand
from gm.core.exceptions import GitException, ConfigException, GitCommandError


class TestCloneCommand:
    """克隆命令测试类"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

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

            yield repo_path

    def test_validate_repo_url_https(self):
        """测试验证 HTTPS 仓库 URL"""
        cmd = CloneCommand("https://github.com/user/repo.git")
        assert cmd.validate_repo_url() is True

    def test_validate_repo_url_ssh(self):
        """测试验证 SSH 仓库 URL"""
        cmd = CloneCommand("git@github.com:user/repo.git")
        assert cmd.validate_repo_url() is True

    def test_validate_repo_url_local_path(self):
        """测试验证本地路径"""
        cmd = CloneCommand("/path/to/repo")
        assert cmd.validate_repo_url() is True

    def test_validate_repo_url_windows_path(self):
        """测试验证 Windows 路径"""
        cmd = CloneCommand("C:\\path\\to\\repo")
        assert cmd.validate_repo_url() is True

    def test_validate_repo_url_empty(self):
        """测试验证空 URL"""
        cmd = CloneCommand("")
        with pytest.raises(GitException):
            cmd.validate_repo_url()

    def test_validate_repo_url_invalid_format(self):
        """测试验证无效 URL 格式"""
        cmd = CloneCommand("invalid://repo")
        with pytest.raises(GitException):
            cmd.validate_repo_url()

    def test_determine_target_path_explicit(self):
        """测试显式指定目标路径"""
        cmd = CloneCommand("https://github.com/user/repo.git", "/path/to/project")
        assert cmd.determine_target_path() == Path("/path/to/project")

    def test_determine_target_path_from_https_url(self):
        """测试从 HTTPS URL 提取目标路径"""
        cmd = CloneCommand("https://github.com/user/repo.git")
        target = cmd.determine_target_path()
        assert target == Path.cwd() / "repo"

    def test_determine_target_path_from_ssh_url(self):
        """测试从 SSH URL 提取目标路径"""
        cmd = CloneCommand("git@github.com:user/repo.git")
        target = cmd.determine_target_path()
        assert target == Path.cwd() / "repo"

    def test_determine_target_path_from_local_path(self):
        """测试从本地路径提取目标路径"""
        cmd = CloneCommand("/path/to/repo")
        target = cmd.determine_target_path()
        assert target == Path.cwd() / "repo"

    def test_determine_target_path_without_git_extension(self):
        """测试从没有 .git 扩展的 URL 提取目标路径"""
        cmd = CloneCommand("https://github.com/user/repo")
        target = cmd.determine_target_path()
        assert target == Path.cwd() / "repo"

    def test_validate_target_path_empty_directory(self, temp_dir):
        """测试验证空目录"""
        cmd = CloneCommand("https://github.com/user/repo.git", str(temp_dir))
        assert cmd.validate_target_path(temp_dir) is True

    def test_validate_target_path_nonexistent(self, temp_dir):
        """测试验证不存在的路径"""
        new_path = temp_dir / "nonexistent"
        cmd = CloneCommand("https://github.com/user/repo.git", str(new_path))
        assert cmd.validate_target_path(new_path) is True

    def test_validate_target_path_not_empty(self, temp_dir):
        """测试验证非空目录"""
        # 在目录中创建一个文件
        (temp_dir / "file.txt").write_text("content")
        cmd = CloneCommand("https://github.com/user/repo.git", str(temp_dir))
        with pytest.raises(GitException):
            cmd.validate_target_path(temp_dir)

    def test_validate_target_path_not_directory(self, temp_dir):
        """测试验证非目录路径"""
        file_path = temp_dir / "file.txt"
        file_path.write_text("content")
        cmd = CloneCommand("https://github.com/user/repo.git", str(file_path))
        with pytest.raises(GitException):
            cmd.validate_target_path(file_path)

    @patch("gm.cli.commands.clone.GitClient.run_command")
    def test_clone_repository_success(self, mock_run_command, temp_dir):
        """测试成功克隆仓库"""
        target_path = temp_dir / "repo"
        cmd = CloneCommand("https://github.com/user/repo.git", str(target_path))

        cmd.clone_repository(target_path)

        assert cmd.cloned_path == target_path
        mock_run_command.assert_called_once()
        call_args = mock_run_command.call_args[0][0]
        assert "git" in call_args
        assert "clone" in call_args

    @patch("gm.cli.commands.clone.GitClient.run_command")
    def test_clone_repository_with_branch(self, mock_run_command, temp_dir):
        """测试使用指定分支克隆仓库"""
        target_path = temp_dir / "repo"
        cmd = CloneCommand(
            "https://github.com/user/repo.git",
            str(target_path),
            branch="develop",
        )

        cmd.clone_repository(target_path)

        call_args = mock_run_command.call_args[0][0]
        assert "--branch" in call_args
        assert "develop" in call_args

    @patch("gm.cli.commands.clone.GitClient.run_command")
    def test_clone_repository_with_depth(self, mock_run_command, temp_dir):
        """测试使用 shallow clone"""
        target_path = temp_dir / "repo"
        cmd = CloneCommand(
            "https://github.com/user/repo.git",
            str(target_path),
            depth=1,
        )

        cmd.clone_repository(target_path)

        call_args = mock_run_command.call_args[0][0]
        assert "--depth" in call_args
        assert "1" in call_args

    @patch("gm.cli.commands.clone.GitClient.run_command")
    def test_clone_repository_failure(self, mock_run_command, temp_dir):
        """测试克隆失败"""
        mock_run_command.side_effect = GitCommandError("Clone failed")

        target_path = temp_dir / "repo"
        cmd = CloneCommand("https://github.com/user/repo.git", str(target_path))

        with pytest.raises(GitCommandError):
            cmd.clone_repository(target_path)

    def test_cleanup_on_failure(self, temp_dir):
        """测试失败时的清理"""
        target_path = temp_dir / "repo"
        target_path.mkdir()
        (target_path / "file.txt").write_text("content")

        cmd = CloneCommand("https://github.com/user/repo.git")
        cmd.cleanup_on_failure(target_path)

        assert not target_path.exists()

    def test_cleanup_on_failure_nonexistent(self, temp_dir):
        """测试清理不存在的路径"""
        target_path = temp_dir / "nonexistent"
        cmd = CloneCommand("https://github.com/user/repo.git")
        # 不应该抛出异常
        cmd.cleanup_on_failure(target_path)

    @patch("gm.cli.commands.clone.InitCommand")
    @patch("gm.cli.commands.clone.GitClient.run_command")
    def test_execute_success_with_init(self, mock_run_command, mock_init_class, temp_dir):
        """测试成功克隆和初始化"""
        target_path = temp_dir / "repo"

        # 模拟 InitCommand
        mock_init_instance = MagicMock()
        mock_init_instance.validate_project.return_value = True
        mock_init_instance.check_already_initialized.return_value = False
        mock_init_instance.git_client.get_current_branch.return_value = "main"
        mock_init_instance.create_directory_structure.return_value = None
        mock_init_instance.create_config.return_value = None
        mock_init_instance.setup_shared_files.return_value = None
        mock_init_instance._rollback_directory.return_value = None
        mock_init_instance._rollback_config.return_value = None
        mock_init_class.return_value = mock_init_instance

        cmd = CloneCommand(
            "https://github.com/user/repo.git",
            str(target_path),
            no_init=False,
        )

        result = cmd.execute()

        assert result == target_path
        mock_run_command.assert_called_once()
        mock_init_class.assert_called_once()

    @patch("gm.cli.commands.clone.GitClient.run_command")
    @patch("gm.cli.commands.clone.InitCommand.execute")
    def test_execute_success_without_init(self, mock_init_execute, mock_run_command, temp_dir):
        """测试成功克隆但不初始化"""
        target_path = temp_dir / "repo"
        cmd = CloneCommand(
            "https://github.com/user/repo.git",
            str(target_path),
            no_init=True,
        )

        result = cmd.execute()

        assert result == target_path
        mock_run_command.assert_called_once()
        mock_init_execute.assert_not_called()

    @patch("gm.cli.commands.clone.GitClient.run_command")
    @patch("gm.cli.commands.clone.InitCommand.execute")
    def test_execute_clone_failure_cleanup(self, mock_init_execute, mock_run_command, temp_dir):
        """测试克隆失败时的清理"""
        mock_run_command.side_effect = GitCommandError("Clone failed")

        target_path = temp_dir / "repo"
        cmd = CloneCommand("https://github.com/user/repo.git", str(target_path))

        with pytest.raises(GitCommandError):
            cmd.execute()

        mock_init_execute.assert_not_called()

    @patch("gm.cli.commands.clone.GitClient.run_command")
    @patch("gm.cli.commands.clone.InitCommand")
    def test_execute_init_failure_cleanup(self, mock_init_class, mock_run_command, temp_dir):
        """测试初始化失败时的清理"""
        target_path = temp_dir / "repo"
        target_path.mkdir()

        # 模拟 InitCommand 初始化失败
        mock_init_instance = MagicMock()
        mock_init_instance.execute.side_effect = ConfigException("Init failed")
        mock_init_class.return_value = mock_init_instance

        cmd = CloneCommand("https://github.com/user/repo.git", str(target_path))

        with pytest.raises(ConfigException):
            cmd.execute()

        # 验证目录被清理
        assert not target_path.exists()

    def test_execute_invalid_url(self, temp_dir):
        """测试使用无效 URL 执行"""
        cmd = CloneCommand("invalid://repo", str(temp_dir / "repo"))
        with pytest.raises(GitException):
            cmd.execute()

    @patch("gm.cli.commands.clone.GitClient.run_command")
    def test_execute_with_branch_parameter(self, mock_run_command, temp_dir):
        """测试使用分支参数执行"""
        target_path = temp_dir / "repo"
        cmd = CloneCommand(
            "https://github.com/user/repo.git",
            str(target_path),
            branch="feature/new-feature",
            no_init=True,
        )

        result = cmd.execute()

        assert result == target_path
        call_args = mock_run_command.call_args[0][0]
        assert "--branch" in call_args
        assert "feature/new-feature" in call_args

    @patch("gm.cli.commands.clone.GitClient.run_command")
    @patch("gm.cli.commands.clone.InitCommand")
    def test_execute_with_automatic_branch_detection(self, mock_init_class, mock_run_command, temp_dir):
        """测试自动分支检测"""
        target_path = temp_dir / "repo"
        target_path.mkdir()

        # 模拟成功的初始化
        mock_init_instance = MagicMock()
        mock_init_instance.validate_project.return_value = True
        mock_init_instance.check_already_initialized.return_value = False
        mock_init_instance.git_client.get_current_branch.return_value = "main"
        mock_init_instance.create_directory_structure.return_value = None
        mock_init_instance.create_config.return_value = None
        mock_init_instance.setup_shared_files.return_value = None
        mock_init_instance._rollback_directory.return_value = None
        mock_init_instance._rollback_config.return_value = None
        mock_init_class.return_value = mock_init_instance

        cmd = CloneCommand(
            "https://github.com/user/repo.git",
            str(target_path),
            no_init=False,
        )

        result = cmd.execute()

        assert result == target_path
        mock_init_class.assert_called_once()
