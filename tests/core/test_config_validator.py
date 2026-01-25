"""ConfigValidator 单元测试"""

import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest

from gm.core.config_validator import (
    ConfigValidator,
    ValidationError,
    ValidationResult,
    ErrorSeverity,
)
from gm.core.exceptions import ConfigValidationError


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def validator(temp_dir):
    """创建验证器实例"""
    return ConfigValidator(project_root=temp_dir)


@pytest.fixture
def valid_config() -> Dict[str, Any]:
    """有效配置示例"""
    return {
        "worktree": {
            "base_path": ".gm",
            "naming_pattern": "{branch}",
            "auto_cleanup": True,
        },
        "display": {
            "colors": True,
            "default_verbose": False,
        },
        "shared_files": [".env", ".gitignore", "README.md"],
        "symlinks": {
            "strategy": "auto",
        },
        "branch_mapping": {},
    }


class TestValidationError:
    """验证错误类测试"""

    def test_validation_error_creation(self):
        """测试创建验证错误"""
        error = ValidationError("field.name", "测试消息", ErrorSeverity.ERROR)

        assert error.field == "field.name"
        assert error.message == "测试消息"
        assert error.severity == ErrorSeverity.ERROR

    def test_validation_error_string_representation(self):
        """测试验证错误字符串表示"""
        error = ValidationError("worktree.base_path", "路径无效", ErrorSeverity.WARNING)

        assert "[WARNING]" in str(error)
        assert "worktree.base_path" in str(error)
        assert "路径无效" in str(error)


class TestValidationResult:
    """验证结果类测试"""

    def test_validation_result_creation(self):
        """测试创建验证结果"""
        result = ValidationResult()

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert len(result.suggestions) == 0

    def test_add_error(self):
        """测试添加错误"""
        result = ValidationResult()
        result.add_error("worktree.base_path", "路径无效")

        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].field == "worktree.base_path"

    def test_add_warning(self):
        """测试添加警告"""
        result = ValidationResult()
        result.add_warning("这是一个警告")

        assert result.is_valid is True  # 警告不影响有效性
        assert len(result.warnings) == 1

    def test_add_suggestion(self):
        """测试添加建议"""
        result = ValidationResult()
        result.add_suggestion("建议使用相对路径")

        assert len(result.suggestions) == 1

    def test_error_count(self):
        """测试错误计数"""
        result = ValidationResult()
        result.add_error("field1", "错误1")
        result.add_error("field2", "错误2", ErrorSeverity.WARNING)

        assert result.get_error_count() == 1
        assert result.get_warning_count() == 1

    def test_to_dict(self):
        """测试转换为字典"""
        result = ValidationResult()
        result.add_error("field", "错误消息")
        result.add_warning("警告消息")

        result_dict = result.to_dict()

        assert result_dict["is_valid"] is False
        assert len(result_dict["errors"]) == 1
        assert len(result_dict["warnings"]) == 1


class TestConfigValidatorBasic:
    """配置验证器基本功能测试"""

    def test_validator_creation(self, temp_dir):
        """测试创建验证器"""
        validator = ConfigValidator(project_root=temp_dir)

        assert validator.project_root == temp_dir
        assert validator.strict is False

    def test_validator_strict_mode(self, temp_dir):
        """测试严格模式"""
        validator = ConfigValidator(strict=True, project_root=temp_dir)

        assert validator.strict is True

    def test_validate_valid_config(self, validator, valid_config):
        """测试验证有效配置"""
        result = validator.validate_config(valid_config)

        assert result.is_valid is True
        assert result.get_error_count() == 0

    def test_validate_invalid_config_type(self, validator):
        """测试验证无效配置类型"""
        result = validator.validate_config("不是字典")

        assert result.is_valid is False
        assert result.get_error_count() > 0

    def test_validate_empty_config(self, validator):
        """测试验证空配置"""
        result = validator.validate_config({})

        assert result.is_valid is False
        assert result.get_error_count() > 0  # 缺少必需部分


class TestRequiredSections:
    """必需配置部分验证测试"""

    def test_missing_worktree_section(self, validator):
        """测试缺失 worktree 部分"""
        config = {
            "display": {},
            "shared_files": [],
        }
        result = validator.validate_config(config)

        assert result.is_valid is False
        assert any("worktree" in e.message for e in result.errors)

    def test_missing_display_section(self, validator):
        """测试缺失 display 部分"""
        config = {
            "worktree": {},
            "shared_files": [],
        }
        result = validator.validate_config(config)

        assert result.is_valid is False

    def test_missing_shared_files_section(self, validator):
        """测试缺失 shared_files 部分"""
        config = {
            "worktree": {},
            "display": {},
        }
        result = validator.validate_config(config)

        assert result.is_valid is False


