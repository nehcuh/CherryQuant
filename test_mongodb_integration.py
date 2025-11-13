#!/usr/bin/env python3
"""
测试 MongoDB 集成功能
"""
import asyncio
import logging
from datetime import datetime
from cherryquant.adapters.data_storage.database_manager import get_database_manager
from cherryquant.adapters.data_storage.timeframe_data_manager import TimeFrame, MarketDataPoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mongodb_integration():
    """测试 MongoDB 数据读写"""
    logger.info("=" * 60)
    logger.info("开始测试 MongoDB 集成...")
    logger.info("=" * 60)

    try:
        # 1. 连接数据库
        logger.info("\n[1/5] 测试数据库连接...")
        db_manager = await get_database_manager()
        logger.info("✅ 数据库连接成功")

        # 2. 测试写入数据
        logger.info("\n[2/5] 测试写入市场数据...")
        test_data = [
            MarketDataPoint(
                timestamp=datetime.now(),
                open=3500.0,
                high=3520.0,
                low=3490.0,
                close=3510.0,
                volume=12345,
                open_interest=5000
            )
        ]

        await db_manager.store_market_data(
            symbol="rb2501",
            exchange="SHFE",
            timeframe=TimeFrame.FIVE_MIN,
            data_points=test_data
        )
        logger.info("✅ 数据写入成功")

        # 3. 测试读取数据
        logger.info("\n[3/5] 测试读取市场数据...")
        data = await db_manager.get_market_data(
            symbol="rb2501",
            exchange="SHFE",
            timeframe=TimeFrame.FIVE_MIN,
            limit=10
        )
        logger.info(f"✅ 读取到 {len(data)} 条数据")
        if data:
            latest = data[-1]
            logger.info(f"   最新价格: {latest.close}, 时间: {latest.timestamp}")

        # 4. 测试统计信息
        logger.info("\n[4/5] 测试数据库统计...")
        stats = await db_manager.mongodb_manager.get_stats()
        logger.info(f"✅ 数据库大小: {stats.get('dataSize', 0) / 1024 / 1024:.2f} MB")
        logger.info(f"   集合数量: {stats.get('collections', 0)}")

        # 5. 测试集合列表
        logger.info("\n[5/5] 测试集合列表...")
        collections = await db_manager.mongodb_manager.list_collections()
        logger.info(f"✅ 找到 {len(collections)} 个集合:")
        for col in collections[:10]:  # 显示前10个
            logger.info(f"   - {col}")

        # 关闭连接
        await db_manager.close()
        logger.info("\n✅ 数据库连接已关闭")

        logger.info("\n" + "=" * 60)
        logger.info("✅ MongoDB 集成测试全部通过！")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mongodb_integration())
    exit(0 if success else 1)
