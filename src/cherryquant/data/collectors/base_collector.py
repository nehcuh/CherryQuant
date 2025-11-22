"""
基础数据采集器抽象类

定义数据采集的标准接口，所有具体采集器必须实现这些方法。
这个设计参考了 QuantBox 的架构，但简化为教学友好的版本。
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum


class DataSource(Enum):
    """数据源枚举"""
    TUSHARE = "tushare"
    VNPY = "vnpy"
    QUANTBOX = "quantbox"
    GOLDMINER = "goldminer"
    CUSTOM = "custom"


class Exchange(Enum):
    """交易所枚举"""
    # 期货交易所
    SHFE = "SHFE"    # 上海期货交易所
    DCE = "DCE"      # 大连商品交易所
    CZCE = "CZCE"    # 郑州商品交易所
    CFFEX = "CFFEX"  # 中国金融期货交易所
    INE = "INE"      # 上海国际能源交易中心
    GFEX = "GFEX"    # 广州期货交易所
    # 股票交易所
    SHSE = "SHSE"    # 上海证券交易所
    SZSE = "SZSE"    # 深圳证券交易所
    BSE = "BSE"      # 北京证券交易所


class TimeFrame(Enum):
    """时间周期枚举"""
    TICK = "tick"
    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    HOUR_1 = "1h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


@dataclass
class MarketData:
    """
    标准化市场数据结构

    这个数据类定义了系统中所有市场数据的标准格式，
    无论来自哪个数据源，都会被转换成这个格式。
    """
    symbol: str              # 合约代码，如 "rb2501"
    exchange: Exchange       # 交易所
    datetime: datetime       # 时间戳
    timeframe: TimeFrame     # 时间周期

    # OHLCV 数据
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    # 期货特有数据
    open_interest: int | None = None  # 持仓量
    turnover: Decimal | None = None   # 成交额

    # 元数据
    source: DataSource = DataSource.CUSTOM
    collected_at: datetime | None = None  # 采集时间

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式（用于存储）"""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "datetime": self.datetime,
            "timeframe": self.timeframe.value,
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": self.volume,
            "open_interest": self.open_interest,
            "turnover": float(self.turnover) if self.turnover else None,
            "source": self.source.value,
            "collected_at": self.collected_at or datetime.now(),
        }

    @property
    def full_symbol(self) -> str:
        """返回完整的合约代码，如 "rb2501.SHFE" """
        return f"{self.symbol}.{self.exchange.value}"


@dataclass
class ContractInfo:
    """
    合约元数据

    存储期货合约的基本信息和交易规则。
    """
    symbol: str              # 合约代码
    name: str                # 合约名称，如 "螺纹钢2501"
    exchange: Exchange       # 交易所
    underlying: str          # 标的代码，如 "rb"

    # 合约规格
    multiplier: int          # 合约乘数
    price_tick: Decimal      # 最小变动价位

    # 日期信息
    list_date: datetime      # 上市日期
    expire_date: datetime    # 到期日期
    delivery_month: str      # 交割月份，如 "2501"

    # 交易规则
    margin_rate: Decimal | None = None  # 保证金率
    is_main_contract: bool = False  # 是否为主力合约

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "exchange": self.exchange.value,
            "underlying": self.underlying,
            "multiplier": self.multiplier,
            "price_tick": float(self.price_tick),
            "list_date": self.list_date,
            "expire_date": self.expire_date,
            "delivery_month": self.delivery_month,
            "margin_rate": float(self.margin_rate) if self.margin_rate else None,
            "is_main_contract": self.is_main_contract,
        }

    @property
    def is_active(self) -> bool:
        """判断合约是否仍在交易"""
        return datetime.now() < self.expire_date


@dataclass
class TradingDay:
    """交易日信息"""
    date: datetime
    exchange: Exchange
    is_trading: bool         # 是否为交易日
    pre_trading_date: datetime | None = None  # 上一个交易日
    next_trading_date: datetime | None = None  # 下一个交易日


class BaseCollector(ABC):
    """
    数据采集器抽象基类

    教学要点：
    1. 抽象基类的设计原则
    2. 接口隔离和依赖倒置
    3. 异步编程模式
    4. 错误处理策略
    """

    def __init__(self, source: DataSource):
        """
        初始化采集器

        Args:
            source: 数据源类型
        """
        self.source = source
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """
        连接到数据源

        Returns:
            bool: 连接是否成功

        教学要点：异步连接处理，资源管理
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        断开数据源连接

        教学要点：资源清理，优雅关闭
        """
        pass

    @abstractmethod
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

        Args:
            symbol: 合约代码
            exchange: 交易所
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间周期

        Returns:
            list[MarketData]: 市场数据列表

        教学要点：
        1. 参数验证
        2. 日期范围处理
        3. 数据格式转换
        4. 错误处理和重试
        """
        pass

    @abstractmethod
    async def fetch_contract_info(
        self,
        symbol: str | None = None,
        exchange: Exchange | None = None,
    ) -> list[ContractInfo]:
        """
        获取合约信息

        Args:
            symbol: 合约代码（可选，为None时返回所有合约）
            exchange: 交易所（可选，用于过滤）

        Returns:
            list[ContractInfo]: 合约信息列表

        教学要点：
        1. 可选参数处理
        2. 数据过滤逻辑
        3. 缓存策略
        """
        pass

    @abstractmethod
    async def fetch_trading_calendar(
        self,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TradingDay]:
        """
        获取交易日历

        Args:
            exchange: 交易所
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            list[TradingDay]: 交易日列表

        教学要点：
        1. 日历数据的重要性
        2. 日期计算和处理
        3. 数据缓存优化
        """
        pass

    async def is_trading_day(
        self,
        date: datetime,
        exchange: Exchange,
    ) -> bool:
        """
        判断指定日期是否为交易日

        这是一个便捷方法，内部调用 fetch_trading_calendar。

        Args:
            date: 要查询的日期
            exchange: 交易所

        Returns:
            bool: 是否为交易日
        """
        calendar = await self.fetch_trading_calendar(
            exchange=exchange,
            start_date=date,
            end_date=date,
        )
        if calendar:
            return calendar[0].is_trading
        return False

    def validate_symbol(self, symbol: str) -> bool:
        """
        验证合约代码格式

        教学要点：
        1. 输入验证的重要性
        2. 正则表达式应用
        3. 防御性编程
        """
        if not symbol or not isinstance(symbol, str):
            return False

        # 基本格式验证：字母+数字
        import re
        pattern = r'^[a-zA-Z]+\d{3,4}$'
        return bool(re.match(pattern, symbol))

    def validate_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> bool:
        """
        验证日期范围

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            bool: 日期范围是否有效
        """
        if not start_date or not end_date:
            return False

        if start_date > end_date:
            return False

        # 检查是否超过当前日期
        if end_date > datetime.now():
            return False

        return True

    @property
    def is_connected(self) -> bool:
        """返回连接状态"""
        return self._connected

    def __repr__(self) -> str:
        """字符串表示"""
        status = "connected" if self._connected else "disconnected"
        return f"<{self.__class__.__name__}({self.source.value}, {status})>"
