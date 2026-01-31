"""GM CLI 主入口"""

import sys

# Windows 系统编码处理：确保能正确输出 UTF-8 字符
# 必须在导入其他模块之前设置！
# if sys.platform == 'win32':
#     import os
#     import io
    
#     # 方法1: 设置环境变量（影响子进程和后续导入）
#     os.environ['PYTHONIOENCODING'] = 'utf-8'
    
#     # 方法2: 重新包装 stdout/stderr（Git Bash 终端必需）
#     # Git Bash 使用伪终端，需要替换 sys.stdout 对象
#     if hasattr(sys.stdout, 'buffer'):
#         try:
#             sys.stdout = io.TextIOWrapper(
#                 sys.stdout.buffer, 
#                 encoding='utf-8',
#                 errors='replace',
#                 line_buffering=True
#             )
#         except Exception:
#             pass
    
#     if hasattr(sys.stderr, 'buffer'):
#         try:
#             sys.stderr = io.TextIOWrapper(
#                 sys.stderr.buffer,
#                 encoding='utf-8',
#                 errors='replace',
#                 line_buffering=True
#             )
#         except Exception:
#             pass
    
#     # 方法3: 设置 locale（某些 C 库函数需要）
#     if sys.version_info >= (3, 7):
#         import locale
#         try:
#             locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
#         except locale.Error:
#             try:
#                 locale.setlocale(locale.LC_ALL, 'C.UTF-8')
#             except locale.Error:
#                 pass

import importlib
import click

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
from gm.cli.utils import GMNotFoundError


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


def main():
    """CLI 入口点，处理全局异常"""
    try:
        cli()
    except GMNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    except Exception as e:
        # 其他未处理的异常
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
