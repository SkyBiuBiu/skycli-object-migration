"""
Tests for version management module
"""
import pytest
from s3_manager._version import __version__, get_version, get_version_info


class TestVersion:
    """测试版本管理模块"""

    def test_version_format(self):
        """测试版本号格式"""
        assert __version__ is not None
        assert isinstance(__version__, str)
        
        # 版本号应该是 X.Y.Z 格式
        parts = __version__.split('.')
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_get_version(self):
        """测试 get_version 函数"""
        version = get_version()
        assert version == __version__
        assert isinstance(version, str)

    def test_get_version_info(self):
        """测试 get_version_info 函数"""
        info = get_version_info()
        
        # 应该返回一个字典
        assert isinstance(info, dict)
        
        # 应该包含必要的键
        assert "major" in info
        assert "minor" in info
        assert "patch" in info
        
        # 版本号应该是整数
        assert isinstance(info["major"], int)
        assert isinstance(info["minor"], int)
        assert isinstance(info["patch"], int)
        
        # 版本号应该与 __version__ 匹配
        parts = __version__.split('.')
        assert info["major"] == int(parts[0])
        assert info["minor"] == int(parts[1])
        assert info["patch"] == int(parts[2])

    def test_version_components(self):
        """测试版本号各组件"""
        info = get_version_info()
        
        # 主版本号、次版本号、补丁号都应该是非负整数
        assert info["major"] >= 0
        assert info["minor"] >= 0
        assert info["patch"] >= 0

    def test_version_info_release_flag(self):
        """测试版本信息中的 release 标志"""
        info = get_version_info()
        
        # 应该有 release 标志
        assert "release" in info
        assert isinstance(info["release"], bool)
