"""
市场数据管理器
支持多种数据源：Tushare (via QuantBox)、Simnow、vn.py内置数据等
使用协议定义标准接口
注意：AKShare 已移除，使用 QuantBox 替代
"""

import logging
from typing import Dict, Any, Optional, List, Protocol, runtime_checkable
from datetime import datetime, timedelta
import asyncio
import os
from dataclasses import dataclass
from abc import ABC, abstractmethod

# import akshare as ak  # 已移除，使用 QuantBox 替代
import pandas as pd

logger = logging.getLogger(__name__)


@runtime_checkable
class MarketDataSource(Protocol):
    """市场数据源协议"""

    @property
    def name(self) -> str:
        """数据源名称"""
        ...

    @property
    def description(self) -> str:
        """数据源描述"""
        ...

    async def get_realtime_price(self, symbol: str) -> Optional[float]:
        """获取实时价格"""
        ...

    async def get_kline_data(
        self, symbol: str, period: str = "5m", count: int = 100
    ) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        ...

    def is_available(self) -> bool:
        """检查数据源是否可用"""
        ...


@dataclass
class DataSourceStatus:
    """数据源状态"""
    name: str
    available: bool
    description: str
    response_time_ms: Optional[float] = None


# ============================================================================
# AKShareDataSource 已移除
# 原因：已迁移到 QuantBox，提供更高性能和更完整的数据支持
# 如需历史数据，请使用 HistoryDataManager (基于 QuantBox)
# 如需实时数据，请使用 VNPy CTP 连接
# ============================================================================

# class AKShareDataSource:
#     """AKShare数据源实现 - 已废弃，使用 QuantBox 替代"""
#     pass


