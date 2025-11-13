"""
历史数据管理器 - 纯 QuantBox 版本
用于获取和存储期货历史K线数据
完全基于 QuantBox 高性能数据管理系统
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import pandas as pd

from ..quantbox_adapter.cherryquant_adapter import CherryQuantQuantBoxAdapter
from ..quantbox_adapter.data_bridge import DataBridge

logger = logging.getLogger(__name__)


class HistoryDataManager:
    """历史数据管理器 - 纯 QuantBox 版本"""

    def __init__(
        self,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
        use_async: bool = True
    ):
        """
        初始化历史数据管理器

        Args:
            cache_size: 缓存大小
            cache_ttl: 缓存TTL（秒）
            use_async: 是否使用异步操作
        """
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self.data_cache = {}

        # 初始化 QuantBox 组件
        self.use_async = use_async
        self.quantbox_adapter = CherryQuantQuantBoxAdapter(
            use_async=self.use_async,
            auto_warm=True
        )
        self.data_bridge = DataBridge(
            adapter=self.quantbox_adapter,
            enable_dual_write=False,  # 不再需要双写
            cache_ttl=self.cache_ttl
        )
        logger.info("✅ QuantBox 历史数据管理器已初始化")

    async def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_date: str = None,
        end_date: str = None,
        days: int = 30
    ) -> pd.DataFrame:
        """
        获取历史数据

        Args:
            symbol: 期货合约代码
            exchange: 交易所
            interval: 时间间隔
            start_date: 开始日期
            end_date: 结束日期
            days: 获取天数

        Returns:
            历史数据DataFrame
        """
        # 解析日期参数
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now() - timedelta(days=days)
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()

        # 先从缓存获取
        cache_key = f"{symbol}_{exchange}_{interval}_{start_date}_{end_date}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data is not None:
            logger.debug(f"从缓存获取历史数据: {cache_key}")
            return cached_data

        # 从 QuantBox 获取数据
        try:
            logger.info(f"从 QuantBox 获取历史数据: {symbol}.{exchange} {interval} {start_dt} ~ {end_dt}")

            if self.use_async:
                df = await self.quantbox_adapter.get_future_daily_async(
                    ts_code=f"{symbol}.{exchange}",
                    start_date=start_dt.strftime("%Y%m%d"),
                    end_date=end_dt.strftime("%Y%m%d")
                )
            else:
                df = self.quantbox_adapter.get_future_daily(
                    ts_code=f"{symbol}.{exchange}",
                    start_date=start_dt.strftime("%Y%m%d"),
                    end_date=end_dt.strftime("%Y%m%d")
                )

            if df is not None and not df.empty:
                # 缓存数据
                self._cache_data(cache_key, df)
                logger.info(f"✅ 获取历史数据成功: {len(df)} 条")
                return df
            else:
                logger.warning(f"⚠️  QuantBox 返回空数据: {symbol}.{exchange}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"❌ QuantBox 获取数据失败: {e}")
            return pd.DataFrame()

    async def get_contract_info(self, symbol: str, exchange: str) -> Dict[str, Any]:
        """
        获取合约信息

        Args:
            symbol: 合约代码
            exchange: 交易所

        Returns:
            合约信息字典
        """
        try:
            if self.use_async:
                contracts = await self.quantbox_adapter.get_future_contracts_async(
                    ts_code=f"{symbol}.{exchange}",
                    exchange=exchange
                )
            else:
                contracts = self.quantbox_adapter.get_future_contracts(
                    ts_code=f"{symbol}.{exchange}",
                    exchange=exchange
                )

            if contracts is not None and not contracts.empty:
                return contracts.iloc[0].to_dict()
            else:
                logger.warning(f"未找到合约信息: {symbol}.{exchange}")
                return {}
        except Exception as e:
            logger.error(f"获取合约信息失败: {e}")
            return {}

    async def is_trading_day(self, date: datetime, exchange: str = "SHFE") -> bool:
        """
        检查是否交易日

        Args:
            date: 日期
            exchange: 交易所

        Returns:
            是否交易日
        """
        try:
            if self.use_async:
                calendar = await self.quantbox_adapter.get_trade_calendar_async(
                    exchange=exchange,
                    start_date=date.strftime("%Y%m%d"),
                    end_date=date.strftime("%Y%m%d")
                )
            else:
                calendar = self.quantbox_adapter.get_trade_calendar(
                    exchange=exchange,
                    start_date=date.strftime("%Y%m%d"),
                    end_date=date.strftime("%Y%m%d")
                )

            if calendar is not None and not calendar.empty:
                return calendar.iloc[0].get("is_open", 0) == 1
            return False
        except Exception as e:
            logger.error(f"检查交易日失败: {e}")
            return False

    async def batch_get_historical_data(
        self,
        symbols: List[str],
        exchange: str,
        interval: str,
        start_date: str = None,
        end_date: str = None,
        days: int = 30
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取历史数据

        Args:
            symbols: 合约代码列表
            exchange: 交易所
            interval: 时间间隔
            start_date: 开始日期
            end_date: 结束日期
            days: 获取天数

        Returns:
            {symbol: DataFrame} 字典
        """
        logger.info(f"批量获取历史数据: {len(symbols)} 个合约")

        # 并发获取
        tasks = [
            self.get_historical_data(symbol, exchange, interval, start_date, end_date, days)
            for symbol in symbols
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 组织结果
        data_dict = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"获取 {symbol} 数据失败: {result}")
                data_dict[symbol] = pd.DataFrame()
            else:
                data_dict[symbol] = result

        successful = sum(1 for df in data_dict.values() if not df.empty)
        logger.info(f"批量获取完成: {successful}/{len(symbols)} 成功")

        return data_dict

    async def test_quantbox_connection(self) -> bool:
        """
        测试 QuantBox 连接

        Returns:
            是否连接成功
        """
        try:
            # 测试获取交易日历
            today = datetime.now().strftime("%Y%m%d")
            if self.use_async:
                calendar = await self.quantbox_adapter.get_trade_calendar_async(
                    exchange="SHFE",
                    start_date=today,
                    end_date=today
                )
            else:
                calendar = self.quantbox_adapter.get_trade_calendar(
                    exchange="SHFE",
                    start_date=today,
                    end_date=today
                )

            if calendar is not None:
                logger.info("✅ QuantBox 连接测试成功")
                return True
            else:
                logger.error("❌ QuantBox 连接测试失败")
                return False
        except Exception as e:
            logger.error(f"❌ QuantBox 连接测试失败: {e}")
            return False

    def get_system_status(self) -> Dict[str, Any]:
        """
        获取系统状态

        Returns:
            系统状态字典
        """
        return {
            "quantbox_enabled": True,
            "use_async": self.use_async,
            "cache_size": len(self.data_cache),
            "cache_ttl": self.cache_ttl,
            "timestamp": datetime.now().isoformat()
        }

    def _get_cached_data(self, key: str) -> Optional[pd.DataFrame]:
        """从缓存获取数据"""
        if key in self.data_cache:
            cached_item = self.data_cache[key]
            # 检查是否过期
            if datetime.now().timestamp() - cached_item["timestamp"] < self.cache_ttl:
                return cached_item["data"]
            else:
                # 移除过期缓存
                del self.data_cache[key]
        return None

    def _cache_data(self, key: str, df: pd.DataFrame):
        """缓存数据"""
        # LRU 策略：超过缓存大小时移除最旧的
        if len(self.data_cache) >= self.cache_size:
            oldest_key = min(self.data_cache.keys(), key=lambda k: self.data_cache[k]["timestamp"])
            del self.data_cache[oldest_key]

        self.data_cache[key] = {
            "data": df,
            "timestamp": datetime.now().timestamp()
        }

    def get_cache_info(self) -> Dict[str, Any]:
        """
        获取缓存信息

        Returns:
            缓存信息字典
        """
        return {
            "total_items": len(self.data_cache),
            "max_size": self.cache_size,
            "ttl_seconds": self.cache_ttl,
            "cache_keys": list(self.data_cache.keys())
        }

    def clear_all_caches(self):
        """清除所有缓存"""
        self.data_cache.clear()
        # 清除 DataBridge 缓存
        if hasattr(self.data_bridge, 'clear_cache'):
            self.data_bridge.clear_cache()
        logger.info("✅ 所有缓存已清除")

    def clear_cache(self):
        """清除缓存（兼容旧接口）"""
        self.clear_all_caches()

    async def update_cache(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        days: int = 7
    ):
        """
        更新缓存

        Args:
            symbol: 合约代码
            exchange: 交易所
            interval: 时间间隔
            days: 更新天数
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # 强制刷新缓存
        cache_key = f"{symbol}_{exchange}_{interval}_{start_date}_{end_date}"
        if cache_key in self.data_cache:
            del self.data_cache[cache_key]

        # 重新获取数据
        await self.get_historical_data(symbol, exchange, interval, start_date, end_date)
        logger.info(f"✅ 缓存已更新: {symbol}.{exchange}")


# 便捷函数
def create_history_data_manager(
    cache_size: int = 1000,
    cache_ttl: int = 3600,
    use_async: bool = True
) -> HistoryDataManager:
    """
    创建历史数据管理器实例

    Args:
        cache_size: 缓存大小
        cache_ttl: 缓存TTL（秒）
        use_async: 是否使用异步操作

    Returns:
        HistoryDataManager 实例
    """
    return HistoryDataManager(
        cache_size=cache_size,
        cache_ttl=cache_ttl,
        use_async=use_async
    )


# 测试代码
if __name__ == "__main__":
    async def test():
        """测试历史数据管理器"""
        logging.basicConfig(level=logging.INFO)

        # 创建管理器
        manager = create_history_data_manager()

        # 测试连接
        connected = await manager.test_quantbox_connection()
        print(f"QuantBox 连接: {'成功' if connected else '失败'}")

        if connected:
            # 获取历史数据
            df = await manager.get_historical_data(
                symbol="rb2501",
                exchange="SHFE",
                interval="1d",
                days=30
            )
            print(f"\n获取数据: {len(df)} 条")
            if not df.empty:
                print(df.head())

            # 获取系统状态
            status = manager.get_system_status()
            print(f"\n系统状态: {status}")

    # 运行测试
    asyncio.run(test())
