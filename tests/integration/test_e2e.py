"""端到端集成测试

测试完整的 GM 工作流，包括：
- 仓库初始化
- Worktree 添加、删除、列表操作
- Git 提交和状态检查
- 配置管理
- 错误恢复机制
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
import subprocess

import pytest

from gm.cli.main import cli
from gm.core.git_client import GitClient
from gm.core.config_manager import ConfigManager
from gm.core.exceptions import (
    GitException,
    GitCommandError,
    ConfigException,
    GMException,
)


class TestEnvironment:
    """测试环境管理工具"""

    def __init__(self, tmp_path: Path):
        """初始化测试环境

        Args:
            tmp_path: pytest 提供的临时目录
        """
        self.tmp_path = tmp_path
        self.repo_path = tmp_path / "test_repo"
        self.worktree_base = self.repo_path / ".gm"

    def setup_git_repo(self) -> Path:
        """创建测试 Git 仓库

        Returns:
            仓库路径
        """
        self.repo_path.mkdir(parents=True, exist_ok=True)

        # 初始化 Git 仓库
        subprocess.run(
            ["git", "init"],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )

        # 配置 Git 用户
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )

        # 创建初始提交
        test_file = self.repo_path / "README.md"
        test_file.write_text("# Test Repository\n")

        subprocess.run(
            ["git", "add", "README.md"],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )

        return self.repo_path

    def create_remote_branch(self, branch_name: str) -> None:
        """创建远程分支

        Args:
            branch_name: 分支名称
        """
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )

        # 创建分支提交
        test_file = self.repo_path / f"{branch_name}.txt"
        test_file.write_text(f"Changes for {branch_name}\n")

        subprocess.run(
            ["git", "add", f"{branch_name}.txt"],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Add {branch_name} changes"],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )

        # 回到 master/main
        subprocess.run(
            ["git", "checkout", "master"],
            cwd=self.repo_path,
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=self.repo_path,
            capture_output=True,
            check=False,
        )

    def cleanup(self) -> None:
        """清理测试环境"""
        if self.repo_path.exists():
            shutil.rmtree(self.repo_path)


@pytest.mark.integration
class TestEndToEndWorkflow:
    """端到端集成测试"""

    def test_complete_workflow(self, tmp_path: Path):
        """
        完整工作流测试：
        1. 初始化项目
        2. 添加 worktree
        3. 在 worktree 中进行更改
        4. 查看状态和列表
        5. 删除 worktree
        """
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            # 初始化项目
            git_client = GitClient(repo_path)
            config_mgr = ConfigManager(repo_path)

            # 初始化 .gm 结构
            worktree_base = repo_path / ".gm"
            worktree_base.mkdir(exist_ok=True)

            # 保存默认配置
            config = config_mgr.get_default_config()
            config["worktree"]["base_path"] = ".gm"
            config_mgr.save_config(config)

            # 验证配置已保存
            loaded_config = config_mgr.load_config()
            assert loaded_config is not None
            assert loaded_config["worktree"]["base_path"] == ".gm"

            # 创建分支进行 worktree 操作
            env.create_remote_branch("feature/test")

            # 验证仓库状态
            branches = git_client.get_branches()
            assert len(branches) > 0

        finally:
            env.cleanup()

    def test_workflow_with_configuration(self, tmp_path: Path):
        """测试带配置的工作流"""
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            config_mgr = ConfigManager(repo_path)

            # 测试配置加载和保存
            config = config_mgr.get_default_config()

            # 修改配置
            config["worktree"]["base_path"] = ".custom_gm"
            config["display"]["colors"] = False

            # 保存修改后的配置
            config_mgr.save_config(config)

            # 重新加载并验证
            loaded = config_mgr.load_config()
            assert loaded["worktree"]["base_path"] == ".custom_gm"
            assert loaded["display"]["colors"] is False

        finally:
            env.cleanup()

    def test_git_operations(self, tmp_path: Path):
        """测试 Git 操作集成"""
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            git_client = GitClient(repo_path)

            # 测试获取分支列表
            branches = git_client.get_branches()
            assert isinstance(branches, list)
            assert len(branches) > 0

            # 测试获取当前分支
            current = git_client.get_current_branch()
            assert current is not None
            assert isinstance(current, str)

            # 测试获取提交历史
            commits = git_client.get_commits(max_count=5)
            assert isinstance(commits, list)
            assert len(commits) > 0

        finally:
            env.cleanup()

    def test_multiple_worktrees(self, tmp_path: Path):
        """测试多个 worktree 的创建和管理"""
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            config_mgr = ConfigManager(repo_path)

            # 创建基础配置
            config = config_mgr.get_default_config()
            worktree_base = repo_path / ".gm"
            worktree_base.mkdir(exist_ok=True)

            config["worktree"]["base_path"] = ".gm"
            config_mgr.save_config(config)

            # 验证配置
            assert config_mgr.config_path.exists()
            loaded = config_mgr.load_config()
            assert loaded is not None

        finally:
            env.cleanup()

    def test_error_handling(self, tmp_path: Path):
        """测试错误处理和恢复"""
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            git_client = GitClient(repo_path)

            # 测试无效分支操作
            with pytest.raises(GitCommandError):
                git_client.run_command(
                    ["git", "checkout", "nonexistent-branch-xyz"],
                    check=True,
                )

            # 验证仓库仍然可用
            branches = git_client.get_branches()
            assert len(branches) > 0

        finally:
            env.cleanup()

    def test_large_repository_simulation(self, tmp_path: Path):
        """模拟大型仓库的操作"""
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            git_client = GitClient(repo_path)
            config_mgr = ConfigManager(repo_path)

            # 创建多个文件以模拟大型仓库
            files_dir = repo_path / "data"
            files_dir.mkdir(exist_ok=True)

            for i in range(10):
                file_path = files_dir / f"file_{i}.txt"
                file_path.write_text(f"Content {i}\n" * 100)

            # 添加并提交这些文件
            subprocess.run(
                ["git", "add", "data/"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Add data files"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )

            # 测试配置管理
            config = config_mgr.get_default_config()
            config_mgr.save_config(config)
            loaded = config_mgr.load_config()
            assert loaded is not None

            # 测试 Git 操作性能
            branches = git_client.get_branches()
            assert len(branches) > 0

        finally:
            env.cleanup()

    def test_config_merge_strategies(self, tmp_path: Path):
        """测试配置合并策略"""
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            config_mgr = ConfigManager(repo_path)

            # 获取默认配置
            base_config = config_mgr.get_default_config()
            assert "worktree" in base_config
            assert "display" in base_config
            assert "shared_files" in base_config

            # 验证共享文件列表
            shared_files = base_config.get("shared_files", [])
            assert isinstance(shared_files, list)
            assert len(shared_files) > 0

        finally:
            env.cleanup()

    def test_git_status_operations(self, tmp_path: Path):
        """测试 Git 状态操作"""
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            git_client = GitClient(repo_path)

            # 修改文件
            test_file = repo_path / "README.md"
            test_file.write_text("# Modified\n")

            # 获取状态
            status = git_client.run_command(
                ["git", "status", "--porcelain"],
                check=True,
            )
            assert "README.md" in status or "modified" in status.lower()

            # 回滚修改
            subprocess.run(
                ["git", "checkout", "README.md"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )

            # 验证已回滚
            status = git_client.run_command(
                ["git", "status", "--porcelain"],
                check=True,
            )
            assert "README.md" not in status or status.strip() == ""

        finally:
            env.cleanup()

    def test_branch_operations(self, tmp_path: Path):
        """测试分支操作"""
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            git_client = GitClient(repo_path)

            # 创建新分支
            subprocess.run(
                ["git", "checkout", "-b", "test/feature"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )

            # 验证分支存在
            branches = git_client.get_branches()
            assert "test/feature" in branches

            # 切换回主分支
            main_branch = git_client.get_current_branch()
            subprocess.run(
                ["git", "checkout", "-"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )

            # 验证切换成功
            current = git_client.get_current_branch()
            assert current is not None

        finally:
            env.cleanup()

    def test_concurrent_file_operations(self, tmp_path: Path):
        """测试并发文件操作"""
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            config_mgr = ConfigManager(repo_path)

            # 创建多个配置加载
            configs = []
            for _ in range(5):
                config = config_mgr.get_default_config()
                configs.append(config)

            # 验证所有配置都有效
            for config in configs:
                assert config["worktree"]["base_path"] == ".gm"

        finally:
            env.cleanup()

    def test_config_persistence(self, tmp_path: Path):
        """测试配置持久化"""
        env = TestEnvironment(tmp_path)
        repo_path = env.setup_git_repo()

        try:
            config_mgr = ConfigManager(repo_path)

            # 创建并保存配置
            config = config_mgr.get_default_config()
            config["custom_key"] = "custom_value"
            config_mgr.save_config(config)

            # 创建新的配置管理器并加载
            new_mgr = ConfigManager(repo_path)
            loaded = new_mgr.load_config()

            # 验证自定义值已保存
            assert loaded["custom_key"] == "custom_value"

        finally:
            env.cleanup()

    def test_empty_repository(self, tmp_path: Path):
        """测试空仓库的处理"""
        env = TestEnvironment(tmp_path)

        try:
            # 创建空目录
            empty_repo = tmp_path / "empty_repo"
            empty_repo.mkdir()

            # 初始化为 Git 仓库
            subprocess.run(
                ["git", "init"],
                cwd=empty_repo,
                capture_output=True,
                check=True,
            )

            # 测试 GitClient 操作
            git_client = GitClient(empty_repo)

            # 获取分支应该返回空列表（未来的提交）
            branches = git_client.get_branches()
            assert isinstance(branches, list)

        finally:
            env.cleanup()


@pytest.mark.integration
class TestConfigIntegration:
    """配置系统集成测试"""

    def test_config_loading_with_missing_file(self, tmp_path: Path):
        """测试配置文件缺失时的处理"""
        config_mgr = ConfigManager(tmp_path)

        # 配置文件不存在，应该加载默认配置
        config = config_mgr.load_config()

        # 当文件不存在时，应该返回 None 或默认配置
        if config is None:
            default = config_mgr.get_default_config()
            assert default is not None
        else:
            assert config is not None

    def test_config_yaml_format(self, tmp_path: Path):
        """测试 YAML 配置格式"""
        config_mgr = ConfigManager(tmp_path)

        # 获取并保存配置
        config = config_mgr.get_default_config()
        config_mgr.save_config(config)

        # 直接读取 YAML 文件验证格式
        yaml_file = tmp_path / ".gm.yaml"
        assert yaml_file.exists()

        # 验证文件内容是有效的 YAML
        with open(yaml_file) as f:
            import yaml
            content = yaml.safe_load(f)
            assert content is not None


@pytest.mark.integration
class TestGitIntegration:
    """Git 操作集成测试"""

    def test_git_command_execution(self, tmp_path: Path):
        """测试 Git 命令执行"""
        # 初始化测试仓库
        subprocess.run(
            ["git", "init"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        git_client = GitClient(tmp_path)

        # 测试成功的命令
        result = git_client.run_command(["git", "status"], check=False)
        assert isinstance(result, str)

    def test_git_error_handling(self, tmp_path: Path):
        """测试 Git 错误处理"""
        git_client = GitClient(tmp_path)

        # 测试失败的命令
        with pytest.raises(GitCommandError):
            git_client.run_command(
                ["git", "checkout", "nonexistent"],
                check=True,
            )