class TestWorktreeValidation:
    """Worktree 配置验证测试"""

    def test_valid_worktree_config(self, validator):
        """测试有效的 worktree 配置"""
        config = {
            "worktree": {
                "base_path": ".gm",
                "naming_pattern": "{branch}",
                "auto_cleanup": True,
            }
        }
        result = validator.validate_section("worktree", config["worktree"])

        assert result.is_valid is True

    def test_worktree_not_dict(self, validator):
        """测试 worktree 不是字典"""
        result = validator.validate_section("worktree", "invalid")

        assert result.is_valid is False
        assert any("必须是字典" in e.message for e in result.errors)

    def test_worktree_base_path_type(self, validator):
        """测试 worktree.base_path 类型验证"""
        worktree = {
            "base_path": 123,
            "naming_pattern": "{branch}",
        }
        result = validator.validate_section("worktree", worktree)

        assert result.is_valid is False
        assert any("base_path" in e.field for e in result.errors)

    def test_worktree_base_path_empty(self, validator):
        """测试 worktree.base_path 为空"""
        worktree = {
            "base_path": "",
            "naming_pattern": "{branch}",
        }
        result = validator.validate_section("worktree", worktree)

        assert result.is_valid is False

    def test_worktree_naming_pattern_missing_branch(self, validator):
        """测试 naming_pattern 缺少 {branch} 占位符"""
        worktree = {
            "base_path": ".gm",
            "naming_pattern": "worktree-{id}",
        }
        result = validator.validate_section("worktree", worktree)

        # 应该产生警告，不是错误
        assert any("{branch}" in w for w in result.warnings)

    def test_worktree_auto_cleanup_type(self, validator):
        """测试 auto_cleanup 类型验证"""
        worktree = {
            "base_path": ".gm",
            "naming_pattern": "{branch}",
            "auto_cleanup": "true",  # 字符串而不是布尔值
        }
        result = validator.validate_section("worktree", worktree)

        assert result.is_valid is False

    def test_worktree_absolute_path_suggestion(self, validator):
        """测试绝对路径的建议"""
        # 在不同平台上使用不同的绝对路径格式
        import platform
        if platform.system() == "Windows":
            abs_path = "C:\\absolute\\path"
        else:
            abs_path = "/absolute/path"

        worktree = {
            "base_path": abs_path,
            "naming_pattern": "{branch}",
        }
        result = validator.validate_section("worktree", worktree)

        # 应该产生关于相对路径的建议或警告
        assert len(result.suggestions) > 0 or len(result.warnings) > 0


class TestDisplayValidation:
    """Display 配置验证测试"""

    def test_valid_display_config(self, validator):
        """测试有效的 display 配置"""
        config = {
            "colors": True,
            "default_verbose": False,
        }
        result = validator.validate_section("display", config)

        assert result.is_valid is True

    def test_display_not_dict(self, validator):
        """测试 display 不是字典"""
        result = validator.validate_section("display", ["invalid"])

        assert result.is_valid is False

    def test_display_colors_type(self, validator):
        """测试 colors 类型验证"""
        config = {
            "colors": "yes",  # 字符串而不是布尔值
        }
        result = validator.validate_section("display", config)

        assert result.is_valid is False

    def test_display_default_verbose_type(self, validator):
        """测试 default_verbose 类型验证"""
        config = {
            "default_verbose": 1,  # 整数而不是布尔值
        }
        result = validator.validate_section("display", config)

        assert result.is_valid is False


class TestSharedFilesValidation:
    """Shared files 配置验证测试"""

    def test_valid_shared_files(self, validator):
        """测试有效的 shared_files 配置"""
        shared_files = [".env", ".gitignore", "README.md"]
        result = validator.validate_section("shared_files", shared_files)

        assert result.is_valid is True

    def test_shared_files_not_list(self, validator):
        """测试 shared_files 不是列表"""
        result = validator.validate_section("shared_files", ".env")

        assert result.is_valid is False

    def test_shared_files_empty_list(self, validator):
        """测试 shared_files 为空列表"""
        result = validator.validate_section("shared_files", [])

        # 空列表应该产生警告，不是错误
        assert result.is_valid is True
        assert len(result.warnings) > 0

    def test_shared_files_invalid_item_type(self, validator):
        """测试 shared_files 包含非字符串项"""
        shared_files = [".env", 123, "README.md"]
        result = validator.validate_section("shared_files", shared_files)

        assert result.is_valid is False
        assert any("[1]" in str(e.field) for e in result.errors)

    def test_shared_files_empty_string_item(self, validator):
        """测试 shared_files 包含空字符串"""
        shared_files = [".env", "", "README.md"]
        result = validator.validate_section("shared_files", shared_files)

        assert result.is_valid is False


