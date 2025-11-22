"""
时间序列数据仓储

提供 MongoDB 时间序列数据的存储和查询功能。

教学要点：
1. Repository 模式的应用
2. 异步数据库操作
3. 批量操作优化
4. 索引和查询优化
"""

import logging
from typing import Any
from datetime import datetime
from decimal import Decimal

from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import BulkWriteError

from cherryquant.data.collectors.base_collector import MarketData, Exchange, TimeFrame
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager
from cherryquant.data.utils import retry_async, RetryConfig, RetryStrategy

logger = logging.getLogger(__name__)


class TimeSeriesRepository:
    """
    时间序列数据仓储

    负责市场数据（OHLCV）的持久化存储和查询。
    使用 MongoDB 时间序列集合优化存储和查询性能。

    教学要点：
    1. Repository 模式隔离数据访问逻辑
    2. 时间序列数据的特殊处理
    3. 批量操作提升性能
    4. 索引优化查询效率
    """

    # 集合名称映射
    COLLECTION_NAMES = {
        TimeFrame.MIN_1: "market_data_1m",
        TimeFrame.MIN_5: "market_data_5m",
        TimeFrame.MIN_15: "market_data_15m",
        TimeFrame.MIN_30: "market_data_30m",
        TimeFrame.HOUR_1: "market_data_1h",
        TimeFrame.DAY_1: "market_data_1d",
    }

    def __init__(
        self,
        connection_manager: MongoDBConnectionManager,
        enable_auto_index: bool = True,
    ):
        """
        初始化时间序列仓储

        Args:
            connection_manager: MongoDB 连接管理器
            enable_auto_index: 是否自动创建索引

        教学要点：
        1. 依赖注入模式
        2. 配置参数化
        """
        self.connection_manager = connection_manager
        self.enable_auto_index = enable_auto_index

        # 集合缓存
        self._collections: dict[str, AsyncIOMotorCollection] = {}
        self._indexes_created = set()

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """获取数据库实例"""
        if not self.connection_manager._async_db:
            raise RuntimeError("数据库未连接，请先调用 connection_manager.connect()")
        return self.connection_manager._async_db

    def _get_collection(self, timeframe: TimeFrame) -> AsyncIOMotorCollection:
        """
        获取指定时间周期的集合

        教学要点：
        1. 集合分离策略（按时间周期）
        2. 集合缓存优化
        """
        collection_name = self.COLLECTION_NAMES.get(timeframe)
        if not collection_name:
            raise ValueError(f"不支持的时间周期: {timeframe}")

        # 从缓存获取
        if collection_name not in self._collections:
            self._collections[collection_name] = self.database[collection_name]

        return self._collections[collection_name]

    async def ensure_indexes(self, timeframe: TimeFrame) -> None:
        """
        确保索引已创建

        教学要点：
        1. 索引对查询性能的影响
        2. 复合索引的设计
        3. 索引创建的幂等性
        """
        collection_name = self.COLLECTION_NAMES.get(timeframe)
        if not collection_name or collection_name in self._indexes_created:
            return

        collection = self._get_collection(timeframe)

        # 定义索引
        indexes = [
            IndexModel(
                [
                    ("metadata.symbol", ASCENDING),
                    ("metadata.exchange", ASCENDING),
                    ("datetime", ASCENDING),
                ],
                name="symbol_exchange_datetime",
            ),
            IndexModel(
                [("datetime", ASCENDING)],
                name="datetime",
            ),
            IndexModel(
                [
                    ("metadata.underlying", ASCENDING),
                    ("datetime", ASCENDING),
                ],
                name="underlying_datetime",
            ),
        ]

        try:
            await collection.create_indexes(indexes)
            self._indexes_created.add(collection_name)
            logger.info(f"✅ 索引创建成功: {collection_name}")
        except Exception as e:
            logger.warning(f"⚠️ 索引创建失败: {e}")

    async def save(self, data: MarketData) -> bool:
        """
        保存单条市场数据

        Args:
            data: 市场数据

        Returns:
            bool: 是否保存成功

        教学要点：
        1. 单条插入 vs 批量插入
        2. 数据转换（MarketData → MongoDB 文档）
        3. 错误处理
        """
        return await self.save_batch([data]) > 0

    @retry_async(RetryConfig(
        max_attempts=2,
        base_delay=0.5,
        strategy=RetryStrategy.EXPONENTIAL,
        non_retriable_exceptions=(
            ValueError,
            TypeError,
            BulkWriteError,  # 批量写入错误（如重复数据）不重试
        ),
    ))
    async def save_batch(
        self,
        data_list: list[MarketData],
        ordered: bool = False,
    ) -> int:
        """
        批量保存市场数据

        Args:
            data_list: 数据列表
            ordered: 是否有序插入（True: 遇到错误停止，False: 跳过错误继续）

        Returns:
            int: 成功保存的数据量

        教学要点：
        1. 批量操作的性能优势
        2. 有序 vs 无序插入的权衡
        3. 部分失败的处理
        4. 自动重试机制 (新增) - 网络问题自动重试
        """
        if not data_list:
            return 0

        # 按时间周期分组
        grouped_data: dict[TimeFrame, list[MarketData]] = {}
        for data in data_list:
            if data.timeframe not in grouped_data:
                grouped_data[data.timeframe] = []
            grouped_data[data.timeframe].append(data)

        total_inserted = 0

        # 分组插入
        for timeframe, group_data in grouped_data.items():
            try:
                collection = self._get_collection(timeframe)

                # 确保索引存在
                if self.enable_auto_index:
                    await self.ensure_indexes(timeframe)

                # 转换为文档
                documents = [self._to_document(data) for data in group_data]

                # 批量插入
                result = await collection.insert_many(
                    documents,
                    ordered=ordered,
                )

                inserted_count = len(result.inserted_ids)
                total_inserted += inserted_count

                logger.info(
                    f"✅ 批量保存成功: {inserted_count}/{len(group_data)} 条 "
                    f"{timeframe.value} 数据"
                )

            except BulkWriteError as e:
                # 处理批量写入错误（如重复数据）
                inserted_count = e.details.get("nInserted", 0)
                total_inserted += inserted_count

                logger.warning(
                    f"⚠️ 批量保存部分失败: {inserted_count}/{len(group_data)} 条成功, "
                    f"{len(e.details.get('writeErrors', []))} 条失败"
                )

            except Exception as e:
                logger.error(f"❌ 批量保存失败: {e}")

        return total_inserted

    def _to_document(self, data: MarketData) -> dict[str, Any]:
        """
        将 MarketData 转换为 MongoDB 文档

        教学要点：
        1. 数据转换的封装
        2. MongoDB 文档结构设计
        3. 数据类型映射（Decimal → float）
        """
        return {
            "datetime": data.datetime,
            "metadata": {
                "symbol": data.symbol,
                "exchange": data.exchange.value,
                # 提取标的代码：去除合约代码末尾的数字
                "underlying": data.symbol.rstrip("0123456789") if data.symbol else "",
            },
            "open": float(data.open),
            "high": float(data.high),
            "low": float(data.low),
            "close": float(data.close),
            "volume": data.volume,
            "open_interest": data.open_interest,
            "turnover": float(data.turnover) if data.turnover else None,
            "source": data.source.value,
            "collected_at": data.collected_at or datetime.now(),
        }

    def _from_document(self, doc: dict[str, Any], timeframe: TimeFrame) -> MarketData:
        """
        从 MongoDB 文档转换为 MarketData

        教学要点：
        1. 反向转换
        2. 枚举类型的重建
        3. 可选字段的处理
        """
        from cherryquant.data.collectors.base_collector import DataSource

        metadata = doc.get("metadata", {})

        return MarketData(
            symbol=metadata.get("symbol"),
            exchange=Exchange(metadata.get("exchange")),  # Lookup by value
            datetime=doc.get("datetime"),
            timeframe=timeframe,
            open=Decimal(str(doc.get("open"))),
            high=Decimal(str(doc.get("high"))),
            low=Decimal(str(doc.get("low"))),
            close=Decimal(str(doc.get("close"))),
            volume=doc.get("volume"),
            open_interest=doc.get("open_interest"),
            turnover=Decimal(str(doc.get("turnover"))) if doc.get("turnover") else None,
            source=DataSource(doc.get("source", "custom")),  # Lookup by value, not name
            collected_at=doc.get("collected_at"),
        )

    @retry_async(RetryConfig(
        max_attempts=2,
        base_delay=0.3,
        strategy=RetryStrategy.EXPONENTIAL,
    ))
    async def query(
        self,
        symbol: str,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
        timeframe: TimeFrame = TimeFrame.DAY_1,
        limit: int | None = None,
    ) -> list[MarketData]:
        """
        查询市场数据

        Args:
            symbol: 合约代码
            exchange: 交易所
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间周期
            limit: 最大返回数量

        Returns:
            list[MarketData]: 市场数据列表

        教学要点：
        1. 查询条件构建
        2. 索引利用
        3. 结果集限制
        4. 排序策略
        5. 自动重试机制 (新增) - 查询失败自动重试
        """
        collection = self._get_collection(timeframe)

        # 构建查询条件
        query = {
            "metadata.symbol": symbol,
            "metadata.exchange": exchange.value,
            "datetime": {
                "$gte": start_date,
                "$lte": end_date,
            },
        }

        # 执行查询
        cursor = collection.find(query).sort("datetime", ASCENDING)

        if limit:
            cursor = cursor.limit(limit)

        # 转换结果
        documents = await cursor.to_list(length=None)
        result = [self._from_document(doc, timeframe) for doc in documents]

        logger.info(
            f"📊 查询完成: {len(result)} 条 {symbol}.{exchange.value} "
            f"{timeframe.value} 数据"
        )

        return result

    async def query_by_underlying(
        self,
        underlying: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: TimeFrame = TimeFrame.DAY_1,
        exchange: Exchange | None = None,
    ) -> list[MarketData]:
        """
        按标的代码查询（如查询所有 rb 合约）

        教学要点：
        1. 通配符查询
        2. 可选过滤条件
        """
        collection = self._get_collection(timeframe)

        query = {
            "metadata.underlying": underlying,
            "datetime": {
                "$gte": start_date,
                "$lte": end_date,
            },
        }

        if exchange:
            query["metadata.exchange"] = exchange.value

        cursor = collection.find(query).sort("datetime", ASCENDING)
        documents = await cursor.to_list(length=None)

        result = [self._from_document(doc, timeframe) for doc in documents]

        logger.info(
            f"📊 查询完成: {len(result)} 条 {underlying} "
            f"{timeframe.value} 数据"
        )

        return result

    async def get_latest(
        self,
        symbol: str,
        exchange: Exchange,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> MarketData | None:
        """
        获取最新的一条数据

        教学要点：
        1. 排序和限制的组合
        2. 单文档查询
        """
        collection = self._get_collection(timeframe)

        query = {
            "metadata.symbol": symbol,
            "metadata.exchange": exchange.value,
        }

        document = await collection.find_one(
            query,
            sort=[("datetime", DESCENDING)],
        )

        if document:
            return self._from_document(document, timeframe)

        return None

    async def count(
        self,
        symbol: str,
        exchange: Exchange,
        timeframe: TimeFrame = TimeFrame.DAY_1,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        """
        统计数据量

        教学要点：
        1. count 操作的优化
        2. 可选日期范围
        """
        collection = self._get_collection(timeframe)

        query = {
            "metadata.symbol": symbol,
            "metadata.exchange": exchange.value,
        }

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            query["datetime"] = date_filter

        count = await collection.count_documents(query)

        logger.debug(
            f"📊 数据统计: {symbol}.{exchange.value} {timeframe.value} "
            f"共 {count} 条"
        )

        return count

    async def delete_range(
        self,
        symbol: str,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> int:
        """
        删除指定日期范围的数据

        教学要点：
        1. 批量删除操作
        2. 删除条件的精确控制
        """
        collection = self._get_collection(timeframe)

        query = {
            "metadata.symbol": symbol,
            "metadata.exchange": exchange.value,
            "datetime": {
                "$gte": start_date,
                "$lte": end_date,
            },
        }

        result = await collection.delete_many(query)
        deleted_count = result.deleted_count

        logger.info(
            f"🗑️ 删除数据: {deleted_count} 条 {symbol}.{exchange.value} "
            f"{timeframe.value} 数据"
        )

        return deleted_count

    async def get_date_range(
        self,
        symbol: str,
        exchange: Exchange,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> tuple[datetime, datetime | None]:
        """
        获取数据的日期范围

        Returns:
            tuple: (最早日期, 最晚日期) 或 None

        教学要点：
        1. 聚合查询
        2. min/max 操作
        """
        collection = self._get_collection(timeframe)

        query = {
            "metadata.symbol": symbol,
            "metadata.exchange": exchange.value,
        }

        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": None,
                    "min_date": {"$min": "$datetime"},
                    "max_date": {"$max": "$datetime"},
                }
            },
        ]

        result = await collection.aggregate(pipeline).to_list(length=1)

        if result:
            return (result[0]["min_date"], result[0]["max_date"])

        return None

    async def upsert(self, data: MarketData) -> bool:
        """
        更新或插入数据（如果存在则更新，不存在则插入）

        教学要点：
        1. upsert 操作
        2. 唯一性约束
        """
        collection = self._get_collection(data.timeframe)

        # 构建查询条件（唯一标识）
        filter_query = {
            "metadata.symbol": data.symbol,
            "metadata.exchange": data.exchange.value,
            "datetime": data.datetime,
        }

        # 转换为文档
        document = self._to_document(data)

        # 执行 upsert
        result = await collection.replace_one(
            filter_query,
            document,
            upsert=True,
        )

        if result.upserted_id:
            logger.debug(f"✅ 插入新数据: {data.symbol} @ {data.datetime}")
        elif result.modified_count > 0:
            logger.debug(f"✅ 更新数据: {data.symbol} @ {data.datetime}")

        return True
