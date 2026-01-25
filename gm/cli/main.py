"""GM CLI 主入口"""

import importlib
import click

from gm.cli.commands.init import init
from gm.cli.commands.add import add
from gm.cli.commands.clone import clone
from gm.cli.commands.status import status
from gm.cli.commands.list import list_command

# 导入 del 命令（del 是保留字，使用 importlib）
_del_module = importlib.import_module("gm.cli.commands.del")
del_cmd = _del_module.del_cmd


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """GM - Git Worktree Manager

    企业级 Git Worktree 管理工具
    """
    pass


# 注册命令
cli.add_command(init)
cli.add_command(add)
cli.add_command(clone)
cli.add_command(del_cmd, name="del")
cli.add_command(status)
cli.add_command(list_command, name="list")


if __name__ == "__main__":
    cli()
