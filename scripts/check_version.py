"""
版本一致性验证脚本
确保项目中所有版本引用保持一致
"""
import os
import re
from pathlib import Path


def check_version_consistency():
    """检查项目中所有版本引用是否一致"""
    project_root = Path(__file__).parent.parent
    
    # 读取主版本文件
    version_file = project_root / "s3_manager" / "_version.py"
    with open(version_file, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'^__version__ = ["\']([^"\']+)["\']', content, re.MULTILINE)
        if not match:
            print("❌ 无法从 _version.py 读取版本号")
            return False
        master_version = match.group(1)
    
    print(f"主版本号 (_version.py): {master_version}")
    print("-" * 50)
    
    # 检查 setup.py
    setup_file = project_root / "setup.py"
    with open(setup_file, "r", encoding="utf-8") as f:
        content = f.read()
        if "get_version()" in content:
            print(f"✅ setup.py: 使用 get_version() 从 _version.py 读取")
        else:
            print(f"❌ setup.py: 未使用 get_version()")
            return False
    
    # 检查 skycli.py
    skycli_file = project_root / "s3_manager" / "skycli.py"
    with open(skycli_file, "r", encoding="utf-8") as f:
        content = f.read()
        if "from ._version import __version__" in content:
            print(f"✅ skycli.py: 从 _version.py 导入 __version__")
        else:
            print(f"❌ skycli.py: 未正确导入 __version__")
            return False
    
    # 检查 README.md 中的最新版本号
    readme_file = project_root / "README.md"
    with open(readme_file, "r", encoding="utf-8") as f:
        content = f.read()
        matches = re.findall(r'### v(\d+\.\d+\.\d+)', content)
        if matches:
            latest_readme_version = matches[0]
            if latest_readme_version == master_version:
                print(f"✅ README.md: 最新版本号一致 ({latest_readme_version})")
            else:
                print(f"⚠️  README.md: 最新版本号 ({latest_readme_version}) 与主版本 ({master_version}) 不一致")
                print(f"   建议：更新 README.md 的 Changelog")
    
    print("-" * 50)
    print(f"✅ 版本一致性检查通过！当前版本：{master_version}")
    return True


if __name__ == "__main__":
    success = check_version_consistency()
    exit(0 if success else 1)
