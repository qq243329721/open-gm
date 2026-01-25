"""分支名称映射器 (BranchNameMapper) 单元测试

覆盖场景：
1. 默认映射规则
2. 自定义映射
3. 反向映射
4. 冲突检测
5. 特殊字符处理
6. 边界情况
7. 配置集成
"""

import pytest

from gm.core.branch_name_mapper import BranchNameMapper, ValidationError
from gm.core.exceptions import (
    InvalidMappingError,
    BranchMappingException,
)


class TestBranchNameMapperDefaults:
    """测试默认映射规则"""

    def test_simple_branch_name(self):
        """测试简单的分支名不变"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("main")
        assert result == "main"

    def test_slash_mapped_to_hyphen(self):
        """测试 / 映射到 - (feature/ui -> feature-ui)"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("feature/ui")
        assert result == "feature-ui"

    def test_nested_slash_mapped(self):
        """测试多个 / 映射 (bugfix/api/v2 -> bugfix-api-v2)"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("bugfix/api/v2")
        assert result == "bugfix-api-v2"

    def test_opening_paren_mapped_to_hyphen(self):
        """测试 ( 映射到 - (fix(#123) -> fix-123)"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("fix(#123)")
        assert result == "fix-123"

    def test_closing_paren_removed(self):
        """测试 ) 被移除"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("fix(issue)")
        assert result == "fix-issue"

    def test_hash_removed(self):
        """测试 # 被移除"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("feature/#123")
        assert result == "feature-123"

    def test_at_mapped_to_hyphen(self):
        """测试 @ 映射到 - (hotfix@v2 -> hotfix-v2)"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("hotfix@v2")
        assert result == "hotfix-v2"

    def test_complex_branch_name_mapping(self):
        """测试复杂分支名 (feature/fix(#123-ui) -> feature-fix-123-ui)"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("feature/fix(#123-ui)")
        assert result == "feature-fix-123-ui"

    def test_version_number_dots_converted(self):
        """测试版本号中的点被转换 (release/v1.0.0 -> release-v1-0-0)"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("release/v1.0.0")
        assert result == "release-v1-0-0"

    def test_consecutive_hyphens_collapsed(self):
        """测试连续的 - 被合并为单个 -"""
        mapper = BranchNameMapper()
        # 创建会产生连续 - 的输入
        result = mapper.map_branch_to_dir("fix//issue")
        assert result == "fix-issue"
        assert "--" not in result

    def test_leading_hyphen_removed(self):
        """测试首部的 - 被移除"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("/feature/ui")
        assert not result.startswith("-")
        assert result == "feature-ui"

    def test_trailing_hyphen_removed(self):
        """测试尾部的 - 被移除"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("feature/ui/")
        assert not result.endswith("-")
        assert result == "feature-ui"

    def test_colon_mapped_to_hyphen(self):
        """测试 : 映射到 -"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("release:v1:0:0")
        assert result == "release-v1-0-0"

    def test_square_brackets_mapped(self):
        """测试 [ 映射到 -，] 被移除"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("feat[WIP]")
        assert result == "feat-WIP"

    def test_space_mapped_to_hyphen(self):
        """测试空格映射到 -"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("my feature branch")
        assert result == "my-feature-branch"

    def test_underscore_preserved(self):
        """测试下划线被保留"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("feature_ui_update")
        assert result == "feature_ui_update"

    def test_alphanumeric_preserved(self):
        """测试字母和数字被保留"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("feature123branch456")
        assert result == "feature123branch456"


class TestBranchNameMapperCustomMapping:
    """测试自定义映射"""

    def test_custom_mapping_created_in_init(self):
        """测试在初始化时传入自定义映射"""
        custom = {
            "feature/fix(#123-ui)": "custom-dir-name",
            "release/v1.0.0": "release-1-0-0",
        }
        mapper = BranchNameMapper(custom_mappings=custom)

        assert mapper.map_branch_to_dir("feature/fix(#123-ui)") == "custom-dir-name"
        assert mapper.map_branch_to_dir("release/v1.0.0") == "release-1-0-0"

    def test_custom_mapping_overrides_default(self):
        """测试自定义映射覆盖默认规则"""
        mapper = BranchNameMapper()
        mapper.add_mapping("feature/ui", "special-name")

        result = mapper.map_branch_to_dir("feature/ui")
        assert result == "special-name"

    def test_add_mapping_single(self):
        """测试添加单个映射"""
        mapper = BranchNameMapper()
        mapper.add_mapping("hotfix/bug@v2", "hotfix-bug-v2")

        assert mapper.map_branch_to_dir("hotfix/bug@v2") == "hotfix-bug-v2"

    def test_add_mapping_multiple(self):
        """测试添加多个映射"""
        mapper = BranchNameMapper()
        mapper.add_mapping("feature/a", "feat-a")
        mapper.add_mapping("feature/b", "feat-b")

        assert mapper.map_branch_to_dir("feature/a") == "feat-a"
        assert mapper.map_branch_to_dir("feature/b") == "feat-b"

    def test_get_all_mappings(self):
        """测试获取所有映射"""
        custom = {
            "feature/ui": "feature-ui-custom",
            "release/v1.0.0": "release-1-0-0",
        }
        mapper = BranchNameMapper(custom_mappings=custom)

        mappings = mapper.get_all_mappings()
        assert len(mappings) == 2
        assert mappings["feature/ui"] == "feature-ui-custom"

    def test_get_all_mappings_is_copy(self):
        """测试 get_all_mappings 返回深拷贝"""
        mapper = BranchNameMapper()
        mapper.add_mapping("feature/ui", "feature-ui")

        mappings = mapper.get_all_mappings()
        mappings["feature/ui"] = "modified"

        # 原映射不应该被修改
        assert mapper.map_branch_to_dir("feature/ui") == "feature-ui"

    def test_is_mapped_returns_true_for_custom(self):
        """测试 is_mapped 对自定义映射返回 True"""
        mapper = BranchNameMapper()
        mapper.add_mapping("feature/ui", "feature-ui")

        assert mapper.is_mapped("feature/ui") is True

    def test_is_mapped_returns_false_for_unmapped(self):
        """测试 is_mapped 对未映射的分支返回 False"""
        mapper = BranchNameMapper()
        assert mapper.is_mapped("feature/ui") is False


class TestBranchNameMapperReverseMapping:
    """测试反向映射"""

    def test_reverse_mapping_from_custom(self):
        """测试从自定义映射反向查找"""
        mapper = BranchNameMapper()
        mapper.add_mapping("feature/ui", "feature-ui")

        result = mapper.map_dir_to_branch("feature-ui")
        assert result == "feature/ui"

    def test_reverse_mapping_returns_none_for_unmapped(self):
        """测试反向映射未来源于自定义映射时返回 None"""
        mapper = BranchNameMapper()
        # 这个是通过默认规则映射的，无法反向找到源
        result = mapper.map_dir_to_branch("feature-ui")
        assert result is None

    def test_reverse_mapping_multiple(self):
        """测试多个反向映射"""
        mapper = BranchNameMapper()
        mapper.add_mapping("feature/a", "feat-a")
        mapper.add_mapping("feature/b", "feat-b")

        assert mapper.map_dir_to_branch("feat-a") == "feature/a"
        assert mapper.map_dir_to_branch("feat-b") == "feature/b"

    def test_reverse_mapping_with_init_mappings(self):
        """测试使用初始化映射的反向查找"""
        custom = {
            "release/v1.0.0": "release-1-0-0",
        }
        mapper = BranchNameMapper(custom_mappings=custom)

        result = mapper.map_dir_to_branch("release-1-0-0")
        assert result == "release/v1.0.0"


class TestBranchNameMapperValidation:
    """测试映射验证"""

    def test_validate_mapping_no_errors_empty(self):
        """测试验证空映射无错误"""
        mapper = BranchNameMapper()
        errors = mapper.validate_mapping()
        assert len(errors) == 0

    def test_validate_mapping_no_errors_valid(self):
        """测试验证有效的映射无错误"""
        mapper = BranchNameMapper()
        mapper.add_mapping("feature/a", "feat-a")
        mapper.add_mapping("feature/b", "feat-b")

        errors = mapper.validate_mapping()
        assert len(errors) == 0

    def test_validate_mapping_detects_conflict(self):
        """测试验证检测两个分支映射到同一目录"""
        mapper = BranchNameMapper()
        mapper.add_mapping("feature/a", "same-dir")
        mapper.add_mapping("feature/b", "same-dir")

        errors = mapper.validate_mapping()
        assert len(errors) == 1
        assert errors[0].error_type == "conflict"
        assert "same-dir" in errors[0].message

    def test_validate_mapping_conflict_details(self):
        """测试冲突错误包含详细信息"""
        mapper = BranchNameMapper()
        mapper.add_mapping("feature/a", "same-dir")
        mapper.add_mapping("feature/b", "same-dir")

        errors = mapper.validate_mapping()
        assert len(errors) == 1
        assert "branches" in errors[0].details
        assert len(errors[0].details["branches"]) == 2

    def test_validate_mapping_detects_circular(self):
        """测试验证检测循环映射"""
        # 手动绕过 add_mapping 的验证，直接修改内部状态
        mapper = BranchNameMapper()
        mapper.custom_mappings["feature/a"] = "feature/b"
        mapper.custom_mappings["feature/b"] = "feature/c"

        errors = mapper.validate_mapping()
        assert len(errors) > 0
        assert any(e.error_type == "circular" for e in errors)

    def test_validate_mapping_invalid_char(self):
        """测试验证检测包含非法字符的目录名"""
        mapper = BranchNameMapper()
        # 直接修改内部状态以添加包含非法字符的映射
        mapper.custom_mappings["feature/a"] = "invalid/char"

        errors = mapper.validate_mapping()
        assert len(errors) == 1
        assert errors[0].error_type == "invalid_char"


class TestBranchNameMapperExceptions:
    """测试异常处理"""

    def test_empty_branch_name_raises_error(self):
        """测试空分支名抛出异常"""
        mapper = BranchNameMapper()
        with pytest.raises(InvalidMappingError):
            mapper.map_branch_to_dir("")

    def test_empty_branch_name_on_add_mapping(self):
        """测试添加空分支名映射抛出异常"""
        mapper = BranchNameMapper()
        with pytest.raises(InvalidMappingError):
            mapper.add_mapping("", "dir-name")

    def test_empty_dir_name_on_add_mapping(self):
        """测试添加空目录名映射抛出异常"""
        mapper = BranchNameMapper()
        with pytest.raises(InvalidMappingError):
            mapper.add_mapping("branch-name", "")

    def test_invalid_dir_name_with_slash(self):
        """测试包含 / 的目录名被拒绝"""
        mapper = BranchNameMapper()
        with pytest.raises(InvalidMappingError):
            mapper.add_mapping("feature/a", "invalid/dir")

    def test_invalid_dir_name_with_special_chars(self):
        """测试包含特殊字符的目录名被拒绝"""
        mapper = BranchNameMapper()
        with pytest.raises(InvalidMappingError):
            mapper.add_mapping("feature/a", "invalid@dir")

    def test_invalid_dir_name_with_dot_prefix(self):
        """测试以 . 开头的目录名被拒绝（隐藏目录）"""
        mapper = BranchNameMapper()
        with pytest.raises(InvalidMappingError):
            mapper.add_mapping("feature/a", ".hidden")

    def test_invalid_dir_name_dot_only(self):
        """测试 . 和 .. 目录名被拒绝"""
        mapper = BranchNameMapper()
        with pytest.raises(InvalidMappingError):
            mapper.add_mapping("feature/a", ".")
        with pytest.raises(InvalidMappingError):
            mapper.add_mapping("feature/b", "..")


class TestBranchNameMapperEdgeCases:
    """测试边界情况"""

    def test_very_long_branch_name(self):
        """测试很长的分支名"""
        mapper = BranchNameMapper()
        long_name = "feature/" + "a" * 100 + "/" + "b" * 100
        result = mapper.map_branch_to_dir(long_name)
        assert len(result) > 0
        assert result.isalnum() or all(c in "-_" for c in result if not c.isalnum())

    def test_only_special_chars(self):
        """测试只包含特殊字符的分支名"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("///")
        # 应该被去掉首尾 - 后变成空或很短
        assert result == "" or len(result) <= 1

    def test_only_dots(self):
        """测试只包含点号的分支名"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("...")
        # 点会被映射为 -，然后合并并去掉首尾
        assert result == "" or len(result) <= 1

    def test_unicode_characters(self):
        """测试 Unicode 字符被转换为 -，然后去掉尾部 -"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("feature/功能")
        # 非 ASCII 字符应该被转换为 -，然后尾部的 - 被去掉
        assert result == "feature"

    def test_single_character_branch(self):
        """测试单个字符的分支名"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("a")
        assert result == "a"

    def test_single_special_char_branch(self):
        """测试单个特殊字符的分支名"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("/")
        # / 被映射为 -，然后去掉首尾
        assert result == ""

    def test_case_preserved(self):
        """测试大小写被保留"""
        mapper = BranchNameMapper()
        result = mapper.map_branch_to_dir("Feature/MyBranch")
        assert "Feature" in result
        assert "MyBranch" in result


class TestBranchNameMapperConfigIntegration:
    """测试与配置的集成"""

    def test_load_from_config(self):
        """测试从配置加载映射"""
        mapper = BranchNameMapper()
        config_mappings = {
            "feature/ui": "feature-ui-custom",
            "release/v1.0.0": "release-1-0-0",
        }

        mapper.load_from_config(config_mappings)

        assert mapper.map_branch_to_dir("feature/ui") == "feature-ui-custom"
        assert mapper.map_branch_to_dir("release/v1.0.0") == "release-1-0-0"

    def test_load_from_config_empty_dict(self):
        """测试从空配置加载"""
        mapper = BranchNameMapper()
        mapper.load_from_config({})

        # 应该不出错，映射为空
        assert len(mapper.get_all_mappings()) == 0

    def test_load_from_config_invalid_type(self):
        """测试从非字典配置加载抛出异常"""
        mapper = BranchNameMapper()
        with pytest.raises(InvalidMappingError):
            mapper.load_from_config("not a dict")

    def test_load_from_config_invalid_mapping_in_dict(self):
        """测试从包含无效映射的配置加载"""
        mapper = BranchNameMapper()
        config_mappings = {
            "feature/a": "invalid/dir",  # 包含 /
        }

        with pytest.raises(InvalidMappingError):
            mapper.load_from_config(config_mappings)


class TestValidationError:
    """测试 ValidationError 类"""

    def test_validation_error_creation(self):
        """测试创建验证错误"""
        error = ValidationError("conflict", "Test message", {"key": "value"})

        assert error.error_type == "conflict"
        assert error.message == "Test message"
        assert error.details == {"key": "value"}

    def test_validation_error_str(self):
        """测试验证错误的字符串表示"""
        error = ValidationError("conflict", "Test message")
        assert str(error) == "conflict: Test message"

    def test_validation_error_repr(self):
        """测试验证错误的 repr"""
        error = ValidationError("conflict", "Test message", {"key": "value"})
        repr_str = repr(error)
        assert "ValidationError" in repr_str
        assert "conflict" in repr_str


class TestBranchNameMapperIntegration:
    """集成测试"""

    def test_full_workflow_with_custom_and_default(self):
        """测试包含自定义和默认映射的完整流程"""
        custom = {
            "feature/special(#123)": "feature-special-123",
        }
        mapper = BranchNameMapper(custom_mappings=custom)

        # 自定义映射
        assert mapper.map_branch_to_dir("feature/special(#123)") == "feature-special-123"

        # 默认映射
        assert mapper.map_branch_to_dir("feature/other") == "feature-other"

        # 验证
        assert mapper.validate_mapping() == []

    def test_migration_scenario(self):
        """测试迁移场景：从默认规则到自定义映射"""
        mapper = BranchNameMapper()

        # 首先使用默认规则
        branch = "feature/fix(#123-ui)"
        default_result = mapper.map_branch_to_dir(branch)
        assert default_result == "feature-fix-123-ui"

        # 添加自定义映射
        mapper.add_mapping(branch, "custom-feature-name")

        # 现在使用自定义映射
        custom_result = mapper.map_branch_to_dir(branch)
        assert custom_result == "custom-feature-name"

    def test_batch_mapping_and_validation(self):
        """测试批量映射和验证"""
        branches = [
            "feature/a",
            "feature/b",
            "bugfix/critical",
            "hotfix@v1",
            "release/v1.0.0",
        ]

        mapper = BranchNameMapper()

        for branch in branches:
            result = mapper.map_branch_to_dir(branch)
            assert len(result) > 0
            assert "-" not in result or not result.startswith("-")
            assert "-" not in result or not result.endswith("-")

        errors = mapper.validate_mapping()
        assert len(errors) == 0