class TushareDataSource:
    """Tushare数据源实现（Pro接口）"""

    def __init__(self, token: str = None):
        self._name = "Tushare"
        self._description = "Tushare Pro 接口"
        self._token = (token or os.getenv("TUSHARE_TOKEN") or "").strip()
        self._ts = None
        self._token_valid = False

        try:
            import tushare as ts  # type: ignore
            self._ts = ts
            if self._token and self._token.lower() != 'your_tushare_pro_token_here':
                ts.set_token(self._token)
                # 使用 pro_api 验证 Token
                try:
                    pro = ts.pro_api()
                    df = pro.trade_cal(exchange='SSE', start_date='20240101', end_date='20240102')
                    self._token_valid = df is not None and not df.empty
                    if self._token_valid:
                        logger.info("✅ Tushare Token验证成功")
                    else:
                        logger.warning("⚠️ Tushare Token验证失败，可能权限不足或无返回数据")
                except Exception as e:
                    logger.warning(f"⚠️ Tushare Token验证失败: {e}")
        except Exception as e:
            logger.debug(f"Tushare导入失败: {e}")

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def is_available(self) -> bool:
        return bool(self._token and self._ts and self._token_valid)

    async def get_realtime_price(self, symbol: str) -> Optional[float]:
        """获取实时价格（占位实现）"""
        try:
            if not self.is_available():
                return None
            # TODO: 使用 Tushare 实时接口（若可用）
            logger.warning("Tushare实时行情尚未实现，返回None")
            return None
        except Exception as e:
            logger.error(f"Tushare获取实时价格失败: {e}")
            return None

    async def get_kline_data(
        self, symbol: str, period: str = "5m", count: int = 100
    ) -> Optional[pd.DataFrame]:
        """获取K线数据（支持分钟线和日线）"""
        try:
            if not self.is_available():
                return None

            self._ts.set_token(self._token)
            pro = self._ts.pro_api()

            # 映射主连合约（如 rb -> RB9999.SHF）
            ts_symbol = self._to_ts_main_symbol(symbol)
            if not ts_symbol:
                logger.warning(f"无法映射合约 {symbol} 到Tushare代码")
                return None

            import datetime as _dt

            # 根据周期选择数据接口
            if period in ("1m", "5m", "15m", "30m", "60m"):
                # 使用分钟线接口（需要2000+积分）
                try:
                    # 计算时间范围（分钟线数据量大，限制查询范围）
                    end_dt = _dt.datetime.now()
                    start_dt = end_dt - _dt.timedelta(days=7)  # 最近7天

                    # Tushare分钟线接口格式
                    freq_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "60m": "60min"}
                    freq = freq_map.get(period, "5min")

                    df = pro.fut_min(
                        ts_code=ts_symbol,
                        start_date=start_dt.strftime("%Y%m%d"),
                        end_date=end_dt.strftime("%Y%m%d"),
                        freq=freq
                    )

                    if df is None or df.empty:
                        logger.warning(f"Tushare分钟线数据为空 ({symbol}, {period})")
                        logger.info("💡 提示：分钟线数据需要Tushare Pro 2000+积分")
                        return None

                    # 标准化列
                    df = df.sort_values("trade_time")
                    df.rename(
                        columns={
                            "trade_time": "datetime",
                            "open": "open",
                            "high": "high",
                            "low": "low",
                            "close": "close",
                            "vol": "volume",
                        },
                        inplace=True,
                    )
                    df["datetime"] = pd.to_datetime(df["datetime"])
                    result = df[["datetime", "open", "high", "low", "close", "volume"]].tail(count)
                    logger.debug(f"Tushare获取分钟线数据成功: {len(result)} 条 ({symbol}, {period})")
                    return result

                except Exception as e:
                    logger.warning(f"Tushare分钟线接口失败 ({symbol}, {period}): {e}")
                    logger.info("💡 降级到日线数据")
                    # 降级到日线

            # 使用日线接口（默认或降级）
            end = _dt.datetime.now().strftime("%Y%m%d")
            start = (_dt.datetime.now() - _dt.timedelta(days=60)).strftime("%Y%m%d")
            df = pro.fut_daily(ts_code=ts_symbol, start_date=start, end_date=end)

            if df is None or df.empty:
                logger.warning(f"Tushare日线数据为空 ({symbol})")
                return None

            # 标准化列
            df = df.sort_values("trade_date")
            df.rename(
                columns={
                    "trade_date": "datetime",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "vol": "volume",
                },
                inplace=True,
            )
            df["datetime"] = pd.to_datetime(df["datetime"])
            result = df[["datetime", "open", "high", "low", "close", "volume"]].tail(count)
            logger.debug(f"Tushare获取日线数据成功: {len(result)} 条 ({symbol})")
            return result

        except Exception as e:
            logger.error(f"Tushare获取K线数据失败 ({symbol}, {period}): {e}")
            return None

    def _to_ts_main_symbol(self, symbol: str) -> Optional[str]:
        """将品种映射为Tushare主连代码，简化版本"""
        try:
            if not symbol:
                return None
            sym = symbol.lower()
            # 使用主连9999合约
            mapping = {
                "shfe": {
                    "rb": "RB9999.SHF",
                    "cu": "CU9999.SHF",
                    "al": "AL9999.SHF",
                    "zn": "ZN9999.SHF",
                    "au": "AU9999.SHF",
                    "ag": "AG9999.SHF",
                },
                "dce": {"i": "I9999.DCE", "j": "J9999.DCE", "jm": "JM9999.DCE"},
                "czce": {
                    "ta": "TA9999.CZC",
                    "ma": "MA9999.CZC",
                    "sr": "SR9999.CZC",
                    "cf": "CF9999.CZC",
                },
            }
            # 仅基于前两位品种码推测交易所（不严谨，后续可改为显式传入）
            prefix2 = sym[:2]
            for ex, mp in mapping.items():
                for k, v in mp.items():
                    if prefix2 == k[:2]:
                        return v
            return None
        except Exception:
            return None


