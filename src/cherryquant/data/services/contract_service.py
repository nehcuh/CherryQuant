"""
合约管理服务

提供期货合约元数据的完整管理功能。

教学要点：
1. 元数据管理策略
2. 主力合约切换逻辑
3. 合约生命周期管理
"""

import logging
from datetime import datetime

from cherryquant.data.collectors.base_collector import (
    BaseCollector,
    ContractInfo,
    Exchange,
)
from cherryquant.data.cleaners.validator import DataValidator
from cherryquant.data.storage.metadata_repository import MetadataRepository
from cherryquant.data.storage.cache_strategy import CacheStrategy

logger = logging.getLogger(__name__)


class ContractService:
    """
    合约管理服务

    整合数据采集、验证和存储，提供统一的合约管理接口。

    教学要点：
    1. 服务层设计
    2. 业务规则实现
    3. 缓存策略应用
    """

    def __init__(
        self,
        collector: BaseCollector,
        repository: MetadataRepository,
        validator: DataValidator | None = None,
        cache: CacheStrategy | None = None,
    ):
        """
        初始化合约管理服务

        Args:
            collector: 数据采集器
            repository: 元数据仓储
            validator: 数据验证器（可选）
            cache: 缓存策略（可选）
        """
        self.collector = collector
        self.repository = repository
        self.validator = validator or DataValidator()
        self.cache = cache

    async def sync_contracts(
        self,
        exchange: Exchange | None = None,
        underlying: str | None = None,
        force_refresh: bool = False,
    ) -> int:
        """
        同步合约信息

        从数据源获取并保存到数据库。

        Args:
            exchange: 交易所（None表示所有）
            underlying: 标的代码（None表示所有）
            force_refresh: 是否强制刷新

        Returns:
            同步的合约数量

        教学要点：
        1. 批量数据同步
        2. 增量更新策略
        """
        logger.info(f"📋 开始同步合约信息: {exchange.value if exchange else '所有交易所'}")

        try:
            # 1. 连接采集器
            if not self.collector.is_connected:
                await self.collector.connect()

            # 2. 获取合约信息
            contracts = await self.collector.fetch_contract_info(
                symbol=underlying,
                exchange=exchange,
            )

            if not contracts:
                logger.warning("⚠️ 未获取到合约信息")
                return 0

            # 3. 验证数据
            valid_contracts = []
            for contract in contracts:
                result = self.validator.validate_contract_info(contract)
                if result.is_valid:
                    valid_contracts.append(contract)
                else:
                    logger.warning(
                        f"⚠️ 合约验证失败: {contract.symbol} - {result}"
                    )

            # 4. 保存到数据库
            saved_count = await self.repository.save_contracts_batch(valid_contracts)

            # 5. 清除缓存
            if force_refresh and self.cache:
                await self.cache.clear("contract_*")

            logger.info(
                f"✅ 合约同步完成: {saved_count}/{len(contracts)} 个 "
                f"(有效: {len(valid_contracts)})"
            )

            return saved_count

        except Exception as e:
            logger.error(f"❌ 合约同步失败: {e}")
            raise

    async def get_contract(
        self,
        symbol: str,
        exchange: Exchange,
    ) -> ContractInfo | None:
        """
        获取单个合约信息（带缓存）

        教学要点：
        1. 缓存键设计
        2. 透明缓存
        """
        cache_key = f"contract_{symbol}_{exchange.value}"

        # 尝试从缓存获取
        if self.cache:
            cached_contract = await self.cache.get(cache_key)
            if cached_contract:
                return cached_contract

        # 从数据库查询
        contract = await self.repository.get_contract(symbol, exchange)

        # 写入缓存
        if contract and self.cache:
            await self.cache.set(cache_key, contract)

        return contract

    async def get_main_contract(
        self,
        underlying: str,
        exchange: Exchange,
    ) -> ContractInfo | None:
        """
        获取主力合约

        教学要点：
        1. 业务规则封装
        2. 主力合约的定义
        """
        cache_key = f"main_contract_{underlying}_{exchange.value}"

        # 尝试从缓存获取
        if self.cache:
            cached_contract = await self.cache.get(cache_key)
            if cached_contract:
                return cached_contract

        # 从数据库查询
        contract = await self.repository.get_main_contract(underlying, exchange)

        # 写入缓存
        if contract and self.cache:
            await self.cache.set(cache_key, contract)

        return contract

    async def query_active_contracts(
        self,
        underlying: str | None = None,
        exchange: Exchange | None = None,
    ) -> list[ContractInfo]:
        """
        查询活跃合约

        Args:
            underlying: 标的代码（可选）
            exchange: 交易所（可选）

        Returns:
            活跃合约列表

        教学要点：
        1. 复杂查询封装
        2. 业务状态过滤
        """
        contracts = await self.repository.query_contracts(
            underlying=underlying,
            exchange=exchange,
            is_active=True,
        )

        logger.info(
            f"📊 查询活跃合约: {len(contracts)} 个 "
            f"({underlying or '所有'}, {exchange.value if exchange else '所有交易所'})"
        )

        return contracts

    async def update_contract_status(
        self,
        symbol: str,
        exchange: Exchange,
        is_active: bool,
    ) -> bool:
        """
        更新合约状态

        教学要点：
        1. 状态管理
        2. 缓存失效
        """
        contract = await self.repository.get_contract(symbol, exchange)

        if not contract:
            logger.warning(f"⚠️ 合约不存在: {symbol}.{exchange.value}")
            return False

        # 更新状态
        contract.is_active = is_active

        # 保存
        success = await self.repository.save_contract(contract)

        # 清除缓存
        if success and self.cache:
            cache_key = f"contract_{symbol}_{exchange.value}"
            await self.cache.delete(cache_key)

            # 如果是主力合约，也清除主力合约缓存
            main_cache_key = f"main_contract_{contract.underlying}_{exchange.value}"
            await self.cache.delete(main_cache_key)

        return success

    async def switch_main_contract(
        self,
        underlying: str,
        exchange: Exchange,
        new_main_symbol: str,
    ) -> bool:
        """
        切换主力合约

        教学要点：
        1. 业务流程实现
        2. 原子操作
        3. 缓存一致性
        """
        logger.info(
            f"🔄 切换主力合约: {underlying}.{exchange.value} → {new_main_symbol}"
        )

        # 获取当前主力合约
        old_main = await self.get_main_contract(underlying, exchange)

        if not old_main:
            logger.warning(f"⚠️ 未找到当前主力合约")
            old_main_symbol = None
        else:
            old_main_symbol = old_main.symbol

        # 执行切换
        success = await self.repository.update_main_contract(
            old_symbol=old_main_symbol or "",
            new_symbol=new_main_symbol,
            exchange=exchange,
        )

        # 清除缓存
        if success and self.cache:
            main_cache_key = f"main_contract_{underlying}_{exchange.value}"
            await self.cache.delete(main_cache_key)

            # 清除旧主力合约缓存
            if old_main_symbol:
                old_cache_key = f"contract_{old_main_symbol}_{exchange.value}"
                await self.cache.delete(old_cache_key)

            # 清除新主力合约缓存
            new_cache_key = f"contract_{new_main_symbol}_{exchange.value}"
            await self.cache.delete(new_cache_key)

        return success

    async def ensure_contracts_available(
        self,
        exchange: Exchange,
    ) -> bool:
        """
        确保合约数据可用

        如果缺失，自动从数据源同步。

        教学要点：
        1. 自动初始化
        2. 数据完整性检查
        """
        # 检查是否已有合约数据
        contracts = await self.repository.query_contracts(
            exchange=exchange,
            is_active=True,
        )

        if len(contracts) < 10:  # 少于10个合约，可能数据不全
            logger.info(
                f"📋 合约数据不足，开始同步 ({len(contracts)} 个)"
            )

            try:
                await self.sync_contracts(exchange=exchange)
                return True

            except Exception as e:
                logger.error(f"❌ 合约同步失败: {e}")
                return False

        logger.info(f"✅ 合约数据充足: {len(contracts)} 个")
        return True
