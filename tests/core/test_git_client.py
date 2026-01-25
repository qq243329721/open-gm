"""GitClient 单元测试

测试 Git 操作客户端的所有功能。
"""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from gm.core.git_client import GitClient
from gm.core.exceptions import GitCommandError


class TestGitClientInit:
    """测试 GitClient 初始化"""

    def test_init_with_default_path(self):
        """测试使用默认路径初始化"""
        client = GitClient()
        assert client.repo_path == Path.cwd()

    def test_init_with_custom_path(self):
        """测试使用自定义路径初始化"""
        custom_path = Path("/custom/path")
        client = GitClient(custom_path)
        assert client.repo_path == custom_path

    def test_init_with_string_path(self):
        """测试使用字符串路径初始化"""
        client = GitClient("/some/path")
        assert client.repo_path == Path("/some/path")


class TestRunCommand:
    """测试 run_command 方法"""

    @patch("subprocess.run")
    def test_successful_command(self, mock_run):
        """测试成功执行命令"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="output content",
            stderr="",
        )

        client = GitClient()
        result = client.run_command(["git", "status"])

        assert result == "output content"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_failed_command_with_check_true(self, mock_run):
        """测试命令失败且 check=True 时抛出异常"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="fatal: not a git repository",
        )

        client = GitClient()
        with pytest.raises(GitCommandError) as exc_info:
            client.run_command(["git", "status"], check=True)

        assert "Git command failed" in str(exc_info.value)

    @patch("subprocess.run")
    def test_failed_command_with_check_false(self, mock_run):
        """测试命令失败且 check=False 时不抛出异常"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error message",
        )

        client = GitClient()
        # 应该不抛出异常
        result = client.run_command(["git", "status"], check=False)
        # 返回空输出或输出内容
        assert isinstance(result, str)

    @patch("subprocess.run")
    def test_command_with_custom_cwd(self, mock_run):
        """测试命令使用自定义工作目录"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        custom_path = Path("/custom/path")
        client = GitClient()
        client.run_command(["git", "status"], cwd=custom_path)

        # 验证 cwd 参数被正确传递
        call_args = mock_run.call_args
        assert call_args[1]["cwd"] == custom_path

    @patch("subprocess.run")
    def test_command_strips_output(self, mock_run):
        """测试命令输出被正确 strip"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="  output with spaces  \n",
            stderr="",
        )

        client = GitClient()
        result = client.run_command(["git", "status"])

        assert result == "output with spaces"


class TestGetVersion:
    """测试 get_version 方法"""

    @patch.object(GitClient, "run_command")
    def test_get_version_success(self, mock_run):
        """测试成功获取版本"""
        mock_run.return_value = "git version 2.30.0"

        client = GitClient()
        version = client.get_version()

        assert version == "2.30.0"
        mock_run.assert_called_once_with(["git", "--version"])

    @patch.object(GitClient, "run_command")
    def test_get_version_error(self, mock_run):
        """测试获取版本出错"""
        mock_run.side_effect = GitCommandError("Command failed")

        client = GitClient()
        with pytest.raises(GitCommandError):
            client.get_version()


class TestGetCurrentBranch:
    """测试 get_current_branch 方法"""

    @patch.object(GitClient, "run_command")
    def test_get_current_branch_success(self, mock_run):
        """测试成功获取当前分支"""
        mock_run.return_value = "main"

        client = GitClient()
        branch = client.get_current_branch()

        assert branch == "main"
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        )

    @patch.object(GitClient, "run_command")
    def test_get_current_branch_error(self, mock_run):
        """测试获取当前分支出错"""
        mock_run.side_effect = GitCommandError("Not a git repository")

        client = GitClient()
        with pytest.raises(GitCommandError):
            client.get_current_branch()


class TestCheckBranchExists:
    """测试 check_branch_exists 方法"""

    @patch.object(GitClient, "run_command")
    def test_branch_exists(self, mock_run):
        """测试分支存在"""
        mock_run.return_value = "refs/heads/feature/test"

        client = GitClient()
        exists = client.check_branch_exists("feature/test")

        assert exists is True

    @patch.object(GitClient, "run_command")
    def test_branch_not_exists(self, mock_run):
        """测试分支不存在"""
        mock_run.side_effect = GitCommandError("Branch not found")

        client = GitClient()
        exists = client.check_branch_exists("nonexistent")

        assert exists is False

    @patch.object(GitClient, "run_command")
    def test_check_branch_command(self, mock_run):
        """验证检查分支的正确命令"""
        mock_run.return_value = ""

        client = GitClient()
        client.check_branch_exists("feature/test")

        mock_run.assert_called_once_with(
            ["git", "show-ref", "--verify", "refs/heads/feature/test"]
        )


class TestGetRemoteBranch:
    """测试 get_remote_branch 方法"""

    @patch.object(GitClient, "check_branch_exists")
    @patch.object(GitClient, "run_command")
    def test_get_remote_branch_success(self, mock_run, mock_check):
        """测试成功获取远程分支"""
        mock_run.return_value = ""
        mock_check.return_value = True

        client = GitClient()
        result = client.get_remote_branch("feature/test")

        assert result is True

    @patch.object(GitClient, "check_branch_exists")
    @patch.object(GitClient, "run_command")
    def test_get_remote_branch_failure(self, mock_run, mock_check):
        """测试获取远程分支失败"""
        mock_run.return_value = ""
        mock_check.return_value = False

        client = GitClient()
        result = client.get_remote_branch("feature/test")

        assert result is False

    @patch.object(GitClient, "check_branch_exists")
    @patch.object(GitClient, "run_command")
    def test_get_remote_branch_command(self, mock_run, mock_check):
        """验证获取远程分支的正确命令"""
        mock_run.return_value = ""
        mock_check.return_value = True

        client = GitClient()
        client.get_remote_branch("feature/test")

        # 验证 fetch 命令
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0:3] == ["git", "fetch", "origin"]


class TestCreateWorktree:
    """测试 create_worktree 方法"""

    @patch.object(GitClient, "run_command")
    def test_create_worktree_success(self, mock_run):
        """测试成功创建 worktree"""
        mock_run.return_value = ""

        client = GitClient()
        path = Path("/repo/feature-test")
        client.create_worktree(path, "feature/test")

        # 验证命令调用
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0:3] == ["git", "worktree", "add"]
        assert "feature/test" in call_args

    @patch.object(GitClient, "run_command")
    def test_create_worktree_error(self, mock_run):
        """测试创建 worktree 失败"""
        mock_run.side_effect = GitCommandError("Failed to create")

        client = GitClient()
        path = Path("/repo/feature-test")

        with pytest.raises(GitCommandError):
            client.create_worktree(path, "feature/test")

    @patch("pathlib.Path.mkdir")
    @patch.object(GitClient, "run_command")
    def test_create_worktree_creates_parent_dir(self, mock_run, mock_mkdir):
        """测试创建 worktree 时创建父目录"""
        mock_run.return_value = ""

        client = GitClient()
        path = Path("/repo/feature-test")
        client.create_worktree(path, "feature/test")

        # 验证 mkdir 被调用
        mock_mkdir.assert_called_once()


class TestDeleteWorktree:
    """测试 delete_worktree 方法"""

    @patch.object(GitClient, "run_command")
    def test_delete_worktree_success(self, mock_run):
        """测试成功删除 worktree"""
        mock_run.return_value = ""

        client = GitClient()
        path = Path("/repo/feature-test")
        client.delete_worktree(path)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "worktree" in call_args
        assert "remove" in call_args
        assert str(path) in call_args

    @patch.object(GitClient, "run_command")
    def test_delete_worktree_force(self, mock_run):
        """测试强制删除 worktree"""
        mock_run.return_value = ""

        client = GitClient()
        path = Path("/repo/feature-test")
        client.delete_worktree(path, force=True)

        call_args = mock_run.call_args[0][0]
        assert "--force" in call_args

    @patch.object(GitClient, "run_command")
    def test_delete_worktree_error(self, mock_run):
        """测试删除 worktree 失败"""
        mock_run.side_effect = GitCommandError("Failed to remove")

        client = GitClient()
        path = Path("/repo/feature-test")

        with pytest.raises(GitCommandError):
            client.delete_worktree(path)


class TestGetWorktreeList:
    """测试 get_worktree_list 方法"""

    @patch.object(GitClient, "run_command")
    def test_get_worktree_list_success(self, mock_run):
        """测试成功获取 worktree 列表"""
        output = (
            "worktree /path/to/main\n"
            "branch /refs/heads/main\n"
            "\n"
            "worktree /path/to/feature-test\n"
            "branch /refs/heads/feature/test\n"
        )
        mock_run.return_value = output

        client = GitClient()
        worktrees = client.get_worktree_list()

        assert len(worktrees) == 2
        assert worktrees[0]["path"] == "/path/to/main"
        assert worktrees[0]["branch"] == "main"
        assert worktrees[1]["path"] == "/path/to/feature-test"
        assert worktrees[1]["branch"] == "feature/test"

    @patch.object(GitClient, "run_command")
    def test_get_worktree_list_error(self, mock_run):
        """测试获取 worktree 列表出错"""
        mock_run.side_effect = GitCommandError("Command failed")

        client = GitClient()
        with pytest.raises(GitCommandError):
            client.get_worktree_list()

    @patch.object(GitClient, "run_command")
    def test_get_worktree_list_empty(self, mock_run):
        """测试获取空 worktree 列表"""
        mock_run.return_value = ""

        client = GitClient()
        worktrees = client.get_worktree_list()

        assert worktrees == []


class TestDeleteBranch:
    """测试 delete_branch 方法"""

    @patch.object(GitClient, "run_command")
    def test_delete_branch_success(self, mock_run):
        """测试成功删除分支"""
        mock_run.return_value = ""

        client = GitClient()
        client.delete_branch("feature/test")

        call_args = mock_run.call_args[0][0]
        assert "branch" in call_args
        assert "-d" in call_args
        assert "feature/test" in call_args

    @patch.object(GitClient, "run_command")
    def test_delete_branch_force(self, mock_run):
        """测试强制删除分支"""
        mock_run.return_value = ""

        client = GitClient()
        client.delete_branch("feature/test", force=True)

        call_args = mock_run.call_args[0][0]
        assert "-D" in call_args

    @patch.object(GitClient, "run_command")
    def test_delete_branch_error(self, mock_run):
        """测试删除分支失败"""
        mock_run.side_effect = GitCommandError("Failed to delete")

        client = GitClient()
        with pytest.raises(GitCommandError):
            client.delete_branch("feature/test")


class TestGetRepoRoot:
    """测试 get_repo_root 方法"""

    @patch.object(GitClient, "run_command")
    def test_get_repo_root_success(self, mock_run):
        """测试成功获取仓库根路径"""
        mock_run.return_value = "/home/user/project"

        client = GitClient()
        root = client.get_repo_root()

        assert root == Path("/home/user/project")
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "--show-toplevel"]
        )

    @patch.object(GitClient, "run_command")
    def test_get_repo_root_error(self, mock_run):
        """测试获取仓库根路径失败"""
        mock_run.side_effect = GitCommandError("Not a git repository")

        client = GitClient()
        with pytest.raises(GitCommandError):
            client.get_repo_root()


class TestGetBranchList:
    """测试 get_branch_list 方法"""

    @patch.object(GitClient, "run_command")
    def test_get_branch_list_local(self, mock_run):
        """测试获取本地分支列表"""
        mock_run.return_value = "* main\n  feature/test\n  feature/ui"

        client = GitClient()
        branches = client.get_branch_list(remote=False)

        assert len(branches) == 3
        assert "main" in branches
        assert "feature/test" in branches

    @patch.object(GitClient, "run_command")
    def test_get_branch_list_remote(self, mock_run):
        """测试获取远程分支列表"""
        mock_run.return_value = "  origin/main\n  origin/feature/test"

        client = GitClient()
        branches = client.get_branch_list(remote=True)

        call_args = mock_run.call_args[0][0]
        assert "-r" in call_args
        assert len(branches) == 2

    @patch.object(GitClient, "run_command")
    def test_get_branch_list_error(self, mock_run):
        """测试获取分支列表出错"""
        mock_run.side_effect = GitCommandError("Command failed")

        client = GitClient()
        branches = client.get_branch_list()

        # 应该返回空列表而不是抛出异常
        assert branches == []


class TestGetStatus:
    """测试 get_status 方法"""

    @patch.object(GitClient, "run_command")
    def test_get_status_clean(self, mock_run):
        """测试获取干净的 git 状态"""
        mock_run.return_value = ""

        client = GitClient()
        status = client.get_status()

        assert status == ""

    @patch.object(GitClient, "run_command")
    def test_get_status_with_changes(self, mock_run):
        """测试获取有改动的 git 状态"""
        mock_run.return_value = "M  file.txt\n?? newfile.txt"

        client = GitClient()
        status = client.get_status()

        assert "file.txt" in status

    @patch.object(GitClient, "run_command")
    def test_get_status_error(self, mock_run):
        """测试获取 git 状态出错"""
        mock_run.side_effect = GitCommandError("Command failed")

        client = GitClient()
        status = client.get_status()

        assert status == ""


class TestHasUncommittedChanges:
    """测试 has_uncommitted_changes 方法"""

    @patch.object(GitClient, "get_status")
    def test_has_changes_true(self, mock_status):
        """测试有未提交改动"""
        mock_status.return_value = "M  file.txt"

        client = GitClient()
        has_changes = client.has_uncommitted_changes()

        assert has_changes is True

    @patch.object(GitClient, "get_status")
    def test_has_changes_false(self, mock_status):
        """测试没有未提交改动"""
        mock_status.return_value = ""

        client = GitClient()
        has_changes = client.has_uncommitted_changes()

        assert has_changes is False

    @patch.object(GitClient, "get_status")
    def test_has_changes_with_custom_cwd(self, mock_status):
        """测试使用自定义工作目录检查改动"""
        mock_status.return_value = ""

        custom_path = Path("/custom/path")
        client = GitClient()
        client.has_uncommitted_changes(cwd=custom_path)

        # 验证 cwd 被正确传递
        call_kwargs = mock_status.call_args[1]
        assert call_kwargs["cwd"] == custom_path
