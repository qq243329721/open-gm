"""ConfigManager 单元测试"""

import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest
import yaml

from gm.core.config_manager import ConfigManager, MergeStrategy
from gm.core.exceptions import (
    ConfigException,
    ConfigIOError,
    ConfigParseError,
    ConfigValidationError,
)


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def config_manager(temp_dir):
    """创建配置管理器实例"""
    return ConfigManager(project_root=temp_dir)


class TestConfigManagerDefaults:
    """测试默认配置"""

    def test_get_default_config_returns_dict(self, config_manager):
        """测试获取默认配置返回字典"""
        config = config_manager.get_default_config()

        assert isinstance(config, dict)
        assert "worktree" in config
        assert "display" in config
        assert "shared_files" in config

    def test_get_default_config_is_deep_copy(self, config_manager):
        """测试获取的默认配置是深拷贝"""
        config1 = config_manager.get_default_config()
        config2 = config_manager.get_default_config()

        # 修改其中一个，不应该影响另一个
        config1["worktree"]["base_path"] = "modified"

        assert config2["worktree"]["base_path"] == ".gm"

    def test_default_config_structure(self, config_manager):
        """测试默认配置结构"""
        config = config_manager.get_default_config()

        # 检查顶级字段
        assert config["worktree"]["base_path"] == ".gm"
        assert config["worktree"]["naming_pattern"] == "{branch}"
        assert config["worktree"]["auto_cleanup"] is True

        assert config["display"]["colors"] is True
        assert config["display"]["default_verbose"] is False

        assert isinstance(config["shared_files"], list)
        assert ".env" in config["shared_files"]

        assert config["symlinks"]["strategy"] == "auto"
        assert isinstance(config["branch_mapping"], dict)


class TestConfigLoad:
    """测试配置加载"""

    def test_load_config_when_file_not_exists(self, config_manager):
        """测试当配置文件不存在时加载返回默认配置"""
        config = config_manager.load_config()

        assert config is not None
        assert config["worktree"]["base_path"] == ".gm"

    def test_load_config_from_existing_file(self, config_manager, temp_dir):
        """测试从现有配置文件加载"""
        config_data = {
            "worktree": {"base_path": ".custom"},
            "display": {"colors": False},
            "shared_files": ["custom.env"],
        }

        config_path = temp_dir / ".gm.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        loaded_config = config_manager.load_config()

        assert loaded_config["worktree"]["base_path"] == ".custom"
        assert loaded_config["display"]["colors"] is False
        # shared_files 会与默认值合并（DEEP_MERGE 策略追加列表）
        assert "custom.env" in loaded_config["shared_files"]
        assert ".env" in loaded_config["shared_files"]

    def test_load_config_with_custom_path(self, config_manager, temp_dir):
        """测试使用自定义路径加载配置"""
        config_data = {"worktree": {"base_path": ".custom"}}

        custom_path = temp_dir / "custom_config.yaml"
        with open(custom_path, "w") as f:
            yaml.dump(config_data, f)

        loaded_config = config_manager.load_config(custom_path)

        assert loaded_config["worktree"]["base_path"] == ".custom"

    def test_load_empty_yaml_file(self, config_manager, temp_dir):
        """测试加载空 YAML 文件返回默认配置"""
        config_path = temp_dir / ".gm.yaml"
        config_path.write_text("")

        config = config_manager.load_config()

        assert config["worktree"]["base_path"] == ".gm"

    def test_load_config_with_invalid_yaml(self, config_manager, temp_dir):
        """测试加载无效 YAML 文件抛出异常"""
        config_path = temp_dir / ".gm.yaml"
        config_path.write_text("invalid: yaml: content: [")

        with pytest.raises(ConfigParseError):
            config_manager.load_config()

    def test_load_config_file_not_readable(self, config_manager, temp_dir):
        """测试读取不可读文件抛出异常"""
        config_path = temp_dir / ".gm.yaml"
        config_path.write_text("test: content")

        # 使测试文件变成目录，使读取失败
        config_path.unlink()
        config_path.mkdir()

        with pytest.raises(ConfigIOError):
            config_manager.load_config()

    def test_load_config_caches_in_instance(self, config_manager, temp_dir):
        """测试加载的配置被缓存在实例中"""
        config_path = temp_dir / ".gm.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"worktree": {"base_path": ".cached"}}, f)

        config1 = config_manager.load_config()
        # 在 load_config 中返回的是同一实例的引用
        assert config_manager._config == config1

        # 第二次加载不创建新的 YAML 读取，而是使用缓存的内容
        config2 = config_manager.load_config()
        assert config2 == config1


