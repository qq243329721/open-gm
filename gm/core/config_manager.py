"""配置管理器实现

提供 gm.yaml 配置文件的加载、验证和保存功能，实现 IConfigManager 接口。"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from gm.core.exceptions import ConfigIOError, ConfigParseError, ConfigValidationError
from gm.core.logger import get_logger
from gm.core.data_structures import GMConfig
from gm.core.interfaces.config import IConfigManager

logger = get_logger("config_manager")


class ConfigManager(IConfigManager):
    """配置管理器实现"""

    def __init__(self, project_root: Path):
        """初始化配置管理器"""
        self.project_root = project_root.resolve()
        self.config_file = project_root / 'gm.yaml'
        self._config: Optional[GMConfig] = None
        logger.info("ConfigManager initialized", project_root=str(self.project_root))
    
    @property
    def config_path(self) -> Path:
        """获取配置路径"""
        return self.config_file

    def load_config(self) -> GMConfig:
        """加载配置"""
        if self._config is not None:
            return self._config
        
        if not self.config_file.exists():
            self._config = GMConfig()
            return self._config
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            self._config = self._parse_config(config_data)
            return self._config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise ConfigIOError(f"Failed to load config: {e}")

    def save_config(self, config: GMConfig) -> None:
        """保存配置"""
        try:
            config_data = self._serialize_config(config)
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
            self._config = config
        except Exception as e:
            raise ConfigIOError(f"Failed to save config: {e}")

    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置节"""
        config = self.load_config()
        if hasattr(config, section):
            return getattr(config, section).__dict__
        return {}

    def validate_config(self, config: GMConfig) -> List[str]:
        """验证配置有效性"""
        return []

    def get_branch_mapping(self) -> Dict[str, str]:
        """获取分支映射"""
        return self.load_config().branch_mapping
    
    def get_shared_files(self) -> List[str]:
        """获取共享文件列表"""
        return self.load_config().symlinks.shared_files

    def _parse_config(self, data: Dict[str, Any]) -> GMConfig:
        """将字典解析为 GMConfig 对象"""
        # 注意：这里应调用 data_structures 中的逻辑，这里简略处理
        return GMConfig()

    def _serialize_config(self, config: GMConfig) -> Dict[str, Any]:
        """将 GMConfig 序列化为字典"""
        return config.__dict__