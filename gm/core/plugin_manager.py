"""插件管理器实现

提供插件加载和生命周期管理功能，支持 worktree 事件触发。"""

from typing import Dict, List, Optional, TYPE_CHECKING
from pathlib import Path
import importlib.util

from gm.core.logger import get_logger

if TYPE_CHECKING:
    from gm.core.interfaces.plugin import IPlugin, IWorktreePlugin
    from gm.core.interfaces.config import IConfigManager
    from gm.core.data_structures import WorktreeInfo


class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self._plugins: Dict[str, 'IPlugin'] = {}
        self._worktree_plugins: List['IWorktreePlugin'] = []
        self._config_manager: Optional['IConfigManager'] = None
        self.logger = get_logger(__name__).bind(component="plugin_manager")
        self._initialized = False
    
    def set_config_manager(self, config_manager: 'IConfigManager') -> None:
        """设置配置管理器"""
        self._config_manager = config_manager
    
    def load_plugin(self, plugin_path: str) -> None:
        """从指定路径加载插件"""
        try:
            spec = importlib.util.spec_from_file_location("plugin", plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                # 简单检查类是否符合插件接口（名称和版本属性）
                if (isinstance(attr, type) and 
                    hasattr(attr, 'name') and
                    hasattr(attr, 'version')):
                    
                    plugin = attr()
                    self._plugins[plugin.name] = plugin
                    
                    # 检查是否为 Worktree 插件
                    if hasattr(attr, 'on_worktree_created'):
                        from gm.core.interfaces.plugin import IWorktreePlugin
                        if isinstance(plugin, IWorktreePlugin):
                            self._worktree_plugins.append(plugin)
                            self.logger.info("Worktree plugin loaded", 
                                           plugin_name=plugin.name, 
                                           version=plugin.version)
                        
        except Exception as e:
            self.logger.error("Failed to load plugin", 
                            plugin_path=plugin_path, error=str(e))
    
    def initialize_plugins(self) -> None:
        """初始化所有加载的插件"""
        if not self._config_manager:
            self.logger.warning("Cannot initialize plugins: no config manager")
            return
            
        for plugin in self._plugins.values():
            try:
                plugin.initialize(self._config_manager)
                self.logger.info("Plugin initialized", 
                               plugin_name=plugin.name, 
                               version=plugin.version)
            except Exception as e:
                self.logger.error("Plugin initialization failed", 
                                plugin_name=plugin.name, error=str(e))
        
        self._initialized = True
    
    def trigger_worktree_created(self, worktree_info: 'WorktreeInfo') -> None:
        """触发 worktree 创建事件"""
        if not self._initialized:
            self.logger.warning("Plugins not initialized, skipping worktree created event")
            return
            
        for plugin in self._worktree_plugins:
            try:
                plugin.on_worktree_created(worktree_info)
                self.logger.debug("Plugin executed on worktree created", 
                                plugin=plugin.name, worktree=worktree_info.name)
            except Exception as e:
                self.logger.warning("Plugin failed on worktree created", 
                                  plugin=plugin.name, error=str(e))
    
    def trigger_worktree_removed(self, worktree_info: 'WorktreeInfo') -> None:
        """触发 worktree 移除事件"""
        if not self._initialized:
            self.logger.warning("Plugins not initialized, skipping worktree removed event")
            return
            
        for plugin in self._worktree_plugins:
            try:
                plugin.on_worktree_removed(worktree_info)
                self.logger.debug("Plugin executed on worktree removed", 
                                plugin=plugin.name, worktree=worktree_info.name)
            except Exception as e:
                self.logger.warning("Plugin failed on worktree removed", 
                                  plugin=plugin.name, error=str(e))
    
    def load_plugins(self, plugin_dirs: Optional[List[str]] = None) -> None:
        """从多个目录加载插件"""
        if plugin_dirs is None:
            plugin_dirs = ["plugins"]
            
        for plugin_dir in plugin_dirs:
            plugin_path = Path(plugin_dir)
            if plugin_path.exists():
                self.logger.info("Loading plugins from directory", directory=str(plugin_path))
                for plugin_file in plugin_path.glob("*.py"):
                    if plugin_file.name != "__init__.py":
                        try:
                            self.load_plugin(str(plugin_file))
                        except Exception as e:
                            self.logger.warning("Failed to load plugin", 
                                             file=str(plugin_file), error=str(e))

    def trigger_worktree_updated(self, worktree_info: 'WorktreeInfo') -> None:
        """触发 worktree 更新事件"""
        if not self._initialized:
            self.logger.warning("Plugins not initialized, skipping worktree updated event")
            return
            
        for plugin in self._worktree_plugins:
            try:
                plugin.on_worktree_updated(worktree_info)
                self.logger.debug("Plugin executed on worktree updated", 
                                plugin=plugin.name, worktree=worktree_info.name)
            except Exception as e:
                self.logger.warning("Plugin failed on worktree updated", 
                                  plugin=plugin.name, error=str(e))
