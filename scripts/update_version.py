"""
版本更新脚本
更新 _version.py 并自动更新 README.md 的 Changelog
使用方法：python scripts/update_version.py <新版本号>
例如：python scripts/update_version.py 0.4.0
"""
import re
import sys
from pathlib import Path
from datetime import datetime


def update_version_file(version: str, project_root: Path) -> bool:
    """更新 _version.py 文件中的版本号"""
    version_file = project_root / "s3_manager" / "_version.py"
    
    with open(version_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 替换版本号
    new_content = re.sub(
        r'^__version__ = ["\'][^"\']+["\']',
        f'__version__ = "{version}"',
        content,
        flags=re.MULTILINE
    )
    
    if new_content == content:
        print(f"⚠️  _version.py 版本号已经是 {version}")
        return True
    
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"✅ 已更新 _version.py 版本号为: {version}")
    return True


def update_readme_changelog(version: str, project_root: Path) -> bool:
    """更新 README.md 的 Changelog，添加新版本记录"""
    readme_file = project_root / "README.md"
    
    with open(readme_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 检查是否已存在该版本
    pattern = f'### v{re.escape(version)}'
    if re.search(pattern, content):
        print(f"⚠️  README.md 中已存在 v{version} 版本记录")
        return True
    
    # 查找 Changelog 部分（支持中英文）
    changelog_match = re.search(r'(##\s*(?:更新日志|Changelog)[^\n]*\n)', content)
    if not changelog_match:
        print(f"❌ 未在 README.md 中找到 Changelog 部分")
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
    
    print(f"✅ 已在 README.md 中添加 v{version} 版本记录")
    return True


def verify_update(version: str, project_root: Path) -> bool:
    """验证更新是否成功"""
    # 验证 _version.py
    version_file = project_root / "s3_manager" / "_version.py"
    
    with open(version_file, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'^__version__ = ["\']([^"\']+)["\']', content, re.MULTILINE)
        if not match or match.group(1) != version:
            return False
    
    # 验证 pyproject.toml 配置
    pyproject_file = project_root / "pyproject.toml"
    if pyproject_file.exists():
        with open(pyproject_file, "r", encoding="utf-8") as f:
            content = f.read()
            # 确保 pyproject.toml 使用动态版本声明
            if 'dynamic = ["version"]' not in content:
                print("⚠️  pyproject.toml 未使用动态版本声明")
                return False
            if 'version = {attr = "s3_manager._version.__version__"}' not in content:
                print("⚠️  pyproject.toml 版本读取配置不正确")
                return False
    
    return True


def main():
    if len(sys.argv) != 2:
        print("使用方法：python scripts/update_version.py <新版本号>")
        print("例如：python scripts/update_version.py 0.4.0")
        sys.exit(1)
    
    new_version = sys.argv[1]
    
    # 验证版本号格式
    if not re.match(r'^\d+\.\d+\.\d+$', new_version):
        print(f"❌ 无效的版本号格式：{new_version}")
        print("版本号格式应为：X.Y.Z (例如：0.4.0)")
        sys.exit(1)
    
    project_root = Path(__file__).parent.parent
    
    print(f"准备更新版本到：{new_version}")
    print("-" * 50)
    
    # 更新 _version.py
    if not update_version_file(new_version, project_root):
        print("❌ 更新 _version.py 失败")
        sys.exit(1)
    
    # 更新 README.md
    if not update_readme_changelog(new_version, project_root):
        print("⚠️  更新 README.md 失败，但 _version.py 已更新")
    
    # 验证更新
    if not verify_update(new_version, project_root):
        print("❌ 验证失败，版本号更新可能未成功")
        sys.exit(1)
    
    print("-" * 50)
    print(f"✅ 版本更新成功！当前版本：{new_version}")
    print("\n版本管理说明:")
    print("  - pyproject.toml: 使用动态版本声明，从 _version.py 读取")
    print("  - setup.py: 通过 get_version() 从 _version.py 读取")
    print("  - 包内代码: 从 _version.py 导入 __version__")
    print("\n下一步:")
    print("1. 检查 README.md 的 Changelog 是否需要补充更新内容")
    print("2. 提交更改: git add s3_manager/_version.py README.md pyproject.toml")
    print("3. 提交并打标签：git commit -m 'Release v{new_version}'")
    print(f"4. 创建 Git 标签：git tag v{new_version}")


if __name__ == "__main__":
    main()
