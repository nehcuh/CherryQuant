#!/usr/bin/env python3
"""
修复 .env 文件中的重复配置
"""
import re
from pathlib import Path

def fix_env_file():
    """清理 .env 文件中的重复配置"""
    env_file = Path('.env')

    if not env_file.exists():
        print("❌ .env 文件不存在")
        return

    # 读取原文件
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 记录已见过的键
    seen_keys = {}
    duplicates = []

    # 第一遍：找出所有重复的配置
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith('#'):
            continue

        if '=' in line_stripped:
            key = line_stripped.split('=')[0].strip()
            if key in seen_keys:
                duplicates.append({
                    'key': key,
                    'first_line': seen_keys[key],
                    'duplicate_line': i,
                    'first_value': lines[seen_keys[key]-1].strip(),
                    'duplicate_value': line.strip()
                })
            else:
                seen_keys[key] = i

    if not duplicates:
        print("✅ 没有发现重复的配置")
        return

    print(f"\n⚠️  发现 {len(duplicates)} 个重复配置:\n")
    for dup in duplicates:
        print(f"配置项: {dup['key']}")
        print(f"  第一次出现 (行{dup['first_line']}): {dup['first_value']}")
        print(f"  重复出现 (行{dup['duplicate_line']}): {dup['duplicate_value']}")
        print()

    # 询问用户如何处理
    print("\n处理方式:")
    print("1. 保留第一次出现的配置，删除后面的重复项")
    print("2. 保留最后一次出现的配置，删除前面的重复项")
    print("3. 手动选择保留哪个")
    print("4. 取消，不做任何修改")

    choice = input("\n请选择 (1-4): ").strip()

    if choice == '4':
        print("取消操作")
        return
    elif choice == '1':
        # 保留第一次出现
        lines_to_remove = set(dup['duplicate_line'] - 1 for dup in duplicates)
        new_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
        print(f"\n✅ 将保留第一次出现的配置，删除 {len(lines_to_remove)} 行重复配置")
    elif choice == '2':
        # 保留最后一次出现
        lines_to_remove = set(dup['first_line'] - 1 for dup in duplicates)
        new_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
        print(f"\n✅ 将保留最后一次出现的配置，删除 {len(lines_to_remove)} 行重复配置")
    else:
        print("❌ 无效选择")
        return

    # 写入新文件
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"✅ .env 文件已更新")
    print(f"备份文件: .env.backup_*")

if __name__ == '__main__':
    fix_env_file()
