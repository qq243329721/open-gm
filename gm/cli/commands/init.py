"""GM init 命令实现

初始化项目为 .gm worktree 结构，创建配置文件和目录结构。"""

import os
import re
import shutil
from pathlib import Path
from typing import Optional
import click

from gm.core.config_manager import ConfigManager
from gm.core.exceptions import GitException, ConfigException
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.core.transaction import Transaction
from gm.core.data_structures import GMConfig
from gm.cli.utils.formatting import OutputFormatter
from gm.cli.utils.project_utils import find_gm_root_optional

logger = get_logger("init_command")


class InitCommand:
    """项目初始化命令处理器"""

    def __init__(self, project_path: Optional[Path] = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.git_client = GitClient(self.project_path)
        self.config_manager = ConfigManager(self.project_path)
        self.repo_root: Optional[Path] = None

    def validate_project(self) -> Path:
        """验证是否为有效的 Git 仓库，并返回仓库根目录路径

        Returns:
            仓库根目录的绝对路径

        Raises:
            ConfigException: 如果不是有效的 Git 仓库
        """
        try:
            repo_root = self.git_client.get_repo_root()
            self.repo_root = Path(repo_root).resolve()
            return self.repo_root
        except GitException:
            raise ConfigException("当前目录不是 Git 仓库，请先运行 'git init'。")

    def check_already_initialized(self) -> tuple[bool, Optional[Path]]:
        """检查项目或其父目录是否已初始化

        Returns:
            (is_initialized, gm_root_path) 元组
            - is_initialized: True 如果已初始化
            - gm_root_path: GM 项目根目录路径，如果未初始化则为 None
        """
        # 首先检查指定路径
        config_file = self.project_path / "gm.yaml"
        gm_dir = self.project_path / ".gm"

        if config_file.exists() or gm_dir.exists():
            return True, self.project_path

        # 然后向上查找
        existing_root = find_gm_root_optional(self.project_path)
        if existing_root:
            return True, existing_root

        return False, None

    def create_directory_structure(self) -> None:
        """创建 .gm 目录结构"""
        gm_dir = self.project_path / ".gm"
        gm_dir.mkdir(exist_ok=True)
        (gm_dir / "worktrees").mkdir(exist_ok=True)
        (gm_dir / "logs").mkdir(exist_ok=True)
        logger.info("Directory structure created")

    def _rollback_directory(self) -> None:
        """回滚目录创建"""
        import shutil
        gm_dir = self.project_path / ".gm"
        if gm_dir.exists():
            shutil.rmtree(gm_dir)

    def _rollback_config(self) -> None:
        """回滚配置创建"""
        config_file = self.project_path / "gm.yaml"
        if config_file.exists():
            config_file.unlink()

    def setup_shared_files(self, main_branch: str) -> None:
        """设置共享文件配置"""
        logger.info("Shared files setup for branch", main_branch=main_branch)

    def _normalize_branch_name(self, branch_name: str) -> str:
        """规范化分支名称，将特殊符号替换为-

        Args:
            branch_name: 原始分支名称

        Returns:
            规范化后的分支名称
        """
        # 将特殊符号替换为短横线
        normalized = re.sub(r'[^a-zA-Z0-9_-]', '-', branch_name)
        # 将连续的短横线替换为单个短横线
        normalized = re.sub(r'-+', '-', normalized)
        # 移除开头和结尾的短横线
        normalized = normalized.strip('-')
        return normalized

    def _convert_to_bare_and_move_git(self) -> None:
        """移动 .git 目录到 .gm/.git，然后生成 .git 文件指向 .gm/.git
        """
        git_src = self.project_path / ".git"
        gm_git_dst = self.project_path / ".gm" / ".git"
        git_file = self.project_path / ".git"

        if git_src.exists() and not gm_git_dst.exists():
            # 1. 移动 .git 目录到 .gm/.git
            shutil.move(str(git_src), str(gm_git_dst))

            # 2. 生成 .git 文件，指向 .gm/.git（使用绝对路径）
            absolute_git_path = self.project_path.resolve() / ".gm" / ".git"
            git_file_content = f"gitdir: {absolute_git_path}"
            with open(git_file, 'w', encoding='utf-8') as f:
                f.write(git_file_content)

            logger.info("Git directory moved and .git file created with absolute path",
                       src=str(git_src), dst=str(gm_git_dst), git_file=str(git_file),
                       git_target=str(absolute_git_path))

    def _create_worktree_directory(self, branch: str) -> None:
        """创建主分支对应的 worktree 目录

        Args:
            branch: 分支名称
        """
        worktree_dir = self.project_path / branch
        worktree_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created worktree directory", path=str(worktree_dir), branch=branch)

    def _move_working_files(self, branch: str) -> None:
        """将工作区文件移到 worktree 目录

        Args:
            branch: 分支名称
        """
        worktree_dir = self.project_path / branch

        # 需要忽略的文件/目录
        # 注意：根目录的.git文件(指向.gm/.git的gitdir文件)会被移动到分支文件夹
        ignore_items = {".gm", "gm.yaml", branch}

        # 移动普通文件和目录到分支目录
        for item in os.listdir(self.project_path):
            if item not in ignore_items:
                src = self.project_path / item
                dst = worktree_dir / item

                if src.is_dir():
                    shutil.move(str(src), str(dst))
                else:
                    shutil.move(str(src), str(dst))

                logger.info("Moved item to worktree", item=item, src=str(src), dst=str(dst))

    def _create_complete_config(self, main_branch: str) -> None:
        """创建包含完整项目信息的配置文件

        Args:
            main_branch: 主分支名称
        """
        # 加载默认配置
        config = self.config_manager.get_default_config()

        # 设置基本配置
        config.initialized = True
        config.use_local_branch = True
        config.main_branch = main_branch

        # 设置项目信息
        config.project_name = self.project_path.name
        config.home_path = str(self.project_path.resolve())

        # 尝试获取远程 URL
        try:
            gm_path = self.project_path / ".gm"
            git_client = GitClient(gm_path)
            remotes = git_client.run_command(["remote", "-v"])
            if remotes:
                # 解析 origin 的 URL
                for line in remotes.split('\n'):
                    if line.startswith('origin') and '(fetch)' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            config.remote_url = parts[1]
                            break
        except Exception:
            config.remote_url = None

        # 设置分支映射（原始分支名 -> 规范化的文件夹名）
        try:
            # GitClient 应该在 .gm 目录执行命令（GM 项目的 git 仓库在 .gm/.git）
            gm_path = self.project_path / ".gm"
            git_client = GitClient(gm_path)
            original_branch = git_client.get_current_branch() or main_branch
            config.branch_mapping[original_branch] = main_branch
        except Exception:
            # 如果获取原始分支失败，只设置规范化后的分支名
            config.branch_mapping[main_branch] = main_branch

        # 保存配置
        self.config_manager.save_config(config)

        logger.info("Complete configuration created",
                   project_name=config.project_name,
                   home_path=config.home_path,
                   remote_url=config.remote_url,
                   main_branch=main_branch)

    def execute(self, yes: bool = False) -> None:
        """执行初始化"""
        # 验证并获取仓库根目录
        repo_root = self.validate_project()

        # 检查当前工作目录是否是仓库根目录
        current_working_dir = Path.cwd().resolve()
        if current_working_dir != repo_root:
            try:
                relative_path = current_working_dir.relative_to(repo_root)
                click.echo("✗ 无法在子目录中执行 gm init")
                click.echo(f"  当前位置: {relative_path}")
            except ValueError:
                click.echo("✗ 当前工作目录不在 Git 仓库中")
            click.echo(f"  仓库根目录: {repo_root}")
            click.echo("")
            click.echo("请切换到仓库根目录后重新执行:")
            click.echo(f"  cd {repo_root}")
            click.echo("  gm init")
            return

        is_initialized, existing_root = self.check_already_initialized()
        if is_initialized:
            if existing_root == self.project_path:
                click.echo("✓ 当前目录已经是 GM 项目。")
            else:
                click.echo("✗ 无法初始化：当前目录或其父目录已是 GM 项目")
                click.echo(f"  已存在的 GM 项目路径: {existing_root}")
                click.echo("  提示: 使用 'gm add <分支名>' 在当前 GM 项目中添加 worktree")
            return

        # 获取当前分支作为主分支
        main_branch: str = "main"
        try:
            current_branch = self.git_client.get_current_branch()
            main_branch = current_branch or "main"
        except Exception:
            main_branch = "main"

        # 规范化分支名称
        normalized_main_branch = self._normalize_branch_name(main_branch)

        # 检查 .git 目录是否存在（已存在的 git 仓库）
        git_dir = self.project_path / ".git"
        is_existing_repo = git_dir.exists()

        tx = Transaction()

        if is_existing_repo:
            # 已存在的 git 仓库：执行完整的 GM 结构转换
            tx.add_operation(
                execute_fn=self.create_directory_structure,
                rollback_fn=self._rollback_directory,
                description="创建 .gm 目录结构"
            )
            tx.add_operation(
                execute_fn=self._convert_to_bare_and_move_git,
                description="移动 .git 到 .gm/.git 并创建 .git 文件"
            )
            tx.add_operation(
                execute_fn=lambda: self._create_complete_config(normalized_main_branch),
                rollback_fn=self._rollback_config,
                description="创建完整的 gm.yaml 配置"
            )
            tx.add_operation(
                execute_fn=lambda: self._create_worktree_directory(normalized_main_branch),
                description="创建 worktree 目录"
            )
            tx.add_operation(
                execute_fn=lambda: self._move_working_files(normalized_main_branch),
                description="移动工作区文件到 worktree 目录"
            )
            tx.add_operation(
                execute_fn=lambda: self.setup_shared_files(normalized_main_branch),
                description="设置共享文件"
            )

            tx.commit()
            click.echo("项目初始化成功！已转换为 GM 结构")
            click.echo(f"  - 主分支: {normalized_main_branch}")
            click.echo(f"  - 工作区已移动到: {normalized_main_branch}/")
            click.echo("  - Git 目录已移动到: .gm/.git/")
            click.echo("  - 现在可以使用 'gm add <分支名>' 添加更多 worktree")
        else:
            # 新目录：简单初始化
            tx.add_operation(
                execute_fn=self.create_directory_structure,
                rollback_fn=self._rollback_directory,
                description="创建 .gm 目录结构"
            )
            tx.add_operation(
                execute_fn=lambda: self.config_manager.save_config(GMConfig(initialized=True)),
                rollback_fn=self._rollback_config,
                description="生成 gm.yaml 配置文件"
            )

            tx.commit()
            click.echo("项目初始化成功！已生成 gm.yaml")
            click.echo("  - 这是一个新的 GM 项目目录")
            click.echo("  - 请先使用 'git init' 和 'git remote add' 设置 Git 仓库")
            click.echo("  - 然后使用 'gm add <分支名>' 添加 worktree")


@click.command(name="init")
@click.argument("project_path", required=False, default=".")
@click.option("-y", "--yes", is_flag=True, help="跳过确认")
@click.pass_context
def init_cmd(ctx: click.Context, project_path: str, yes: bool) -> None:
    """初始化项目为 .gm worktree 结构"""
    try:
        cmd = InitCommand(Path(project_path))
        cmd.execute(yes=yes)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        ctx.exit(1)
