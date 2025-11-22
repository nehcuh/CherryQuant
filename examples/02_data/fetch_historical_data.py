#!/usr/bin/env python3
"""
获取历史数据示例

难度：⭐⭐ 初级

学习要点：
1. Tushare 数据源使用
2. 数据适配器模式
3. 异步数据获取
4. 数据验证和清洗

运行方式：
    uv run python examples/02_data/fetch_historical_data.py

前置要求：
    - 设置 TUSHARE_TOKEN 环境变量
    - MongoDB 服务运行中（可选）
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cherryquant.data.collectors.tushare_collector import TushareCollector
from cherryquant.data.collectors.base_collector import Exchange, TimeFrame
from cherryquant.data.cleaners.validator import DataValidator
from cherryquant.data.cleaners.normalizer import DataNormalizer


async def example_1_basic_fetch():
    """示例1：基础数据获取"""
    print("\n" + "=" * 60)
    print("示例 1: 基础历史数据获取")
    print("=" * 60 + "\n")

    # 1. 初始化采集器
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token or tushare_token == "your_tushare_pro_token_here":
        print("❌ 错误: 请设置 TUSHARE_TOKEN 环境变量")
        print("   获取方式: https://tushare.pro")
        return

    print("📦 初始化 Tushare 采集器...")
    collector = TushareCollector(token=tushare_token)
    await collector.connect()
    print("✅ 采集器连接成功\n")

    # 2. 获取螺纹钢 rb2501 的日线数据
    symbol = "rb2501"
    exchange = Exchange.SHFE
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()

    print(f"📊 获取 {symbol}.{exchange.value} 的日线数据")
    print(f"   时间范围: {start_date.date()} 至 {end_date.date()}")

    market_data = await collector.fetch_market_data(
        symbol=symbol,
        exchange=exchange,
        start_date=start_date,
        end_date=end_date,
        timeframe=TimeFrame.DAY_1,
    )

    print(f"\n✅ 获取成功: {len(market_data)} 条数据")

    # 3. 显示前3条数据
    if market_data:
        print("\n前3条数据:")
        for i, data in enumerate(market_data[:3]):
            print(f"\n  [{i+1}] {data.datetime.date()}")
            print(f"      开盘: {data.open:.2f}")
            print(f"      最高: {data.high:.2f}")
            print(f"      最低: {data.low:.2f}")
            print(f"      收盘: {data.close:.2f}")
            print(f"      成交量: {data.volume:,}")

    # 4. 断开连接
    await collector.disconnect()
    print("\n✅ 示例1完成")


async def example_2_with_validation():
    """示例2：带数据验证的获取"""
    print("\n" + "=" * 60)
    print("示例 2: 带数据验证的历史数据获取")
    print("=" * 60 + "\n")

    # 1. 初始化组件
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token or tushare_token == "your_tushare_pro_token_here":
        print("❌ 错误: 请设置 TUSHARE_TOKEN 环境变量")
        return

    collector = TushareCollector(token=tushare_token)
    validator = DataValidator()
    await collector.connect()

    # 2. 获取数据
    symbol = "hc2501"
    exchange = Exchange.SHFE
    start_date = datetime.now() - timedelta(days=60)
    end_date = datetime.now()

    print(f"📊 获取 {symbol}.{exchange.value} 的数据...")

    market_data = await collector.fetch_market_data(
        symbol=symbol,
        exchange=exchange,
        start_date=start_date,
        end_date=end_date,
        timeframe=TimeFrame.DAY_1,
    )

    print(f"✅ 获取 {len(market_data)} 条原始数据")

    # 3. 数据验证
    print("\n🔍 开始数据验证...")

    valid_data, invalid_data, validation_result = (
        validator.validate_market_data_batch(market_data)
    )

    print(f"\n验证结果:")
    print(f"  ✅ 有效数据: {len(valid_data)} 条")
    print(f"  ❌ 无效数据: {len(invalid_data)} 条")
    total = len(valid_data) + len(invalid_data)
    pass_rate = len(valid_data) / total if total > 0 else 0
    print(f"  📊 通过率: {pass_rate:.1%}")

    # 4. 显示无效数据的问题
    if invalid_data:
        print(f"\n⚠️  发现 {len(invalid_data)} 条无效数据:")
        for i, (data, issues) in enumerate(invalid_data[:3]):
            print(f"\n  [{i+1}] {data.datetime.date()}")
            print(f"      问题: {', '.join(issues)}")

    # 5. 断开连接
    await collector.disconnect()
    print("\n✅ 示例2完成")


async def example_3_multi_symbols():
    """示例3：批量获取多个品种数据"""
    print("\n" + "=" * 60)
    print("示例 3: 批量获取多个品种的历史数据")
    print("=" * 60 + "\n")

    # 1. 初始化采集器
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token or tushare_token == "your_tushare_pro_token_here":
        print("❌ 错误: 请设置 TUSHARE_TOKEN 环境变量")
        return

    collector = TushareCollector(token=tushare_token)
    normalizer = DataNormalizer()
    await collector.connect()

    # 2. 定义要获取的品种
    symbols = [
        ("rb2501", Exchange.SHFE, "螺纹钢"),
        ("hc2501", Exchange.SHFE, "热卷"),
        ("i2501", Exchange.DCE, "铁矿石"),
    ]

    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()

    print(f"📊 批量获取 {len(symbols)} 个品种的数据")
    print(f"   时间范围: {start_date.date()} 至 {end_date.date()}\n")

    # 3. 并发获取数据
    async def fetch_one(symbol: str, exchange: Exchange, name: str):
        print(f"  → 获取 {name} ({symbol}.{exchange.value})...")
        data = await collector.fetch_market_data(
            symbol=symbol,
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
            timeframe=TimeFrame.DAY_1,
        )

        # 标准化数据
        normalized_data = normalizer.normalize_batch(
            data,
            deduplicate=True,
            fill_missing=False,
        )

        return name, len(normalized_data)

    # 并发执行
    tasks = [fetch_one(sym, exch, name) for sym, exch, name in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. 显示结果
    print("\n结果汇总:")
    for result in results:
        if isinstance(result, Exception):
            print(f"  ❌ 错误: {result}")
        else:
            name, count = result
            print(f"  ✅ {name}: {count} 条数据")

    # 5. 断开连接
    await collector.disconnect()
    print("\n✅ 示例3完成")


async def example_4_different_timeframes():
    """示例4：获取不同时间周期的数据"""
    print("\n" + "=" * 60)
    print("示例 4: 获取不同时间周期的数据")
    print("=" * 60 + "\n")

    # 1. 初始化采集器
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token or tushare_token == "your_tushare_pro_token_here":
        print("❌ 错误: 请设置 TUSHARE_TOKEN 环境变量")
        return

    collector = TushareCollector(token=tushare_token)
    await collector.connect()

    # 2. 定义不同的时间周期
    symbol = "rb2501"
    exchange = Exchange.SHFE
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()

    timeframes = [
        (TimeFrame.MIN_1, "1分钟"),
        (TimeFrame.MIN_5, "5分钟"),
        (TimeFrame.MIN_15, "15分钟"),
        (TimeFrame.HOUR_1, "1小时"),
        (TimeFrame.DAY_1, "日线"),
    ]

    print(f"📊 获取 {symbol}.{exchange.value} 的多周期数据")
    print(f"   时间范围: {start_date.date()} 至 {end_date.date()}\n")

    # 3. 获取各周期数据
    for timeframe, name in timeframes:
        try:
            print(f"  → 获取 {name} 数据...")
            data = await collector.fetch_market_data(
                symbol=symbol,
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
            )
            print(f"    ✅ {len(data)} 条数据")
        except Exception as e:
            print(f"    ⚠️  暂不支持: {e}")

    # 4. 断开连接
    await collector.disconnect()
    print("\n✅ 示例4完成")


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("📚 CherryQuant 数据获取示例 - 历史数据")
    print("=" * 70)

    try:
        # 运行所有示例
        await example_1_basic_fetch()
        await example_2_with_validation()
        await example_3_multi_symbols()
        await example_4_different_timeframes()

        # 总结
        print("\n" + "=" * 70)
        print("✅ 所有示例运行完成！")
        print("=" * 70)
        print("\n💡 下一步:")
        print("  1. 阅读 docs/course/02_Data_Pipeline.md 深入学习数据管道")
        print("  2. 运行 examples/02_data/data_storage.py 学习数据存储")
        print("  3. 完成 Lab 02 实验任务")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