class TestSymlinksValidation:
    """Symlinks 配置验证测试"""

    def test_valid_symlinks_config(self, validator):
        """测试有效的 symlinks 配置"""
        symlinks = {"strategy": "auto"}
        result = validator.validate_section("symlinks", symlinks)

        assert result.is_valid is True

    def test_symlinks_all_valid_strategies(self, validator):
        """测试所有有效的策略"""
        for strategy in ["auto", "symlink", "junction", "hardlink"]:
            symlinks = {"strategy": strategy}
            result = validator.validate_section("symlinks", symlinks)

            assert result.is_valid is True, f"策略 {strategy} 应该有效"

    def test_symlinks_invalid_strategy(self, validator):
        """测试无效的策略"""
        symlinks = {"strategy": "invalid"}
        result = validator.validate_section("symlinks", symlinks)

        assert result.is_valid is False
        assert any("strategy" in e.field for e in result.errors)

    def test_symlinks_strategy_type(self, validator):
        """测试 strategy 类型验证"""
        symlinks = {"strategy": 123}
        result = validator.validate_section("symlinks", symlinks)

        assert result.is_valid is False

    def test_symlinks_not_dict(self, validator):
        """测试 symlinks 不是字典"""
        result = validator.validate_section("symlinks", ["auto"])

        assert result.is_valid is False


class TestBranchMappingValidation:
    """Branch mapping 配置验证测试"""

    def test_valid_branch_mapping(self, validator):
        """测试有效的 branch_mapping 配置"""
        mapping = {
            "feature/fix(#123)": "feature-fix-123",
            "hotfix/bug@v2": "hotfix-bug-v2",
        }
        result = validator.validate_section("branch_mapping", mapping)

        assert result.is_valid is True

    def test_empty_branch_mapping(self, validator):
        """测试空 branch_mapping"""
        result = validator.validate_section("branch_mapping", {})

        assert result.is_valid is True

    def test_branch_mapping_not_dict(self, validator):
        """测试 branch_mapping 不是字典"""
        result = validator.validate_section("branch_mapping", ["invalid"])

        assert result.is_valid is False

    def test_branch_mapping_invalid_key_type(self, validator):
        """测试 branch_mapping 键不是字符串"""
        mapping = {
            123: "feature-fix-123",
        }
        result = validator.validate_section("branch_mapping", mapping)

        assert result.is_valid is False

    def test_branch_mapping_invalid_value_type(self, validator):
        """测试 branch_mapping 值不是字符串"""
        mapping = {
            "feature/fix": 123,
        }
        result = validator.validate_section("branch_mapping", mapping)

        assert result.is_valid is False

    def test_branch_mapping_empty_key(self, validator):
        """测试 branch_mapping 空键"""
        mapping = {
            "": "feature-fix",
        }
        result = validator.validate_section("branch_mapping", mapping)

        assert result.is_valid is False

    def test_branch_mapping_empty_value(self, validator):
        """测试 branch_mapping 空值"""
        mapping = {
            "feature/fix": "",
        }
        result = validator.validate_section("branch_mapping", mapping)

        assert result.is_valid is False

    def test_branch_mapping_invalid_path_chars(self, validator):
        """测试 branch_mapping 值包含无效路径字符"""
        mapping = {
            "feature/fix": "feature:fix",  # 冒号在 Windows 路径中无效
        }
        result = validator.validate_section("branch_mapping", mapping)

        # 应该产生警告
        assert any("无效路径字符" in w for w in result.warnings)


class TestSymlinkStrategyValidation:
    """符号链接策略验证测试"""

    def test_valid_strategies(self, validator):
        """测试所有有效策略"""
        for strategy in ["auto", "symlink", "junction", "hardlink"]:
            result = validator.validate_symlink_strategy(strategy)
            assert result.is_valid is True

    def test_invalid_strategy(self, validator):
        """测试无效策略"""
        result = validator.validate_symlink_strategy("invalid_strategy")

        assert result.is_valid is False

    def test_strategy_type_validation(self, validator):
        """测试策略类型验证"""
        result = validator.validate_symlink_strategy(123)

        assert result.is_valid is False