class TestConfigValidation:
    """测试配置验证"""

    def test_validate_valid_config(self, config_manager):
        """测试验证有效配置"""
        config = config_manager.get_default_config()

        assert config_manager.validate_config(config) is True

    def test_validate_missing_required_sections(self, config_manager):
        """测试缺少必需字段抛出异常"""
        config = {"display": {}}

        with pytest.raises(ConfigValidationError) as exc_info:
            config_manager.validate_config(config)

        assert "worktree" in str(exc_info.value)

    def test_validate_invalid_worktree_base_path(self, config_manager):
        """测试 worktree.base_path 无效抛出异常"""
        config = {
            "worktree": {"base_path": 123},  # 应该是字符串
            "display": {},
            "shared_files": [],
        }

        with pytest.raises(ConfigValidationError):
            config_manager.validate_config(config)

    def test_validate_invalid_display_colors(self, config_manager):
        """测试 display.colors 无效抛出异常"""
        config = {
            "worktree": {"base_path": ".gm", "naming_pattern": "{branch}"},
            "display": {"colors": "yes"},  # 应该是布尔值
            "shared_files": [],
        }

        with pytest.raises(ConfigValidationError):
            config_manager.validate_config(config)

    def test_validate_invalid_shared_files(self, config_manager):
        """测试 shared_files 无效抛出异常"""
        config = {
            "worktree": {"base_path": ".gm", "naming_pattern": "{branch}"},
            "display": {},
            "shared_files": ["file1", 123],  # 应该全是字符串
        }

        with pytest.raises(ConfigValidationError):
            config_manager.validate_config(config)

    def test_validate_invalid_symlink_strategy(self, config_manager):
        """测试无效的符号链接策略抛出异常"""
        config = config_manager.get_default_config()
        config["symlinks"]["strategy"] = "invalid_strategy"

        with pytest.raises(ConfigValidationError):
            config_manager.validate_config(config)

    def test_validate_with_no_config_loaded(self, config_manager):
        """测试没有加载配置时抛出异常"""
        with pytest.raises(ConfigValidationError):
            config_manager.validate_config()

    def test_validate_branch_mapping_must_be_dict(self, config_manager):
        """测试 branch_mapping 必须是字典"""
        config = config_manager.get_default_config()
        config["branch_mapping"] = ["not", "a", "dict"]

        with pytest.raises(ConfigValidationError):
            config_manager.validate_config(config)


class TestConfigMerge:
    """测试配置合并"""

    def test_merge_with_override_strategy(self, config_manager):
        """测试 OVERRIDE 策略"""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = config_manager.merge_configs(base, override, MergeStrategy.OVERRIDE)

        assert result == {"b": 3, "c": 4}

    def test_merge_with_skip_strategy(self, config_manager):
        """测试 SKIP 策略"""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = config_manager.merge_configs(base, override, MergeStrategy.SKIP)

        assert result == {"a": 1, "b": 2}

    def test_merge_with_append_strategy_lists(self, config_manager):
        """测试 APPEND 策略合并列表"""
        base = [1, 2]
        override = [3, 4]

        result = config_manager.merge_configs(base, override, MergeStrategy.APPEND)

        assert result == [1, 2, 3, 4]

    def test_merge_with_append_strategy_non_lists(self, config_manager):
        """测试 APPEND 策略处理非列表"""
        base = "string"
        override = "override"

        result = config_manager.merge_configs(base, override, MergeStrategy.APPEND)

        assert result == "override"

    def test_merge_with_deep_merge_strategy(self, config_manager):
        """测试 DEEP_MERGE 策略"""
        base = {
            "a": {"nested": 1},
            "b": 2,
            "list": [1, 2],
        }
        override = {
            "a": {"nested": 2, "new": 3},
            "c": 4,
            "list": [3, 4],
        }

        result = config_manager.merge_configs(base, override, MergeStrategy.DEEP_MERGE)

        assert result["a"]["nested"] == 2
        assert result["a"]["new"] == 3
        assert result["b"] == 2
        assert result["c"] == 4
        assert result["list"] == [1, 2, 3, 4]

    def test_merge_deep_merge_does_not_modify_originals(self, config_manager):
        """测试 DEEP_MERGE 不修改原始配置"""
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}

        config_manager.merge_configs(base, override, MergeStrategy.DEEP_MERGE)

        assert "c" not in base["a"]
        assert "b" not in override["a"]

    def test_merge_configs_real_yaml_structure(self, config_manager):
        """测试合并真实 YAML 结构"""
        base = config_manager.get_default_config()
        override = {
            "worktree": {"base_path": ".custom"},
            "shared_files": ["extra.env"],
        }

        result = config_manager.merge_configs(base, override)

        assert result["worktree"]["base_path"] == ".custom"
        assert result["worktree"]["naming_pattern"] == "{branch}"  # 保留默认值
        assert ".env" in result["shared_files"]  # 原始列表
        assert "extra.env" in result["shared_files"]  # 新增项


