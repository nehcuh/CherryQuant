"""
数据桥接器

在 CherryQuant 和 QuantBox 之间提供数据格式和协议的转换
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

from .cherryquant_adapter import CherryQuantQuantBoxAdapter
from ..data_storage.timeframe_data_manager import TimeFrame, MarketDataPoint, TechnicalIndicators

logger = logging.getLogger(__name__)


class DataBridge:
    """
    数据桥接器

    功能：
    1. 数据格式转换
    2. 缓存策略管理
    3. 双写机制支持
    4. 数据一致性保证
    """

    def __init__(
        self,
        adapter: CherryQuantQuantBoxAdapter,
        enable_dual_write: bool = False,
        cache_ttl: int = 3600
    ):
        """
        初始化数据桥接器

        Args:
            adapter: QuantBox 适配器
            enable_dual_write: 是否启用双写（同时写入新旧系统）
            cache_ttl: 缓存TTL（秒）
        """
        self.adapter = adapter
        self.enable_dual_write = enable_dual_write
        self.cache_ttl = cache_ttl

        # 缓存
        self._cache = {}
        self._cache_timestamps = {}

    def _get_cache_key(self, method: str, **kwargs) -> str:
        """生成缓存键"""
        key_parts = [method]
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}={v}")
        return "|".join(key_parts)

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache:
            return False

        timestamp = self._cache_timestamps.get(key, 0)
        return (datetime.now().timestamp() - timestamp) < self.cache_ttl

    def _set_cache(self, key: str, data: Any):
        """设置缓存"""
        self._cache[key] = data
        self._cache_timestamps[key] = datetime.now().timestamp()

    def _get_cache(self, key: str) -> Any:
        """获取缓存"""
        return self._cache.get(key) if self._is_cache_valid(key) else None

    # ==================== K线数据桥接 ====================

    async def get_kline_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[MarketDataPoint]:
        """
        获取K线数据（统一接口）

        Args:
            symbol: 合约代码
            exchange: 交易所
            interval: 时间周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 数据条数限制

        Returns:
            MarketDataPoint 列表
        """
        # 生成缓存键
        cache_key = self._get_cache_key(
            "kline",
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            start_time=start_time.isoformat() if start_time else None,
            end_time=end_time.isoformat() if end_time else None,
            limit=limit
        )

        # 尝试从缓存获取
        cached_data = self._get_cache(cache_key)
        if cached_data:
            logger.debug(f"从缓存获取K线数据: {symbol}.{exchange} {interval}")
            return cached_data

        try:
            # 映射 CherryQuant 时间周期到 QuantBox 格式
            quantbox_interval = self._map_timeframe(interval)

            # 确定数据源和参数
            if quantbox_interval == "1d":
                # 使用期货日线数据
                df = await self.adapter.get_future_daily_async(
                    symbols=self._format_symbol(symbol, exchange),
                    exchanges=self._map_exchange(exchange),
                    start_date=start_time.strftime("%Y%m%d") if start_time else None,
                    end_date=end_time.strftime("%Y%m%d") if end_time else None
                )
            else:
                # 其他周期需要从其他数据源获取或计算
                df = await self._get_other_timeframe_data(
                    symbol, exchange, quantbox_interval, start_time, end_time, limit
                )

            # 转换为 CherryQuant 格式
            data_points = self.adapter.quantbox_to_cherryquant_data(df)

            # 应用数据条数限制
            if limit and len(data_points) > limit:
                data_points = data_points[-limit:]

            # 缓存结果
            self._set_cache(cache_key, data_points)

            logger.info(f"获取K线数据: {symbol}.{exchange} {interval} {len(data_points)}条")
            return data_points

        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return []

    def _map_timeframe(self, interval: str) -> str:
        """将 CherryQuant 时间周期映射到 QuantBox 格式"""
        timeframe_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1hour",
            "4h": "4hour",
            "1d": "1d",
            "1w": "1w",
            "1M": "1M"
        }
        return timeframe_map.get(interval, "1d")

    def _map_exchange(self, exchange: str) -> str:
        """映射交易所代码"""
        exchange_map = {
            "SHFE": "SHFE",
            "DCE": "DCE",
            "CZCE": "CZCE",
            "CFFEX": "CFFEX",
            "INE": "INE",
            "SSE": "SHSE",   # 股票交易所映射
            "SZSE": "SZSE",
            "SSE": "SHSE",
            "SZSE": "SZSE"
        }
        return exchange_map.get(exchange.upper(), exchange.upper())

    def _format_symbol(self, symbol: str, exchange: str) -> str:
        """格式化合约代码为 QuantBox 格式"""
        # 如果已经是完整格式（交易所.合约），直接返回
        if "." in symbol.upper():
            return symbol.upper()

        # 否则添加交易所前缀
        exchange_mapped = self._map_exchange(exchange)
        return f"{exchange_mapped}.{symbol.upper()}"

    async def _get_other_timeframe_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        limit: Optional[int]
    ) -> pd.DataFrame:
        """
        获取非日线数据（需要从日线数据重采样）

        Args:
            symbol: 合约代码
            exchange: 交易所
            interval: 时间周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 数据条数限制

        Returns:
            调整后的数据 DataFrame
        """
        try:
            # 先获取日线数据
            daily_df = await self.adapter.get_future_daily_async(
                symbols=self._format_symbol(symbol, exchange),
                exchanges=self._map_exchange(exchange),
                start_date=(start_time - timedelta(days=365)).strftime("%Y%m%d") if start_time else None,
                end_date=end_time.strftime("%Y%m%d") if end_time else None
            )

            if daily_df.empty:
                return pd.DataFrame()

            # 重采样为目标周期
            return self._resample_data(daily_df, interval)

        except Exception as e:
            logger.error(f"重采样数据失败: {e}")
            return pd.DataFrame()

    def _resample_data(self, df: pd.DataFrame, interval: str) -> pd.DataFrame:
        """
        数据重采样

        Args:
            df: 原始日线数据
            interval: 目标周期

        Returns:
            重采样后的数据
        """
        try:
            # 确保时间索引
            if 'datetime' in df.columns:
                df = df.set_index('datetime')
            elif 'date' in df.columns:
                df = df.set_index('date')
            elif 'time' in df.columns:
                df = df.set_index('time')
            else:
                df = df.set_index(df.index)

            # 确保索引是 datetime 类型
            df.index = pd.to_datetime(df.index)

            # 重采样规则
            resample_rules = {
                "1hour": "1H",
                "4hour": "4H",
                "1w": "1W",
                "1M": "1M"
            }

            rule = resample_rules.get(interval)
            if not rule:
                logger.warning(f"不支持的重采样周期: {interval}")
                return df

            # 重采样
            resampled = df.resample(rule).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()

            return resampled.reset_index().rename(columns={'index': 'datetime'})

        except Exception as e:
            logger.error(f"数据重采样失败: {e}")
            return pd.DataFrame()

    # ==================== 合约信息桥接 ====================

    async def get_contract_info(
        self,
        symbol: str,
        exchange: str,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取合约信息

        Args:
            symbol: 合约代码
            exchange: 交易所
            date: 查询日期

        Returns:
            合约信息字典
        """
        try:
            # 获取交易所的所有合约
            contracts_df = await self.adapter.get_future_contracts_async(
                exchanges=self._map_exchange(exchange),
                date=date or datetime.now().strftime("%Y%m%d")
            )

            if contracts_df.empty:
                return {}

            # 查找目标合约
            target_symbol = symbol.upper()
            contract_row = contracts_df[
                contracts_df['symbol'].str.contains(target_symbol, case=False)
            ]

            if contract_row.empty:
                return {}

            contract = contract_row.iloc[0].to_dict()

            return {
                "symbol": contract.get("symbol", ""),
                "name": contract.get("name", ""),
                "exchange": contract.get("exchange", ""),
                "underlying": contract.get("underlying", ""),
                "multiplier": contract.get("multiplier", 1),
                "price_tick": contract.get("price_tick", 0.01),
                "trading_unit": contract.get("trading_unit", 1),
                "expire_date": contract.get("expire_date", ""),
                "list_date": contract.get("list_date", ""),
                "product_class": contract.get("product_class", "")
            }

        except Exception as e:
            logger.error(f"获取合约信息失败: {e}")
            return {}

    # ==================== 交易日历桥接 ====================

    async def is_trading_day(
        self,
        date: datetime,
        exchange: str = "SHFE"
    ) -> bool:
        """
        检查是否为交易日

        Args:
            date: 日期
            exchange: 交易所

        Returns:
            是否为交易日
        """
        try:
            # 获取交易日历
            calendar_df = await self.adapter.get_trade_calendar_async(
                exchanges=self._map_exchange(exchange),
                start_date=date.strftime("%Y%m%d"),
                end_date=date.strftime("%Y%m%d")
            )

            if calendar_df.empty:
                return False

            # 检查是否在交易日历中
            date_str = date.strftime("%Y%m%d")
            return not calendar_df[calendar_df['date'] == int(date_str)].empty

        except Exception as e:
            logger.error(f"检查交易日失败: {e}")
            return False

    # ==================== 缓存管理 ====================

    def clear_cache(self, pattern: Optional[str] = None):
        """
        清空缓存

        Args:
            pattern: 缓存键模式（可选）
        """
        if pattern:
            keys_to_remove = [key for key in self._cache.keys() if pattern in key]
            for key in keys_to_remove:
                self._cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
            logger.info(f"清理缓存: {len(keys_to_remove)}个键")
        else:
            self._cache.clear()
            self._cache_timestamps.clear()
            logger.info("清空所有缓存")

    def get_cache_status(self) -> Dict[str, Any]:
        """
        获取缓存状态

        Returns:
            缓存统计信息
        """
        valid_cache_count = sum(
            1 for key in self._cache.keys()
            if self._is_cache_valid(key)
        )

        return {
            "total_cache_entries": len(self._cache),
            "valid_cache_entries": valid_cache_count,
            "cache_ttl": self.cache_ttl,
            "enable_dual_write": self.enable_dual_write,
            "memory_usage": len(str(self._cache))  # 简化的内存使用估算
        }

    # ==================== 性能优化 ====================

    async def batch_get_kline_data(
        self,
        requests: List[Dict[str, Any]]
    ) -> Dict[str, List[MarketDataPoint]]:
        """
        批量获取K线数据

        Args:
            requests: 请求列表，每个请求包含symbol、exchange、interval等参数

        Returns:
            批量数据结果
        """
        results = {}

        # 并发获取数据
        tasks = []
        request_keys = []

        for i, req in enumerate(requests):
            task = self.get_kline_data(
                symbol=req.get('symbol'),
                exchange=req.get('exchange'),
                interval=req.get('interval'),
                start_time=req.get('start_time'),
                end_time=req.get('end_time'),
                limit=req.get('limit')
            )
            tasks.append(task)
            request_keys.append(f"{req.get('symbol')}.{req.get('exchange')}.{req.get('interval')}")

        try:
            # 并发执行
            data_list = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            for i, data in enumerate(data_list):
                if isinstance(data, Exception):
                    logger.error(f"批量获取数据失败 {request_keys[i]}: {data}")
                    results[request_keys[i]] = []
                else:
                    results[request_keys[i]] = data

        except Exception as e:
            logger.error(f"批量获取数据失败: {e}")

        return results