class MarketDataManager:
    """市场数据管理器 - 统一管理多种数据源"""

    def __init__(self, db_manager=None, mode: str = "dev"):
        self.db_manager = db_manager
        self.mode = mode  # 'live' or 'dev'
        self.data_sources: List[MarketDataSource] = []
        self.primary_source: Optional[MarketDataSource] = None
        self.fallback_sources: List[MarketDataSource] = []

    def add_data_source(self, source: MarketDataSource, is_primary: bool = False):
        """添加数据源"""
        # Verify that the source implements the MarketDataSource protocol
        if not isinstance(source, MarketDataSource):
            raise TypeError(f"Data source must implement MarketDataSource protocol, got {type(source)}")

        self.data_sources.append(source)

        if is_primary:
            self.primary_source = source
        else:
            self.fallback_sources.append(source)

    async def initialize(self):
        """已弃用：请使用工厂方法（create_default_data_manager/create_tushare_data_manager/create_simnow_data_manager）"""
        logger.warning("MarketDataManager.initialize() 已弃用，请使用工厂方法创建并配置数据源")
        # 为保持向后兼容，这里不做任何数据源变更，仅返回 True
        return True

    async def _get_price_from_db(self, symbol: str) -> Optional[float]:
        """从数据库获取最新价格（live模式）"""
        if not self.db_manager:
            return None

        try:
            # 从数据库获取最新的5m K线收盘价
            from cherryquant.adapters.data_storage.timeframe_data_manager import TimeFrame
            data = await self.db_manager.get_market_data(
                symbol=symbol,
                exchange="SHFE",  # 默认上期所，后续可改为动态获取
                timeframe=TimeFrame.FIVE_MIN,
                limit=1
            )
            if data and len(data) > 0:
                latest = data[-1]
                price = float(latest.close)
                logger.debug(f"从数据库获取 {symbol} 最新价格: {price}")
                return price
            return None
        except Exception as e:
            logger.error(f"从数据库获取价格失败: {e}")
            return None

    async def get_realtime_price(self, symbol: str) -> Optional[float]:
        """获取实时价格 - 支持双模式和多数据源切换"""

        # Live模式：优先从数据库读取（RealtimeRecorder写入的实时数据）
        if self.mode == "live" and self.db_manager:
            price = await self._get_price_from_db(symbol)
            if price is not None:
                logger.debug(f"Live模式从数据库获取价格成功: {symbol} = {price}")
                return price
            else:
                logger.warning(f"Live模式数据库无数据，尝试备用数据源")

        # Dev模式或Live模式fallback：使用数据源API
        # 优先使用主数据源
        if self.primary_source:
            start_time = datetime.now()
            price = await self.primary_source.get_realtime_price(symbol)
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            if price is not None:
                logger.debug(
                    f"主数据源 {self.primary_source.name} 获取价格成功: {price} (响应时间: {response_time:.2f}ms)"
                )
                return price
            else:
                logger.warning(f"主数据源 {self.primary_source.name} 获取价格失败 (响应时间: {response_time:.2f}ms)")

        # 使用备用数据源
        for source in self.fallback_sources:
            if source.is_available():
                start_time = datetime.now()
                price = await source.get_realtime_price(symbol)
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                if price is not None:
                    logger.info(f"备用数据源 {source.name} 获取价格成功: {price} (响应时间: {response_time:.2f}ms)")
                    return price
                else:
                    logger.warning(f"备用数据源 {source.name} 获取价格失败 (响应时间: {response_time:.2f}ms)")

        logger.error("所有数据源都无法获取实时价格")
        return None

    async def get_kline_data(
        self, symbol: str, period: str = "5m", count: int = 100
    ) -> Optional[pd.DataFrame]:
        """获取K线数据 - 支持多数据源切换"""

        # 优先使用主数据源
        if self.primary_source:
            start_time = datetime.now()
            data = await self.primary_source.get_kline_data(symbol, period, count)
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            if data is not None:
                logger.debug(f"主数据源 {self.primary_source.name} 获取K线数据成功 (响应时间: {response_time:.2f}ms)")
                return data
            else:
                logger.warning(f"主数据源 {self.primary_source.name} 获取K线数据失败 (响应时间: {response_time:.2f}ms)")

        # 使用备用数据源
        for source in self.fallback_sources:
            if source.is_available():
                start_time = datetime.now()
                data = await source.get_kline_data(symbol, period, count)
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                if data is not None:
                    logger.info(f"备用数据源 {source.name} 获取K线数据成功 (响应时间: {response_time:.2f}ms)")
                    return data
                else:
                    logger.warning(f"备用数据源 {source.name} 获取K线数据失败 (响应时间: {response_time:.2f}ms)")

        logger.error("所有数据源都无法获取K线数据")
        return None

    def get_data_sources_status(self) -> List[DataSourceStatus]:
        """获取数据源状态"""
        statuses = []

        if self.primary_source:
            statuses.append(DataSourceStatus(
                name=self.primary_source.name,
                available=self.primary_source.is_available(),
                description=self.primary_source.description,
                response_time_ms=None  # Would need to measure this in actual requests
            ))

        for source in self.fallback_sources:
            statuses.append(DataSourceStatus(
                name=source.name,
                available=source.is_available(),
                description=source.description,
                response_time_ms=None
            ))

        return statuses


