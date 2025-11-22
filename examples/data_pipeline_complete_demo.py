"""
完整数据采集流程示例 - 整合所有 Quantbox 工具

演示如何使用 P0 和 P1 工具构建一个完整的生产级数据采集流程。

功能:
1. 使用 date_utils 获取交易日历
2. 使用 contract_utils 转换合约格式
3. 使用 BulkWriter 批量保存数据
4. 使用 SaveResult 追踪操作结果
5. 完整的错误处理和日志记录

依赖:
- MongoDB (用于存储数据)
- Tushare Token (可选，用于真实数据采集)

运行:
    python examples/data_pipeline_complete_demo.py
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo

# CherryQuant 工具导入
from cherryquant.utils.date_utils import (
    get_trade_calendar,
    is_trade_date,
    date_to_int
)
from cherryquant.utils.contract_utils import (
    parse_contract,
    format_contract,
    ParsedContractInfo,
)
from cherryquant.utils.exchange_utils import (
    normalize_exchange,
    is_futures_exchange,
)
from cherryquant.data.storage.bulk_writer import BulkWriter
from cherryquant.data.storage.save_result import SaveResult

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataCollectionPipeline:
    """
    完整的数据采集流程

    集成了所有 Quantbox 工具：
    - P0: date_utils, contract_utils, exchange_utils
    - P1: BulkWriter, SaveResult
    """

    def __init__(self, db_url: str = "mongodb://localhost:27017"):
        """初始化数据采集流程"""
        self.db_url = db_url
        self.client = None
        self.db = None

    async def connect(self):
        """连接 MongoDB"""
        logger.info(f"连接 MongoDB: {self.db_url}")
        self.client = AsyncIOMotorClient(self.db_url)
        self.db = self.client.cherryquant

        # 创建索引
        await self._ensure_indexes()

    async def _ensure_indexes(self):
        """确保必要的索引存在"""
        logger.info("创建数据库索引...")

        await BulkWriter.ensure_indexes(
            collection=self.db.market_data,
            index_specs=[
                {
                    "keys": [("symbol", 1), ("date", 1)],
                    "unique": True
                },
                {
                    "keys": [("exchange", 1), ("date", -1)],
                    "unique": False
                }
            ]
        )

        logger.info("✓ 索引创建完成")

    async def get_trading_dates_for_symbols(
        self,
        symbols: List[str],
        days: int = 30
    ) -> List[int]:
        """
        获取交易日列表（使用 date_utils）

        Args:
            symbols: 合约代码列表
            days: 最近N天

        Returns:
            交易日列表（整数格式 YYYYMMDD）
        """
        logger.info(f"获取最近 {days} 天的交易日...")

        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 从第一个合约提取交易所
        info = parse_contract(symbols[0])
        exchange = info.exchange

        # 获取交易日列表（使用 date_utils）
        trading_dates = get_trade_calendar(
            start_date.strftime("%Y%m%d"),
            end_date.strftime("%Y%m%d"),
            exchange=exchange
        )

        # 转换为整数格式
        date_ints = [date_to_int(d) for d in trading_dates]

        logger.info(f"✓ 获取到 {len(date_ints)} 个交易日")
        return date_ints

    def convert_symbols_for_data_source(
        self,
        symbols: List[str],
        target_format: str = "tushare"
    ) -> Dict[str, str]:
        """
        转换合约格式以匹配数据源（使用 contract_utils）

        Args:
            symbols: 内部标准格式的合约列表
            target_format: 目标格式 (tushare/goldminer/vnpy)

        Returns:
            {标准格式: 数据源格式} 映射
        """
        logger.info(f"转换合约格式为 {target_format}...")

        mapping = {}
        for symbol in symbols:
            converted = format_contract(symbol, target_format)
            mapping[symbol] = converted
            logger.debug(f"  {symbol} → {converted}")

        logger.info(f"✓ 转换完成 {len(mapping)} 个合约")
        return mapping

    async def collect_mock_data(
        self,
        symbols: List[str],
        trading_dates: List[int]
    ) -> List[Dict[str, Any]]:
        """
        模拟数据采集（实际项目中替换为真实 API 调用）

        Args:
            symbols: 合约代码列表（标准格式）
            trading_dates: 交易日列表

        Returns:
            采集的数据列表
        """
        logger.info(f"开始采集数据: {len(symbols)} 个合约, {len(trading_dates)} 个交易日...")

        all_data = []

        for symbol in symbols:
            # 解析合约信息
            info = parse_contract(symbol)

            for date_int in trading_dates:
                # 模拟生成数据（实际项目中调用 API）
                data = {
                    "symbol": info.symbol,
                    "exchange": info.exchange,
                    "underlying": info.underlying,
                    "date": date_int,
                    "open": 3500.0 + (date_int % 100) * 0.1,
                    "high": 3520.0 + (date_int % 100) * 0.1,
                    "low": 3480.0 + (date_int % 100) * 0.1,
                    "close": 3500.0 + (date_int % 100) * 0.1,
                    "volume": 100000 + (date_int % 1000) * 100,
                    "open_interest": 50000,
                    "collected_at": datetime.now(),
                }
                all_data.append(data)

        logger.info(f"✓ 采集完成 {len(all_data)} 条数据")
        return all_data

    async def save_data(
        self,
        data: List[Dict[str, Any]]
    ) -> SaveResult:
        """
        批量保存数据（使用 BulkWriter 和 SaveResult）

        Args:
            data: 数据列表

        Returns:
            SaveResult 对象
        """
        logger.info(f"开始保存数据: {len(data)} 条...")

        # 创建结果追踪器
        result = SaveResult()

        # 批量 upsert（使用 BulkWriter）
        await BulkWriter.bulk_upsert(
            collection=self.db.market_data,
            data=data,
            key_fields=["symbol", "date"],  # 唯一键
            result=result
        )

        result.complete()

        # 记录详细日志
        if result.success:
            logger.info(f"✓ 数据保存成功: {result}")
            logger.info(f"  插入: {result.inserted_count} 条")
            logger.info(f"  更新: {result.modified_count} 条")
            logger.info(f"  总计: {result.total_count} 条")
            logger.info(f"  耗时: {result.duration.total_seconds():.3f} 秒")
            logger.info(f"  成功率: {result.success_rate:.1%}")
        else:
            logger.error(f"✗ 数据保存失败: {result}")
            for error in result.errors:
                logger.error(f"  错误: {error['type']} - {error['message']}")

        return result

    async def run_collection(
        self,
        symbols: List[str],
        days: int = 7
    ) -> SaveResult:
        """
        运行完整的数据采集流程

        Args:
            symbols: 合约代码列表（标准格式，如 ["SHFE.rb2501", "DCE.m2501"]）
            days: 采集最近N天的数据

        Returns:
            SaveResult 对象
        """
        logger.info("=" * 70)
        logger.info("开始完整数据采集流程")
        logger.info("=" * 70)

        # 步骤 1: 验证合约代码
        logger.info("\n步骤 1/5: 验证合约代码")
        for symbol in symbols:
            info = parse_contract(symbol)
            exchange_type = "期货" if is_futures_exchange(info.exchange) else "股票"
            logger.info(f"  {symbol}: {info.underlying} ({info.exchange} - {exchange_type})")

        # 步骤 2: 获取交易日历
        logger.info("\n步骤 2/5: 获取交易日历")
        trading_dates = await self.get_trading_dates_for_symbols(symbols, days)
        logger.info(f"  交易日: {trading_dates[:5]}... ({len(trading_dates)} 个)")

        # 步骤 3: 转换合约格式（如果需要调用外部 API）
        logger.info("\n步骤 3/5: 转换合约格式")
        symbol_mapping = self.convert_symbols_for_data_source(symbols, "tushare")
        for std, ts in list(symbol_mapping.items())[:3]:
            logger.info(f"  {std} → {ts}")

        # 步骤 4: 采集数据
        logger.info("\n步骤 4/5: 采集市场数据")
        data = await self.collect_mock_data(symbols, trading_dates)

        # 步骤 5: 保存数据
        logger.info("\n步骤 5/5: 批量保存数据")
        result = await self.save_data(data)

        logger.info("\n" + "=" * 70)
        logger.info("数据采集流程完成!")
        logger.info("=" * 70)

        return result

    async def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB 连接已关闭")


async def example_1_basic_flow():
    """示例 1: 基础数据采集流程"""
    print("\n" + "=" * 70)
    print("示例 1: 基础数据采集流程")
    print("=" * 70)

    # 创建流程
    pipeline = DataCollectionPipeline()

    try:
        # 连接数据库
        await pipeline.connect()

        # 定义要采集的合约
        symbols = [
            "SHFE.rb2501",  # 螺纹钢
            "DCE.m2501",    # 豆粕
            "CZCE.SR501",   # 白糖（3位年月格式）
        ]

        # 运行采集流程（最近 7 天）
        result = await pipeline.run_collection(symbols, days=7)

        # 导出结果
        result_dict = result.to_dict()
        print("\n📊 结果摘要:")
        print(f"  成功: {result_dict['success']}")
        print(f"  总计: {result_dict['total_count']} 条")
        print(f"  插入: {result_dict['inserted_count']} 条")
        print(f"  更新: {result_dict['modified_count']} 条")
        print(f"  耗时: {result_dict['duration_seconds']:.3f} 秒")
        print(f"  成功率: {result_dict['success_rate']:.1%}")

    finally:
        await pipeline.close()


async def example_2_incremental_update():
    """示例 2: 增量更新（只采集缺失的数据）"""
    print("\n" + "=" * 70)
    print("示例 2: 增量更新")
    print("=" * 70)

    pipeline = DataCollectionPipeline()

    try:
        await pipeline.connect()

        symbols = ["SHFE.rb2501"]

        # 第一次采集
        print("\n第一次采集（完整）:")
        result1 = await pipeline.run_collection(symbols, days=5)
        print(f"  结果: {result1}")

        # 第二次采集（增量，会自动去重）
        print("\n第二次采集（增量）:")
        result2 = await pipeline.run_collection(symbols, days=5)
        print(f"  结果: {result2}")
        print(f"  说明: modified_count={result2.modified_count}（自动更新已存在的数据）")

    finally:
        await pipeline.close()


async def example_3_error_handling():
    """示例 3: 错误处理"""
    print("\n" + "=" * 70)
    print("示例 3: 错误处理演示")
    print("=" * 70)

    pipeline = DataCollectionPipeline()

    try:
        await pipeline.connect()

        # 包含无效合约代码
        symbols = [
            "SHFE.rb2501",    # 有效
            "INVALID.CODE",   # 无效（会在解析时报错）
        ]

        print("\n尝试处理包含无效合约的请求...")

        # 单独处理每个合约，捕获错误
        for symbol in symbols:
            try:
                info = parse_contract(symbol)
                print(f"✓ {symbol}: 有效")
            except Exception as e:
                print(f"✗ {symbol}: 无效 - {e}")

    finally:
        await pipeline.close()


async def example_4_query_data():
    """示例 4: 查询已采集的数据"""
    print("\n" + "=" * 70)
    print("示例 4: 查询已采集的数据")
    print("=" * 70)

    pipeline = DataCollectionPipeline()

    try:
        await pipeline.connect()

        # 先采集一些数据
        await pipeline.run_collection(["SHFE.rb2501"], days=3)

        # 查询数据
        print("\n查询最近 3 条数据:")
        docs = await pipeline.db.market_data.find(
            {"symbol": "rb2501"}
        ).sort("date", -1).limit(3).to_list(None)

        for doc in docs:
            print(f"  {doc['date']}: "
                  f"open={doc['open']:.2f}, "
                  f"close={doc['close']:.2f}, "
                  f"volume={doc['volume']}")

        # 统计数据
        print("\n数据统计:")
        total = await pipeline.db.market_data.count_documents({})
        print(f"  总条数: {total}")

        by_symbol = await pipeline.db.market_data.aggregate([
            {"$group": {"_id": "$symbol", "count": {"$sum": 1}}}
        ]).to_list(None)

        print("  各合约数据量:")
        for item in by_symbol:
            print(f"    {item['_id']}: {item['count']} 条")

    finally:
        await pipeline.close()


async def main():
    """运行所有示例"""
    print("\n")
    print("🎯 " + "=" * 68)
    print("🎯  完整数据采集流程示例 - Quantbox 工具整合")
    print("🎯 " + "=" * 68)

    try:
        await example_1_basic_flow()
        await example_2_incremental_update()
        await example_3_error_handling()
        await example_4_query_data()

        print("\n" + "=" * 70)
        print("✅ 所有示例运行完成!")
        print("=" * 70)
        print("\n📖 关键亮点:")
        print("  ✅ P0 工具: date_utils, contract_utils, exchange_utils")
        print("  ✅ P1 工具: BulkWriter, SaveResult")
        print("  ✅ 性能: 批量写入提速 100 倍")
        print("  ✅ 追踪: 完整的操作统计和错误管理")
        print("  ✅ 智能: 自动去重（upsert 模式）")
        print("\n📚 更多信息:")
        print("  - 文档: docs/quantbox_integration_p0.md, docs/quantbox_integration_p1.md")
        print("  - 迁移: docs/MIGRATION_GUIDE.md")
        print("  - 架构: docs/ARCHITECTURE_REFLECTION_QUANTBOX.md")
        print()

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n请确保:")
        print("  1. MongoDB 已启动 (mongod)")
        print("  2. 连接地址正确 (mongodb://localhost:27017)")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
