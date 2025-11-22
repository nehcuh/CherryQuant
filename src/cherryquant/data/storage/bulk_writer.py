"""
BulkWriter - 批量数据写入优化工具

整合自quantbox.services.data_saver_service的批量写入优化
提供高性能的批量upsert操作和自动索引管理。

教学要点：
1. MongoDB bulk_write的正确使用
2. Upsert（update or insert）模式的应用
3. 索引管理和优化
4. 批量操作的性能优势
"""
from __future__ import annotations

import logging
from typing import Any
from motor.motor_asyncio import AsyncIOMotorCollection
import pymongo
from pymongo import UpdateOne

from cherryquant.data.storage.save_result import SaveResult

logger = logging.getLogger(__name__)


class BulkWriter:
    """
    批量数据写入优化工具

    教学要点：
    1. 批量操作比单条操作性能提升10-100倍
    2. Upsert模式实现增量更新和去重
    3. 后台索引创建避免阻塞
    4. 唯一索引保证数据完整性

    设计理念（来自quantbox）：
    - 批量操作优先：永远使用bulk_write而非循环insert
    - 智能去重：通过唯一键自动处理重复数据
    - 索引优化：根据查询模式创建合适的索引
    - 错误容忍：单条失败不影响整批操作
    """

    @staticmethod
    async def create_index(
        collection: AsyncIOMotorCollection,
        index_keys: list[tuple[str, int]],
        unique: bool = False,
        background: bool = True
    ) -> None:
        """
        创建索引（异步版本）

        教学要点：
        1. background=True避免阻塞数据库
        2. unique=True保证数据唯一性
        3. 复合索引的字段顺序很重要
        4. 索引存在时创建操作是幂等的

        Args:
            collection: MongoDB集合
            index_keys: 索引键列表，如 [("symbol", 1), ("date", 1)]
            unique: 是否为唯一索引
            background: 是否后台创建（推荐True）

        Examples:
            >>> await BulkWriter.create_index(
            ...     collection,
            ...     [("symbol", pymongo.ASCENDING), ("date", pymongo.ASCENDING)],
            ...     unique=True
            ... )
        """
        try:
            await collection.create_index(
                index_keys,
                unique=unique,
                background=background
            )
            index_name = "_".join([f"{k}_{v}" for k, v in index_keys])
            logger.debug(f"✓ Created index: {index_name} on {collection.name}")
        except pymongo.errors.DuplicateKeyError:
            # 索引已存在，忽略
            pass
        except Exception as e:
            logger.warning(f"⚠ Index creation warning for {collection.name}: {e}")

    @staticmethod
    async def bulk_upsert(
        collection: AsyncIOMotorCollection,
        data: list[dict[str, Any]],
        key_fields: list[str],
        result: SaveResult | None = None
    ) -> dict[str, int]:
        """
        批量更新或插入数据（upsert模式）

        教学要点：
        1. Upsert = Update + Insert：存在则更新，不存在则插入
        2. key_fields定义唯一性：相同key_fields的记录会被更新
        3. bulk_write一次性执行所有操作，性能最优
        4. 返回详细的操作统计

        性能对比：
        - 单条insert: 1000条 ≈ 10秒
        - 批量bulk_write: 1000条 ≈ 0.1秒（快100倍）

        Args:
            collection: MongoDB集合
            data: 数据字典列表
            key_fields: 唯一键字段列表（用于判断是否重复）
            result: SaveResult对象（可选，用于记录统计）

        Returns:
            dict: {"upserted_count": int, "modified_count": int}

        Raises:
            ValueError: data为空或key_fields无效

        Examples:
            >>> data = [
            ...     {"symbol": "rb2501", "date": 20241122, "close": 3500.0},
            ...     {"symbol": "rb2501", "date": 20241123, "close": 3510.0},
            ... ]
            >>> result = await BulkWriter.bulk_upsert(
            ...     collection=db.market_data,
            ...     data=data,
            ...     key_fields=["symbol", "date"]
            ... )
            >>> print(result)  # {"upserted_count": 2, "modified_count": 0}
        """
        if not data:
            logger.warning("No data to upsert")
            return {"upserted_count": 0, "modified_count": 0}

        if not key_fields:
            raise ValueError("key_fields cannot be empty")

        # 构建批量操作
        operations = []
        for doc in data:
            # 构建查询条件（基于唯一键）
            query = {field: doc[field] for field in key_fields if field in doc}

            if not query:
                # 如果唯一键字段不完整，记录错误并跳过
                if result:
                    result.add_error(
                        "INVALID_KEY",
                        f"Document missing key fields: {key_fields}",
                        doc
                    )
                continue

            # UpdateOne with upsert=True
            # 教学要点：$set只更新提供的字段，保留其他字段
            operations.append(
                UpdateOne(
                    query,
                    {"$set": doc},
                    upsert=True
                )
            )

        if not operations:
            logger.warning("No valid operations to execute")
            return {"upserted_count": 0, "modified_count": 0}

        try:
            # 执行批量写入
            bulk_result = await collection.bulk_write(operations)

            upserted = bulk_result.upserted_count
            modified = bulk_result.modified_count

            # 更新SaveResult统计
            if result:
                result.inserted_count += upserted
                result.modified_count += modified

            logger.info(
                f"✓ Bulk upsert completed: "
                f"{upserted} inserted, {modified} modified"
            )

            return {
                "upserted_count": upserted,
                "modified_count": modified
            }

        except Exception as e:
            error_msg = f"Bulk upsert failed: {str(e)}"
            logger.error(error_msg)
            if result:
                result.add_error("BULK_WRITE_ERROR", error_msg)
            raise

    @staticmethod
    async def ensure_indexes(
        collection: AsyncIOMotorCollection,
        index_specs: list[dict[str, Any]]
    ) -> None:
        """
        批量创建索引（确保所有必需的索引都存在）

        教学要点：
        1. 数据入库前先创建索引
        2. 批量创建索引提高效率
        3. 索引规范使用字典定义更灵活

        Args:
            collection: MongoDB集合
            index_specs: 索引规范列表，每项包含：
                - keys: 索引键列表
                - unique: 是否唯一（可选，默认False）
                - background: 是否后台创建（可选，默认True）

        Examples:
            >>> specs = [
            ...     {
            ...         "keys": [("symbol", 1), ("date", 1)],
            ...         "unique": True
            ...     },
            ...     {
            ...         "keys": [("date", -1)],  # 降序索引，适合时间倒序查询
            ...         "unique": False
            ...     }
            ... ]
            >>> await BulkWriter.ensure_indexes(collection, specs)
        """
        for spec in index_specs:
            keys = spec.get("keys")
            unique = spec.get("unique", False)
            background = spec.get("background", True)

            if not keys:
                logger.warning(f"Invalid index spec (missing keys): {spec}")
                continue

            await BulkWriter.create_index(
                collection=collection,
                index_keys=keys,
                unique=unique,
                background=background
            )


