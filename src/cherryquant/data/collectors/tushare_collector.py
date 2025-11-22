"""
Tushare 数据采集器实现

提供基于 Tushare Pro API 的期货数据采集功能。
这是 BaseCollector 的第一个具体实现，用于教学演示。

教学要点：
1. 如何实现抽象基类
2. 第三方 API 的错误处理
3. 数据格式转换和验证
4. 速率限制和重试机制
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any
from decimal import Decimal
import re

from cherryquant.data.collectors.base_collector import (
    BaseCollector,
    DataSource,
    Exchange,
    TimeFrame,
    MarketData,
    ContractInfo,
    TradingDay,
)
from cherryquant.data.utils import retry_async, RetryConfig, RetryStrategy

logger = logging.getLogger(__name__)

# Tushare API 可选依赖
try:
    import tushare as ts
    import pandas as pd
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    logger.warning("⚠️ Tushare 未安装，TushareCollector 不可用")


class TushareCollector(BaseCollector):
    """
    Tushare 数据采集器

    通过 Tushare Pro API 获取中国期货市场数据。

    功能特性：
    - 支持日线和分钟线数据
    - 自动处理 API 限流
    - 数据缓存机制
    - 符号格式转换

    教学要点：
    1. API 配额管理（Tushare 有调用限制）
    2. 异步 API 调用（Tushare 是同步库，需要包装）
    3. 数据验证和清洗
    4. 错误分类处理（配额、网络、数据）
    """

    # Tushare 交易所代码映射
    EXCHANGE_MAP = {
        Exchange.SHFE: "SHF",     # 上期所
        Exchange.DCE: "DCE",      # 大商所
        Exchange.CZCE: "ZCE",     # 郑商所
        Exchange.CFFEX: "CFX",    # 中金所
        Exchange.INE: "INE",      # 能源中心
    }

    # 反向映射
    EXCHANGE_REVERSE_MAP = {v: k for k, v in EXCHANGE_MAP.items()}

    # 时间周期映射
    TIMEFRAME_MAP = {
        TimeFrame.MIN_1: "1min",
        TimeFrame.MIN_5: "5min",
        TimeFrame.MIN_15: "15min",
        TimeFrame.MIN_30: "30min",
        TimeFrame.HOUR_1: "60min",
        TimeFrame.DAY_1: "D",
    }

    def __init__(self, token: str, call_limit_per_minute: int = 100):
        """
        初始化 Tushare 采集器

        Args:
            token: Tushare Pro API Token
            call_limit_per_minute: 每分钟最大调用次数（根据 Tushare 积分等级调整）

        教学要点：
        1. API 认证管理
        2. 速率限制参数化
        """
        super().__init__(source=DataSource.TUSHARE)

        if not TUSHARE_AVAILABLE:
            raise ImportError(
                "Tushare 未安装。请运行: pip install tushare"
            )

        self.token = token
        self.call_limit_per_minute = call_limit_per_minute
        self.pro_api: Any | None = None

        # 速率限制相关
        self._call_count = 0
        self._call_reset_time = datetime.now()
        self._rate_limit_lock = asyncio.Lock()

        # 缓存
        self._contract_cache: dict[str, list[ContractInfo]] = {}
        self._calendar_cache: dict[str, list[TradingDay]] = {}

    async def connect(self) -> bool:
        """
        连接到 Tushare API

        Returns:
            bool: 连接是否成功

        教学要点：
        1. API 认证
        2. 连接验证
        3. 错误处理
        """
        try:
            # Tushare 是同步库，在 executor 中运行
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, ts.set_token, self.token)
            self.pro_api = await loop.run_in_executor(None, ts.pro_api)

            # 测试连接：获取交易日历（轻量级查询）
            test_date = datetime.now().strftime("%Y%m%d")
            await loop.run_in_executor(
                None,
                lambda: self.pro_api.trade_cal(
                    exchange="SHFE",
                    start_date=test_date,
                    end_date=test_date,
                )
            )

            self._connected = True
            logger.info("✅ Tushare API 连接成功")
            return True

        except Exception as e:
            logger.error(f"❌ Tushare API 连接失败: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """
        断开连接

        Tushare 是无状态 API，不需要显式断开。
        """
        self._connected = False
        self.pro_api = None
        logger.info("✅ Tushare API 连接已断开")

    async def _rate_limit_check(self) -> None:
        """
        速率限制检查

        教学要点：
        1. 令牌桶算法的简单实现
        2. 异步锁的使用
        3. API 配额管理策略
        """
        async with self._rate_limit_lock:
            now = datetime.now()

            # 每分钟重置计数器
            if (now - self._call_reset_time).total_seconds() >= 60:
                self._call_count = 0
                self._call_reset_time = now

            # 检查是否超过限制
            if self._call_count >= self.call_limit_per_minute:
                wait_seconds = 60 - (now - self._call_reset_time).total_seconds()
                if wait_seconds > 0:
                    logger.warning(
                        f"⚠️ Tushare API 速率限制，等待 {wait_seconds:.1f} 秒"
                    )
                    await asyncio.sleep(wait_seconds)
                    self._call_count = 0
                    self._call_reset_time = datetime.now()

            self._call_count += 1

    def _convert_symbol_to_tushare(self, symbol: str, exchange: Exchange) -> str:
        """
        转换合约代码为 Tushare 格式

        Args:
            symbol: CherryQuant 格式，如 "rb2501"
            exchange: 交易所

        Returns:
            str: Tushare 格式，如 "RB2501.SHF"

        教学要点：
        1. 符号标准化
        2. 字符串处理
        3. 格式映射表的使用
        """
        ts_exchange = self.EXCHANGE_MAP.get(exchange, "")
        # Tushare 要求大写
        return f"{symbol.upper()}.{ts_exchange}"

    def _convert_symbol_from_tushare(self, ts_code: str) -> tuple[str, Exchange]:
        """
        从 Tushare 格式转换合约代码

        Args:
            ts_code: Tushare 格式，如 "RB2501.SHF"

        Returns:
            tuple: (symbol, exchange)
        """
        parts = ts_code.split(".")
        if len(parts) != 2:
            raise ValueError(f"无效的 Tushare 代码: {ts_code}")

        symbol = parts[0].lower()
        ts_exchange = parts[1]
        exchange = self.EXCHANGE_REVERSE_MAP.get(ts_exchange)

        if not exchange:
            raise ValueError(f"未知的交易所代码: {ts_exchange}")

        return symbol, exchange

    @retry_async(RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        strategy=RetryStrategy.EXPONENTIAL,
        retriable_exceptions=(
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
            # Tushare 可能抛出的异常
            Exception,  # 暂时捕获所有异常，但排除 ValueError
        ),
        non_retriable_exceptions=(
            ValueError,  # 参数错误不重试
            TypeError,
            KeyError,
        ),
    ))
    async def fetch_market_data(
        self,
        symbol: str,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> list[MarketData]:
        """
        获取历史市场数据

        教学要点：
        1. 参数验证的完整流程
        2. 异步包装同步 API
        3. DataFrame 到数据类的转换
        4. 数据质量检查
        5. 自动重试机制 (新增) - 网络错误时自动重试3次
        """
        if not self.is_connected:
            raise RuntimeError("未连接到 Tushare API，请先调用 connect()")

        # 参数验证
        if not self.validate_symbol(symbol):
            raise ValueError(f"无效的合约代码: {symbol}")

        if not self.validate_date_range(start_date, end_date):
            raise ValueError(f"无效的日期范围: {start_date} 到 {end_date}")

        # 速率限制检查
        await self._rate_limit_check()

        # 转换格式
        ts_code = self._convert_symbol_to_tushare(symbol, exchange)
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        try:
            loop = asyncio.get_event_loop()

            # 根据时间周期选择 API
            if timeframe == TimeFrame.DAY_1:
                # 日线数据
                df = await loop.run_in_executor(
                    None,
                    lambda: self.pro_api.fut_daily(
                        ts_code=ts_code,
                        start_date=start_str,
                        end_date=end_str,
                    )
                )
            else:
                # 分钟线数据（需要更高积分）
                ts_freq = self.TIMEFRAME_MAP.get(timeframe)
                if not ts_freq:
                    raise ValueError(f"不支持的时间周期: {timeframe}")

                df = await loop.run_in_executor(
                    None,
                    lambda: self.pro_api.ft_mins(
                        ts_code=ts_code,
                        start_date=start_str,
                        end_date=end_str,
                        freq=ts_freq,
                    )
                )

            if df is None or df.empty:
                logger.warning(
                    f"⚠️ 未获取到数据: {symbol}.{exchange.value} "
                    f"({start_date.date()} 到 {end_date.date()})"
                )
                return []

            # 转换为 MarketData 对象
            return self._convert_dataframe_to_market_data(
                df, symbol, exchange, timeframe
            )

        except Exception as e:
            logger.error(f"❌ 获取市场数据失败: {e}")
            raise

    def _convert_dataframe_to_market_data(
        self,
        df: "pd.DataFrame",
        symbol: str,
        exchange: Exchange,
        timeframe: TimeFrame,
    ) -> list[MarketData]:
        """
        将 Tushare DataFrame 转换为 MarketData 列表

        教学要点：
        1. DataFrame 遍历的最佳实践
        2. 类型转换和验证
        3. 数据清洗（处理 NaN、0 值等）
        """
        market_data_list = []
        collected_at = datetime.now()

        for _, row in df.iterrows():
            try:
                # 解析日期时间
                if "trade_time" in row:
                    # 分钟线数据
                    dt = datetime.strptime(
                        f"{row['trade_date']} {row['trade_time']}",
                        "%Y%m%d %H:%M:%S"
                    )
                else:
                    # 日线数据
                    dt = datetime.strptime(str(row["trade_date"]), "%Y%m%d")

                # 创建 MarketData 对象
                market_data = MarketData(
                    symbol=symbol,
                    exchange=exchange,
                    datetime=dt,
                    timeframe=timeframe,
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=int(row["vol"]),
                    open_interest=int(row.get("oi", 0)) if pd.notna(row.get("oi")) else None,
                    turnover=Decimal(str(row.get("amount", 0))) if pd.notna(row.get("amount")) else None,
                    source=DataSource.TUSHARE,
                    collected_at=collected_at,
                )

                market_data_list.append(market_data)

            except Exception as e:
                logger.warning(f"⚠️ 跳过无效数据行: {e}")
                continue

        logger.info(
            f"✅ 转换完成: {len(market_data_list)} 条 {symbol}.{exchange.value} "
            f"{timeframe.value} 数据"
        )
        return market_data_list

    @retry_async(RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        strategy=RetryStrategy.EXPONENTIAL,
    ))
    async def fetch_contract_info(
        self,
        symbol: str | None = None,
        exchange: Exchange | None = None,
    ) -> list[ContractInfo]:
        """
        获取合约信息

        教学要点：
        1. 缓存策略的实现
        2. 可选参数的处理逻辑
        3. 批量数据的过滤
        4. 自动重试机制 (新增)
        """
        if not self.is_connected:
            raise RuntimeError("未连接到 Tushare API")

        # 生成缓存键
        cache_key = f"{symbol or 'all'}_{exchange.value if exchange else 'all'}"

        # 检查缓存
        if cache_key in self._contract_cache:
            logger.debug(f"📦 使用缓存的合约信息: {cache_key}")
            return self._contract_cache[cache_key]

        await self._rate_limit_check()

        try:
            loop = asyncio.get_event_loop()

            # 构建查询参数
            params = {}
            if exchange:
                params["exchange"] = self.EXCHANGE_MAP[exchange]
            if symbol:
                # Tushare 合约查询需要完整代码
                if exchange:
                    params["fut_code"] = symbol.upper()

            # 获取期货基本信息
            df = await loop.run_in_executor(
                None,
                lambda: self.pro_api.fut_basic(**params)
            )

            if df is None or df.empty:
                logger.warning(f"⚠️ 未获取到合约信息")
                return []

            # 转换为 ContractInfo 对象
            contracts = self._convert_dataframe_to_contract_info(df)

            # 缓存结果
            self._contract_cache[cache_key] = contracts

            return contracts

        except Exception as e:
            logger.error(f"❌ 获取合约信息失败: {e}")
            raise

    def _convert_dataframe_to_contract_info(
        self,
        df: "pd.DataFrame",
    ) -> list[ContractInfo]:
        """转换 DataFrame 到 ContractInfo"""
        contracts = []

        for _, row in df.iterrows():
            try:
                ts_code = row["ts_code"]
                symbol, exchange = self._convert_symbol_from_tushare(ts_code)

                # 提取标的代码（去除数字）
                underlying = re.sub(r'\d+', '', symbol)

                contract = ContractInfo(
                    symbol=symbol,
                    name=row.get("name", symbol),
                    exchange=exchange,
                    underlying=underlying,
                    multiplier=int(row.get("per_unit", 1)),
                    price_tick=Decimal(str(row.get("quote_unit", 0.01))),
                    list_date=datetime.strptime(str(row["list_date"]), "%Y%m%d")
                    if pd.notna(row.get("list_date")) else datetime.now(),
                    expire_date=datetime.strptime(str(row["delist_date"]), "%Y%m%d")
                    if pd.notna(row.get("delist_date")) else datetime.now() + timedelta(days=365),
                    delivery_month=symbol[-4:],  # 最后4位通常是年月
                )

                contracts.append(contract)

            except Exception as e:
                logger.warning(f"⚠️ 跳过无效合约: {e}")
                continue

        logger.info(f"✅ 转换完成: {len(contracts)} 个合约")
        return contracts

    @retry_async(RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        strategy=RetryStrategy.EXPONENTIAL,
    ))
    async def fetch_trading_calendar(
        self,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TradingDay]:
        """
        获取交易日历

        教学要点：
        1. 日历数据的重要性
        2. 缓存键的设计
        3. 日期序列的处理
        4. 自动重试机制 (新增)
        """
        if not self.is_connected:
            raise RuntimeError("未连接到 Tushare API")

        # 缓存键
        cache_key = f"{exchange.value}_{start_date.date()}_{end_date.date()}"
        if cache_key in self._calendar_cache:
            logger.debug(f"📦 使用缓存的交易日历: {cache_key}")
            return self._calendar_cache[cache_key]

        await self._rate_limit_check()

        try:
            loop = asyncio.get_event_loop()

            df = await loop.run_in_executor(
                None,
                lambda: self.pro_api.trade_cal(
                    exchange=self.EXCHANGE_MAP[exchange],
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                )
            )

            if df is None or df.empty:
                return []

            # 转换为 TradingDay 对象
            trading_days = []
            for _, row in df.iterrows():
                cal_date = datetime.strptime(str(row["cal_date"]), "%Y%m%d")
                is_trading = row["is_open"] == 1

                trading_day = TradingDay(
                    date=cal_date,
                    exchange=exchange,
                    is_trading=is_trading,
                )
                trading_days.append(trading_day)

            # 计算前后交易日
            self._calculate_adjacent_trading_days(trading_days)

            # 缓存
            self._calendar_cache[cache_key] = trading_days

            logger.info(
                f"✅ 获取交易日历: {len(trading_days)} 天 "
                f"({start_date.date()} 到 {end_date.date()})"
            )
            return trading_days

        except Exception as e:
            logger.error(f"❌ 获取交易日历失败: {e}")
            raise

    def _calculate_adjacent_trading_days(self, trading_days: list[TradingDay]) -> None:
        """
        计算每个交易日的前后交易日

        教学要点：
        1. 列表遍历优化
        2. 日期序列处理
        """
        # 提取交易日
        trading_dates = [td.date for td in trading_days if td.is_trading]

        for i, td in enumerate(trading_days):
            if not td.is_trading:
                continue

            # 查找在 trading_dates 中的索引
            idx = trading_dates.index(td.date)

            if idx > 0:
                td.pre_trading_date = trading_dates[idx - 1]
            if idx < len(trading_dates) - 1:
                td.next_trading_date = trading_dates[idx + 1]

    def __repr__(self) -> str:
        """字符串表示"""
        status = "connected" if self._connected else "disconnected"
        return (
            f"<TushareCollector(token={'***' if self.token else 'None'}, "
            f"limit={self.call_limit_per_minute}/min, {status})>"
        )
