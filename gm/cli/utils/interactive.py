"""CLI 交互式输入工具

提供交互式确认、选择、输入等功能。
"""

from typing import List, Optional, Any, Callable


class InteractivePrompt:
    """交互式提示工具"""

    @staticmethod
    def confirm(
        message: str,
        default: bool = False,
        show_default: bool = True
    ) -> bool:
        """交互式确认提示

        Args:
            message: 提示消息
            default: 默认值
            show_default: 是否显示默认值

        Returns:
            用户的确认结果
        """
        import click

        return click.confirm(
            message,
            default=default,
            show_default=show_default
        )

    @staticmethod
    def choose(
        message: str,
        options: List[str],
        default_index: int = 0
    ) -> str:
        """交互式选择

        Args:
            message: 提示消息
            options: 选项列表
            default_index: 默认选项索引

        Returns:
            用户选择的选项
        """
        import click

        click.echo(message)
        for i, option in enumerate(options, 1):
            mark = " >" if i - 1 == default_index else "  "
            click.echo(f"{mark} {i}. {option}")

        while True:
            try:
                choice = click.prompt(
                    "请选择",
                    type=int,
                    default=default_index + 1,
                    show_default=True
                )
                if 1 <= choice <= len(options):
                    return options[choice - 1]
                click.echo(f"错误：请输入 1-{len(options)} 之间的数字")
            except (ValueError, click.Abort):
                click.echo("操作已取消")
                raise

    @staticmethod
    def prompt_text(
        message: str,
        default: Optional[str] = None,
        type: Any = str,
        validation: Optional[Callable[[str], bool]] = None
    ) -> str:
        """交互式文本输入

        Args:
            message: 提示消息
            default: 默认值
            type: 输入类型
            validation: 验证函数

        Returns:
            用户输入的文本
        """
        import click

        while True:
            value = click.prompt(
                message,
                default=default,
                type=type,
                show_default=True if default else False
            )

            if validation is None or validation(value):
                return value

            click.echo("输入无效，请重试")

    @staticmethod
    def prompt_password(
        message: str,
        confirmation: bool = False
    ) -> str:
        """交互式密码输入

        Args:
            message: 提示消息
            confirmation: 是否要求重复确认

        Returns:
            用户输入的密码
        """
        import click

        while True:
            password = click.prompt(message, hide_input=True)

            if not confirmation:
                return password

            confirm = click.prompt("确认密码", hide_input=True)

            if password == confirm:
                return password

            click.echo("密码不匹配，请重试")

    @staticmethod
    def show_summary(title: str, items: List[tuple]) -> None:
        """显示摘要

        Args:
            title: 摘要标题
            items: 摘要项目列表（(key, value) 元组）
        """
        import click

        click.echo()
        click.echo(f"{'═' * 50}")
        click.echo(f"{title:^50}")
        click.echo(f"{'═' * 50}")

        for key, value in items:
            click.echo(f"{key:20s}: {value}")

        click.echo(f"{'═' * 50}")
        click.echo()

    @staticmethod
    def show_warning(message: str) -> None:
        """显示警告信息

        Args:
            message: 警告消息
        """
        import click

        click.echo(click.style("⚠  警告", fg="yellow", bold=True), err=True)
        click.echo(message, err=True)
        click.echo()

    @staticmethod
    def show_error(message: str) -> None:
        """显示错误信息

        Args:
            message: 错误消息
        """
        import click

        click.echo(click.style("✗ 错误", fg="red", bold=True), err=True)
        click.echo(message, err=True)
        click.echo()

    @staticmethod
    def show_info(message: str) -> None:
        """显示信息

        Args:
            message: 信息内容
        """
        import click

        click.echo(click.style("ℹ  信息", fg="blue", bold=True))
        click.echo(message)
        click.echo()

    @staticmethod
    def show_success(message: str) -> None:
        """显示成功信息

        Args:
            message: 成功消息
        """
        import click

        click.echo(click.style("✓ 成功", fg="green", bold=True))
        click.echo(message)
        click.echo()
