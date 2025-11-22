"""
CherryQuant 入门示例 - Hello CherryQuant

这是最简单的 CherryQuant 示例程序，演示：
1. 如何加载项目配置
2. 如何使用结构化日志
3. 如何访问基本的项目信息

学习目标：
- 理解项目的基本导入方式
- 了解配置加载流程
- 熟悉日志输出

难度：⭐ 入门级
预计时间：5-10 分钟
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import structlog
from config.settings.settings import CONFIG

# 配置结构化日志
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

def main():
    """主函数"""
    # 1. 欢迎信息
    print("\n" + "=" * 60)
    print("🍒 欢迎使用 CherryQuant AI 量化交易教学项目！")
    print("=" * 60 + "\n")

    # 2. 加载配置
    logger.info("正在加载项目配置...")
    # CONFIG 已经在导入时加载
    logger.info("✅ 环境配置加载成功")

    # 3. 显示基本信息
    print("\n📋 项目基本信息:")
    print(f"  • 项目根目录: {project_root}")
    print(f"  • 日志级别: {CONFIG.logging.level}")
    print(f"  • 是否启用调试模式: {CONFIG.debug}")

    # 4. 显示数据库配置（隐藏敏感信息）
    print("\n🗄️  数据库配置:")
    print(f"  • MongoDB 数据库: {CONFIG.database.mongodb_database}")
    print(f"  • Redis 主机: {CONFIG.database.redis_host}")

    # 5. 显示支持的期货品种 (示例)
    # 由于 config.symbols 可能不存在，这里使用硬编码示例
    FUTURES_SYMBOLS = {
        "rb2601": {"sector": "黑色"},
        "hc2601": {"sector": "黑色"},
        "i2601":  {"sector": "黑色"},
        "cu2601": {"sector": "有色"},
        "al2601": {"sector": "有色"},
    }

    print(f"\n📊 支持的期货品种 (示例 - {len(FUTURES_SYMBOLS)} 个):")
    # 按板块分组显示
    sectors = {}
    for symbol, info in FUTURES_SYMBOLS.items():
        sector = info.get("sector", "未分类")
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append(symbol)

    for sector, symbols in sorted(sectors.items()):
        print(f"  • {sector}: {', '.join(sorted(symbols))}")

    # 6. 成功提示
    print("\n" + "=" * 60)
    print("✅ 示例运行成功！")
    print("=" * 60)
    print("\n💡 下一步:")
    print("  1. 阅读 docs/course/01_System_Architecture.md 了解系统架构")
    print("  2. 运行 examples/02_data/ 下的数据获取示例")
    print("  3. 完成 Lab 01 实验任务")
    print()

if __name__ == "__main__":
    main()
