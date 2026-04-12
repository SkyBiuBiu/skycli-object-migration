"""
版本一致性验证脚本
确保项目中所有版本引用保持一致
使用方法:
    python scripts/check_version.py          # 检查版本一致性
    python scripts/check_version.py --fix    # 自动修复 README.md 版本
"""
import os
import re
import argparse
from pathlib import Path
from datetime import datetime


def check_version_consistency(auto_fix=False):
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
    
    # 检查 pyproject.toml
    pyproject_file = project_root / "pyproject.toml"
    if pyproject_file.exists():
        with open(pyproject_file, "r", encoding="utf-8") as f:
            content = f.read()
            if 'dynamic = ["version"]' in content and 's3_manager._version.__version__' in content:
                print(f"✅ pyproject.toml: 使用动态版本声明从 _version.py 读取")
            else:
                print(f"⚠️  pyproject.toml: 未正确配置动态版本")
    
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
    readme_version_ok = True
    with open(readme_file, "r", encoding="utf-8") as f:
        content = f.read()
        matches = re.findall(r'### v(\d+\.\d+\.\d+)', content)
        if matches:
            latest_readme_version = matches[0]
            if latest_readme_version == master_version:
                print(f"✅ README.md: 最新版本号一致 ({latest_readme_version})")
            else:
                print(f"⚠️  README.md: 最新版本号 ({latest_readme_version}) 与主版本 ({master_version}) 不一致")
                if auto_fix:
                    print(f"🔧 正在自动更新 README.md...")
                    if add_changelog_entry(readme_file, master_version):
                        print(f"✅ 已更新 README.md Changelog")
                        readme_version_ok = True
                    else:
                        print(f"❌ 更新 README.md 失败")
                        readme_version_ok = False
                else:
                    print(f"   建议：运行 python scripts/check_version.py --fix 自动更新")
                    print(f"   或运行 python scripts/update_version.py {master_version}")
                readme_version_ok = False
    
    print("-" * 50)
    if readme_version_ok:
        print(f"✅ 版本一致性检查通过！当前版本：{master_version}")
    else:
        print(f"⚠️  版本一致性检查发现问题，请检查上述输出")
    return readme_version_ok


def add_changelog_entry(readme_file: Path, version: str) -> bool:
    """在 README.md 中添加新的 Changelog 条目"""
    with open(readme_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 检查是否已存在该版本，如果存在则不需要添加
    pattern = f'### v{re.escape(version)}'
    if re.search(pattern, content):
        return True
    
    # 查找 Changelog 部分（支持中英文）
    changelog_match = re.search(r'(##\s*(?:更新日志|Changelog)[^\n]*\n)', content)
    if not changelog_match:
        return False
    
    # 生成新版本记录
    today = datetime.now().strftime("%Y-%m-%d")
    new_version_entry = f"""
### v{version} ({today})
- 新版本发布

"""
    
    # 在 Changelog 标题后插入新版本记录
    insert_pos = changelog_match.end()
    new_content = content[:insert_pos] + new_version_entry + content[insert_pos:]
    
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    return True


def main():
    parser = argparse.ArgumentParser(description="版本一致性验证工具")
    parser.add_argument("--fix", action="store_true", help="自动修复 README.md 版本不一致问题")
    args = parser.parse_args()
    
    success = check_version_consistency(auto_fix=args.fix)
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
