"""
环境验证脚本

用于验证 CherryQuant 开发环境是否正确配置
适用于学生完成 Module 0 后的环境检查
"""

import asyncio
import sys
from pathlib import Path
from typing import Tuple

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class Colors:
    """终端颜色"""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def check_python_version() -> Tuple[bool, str]:
    """检查 Python 版本"""
    version_info = sys.version_info
    if version_info.major == 3 and version_info.minor >= 12:
        return True, f"Python {version_info.major}.{version_info.minor}.{version_info.micro}"
    return False, f"Python {version_info.major}.{version_info.minor} (需要 3.12+)"


def check_uv_installed() -> Tuple[bool, str]:
    """检查 uv 是否安装"""
    import subprocess

    try:
        result = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, version
        return False, "uv 命令运行失败"
    except FileNotFoundError:
        return False, "uv 未安装"
    except Exception as e:
        return False, f"检查失败: {str(e)}"


def check_env_file() -> Tuple[bool, str]:
    """检查 .env 文件是否存在"""
    env_file = project_root / ".env"
    if env_file.exists():
        return True, str(env_file)
    return False, ".env 文件不存在（请从 .env.example 复制）"


def check_dependencies() -> Tuple[bool, str]:
    """检查关键依赖是否安装"""
    try:
        import structlog  # noqa: F401
        import motor  # noqa: F401
        import redis  # noqa: F401
        from vnpy.trader.constant import Exchange  # noqa: F401

        return True, "所有关键依赖已安装"
    except ImportError as e:
        return False, f"依赖缺失: {str(e)}"


async def check_mongodb() -> Tuple[bool, str]:
    """检查 MongoDB 连接"""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        from config.settings.settings import get_settings

        settings = get_settings()
        client = AsyncIOMotorClient(
            f"mongodb://{settings.mongo_host}:{settings.mongo_port}",
            serverSelectionTimeoutMS=3000,
        )
        # 测试连接
        await client.admin.command("ping")
        await client.close()
        return True, f"{settings.mongo_host}:{settings.mongo_port}"
    except Exception as e:
        return False, f"连接失败: {str(e)}"


async def check_redis() -> Tuple[bool, str]:
    """检查 Redis 连接"""
    try:
        import redis.asyncio as aioredis

        from config.settings.settings import get_settings

        settings = get_settings()
        client = aioredis.from_url(
            f"redis://{settings.redis_host}:{settings.redis_port}",
            decode_responses=True,
            socket_connect_timeout=3,
        )
        await client.ping()
        await client.close()
        return True, f"{settings.redis_host}:{settings.redis_port}"
    except Exception as e:
        return False, f"连接失败: {str(e)}"


def check_directory_structure() -> Tuple[bool, str]:
    """检查项目目录结构"""
    required_dirs = [
        "config",
        "src/cherryquant",
        "examples",
        "docs/course",
        "tests",
        "scripts",
    ]

    missing_dirs = []
    for dir_path in required_dirs:
        if not (project_root / dir_path).exists():
            missing_dirs.append(dir_path)

    if not missing_dirs:
        return True, "所有必需目录存在"
    return False, f"缺失目录: {', '.join(missing_dirs)}"


def print_check_result(name: str, success: bool, message: str):
    """打印检查结果"""
    icon = "✅" if success else "❌"
    color = Colors.GREEN if success else Colors.RED
    print(f"  {icon} {color}{name}{Colors.RESET}: {message}")


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🔍 CherryQuant 环境验证")
    print("=" * 60 + "\n")

    checks = []

    # 同步检查
    print("📋 基础环境检查:")
    checks.append(("Python 版本", *check_python_version()))
    checks.append(("uv 包管理器", *check_uv_installed()))
    checks.append((".env 配置文件", *check_env_file()))
    checks.append(("Python 依赖", *check_dependencies()))
    checks.append(("项目目录结构", *check_directory_structure()))

    for check in checks:
        print_check_result(*check)

    # 异步检查
    print("\n🗄️  数据库服务检查:")
    mongo_check = ("MongoDB", *await check_mongodb())
    redis_check = ("Redis", *await check_redis())

    print_check_result(*mongo_check)
    print_check_result(*redis_check)

    all_checks = checks + [mongo_check, redis_check]

    # 统计结果
    passed = sum(1 for _, success, _ in all_checks if success)
    total = len(all_checks)
    success_rate = (passed / total) * 100

    print("\n" + "=" * 60)
    print(f"📊 检查结果: {passed}/{total} 项通过 ({success_rate:.1f}%)")
    print("=" * 60 + "\n")

    if passed == total:
        print(f"{Colors.GREEN}🎉 恭喜！环境配置完全正确！{Colors.RESET}")
        print("\n💡 下一步:")
        print("  1. 运行示例: uv run python examples/01_basics/hello_cherryquant.py")
        print("  2. 学习 Module 1: docs/course/01_System_Architecture.md")
        print("  3. 完成 Lab 01 实验任务\n")
        return 0
    else:
        print(f"{Colors.YELLOW}⚠️  部分检查未通过，请修复以下问题:{Colors.RESET}\n")

        for name, success, message in all_checks:
            if not success:
                print(f"  • {name}: {message}")

        print(f"\n{Colors.BLUE}💡 常见问题解决方案:{Colors.RESET}")
        print("  • MongoDB/Redis 连接失败:")
        print("    → docker-compose up -d mongodb redis")
        print("  • .env 文件不存在:")
        print("    → cp .env.example .env")
        print("  • Python 依赖缺失:")
        print("    → uv sync")
        print("\n📚 详细帮助: docs/course/00_Prerequisites.md\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
