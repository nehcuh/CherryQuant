"""
合约解析器模块
定义合约解析的基础接口和期货实现
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
from abc import ABC, abstractmethod

from cherryquant.constants import COMMODITY_EXCHANGE_MAP, EXCHANGE_TO_TUSHARE

logger = logging.getLogger(__name__)


class BaseContractResolver(ABC):
    """合约解析器基类"""

    @abstractmethod
    async def resolve_vt_symbol(self, symbol: str) -> Optional[str]:
        """解析为vnpy格式的vt_symbol"""
        pass

    @abstractmethod
    def get_instrument_info(self, symbol: str) -> Dict[str, Any]:
        """获取合约基础信息"""
        pass


class FuturesContractResolver(BaseContractResolver):
    """期货合约解析器 - 动态查询主力合约"""

    def __init__(self, tushare_token: Optional[str] = None):
        """
        初始化期货合约解析器

        Args:
            tushare_token: Tushare Pro API令牌
        """
        self.tushare_token = tushare_token
        self.tushare_pro = None
        self._cache: Dict[str, Dict] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=1)  # 缓存1小时

        if tushare_token:
            try:
                import tushare as ts
                self.tushare_pro = ts.pro_api(tushare_token)
                logger.info("✅ Tushare Pro API 初始化成功")
            except Exception as e:
                logger.warning(f"⚠️ Tushare Pro API 初始化失败: {e}")
                self.tushare_pro = None

    async def get_dominant_contract(
        self,
        commodity: str,
        trade_date: Optional[str] = None
    ) -> Optional[str]:
        """
        获取指定品种的主力合约

        Args:
            commodity: 品种代码（如 rb, cu, IF）
            trade_date: 交易日期（YYYYMMDD格式），默认为今天

        Returns:
            主力合约代码（如 rb2501），失败返回 None
        """
        try:
            # 检查缓存
            if self._is_cache_valid():
                cached_contract = self._cache.get(commodity)
                if cached_contract:
                    logger.debug(f"从缓存获取主力合约: {commodity} -> {cached_contract}")
                    return cached_contract["contract"]

            # 从Tushare查询
            if self.tushare_pro:
                contract = await self._get_from_tushare(commodity, trade_date)
                if contract:
                    return contract

            # 降级方案：使用简单规则推算
            contract = self._infer_dominant_contract(commodity)
            logger.warning(f"⚠️ 使用推算的主力合约: {commodity} -> {contract}")
            return contract

        except Exception as e:
            logger.error(f"获取主力合约失败: {commodity}, 错误: {e}")
            return self._infer_dominant_contract(commodity)

    async def _get_from_tushare(
        self,
        commodity: str,
        trade_date: Optional[str] = None
    ) -> Optional[str]:
        """从Tushare获取主力合约"""
        try:
            if not self.tushare_pro:
                return None

            # 获取交易所代码
            exchange = COMMODITY_EXCHANGE_MAP.get(commodity.lower())
            if not exchange:
                logger.warning(f"未知品种: {commodity}")
                return None

            tushare_exchange = EXCHANGE_TO_TUSHARE.get(exchange)
            if not tushare_exchange:
                logger.warning(f"不支持的交易所: {exchange}")
                return None

            # 构造主力合约代码（Tushare格式）
            # 例如: RB.SHF (主力连续), RB2501.SHF (具体合约)
            ts_code = f"{commodity.upper()}.{tushare_exchange}"

            if trade_date is None:
                trade_date = datetime.now().strftime("%Y%m%d")

            # 使用 fut_mapping 查询主力合约映射
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: self.tushare_pro.fut_mapping(
                    ts_code=ts_code,
                    trade_date=trade_date
                )
            )

            if df is not None and not df.empty:
                # 获取映射到的月度合约
                mapping_ts_code = df.iloc[0]["mapping_ts_code"]
                # 提取合约代码（去除交易所后缀）
                contract = mapping_ts_code.split('.')[0].lower()

                # 更新缓存
                self._cache[commodity] = {
                    "contract": contract,
                    "ts_code": mapping_ts_code,
                    "exchange": exchange,
                    "update_time": datetime.now()
                }
                self._cache_time = datetime.now()

                logger.info(f"✅ 从Tushare获取主力合约: {commodity} -> {contract}")
                return contract
            else:
                logger.warning(f"Tushare未返回主力合约数据: {commodity}")
                return None

        except Exception as e:
            logger.error(f"从Tushare查询主力合约失败: {commodity}, 错误: {e}")
            return None

    def _infer_dominant_contract(self, commodity: str) -> str:
        """
        推算主力合约（降级方案）
        基于当前月份推算最可能的主力合约月份
        """
        now = datetime.now()
        current_month = now.month
        current_year = now.year

        # 不同品种的主力合约规律
        # 大部分商品：当月+2 或 当月+3
        # 股指期货：当月合约

        if commodity.upper() in ["IF", "IC", "IH", "IM"]:
            # 股指期货：通常是当月
            month_code = current_month
            year_code = current_year % 100
        else:
            # 商品期货：通常是当月+2或+3
            month_code = current_month + 2
            if month_code > 12:
                month_code -= 12
                year_code = (current_year + 1) % 100
            else:
                year_code = current_year % 100

        # 构造合约代码
        contract = f"{commodity.lower()}{year_code:02d}{month_code:02d}"
        return contract

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self._cache_time:
            return False
        return datetime.now() - self._cache_time < self._cache_ttl

    async def resolve_vt_symbol(self, commodity: str) -> Optional[str]:
        """
        解析品种代码为vnpy格式的vt_symbol

        Args:
            commodity: 品种代码（如 rb, cu）

        Returns:
            vt_symbol格式（如 rb2501.SHFE）
        """
        try:
            contract = await self.get_dominant_contract(commodity)
            if not contract:
                return None

            exchange = COMMODITY_EXCHANGE_MAP.get(commodity.lower())
            if not exchange:
                return None

            vt_symbol = f"{contract}.{exchange}"
            return vt_symbol

        except Exception as e:
            logger.error(f"解析vt_symbol失败: {commodity}, 错误: {e}")
            return None

    async def batch_resolve_contracts(
        self,
        commodities: List[str]
    ) -> Dict[str, Optional[str]]:
        """
        批量解析主力合约

        Args:
            commodities: 品种代码列表

        Returns:
            品种到主力合约的映射字典
        """
        results = {}
        tasks = [
            self.get_dominant_contract(commodity)
            for commodity in commodities
        ]

        contracts = await asyncio.gather(*tasks, return_exceptions=True)

        for commodity, contract in zip(commodities, contracts):
            if isinstance(contract, Exception):
                logger.error(f"解析 {commodity} 时出错: {contract}")
                results[commodity] = None
            else:
                results[commodity] = contract

        return results

    def get_instrument_info(self, commodity: str) -> Dict[str, str]:
        """
        获取品种信息

        Args:
            commodity: 品种代码

        Returns:
            包含交易所等信息的字典
        """
        exchange = COMMODITY_EXCHANGE_MAP.get(commodity.lower())
        return {
            "commodity": commodity,
            "exchange": exchange or "UNKNOWN",
            "tushare_exchange": EXCHANGE_TO_TUSHARE.get(exchange, "UNKNOWN") if exchange else "UNKNOWN"
        }

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
        self._cache_time = None
        logger.info("合约缓存已清除")


# 兼容旧代码
ContractResolver = FuturesContractResolver

# 全局单例
_resolver_instance: Optional[ContractResolver] = None

def get_contract_resolver(tushare_token: Optional[str] = None) -> ContractResolver:
    """获取全局合约解析器实例"""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = ContractResolver(tushare_token)
    return _resolver_instance
