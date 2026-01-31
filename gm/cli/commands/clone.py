"""GM clone 命令实现

克隆仓库并初始化为 .gm worktree 结构。
"""

import shutil
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import click

from gm.cli.commands.init import InitCommand
from gm.cli.utils.project_utils import find_gm_root_optional
from gm.core.config_manager import ConfigManager
from gm.core.exceptions import (
    GitException,
    ConfigException,
    TransactionRollbackError,
    GitCommandError,
)
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.core.transaction import Transaction

# Windows 系统编码处理：确保能正确输出 UTF-8 字符
# if sys.platform == 'win32':
#     # 强制 stdout 使用 UTF-8，忽略系统编码
#     sys.stdout.reconfigure(encoding='utf-8')
#     sys.stderr.reconfigure(encoding='utf-8')

logger = get_logger("clone_command")


class CloneCommand:
    """克隆命令处理器

    负责克隆 Git 仓库并初始化为 .gm 结构。
    """

    def __init__(
        self,
        repo_url: str,
        project_path: Optional[str] = None,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
        no_init: bool = False,
    ):
        """初始化克隆命令处理器

        Args:
            repo_url: 仓库 URL
            project_path: 克隆目标路径，默认使用仓库名称
            branch: 初始分支，默认为仓库默认分支
            depth: shallow clone 的深度，默认不使用 shallow clone
            no_init: 是否仅克隆不初始化，默认为 False
        """
        self.repo_url = repo_url
        self.project_path = Path(project_path) if project_path else None
        self.branch = branch
        self.depth = depth
        self.no_init = no_init
        self.cloned_path: Optional[Path] = None

    def validate_repo_url(self) -> bool:
        """验证仓库 URL 有效性

        Returns:
            True 如果 URL 有效

        Raises:
            GitException: 如果 URL 无效
        """
        try:
            # 验证 URL 格式
            if not self.repo_url:
                raise GitException("仓库 URL 不能为空")

            # 支持多种 URL 格式
            # https://github.com/user/repo.git
            # git@github.com:user/repo.git
            # /path/to/repo
            # file:///path/to/repo
            # C:\path\to\repo (Windows)

            parsed = urlparse(self.repo_url)

            # 检查是本地路径还是远程 URL
            # 支持 Unix 路径和 Windows 路径
            is_unix_path = self.repo_url.startswith("/")
            is_windows_path = (len(self.repo_url) > 1 and
                              self.repo_url[1] == ":" and
                              self.repo_url[0].isalpha())
            is_file_url = parsed.scheme == "file"
            is_no_scheme = not parsed.scheme

            is_local_path = (
                is_unix_path or is_windows_path or is_file_url or
                (is_no_scheme and not self.repo_url.startswith("git@"))
            )
            is_remote_url = parsed.scheme in ("http", "https", "git")
            is_ssh_url = self.repo_url.startswith("git@")

            if not (is_local_path or is_remote_url or is_ssh_url):
                raise GitException(f"无效的仓库 URL 格式：{self.repo_url}")

            logger.info("Repository URL validated", url=self.repo_url)
            return True

        except GitException:
            raise
        except Exception as e:
            logger.error("Failed to validate repository URL", url=self.repo_url, error=str(e))
            raise GitException(f"验证仓库 URL 失败：{str(e)}")

    def determine_target_path(self) -> Path:
        """确定目标路径

        如果未指定目标路径，从仓库 URL 提取仓库名称。

        Returns:
            目标路径

        Raises:
            GitException: 如果无法确定目标路径
        """
        try:
            if self.project_path:
                return self.project_path

            # 从 URL 提取仓库名称
            # https://github.com/user/repo.git -> repo
            # git@github.com:user/repo.git -> repo
            # /path/to/repo -> repo
            url_path = self.repo_url.rstrip("/")

            if url_path.endswith(".git"):
                url_path = url_path[:-4]

            # 获取最后一个部分
            repo_name = url_path.split("/")[-1]

            if not repo_name:
                raise GitException(f"无法从 URL 提取仓库名称：{self.repo_url}")

            target_path = Path.cwd() / repo_name
            logger.info("Target path determined", url=self.repo_url, path=str(target_path))
            return target_path

        except GitException:
            raise
        except Exception as e:
            logger.error("Failed to determine target path", url=self.repo_url, error=str(e))
            raise GitException(f"确定目标路径失败：{str(e)}")

    def validate_target_path(self, target_path: Path) -> bool:
        """验证目标路径有效性

        Returns:
            True 如果路径有效

        Raises:
            GitException: 如果路径已存在且非空，或已是 GM 项目
        """
        try:
            if target_path.exists():
                # 检查目录是否为空
                if target_path.is_dir():
                    items = list(target_path.iterdir())
                    if items:
                        logger.error(
                            "Target path is not empty",
                            path=str(target_path),
                            items_count=len(items),
                        )
                        raise GitException(
                            f"目标路径已存在且不为空：{target_path}"
                        )
                else:
                    logger.error("Target path exists and is not a directory", path=str(target_path))
                    raise GitException(
                        f"目标路径存在但不是目录：{target_path}"
                    )

            # 验证父目录是否可写
            parent_dir = target_path.parent
            if not parent_dir.exists():
                logger.warning("Parent directory does not exist, will be created", path=str(parent_dir))
            elif not parent_dir.is_dir():
                raise GitException(f"父目录不是目录：{parent_dir}")

            # 检查目标路径或其父目录是否已是 GM 项目
            existing_root = find_gm_root_optional(target_path)
            if existing_root:
                raise GitException(
                    f"目标路径或其父目录已是 GM 项目：{existing_root}\n"
                    f"提示: 请选择一个非 GM 项目的目录进行克隆"
                )

            logger.info("Target path validated", path=str(target_path))
            return True

        except GitException:
            raise
        except Exception as e:
            logger.error("Failed to validate target path", path=str(target_path), error=str(e))
            raise GitException(f"验证目标路径失败：{str(e)}")

    def clone_repository(self, target_path: Path) -> None:
        """克隆 Git 仓库

        Args:
            target_path: 克隆目标路径

        Raises:
            GitCommandError: 克隆失败时抛出
        """
        try:
            # 确保父目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # 构建 git clone 命令
            cmd = ["git", "clone"]

            if self.depth:
                cmd.extend(["--depth", str(self.depth)])

            if self.branch:
                cmd.extend(["--branch", self.branch])

            cmd.extend([self.repo_url, str(target_path)])

            # 使用 GitClient 执行命令
            git_client = GitClient()
            git_client.run_command(cmd)

            self.cloned_path = target_path
            logger.info(
                "Repository cloned successfully",
                url=self.repo_url,
                path=str(target_path),
                branch=self.branch,
            )

        except GitCommandError as e:
            logger.error("Failed to clone repository", url=self.repo_url, error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during cloning", url=self.repo_url, error=str(e))
            raise GitCommandError(f"克隆失败：{str(e)}") from e

    def _convert_to_bare_and_move_git(self, repo_path: Path) -> None:
        """移动 .git 目录到 .gm/.git，然后生成 .git 文件指向 .gm/.git

        Args:
            repo_path: 仓库路径
        """
        import shutil
        
        git_src = repo_path / ".git"
        gm_git_dst = repo_path / ".gm" / ".git"
        git_file = repo_path / ".git"
        
        if git_src.exists() and not gm_git_dst.exists():
            # 1. 移动 .git 目录到 .gm/.git
            shutil.move(str(git_src), str(gm_git_dst))
            
            # 2. 生成 .git 文件，指向 .gm/.git（使用绝对路径）
            absolute_git_path = repo_path.resolve() / ".gm" / ".git"
            git_file_content = f"gitdir: {absolute_git_path}"
            with open(git_file, 'w', encoding='utf-8') as f:
                f.write(git_file_content)
            
            logger.info("Git directory moved and .git file created with absolute path", 
                       src=str(git_src), dst=str(gm_git_dst), git_file=str(git_file), 
                       git_target=str(absolute_git_path))

    def _create_worktree_directory(self, repo_path: Path, branch: str) -> None:
        """创建主分支对应的 worktree 目录

        Args:
            repo_path: 仓库路径
            branch: 分支名称
        """
        worktree_dir = repo_path / branch
        worktree_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created worktree directory", path=str(worktree_dir), branch=branch)

    def _move_working_files(self, repo_path: Path, branch: str) -> None:
        """将工作区文件移到 worktree 目录

        Args:
            repo_path: 仓库路径
            branch: 分支名称
        """
        import shutil
        import os

        worktree_dir = repo_path / branch
        gm_dir = repo_path / ".gm"
        gm_yaml = repo_path / "gm.yaml"

        # 需要忽略的文件/目录
        # 注意：根目录的.git文件(指向.gm/.git的gitdir文件)会被移动到分支文件夹
        ignore_items = {".gm", "gm.yaml", branch}

        # 移动普通文件和目录到分支目录
        for item in os.listdir(repo_path):
            if item not in ignore_items:
                src = repo_path / item
                dst = worktree_dir / item

                if src.is_dir():
                    shutil.move(str(src), str(dst))
                else:
                    shutil.move(str(src), str(dst))

                logger.info("Moved item to worktree", item=item, src=str(src), dst=str(dst))

        # 注意：根目录的.git文件已经在 _convert_to_bare_and_move_git 中生成
        # 并在上面的循环中被移动到分支文件夹，所以这里不需要再创建

    def _create_complete_config(self, repo_path: Path, use_local: bool, main_branch: str) -> None:
        """创建包含完整项目信息的配置文件

        Args:
            repo_path: 仓库路径
            use_local: 是否使用本地分支
            main_branch: 主分支名称
        """
        from gm.core.config_manager import ConfigManager
        
        # 创建配置管理器
        config_manager = ConfigManager(repo_path)
        
        # 加载默认配置
        config = config_manager.get_default_config()
        
        # 设置基本配置
        config.initialized = True
        config.use_local_branch = use_local
        config.main_branch = main_branch
        
        # 设置项目信息
        config.project_name = repo_path.name
        config.home_path = str(repo_path.resolve())
        config.remote_url = self.repo_url
        
        # 设置分支映射（原始分支名 -> 规范化的文件夹名）
        try:
            # GitClient 应该在 .gm 目录执行命令（GM 项目的 git 仓库在 .gm/.git）
            gm_path = repo_path / ".gm"
            git_client = GitClient(gm_path)
            original_branch = git_client.get_current_branch() or main_branch
            config.branch_mapping[original_branch] = main_branch
        except Exception:
            # 如果获取原始分支失败，只设置规范化后的分支名
            config.branch_mapping[main_branch] = main_branch
        
        # 保存配置
        config_manager.save_config(config)
        
        logger.info("Complete configuration created", 
                   project_name=config.project_name,
                   home_path=config.home_path,
                   remote_url=config.remote_url,
                   main_branch=main_branch)

    def _normalize_branch_name(self, branch_name: str) -> str:
        """规范化分支名称，将特殊符号替换为-

        Args:
            branch_name: 原始分支名称

        Returns:
            规范化后的分支名称
        """
        import re
        # 将特殊符号替换为短横线
        normalized = re.sub(r'[^a-zA-Z0-9_-]', '-', branch_name)
        # 将连续的短横线替换为单个短横线
        normalized = re.sub(r'-+', '-', normalized)
        # 移除开头和结尾的短横线
        normalized = normalized.strip('-')
        return normalized

    def initialize_gm(self, repo_path: Path) -> None:
        """初始化为 .gm 结构

        Args:
            repo_path: 仓库路径

        Raises:
            ConfigException: 初始化失败时抛出
        """
        try:
            # 创建 InitCommand 实例
            init_cmd = InitCommand(repo_path)

            # 验证项目
            init_cmd.validate_project()

            # 检查是否已初始化
            is_initialized, _ = init_cmd.check_already_initialized()
            if is_initialized:
                raise ConfigException("项目已初始化")

            # 自动初始化，不进行交互
            # 使用本地分支，主分支为当前分支或 main
            use_local = True
            main_branch: str = "main"  # 默认值
            try:
                current_branch = init_cmd.git_client.get_current_branch()
                main_branch = current_branch or "main"
            except Exception:
                main_branch = "main"
            
            # 规范化分支名称
            normalized_main_branch = self._normalize_branch_name(main_branch)

            # 使用事务确保原子操作
            tx = Transaction()

            try:
                # 添加操作到事务
                tx.add_operation(
                    execute_fn=init_cmd.create_directory_structure,
                    rollback_fn=init_cmd._rollback_directory,
                    description="Create .gm directory structure",
                )

                tx.add_operation(
                    execute_fn=lambda: self._convert_to_bare_and_move_git(repo_path),
                    description="Convert to bare and move .git to .gm/.git",
                )

                tx.add_operation(
                    execute_fn=lambda: self._create_complete_config(repo_path, use_local, normalized_main_branch),
                    rollback_fn=init_cmd._rollback_config,
    description="Create gm.yaml configuration with complete project info",
                )

                tx.add_operation(
                    execute_fn=lambda: self._create_worktree_directory(repo_path, normalized_main_branch),
                    description="Create worktree directory",
                )

                tx.add_operation(
                    execute_fn=lambda: self._move_working_files(repo_path, normalized_main_branch),
                    description="Move working files to worktree",
                )

                tx.add_operation(
                    execute_fn=lambda: init_cmd.setup_shared_files(main_branch),
                    description="Setup shared files",
                )

                # 提交事务
                tx.commit()

                logger.info("Repository initialized as GM project", path=str(repo_path))

            except TransactionRollbackError as e:
                logger.error("Failed to initialize GM project, transaction rolled back", error=str(e))
                raise ConfigException(f"初始化失败并已回滚：{str(e)}")

        except ConfigException:
            raise
        except Exception as e:
            logger.error("Failed to initialize GM project", path=str(repo_path), error=str(e))
            raise ConfigException(f"初始化失败：{str(e)}") from e

    def cleanup_on_failure(self, target_path: Path) -> None:
        """在失败时清理克隆的仓库

        Args:
            target_path: 克隆的路径
        """
        try:
            if target_path.exists():
                logger.info("Cleaning up cloned repository", path=str(target_path))
                shutil.rmtree(target_path)
                logger.info("Cloned repository removed", path=str(target_path))
        except Exception as e:
            logger.error("Failed to cleanup cloned repository", path=str(target_path), error=str(e))

    def execute(self) -> Path:
        """执行克隆和初始化

        Returns:
            克隆的仓库路径

        Raises:
            GitException: 如果 git 操作失败
            ConfigException: 如果配置操作失败
        """
        logger.info("Starting clone operation", url=self.repo_url, no_init=self.no_init)

        try:
            # 1. 验证仓库 URL
            self.validate_repo_url()

            # 2. 确定目标路径
            target_path = self.determine_target_path()

            # 3. 验证目标路径
            self.validate_target_path(target_path)

            # 4. 克隆仓库
            self.clone_repository(target_path)

            # 5. 初始化为 .gm 结构（如果不跳过）
            if not self.no_init:
                try:
                    self.initialize_gm(target_path)
                except Exception as e:
                    # 初始化失败时清理克隆的仓库
                    logger.error("Initialization failed, cleaning up", error=str(e))
                    self.cleanup_on_failure(target_path)
                    raise

            logger.info(
                "Clone operation completed successfully",
                url=self.repo_url,
                path=str(target_path),
            )
            return target_path

        except (GitException, ConfigException):
            raise
        except Exception as e:
            logger.error("Unexpected error during clone operation", error=str(e))
            raise GitException(f"克隆失败：{str(e)}") from e


@click.command()
@click.argument("repo_url")
@click.argument("project_path", required=False)
@click.option(
    "-b",
    "--branch",
    type=str,
    default=None,
    help="克隆时指定的初始分支",
)
@click.option(
    "--depth",
    type=int,
    default=None,
    help="使用 shallow clone 的深度",
)
@click.option(
    "--no-init",
    is_flag=True,
    default=False,
    help="仅克隆，不初始化为 .gm 结构",
)
def clone(
    repo_url: str,
    project_path: Optional[str],
    branch: Optional[str],
    depth: Optional[int],
    no_init: bool,
) -> None:
    """克隆仓库并初始化为 .gm worktree 结构

    \b
    使用示例:
    gm clone https://github.com/user/repo.git
    gm clone https://github.com/user/repo.git /path/to/project
    gm clone https://github.com/user/repo.git -b develop
    gm clone https://github.com/user/repo.git --no-init
    """
    try:
        cmd = CloneCommand(
            repo_url=repo_url,
            project_path=project_path,
            branch=branch,
            depth=depth,
            no_init=no_init,
        )

        cloned_path = cmd.execute()

        click.echo(f"[OK] 仓库已从以下位置克隆：{repo_url}")
        click.echo(f"[OK] 位置：{cloned_path}")

        if not no_init:
            click.echo(f"[OK] 已初始化为 GM 项目")
            click.echo(f"[OK] .gm/ 目录已创建")
            click.echo(f"[OK] gm.yaml 配置文件已生成")
            click.echo(f"[OK] 准备使用 gm add [BRANCH] 添加 worktree")
        else:
            click.echo(f"[OK] Clone only, not initialized")

    except GitCommandError as e:
        click.echo(f"\nClone failed", err=True)
        click.echo(f"Reason: {e.message}", err=True)
        click.echo(f"\nTroubleshooting suggestions:", err=True)
        click.echo(f"  1. Check network connection: ping github.com", err=True)
        click.echo(f"  2. Verify URL is correct: {repo_url}", err=True)
        click.echo(f"  3. Try using SSH instead of HTTPS", err=True)
        click.echo(f"  4. If problem persists, try re-running the command", err=True)
        sys.exit(1)
    except GitException as e:
        click.echo(f"\nGit operation failed", err=True)
        click.echo(f"Reason: {e.message}", err=True)
        sys.exit(1)
    except ConfigException as e:
        click.echo(f"\nConfiguration error", err=True)
        click.echo(f"Reason: {e.message}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\nUnknown error occurred", err=True)
        click.echo(f"Reason: {str(e)}", err=True)
        click.echo(f"\nIf problem persists, please check logs for details", err=True)
        sys.exit(1)
