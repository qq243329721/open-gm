"""GM CLI 主入口"""

import sys
import importlib
import click

# Windows 系统编码处理：确保能正确输出 UTF-8 字符
if sys.platform == 'win32':
    import os
    if sys.version_info >= (3, 7):
        # Python 3.7+ 使用更安全的方式
        import locale
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'C.UTF-8')
            except locale.Error:
                pass  # 使用系统默认编码

from gm.cli.commands.init import init_cmd
from gm.cli.commands.add import add
from gm.cli.commands.clone import clone
from gm.cli.commands.status import status
from gm.cli.commands.list import list_command

# 导入 del 命令（del 是保留字，使用 importlib）
_del_module = importlib.import_module("gm.cli.commands.del")
del_cmd = _del_module.del_cmd

# 导入高级命令
from gm.cli.commands.advanced import config, symlink, cache


@click.group()
@click.version_option(version="0.1.0")
@click.option(
    '--verbose', 
    is_flag=True,
    help='详细日志输出（调试用）'
)
@click.option(
    '--no-color',
    is_flag=True, 
    help='关闭彩色输出'
)
@click.pass_context
def cli(ctx, verbose, no_color):
    """GM - Git Worktree Manager

    企业级 Git Worktree 管理工具
    
    核心命令：
      init <path>             初始化项目为 .gm 结构
      clone <url>             克隆并初始化为 .gm 结构
      add <branch> [options]  添加新 worktree
      del <branch> [options]  删除 worktree
      list [options]          列出所有 worktree
      status [branch]         查看状态
    高级命令：
      config                  配置管理
      symlink                 符号链接操作
      cache                   缓存管理
      
    全局选项:
      --help                  显示帮助信息
      --version               显示版本号
      --verbose               详细日志输出（调试用）
      --no-color              关闭彩色输出
      
    示例:
      gm init .
      gm add feature/new-ui
      gm list -v
      gm status feature/new-ui
      gm del hotfix/bug -D
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['no_color'] = no_color
    # 为所有命令传递全局配置
    ctx.obj['formatter_config'] = {'no_color': no_color}


# 注册命令
cli.add_command(init_cmd, name="init")
cli.add_command(add)
cli.add_command(clone)
cli.add_command(del_cmd, name="del")
cli.add_command(status)
cli.add_command(list_command, name="list")

# 注册高级命令
cli.add_command(config)
cli.add_command(symlink)
cli.add_command(cache)


if __name__ == "__main__":
    cli()