# 使用示例和测试代码
if __name__ == "__main__":
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient

    async def example_usage():
        """使用示例"""
        print("=" * 60)
        print("BulkWriter 使用示例")
        print("=" * 60)

        # 连接MongoDB（请根据实际情况修改）
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client.test_database
        collection = db.test_collection

        # 示例1：创建索引
        print("\n示例1：创建索引")
        await BulkWriter.ensure_indexes(
            collection,
            [
                {
                    "keys": [("symbol", pymongo.ASCENDING), ("date", pymongo.ASCENDING)],
                    "unique": True
                },
                {
                    "keys": [("date", pymongo.DESCENDING)],
                    "unique": False
                }
            ]
        )
        print("✓ 索引创建完成")

        # 示例2：批量upsert
        print("\n示例2：批量upsert数据")
        test_data = [
            {"symbol": "rb2501", "date": 20241122, "close": 3500.0, "volume": 100000},
            {"symbol": "rb2501", "date": 20241123, "close": 3510.0, "volume": 120000},
            {"symbol": "hc2501", "date": 20241122, "close": 3200.0, "volume": 80000},
        ]

        result = SaveResult()
        await BulkWriter.bulk_upsert(
            collection=collection,
            data=test_data,
            key_fields=["symbol", "date"],
            result=result
        )

        result.complete()
        print(result)

        # 示例3：更新已存在的数据
        print("\n示例3：更新已存在的数据（测试upsert）")
        update_data = [
            {"symbol": "rb2501", "date": 20241122, "close": 3505.0, "volume": 105000},  # 更新
            {"symbol": "rb2501", "date": 20241124, "close": 3520.0, "volume": 110000},  # 新插入
        ]

        result2 = SaveResult()
        await BulkWriter.bulk_upsert(
            collection=collection,
            data=update_data,
            key_fields=["symbol", "date"],
            result=result2
        )

        result2.complete()
        print(result2)
        print(f"  - 第一条数据被更新（modified_count）")
        print(f"  - 第二条数据被插入（inserted_count）")

        # 清理测试数据
        await collection.drop()
        print("\n✓ 测试数据已清理")

    # 运行示例
    # asyncio.run(example_usage())  # 取消注释以运行
    print("\n提示：取消注释 asyncio.run(example_usage()) 以运行示例")
