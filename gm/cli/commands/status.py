"""GM status 命令实现

显示 worktree 或全局状态。
"""

import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import click

from gm.core.config_manager import ConfigManager
from gm.core.exceptions import (
    GitException,
    ConfigException,
    WorktreeNotFound,
)
from gm.core.git_client import GitClient
from gm.core.logger import get_logger
from gm.core.branch_name_mapper import BranchNameMapper

logger = get_logger("status_command")


class StatusCommand:
    """状态显示命令处理器

    负责显示 worktree 或全局状态。
    """

    def __init__(self, project_path: Optional[Path] = None):
        """初始化命令处理器

        Args:
            project_path: 项目路径，默认为当前目录
        """
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.git_client = GitClient(self.project_path)
        self.config_manager = ConfigManager(self.project_path)
        self.mapper = BranchNameMapper()

        logger.info("StatusCommand initialized", path=str(self.project_path))

    def get_current_location(self) -> str:
        """获取当前位置类型

        Returns:
            'root' - 在项目根目录
            'worktree' - 在某个 worktree 中
            'external' - 在项目外部
        """
        try:
            repo_root = self.git_client.get_repo_root()
            gm_base = repo_root / self.config_manager.get("worktree.base_path", ".gm")

            # 检查当前目录是否在 gm_base 下
            cwd = Path.cwd()
            try:
                cwd.relative_to(gm_base)
                return "worktree"
            except ValueError:
                pass

            # 检查当前目录是否是根目录
            if cwd == repo_root:
                return "root"

            # 检查当前目录是否在项目中
            try:
                cwd.relative_to(repo_root)
                return "root"
            except ValueError:
                return "external"

        except GitException:
            return "external"

    def get_current_branch(self, path: Optional[Path] = None) -> Optional[str]:
        """获取当前分支名

        Args:
            path: 可选的工作目录路径

        Returns:
            分支名或 None
        """
        try:
            branch = self.git_client.get_current_branch()
            if branch != "HEAD":  # 避免 detached head 状态
                return branch
            return None
        except GitException:
            return None

    def get_worktree_list(self) -> List[Dict[str, Any]]:
        """获取所有 worktree 列表

        Returns:
            worktree 信息列表
        """
        try:
            worktrees = self.git_client.get_worktree_list()
            logger.debug("Worktree list retrieved", count=len(worktrees))
            return worktrees
        except GitException as e:
            logger.error("Failed to get worktree list", error=str(e))
            return []

    def get_worktree_path_by_branch(self, branch_name: str) -> Optional[Path]:
        """根据分支名获取 worktree 路径

        Args:
            branch_name: 分支名

        Returns:
            worktree 路径或 None
        """
        repo_root = self.git_client.get_repo_root()
        gm_base = repo_root / self.config_manager.get("worktree.base_path", ".gm")

        # 尝试获取映射的目录名
        mapped_name = self.mapper.map_branch_to_dir(branch_name)
        worktree_path = gm_base / mapped_name

        if worktree_path.exists():
            return worktree_path

        return None

    def get_working_dir_status(self, path: Path) -> Dict[str, int]:
        """获取工作目录的文件状态

        Args:
            path: 工作目录路径

        Returns:
            包含 modified, untracked, staged 数量的字典
        """
        try:
            status_output = self.git_client.get_status(path)

            modified = 0
            untracked = 0
            staged = 0

            for line in status_output.split("\n"):
                if not line.strip():
                    continue

                if len(line) < 2:
                    continue

                status_code = line[:2]

                # 检查第二个字符：M 表示修改，? 表示未跟踪
                if status_code[1] == "M":
                    modified += 1
                elif status_code[1] == "D":
                    modified += 1
                elif status_code[1] == "A":
                    modified += 1
                elif status_code == "??":
                    untracked += 1

                # 检查第一个字符：表示暂存区状态
                if status_code[0] in ("M", "A", "D", "R", "C"):
                    staged += 1

            logger.debug(
                "Working directory status retrieved",
                path=str(path),
                modified=modified,
                untracked=untracked,
                staged=staged,
            )

            return {
                "modified": modified,
                "untracked": untracked,
                "staged": staged,
            }

        except GitException as e:
            logger.error("Failed to get working directory status", error=str(e))
            return {"modified": 0, "untracked": 0, "staged": 0}

    def get_commit_stats(self, path: Path) -> Dict[str, Any]:
        """获取提交统计信息

        Args:
            path: worktree 路径

        Returns:
            包含 ahead, behind, last_commit_msg, last_commit_author, last_commit_time 的字典
        """
        try:
            # 获取当前分支的追踪分支
            try:
                output = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                tracking_branch = output.stdout.strip()
            except Exception:
                tracking_branch = ""

            ahead = 0
            behind = 0

            # 如果有追踪分支，计算 ahead/behind
            if tracking_branch and tracking_branch != "@{u}":
                try:
                    output = subprocess.run(
                        ["git", "rev-list", "--left-right", "--count", f"{tracking_branch}...HEAD"],
                        cwd=path,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if output.returncode == 0:
                        parts = output.stdout.strip().split()
                        if len(parts) == 2:
                            behind = int(parts[0])
                            ahead = int(parts[1])
                except Exception:
                    pass

            # 获取最后一次提交信息
            last_commit_msg = ""
            last_commit_author = ""
            last_commit_time = ""

            try:
                # 获取最后一次提交的简要信息
                output = subprocess.run(
                    ["git", "log", "-1", "--pretty=format:%s"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if output.returncode == 0:
                    last_commit_msg = output.stdout.strip()

                # 获取提交作者
                output = subprocess.run(
                    ["git", "log", "-1", "--pretty=format:%an"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if output.returncode == 0:
                    last_commit_author = output.stdout.strip()

                # 获取提交时间（相对时间）
                output = subprocess.run(
                    ["git", "log", "-1", "--pretty=format:%ar"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if output.returncode == 0:
                    last_commit_time = output.stdout.strip()

            except Exception as e:
                logger.debug("Failed to get commit details", error=str(e))

            logger.debug(
                "Commit stats retrieved",
                path=str(path),
                ahead=ahead,
                behind=behind,
            )

            return {
                "ahead": ahead,
                "behind": behind,
                "last_commit_msg": last_commit_msg,
                "last_commit_author": last_commit_author,
                "last_commit_time": last_commit_time,
            }

        except Exception as e:
            logger.error("Failed to get commit stats", error=str(e))
            return {
                "ahead": 0,
                "behind": 0,
                "last_commit_msg": "",
                "last_commit_author": "",
                "last_commit_time": "",
            }

    def get_worktree_status(self, worktree_path: Path) -> str:
        """获取 worktree 状态（clean/dirty）

        Args:
            worktree_path: worktree 路径

        Returns:
            'clean' 或 'dirty'
        """
        status = self.get_working_dir_status(worktree_path)
        changes = status["modified"] + status["untracked"] + status["staged"]
        return "dirty" if changes > 0 else "clean"

    def format_detailed_output(self, branch_name: str) -> str:
        """格式化详细状态输出

        Args:
            branch_name: 分支名

        Returns:
            格式化的输出字符串
        """
        repo_root = self.git_client.get_repo_root()
        worktree_path = self.get_worktree_path_by_branch(branch_name)

        if not worktree_path:
            return f"错误：分支 '{branch_name}' 的 worktree 不存在"

        output_lines = []
        output_lines.append(f"[OK] Project Root: {repo_root}")
        output_lines.append("")
        output_lines.append("Current Worktree Status")
        output_lines.append("─" * 45)

        # 基本信息
        output_lines.append(f"Branch:           {branch_name}")
        output_lines.append(f"Path:             {worktree_path.relative_to(repo_root)}")

        # 状态
        status_info = self.get_working_dir_status(worktree_path)
        changes_count = (
            status_info["modified"]
            + status_info["untracked"]
            + status_info["staged"]
        )
        status_str = f"dirty ({changes_count} changes)" if changes_count > 0 else "clean"
        output_lines.append(f"Status:           {status_str}")

        # 工作目录信息
        output_lines.append("")
        output_lines.append("Working Directory")
        output_lines.append("─" * 45)
        output_lines.append(
            f"Modified:   {status_info['modified']} {'file' if status_info['modified'] == 1 else 'files'}"
        )
        output_lines.append(
            f"Untracked:  {status_info['untracked']} {'file' if status_info['untracked'] == 1 else 'files'}"
        )
        output_lines.append(
            f"Staged:     {status_info['staged']} {'file' if status_info['staged'] == 1 else 'files'}"
        )

        # 提交统计
        commit_stats = self.get_commit_stats(worktree_path)
        output_lines.append("")
        output_lines.append("Commits")
        output_lines.append("─" * 45)
        output_lines.append(f"Ahead:      {commit_stats['ahead']} {'commit' if commit_stats['ahead'] == 1 else 'commits'}")
        output_lines.append(f"Behind:     {commit_stats['behind']} {'commit' if commit_stats['behind'] == 1 else 'commits'}")

        if commit_stats["last_commit_msg"]:
            output_lines.append(f"Last:       \"{commit_stats['last_commit_msg']}\"")
            if commit_stats["last_commit_time"]:
                output_lines.append(f"            ({commit_stats['last_commit_time']})")

        return "\n".join(output_lines)

    def format_summary_output(self) -> str:
        """格式化全局摘要输出

        Returns:
            格式化的输出字符串
        """
        repo_root = self.git_client.get_repo_root()
        worktrees = self.get_worktree_list()

        output_lines = []
        output_lines.append(f"[OK] Project initialized at: {repo_root}")
        output_lines.append("")
        output_lines.append("Worktree Summary")
        output_lines.append("─" * 45)

        # 计算统计信息
        total = len(worktrees)
        clean_count = 0
        dirty_count = 0
        dirty_branches = []

        for wt in worktrees:
            branch = wt.get("branch")
            if not branch or wt.get("detached"):
                continue

            wt_path = Path(wt["path"])
            status_info = self.get_working_dir_status(wt_path)
            changes = (
                status_info["modified"]
                + status_info["untracked"]
                + status_info["staged"]
            )

            if changes > 0:
                dirty_count += 1
                dirty_branches.append((branch, wt_path.relative_to(repo_root)))
            else:
                clean_count += 1

        output_lines.append(f"Total:       {total} {'worktree' if total == 1 else 'worktrees'}")
        output_lines.append(f"Clean:       {clean_count} {'worktree' if clean_count == 1 else 'worktrees'}")
        output_lines.append(f"Dirty:       {dirty_count} {'worktree' if dirty_count == 1 else 'worktrees'}")

        if dirty_branches:
            for branch, rel_path in dirty_branches:
                output_lines.append(f"             ({branch})")

        # Quick Access
        if worktrees:
            output_lines.append("")
            output_lines.append("Quick Access")
            output_lines.append("─" * 45)

            for wt in worktrees:
                branch = wt.get("branch")
                if not branch or wt.get("detached"):
                    continue

                wt_path = Path(wt["path"])
                rel_path = wt_path.relative_to(repo_root)
                status_info = self.get_working_dir_status(wt_path)
                changes = (
                    status_info["modified"]
                    + status_info["untracked"]
                    + status_info["staged"]
                )
                status_str = "dirty" if changes > 0 else "clean"

                output_lines.append(
                    f"cd {rel_path}    ({branch} - {status_str})"
                )

        return "\n".join(output_lines)

    def execute(self, branch_name: Optional[str] = None) -> str:
        """执行状态命令

        Args:
            branch_name: 可选的分支名，如果提供则显示该分支的详细状态

        Returns:
            格式化的输出字符串

        Raises:
            GitException: 如果 git 操作失败
            ConfigException: 如果配置操作失败
            WorktreeNotFound: 如果指定的分支的 worktree 不存在
        """
        logger.info("Executing status command", branch_name=branch_name)

        try:
            self.config_manager.load_config()
        except ConfigException as e:
            logger.error("Failed to load configuration", error=str(e))
            raise

        # 如果指定了分支名，显示该分支的详细状态
        if branch_name:
            worktree_path = self.get_worktree_path_by_branch(branch_name)
            if not worktree_path:
                logger.error("Worktree not found", branch=branch_name)
                raise WorktreeNotFound(f"分支 '{branch_name}' 的 worktree 不存在")

            output = self.format_detailed_output(branch_name)
            logger.info("Status command executed", location="branch_specific")
            return output

        # 否则根据当前位置决定显示什么
        location = self.get_current_location()

        if location == "worktree":
            # 在 worktree 中，显示该 worktree 的详细状态
            current_branch = self.get_current_branch()
            if current_branch:
                output = self.format_detailed_output(current_branch)
                logger.info("Status command executed", location="worktree")
                return output
            else:
                logger.error("Cannot determine current branch")
                raise GitException("无法确定当前分支")

        elif location == "root":
            # 在根目录，显示全局摘要
            output = self.format_summary_output()
            logger.info("Status command executed", location="root")
            return output

        else:
            # 在项目外部
            logger.error("Not in a GM project", location=location)
            raise GitException("不在 GM 项目中，请初始化项目后再运行此命令")


@click.command()
@click.argument("branch", required=False, default=None)
def status(branch: Optional[str]) -> None:
    """显示 worktree 或全局状态

    \b
    使用示例:
    gm status                    # 显示当前 worktree 或全局摘要
    gm status feature/my-branch  # 显示特定分支的详细状态
    """
    try:
        cmd = StatusCommand()
        output = cmd.execute(branch)
        click.echo(output)

    except WorktreeNotFound as e:
        click.echo(f"错误：{e.message}", err=True)
        raise click.Exit(1)
    except GitException as e:
        click.echo(f"Git 错误：{e.message}", err=True)
        raise click.Exit(1)
    except ConfigException as e:
        click.echo(f"配置错误：{e.message}", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"错误：{str(e)}", err=True)
        raise click.Exit(1)
