"""
数据管道协调器

整合采集、清洗、存储、查询的完整数据管道。

教学要点：
1. Facade 模式简化复杂系统
2. 依赖注入和组件协同
3. 端到端的数据处理流程
"""

import logging
from typing import Any
from datetime import datetime

from cherryquant.data.collectors.base_collector import (
    BaseCollector,
    MarketData,
    ContractInfo,
    TradingDay,
    Exchange,
    TimeFrame,
)
from cherryquant.data.cleaners.validator import DataValidator
from cherryquant.data.cleaners.normalizer import DataNormalizer
from cherryquant.data.cleaners.quality_control import QualityController
from cherryquant.data.storage.timeseries_repository import TimeSeriesRepository
from cherryquant.data.storage.metadata_repository import MetadataRepository
from cherryquant.data.storage.cache_strategy import CacheStrategy
from cherryquant.data.services.calendar_service import CalendarService
from cherryquant.data.services.contract_service import ContractService
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager

logger = logging.getLogger(__name__)


class DataPipeline:
    """
    数据管道协调器

    提供完整的数据处理流程：
    采集 → 验证 → 标准化 → 质量控制 → 存储 → 查询

    教学要点：
    1. Facade 模式的应用
    2. 依赖注入容器
    3. 组件生命周期管理
    """

    def __init__(
        self,
        collector: BaseCollector,
        db_manager: MongoDBConnectionManager,
        enable_cache: bool = True,
        enable_validation: bool = True,
        enable_quality_control: bool = True,
    ):
        """
        初始化数据管道

        Args:
            collector: 数据采集器
            db_manager: 数据库连接管理器
            enable_cache: 是否启用缓存
            enable_validation: 是否启用数据验证
            enable_quality_control: 是否启用质量控制

        教学要点：
        1. 构造函数注入
        2. 特性开关（Feature Toggle）
        """
        self.collector = collector
        self.db_manager = db_manager

        # 清洗组件
        self.validator = DataValidator() if enable_validation else None
        self.normalizer = DataNormalizer()
        self.quality_controller = (
            QualityController(validator=self.validator)
            if enable_quality_control
            else None
        )

        # 存储组件
        self.timeseries_repo = TimeSeriesRepository(db_manager)
        self.metadata_repo = MetadataRepository(db_manager, enable_cache=enable_cache)

        # 缓存组件
        self.cache = CacheStrategy() if enable_cache else None

        # 服务组件
        self.calendar_service = CalendarService(
            collector=collector,
            repository=self.metadata_repo,
            cache=self.cache,
        )
        self.contract_service = ContractService(
            collector=collector,
            repository=self.metadata_repo,
            validator=self.validator,
            cache=self.cache,
        )

        self._initialized = False

    async def initialize(self) -> None:
        """
        初始化数据管道

        教学要点：
        1. 异步初始化模式
        2. 资源预分配
        3. 健康检查
        """
        if self._initialized:
            logger.info("✅ 数据管道已初始化")
            return

        logger.info("🚀 初始化数据管道...")

        # 1. 连接数据库
        if not self.db_manager._is_connected:
            await self.db_manager.connect()

        # 2. 连接采集器
        if not self.collector.is_connected:
            await self.collector.connect()

        # 3. 创建索引
        for timeframe in [TimeFrame.MIN_1, TimeFrame.MIN_5, TimeFrame.DAY_1]:
            await self.timeseries_repo.ensure_indexes(timeframe)

        await self.metadata_repo.ensure_indexes()

        self._initialized = True
        logger.info("✅ 数据管道初始化完成")

    async def shutdown(self) -> None:
        """
        关闭数据管道

        教学要点：
        1. 优雅关闭
        2. 资源清理
        """
        logger.info("🛑 关闭数据管道...")

        # 断开采集器
        if self.collector.is_connected:
            await self.collector.disconnect()

        # 断开数据库
        if self.db_manager._is_connected:
            await self.db_manager.disconnect()

        # 清理缓存统计
        if self.cache:
            self.cache.print_stats()

        self._initialized = False
        logger.info("✅ 数据管道已关闭")

    # ==================== 市场数据管道 ====================

    async def collect_and_store_market_data(
        self,
        symbol: str,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
        timeframe: TimeFrame = TimeFrame.DAY_1,
        skip_validation: bool = False,
    ) -> dict[str, Any]:
        """
        采集并存储市场数据（完整流程）

        流程：采集 → 验证 → 标准化 → 质量控制 → 存储

        Args:
            symbol: 合约代码
            exchange: 交易所
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间周期
            skip_validation: 是否跳过验证

        Returns:
            Dict: 处理结果统计

        教学要点：
        1. 端到端数据处理
        2. 错误处理和降级
        3. 处理结果追踪
        """
        await self._ensure_initialized()

        logger.info(
            f"📊 开始数据采集: {symbol}.{exchange.value} "
            f"({start_date.date()} 到 {end_date.date()}, {timeframe.value})"
        )

        result = {
            "symbol": symbol,
            "exchange": exchange.value,
            "timeframe": timeframe.value,
            "collected_count": 0,
            "valid_count": 0,
            "stored_count": 0,
            "quality_score": 0.0,
            "errors": [],
        }

        try:
            # 1. 采集数据
            market_data = await self.collector.fetch_market_data(
                symbol=symbol,
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
            )

            result["collected_count"] = len(market_data)

            if not market_data:
                logger.warning("⚠️ 未采集到数据")
                return result

            # 2. 数据验证（可选）
            if self.validator and not skip_validation:
                valid_data, invalid_data, validation_result = (
                    self.validator.validate_market_data_batch(market_data)
                )

                result["valid_count"] = len(valid_data)

                if invalid_data:
                    logger.warning(
                        f"⚠️ 数据验证: {len(invalid_data)} 条无效数据"
                    )
                    result["errors"].append(
                        f"{len(invalid_data)} invalid records"
                    )

                market_data = valid_data

            # 3. 数据标准化
            market_data = self.normalizer.normalize_batch(
                market_data,
                deduplicate=True,
                fill_missing=False,  # 市场数据不填充缺失值
            )

            # 4. 质量控制（可选）
            if self.quality_controller:
                quality_metrics = self.quality_controller.assess_data_quality(
                    market_data
                )
                result["quality_score"] = quality_metrics.overall_score

                logger.info(f"📊 数据质量: {quality_metrics.quality_grade}")

            # 5. 存储数据
            stored_count = await self.timeseries_repo.save_batch(market_data)
            result["stored_count"] = stored_count

            logger.info(
                f"✅ 数据处理完成: 采集 {result['collected_count']}, "
                f"存储 {stored_count}"
            )

        except Exception as e:
            logger.error(f"❌ 数据处理失败: {e}")
            result["errors"].append(str(e))

        return result

    async def get_market_data(
        self,
        symbol: str,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
        timeframe: TimeFrame = TimeFrame.DAY_1,
        use_cache: bool = True,
    ) -> list[MarketData]:
        """
        获取市场数据（带缓存）

        教学要点：
        1. 缓存优先策略
        2. 查询优化
        """
        await self._ensure_initialized()

        # 生成缓存键
        cache_key = (
            f"market_data_{symbol}_{exchange.value}_"
            f"{start_date.date()}_{end_date.date()}_{timeframe.value}"
        )

        # 尝试从缓存获取
        if use_cache and self.cache:
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                logger.debug(f"📦 缓存命中: {symbol} {timeframe.value}")
                return cached_data

        # 从数据库查询
        market_data = await self.timeseries_repo.query(
            symbol=symbol,
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        # 写入缓存
        if use_cache and self.cache and market_data:
            await self.cache.set(cache_key, market_data)

        return market_data

    async def get_latest_data(
        self,
        symbol: str,
        exchange: Exchange,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> MarketData | None:
        """
        获取最新的一条数据

        教学要点：
        1. 单条查询优化
        2. 最新数据获取
        """
        await self._ensure_initialized()

        return await self.timeseries_repo.get_latest(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        )

    # ==================== 交易日历管道 ====================

    async def sync_trading_calendar(
        self,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        """
        同步交易日历（代理到 CalendarService）

        教学要点：
        1. 服务代理模式
        2. 统一接口
        """
        await self._ensure_initialized()

        return await self.calendar_service.sync_calendar(
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
        )

    async def is_trading_day(
        self,
        date: datetime,
        exchange: Exchange,
    ) -> bool:
        """判断是否为交易日"""
        await self._ensure_initialized()

        return await self.calendar_service.is_trading_day(date, exchange)

    async def get_next_trading_day(
        self,
        date: datetime,
        exchange: Exchange,
    ) -> datetime | None:
        """获取下一个交易日"""
        await self._ensure_initialized()

        return await self.calendar_service.get_next_trading_day(date, exchange)

    # ==================== 合约管理管道 ====================

    async def sync_contracts(
        self,
        exchange: Exchange | None = None,
    ) -> int:
        """
        同步合约信息（代理到 ContractService）
        """
        await self._ensure_initialized()

        return await self.contract_service.sync_contracts(exchange=exchange)

    async def get_contract(
        self,
        symbol: str,
        exchange: Exchange,
    ) -> ContractInfo | None:
        """获取合约信息"""
        await self._ensure_initialized()

        return await self.contract_service.get_contract(symbol, exchange)

    async def get_main_contract(
        self,
        underlying: str,
        exchange: Exchange,
    ) -> ContractInfo | None:
        """获取主力合约"""
        await self._ensure_initialized()

        return await self.contract_service.get_main_contract(underlying, exchange)

    # ==================== 批量操作 ====================

    async def batch_collect_and_store(
        self,
        requests: list[dict[str, Any]],
        concurrent_limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        批量采集和存储数据

        Args:
            requests: 请求列表，每个请求包含 {symbol, exchange, start_date, end_date, timeframe}
            concurrent_limit: 并发限制

        Returns:
            结果列表

        教学要点：
        1. 批量操作优化
        2. 并发控制
        3. 信号量（Semaphore）的使用
        """
        import asyncio

        await self._ensure_initialized()

        logger.info(f"📦 批量采集: {len(requests)} 个请求")

        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(concurrent_limit)

        async def process_one(request: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await self.collect_and_store_market_data(**request)

        # 并发执行
        results = await asyncio.gather(
            *[process_one(req) for req in requests],
            return_exceptions=True,
        )

        # 统计结果
        success_count = sum(
            1 for r in results
            if isinstance(r, dict) and r.get("stored_count", 0) > 0
        )

        logger.info(f"✅ 批量采集完成: {success_count}/{len(requests)} 成功")

        return results

    # ==================== 数据预热 ====================

    async def warm_up(
        self,
        symbols: list[str],
        exchange: Exchange,
        days_back: int = 30,
        timeframes: list[TimeFrame | None] = None,
    ) -> dict[str, int]:
        """
        数据预热

        预先加载常用数据到缓存，避免冷启动。

        Args:
            symbols: 合约代码列表
            exchange: 交易所
            days_back: 回溯天数
            timeframes: 时间周期列表

        Returns:
            预热结果统计

        教学要点：
        1. 缓存预热策略
        2. 系统启动优化
        """
        await self._ensure_initialized()

        if not self.cache:
            logger.warning("⚠️ 缓存未启用，跳过预热")
            return {}

        timeframes = timeframes or [TimeFrame.DAY_1]
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        logger.info(
            f"🔥 开始数据预热: {len(symbols)} 个合约, "
            f"{len(timeframes)} 个周期"
        )

        stats = {
            "total_requests": 0,
            "cache_filled": 0,
        }

        for symbol in symbols:
            for timeframe in timeframes:
                # 预加载数据
                data = await self.get_market_data(
                    symbol=symbol,
                    exchange=exchange,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=timeframe,
                    use_cache=True,
                )

                stats["total_requests"] += 1
                if data:
                    stats["cache_filled"] += 1

        logger.info(
            f"✅ 数据预热完成: {stats['cache_filled']}/{stats['total_requests']} "
            f"已缓存"
        )

        return stats

    # ==================== 辅助方法 ====================

    async def _ensure_initialized(self) -> None:
        """确保管道已初始化"""
        if not self._initialized:
            await self.initialize()

    def get_stats(self) -> dict[str, Any]:
        """
        获取管道统计信息

        教学要点：
        1. 系统监控指标
        2. 性能分析
        """
        stats = {
            "initialized": self._initialized,
            "collector": {
                "type": self.collector.__class__.__name__,
                "connected": self.collector.is_connected,
            },
            "database": {
                "connected": self.db_manager._is_connected,
            },
            "components": {
                "validator": self.validator is not None,
                "normalizer": True,
                "quality_controller": self.quality_controller is not None,
                "cache": self.cache is not None,
            },
        }

        # 缓存统计
        if self.cache:
            stats["cache"] = self.cache.get_stats()

        return stats

    def print_stats(self) -> None:
        """打印统计信息"""
        stats = self.get_stats()

        print("\n" + "=" * 60)
        print("数据管道统计信息")
        print("=" * 60)
        print(f"状态: {'已初始化' if stats['initialized'] else '未初始化'}")
        print(f"\n采集器:")
        print(f"  - 类型: {stats['collector']['type']}")
        print(f"  - 状态: {'已连接' if stats['collector']['connected'] else '未连接'}")
        print(f"\n数据库:")
        print(f"  - 状态: {'已连接' if stats['database']['connected'] else '未连接'}")
        print(f"\n组件:")
        for name, enabled in stats['components'].items():
            print(f"  - {name}: {'启用' if enabled else '禁用'}")

        if "cache" in stats:
            print(f"\n缓存统计:")
            cache_stats = stats["cache"]
            print(f"  - L1 命中率: {cache_stats['l1']['hit_rate']}")
            print(f"  - L2 命中率: {cache_stats['l2']['hit_rate']}")
            print(f"  - 总请求数: {cache_stats['total_requests']}")

        print("=" * 60 + "\n")

    def __repr__(self) -> str:
        """字符串表示"""
        return (
            f"<DataPipeline("
            f"collector={self.collector.__class__.__name__}, "
            f"initialized={self._initialized})>"
        )
