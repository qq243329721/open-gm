"""GM add 命令的单元测试"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from gm.cli.commands.add import AddCommand
from gm.core.exceptions import (
    ConfigException,
    GitException,
    WorktreeAlreadyExists,
)


class TestAddCommand:
    """添加 worktree 命令测试类"""

    @pytest.fixture
    def temp_git_repo_initialized(self):
        """创建已初始化的临时 git 仓库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            # 初始化 git 仓库
            import subprocess
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)

            # 创建初始提交
            readme = repo_path / "README.md"
            readme.write_text("# Test Project\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

            # 创建 main 分支
            subprocess.run(["git", "branch", "-M", "main"], cwd=repo_path, capture_output=True)

            # 初始化 .gm 项目
            gm_dir = repo_path / ".gm"
            gm_dir.mkdir()

            config_file = repo_path / ".gm.yaml"
            config_file.write_text("""
initialized: true
main_branch: main
worktree:
  base_path: .gm
  naming_pattern: '{branch}'
shared_files:
  - README.md
""")

            yield repo_path

    @pytest.fixture
    def temp_git_repo_not_initialized(self):
        """创建未初始化的临时 git 仓库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            # 初始化 git 仓库
            import subprocess
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)

            # 创建初始提交
            readme = repo_path / "README.md"
            readme.write_text("# Test Project\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

            yield repo_path

    def test_validate_project_initialized_success(self, temp_git_repo_initialized):
        """测试项目初始化验证成功"""
        cmd = AddCommand(temp_git_repo_initialized)
        assert cmd.validate_project_initialized() is True

    def test_validate_project_initialized_failure(self, temp_git_repo_not_initialized):
        """测试项目初始化验证失败"""
        cmd = AddCommand(temp_git_repo_not_initialized)
        with pytest.raises(ConfigException, match="尚未初始化"):
            cmd.validate_project_initialized()

    def test_check_branch_exists_local_only(self, temp_git_repo_initialized):
        """测试本地分支检查（仅本地分支存在）"""
        import subprocess
        repo_path = temp_git_repo_initialized

        # 创建本地分支
        subprocess.run(["git", "checkout", "-b", "feature/test"], cwd=repo_path, capture_output=True)

        cmd = AddCommand(repo_path)
        exists, branch_type = cmd.check_branch_exists("feature/test", local=True)

        assert exists is True
        assert branch_type == "local"

    def test_check_branch_exists_local_not_found(self, temp_git_repo_initialized):
        """测试本地分支检查失败（分支不存在）"""
        cmd = AddCommand(temp_git_repo_initialized)

        with pytest.raises(GitException, match="本地分支不存在"):
            cmd.check_branch_exists("feature/nonexistent", local=True)

    def test_check_branch_exists_auto_detect(self, temp_git_repo_initialized):
        """测试自动检测本地分支"""
        import subprocess
        repo_path = temp_git_repo_initialized

        # 创建本地分支
        subprocess.run(["git", "checkout", "-b", "feature/auto"], cwd=repo_path, capture_output=True)

        cmd = AddCommand(repo_path)
        exists, branch_type = cmd.check_branch_exists("feature/auto", local=None)

        assert exists is True
        assert branch_type in ("local", "remote")

    def test_check_branch_exists_not_found(self, temp_git_repo_initialized):
        """测试分支检查失败（分支不存在）"""
        cmd = AddCommand(temp_git_repo_initialized)

        with pytest.raises(GitException, match="分支不存在"):
            cmd.check_branch_exists("feature/notfound", local=None)

    def test_map_branch_to_dir(self, temp_git_repo_initialized):
        """测试分支名映射到目录名"""
        cmd = AddCommand(temp_git_repo_initialized)

        # 简单分支名
        assert cmd.map_branch_to_dir("main") == "main"

        # 包含斜杠的分支名
        assert cmd.map_branch_to_dir("feature/new-ui") == "feature-new-ui"

        # 包含特殊字符的分支名
        assert cmd.map_branch_to_dir("fix(#123)") == "fix-123"

    def test_get_worktree_path(self, temp_git_repo_initialized):
        """测试 worktree 路径计算"""
        cmd = AddCommand(temp_git_repo_initialized)

        worktree_path = cmd.get_worktree_path("feature-test")

        assert worktree_path == temp_git_repo_initialized / ".gm" / "feature-test"

    def test_check_worktree_not_exists_success(self, temp_git_repo_initialized):
        """测试 worktree 不存在检查成功"""
        cmd = AddCommand(temp_git_repo_initialized)

        worktree_path = temp_git_repo_initialized / ".gm" / "feature-test"

        assert cmd.check_worktree_not_exists(worktree_path) is True

    def test_check_worktree_not_exists_failure(self, temp_git_repo_initialized):
        """测试 worktree 不存在检查失败"""
        repo_path = temp_git_repo_initialized

        # 预先创建 worktree 目录
        worktree_path = repo_path / ".gm" / "feature-test"
        worktree_path.mkdir(parents=True, exist_ok=True)

        cmd = AddCommand(repo_path)

        with pytest.raises(WorktreeAlreadyExists):
            cmd.check_worktree_not_exists(worktree_path)

    def test_create_worktree(self, temp_git_repo_initialized):
        """测试 worktree 创建"""
        import subprocess
        repo_path = temp_git_repo_initialized

        # 创建测试分支
        subprocess.run(["git", "checkout", "-b", "feature/create"], cwd=repo_path, capture_output=True)
        # 切换回主分支（worktree 不能用当前分支）
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, capture_output=True)

        cmd = AddCommand(repo_path)

        worktree_path = repo_path / ".gm" / "feature-create"

        cmd.create_worktree(worktree_path, "feature/create")

        # 验证 worktree 创建成功
        assert worktree_path.exists()
        assert (worktree_path / ".git").exists()

    def test_setup_symlinks(self, temp_git_repo_initialized):
        """测试符号链接设置"""
        import subprocess
        repo_path = temp_git_repo_initialized

        # 创建测试分支
        subprocess.run(["git", "checkout", "-b", "feature/symlinks"], cwd=repo_path, capture_output=True)
        # 切换回主分支
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, capture_output=True)

        cmd = AddCommand(repo_path)

        worktree_path = repo_path / ".gm" / "feature-symlinks"

        # 创建 worktree
        cmd.create_worktree(worktree_path, "feature/symlinks")

        # 设置符号链接
        cmd.setup_symlinks(worktree_path)

        # 验证符号链接
        readme_link = worktree_path / "README.md"
        assert readme_link.exists()

    def test_update_config(self, temp_git_repo_initialized):
        """测试配置文件更新"""
        repo_path = temp_git_repo_initialized

        cmd = AddCommand(repo_path)

        worktree_path = repo_path / ".gm" / "feature-update"

        cmd.update_config("feature/update", "feature-update", worktree_path)

        # 重新加载配置并验证
        import yaml
        config_file = repo_path / ".gm.yaml"
        with open(config_file) as f:
            config = yaml.safe_load(f)

        assert "worktrees" in config
        assert "feature-update" in config["worktrees"]
        assert config["worktrees"]["feature-update"]["branch"] == "feature/update"

    def test_execute_success(self, temp_git_repo_initialized):
        """测试执行成功"""
        import subprocess
        repo_path = temp_git_repo_initialized

        # 创建测试分支
        subprocess.run(["git", "checkout", "-b", "feature/execute"], cwd=repo_path, capture_output=True)
        # 切换回主分支
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, capture_output=True)

        cmd = AddCommand(repo_path)

        cmd.execute("feature/execute", local=True)

        # 验证 worktree 创建成功
        worktree_path = repo_path / ".gm" / "feature-execute"
        assert worktree_path.exists()

        # 验证配置更新
        import yaml
        config_file = repo_path / ".gm.yaml"
        with open(config_file) as f:
            config = yaml.safe_load(f)

        assert "worktrees" in config
        assert "feature-execute" in config["worktrees"]

    def test_execute_project_not_initialized(self, temp_git_repo_not_initialized):
        """测试执行时项目未初始化"""
        cmd = AddCommand(temp_git_repo_not_initialized)

        with pytest.raises(ConfigException, match="尚未初始化"):
            cmd.execute("feature/test")

    def test_execute_branch_not_found(self, temp_git_repo_initialized):
        """测试执行时分支不存在"""
        cmd = AddCommand(temp_git_repo_initialized)

        with pytest.raises(GitException, match="分支不存在"):
            cmd.execute("feature/nonexistent", local=True)

    def test_execute_worktree_already_exists(self, temp_git_repo_initialized):
        """测试执行时 worktree 已存在"""
        import subprocess
        repo_path = temp_git_repo_initialized

        # 创建测试分支
        subprocess.run(["git", "checkout", "-b", "feature/exists"], cwd=repo_path, capture_output=True)

        # 预先创建 worktree
        worktree_path = repo_path / ".gm" / "feature-exists"
        worktree_path.mkdir(parents=True, exist_ok=True)

        cmd = AddCommand(repo_path)

        with pytest.raises(WorktreeAlreadyExists):
            cmd.execute("feature/exists", local=True)

    def test_rollback_worktree(self, temp_git_repo_initialized):
        """测试 worktree 回滚"""
        import subprocess
        repo_path = temp_git_repo_initialized

        # 创建测试分支
        subprocess.run(["git", "checkout", "-b", "feature/rollback"], cwd=repo_path, capture_output=True)
        # 切换回主分支
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, capture_output=True)

        cmd = AddCommand(repo_path)

        worktree_path = repo_path / ".gm" / "feature-rollback"

        # 创建 worktree
        cmd.create_worktree(worktree_path, "feature/rollback")
        assert worktree_path.exists()

        # 回滚
        cmd._rollback_worktree(worktree_path)

        # 验证 worktree 被删除
        assert not worktree_path.exists()


class TestAddCommandIntegration:
    """添加命令集成测试"""

    @pytest.fixture
    def temp_git_repo_with_branches(self):
        """创建有多个分支的临时 git 仓库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            import subprocess
            # 初始化仓库
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)

            # 创建初始提交
            readme = repo_path / "README.md"
            readme.write_text("# Test Project\n")
            subprocess.run(["git", "add", "README.md"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

            # 创建多个分支
            subprocess.run(["git", "branch", "-M", "main"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "checkout", "-b", "develop"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "checkout", "-b", "feature/test"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "checkout", "main"], cwd=repo_path, capture_output=True)

            # 初始化 .gm 项目
            gm_dir = repo_path / ".gm"
            gm_dir.mkdir()

            config_file = repo_path / ".gm.yaml"
            config_file.write_text("""
initialized: true
main_branch: main
worktree:
  base_path: .gm
  naming_pattern: '{branch}'
shared_files:
  - README.md
""")

            yield repo_path

    def test_full_add_flow(self, temp_git_repo_with_branches):
        """测试完整的添加流程"""
        repo_path = temp_git_repo_with_branches

        cmd = AddCommand(repo_path)

        cmd.execute("feature/test", local=True)

        # 验证 worktree 创建成功
        worktree_path = repo_path / ".gm" / "feature-test"
        assert worktree_path.exists()

        # 验证配置更新
        import yaml
        config_file = repo_path / ".gm.yaml"
        with open(config_file) as f:
            config = yaml.safe_load(f)

        assert "worktrees" in config
        assert "feature-test" in config["worktrees"]
        assert config["worktrees"]["feature-test"]["branch"] == "feature/test"

    def test_add_multiple_worktrees(self, temp_git_repo_with_branches):
        """测试添加多个 worktree"""
        repo_path = temp_git_repo_with_branches

        cmd = AddCommand(repo_path)

        # 添加第一个 worktree
        cmd.execute("develop", local=True)
        assert (repo_path / ".gm" / "develop").exists()

        # 添加第二个 worktree
        cmd.execute("feature/test", local=True)
        assert (repo_path / ".gm" / "feature-test").exists()

        # 验证配置
        import yaml
        config_file = repo_path / ".gm.yaml"
        with open(config_file) as f:
            config = yaml.safe_load(f)

        assert len(config["worktrees"]) == 2
        assert "develop" in config["worktrees"]
        assert "feature-test" in config["worktrees"]

    def test_add_with_special_characters(self, temp_git_repo_with_branches):
        """测试添加分支名包含特殊字符的 worktree"""
        import subprocess
        repo_path = temp_git_repo_with_branches

        # 创建特殊字符的分支
        subprocess.run(["git", "checkout", "-b", "fix/issue-#123"], cwd=repo_path, capture_output=True)
        # 切换回主分支
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, capture_output=True)

        cmd = AddCommand(repo_path)

        cmd.execute("fix/issue-#123", local=True)

        # 验证目录名正确映射
        worktree_path = repo_path / ".gm" / "fix-issue-123"
        assert worktree_path.exists()
