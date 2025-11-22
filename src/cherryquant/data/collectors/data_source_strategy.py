"""
数据源切换策略 - 本地优先，远程备用

整合自quantbox.services.market_data_service的核心设计思想
演示如何实现智能的数据源选择策略。

教学要点：
1. 策略模式的应用
2. 降级策略（本地失败降级到远程）
3. 可用性检查的重要性
4. 灵活的配置覆盖

设计理念（来自quantbox）：
- 本地优先：本地数据库查询速度快，无网络延迟
- 自动降级：本地不可用时自动切换到远程
- 用户可控：允许用户显式指定使用哪个数据源
- 透明切换：调用方无需关心数据来自哪里
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class DataSourceAdapter(ABC):
    """
    数据源适配器抽象基类

    教学要点：
    1. 定义统一的数据访问接口
    2. 所有数据源实现相同接口，保证可替换性
    3. check_availability()是关键的可用性检查方法
    """

    @abstractmethod
    async def get_data(self, **kwargs) -> Any:
        """获取数据"""
        pass

    @abstractmethod
    async def check_availability(self) -> bool:
        """检查数据源是否可用"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        pass


class LocalDataSource(DataSourceAdapter):
    """
    本地数据源（MongoDB）

    特点：
    - 快速：无网络延迟
    - 稳定：不受外部API限制
    - 有限：可能没有最新数据
    """

    async def get_data(self, **kwargs) -> Any:
        """从本地MongoDB获取数据"""
        logger.info("📂 Fetching data from local MongoDB...")
        # 实际实现：查询MongoDB
        # db = get_database()
        # return await db.collection.find(query)
        return {"source": "local", "data": "..."}

    async def check_availability(self) -> bool:
        """检查MongoDB连接是否可用"""
        try:
            # 实际实现：ping MongoDB
            # db = get_database()
            # await db.command("ping")
            # return True
            return True  # 示例代码
        except Exception as e:
            logger.warning(f"Local data source unavailable: {e}")
            return False

    @property
    def name(self) -> str:
        return "LocalMongoDB"


class RemoteDataSource(DataSourceAdapter):
    """
    远程数据源（Tushare/GoldMiner等）

    特点：
    - 完整：数据最全最新
    - 较慢：有网络延迟
    - 受限：可能有API调用限制
    """

    async def get_data(self, **kwargs) -> Any:
        """从远程API获取数据"""
        logger.info("🌐 Fetching data from remote API...")
        # 实际实现：调用Tushare/GoldMiner API
        # api = TushareAPI(token=...)
        # return await api.get_future_daily(...)
        return {"source": "remote", "data": "..."}

    async def check_availability(self) -> bool:
        """检查远程API是否可用"""
        try:
            # 实际实现：测试API连接
            # response = await api.ping()
            # return response.ok
            return True  # 示例代码
        except Exception as e:
            logger.warning(f"Remote data source unavailable: {e}")
            return False

    @property
    def name(self) -> str:
        return "RemoteAPI"


class DataSourceStrategy:
    """
    数据源切换策略

    教学要点：
    1. 策略模式：封装算法（选择哪个数据源）
    2. 智能降级：本地→远程的自动切换
    3. 配置灵活：支持显式指定数据源
    4. 日志记录：清晰记录数据来源

    核心设计（来自quantbox）：
    ```
    if use_local is None:
        # 自动选择模式
        if prefer_local and local.check_availability():
            return local
        else:
            return remote
    elif use_local:
        # 强制使用本地
        return local
    else:
        # 强制使用远程
        return remote
    ```
    """

    def __init__(
        self,
        local_source: DataSourceAdapter,
        remote_source: DataSourceAdapter,
        prefer_local: bool = True
    ):
        """
        初始化数据源策略

        Args:
            local_source: 本地数据源
            remote_source: 远程数据源
            prefer_local: 是否优先使用本地数据源（默认True）

        Examples:
            >>> strategy = DataSourceStrategy(
            ...     local_source=LocalDataSource(),
            ...     remote_source=RemoteDataSource(),
            ...     prefer_local=True
            ... )
        """
        self.local = local_source
        self.remote = remote_source
        self.prefer_local = prefer_local

    async def get_adapter(self, use_local: bool | None = None) -> DataSourceAdapter:
        """
        获取合适的数据源适配器

        教学要点：
        1. use_local=None: 自动选择（根据prefer_local和可用性）
        2. use_local=True: 强制使用本地
        3. use_local=False: 强制使用远程
        4. 自动降级：本地不可用时fallback到远程

        Args:
            use_local: 是否使用本地数据源
                - None: 自动选择（默认）
                - True: 强制使用本地
                - False: 强制使用远程

        Returns:
            DataSourceAdapter: 选定的数据源适配器

        Examples:
            >>> # 自动选择（本地优先）
            >>> adapter = await strategy.get_adapter()

            >>> # 强制使用远程
            >>> adapter = await strategy.get_adapter(use_local=False)
        """
        if use_local is None:
            # 自动选择模式
            use_local = self.prefer_local

        if use_local:
            # 优先使用本地，检查可用性
            if await self.local.check_availability():
                logger.info(f"✓ Using local data source: {self.local.name}")
                return self.local
            else:
                # 本地不可用，降级到远程
                logger.warning(
                    f"⚠ Local source unavailable, falling back to remote"
                )
                return self.remote
        else:
            # 使用远程
            logger.info(f"✓ Using remote data source: {self.remote.name}")
            return self.remote

    async def get_data(self, use_local: bool | None = None, **kwargs) -> Any:
        """
        获取数据（自动选择数据源）

        教学要点：
        1. 对外提供统一接口
        2. 内部自动选择数据源
        3. 调用方无需关心数据来源

        Args:
            use_local: 数据源选择参数
            **kwargs: 传递给数据源的参数

        Returns:
            Any: 数据

        Examples:
            >>> # 自动选择数据源获取数据
            >>> data = await strategy.get_data(symbol="rb2501", date="2024-11-22")

            >>> # 强制从远程获取
            >>> data = await strategy.get_data(use_local=False, symbol="rb2501")
        """
        adapter = await self.get_adapter(use_local)
        return await adapter.get_data(**kwargs)


# 使用示例
async def example_usage():
    """完整使用示例"""
    print("=" * 60)
    print("数据源切换策略使用示例")
    print("=" * 60)

    # 1. 创建数据源
    local_source = LocalDataSource()
    remote_source = RemoteDataSource()

    # 2. 创建策略（本地优先）
    strategy = DataSourceStrategy(
        local_source=local_source,
        remote_source=remote_source,
        prefer_local=True
    )

    print("\n示例1：自动选择数据源（本地优先）")
    adapter = await strategy.get_adapter()
    print(f"  选中的数据源: {adapter.name}")

    print("\n示例2：强制使用远程数据源")
    adapter = await strategy.get_adapter(use_local=False)
    print(f"  选中的数据源: {adapter.name}")

    print("\n示例3：获取数据（自动选择）")
    data = await strategy.get_data(symbol="rb2501", date="2024-11-22")
    print(f"  数据来源: {data['source']}")

    print("\n示例4：创建远程优先策略")
    remote_first_strategy = DataSourceStrategy(
        local_source=local_source,
        remote_source=remote_source,
        prefer_local=False  # 远程优先
    )
    adapter = await remote_first_strategy.get_adapter()
    print(f"  选中的数据源: {adapter.name}")


if __name__ == "__main__":
    import asyncio

    print(__doc__)
    print("\n运行示例：")
    # asyncio.run(example_usage())  # 取消注释以运行
    print("提示：取消注释 asyncio.run(example_usage()) 以运行示例")
