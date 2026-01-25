"""CLI 输出格式化工具

提供美化的命令输出、表格、进度条等格式化功能。
"""

import json
import csv
import io
from typing import List, Dict, Any, Optional, Union
from enum import Enum


class Color:
    """ANSI 颜色代码"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # 前景色
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # 背景色
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'


class FormatterConfig:
    """格式化器配置"""

    def __init__(self, no_color: bool = False):
        """初始化格式化器配置

        Args:
            no_color: 是否禁用颜色输出
        """
        self.no_color = no_color

    def colorize(self, text: str, color: str) -> str:
        """应用颜色到文本

        Args:
            text: 要着色的文本
            color: 颜色代码

        Returns:
            着色后的文本（如果禁用颜色则返回原文本）
        """
        if self.no_color:
            return text
        return f"{color}{text}{Color.RESET}"


class OutputFormatter:
    """CLI 输出格式化器"""

    def __init__(self, config: Optional[FormatterConfig] = None):
        """初始化格式化器

        Args:
            config: 格式化器配置
        """
        self.config = config or FormatterConfig()

    def success(self, message: str) -> str:
        """格式化成功消息

        Args:
            message: 消息内容

        Returns:
            格式化的消息
        """
        prefix = self.config.colorize("✓", Color.GREEN)
        return f"{prefix} {message}"

    def error(self, message: str) -> str:
        """格式化错误消息

        Args:
            message: 消息内容

        Returns:
            格式化的消息
        """
        prefix = self.config.colorize("✗", Color.RED)
        return f"{prefix} {message}"

    def warning(self, message: str) -> str:
        """格式化警告消息

        Args:
            message: 消息内容

        Returns:
            格式化的消息
        """
        prefix = self.config.colorize("⚠", Color.YELLOW)
        return f"{prefix} {message}"

    def info(self, message: str) -> str:
        """格式化信息消息

        Args:
            message: 消息内容

        Returns:
            格式化的消息
        """
        prefix = self.config.colorize("ℹ", Color.BLUE)
        return f"{prefix} {message}"

    def format_table(
        self,
        headers: List[str],
        rows: List[List[Any]],
        column_widths: Optional[List[int]] = None
    ) -> str:
        """格式化为表格

        Args:
            headers: 表头
            rows: 数据行
            column_widths: 每列的宽度（如果为 None 则自动计算）

        Returns:
            格式化的表格字符串
        """
        if not headers:
            return ""

        # 计算列宽
        if column_widths is None:
            column_widths = []
            for i, header in enumerate(headers):
                max_width = len(str(header))
                for row in rows:
                    if i < len(row):
                        max_width = max(max_width, len(str(row[i])))
                column_widths.append(max_width)

        # 构建表格
        lines = []

        # 表头
        header_row = ""
        for i, header in enumerate(headers):
            width = column_widths[i] if i < len(column_widths) else len(header)
            header_row += f"{str(header).ljust(width)}  "

        header_row = self.config.colorize(header_row, Color.BOLD)
        lines.append(header_row)

        # 分隔线
        separator = ""
        for width in column_widths:
            separator += "─" * width + "  "
        lines.append(separator)

        # 数据行
        for row in rows:
            data_row = ""
            for i, cell in enumerate(row):
                width = column_widths[i] if i < len(column_widths) else len(str(cell))
                data_row += f"{str(cell).ljust(width)}  "
            lines.append(data_row)

        return "\n".join(lines)

    def format_list(self, items: List[str], bullet: str = "•") -> str:
        """格式化列表

        Args:
            items: 列表项
            bullet: 列表符号

        Returns:
            格式化的列表字符串
        """
        lines = []
        for item in items:
            lines.append(f"{bullet} {item}")
        return "\n".join(lines)

    def format_key_value(self, items: Dict[str, Any]) -> str:
        """格式化键值对

        Args:
            items: 键值对字典

        Returns:
            格式化的键值对字符串
        """
        lines = []
        max_key_len = max(len(k) for k in items.keys()) if items else 0

        for key, value in items.items():
            lines.append(f"{key.ljust(max_key_len)}: {value}")

        return "\n".join(lines)


class TableExporter:
    """表格导出工具"""

    @staticmethod
    def to_json(headers: List[str], rows: List[List[Any]]) -> str:
        """导出为 JSON

        Args:
            headers: 表头
            rows: 数据行

        Returns:
            JSON 字符串
        """
        data = []
        for row in rows:
            item = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    item[header] = row[i]
            data.append(item)

        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def to_csv(headers: List[str], rows: List[List[Any]]) -> str:
        """导出为 CSV

        Args:
            headers: 表头
            rows: 数据行

        Returns:
            CSV 字符串
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue()

    @staticmethod
    def to_tsv(headers: List[str], rows: List[List[Any]]) -> str:
        """导出为 TSV

        Args:
            headers: 表头
            rows: 数据行

        Returns:
            TSV 字符串
        """
        output = io.StringIO()
        writer = csv.writer(output, delimiter='\t')
        writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue()


class ProgressBar:
    """简单的进度条"""

    def __init__(self, total: int, config: Optional[FormatterConfig] = None, prefix: str = ""):
        """初始化进度条

        Args:
            total: 总任务数
            config: 格式化器配置
            prefix: 进度条前缀
        """
        self.total = total
        self.current = 0
        self.config = config or FormatterConfig()
        self.prefix = prefix

    def update(self, step: int = 1) -> str:
        """更新进度

        Args:
            step: 更新的步数

        Returns:
            进度条显示字符串
        """
        self.current = min(self.current + step, self.total)
        percentage = int((self.current / self.total) * 100) if self.total > 0 else 0

        # 构建进度条
        bar_length = 30
        filled = int(bar_length * self.current / self.total) if self.total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        return f"{self.prefix}[{bar}] {percentage}% ({self.current}/{self.total})"

    def reset(self) -> None:
        """重置进度条"""
        self.current = 0


def format_summary(title: str, items: Dict[str, Any], config: Optional[FormatterConfig] = None) -> str:
    """格式化摘要块

    Args:
        title: 摘要标题
        items: 摘要项目
        config: 格式化器配置

    Returns:
        格式化的摘要字符串
    """
    cfg = config or FormatterConfig()
    lines = []

    # 标题
    title_line = cfg.colorize(f"┌─ {title} " + "─" * (40 - len(title)), Color.BOLD)
    lines.append(title_line)

    # 内容
    max_key_len = max(len(str(k)) for k in items.keys()) if items else 0
    for key, value in items.items():
        lines.append(f"│ {str(key).ljust(max_key_len)}: {value}")

    # 底部
    lines.append("└" + "─" * 50)

    return "\n".join(lines)