class SimNowDataSource:
    """Simnow数据源实现 - 需要账号配置"""

    def __init__(self, userid: str, password: str, broker_id: str = "9999"):
        self._name = "SimNow"
        self._description = "期货模拟交易专用数据源"
        self.userid = userid
        self.password = password
        self.broker_id = broker_id
        self.gateway = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    async def get_realtime_price(self, symbol: str) -> Optional[float]:
        """获取实时价格"""
        try:
            if not self.gateway:
                await self._connect_gateway()

            # 这里需要vn.py的CTP网关支持
            # 暂时返回None，需要后续实现
            return None
        except Exception as e:
            logger.error(f"SimNow获取实时价格失败: {e}")
            return None

    async def get_kline_data(
        self, symbol: str, period: str = "5m", count: int = 100
    ) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        try:
            if not self.gateway:
                await self._connect_gateway()

            # 需要vn.py网关支持
            return None
        except Exception as e:
            logger.error(f"SimNow获取K线数据失败: {e}")
            return None

    def is_available(self) -> bool:
        """检查SimNow是否可用"""
        return bool(self.userid and self.password)

    async def _connect_gateway(self):
        """连接SimNow网关"""
        # 这里需要实现vn.py CTP网关连接
        # 暂时留空，后续实现
        pass


def create_default_data_manager(db_manager=None) -> MarketDataManager:
    """创建默认的数据管理器（支持双模式）"""
    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv()

    # 获取数据模式
    data_mode = os.getenv('DATA_MODE', 'dev').lower()
    manager = MarketDataManager(db_manager=db_manager, mode=data_mode)

    logger.info(f"数据管理器模式: {data_mode.upper()}")

    if data_mode == "dev":
        # Dev模式：使用 Tushare (via QuantBox) 作为主数据源
        # AKShare 已移除 - 使用 HistoryDataManager (QuantBox) 替代
        logger.info("✅ Dev模式：使用 QuantBox 提供的 Tushare 数据")

        # Tushare作为主数据源（通过 QuantBox）
        tushare_token = os.getenv('TUSHARE_TOKEN')
        if tushare_token and tushare_token != 'your_tushare_pro_token_here':
            ts_source = TushareDataSource(token=tushare_token)
            if ts_source.is_available():
                manager.add_data_source(ts_source, is_primary=True)
                logger.info("✅ Dev模式：主数据源 Tushare（通过 QuantBox）")
        else:
            logger.warning("⚠️ Tushare Token 未配置，部分功能受限")

    elif data_mode == "live":
        # Live模式：主要从数据库读取RealtimeRecorder写入的实时数据
        logger.info("✅ Live模式：主数据源 MongoDB（CTP实时 tick聚合）")

        # Tushare 作为备用（历史数据）
        tushare_token = os.getenv('TUSHARE_TOKEN')
        if tushare_token and tushare_token != 'your_tushare_pro_token_here':
            ts_source = TushareDataSource(token=tushare_token)
            if ts_source.is_available():
                manager.add_data_source(ts_source, is_primary=False)
                logger.info("✅ Live模式：备用数据源 Tushare")

        # Tushare作为备用
        tushare_token = os.getenv('TUSHARE_TOKEN')
        if tushare_token and tushare_token != 'your_tushare_pro_token_here':
            ts_source = TushareDataSource(token=tushare_token)
            if ts_source.is_available():
                manager.add_data_source(ts_source, is_primary=False)
                logger.info("✅ Live模式：备用数据源 Tushare")

    logger.info("数据管理器初始化完成")
    return manager


def create_simnow_data_manager(userid: str, password: str) -> MarketDataManager:
    """创建Simnow数据管理器"""
    manager = MarketDataManager()

    # Simnow作为主数据源
    simnow_source = SimNowDataSource(userid, password)
    manager.add_data_source(simnow_source, is_primary=True)

    # AKShare 已移除 - 使用 Tushare (via QuantBox) 作为备用
    # 如有Tushare Token，则加入备用数据源
    tushare_token = os.getenv('TUSHARE_TOKEN')
    if tushare_token and tushare_token != 'your_tushare_pro_token_here':
        ts_source = TushareDataSource(token=tushare_token)
        if ts_source.is_available():
            manager.add_data_source(ts_source, is_primary=False)
            logger.info("✅ 添加备用数据源: Tushare")

    logger.info("数据管理器初始化完成，主数据源：SimNow，备用数据源：Tushare (via QuantBox)")
    return manager


def create_tushare_data_manager() -> MarketDataManager:
    """创建Tushare主数据源的数据管理器（不回退AKShare）"""
    manager = MarketDataManager()
    ts_source = TushareDataSource()
    if ts_source.is_available():
        manager.add_data_source(ts_source, is_primary=True)
        logger.info("数据管理器初始化完成，主数据源：Tushare")
    else:
        logger.warning("未检测到可用的 Tushare Token，历史数据功能将受限（不回退 AKShare）")
        # 启动受限模式（无主数据源），由上层根据需要处理
    return manager
