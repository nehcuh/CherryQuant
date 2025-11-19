#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refactor_imports.py

用途：
  - 批量把旧导入路径迁移为新包路径（用于外部仓库/工程的适配）。
  - 旧 → 新 规则：
      * ai.*       → cherryquant.ai.*
      * adapters.* → cherryquant.adapters.*
      * services.* → cherryquant.services.*
      * web.*      → cherryquant.web.*

使用示例：
  # 仅查看将要修改的文件（dry-run，默认行为）
  uv run python scripts/refactor_imports.py /path/to/your/repo

  # 实际写回修改（apply）
  uv run python scripts/refactor_imports.py /path/to/your/repo --apply

  # 显示 diff（dry-run 下也会显示）
  uv run python scripts/refactor_imports.py /path/to/your/repo --show-diff

  # 更详细输出（包括每个文件的行级变更条目）
  uv run python scripts/refactor_imports.py /path/to/your/repo --verbose

选项说明：
  - --apply        实际写回文件（默认仅预览）
  - --ext          逗号分隔的文件扩展名，默认：.py
  - --exclude-dir  额外排除的目录名（可多次指定）
  - --show-diff    输出 unified diff
  - --verbose      输出详细变更信息

注意：
  - 脚本会跳过常见缓存与虚拟环境目录：.git、.venv、venv、__pycache__、node_modules、dist、build、
    .ruff_cache、.pytest_cache、.mypy_cache 等。
  - 仅对 import/from import 语句做前缀替换，尽量避免误伤其他代码。
  - 多个导入项共享一行时（如 import ai, adapters as ad），会逐项替换。
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

# 旧 → 新 前缀映射
PREFIX_MAP: Dict[str, str] = {
    "ai": "cherryquant.ai",
    "adapters": "cherryquant.adapters",
    "services": "cherryquant.services",
    "web": "cherryquant.web",
}

# 默认排除目录
DEFAULT_SKIP_DIRS: Set[str] = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
}


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量迁移导入路径：ai/、adapters/、services/、web/ → cherryquant.*",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "root",
        type=str,
        help="要处理的工程根目录（递归扫描）",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际写回修改（默认 dry-run，仅查看变更）",
    )
    parser.add_argument(
        "--ext",
        type=str,
        default=".py",
        help="逗号分隔的文件扩展名列表（例如：.py,.pyi）",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="额外要排除的目录名（可多次指定）",
    )
    parser.add_argument(
        "--show-diff",
        action="store_true",
        help="输出 unified diff（便于审阅变更）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出详细变更（逐文件逐行）",
    )
    return parser.parse_args(list(argv))


def should_skip_dir(path: Path, extra_skips: Set[str]) -> bool:
    name = path.name
    return name in DEFAULT_SKIP_DIRS or name in extra_skips


def scan_files(root: Path, exts: Set[str], extra_skips: Set[str]) -> List[Path]:
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_dir():
            if should_skip_dir(p, extra_skips):
                # 跳过整个目录
                # 使用 rglob 无法中途剪枝，这里仅在文件层面过滤
                continue
            else:
                continue
        if p.suffix in exts:
            # 再次检查路径中是否包含要跳过的目录
            if any(part in DEFAULT_SKIP_DIRS or part in extra_skips for part in p.parts):
                continue
            files.append(p)
    return files


def transform_import_token(token: str) -> str:
    """
    将单个 import token 替换前缀，例如：
      - ai                    -> cherryquant.ai
      - ai as A               -> cherryquant.ai as A
      - ai.decision_engine    -> cherryquant.ai.decision_engine
      - adapters.data_adapter -> cherryquant.adapters.data_adapter
      - services as svc       -> cherryquant.services as svc
    """
    original = token
    ts = token.lstrip()
    leading = token[: len(token) - len(ts)]  # 保留前导空白
    # 处理 "name as alias"
    # 格式可能是：   ai as alias
    # 或者：         adapters.data_storage as ds
    # 直接找到首个空格之前的模块前缀，再做替换
    head = ts
    rest = ""
    if " " in ts:
        space_idx = ts.find(" ")
        head, rest = ts[:space_idx], ts[space_idx:]  # head: 模块部分；rest: " as alias"
    # 匹配前缀表
    for old, new in PREFIX_MAP.items():
        if head == old:
            head = new
            break
        if head.startswith(old + "."):
            head = new + head[len(old) :]
            break
    new_token = leading + head + rest
    if new_token != original:
        return new_token
    return token