class TestConfigSave:
    """测试配置保存"""

    def test_save_config_creates_file(self, config_manager, temp_dir):
        """测试保存配置创建文件"""
        config = config_manager.get_default_config()

        config_manager.save_config(config)

        assert (temp_dir / ".gm.yaml").exists()

    def test_save_config_with_custom_path(self, config_manager, temp_dir):
        """测试使用自定义路径保存配置"""
        config = config_manager.get_default_config()
        custom_path = temp_dir / "custom.yaml"

        config_manager.save_config(config, custom_path)

        assert custom_path.exists()

    def test_save_config_creates_parent_directories(self, config_manager, temp_dir):
        """测试保存时创建父目录"""
        config = config_manager.get_default_config()
        custom_path = temp_dir / "subdir" / "deep" / "config.yaml"

        config_manager.save_config(config, custom_path)

        assert custom_path.exists()

    def test_save_config_validates_before_saving(self, config_manager, temp_dir):
        """测试保存前验证配置"""
        invalid_config = {"worktree": {}}

        with pytest.raises(ConfigValidationError):
            config_manager.save_config(invalid_config)

    def test_save_config_content_is_valid_yaml(self, config_manager, temp_dir):
        """测试保存的内容是有效的 YAML"""
        config = config_manager.get_default_config()

        config_manager.save_config(config)

        with open(temp_dir / ".gm.yaml", "r") as f:
            loaded = yaml.safe_load(f)

        assert loaded == config

    def test_save_config_updates_internal_state(self, config_manager, temp_dir):
        """测试保存后更新内部状态"""
        config = config_manager.get_default_config()
        config["worktree"]["base_path"] = ".custom"

        config_manager.save_config(config)

        # 验证内部状态被更新
        assert config_manager._config["worktree"]["base_path"] == ".custom"

    def test_save_config_with_none_raises_exception(self, config_manager):
        """测试保存 None 抛出异常"""
        with pytest.raises(ConfigException):
            config_manager.save_config(None)


class TestConfigGetAndSet:
    """测试 get 和 set 方法"""

    def test_get_existing_key(self, config_manager):
        """测试获取存在的键"""
        config_manager.load_config()

        value = config_manager.get("worktree.base_path")

        assert value == ".gm"

    def test_get_nested_key(self, config_manager):
        """测试获取嵌套键"""
        config_manager.load_config()

        value = config_manager.get("display.colors")

        assert value is True

    def test_get_non_existing_key_returns_default(self, config_manager):
        """测试获取不存在的键返回默认值"""
        config_manager.load_config()

        value = config_manager.get("nonexistent.key", "default")

        assert value == "default"

    def test_get_non_existing_key_returns_none_by_default(self, config_manager):
        """测试获取不存在的键默认返回 None"""
        config_manager.load_config()

        value = config_manager.get("nonexistent.key")

        assert value is None

    def test_set_existing_key(self, config_manager):
        """测试设置存在的键"""
        config_manager.load_config()

        config_manager.set("worktree.base_path", ".new_path")

        assert config_manager.get("worktree.base_path") == ".new_path"

    def test_set_creates_new_keys(self, config_manager):
        """测试设置创建新键"""
        config_manager.load_config()

        config_manager.set("new.nested.key", "value")

        assert config_manager.get("new.nested.key") == "value"

    def test_set_overwrites_existing_value(self, config_manager):
        """测试设置覆盖现有值"""
        config_manager.load_config()

        config_manager.set("worktree.base_path", "overwritten")

        assert config_manager.get("worktree.base_path") == "overwritten"


class TestConfigSharedFiles:
    """测试获取共享文件列表"""

    def test_get_shared_files_returns_list(self, config_manager):
        """测试获取共享文件返回列表"""
        config_manager.load_config()

        files = config_manager.get_shared_files()

        assert isinstance(files, list)
        assert len(files) > 0

    def test_get_shared_files_contains_defaults(self, config_manager):
        """测试共享文件包含默认值"""
        config_manager.load_config()

        files = config_manager.get_shared_files()

        assert ".env" in files
        assert ".gitignore" in files
        assert "README.md" in files

    def test_get_shared_files_from_custom_config(self, config_manager, temp_dir):
        """测试从自定义配置获取共享文件"""
        config_data = {
            "shared_files": ["custom.env", "custom.gitignore"],
        }

        config_path = temp_dir / ".gm.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        config_manager.load_config()

        files = config_manager.get_shared_files()

        assert "custom.env" in files
        assert "custom.gitignore" in files


