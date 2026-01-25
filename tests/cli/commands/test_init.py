"""GM init 命令的单元测试"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from gm.cli.commands.init import InitCommand
from gm.core.exceptions import GitException, ConfigException


class TestInitCommand:
    """初始化命令测试类"""

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
            yield repo_path

    def test_validate_project_success(self, temp_git_repo):
        """测试项目验证成功"""
        cmd = InitCommand(temp_git_repo)
        assert cmd.validate_project() is True

    def test_validate_project_failure(self, tmp_path):
        """测试项目验证失败（非 git 仓库）"""
        cmd = InitCommand(tmp_path)
        with pytest.raises(GitException):
            cmd.validate_project()

    def test_check_already_initialized_false(self, temp_git_repo):
        """测试项目未初始化"""
        cmd = InitCommand(temp_git_repo)
        assert cmd.check_already_initialized() is False

    def test_check_already_initialized_true(self, temp_git_repo):
        """测试项目已初始化（.gm 目录存在）"""
        gm_dir = temp_git_repo / ".gm"
        gm_dir.mkdir()

        cmd = InitCommand(temp_git_repo)
        assert cmd.check_already_initialized() is True

    def test_check_already_initialized_with_config(self, temp_git_repo):
        """测试项目已初始化（.gm.yaml 文件存在）"""
        config_file = temp_git_repo / ".gm.yaml"
        config_file.write_text("initialized: true\n")

        cmd = InitCommand(temp_git_repo)
        assert cmd.check_already_initialized() is True

    def test_create_directory_structure(self, temp_git_repo):
        """测试目录结构创建"""
        cmd = InitCommand(temp_git_repo)
        cmd.create_directory_structure()

        gm_dir = temp_git_repo / ".gm"
        assert gm_dir.exists()
        assert gm_dir.is_dir()

    def test_create_config(self, temp_git_repo):
        """测试配置文件创建"""
        cmd = InitCommand(temp_git_repo)
        cmd.create_config(use_local=True, main_branch="main")

        config_file = temp_git_repo / ".gm.yaml"
        assert config_file.exists()

        # 验证配置内容
        import yaml
        with open(config_file) as f:
            config = yaml.safe_load(f)

        assert config["initialized"] is True
        assert config["use_local_branch"] is True
        assert config["main_branch"] == "main"

    def test_create_config_with_defaults(self, temp_git_repo):
        """测试配置文件包含默认值"""
        cmd = InitCommand(temp_git_repo)
        cmd.create_config(use_local=False, main_branch="master")

        config_file = temp_git_repo / ".gm.yaml"

        import yaml
        with open(config_file) as f:
            config = yaml.safe_load(f)

        # 验证默认配置存在
        assert "worktree" in config
        assert "display" in config
        assert "shared_files" in config

    def test_setup_shared_files(self, temp_git_repo):
        """测试共享文件设置"""
        cmd = InitCommand(temp_git_repo)
        # 不应该抛出异常
        cmd.setup_shared_files("main")

    def test_rollback_directory(self, temp_git_repo):
        """测试目录回滚"""
        cmd = InitCommand(temp_git_repo)

        # 创建目录
        cmd.create_directory_structure()
        gm_dir = temp_git_repo / ".gm"
        assert gm_dir.exists()

        # 回滚
        cmd._rollback_directory()
        assert not gm_dir.exists()

    def test_rollback_config(self, temp_git_repo):
        """测试配置文件回滚"""
        cmd = InitCommand(temp_git_repo)

        # 创建配置
        cmd.create_config(use_local=True, main_branch="main")
        config_file = temp_git_repo / ".gm.yaml"
        assert config_file.exists()

        # 回滚
        cmd._rollback_config()
        assert not config_file.exists()

    def test_execute_success(self, temp_git_repo):
        """测试执行成功"""
        cmd = InitCommand(temp_git_repo)

        with patch.object(cmd, 'get_branch_config', return_value=(True, 'main')):
            cmd.execute()

        # 验证目录结构
        assert (temp_git_repo / ".gm").exists()

        # 验证配置文件
        assert (temp_git_repo / ".gm.yaml").exists()

    def test_execute_already_initialized(self, temp_git_repo):
        """测试执行时项目已初始化"""
        # 预先初始化
        gm_dir = temp_git_repo / ".gm"
        gm_dir.mkdir()

        cmd = InitCommand(temp_git_repo)

        with pytest.raises(Exception, match="已初始化"):
            cmd.execute()

    def test_execute_not_git_repo(self, tmp_path):
        """测试执行时不是 git 仓库"""
        cmd = InitCommand(tmp_path)

        with pytest.raises(GitException):
            cmd.execute()

    def test_get_branch_config(self, temp_git_repo):
        """测试交互式分支配置"""
        cmd = InitCommand(temp_git_repo)

        with patch('click.confirm', return_value=True):
            with patch('click.prompt', return_value='main'):
                use_local, main_branch = cmd.get_branch_config()

        assert use_local is True
        assert main_branch == 'main'

    def test_transaction_rollback_on_failure(self, temp_git_repo):
        """测试事务失败时回滚"""
        cmd = InitCommand(temp_git_repo)

        # 模拟配置创建失败
        with patch.object(cmd, 'get_branch_config', return_value=(True, 'main')):
            with patch.object(cmd, 'create_config', side_effect=ConfigException("配置失败")):
                from gm.core.exceptions import TransactionRollbackError

                with pytest.raises(TransactionRollbackError):
                    cmd.execute()

        # 验证目录被回滚
        gm_dir = temp_git_repo / ".gm"
        assert not gm_dir.exists()

    def test_config_validation(self, temp_git_repo):
        """测试配置验证"""
        cmd = InitCommand(temp_git_repo)
        cmd.create_config(use_local=True, main_branch="develop")

        # 重新加载并验证配置
        import yaml
        config_file = temp_git_repo / ".gm.yaml"
        with open(config_file) as f:
            config = yaml.safe_load(f)

        # 验证配置结构
        assert isinstance(config, dict)
        assert config.get("initialized") is True
        assert config.get("main_branch") == "develop"

    def test_execute_creates_all_required_files(self, temp_git_repo):
        """测试执行创建所有必要文件"""
        cmd = InitCommand(temp_git_repo)

        with patch.object(cmd, 'get_branch_config', return_value=(True, 'main')):
            cmd.execute()

        # 验证 .gm 目录
        assert (temp_git_repo / ".gm").exists()

        # 验证 .gm.yaml 配置文件
        assert (temp_git_repo / ".gm.yaml").exists()


class TestInitCommandIntegration:
    """初始化命令集成测试"""

    @pytest.fixture
    def temp_git_repo_with_commits(self):
        """创建有提交的临时 git 仓库"""
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

            # 创建 main 分支
            subprocess.run(["git", "branch", "-M", "main"], cwd=repo_path, capture_output=True)

            yield repo_path

    def test_full_initialization_flow(self, temp_git_repo_with_commits):
        """测试完整初始化流程"""
        cmd = InitCommand(temp_git_repo_with_commits)

        with patch.object(cmd, 'get_branch_config', return_value=(True, 'main')):
            cmd.execute()

        # 验证所有必要的文件和目录
        assert (temp_git_repo_with_commits / ".gm").exists()
        assert (temp_git_repo_with_commits / ".gm.yaml").exists()

        # 验证配置内容
        import yaml
        config_file = temp_git_repo_with_commits / ".gm.yaml"
        with open(config_file) as f:
            config = yaml.safe_load(f)

        assert config["initialized"] is True
        assert config["main_branch"] == "main"
