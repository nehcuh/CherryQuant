"""
交易日历服务

提供交易日历的完整管理功能，包括数据采集、验证、存储和查询。

教学要点：
1. 服务层的设计模式
2. 多组件协同工作
3. 业务逻辑封装
"""

import logging
from datetime import datetime, timedelta

from cherryquant.data.collectors.base_collector import (
    BaseCollector,
    TradingDay,
    Exchange,
)
from cherryquant.data.storage.metadata_repository import MetadataRepository
from cherryquant.data.storage.cache_strategy import CacheStrategy

logger = logging.getLogger(__name__)


class CalendarService:
    """
    交易日历服务

    整合数据采集、验证和存储，提供统一的交易日历管理接口。

    教学要点：
    1. Facade 模式简化复杂操作
    2. 依赖注入提高可测试性
    3. 缓存策略提升性能
    """

    def __init__(
        self,
        collector: BaseCollector,
        repository: MetadataRepository,
        cache: CacheStrategy | None = None,
    ):
        """
        初始化交易日历服务

        Args:
            collector: 数据采集器
            repository: 元数据仓储
            cache: 缓存策略（可选）

        教学要点：
        1. 构造函数注入
        2. 可选依赖处理
        """
        self.collector = collector
        self.repository = repository
        self.cache = cache

    async def sync_calendar(
        self,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
        force_refresh: bool = False,
    ) -> int:
        """
        同步交易日历数据

        从数据源获取并保存到数据库。

        Args:
            exchange: 交易所
            start_date: 开始日期
            end_date: 结束日期
            force_refresh: 是否强制刷新（清除缓存）

        Returns:
            同步的天数

        教学要点：
        1. 数据同步策略
        2. 增量 vs 全量更新
        3. 缓存失效处理
        """
        logger.info(
            f"📅 开始同步交易日历: {exchange.value} "
            f"({start_date.date()} 到 {end_date.date()})"
        )

        try:
            # 1. 从采集器获取数据
            if not self.collector.is_connected:
                await self.collector.connect()

            trading_days = await self.collector.fetch_trading_calendar(
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
            )

            if not trading_days:
                logger.warning("⚠️ 未获取到交易日历数据")
                return 0

            # 2. 保存到数据库
            saved_count = await self.repository.save_trading_days_batch(trading_days)

            # 3. 清除缓存
            if force_refresh and self.cache:
                pattern = f"calendar_{exchange.value}_*"
                await self.cache.clear(pattern)

            logger.info(
                f"✅ 交易日历同步完成: {saved_count}/{len(trading_days)} 天"
            )

            return saved_count

        except Exception as e:
            logger.error(f"❌ 交易日历同步失败: {e}")
            raise

    async def is_trading_day(
        self,
        date: datetime,
        exchange: Exchange,
    ) -> bool:
        """
        判断是否为交易日（带缓存）

        教学要点：
        1. 缓存优先策略
        2. 简单查询优化
        """
        # 生成缓存键
        cache_key = f"is_trading_{exchange.value}_{date.date()}"

        # 尝试从缓存获取
        if self.cache:
            cached_result = await self.cache.get(cache_key)
            if cached_result is not None:
                return cached_result

        # 从数据库查询
        result = await self.repository.is_trading_day(date, exchange)

        # 写入缓存
        if self.cache:
            await self.cache.set(cache_key, result)

        return result

    async def get_trading_days(
        self,
        start_date: datetime,
        end_date: datetime,
        exchange: Exchange,
    ) -> list[TradingDay]:
        """
        获取日期范围内的所有交易日

        教学要点：
        1. 批量查询优化
        2. 缓存键设计
        """
        # 缓存键
        cache_key = f"trading_days_{exchange.value}_{start_date.date()}_{end_date.date()}"

        # 尝试从缓存获取
        if self.cache:
            cached_days = await self.cache.get(cache_key)
            if cached_days:
                return cached_days

        # 从数据库查询
        trading_days = await self.repository.get_trading_days(
            start_date=start_date,
            end_date=end_date,
            exchange=exchange,
            only_trading_days=True,
        )

        # 写入缓存
        if self.cache:
            await self.cache.set(cache_key, trading_days)

        return trading_days

    async def get_next_trading_day(
        self,
        date: datetime,
        exchange: Exchange,
    ) -> datetime | None:
        """
        获取下一个交易日

        教学要点：
        1. 关联查询
        2. 边界情况处理
        """
        next_day = await self.repository.get_next_trading_day(date, exchange)

        if not next_day:
            logger.warning(f"⚠️ 未找到 {date.date()} 之后的交易日")

        return next_day

    async def get_prev_trading_day(
        self,
        date: datetime,
        exchange: Exchange,
    ) -> datetime | None:
        """获取上一个交易日"""
        prev_day = await self.repository.get_prev_trading_day(date, exchange)

        if not prev_day:
            logger.warning(f"⚠️ 未找到 {date.date()} 之前的交易日")

        return prev_day

    async def count_trading_days(
        self,
        start_date: datetime,
        end_date: datetime,
        exchange: Exchange,
    ) -> int:
        """
        统计日期范围内的交易日数量

        教学要点：
        1. 聚合查询
        2. 业务逻辑封装
        """
        trading_days = await self.get_trading_days(
            start_date, end_date, exchange
        )

        return len(trading_days)

    async def ensure_calendar_available(
        self,
        exchange: Exchange,
        months_ahead: int = 12,
        months_back: int = 12,
    ) -> bool:
        """
        确保交易日历数据可用

        如果缺失，自动从数据源同步。

        Args:
            exchange: 交易所
            months_ahead: 向前预载月数
            months_back: 向后预载月数

        Returns:
            是否成功

        教学要点：
        1. 自动初始化策略
        2. 数据预热
        """
        now = datetime.now()
        start_date = now - timedelta(days=30 * months_back)
        end_date = now + timedelta(days=30 * months_ahead)

        # 检查是否已有数据
        trading_days = await self.repository.get_trading_days(
            start_date=start_date,
            end_date=end_date,
            exchange=exchange,
        )

        # 计算应有的天数（粗略估计）
        expected_days = (end_date - start_date).days

        if len(trading_days) < expected_days * 0.5:  # 少于一半，可能数据不全
            logger.info(
                f"📅 交易日历数据不足，开始同步 "
                f"({len(trading_days)}/{expected_days} 天)"
            )

            try:
                await self.sync_calendar(
                    exchange=exchange,
                    start_date=start_date,
                    end_date=end_date,
                )
                return True

            except Exception as e:
                logger.error(f"❌ 交易日历同步失败: {e}")
                return False

        logger.info(f"✅ 交易日历数据充足: {len(trading_days)} 天")
        return True
