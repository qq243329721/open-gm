"""GM 缓存管理命令

提供缓存信息查看和清理功能。"""

import click
import shutil
from pathlib import Path
from typing import List

from gm.core.cache_manager import get_cache_manager
from gm.core.logger import get_logger
from gm.cli.utils import OutputFormatter, FormatterConfig

logger = get_logger("cache_command")


class CacheCommand:
    """缓存命令实现类"""
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
    
    def get_cache_info(self) -> dict:
        """获取缓存目录信息"""
        try:
            cache_dir = self.cache_manager.cache_path
            cache_size = self._calculate_cache_size(cache_dir)
            
            return {
                'cache_dir': str(cache_dir),
                'size_mb': round(cache_size, 2),
                'size_human': self._format_size(cache_size)
            }
        except Exception as e:
            logger.error("Failed to get cache info", error=str(e))
            raise
    
    def _calculate_cache_size(self, cache_dir: Path) -> float:
        """计算缓存大小 (MB)"""
        if not cache_dir.exists():
            return 0.0
        
        total_size = 0
        try:
            for item in cache_dir.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
        except Exception as e:
            logger.warning("Failed to calculate cache size", error=str(e))
            return 0.0
        
        return total_size / (1024 * 1024)
    
    def _format_size(self, size_mb: float) -> str:
        """格式化大小显示"""
        if size_mb < 1:
            size_kb = size_mb * 1024
            return f"{size_kb:.1f} KB"
        elif size_mb < 1024:
            return f"{size_mb:.1f} MB"
        else:
            size_gb = size_mb / 1024
            return f"{size_gb:.1f} GB"
    
    def clear_cache(self, clear_all: bool = False) -> dict:
        """清理缓存"""
        try:
            cache_dir = self.cache_manager.cache_path
            before_size = self._calculate_cache_size(cache_dir)
            
            if not cache_dir.exists():
                return {'success': True, 'freed_mb': 0}
            
            if clear_all:
                shutil.rmtree(cache_dir)
                cache_dir.mkdir(parents=True, exist_ok=True)
            else:
                self.cache_manager.cleanup_expired()
            
            after_size = self._calculate_cache_size(cache_dir)
            freed_size = before_size - after_size
            
            return {
                'success': True,
                'before_size_mb': round(before_size, 2),
                'after_size_mb': round(after_size, 2),
                'freed_mb': round(freed_size, 2)
            }
        except Exception as e:
            logger.error("Failed to clear cache", error=str(e))
            raise


@click.group()
@click.pass_context
def cache(ctx: click.Context) -> None:
    """管理 GM 缓存"""
    pass


@cache.command('info')
@click.pass_context
def cache_info(ctx: click.Context) -> None:
    """查看缓存状态"""
    no_color = ctx.obj.get('no_color', False)
    formatter = OutputFormatter(FormatterConfig(no_color=no_color))
    
    try:
        cmd = CacheCommand()
        info = cmd.get_cache_info()
        click.echo(formatter.info("缓存信息:"))
        click.echo(f"  路径: {info['cache_dir']}")
        click.echo(f"  大小: {info['size_human']}")
    except Exception as e:
        click.echo(formatter.error(f"获取失败: {str(e)}"), err=True)
        raise SystemExit(1)


@cache.command('clear')
@click.option('--all', is_flag=True, help='清理所有缓存')
@click.pass_context
def cache_clear(ctx: click.Context, all: bool) -> None:
    """清理过期或所有缓存"""
    no_color = ctx.obj.get('no_color', False)
    formatter = OutputFormatter(FormatterConfig(no_color=no_color))
    
    try:
        cmd = CacheCommand()
        click.echo(formatter.info("正在清理..."))
        result = cmd.clear_cache(clear_all=all)
        if result['success']:
            click.echo(formatter.success("清理完成!"))
            click.echo(f"  释放空间: {result['freed_mb']} MB")
    except Exception as e:
        click.echo(formatter.error(f"清理失败: {str(e)}"), err=True)
        raise SystemExit(1)
