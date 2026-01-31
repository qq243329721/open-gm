"""配置管理接口定义"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pathlib import Path


class IConfigManager(ABC):
    """配置管理器接口"""
    
    @abstractmethod
    def load_config(self) -> 'GMConfig':
        """加载配置"""
        pass
    
    @abstractmethod
    def save_config(self, config: 'GMConfig') -> None:
        """保存配置"""
        pass
    
    @abstractmethod
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取特定配置节"""
        pass
    
    @abstractmethod
    def validate_config(self, config: 'GMConfig') -> List[str]:
        """验证配置有效性"""
        pass


# 类型提示支持
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gm.core.data_structures import GMConfig