def transform_import_line(line: str) -> Tuple[str, bool]:
    """
    仅处理以 'import ' 起始的行：
      import ai, adapters as ad, os
    """
    original = line
    # 保留行尾换行符
    end = ""
    if line.endswith("\n"):
        end = "\n"
        line = line[:-1]

    if not line.lstrip().startswith("import "):
        return original, False

    leading = line[: len(line) - len(line.lstrip())]
    body = line.strip()  # 'import ...'
    _, rest = body.split("import", 1)
    # 逗号分隔各 token
    parts = [p.strip() for p in rest.split(",")]
    new_parts = [transform_import_token(p) for p in parts]
    new_line = f"{leading}import {', '.join(new_parts)}{end}"
    return (new_line, new_line != original)


def transform_from_import_line(line: str) -> Tuple[str, bool]:
    """
    仅处理以 'from ' 起始的行：
      from ai.decision_engine import FuturesDecisionEngine
      from adapters import data_adapter
    """
    original = line
    # 保留行尾换行符
    end = ""
    if line.endswith("\n"):
        end = "\n"
        line = line[:-1]

    ls = line.lstrip()
    if not ls.startswith("from "):
        return original, False

    leading = line[: len(line) - len(ls)]
    # 拆分 'from <module> import <names>'
    # 注意：尽量稳妥，不处理极端换行续行的复杂情况（大部分场景足够）
    try:
        _, tail = ls.split("from ", 1)
        module, after = tail.split(" import ", 1)
    except ValueError:
        # 结构不符合预期，不处理
        return original, False

    module_strip = module.strip()
    new_module = module_strip
    for old, new in PREFIX_MAP.items():
        if module_strip == old:
            new_module = new
            break
        if module_strip.startswith(old + "."):
            new_module = new + module_strip[len(old) :]
            break

    new_line = f"{leading}from {new_module} import {after}{end}"
    return (new_line, new_line != original)


def transform_line(line: str) -> Tuple[str, bool]:
    """
    处理单行：
      - import ...
      - from ... import ...
    其他行原样返回。
    """
    new_line, changed = transform_import_line(line)
    if changed:
        return new_line, True
    new_line, changed = transform_from_import_line(line)
    if changed:
        return new_line, True
    return line, False


def refactor_text(text: str) -> Tuple[str, List[Tuple[int, str, str]]]:
    """
    返回新的文本与变更列表 [(lineno, old, new), ...]
    """
    lines = text.splitlines(keepends=True)
    changes: List[Tuple[int, str, str]] = []
    out_lines: List[str] = []
    for idx, line in enumerate(lines, start=1):
        new_line, changed = transform_line(line)
        out_lines.append(new_line)
        if changed:
            changes.append((idx, line, new_line))
    return "".join(out_lines), changes


def print_diff(path: Path, old: str, new: str) -> None:
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=str(path),
        tofile=str(path),
    )
    sys.stdout.writelines(diff)


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] 非法路径：{root}", file=sys.stderr)
        return 2

    exts = {e if e.startswith(".") else f".{e}" for e in args.ext.split(",")}
    extra_skips = set(args.exclude_dir or [])
    files = scan_files(root, exts, extra_skips)

    total = 0
    changed_files = 0
    changed_lines = 0

    for fp in files:
        try:
            original = fp.read_text(encoding="utf-8")
        except Exception as e:
            if args.verbose:
                print(f"[WARN] 无法读取：{fp} ({e})")
            continue

        new_text, changes = refactor_text(original)
        total += 1

        if not changes:
            continue

        changed_files += 1
        changed_lines += len(changes)

        if args.verbose:
            print(f"\n{'UPDATED' if args.apply else 'WOULD-UPDATE'}: {fp}")
            for lineno, old, new in changes:
                old_s = old.rstrip("\n")
                new_s = new.rstrip("\n")
                print(f"  L{lineno}:")
                print(f"    - {old_s}")
                print(f"    + {new_s}")

        if args.show_diff:
            print_diff(fp, original, new_text)

        if args.apply:
            try:
                fp.write_text(new_text, encoding="utf-8")
            except Exception as e:
                print(f"[ERROR] 写回失败：{fp} ({e})", file=sys.stderr)

    print("\n========== 迁移结果 ==========")
    print(f"扫描文件数: {total}")
    print(f"{'修改文件数' if args.apply else '将修改文件数'}: {changed_files}")
    print(f"{'修改总行数' if args.apply else '将修改总行数'}: {changed_lines}")
    if not args.apply:
        print("当前为 dry-run（预览模式），添加 --apply 才会写回文件")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