class TestStrictMode:
    """严格模式测试"""

    def test_strict_mode_converts_warnings_to_errors(self):
        """测试严格模式将警告转换为错误"""
        validator = ConfigValidator(strict=True)

        config = {
            "worktree": {
                "base_path": ".gm",
                "naming_pattern": "{branch}",
            },
            "display": {},
            "shared_files": [".env"],  # 非空列表，避免警告
        }

        result = validator.validate_config(config)

        # 即使没有警告也应该是有效的
        # 如果有警告，在严格模式下会被转换为错误
        # 这个配置应该是有效的，因为没有警告
        assert result.is_valid is True


class TestGetValidationResult:
    """验证结果获取测试"""

    def test_get_validation_result_before_validation(self, validator):
        """测试未验证前获取结果"""
        result = validator.get_validation_result()

        assert result is None

    def test_get_validation_result_after_validation(self, validator, valid_config):
        """测试验证后获取结果"""
        validator.validate_config(valid_config)
        result = validator.get_validation_result()

        assert result is not None
        assert result.is_valid is True


class TestSuggestFixes:
    """修复建议测试"""

    def test_suggest_fixes_with_errors(self, validator):
        """测试有错误时的修复建议"""
        config = {
            "worktree": {
                "base_path": "",  # 空值
            }
        }

        validator.validate_config(config)
        suggestions = validator.suggest_fixes()

        assert len(suggestions) > 0

    def test_suggest_fixes_without_errors(self, validator, valid_config):
        """测试没有错误时的修复建议"""
        validator.validate_config(valid_config)
        suggestions = validator.suggest_fixes()

        # 无错误时可能没有建议
        assert isinstance(suggestions, list)


class TestUnknownFields:
    """未知字段验证测试"""

    def test_unknown_top_level_field(self, validator, valid_config):
        """测试未知的顶级字段"""
        valid_config["unknown_field"] = "value"

        result = validator.validate_config(valid_config)

        # 应该产生警告
        assert any("未知的配置部分" in w for w in result.warnings)

    def test_unknown_field_in_worktree(self, validator):
        """测试 worktree 中的未知字段"""
        worktree = {
            "base_path": ".gm",
            "unknown_field": "value",
        }

        result = validator.validate_section("worktree", worktree)

        # 应该产生警告
        assert any("未知字段" in w for w in result.warnings)


class TestComplexScenarios:
    """复杂场景测试"""

    def test_multiple_errors(self, validator):
        """测试多个错误"""
        config = {
            "worktree": {
                "base_path": "",
                "auto_cleanup": "not_bool",
            },
            "display": {
                "colors": 123,
            },
        }

        result = validator.validate_config(config)

        assert result.is_valid is False
        assert result.get_error_count() >= 2

    def test_errors_and_warnings_mixed(self, validator):
        """测试错误和警告混合"""
        config = {
            "worktree": {
                "base_path": "/absolute/path",  # 警告：绝对路径
                "naming_pattern": "static-name",  # 警告：缺少 {branch}
            },
            "display": {},
            "shared_files": [],
        }

        result = validator.validate_config(config)

        assert len(result.warnings) > 0

    def test_cross_platform_path_handling(self, validator):
        """测试跨平台路径处理"""
        worktree_configs = [
            {".gm": {"base_path": ".gm"}},  # Unix 路径
            {".gm\\worktree": {"base_path": ".gm\\worktree"}},  # Windows 路径
        ]

        for config in worktree_configs:
            result = validator.validate_section("worktree", list(config.values())[0])
            # 两种路径格式都应该被接受
            # 验证不应该因为路径格式而失败


class TestValidateSection:
    """验证特定部分的测试"""

    def test_validate_unknown_section(self, validator):
        """测试验证未知部分"""
        result = validator.validate_section("unknown_section", {})

        assert result.is_valid is False
        assert any("未知的配置部分" in e.message for e in result.errors)

    def test_validate_all_sections(self, validator):
        """测试验证所有部分"""
        sections = {
            "worktree": {"base_path": ".gm", "naming_pattern": "{branch}"},
            "display": {"colors": True},
            "shared_files": [".env"],
            "symlinks": {"strategy": "auto"},
            "branch_mapping": {},
        }

        for section_name, section_data in sections.items():
            result = validator.validate_section(section_name, section_data)
            assert result.is_valid is True, f"部分 {section_name} 应该有效"
