"""
元数据仓储

提供期货合约信息和交易日历的存储和查询功能。

教学要点：
1. 元数据管理的重要性
2. 缓存策略的应用
3. 复杂查询的实现
"""

import logging
from typing import Any
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from cherryquant.data.collectors.base_collector import (
    ContractInfo,
    TradingDay,
    Exchange,
)
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager
from cherryquant.data.utils import retry_async, RetryConfig, RetryStrategy

logger = logging.getLogger(__name__)


class MetadataRepository:
    """
    元数据仓储

    管理期货合约信息和交易日历数据。

    教学要点：
    1. 元数据与时间序列数据的分离
    2. 引用完整性维护
    3. 缓存层设计
    """

    # 集合名称
    CONTRACTS_COLLECTION = "futures_contracts"
    CALENDAR_COLLECTION = "trading_calendar"

    def __init__(
        self,
        connection_manager: MongoDBConnectionManager,
        enable_cache: bool = True,
    ):
        """
        初始化元数据仓储

        Args:
            connection_manager: MongoDB 连接管理器
            enable_cache: 是否启用缓存
        """
        self.connection_manager = connection_manager
        self.enable_cache = enable_cache

        # 内存缓存
        self._contract_cache: dict[str, ContractInfo] = {}
        self._calendar_cache: dict[str, list[TradingDay]] = {}
        self._indexes_created = False

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """获取数据库实例"""
        if not self.connection_manager._async_db:
            raise RuntimeError("数据库未连接")
        return self.connection_manager._async_db

    @property
    def contracts_collection(self) -> AsyncIOMotorCollection:
        """获取合约集合"""
        return self.database[self.CONTRACTS_COLLECTION]

    @property
    def calendar_collection(self) -> AsyncIOMotorCollection:
        """获取日历集合"""
        return self.database[self.CALENDAR_COLLECTION]

    async def ensure_indexes(self) -> None:
        """确保索引已创建"""
        if self._indexes_created:
            return

        # 合约集合索引
        contract_indexes = [
            IndexModel(
                [("symbol", ASCENDING), ("exchange", ASCENDING)],
                name="symbol_exchange",
                unique=True,
            ),
            IndexModel(
                [("underlying", ASCENDING), ("is_main_contract", ASCENDING)],
                name="underlying_main",
            ),
            IndexModel(
                [("expire_date", ASCENDING)],
                name="expire_date",
            ),
            IndexModel(
                [("is_active", ASCENDING)],
                name="is_active",
                sparse=True,
            ),
        ]

        # 日历集合索引
        calendar_indexes = [
            IndexModel(
                [("date", ASCENDING), ("exchange", ASCENDING)],
                name="date_exchange",
                unique=True,
            ),
            IndexModel(
                [("is_trading_day", ASCENDING), ("date", ASCENDING)],
                name="is_trading_day_date",
            ),
        ]

        try:
            await self.contracts_collection.create_indexes(contract_indexes)
            await self.calendar_collection.create_indexes(calendar_indexes)
            self._indexes_created = True
            logger.info("✅ 元数据索引创建成功")
        except Exception as e:
            logger.warning(f"⚠️ 索引创建失败: {e}")

    # ==================== 合约信息管理 ====================

    async def save_contract(self, contract: ContractInfo) -> bool:
        """
        保存合约信息

        教学要点：
        1. 唯一性约束处理
        2. 更新 vs 插入
        """
        await self.ensure_indexes()

        document = self._contract_to_document(contract)

        try:
            # 使用 update_one 实现 upsert
            result = await self.contracts_collection.update_one(
                {
                    "symbol": contract.symbol,
                    "exchange": contract.exchange.value,
                },
                {"$set": document},
                upsert=True,
            )

            # 更新缓存
            if self.enable_cache:
                cache_key = f"{contract.symbol}_{contract.exchange.value}"
                self._contract_cache[cache_key] = contract

            if result.upserted_id:
                logger.debug(f"✅ 插入合约: {contract.symbol}")
            else:
                logger.debug(f"✅ 更新合约: {contract.symbol}")

            return True

        except Exception as e:
            logger.error(f"❌ 保存合约失败: {e}")
            return False

    @retry_async(RetryConfig(max_attempts=2, base_delay=0.5))
    async def save_contracts_batch(self, contracts: list[ContractInfo]) -> int:
        """批量保存合约信息（自动重试）"""
        if not contracts:
            return 0

        success_count = 0
        for contract in contracts:
            if await self.save_contract(contract):
                success_count += 1

        logger.info(f"✅ 批量保存合约: {success_count}/{len(contracts)} 成功")
        return success_count

    def _contract_to_document(self, contract: ContractInfo) -> dict[str, Any]:
        """
        合约信息转文档

        注意: is_active 是一个计算属性(property)，不存储在数据库中。
        查询时需要基于 expire_date 在代码层过滤。
        """
        return {
            "symbol": contract.symbol,
            "name": contract.name,
            "exchange": contract.exchange.value,
            "underlying": contract.underlying,
            "multiplier": contract.multiplier,
            "price_tick": float(contract.price_tick),
            "list_date": contract.list_date,
            "expire_date": contract.expire_date,
            "delivery_month": contract.delivery_month,
            "margin_rate": float(contract.margin_rate) if contract.margin_rate else None,
            "is_main_contract": contract.is_main_contract,
            "updated_at": datetime.now(),
        }

    def _document_to_contract(self, doc: dict[str, Any]) -> ContractInfo:
        """文档转合约信息"""
        from decimal import Decimal

        return ContractInfo(
            symbol=doc["symbol"],
            name=doc["name"],
            exchange=Exchange[doc["exchange"]],
            underlying=doc["underlying"],
            multiplier=doc["multiplier"],
            price_tick=Decimal(str(doc["price_tick"])),
            list_date=doc["list_date"],
            expire_date=doc["expire_date"],
            delivery_month=doc["delivery_month"],
            margin_rate=Decimal(str(doc["margin_rate"])) if doc.get("margin_rate") else None,
            is_main_contract=doc.get("is_main_contract", False),
        )

    async def get_contract(
        self,
        symbol: str,
        exchange: Exchange,
    ) -> ContractInfo | None:
        """
        获取单个合约信息

        教学要点：
        1. 缓存优先策略
        2. 缓存穿透处理
        """
        # 检查缓存
        cache_key = f"{symbol}_{exchange.value}"
        if self.enable_cache and cache_key in self._contract_cache:
            logger.debug(f"📦 缓存命中: {symbol}")
            return self._contract_cache[cache_key]

        # 查询数据库
        document = await self.contracts_collection.find_one({
            "symbol": symbol,
            "exchange": exchange.value,
        })

        if document:
            contract = self._document_to_contract(document)

            # 更新缓存
            if self.enable_cache:
                self._contract_cache[cache_key] = contract

            return contract

        return None

    @retry_async(RetryConfig(max_attempts=2, base_delay=0.3))
    async def query_contracts(
        self,
        underlying: str | None = None,
        exchange: Exchange | None = None,
        is_active: bool | None = None,
        is_main_contract: bool | None = None,
    ) -> list[ContractInfo]:
        """
        查询合约信息

        Args:
            underlying: 标的代码（如 "rb"）
            exchange: 交易所
            is_active: 是否活跃（基于 expire_date 在代码层过滤）
            is_main_contract: 是否主力合约

        教学要点：
        1. 动态查询条件构建
        2. 可选过滤器模式
        3. 两阶段过滤：数据库层 + 代码层
        4. 自动重试机制（新增）
        """
        query = {}

        if underlying:
            query["underlying"] = underlying
        if exchange:
            query["exchange"] = exchange.value
        if is_main_contract is not None:
            query["is_main_contract"] = is_main_contract

        cursor = self.contracts_collection.find(query)
        documents = await cursor.to_list(length=None)

        contracts = [self._document_to_contract(doc) for doc in documents]

        # 在代码层过滤 is_active（因为它是计算属性）
        if is_active is not None:
            contracts = [c for c in contracts if c.is_active == is_active]

        logger.info(f"📊 查询合约: {len(contracts)} 个")
        return contracts

    async def get_main_contract(
        self,
        underlying: str,
        exchange: Exchange,
    ) -> ContractInfo | None:
        """
        获取主力合约

        教学要点：
        1. 业务规则封装
        2. 特定查询优化
        """
        contracts = await self.query_contracts(
            underlying=underlying,
            exchange=exchange,
            is_main_contract=True,
        )

        if contracts:
            return contracts[0]

        return None

    async def update_main_contract(
        self,
        old_symbol: str,
        new_symbol: str,
        exchange: Exchange,
    ) -> bool:
        """
        更新主力合约标记

        教学要点：
        1. 事务性更新
        2. 多文档原子操作
        """
        try:
            # 取消旧主力合约标记
            await self.contracts_collection.update_one(
                {
                    "symbol": old_symbol,
                    "exchange": exchange.value,
                },
                {"$set": {"is_main_contract": False}},
            )

            # 设置新主力合约
            await self.contracts_collection.update_one(
                {
                    "symbol": new_symbol,
                    "exchange": exchange.value,
                },
                {"$set": {"is_main_contract": True}},
            )

            # 清除缓存
            if self.enable_cache:
                self._contract_cache.clear()

            logger.info(f"✅ 主力合约切换: {old_symbol} → {new_symbol}")
            return True

        except Exception as e:
            logger.error(f"❌ 主力合约切换失败: {e}")
            return False

    # ==================== 交易日历管理 ====================

    async def save_trading_day(self, trading_day: TradingDay) -> bool:
        """保存交易日"""
        await self.ensure_indexes()

        document = self._trading_day_to_document(trading_day)

        try:
            await self.calendar_collection.update_one(
                {
                    "date": trading_day.date,
                    "exchange": trading_day.exchange.value,
                },
                {"$set": document},
                upsert=True,
            )

            logger.debug(
                f"✅ 保存交易日: {trading_day.date.date()} "
                f"({'交易日' if trading_day.is_trading else '休市'})"
            )
            return True

        except Exception as e:
            logger.error(f"❌ 保存交易日失败: {e}")
            return False

    async def save_trading_days_batch(self, trading_days: list[TradingDay]) -> int:
        """批量保存交易日"""
        if not trading_days:
            return 0

        success_count = 0
        for trading_day in trading_days:
            if await self.save_trading_day(trading_day):
                success_count += 1

        # 更新相邻交易日
        await self._update_adjacent_trading_days(trading_days)

        # 清除缓存
        if self.enable_cache:
            self._calendar_cache.clear()

        logger.info(f"✅ 批量保存交易日: {success_count}/{len(trading_days)} 成功")
        return success_count

    def _trading_day_to_document(self, trading_day: TradingDay) -> dict[str, Any]:
        """交易日转文档"""
        return {
            "date": trading_day.date,
            "exchange": trading_day.exchange.value,
            "is_trading_day": trading_day.is_trading,
            "pre_trading_date": trading_day.pre_trading_date,
            "next_trading_date": trading_day.next_trading_date,
        }

    def _document_to_trading_day(self, doc: dict[str, Any]) -> TradingDay:
        """文档转交易日"""
        return TradingDay(
            date=doc["date"],
            exchange=Exchange[doc["exchange"]],
            is_trading=doc["is_trading_day"],
            pre_trading_date=doc.get("pre_trading_date"),
            next_trading_date=doc.get("next_trading_date"),
        )

    async def is_trading_day(
        self,
        date: datetime,
        exchange: Exchange,
    ) -> bool:
        """
        判断是否为交易日

        教学要点：
        1. 简单查询优化
        2. 投影（只查询需要的字段）
        """
        # 检查缓存
        cache_key = f"{date.date()}_{exchange.value}"
        if self.enable_cache and cache_key in self._calendar_cache:
            cached_days = self._calendar_cache[cache_key]
            if cached_days:
                return cached_days[0].is_trading

        # 查询数据库（只返回 is_trading_day 字段）
        document = await self.calendar_collection.find_one(
            {
                "date": date,
                "exchange": exchange.value,
            },
            {"is_trading_day": 1},
        )

        if document:
            return document.get("is_trading_day", False)

        # 未找到记录，默认为非交易日
        logger.warning(
            f"⚠️ 未找到交易日历记录: {date.date()} {exchange.value}"
        )
        return False

    async def get_trading_days(
        self,
        start_date: datetime,
        end_date: datetime,
        exchange: Exchange,
        only_trading_days: bool = False,
    ) -> list[TradingDay]:
        """
        获取日期范围内的交易日历

        Args:
            start_date: 开始日期
            end_date: 结束日期
            exchange: 交易所
            only_trading_days: 是否只返回交易日

        教学要点：
        1. 范围查询
        2. 条件过滤
        """
        # 检查缓存
        cache_key = f"{start_date.date()}_{end_date.date()}_{exchange.value}_{only_trading_days}"
        if self.enable_cache and cache_key in self._calendar_cache:
            logger.debug(f"📦 缓存命中: 交易日历")
            return self._calendar_cache[cache_key]

        query = {
            "date": {"$gte": start_date, "$lte": end_date},
            "exchange": exchange.value,
        }

        if only_trading_days:
            query["is_trading_day"] = True

        cursor = self.calendar_collection.find(query).sort("date", ASCENDING)
        documents = await cursor.to_list(length=None)

        trading_days = [self._document_to_trading_day(doc) for doc in documents]

        # 更新缓存
        if self.enable_cache:
            self._calendar_cache[cache_key] = trading_days

        logger.info(
            f"📊 查询交易日历: {len(trading_days)} 天 "
            f"({start_date.date()} 到 {end_date.date()})"
        )

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
        2. 预计算字段的使用
        """
        document = await self.calendar_collection.find_one({
            "date": date,
            "exchange": exchange.value,
        })

        if document and document.get("next_trading_date"):
            return document["next_trading_date"]

        # 如果没有预计算的字段，则手动查找
        next_day = await self.calendar_collection.find_one(
            {
                "date": {"$gt": date},
                "exchange": exchange.value,
                "is_trading_day": True,
            },
            sort=[("date", ASCENDING)],
        )

        if next_day:
            return next_day["date"]

        return None

    async def get_prev_trading_day(
        self,
        date: datetime,
        exchange: Exchange,
    ) -> datetime | None:
        """获取上一个交易日"""
        document = await self.calendar_collection.find_one({
            "date": date,
            "exchange": exchange.value,
        })

        if document and document.get("pre_trading_date"):
            return document["pre_trading_date"]

        # 手动查找
        prev_day = await self.calendar_collection.find_one(
            {
                "date": {"$lt": date},
                "exchange": exchange.value,
                "is_trading_day": True,
            },
            sort=[("date", DESCENDING)],
        )

        if prev_day:
            return prev_day["date"]

        return None

    async def _update_adjacent_trading_days(
        self,
        trading_days: list[TradingDay],
    ) -> None:
        """
        更新相邻交易日信息

        教学要点：
        1. 批量更新优化
        2. 关联数据维护
        """
        # 提取所有交易日
        all_trading_dates = sorted([
            td.date for td in trading_days if td.is_trading
        ])

        if not all_trading_dates:
            return

        # 为每个交易日更新前后交易日
        for i, date in enumerate(all_trading_dates):
            prev_date = all_trading_dates[i - 1] if i > 0 else None
            next_date = all_trading_dates[i + 1] if i < len(all_trading_dates) - 1 else None

            # 找到对应的 TradingDay 对象
            for td in trading_days:
                if td.date == date:
                    await self.calendar_collection.update_one(
                        {
                            "date": date,
                            "exchange": td.exchange.value,
                        },
                        {
                            "$set": {
                                "pre_trading_date": prev_date,
                                "next_trading_date": next_date,
                            }
                        },
                    )
                    break

        logger.debug(f"✅ 更新相邻交易日: {len(all_trading_dates)} 天")

    async def clear_cache(self) -> None:
        """清除缓存"""
        self._contract_cache.clear()
        self._calendar_cache.clear()
        logger.info("🗑️ 元数据缓存已清除")
