"""配置验证器使用示例

演示如何使用 ConfigValidator 进行配置验证。
"""

from pathlib import Path
from gm.core.config_validator import ConfigValidator, ErrorSeverity


def example_valid_config():
    """示例：验证有效配置"""
    print("=" * 60)
    print("示例 1: 验证有效配置")
    print("=" * 60)

    config = {
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
        "branch_mapping": {
            "feature/fix(#123)": "feature-fix-123",
        },
    }

    validator = ConfigValidator()
    result = validator.validate_config(config)

    print(f"验证是否通过: {result.is_valid}")
    print(f"错误数量: {result.get_error_count()}")
    print(f"警告数量: {result.get_warning_count()}")
    print()


def example_invalid_config():
    """示例：验证无效配置"""
    print("=" * 60)
    print("示例 2: 验证无效配置")
    print("=" * 60)

    config = {
        "worktree": {
            "base_path": "",  # 空字符串
            "naming_pattern": "static-name",  # 缺少 {branch}
            "auto_cleanup": "true",  # 应该是布尔值
        },
        "display": {
            "colors": 123,  # 应该是布尔值
        },
    }

    validator = ConfigValidator()
    result = validator.validate_config(config)

    print(f"验证是否通过: {result.is_valid}")
    print(f"错误数量: {result.get_error_count()}")
    print(f"警告数量: {result.get_warning_count()}")

    print("\n错误列表:")
    for error in result.errors:
        print(f"  - {error}")

    print("\n警告列表:")
    for warning in result.warnings:
        print(f"  - {warning}")

    print("\n修复建议:")
    suggestions = validator.suggest_fixes()
    for suggestion in suggestions:
        print(f"  - {suggestion}")
    print()


def example_section_validation():
    """示例：验证特定配置段"""
    print("=" * 60)
    print("示例 3: 验证特定配置段")
    print("=" * 60)

    # 验证 worktree 配置
    worktree_config = {
        "base_path": ".gm",
        "naming_pattern": "{branch}",
    }

    validator = ConfigValidator()
    result = validator.validate_section("worktree", worktree_config)

    print("验证 worktree 配置:")
    print(f"  是否有效: {result.is_valid}")
    print(f"  错误数: {result.get_error_count()}")

    # 验证 branch_mapping 配置
    branch_mapping = {
        "feature/fix(#123)": "feature-fix-123",
        "hotfix/bug@v2": "hotfix-bug-v2",
    }

    result = validator.validate_section("branch_mapping", branch_mapping)

    print("\n验证 branch_mapping 配置:")
    print(f"  是否有效: {result.is_valid}")
    print(f"  错误数: {result.get_error_count()}")
    print()


def example_strict_mode():
    """示例：严格模式验证"""
    print("=" * 60)
    print("示例 4: 严格模式验证")
    print("=" * 60)

    config = {
        "worktree": {
            "base_path": ".gm",
            "naming_pattern": "{branch}",
        },
        "display": {},
        "shared_files": [],  # 空列表会产生警告
    }

    # 非严格模式
    validator_normal = ConfigValidator(strict=False)
    result_normal = validator_normal.validate_config(config)

    print("非严格模式:")
    print(f"  是否有效: {result_normal.is_valid}")
    print(f"  警告数: {len(result_normal.warnings)}")

    # 严格模式
    validator_strict = ConfigValidator(strict=True)
    result_strict = validator_strict.validate_config(config)

    print("\n严格模式:")
    print(f"  是否有效: {result_strict.is_valid}")
    print(f"  警告转换为错误数: {result_strict.get_warning_count()}")
    print()


def example_symlink_strategies():
    """示例：符号链接策略验证"""
    print("=" * 60)
    print("示例 5: 符号链接策略验证")
    print("=" * 60)

    strategies = ["auto", "symlink", "junction", "hardlink", "invalid"]

    validator = ConfigValidator()

    for strategy in strategies:
        result = validator.validate_symlink_strategy(strategy)
        status = "[OK]" if result.is_valid else "[FAIL]"
        print(f"  {status} {strategy}")
    print()


if __name__ == "__main__":
    example_valid_config()
    example_invalid_config()
    example_section_validation()
    example_strict_mode()
    example_symlink_strategies()

    print("=" * 60)
    print("所有示例完成！")
    print("=" * 60)
