#!/usr/bin/env python3
"""
数据管道完整示例

展示如何使用新的数据管道进行端到端的数据处理。

教学要点：
1. 数据管道的初始化和配置
2. 完整的数据采集、清洗、存储流程
3. 缓存策略的应用
4. 质量控制和监控

运行方式：
    python examples/data_pipeline_demo.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from cherryquant.data.pipeline import DataPipeline
from cherryquant.data.collectors.tushare_collector import TushareCollector
from cherryquant.data.collectors.base_collector import Exchange, TimeFrame
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager


async def demo_basic_usage():
    """基础用法演示"""
    print("\n" + "=" * 60)
    print("示例 1: 基础数据采集和存储")
    print("=" * 60 + "\n")

    # 1. 初始化组件
    print("📦 初始化组件...")

    # 数据库连接
    db_manager = MongoDBConnectionManager(
        uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        database=os.getenv("MONGODB_DATABASE", "cherryquant"),
    )

    # 数据采集器
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token or tushare_token == "your_tushare_pro_token_here":
        print("❌ 错误: 请设置 TUSHARE_TOKEN 环境变量")
        return

    collector = TushareCollector(token=tushare_token)

    # 创建数据管道
    pipeline = DataPipeline(
        collector=collector,
        db_manager=db_manager,
        enable_cache=True,
        enable_validation=True,
        enable_quality_control=True,
    )

    # 2. 初始化管道
    await pipeline.initialize()
    print("✅ 数据管道初始化完成\n")

    # 3. 采集并存储数据
    print("📊 采集螺纹钢 rb2501 的日线数据...")

    result = await pipeline.collect_and_store_market_data(
        symbol="rb2501",
        exchange=Exchange.SHFE,
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now(),
        timeframe=TimeFrame.DAY_1,
    )

    print(f"\n采集结果:")
    print(f"  - 采集数量: {result['collected_count']}")
    print(f"  - 有效数量: {result.get('valid_count', 'N/A')}")
    print(f"  - 存储数量: {result['stored_count']}")
    print(f"  - 质量得分: {result.get('quality_score', 'N/A'):.2%}")

    if result.get('errors'):
        print(f"  - 错误: {', '.join(result['errors'])}")

    # 4. 查询数据（第一次，从数据库）
    print("\n📖 查询数据（第一次，从数据库）...")

    market_data = await pipeline.get_market_data(
        symbol="rb2501",
        exchange=Exchange.SHFE,
        start_date=datetime.now() - timedelta(days=7),
        end_date=datetime.now(),
        timeframe=TimeFrame.DAY_1,
        use_cache=True,
    )

    print(f"查询到 {len(market_data)} 条数据")
    if market_data:
        latest = market_data[-1]
        print(f"最新数据: {latest.datetime.date()} 收盘价={latest.close}")

    # 5. 再次查询（第二次，从缓存）
    print("\n📦 查询数据（第二次，从缓存）...")

    market_data_cached = await pipeline.get_market_data(
        symbol="rb2501",
        exchange=Exchange.SHFE,
        start_date=datetime.now() - timedelta(days=7),
        end_date=datetime.now(),
        timeframe=TimeFrame.DAY_1,
        use_cache=True,
    )

    print(f"查询到 {len(market_data_cached)} 条数据（应该来自缓存）")

    # 6. 关闭管道
    await pipeline.shutdown()


async def demo_calendar_and_contracts():
    """交易日历和合约管理演示"""
    print("\n" + "=" * 60)
    print("示例 2: 交易日历和合约管理")
    print("=" * 60 + "\n")

    # 初始化
    db_manager = MongoDBConnectionManager()
    collector = TushareCollector(token=os.getenv("TUSHARE_TOKEN"))

    pipeline = DataPipeline(
        collector=collector,
        db_manager=db_manager,
        enable_cache=True,
    )

    await pipeline.initialize()

    # 1. 同步交易日历
    print("📅 同步交易日历...")

    calendar_count = await pipeline.sync_trading_calendar(
        exchange=Exchange.SHFE,
        start_date=datetime.now() - timedelta(days=90),
        end_date=datetime.now() + timedelta(days=30),
    )

    print(f"同步了 {calendar_count} 天的交易日历")

    # 2. 查询交易日
    print("\n📆 查询最近的交易日...")

    today = datetime.now()
    is_trading = await pipeline.is_trading_day(today, Exchange.SHFE)
    print(f"{today.date()} 是否交易日: {'是' if is_trading else '否'}")

    next_trading = await pipeline.get_next_trading_day(today, Exchange.SHFE)
    if next_trading:
        print(f"下一个交易日: {next_trading.date()}")

    # 3. 同步合约信息
    print("\n📋 同步合约信息...")

    contract_count = await pipeline.sync_contracts(exchange=Exchange.SHFE)
    print(f"同步了 {contract_count} 个合约")

    # 4. 查询合约
    print("\n🔍 查询螺纹钢合约...")

    contract = await pipeline.get_contract("rb2501", Exchange.SHFE)
    if contract:
        print(f"合约名称: {contract.name}")
        print(f"合约乘数: {contract.multiplier}")
        print(f"最小变动价位: {contract.price_tick}")
        print(f"到期日期: {contract.expire_date.date()}")

    # 5. 查询主力合约
    print("\n⭐ 查询螺纹钢主力合约...")

    main_contract = await pipeline.get_main_contract("rb", Exchange.SHFE)
    if main_contract:
        print(f"主力合约: {main_contract.symbol}")
        print(f"到期日期: {main_contract.expire_date.date()}")

    await pipeline.shutdown()


async def demo_batch_operations():
    """批量操作演示"""
    print("\n" + "=" * 60)
    print("示例 3: 批量数据采集")
    print("=" * 60 + "\n")

    # 初始化
    db_manager = MongoDBConnectionManager()
    collector = TushareCollector(token=os.getenv("TUSHARE_TOKEN"))

    pipeline = DataPipeline(
        collector=collector,
        db_manager=db_manager,
        enable_cache=True,
    )

    await pipeline.initialize()

    # 批量采集多个合约的数据
    print("📦 批量采集数据...")

    requests = [
        {
            "symbol": "rb2501",
            "exchange": Exchange.SHFE,
            "start_date": datetime.now() - timedelta(days=30),
            "end_date": datetime.now(),
            "timeframe": TimeFrame.DAY_1,
        },
        {
            "symbol": "hc2501",
            "exchange": Exchange.SHFE,
            "start_date": datetime.now() - timedelta(days=30),
            "end_date": datetime.now(),
            "timeframe": TimeFrame.DAY_1,
        },
        {
            "symbol": "i2501",
            "exchange": Exchange.DCE,
            "start_date": datetime.now() - timedelta(days=30),
            "end_date": datetime.now(),
            "timeframe": TimeFrame.DAY_1,
        },
    ]

    results = await pipeline.batch_collect_and_store(
        requests=requests,
        concurrent_limit=3,
    )

    # 统计结果
    print("\n批量采集结果:")
    for i, result in enumerate(results):
        if isinstance(result, dict):
            print(
                f"  {i+1}. {result['symbol']}.{result['exchange']}: "
                f"采集 {result['collected_count']}, "
                f"存储 {result['stored_count']}"
            )
        else:
            print(f"  {i+1}. 错误: {result}")

    await pipeline.shutdown()


async def demo_warm_up():
    """缓存预热演示"""
    print("\n" + "=" * 60)
    print("示例 4: 缓存预热")
    print("=" * 60 + "\n")

    # 初始化
    db_manager = MongoDBConnectionManager()
    collector = TushareCollector(token=os.getenv("TUSHARE_TOKEN"))

    pipeline = DataPipeline(
        collector=collector,
        db_manager=db_manager,
        enable_cache=True,
    )

    await pipeline.initialize()

    # 缓存预热
    print("🔥 开始缓存预热...")

    warm_up_stats = await pipeline.warm_up(
        symbols=["rb2501", "hc2501", "i2501"],
        exchange=Exchange.SHFE,
        days_back=30,
        timeframes=[TimeFrame.DAY_1],
    )

    print(f"\n预热结果:")
    print(f"  - 总请求: {warm_up_stats['total_requests']}")
    print(f"  - 缓存填充: {warm_up_stats['cache_filled']}")

    # 显示缓存统计
    print("\n📊 缓存统计:")
    pipeline.cache.print_stats()

    await pipeline.shutdown()


async def demo_pipeline_stats():
    """管道统计演示"""
    print("\n" + "=" * 60)
    print("示例 5: 管道统计和监控")
    print("=" * 60 + "\n")

    # 初始化
    db_manager = MongoDBConnectionManager()
    collector = TushareCollector(token=os.getenv("TUSHARE_TOKEN"))

    pipeline = DataPipeline(
        collector=collector,
        db_manager=db_manager,
        enable_cache=True,
        enable_validation=True,
        enable_quality_control=True,
    )

    await pipeline.initialize()

    # 执行一些操作
    await pipeline.collect_and_store_market_data(
        symbol="rb2501",
        exchange=Exchange.SHFE,
        start_date=datetime.now() - timedelta(days=7),
        end_date=datetime.now(),
        timeframe=TimeFrame.DAY_1,
    )

    await pipeline.get_market_data(
        symbol="rb2501",
        exchange=Exchange.SHFE,
        start_date=datetime.now() - timedelta(days=7),
        end_date=datetime.now(),
        timeframe=TimeFrame.DAY_1,
    )

    # 显示统计信息
    print("📊 数据管道统计:")
    pipeline.print_stats()

    await pipeline.shutdown()


async def main():
    """主函数"""
    print("\n")
    print("=" * 60)
    print("CherryQuant 数据管道完整示例")
    print("=" * 60)
    print("\n这个示例展示了新数据管道的所有核心功能:")
    print("  1. 基础数据采集和存储")
    print("  2. 交易日历和合约管理")
    print("  3. 批量数据采集")
    print("  4. 缓存预热")
    print("  5. 管道统计和监控")
    print("\n" + "=" * 60)

    # 检查环境变量
    if not os.getenv("TUSHARE_TOKEN"):
        print("\n⚠️  请先设置环境变量:")
        print("export TUSHARE_TOKEN=your_token_here")
        print("export MONGODB_URI=mongodb://localhost:27017")
        print("export MONGODB_DATABASE=cherryquant")
        return

    try:
        # 运行所有示例
        await demo_basic_usage()
        await demo_calendar_and_contracts()
        await demo_batch_operations()
        await demo_warm_up()
        await demo_pipeline_stats()

        print("\n" + "=" * 60)
        print("✅ 所有示例运行完成！")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
