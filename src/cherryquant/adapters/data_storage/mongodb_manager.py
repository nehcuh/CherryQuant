"""
MongoDB Connection Manager
基于 motor 的异步 MongoDB 连接管理器
"""
from __future__ import annotations

import logging
from typing import Any
from datetime import datetime
import asyncio

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)


class MongoDBConnectionManager:
    """MongoDB 连接管理器"""

    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        database: str = "cherryquant",
        min_pool_size: int = 5,
        max_pool_size: int = 50,
        username: str | None = None,
        password: str | None = None,
        server_selection_timeout_ms: int = 5000,
        connect_timeout_ms: int = 10000,
    ):
        """
        初始化 MongoDB 连接管理器

        Args:
            uri: MongoDB 连接 URI
            database: 数据库名称
            min_pool_size: 最小连接池大小
            max_pool_size: 最大连接池大小
            username: 用户名（可选）
            password: 密码（可选）
            server_selection_timeout_ms: 服务器选择超时（毫秒）
            connect_timeout_ms: 连接超时（毫秒）
        """
        self.uri = uri
        self.database_name = database
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.username = username
        self.password = password
        self.server_selection_timeout_ms = server_selection_timeout_ms
        self.connect_timeout_ms = connect_timeout_ms

        # 异步客户端（用于应用程序）
        self._async_client: AsyncIOMotorClient | None = None
        self._async_db: AsyncIOMotorDatabase | None = None

        # 同步客户端（用于初始化和健康检查）
        self._sync_client: MongoClient | None = None

        self._is_connected = False

    def _build_connection_options(self) -> dict[str, Any]:
        """构建连接选项"""
        options = {
            "minPoolSize": self.min_pool_size,
            "maxPoolSize": self.max_pool_size,
            "serverSelectionTimeoutMS": self.server_selection_timeout_ms,
            "connectTimeoutMS": self.connect_timeout_ms,
            # 复制集和读写分离配置
            "retryWrites": True,
            "retryReads": True,
            "w": "majority",  # 写确认级别
            "readPreference": "primaryPreferred",  # 读优先级
        }

        # 如果提供了认证信息
        if self.username and self.password:
            options["username"] = self.username
            options["password"] = self.password
            options["authSource"] = "admin"  # 认证数据库

        return options

    async def connect(self):
        """建立数据库连接"""
        if self._is_connected:
            logger.info("✓ MongoDB already connected")
            return

        try:
            logger.info(f"Connecting to MongoDB: {self.uri}/{self.database_name}")

            # 构建连接选项
            options = self._build_connection_options()

            # 创建异步客户端
            self._async_client = AsyncIOMotorClient(self.uri, **options)
            self._async_db = self._async_client[self.database_name]

            # 创建同步客户端（用于健康检查）
            self._sync_client = MongoClient(self.uri, **options)

            # 测试连接
            await self.health_check()

            self._is_connected = True
            logger.info(f"✓ Connected to MongoDB: {self.database_name}")

        except ConnectionFailure as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during MongoDB connection: {e}")
            raise

    async def disconnect(self):
        """关闭数据库连接"""
        if not self._is_connected:
            logger.info("MongoDB already disconnected")
            return

        try:
            if self._async_client:
                self._async_client.close()
                logger.info("✓ Closed async MongoDB client")

            if self._sync_client:
                self._sync_client.close()
                logger.info("✓ Closed sync MongoDB client")

            self._is_connected = False
            logger.info("✓ Disconnected from MongoDB")

        except Exception as e:
            logger.error(f"Error during MongoDB disconnection: {e}")
            raise

    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            是否健康
        """
        try:
            # 使用 ping 命令检查连接
            if self._async_db is not None:
                await self._async_db.command("ping")
                logger.debug("✓ MongoDB health check passed")
                return True
            else:
                logger.warning("⚠ MongoDB database not initialized")
                return False
        except Exception as e:
            logger.error(f"❌ MongoDB health check failed: {e}")
            return False

    def get_database(self) -> AsyncIOMotorDatabase:
        """
        获取数据库实例

        Returns:
            数据库实例

        Raises:
            RuntimeError: 如果未连接
        """
        if not self._is_connected or self._async_db is None:
            raise RuntimeError("MongoDB not connected. Call connect() first.")
        return self._async_db

    def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """
        获取集合实例

        Args:
            collection_name: 集合名称

        Returns:
            集合实例

        Raises:
            RuntimeError: 如果未连接
        """
        db = self.get_database()
        return db[collection_name]

    async def list_collections(self):
        """列出所有集合"""
        db = self.get_database()
        collections = await db.list_collection_names()
        return collections

    async def create_indexes(self, collection_name: str, indexes: list):
        """
        创建索引

        Args:
            collection_name: 集合名称
            indexes: 索引列表
        """
        collection = self.get_collection(collection_name)
        for index_spec in indexes:
            try:
                if isinstance(index_spec, tuple):
                    # 单字段索引
                    await collection.create_index([index_spec])
                elif isinstance(index_spec, dict):
                    # 复合索引或带选项的索引
                    keys = index_spec.get("keys")
                    options = {k: v for k, v in index_spec.items() if k != "keys"}
                    await collection.create_index(keys, **options)
                logger.debug(f"✓ Created index on {collection_name}")
            except Exception as e:
                logger.warning(f"⚠ Index creation warning for {collection_name}: {e}")

    async def drop_collection(self, collection_name: str):
        """删除集合"""
        db = self.get_database()
        await db.drop_collection(collection_name)
        logger.info(f"✓ Dropped collection: {collection_name}")

    async def get_stats(self) -> dict[str, Any]:
        """
        获取数据库统计信息

        Returns:
            统计信息字典
        """
        db = self.get_database()
        stats = await db.command("dbStats")
        return stats

    async def get_collection_stats(self, collection_name: str) -> dict[str, Any]:
        """
        获取集合统计信息

        Args:
            collection_name: 集合名称

        Returns:
            统计信息字典
        """
        db = self.get_database()
        stats = await db.command("collStats", collection_name)
        return stats

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._is_connected

    def __repr__(self):
        status = "connected" if self._is_connected else "disconnected"
        return f"<MongoDBConnectionManager(database={self.database_name}, status={status})>"


class MongoDBConnectionPool:
    """MongoDB 连接池管理器（单例模式）"""

    _instance: MongoDBConnectionPool | None = None
    _manager: MongoDBConnectionManager | None = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def get_manager(
        cls,
        uri: str = "mongodb://localhost:27017",
        database: str = "cherryquant",
        **kwargs
    ) -> MongoDBConnectionManager:
        """
        获取连接管理器（单例）

        Args:
            uri: MongoDB URI
            database: 数据库名称
            **kwargs: 其他连接选项

        Returns:
            连接管理器实例
        """
        async with cls._lock:
            if cls._manager is None or not cls._manager.is_connected:
                cls._manager = MongoDBConnectionManager(
                    uri=uri,
                    database=database,
                    **kwargs
                )
                await cls._manager.connect()
            return cls._manager

    @classmethod
    async def close(cls):
        """关闭连接池"""
        async with cls._lock:
            if cls._manager and cls._manager.is_connected:
                await cls._manager.disconnect()
                cls._manager = None


# 便捷函数
async def get_mongodb_manager(
    uri: str = None,
    database: str = None,
    **kwargs
) -> MongoDBConnectionManager:
    """
    获取 MongoDB 管理器（便捷函数）

    Args:
        uri: MongoDB URI（默认使用 CherryQuantConfig.database.mongodb_uri）
        database: 数据库名称（默认使用 CherryQuantConfig.database.mongodb_database）
        **kwargs: 其他连接选项（如未提供，将使用 CherryQuantConfig 中的连接池/认证配置）

    Returns:
        MongoDB 连接管理器
    """
    # 延迟导入以避免潜在循环依赖
    from config.settings.base import CONFIG

    db_cfg = CONFIG.database

    # 使用集中配置作为默认值
    if uri is None:
        uri = db_cfg.mongodb_uri
    if database is None:
        database = db_cfg.mongodb_database

    # 连接池和认证配置：显式参数优先，其次使用集中配置
    kwargs.setdefault("min_pool_size", db_cfg.mongodb_min_pool_size)
    kwargs.setdefault("max_pool_size", db_cfg.mongodb_max_pool_size)
    if db_cfg.mongodb_username is not None:
        kwargs.setdefault("username", db_cfg.mongodb_username)
    if db_cfg.mongodb_password is not None:
        kwargs.setdefault("password", db_cfg.mongodb_password)

    return await MongoDBConnectionPool.get_manager(uri=uri, database=database, **kwargs)


# 测试代码
if __name__ == "__main__":
    async def test_connection():
        """测试连接"""
        logging.basicConfig(level=logging.INFO)

        # 测试连接管理器
        manager = await get_mongodb_manager()

        # 健康检查
        is_healthy = await manager.health_check()
        print(f"Health check: {'✓ Passed' if is_healthy else '✗ Failed'}")

        # 列出集合
        collections = await manager.list_collections()
        print(f"\nCollections ({len(collections)}):")
        for coll in collections:
            print(f"  - {coll}")

        # 获取统计信息
        stats = await manager.get_stats()
        print(f"\nDatabase Stats:")
        print(f"  - Storage Size: {stats.get('storageSize', 0) / 1024 / 1024:.2f} MB")
        print(f"  - Data Size: {stats.get('dataSize', 0) / 1024 / 1024:.2f} MB")
        print(f"  - Collections: {stats.get('collections', 0)}")

        # 关闭连接
        await manager.disconnect()

    # 运行测试
    asyncio.run(test_connection())
