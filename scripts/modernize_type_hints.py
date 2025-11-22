#!/usr/bin/env python3
"""
代码现代化脚本 - Python 3.12+ 类型注解

自动将旧风格的类型注解升级到 Python 3.12+ 风格:
- Optional[T] → T | None
- Dict[K, V] → dict[K, V]
- List[T] → list[T]
- Tuple[T, ...] → tuple[T, ...]
- Set[T] → set[T]

使用方式:
    python scripts/modernize_type_hints.py <file_path>
    python scripts/modernize_type_hints.py src/cherryquant/ai/decision_engine/futures_engine.py
"""

import re
import sys
from pathlib import Path


def modernize_file(file_path: Path) -> tuple[bool, str]:
    """现代化单个文件的类型注解"""

    if not file_path.exists():
        return False, f"文件不存在: {file_path}"

    # 读取文件
    content = file_path.read_text(encoding="utf-8")
    original = content

    # 1. 替换 Optional[T] → T | None
    # 处理嵌套情况，如 Optional[Dict[str, Any]]
    def replace_optional(match):
        inner = match.group(1)
        return f"{inner} | None"

    content = re.sub(r"Optional\[([^\]]+(?:\[[^\]]+\])?)\]", replace_optional, content)

    # 2. 替换 Dict → dict
    content = re.sub(r"\bDict\[", "dict[", content)

    # 3. 替换 List → list
    content = re.sub(r"\bList\[", "list[", content)

    # 4. 替换 Tuple → tuple
    content = re.sub(r"\bTuple\[", "tuple[", content)

    # 5. 替换 Set → set
    content = re.sub(r"\bSet\[", "set[", content)

    # 6. 更新 import 语句
    # 如果不再使用任何旧类型，移除导入
    lines = content.split("\n")
    new_lines = []

    for line in lines:
        # 检查是否是 typing 导入行
        if line.strip().startswith("from typing import"):
            # 移除已经替换的类型
            imports = line.split("import")[1].strip()
            import_list = [
                item.strip() for item in imports.split(",") if item.strip()
            ]

            # 过滤掉已替换的类型
            filtered = [
                item
                for item in import_list
                if item not in ["Optional", "Dict", "List", "Tuple", "Set"]
            ]

            if filtered:
                # 还有其他导入，保留这行
                new_line = f"from typing import {', '.join(filtered)}"
                new_lines.append(new_line)
            elif not line.strip().endswith("\\"):
                # 没有其他导入且不是续行，跳过这行
                continue
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    content = "\n".join(new_lines)

    # 检查是否有变化
    if content == original:
        return False, "无需修改"

    # 写回文件
    file_path.write_text(content, encoding="utf-8")

    # 统计修改
    changes = []
    if "| None" in content and "| None" not in original:
        changes.append("Optional→|None")
    if "dict[" in content and "dict[" not in original:
        changes.append("Dict→dict")
    if "list[" in content and "list[" not in original:
        changes.append("List→list")

    return True, f"✅ 升级成功: {', '.join(changes)}"


def main():
    if len(sys.argv) < 2:
        print("使用方式: python scripts/modernize_type_hints.py <file_path>")
        print("\n示例:")
        print("  python scripts/modernize_type_hints.py src/cherryquant/ai/decision_engine/futures_engine.py")
        sys.exit(1)

    file_path = Path(sys.argv[1])

    print(f"🔧 现代化类型注解: {file_path}")

    success, message = modernize_file(file_path)

    if success:
        print(f"  {message}")
    else:
        print(f"  ⚠️  {message}")


if __name__ == "__main__":
    main()
