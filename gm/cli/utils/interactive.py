"""CLI 交互输入工具封装"""

import click
import sys
import time
from typing import List, Optional, Any, Callable


class InteractivePrompt:
    """交互式提示工具"""

    @staticmethod
    def confirm(message: str, default: bool = False, show_default: bool = True) -> bool:
        """交互确认"""
        return click.confirm(message, default=default, show_default=show_default)

    @staticmethod
    def choose(message: str, options: List[str], default_index: int = 0) -> str:
        """交互选择列表"""
        click.echo(message)
        for i, option in enumerate(options, 1):
            mark = " >" if i - 1 == default_index else "  "
            click.echo(f"{mark} {i}. {option}")
        
        choice = click.prompt("请选择", type=int, default=default_index + 1)
        if 1 <= choice <= len(options):
            return options[choice - 1]
        return options[default_index]

    @staticmethod
    def prompt_text(message: str, default: Optional[str] = None, type: Any = str) -> str:
        """交互文本输入"""
        return click.prompt(message, default=default, type=type)

    @staticmethod
    def show_info(message: str) -> None:
        """输出信息"""
        click.echo(click.style("INFO", fg="blue") + f": {message}")

    @staticmethod
    def show_error(message: str) -> None:
        """输出错误"""
        click.echo(click.style("ERROR", fg="red") + f": {message}", err=True)

    @staticmethod
    def show_success(message: str) -> None:
        """输出成功"""
        click.echo(click.style("SUCCESS", fg="green") + f": {message}")


class ProgressBar:
    """简易进度条"""
    
    def __init__(self, total: int, description: str = "处理中"):
        self.total = total
        self.current = 0
        self.description = description
    
    def update(self, increment: int = 1):
        """更新进度"""
        self.current = min(self.current + increment, self.total)
        self._draw()

    def _draw(self):
        """绘制进度条"""
        percent = (self.current / self.total) * 100
        bar = "#" * int(percent / 5) + "-" * (20 - int(percent / 5))
        sys.stdout.write(f"\r{self.description}: [{bar}] {percent:.1f}%")
        sys.stdout.flush()
        if self.current >= self.total:
            sys.stdout.write("\n")

    def finish(self):
        """完成进度"""
        self.current = self.total
        self._draw()
