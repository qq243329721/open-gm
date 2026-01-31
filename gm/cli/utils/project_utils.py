"""项目路径查找工具

提供类似 git 的目录查找机制，从当前目录逐级向上查找 GM 项目根目录。
"""

from pathlib import Path
from typing import Optional


class GMNotFoundError(Exception):
    """未找到 GM 项目的异常"""
    
    def __init__(self, start_path: Path):
        self.start_path = start_path
        super().__init__(
            f"fatal: not a gm repository (or any of the parent directories): .gm\n"
            f"searched from: {start_path}"
        )


def find_gm_root(start_path: Optional[Path] = None) -> Path:
    """查找 GM 项目根目录
    
    从起始目录开始，逐级向上查找包含 .gm 目录的目录。
    如果找到 .gm 目录，还会检查其中是否有 .git 目录以确保是有效的 GM 项目。
    
    特殊处理：如果当前目录就是 .gm 目录，返回其父目录作为项目根。
    
    类似 git 的行为：
    - 从当前目录开始向上查找
    - 查找 .gm 目录
    - 验证 .gm/.git 存在
    - 返回找到的项目根目录
    
    Args:
        start_path: 起始查找目录，默认为当前工作目录
        
    Returns:
        GM 项目根目录路径
        
    Raises:
        GMNotFoundError: 如果未找到有效的 GM 项目
    """
    if start_path is None:
        start_path = Path.cwd()
    
    current = start_path.resolve()
    
    # 特殊处理：如果当前目录就是 .gm 目录，直接返回其父目录
    if current.name == ".gm" and current.is_dir():
        parent = current.parent
        gm_git = current / ".git"
        if gm_git.exists():
            return parent
    
    # 逐级向上查找
    while True:
        gm_dir = current / ".gm"
        gm_git = gm_dir / ".git"
        
        # 检查 .gm 目录和 .gm/.git 是否存在
        if gm_dir.is_dir() and gm_git.exists():
            return current
        
        # 到达根目录仍未找到
        parent = current.parent
        if parent == current:
            raise GMNotFoundError(start_path)
        
        current = parent


def find_gm_root_optional(start_path: Optional[Path] = None) -> Optional[Path]:
    """查找 GM 项目根目录（可选版本）
    
    与 find_gm_root 相同，但不抛出异常，而是返回 None。
    
    Args:
        start_path: 起始查找目录，默认为当前工作目录
        
    Returns:
        GM 项目根目录路径，如果未找到则返回 None
    """
    try:
        return find_gm_root(start_path)
    except GMNotFoundError:
        return None