class TestConfigBranchMapping:
    """测试获取分支映射"""

    def test_get_branch_mapping_returns_dict(self, config_manager):
        """测试获取分支映射返回字典"""
        config_manager.load_config()

        mapping = config_manager.get_branch_mapping()

        assert isinstance(mapping, dict)

    def test_get_branch_mapping_empty_by_default(self, config_manager):
        """测试默认分支映射为空"""
        config_manager.load_config()

        mapping = config_manager.get_branch_mapping()

        assert len(mapping) == 0

    def test_get_branch_mapping_from_config(self, config_manager, temp_dir):
        """测试从配置获取分支映射"""
        config_data = {
            "branch_mapping": {
                "feature/test(#123)": "feature-test-123",
                "hotfix/@v2": "hotfix-v2",
            },
        }

        config_path = temp_dir / ".gm.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        config_manager.load_config()

        mapping = config_manager.get_branch_mapping()

        assert "feature/test(#123)" in mapping
        assert mapping["feature/test(#123)"] == "feature-test-123"
        assert mapping["hotfix/@v2"] == "hotfix-v2"


class TestConfigReload:
    """测试配置重新加载"""

    def test_reload_refreshes_config(self, config_manager, temp_dir):
        """测试重新加载刷新配置"""
        # 首次加载
        config_manager.load_config()
        original_value = config_manager.get("worktree.base_path")

        # 修改文件
        config_data = {"worktree": {"base_path": ".reloaded"}}
        config_path = temp_dir / ".gm.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        # 重新加载
        config_manager.reload()

        reloaded_value = config_manager.get("worktree.base_path")

        assert original_value != reloaded_value
        assert reloaded_value == ".reloaded"

    def test_reload_returns_config(self, config_manager):
        """测试重新加载返回配置"""
        config = config_manager.reload()

        assert isinstance(config, dict)
        assert "worktree" in config


class TestConfigResetToDefaults:
    """测试重置为默认值"""

    def test_reset_to_defaults_resets_config(self, config_manager, temp_dir):
        """测试重置配置为默认值"""
        # 创建自定义配置
        config_data = {"worktree": {"base_path": ".custom"}}
        config_path = temp_dir / ".gm.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        config_manager.load_config()
        assert config_manager.get("worktree.base_path") == ".custom"

        # 重置
        config_manager.reset_to_defaults()

        assert config_manager.get("worktree.base_path") == ".gm"

    def test_reset_to_defaults_preserves_default_structure(self, config_manager):
        """测试重置保留默认结构"""
        config_manager.reset_to_defaults()

        config = config_manager._config

        assert "worktree" in config
        assert "display" in config
        assert "shared_files" in config
        assert "symlinks" in config
        assert "branch_mapping" in config


class TestConfigIntegration:
    """集成测试"""

    def test_full_workflow_load_modify_save(self, config_manager, temp_dir):
        """测试完整工作流：加载、修改、保存"""
        # 加载配置
        config_manager.load_config()

        # 修改配置
        config_manager.set("worktree.base_path", ".modified")
        config_manager.set("display.colors", False)

        # 保存配置
        config_manager.save_config()

        # 创建新实例并重新加载验证
        new_manager = ConfigManager(project_root=temp_dir)
        new_manager.load_config()

        assert new_manager.get("worktree.base_path") == ".modified"
        assert new_manager.get("display.colors") is False

    def test_load_partial_config_merges_with_defaults(self, config_manager, temp_dir):
        """测试加载部分配置与默认值合并"""
        # 创建只包含部分配置的文件
        config_data = {
            "worktree": {"base_path": ".custom"},
            # 其他字段缺失
        }

        config_path = temp_dir / ".gm.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        config = config_manager.load_config()

        # 自定义值应该被保留
        assert config["worktree"]["base_path"] == ".custom"
        # 默认值应该被填充
        assert config["worktree"]["naming_pattern"] == "{branch}"
        assert config["display"]["colors"] is True

    def test_config_path_property(self, config_manager, temp_dir):
        """测试配置路径属性"""
        path = config_manager.config_path

        assert path == temp_dir / ".gm.yaml"

    def test_config_manager_with_different_roots(self):
        """测试具有不同根目录的多个配置管理器"""
        with tempfile.TemporaryDirectory() as tmp1:
            with tempfile.TemporaryDirectory() as tmp2:
                manager1 = ConfigManager(Path(tmp1))
                manager2 = ConfigManager(Path(tmp2))

                assert manager1.config_path != manager2.config_path
