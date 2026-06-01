#!/usr/bin/env python3
"""AST 批量分析工具 - 同时分析多个测试文件"""

import subprocess
import sys
from pathlib import Path

# 要分析的文件列表
FILES_TO_ANALYZE = [
    "TestCases/Perform/Redfish/Redfish_performance.py",
    "TestCases/Perform/Snmp/Snmp_performance.py",
    "TestCases/Perform/Start/Start_performance.py",
]

def main():
    script_path = Path(__file__).parent / "ast_demo.py"

    for i, file_path in enumerate(FILES_TO_ANALYZE, 1):
        print(f"\n{'=' * 70}")
        print(f"[{i}/{len(FILES_TO_ANALYZE)}] 正在分析: {file_path}")
        print('=' * 70)

        # 使用环境变量临时覆盖 MAIN_FILE
        env = {"MAIN_FILE": file_path}
        result = subprocess.run(
            [sys.executable, str(script_path)],
            env={**subprocess.os.environ, **env},
            capture_output=False
        )

        if result.returncode != 0:
            print(f"✗ 分析失败: {file_path}")

    print(f"\n{'=' * 70}")
    print("✓ 批量分析完成！")
    print('=' * 70)

if __name__ == "__main__":
    main()