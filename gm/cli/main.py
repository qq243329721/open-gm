"""GM CLI 主入口"""

import click


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """GM - Git Worktree Manager

    企业级 Git Worktree 管理工具
    """
    pass


if __name__ == "__main__":
    cli()
