#!/usr/bin/env python3
"""
SNK_SIT 未使用代码清理工具
基于 dependencies.json 分析并清理未被导入的Python文件和目录
"""

import json
import sys
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional

ARCHIVE_DIR = ".unused_archive"



def get_python_files(root_dir: Path) -> List[Path]:
    """获取目录下所有Python文件"""
    py_files = []
    for path in root_dir.rglob("*.py"):
        if "__pycache__" not in str(path):
            py_files.append(path)
    return sorted(py_files)


def load_dependencies_json(root_dir: Path) -> Optional[Dict]:
    """加载 dependencies.json"""
    dep_file = root_dir.parent / "dependencies.json"
    if dep_file.exists():
        try:
            with open(dep_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return None


def get_module_name(file_path: Path, root_dir: Path) -> str:
    """获取文件的模块名"""
    rel_path = file_path.relative_to(root_dir)
    parts = list(rel_path.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].replace(".py", "")
    return ".".join(parts) if parts else ""


def find_unused_from_deps_json(root_dir: Path, deps: Dict) -> List[Tuple[Path, str]]:
    """基于 dependencies.json 找出未使用的 SNK_SIT 模块"""
    # 收集所有已使用的模块 (支持多种格式: SNK_SIT.xxx 或 SNK_SIT.xxx.yyy)
    used_modules = set()
    for key in deps.keys():
        if key.startswith("SNK_SIT."):
            # 标准化: 去掉前缀 SNK_SIT. 或 SNK_SIT/
            mod = key.replace("SNK_SIT.", "").replace("SNK_SIT/", "").replace("/", ".")
            used_modules.add(mod)
            # 也添加带目录前缀的形式
            used_modules.add(f"SNK_SIT.{mod}")

    # 获取所有实际存在的文件
    py_files = get_python_files(root_dir)
    all_modules = {}
    for f in py_files:
        mod_name = get_module_name(f, root_dir)
        if mod_name:
            all_modules[mod_name] = f
            all_modules[f"SNK_SIT.{mod_name}"] = f

    # 找出未使用的
    unused = []
    for mod_name, file_path in all_modules.items():
        # 跳过测试文件
        if "test" in mod_name.lower() or "tests" in mod_name.lower():
            continue
        # 跳过第三方库
        if any(p in mod_name.lower() for p in ["requests_toolbelt", "gitlab"]):
            continue

        # 检查是否在依赖图中
        if mod_name not in used_modules:
            # 避免重复
            actual_mod = mod_name.replace("SNK_SIT.", "")
            already_added = any(u[1] == actual_mod for u in unused)
            if not already_added:
                unused.append((file_path, actual_mod))

    return sorted(unused, key=lambda x: x[1])


def archive_files(files: List[Path], root_dir: Path, dry_run: bool = True):
    """将文件归档到unused_archive目录"""
    archive_root = root_dir / ARCHIVE_DIR
    operations = []

    for file_path in files:
        rel_path = file_path.relative_to(root_dir)
        dest = archive_root / rel_path
        operations.append({
            "src": file_path,
            "dst": dest,
        })

    if dry_run:
        print(f"\n{'=' * 60}")
        print(f"[DRY RUN] 将归档 {len(operations)} 个文件:")
        for op in operations[:20]:
            print(f"  -> {op['src'].relative_to(root_dir)}")
        if len(operations) > 20:
            print(f"  ... 还有 {len(operations) - 20} 个文件")
    else:
        print(f"\n{'=' * 60}")
        print(f"归档 {len(operations)} 个文件到 {ARCHIVE_DIR}/")
        archive_root.mkdir(exist_ok=True)

        for op in operations:
            dest = op["dst"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(op["src"]), str(dest))
            print(f"  moved: {op['src'].relative_to(root_dir)}")

    return operations


def delete_files(files: List[Path], dry_run: bool = True):
    """删除文件"""
    operations = []

    for file_path in files:
        operations.append({"file": file_path})

    if dry_run:
        print(f"\n{'=' * 60}")
        print(f"[DRY RUN] 将删除 {len(operations)} 个文件:")
        for op in operations[:20]:
            print(f"  -> {op['file']}")
        if len(operations) > 20:
            print(f"  ... 还有 {len(operations) - 20} 个文件")
    else:
        print(f"\n{'=' * 60}")
        print(f"删除 {len(operations)} 个文件:")
        for op in operations:
            op["file"].unlink()
            print(f"  deleted: {op['file']}")

    return operations


def main():
    parser = argparse.ArgumentParser(
        description="SNK_SIT 未使用代码清理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 分析并显示未使用的文件(预览模式)
  python cleanup_unused.py

  # 预览归档操作
  python cleanup_unused.py --archive --dry-run

  # 执行归档操作
  python cleanup_unused.py --archive

  # 直接删除文件(危险!)
  python cleanup_unused.py --delete --dry-run
  python cleanup_unused.py --delete
        """
    )
    parser.add_argument("--archive", action="store_true", help="归档未使用的文件到 .unused_archive 目录")
    parser.add_argument("--delete", action="store_true", help="直接删除未使用的文件(危险)")
    parser.add_argument("--dry-run", action="store_true", default=None,
                        help="预览模式,不执行实际操作")
    parser.add_argument("--no-dry-run", action="store_true",
                        help="执行实际操作(与 --dry-run 互斥)")
    parser.add_argument("--deps", type=str, default=None,
                        help="指定 dependencies.json 路径")

    args = parser.parse_args()

    # 确定根目录
    script_dir = Path(__file__).parent
    root_dir = script_dir / "SNK_SIT"

    if not root_dir.exists():
        print(f"错误: 目录不存在 {root_dir}")
        sys.exit(1)

    # 确定执行模式
    if args.no_dry_run:
        dry_run = False
    elif args.dry_run:
        dry_run = True
    else:
        dry_run = True

    # 加载依赖
    if args.deps:
        deps = json.load(open(args.deps))
    else:
        deps = load_dependencies_json(root_dir)

    if not deps:
        print("错误: 无法加载 dependencies.json")
        print("请先运行依赖分析工具生成 dependencies.json")
        sys.exit(1)

    print(f"{'=' * 60}")
    print(f"SNK_SIT 未使用代码清理工具")
    print(f"{'=' * 60}")
    print(f"目录: {root_dir}")
    print(f"模式: {'预览' if dry_run else '执行'}")
    print(f"依赖文件: dependencies.json (共 {len(deps)} 个模块)")

    # 分析未使用的模块
    print(f"\n{'=' * 60}")
    print("分析未使用的模块...")
    unused = find_unused_from_deps_json(root_dir, deps)

    if not unused:
        print("\n未发现未使用的文件!")
        return

    print(f"\n发现 {len(unused)} 个未使用的文件/模块:\n")

    for i, (file_path, module_name) in enumerate(unused, 1):
        rel_path = file_path.relative_to(root_dir)
        print(f"{i:3d}. {rel_path}")

    # 执行操作
    if args.archive:
        files = [f for f, _ in unused]
        archive_files(files, root_dir, dry_run)
    elif args.delete:
        files = [f for f, _ in unused]
        delete_files(files, dry_run)
    else:
        print(f"\n{'=' * 60}")
        print("使用 --archive 或 --delete 执行操作")
        print("使用 --no-dry-run 确认执行")


if __name__ == "__main__":
    main()