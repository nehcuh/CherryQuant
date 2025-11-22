#!/usr/bin/env python3
"""
数据存储示例

难度：⭐⭐ 初级

学习要点：
1. MongoDB 时间序列集合
2. 批量插入优化
3. 索引设计
4. 数据去重

运行方式：
    uv run python examples/02_data/data_storage.py

前置要求：
    - MongoDB 服务运行中
    - 设置 MONGODB_URI 环境变量（可选）
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cherryquant.data.pipeline import DataPipeline
from cherryquant.data.collectors.base_collector import Exchange, TimeFrame, MarketData
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager


class MockCollector:
    """模拟数据采集器（用于演示存储，无需真实API）"""

    def __init__(self):
        self.is_connected = False

    async def connect(self):
        self.is_connected = True

    async def disconnect(self):
        self.is_connected = False

    async def fetch_market_data(
        self, symbol: str, exchange: Exchange, start_date: datetime, end_date: datetime, timeframe: TimeFrame
    ) -> list[MarketData]:
        """生成模拟数据"""
        import random

        data = []
        current = start_date
        base_price = 3500.0

        while current <= end_date:
            price = base_price + random.uniform(-50, 50)
            data.append(
                MarketData(
                    symbol=symbol,
                    exchange=exchange,
                    datetime=current,
                    open=price,
                    high=price + random.uniform(0, 20),
                    low=price - random.uniform(0, 20),
                    close=price + random.uniform(-10, 10),
                    volume=random.randint(50000, 150000),
                    open_interest=random.randint(100000, 300000),
                    timeframe=timeframe,
                )
            )
            current += timedelta(days=1)

        return data


async def example_1_basic_storage():
    """示例1：基础数据存储"""
    print("\n" + "=" * 60)
    print("示例 1: 基础数据存储到MongoDB")
    print("=" * 60 + "\n")

    # 1. 初始化数据库连接
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_manager = MongoDBConnectionManager(uri=mongo_uri, database="cherryquant_demo")

    print(f"📦 连接MongoDB: {mongo_uri}")

    try:
        await db_manager.connect()
        print("✅ 数据库连接成功\n")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("   请确保MongoDB服务已启动")
        return

    # 2. 创建数据管道
    collector = MockCollector()
    pipeline = DataPipeline(
        collector=collector,
        db_manager=db_manager,
        enable_cache=True,
        enable_validation=True,
    )

    await pipeline.initialize()

    # 3. 采集并存储数据
    symbol = "rb2501"
    exchange = Exchange.SHFE
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()

    print(f"📊 采集并存储 {symbol}.{exchange.value} 的数据...")
    print(f"   时间范围: {start_date.date()} 至 {end_date.date()}")

    result = await pipeline.collect_and_store_market_data(
        symbol=symbol,
        exchange=exchange,
        start_date=start_date,
        end_date=end_date,
        timeframe=TimeFrame.DAY_1,
    )

    print(f"\n存储结果:")
    print(f"  采集: {result['collected_count']} 条")
    print(f"  存储: {result['stored_count']} 条")
    print(f"  质量评分: {result.get('quality_score', 0):.1%}")

    # 4. 查询验证
    print(f"\n🔍 查询验证...")
    stored_data = await pipeline.get_market_data(
        symbol=symbol,
        exchange=exchange,
        start_date=start_date,
        end_date=end_date,
        timeframe=TimeFrame.DAY_1,
    )

    print(f"✅ 查询到 {len(stored_data)} 条数据")

    if stored_data:
        latest = stored_data[-1]
        print(f"\n最新数据:")
        print(f"  日期: {latest.datetime.date()}")
        print(f"  收盘价: {latest.close:.2f}")

    # 5. 清理
    await pipeline.shutdown()
    print("\n✅ 示例1完成")


async def example_2_batch_insert():
    """示例2：批量插入优化"""
    print("\n" + "=" * 60)
    print("示例 2: 批量插入性能优化")
    print("=" * 60 + "\n")

    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_manager = MongoDBConnectionManager(uri=mongo_uri, database="cherryquant_demo")

    try:
        await db_manager.connect()
    except:
        print("❌ 数据库连接失败，跳过示例")
        return

    collector = MockCollector()
    pipeline = DataPipeline(collector=collector, db_manager=db_manager)
    await pipeline.initialize()

    # 批量采集多个品种
    symbols = ["rb2501", "hc2501", "i2501"]
    requests = []

    for symbol in symbols:
        requests.append(
            {
                "symbol": symbol,
                "exchange": Exchange.SHFE if symbol.startswith(("rb", "hc")) else Exchange.DCE,
                "start_date": datetime.now() - timedelta(days=60),
                "end_date": datetime.now(),
                "timeframe": TimeFrame.DAY_1,
            }
        )

    print(f"📦 批量采集 {len(requests)} 个品种的数据...")

    # 并发执行
    import time

    start_time = time.time()

    results = await pipeline.batch_collect_and_store(requests, concurrent_limit=3)

    elapsed = time.time() - start_time

    # 统计结果
    success = sum(1 for r in results if isinstance(r, dict) and r.get("stored_count", 0) > 0)
    total_stored = sum(r.get("stored_count", 0) for r in results if isinstance(r, dict))

    print(f"\n批量存储结果:")
    print(f"  成功: {success}/{len(requests)}")
    print(f"  总存储: {total_stored} 条")
    print(f"  耗时: {elapsed:.2f}秒")
    print(f"  平均: {total_stored / elapsed:.0f} 条/秒")

    await pipeline.shutdown()
    print("\n✅ 示例2完成")


async def example_3_deduplication():
    """示例3：数据去重和更新"""
    print("\n" + "=" * 60)
    print("示例 3: 数据去重机制")
    print("=" * 60 + "\n")

    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_manager = MongoDBConnectionManager(uri=mongo_uri, database="cherryquant_demo")

    try:
        await db_manager.connect()
    except:
        print("❌ 数据库连接失败，跳过示例")
        return

    collector = MockCollector()
    pipeline = DataPipeline(collector=collector, db_manager=db_manager)
    await pipeline.initialize()

    symbol = "test2501"
    exchange = Exchange.SHFE
    start_date = datetime.now() - timedelta(days=10)
    end_date = datetime.now()

    print(f"📊 第一次存储 {symbol} 数据...")

    result1 = await pipeline.collect_and_store_market_data(
        symbol=symbol, exchange=exchange, start_date=start_date, end_date=end_date, timeframe=TimeFrame.DAY_1
    )

    print(f"  存储: {result1['stored_count']} 条")

    print(f"\n📊 重复存储相同数据（测试去重）...")

    result2 = await pipeline.collect_and_store_market_data(
        symbol=symbol, exchange=exchange, start_date=start_date, end_date=end_date, timeframe=TimeFrame.DAY_1
    )

    print(f"  存储: {result2['stored_count']} 条")

    print(f"\n💡 观察: MongoDB的唯一索引自动处理了重复数据")
    print(f"   第二次存储应该是0条（数据已存在）")

    await pipeline.shutdown()
    print("\n✅ 示例3完成")


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("📚 CherryQuant 数据存储示例")
    print("=" * 70)

    try:
        await example_1_basic_storage()
        await example_2_batch_insert()
        await example_3_deduplication()

        print("\n" + "=" * 70)
        print("✅ 所有示例运行完成！")
        print("=" * 70)

        print("\n💡 数据库管理提示:")
        print("  - 查看数据: mongo cherryquant_demo")
        print("  - 清理数据: db.dropDatabase()")
        print("  - 查看索引: db.market_data_day_1.getIndexes()")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
