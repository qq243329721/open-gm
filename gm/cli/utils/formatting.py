"""CLI 输出格式化工具

提供各种颜色、表格、列表和错误模板的格式化功能。"""

import json
import csv
import io
from typing import List, Dict, Any, Optional, Union
from enum import Enum


# 错误消息模板
ERROR_TEMPLATES = {
    'not_initialized': "项目未初始化。请先运行 'gm init'。",
    'worktree_exists': "工作树已存在: {path}\n解决方案: 运行 'gm del {name}' 删除已有工作树。",
    'branch_not_found': "分支 '{branch}' 不存在。\n可用分支: {branches}\n解决方案: 使用 '-l' 参数查看所有分支。",
    'symlink_broken': "符号链接损坏: {file}\n目标: {target}\n解决方案: 运行 'gm symlink repair {worktree}'。",
    'not_git_repo': "当前目录不是 Git 仓库。\n解决方案: 先用 'git init' 初始化 Git 仓库。",
    'cannot_delete_main': "无法删除主工作树。\nmain 是主要工作树，不可删除。\n解决方案: 先切换到其他分支。",
    'uncommitted_changes': "工作树有未提交的更改。\n修改: {modified}\n暂存: {staged}\n是否继续? (y/n): ",
}


class Color:
    """ANSI 颜色代码"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # 基本颜色
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # 背景颜色
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'


class FormatterConfig:
    """格式化配置中心"""

    def __init__(self, no_color: bool = False):
        """初始化配置
        Args:
            no_color: 是否禁用颜色输出
        """
        self.no_color = no_color

    def colorize(self, text: str, color: str) -> str:
        """根据配置为文本添加 ANSI 颜色
        Args:
            text: 目标文本
            color: ANSI 颜色代码
        Returns:
            格式化后的文本
        """
        if self.no_color:
            return text
        return f"{color}{text}{Color.RESET}"


class OutputFormatter:
    """CLI 输出格式化器实现"""

    def __init__(self, config: Optional[FormatterConfig] = None):
        """初始化格式化器
        Args:
            config: 格式化配置
        """
        self.config = config or FormatterConfig()

    def success(self, message: str) -> str:
        """格式化成功消息"""
        prefix = self.config.colorize("+", Color.GREEN)
        return f"{prefix} {message}"

    def error(self, message: str) -> str:
        """格式化错误消息"""
        prefix = self.config.colorize("-", Color.RED)
        return f"{prefix} {message}"

    def warning(self, message: str) -> str:
        """格式化警告消息"""
        prefix = self.config.colorize("!", Color.YELLOW)
        return f"{prefix} {message}"

    def info(self, message: str) -> str:
        """格式化普通信息消息"""
        prefix = self.config.colorize("*", Color.BLUE)
        return f"{prefix} {message}"

    def format_error(self, error_type: str, **kwargs) -> str:
        """根据模板格式化特定类型的错误
        Args:
            error_type: ERROR_TEMPLATES 中的 key
            **kwargs: 填充模板用的参数
        """
        template = ERROR_TEMPLATES.get(error_type, f"错误: {error_type}")
        try:
            message = template.format(**kwargs)
        except (KeyError, ValueError):
            message = template
        return self.error(message)

    def format_success(self, operation: str, details: Dict[str, Any] = None) -> str:
        """格式化操作成功的详细总结"""
        if not details:
            return self.success(f"{operation} 成功")
        
        detail_lines = []
        for key, value in details.items():
            detail_lines.append(f"  {key}: {value}")
        
        details_str = "\n".join(detail_lines)
        return self.success(f"{operation} 成功\n{details_str}")

    def format_table(
        self,
        headers: List[str],
        rows: List[List[Any]],
        column_widths: Optional[List[int]] = None
    ) -> str:
        """格式化对齐的表格字符串
        Args:
            headers: 表头列表
            rows: 数据行列表
            column_widths: 可选的列宽限制
        """
        if not headers:
            return ""

        # 自动计算列宽
        if column_widths is None:
            column_widths = []
            for i, header in enumerate(headers):
                max_width = len(str(header))
                for row in rows:
                    if i < len(row):
                        max_width = max(max_width, len(str(row[i])))
                column_widths.append(max_width)

        lines = []

        # 格式化头部
        header_row = ""
        for i, header in enumerate(headers):
            width = column_widths[i] if i < len(column_widths) else len(header)
            header_row += f"{str(header).ljust(width)}  "
        lines.append(self.config.colorize(header_row, Color.BOLD))

        # 分隔线
        separator = ""
        for width in column_widths:
            separator += "-" * width + "  "
        lines.append(separator)

        # 格式化数据行
        for row in rows:
            data_row = ""
            for i, cell in enumerate(row):
                width = column_widths[i] if i < len(column_widths) else len(str(cell))
                data_row += f"{str(cell).ljust(width)}  "
            lines.append(data_row)

        return "\n".join(lines)

    def format_list(self, items: List[str], bullet: str = "*") -> str:
        """格式化列表"""
        lines = []
        for item in items:
            lines.append(f"{bullet} {item}")
        return "\n".join(lines)

    def format_key_value(self, items: Dict[str, Any]) -> str:
        """格式化键值对列表"""
        if not items:
            return ""
        max_key_len = max(len(str(k)) for k in items.keys())
        lines = []
        for key, value in items.items():
            lines.append(f"{str(key).ljust(max_key_len)}: {value}")
        return "\n".join(lines)


class TableExporter:
    """表格数据导出工具类"""

    @staticmethod
    def to_json(headers: List[str], rows: List[List[Any]]) -> str:
        """导出为 JSON 格式"""
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
        """导出为 CSV 格式"""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue()

    @staticmethod
    def to_tsv(headers: List[str], rows: List[List[Any]]) -> str:
        """导出为 TSV 格式"""
        output = io.StringIO()
        writer = csv.writer(output, delimiter='\t')
        writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue()


class ProgressBar:
    """CLI 进度条实现"""

    def __init__(self, total: int, config: Optional[FormatterConfig] = None, prefix: str = ""):
        self.total = total
        self.current = 0
        self.config = config or FormatterConfig()
        self.prefix = prefix

    def update(self, step: int = 1) -> str:
        """更新并返回进度条字符串"""
        self.current = min(self.current + step, self.total)
        percentage = int((self.current / self.total) * 100) if self.total > 0 else 0
        bar_length = 30
        filled = int(bar_length * self.current / self.total) if self.total > 0 else 0
        bar = "#" * filled + "-" * (bar_length - filled)
        return f"{self.prefix}[{bar}] {percentage}% ({self.current}/{self.total})"

    def reset(self) -> None:
        """重置进度"""
        self.current = 0


def format_summary(title: str, items: Dict[str, Any], config: Optional[FormatterConfig] = None) -> str:
    """生成格式化的摘要总结"""
    cfg = config or FormatterConfig()
    lines = []
    title_line = cfg.colorize(f" {title} " + "=" * (40 - len(title)), Color.BOLD)
    lines.append(title_line)

    if items:
        max_key_len = max(len(str(k)) for k in items.keys())
        for key, value in items.items():
            lines.append(f"  {str(key).ljust(max_key_len)}: {value}")
    
    lines.append("-" * 50)
    return "\n".join(lines)
