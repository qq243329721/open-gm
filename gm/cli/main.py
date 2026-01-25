"""GM CLI 主入口"""

import click

from gm.cli.commands.init import init


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """GM - Git Worktree Manager

    企业级 Git Worktree 管理工具
    """
    pass


# 注册命令
cli.add_command(init)


if __name__ == "__main__":
    cli()
