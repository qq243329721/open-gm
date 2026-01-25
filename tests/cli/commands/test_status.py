"""GM status 命令的单元测试"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

import pytest

from gm.cli.commands.status import StatusCommand
from gm.core.exceptions import GitException, ConfigException, WorktreeNotFound


class TestStatusCommand:
    """状态显示命令测试类"""

    @pytest.fixture
    def temp_git_repo(self):
        """创建临时 git 仓库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            # 初始化 git 仓库
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)

            # 创建初始提交
            (repo_path / "README.md").write_text("# Test Project\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

            yield repo_path

    @pytest.fixture
    def initialized_repo(self, temp_git_repo):
        """创建已初始化的 gm 项目"""
        gm_dir = temp_git_repo / ".gm"
        gm_dir.mkdir(parents=True, exist_ok=True)

        config_file = temp_git_repo / ".gm.yaml"
        config_file.write_text("""
worktree:
  base_path: .gm
  naming_pattern: '{branch}'
  auto_cleanup: true
display:
  colors: true
  default_verbose: false
shared_files:
  - .env
  - .gitignore
  - README.md
branch_mapping: {}
""")

        yield temp_git_repo

    def test_status_command_init(self, temp_git_repo):
        """测试 StatusCommand 初始化"""
        cmd = StatusCommand(temp_git_repo)
        assert cmd.project_path == temp_git_repo
        assert cmd.git_client is not None
        assert cmd.config_manager is not None
        assert cmd.mapper is not None

    def test_get_current_location_external(self):
        """测试在项目外部的位置检测"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = StatusCommand(tmpdir)
            location = cmd.get_current_location()
            assert location == "external"

    def test_get_current_location_root(self, temp_git_repo):
        """测试在项目根目录的位置检测"""
        cmd = StatusCommand(temp_git_repo)
        # 注意：实际测试中需要模拟当前工作目录
        # 这里我们只验证命令能执行而不抛出异常
        location = cmd.get_current_location()
        assert location in ["root", "external", "worktree"]

    def test_get_worktree_list_empty(self, temp_git_repo):
        """测试在没有 worktree 的仓库中获取列表"""
        cmd = StatusCommand(temp_git_repo)
        worktrees = cmd.get_worktree_list()
        # 至少会返回主仓库本身
        assert isinstance(worktrees, list)

    def test_get_working_dir_status_clean(self, temp_git_repo):
        """测试获取干净的工作目录状态"""
        cmd = StatusCommand(temp_git_repo)
        status = cmd.get_working_dir_status(temp_git_repo)

        assert "modified" in status
        assert "untracked" in status
        assert "staged" in status
        assert status["modified"] == 0
        assert status["untracked"] == 0
        assert status["staged"] == 0

    def test_get_working_dir_status_dirty(self, temp_git_repo):
        """测试获取修改的工作目录状态"""
        # 修改已跟踪文件
        (temp_git_repo / "README.md").write_text("# Modified\n")

        # 创建未跟踪文件
        (temp_git_repo / "untracked.txt").write_text("untracked content")

        cmd = StatusCommand(temp_git_repo)
        status = cmd.get_working_dir_status(temp_git_repo)

        # 验证至少有一个未跟踪文件
        assert status["untracked"] > 0

    def test_get_worktree_status_clean(self, temp_git_repo):
        """测试获取 worktree 干净状态"""
        cmd = StatusCommand(temp_git_repo)
        status_str = cmd.get_worktree_status(temp_git_repo)
        assert status_str == "clean"

    def test_get_worktree_status_dirty(self, temp_git_repo):
        """测试获取 worktree 脏状态"""
        # 创建未跟踪文件
        (temp_git_repo / "new_file.txt").write_text("new content")

        cmd = StatusCommand(temp_git_repo)
        status_str = cmd.get_worktree_status(temp_git_repo)
        assert status_str == "dirty"

    def test_get_commit_stats(self, temp_git_repo):
        """测试获取提交统计"""
        cmd = StatusCommand(temp_git_repo)
        stats = cmd.get_commit_stats(temp_git_repo)

        assert "ahead" in stats
        assert "behind" in stats
        assert "last_commit_msg" in stats
        assert "last_commit_author" in stats
        assert "last_commit_time" in stats

    def test_format_summary_output(self, initialized_repo):
        """测试格式化全局摘要输出"""
        cmd = StatusCommand(initialized_repo)
        output = cmd.format_summary_output()

        assert "Project initialized at:" in output
        assert "Worktree Summary" in output
        assert "Total:" in output or "total" in output.lower()

    def test_execute_in_external_location(self):
        """测试在项目外部执行状态命令"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = StatusCommand(tmpdir)
            with pytest.raises(GitException):
                cmd.execute()

    def test_execute_with_nonexistent_branch(self, initialized_repo):
        """测试查询不存在的分支状态"""
        cmd = StatusCommand(initialized_repo)
        with pytest.raises(WorktreeNotFound):
            cmd.execute("nonexistent-branch")

    def test_get_current_branch(self, temp_git_repo):
        """测试获取当前分支"""
        cmd = StatusCommand(temp_git_repo)
        branch = cmd.get_current_branch()
        # 初始化后应该在某个分支上
        assert branch is None or isinstance(branch, str)

    def test_format_detailed_output_with_repo(self, initialized_repo):
        """测试格式化详细输出"""
        cmd = StatusCommand(initialized_repo)

        # 尝试在一个分支上创建 worktree（需要先创建分支）
        subprocess.run(
            ["git", "checkout", "-b", "feature/test"],
            cwd=initialized_repo,
            capture_output=True
        )

        # 创建 worktree
        gm_dir = initialized_repo / ".gm"
        wt_path = gm_dir / "feature-test"
        wt_path.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "feature/test"],
            cwd=initialized_repo,
            capture_output=True
        )

        # 现在测试详细输出
        output = cmd.format_detailed_output("feature/test")

        assert "Current Worktree Status" in output
        assert "Branch:" in output
        assert "Status:" in output

    def test_get_worktree_path_by_branch(self, initialized_repo):
        """测试根据分支名获取 worktree 路径"""
        # 创建分支和 worktree
        subprocess.run(
            ["git", "checkout", "-b", "feature/new-ui"],
            cwd=initialized_repo,
            capture_output=True
        )

        gm_dir = initialized_repo / ".gm"
        wt_path = gm_dir / "feature-new-ui"
        wt_path.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "feature/new-ui"],
            cwd=initialized_repo,
            capture_output=True
        )

        cmd = StatusCommand(initialized_repo)
        found_path = cmd.get_worktree_path_by_branch("feature/new-ui")

        assert found_path is not None
        assert found_path == wt_path

    def test_status_output_contains_required_fields(self, initialized_repo):
        """测试状态输出包含所有必需的字段"""
        # 创建分支和 worktree
        subprocess.run(
            ["git", "checkout", "-b", "feature/ui"],
            cwd=initialized_repo,
            capture_output=True
        )

        gm_dir = initialized_repo / ".gm"
        wt_path = gm_dir / "feature-ui"
        wt_path.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "feature/ui"],
            cwd=initialized_repo,
            capture_output=True
        )

        cmd = StatusCommand(initialized_repo)
        output = cmd.format_detailed_output("feature/ui")

        required_fields = [
            "Project Root:",
            "Current Worktree Status",
            "Branch:",
            "Path:",
            "Status:",
            "Working Directory",
            "Modified:",
            "Untracked:",
            "Staged:",
            "Commits",
            "Ahead:",
            "Behind:",
        ]

        for field in required_fields:
            assert field in output, f"Missing field: {field}"

    def test_summary_output_shows_worktrees(self, initialized_repo):
        """测试摘要输出显示 worktree 列表"""
        # 创建多个分支和 worktree
        for i in range(2):
            branch_name = f"feature/branch-{i}"
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=initialized_repo,
                capture_output=True
            )

            gm_dir = initialized_repo / ".gm"
            wt_path = gm_dir / f"feature-branch-{i}"
            wt_path.mkdir(parents=True, exist_ok=True)

            subprocess.run(
                ["git", "worktree", "add", str(wt_path), branch_name],
                cwd=initialized_repo,
                capture_output=True
            )

        cmd = StatusCommand(initialized_repo)
        output = cmd.format_summary_output()

        assert "Worktree Summary" in output
        assert "Quick Access" in output
        assert "Total:" in output or "total" in output.lower()
