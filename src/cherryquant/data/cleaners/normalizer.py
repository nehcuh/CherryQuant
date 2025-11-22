"""
数据标准化器

将来自不同数据源的数据转换为统一格式。

教学要点：
1. 数据标准化的必要性
2. 符号映射和转换
3. 格式统一策略
4. 缺失值填充方法
"""

import logging
import re
from typing import Any
from decimal import Decimal
from datetime import datetime, timedelta

from cherryquant.data.collectors.base_collector import (
    MarketData,
    Exchange,
    TimeFrame,
    ContractInfo,
)

logger = logging.getLogger(__name__)


class DataNormalizer:
    """
    数据标准化器

    主要功能：
    1. 符号标准化：统一合约代码格式
    2. 时区处理：统一时间戳格式
    3. 数值处理：精度统一、单位转换
    4. 缺失值填充：前向填充、插值等方法

    教学要点：
    1. 为什么需要标准化
    2. 不同数据源的差异
    3. 标准化策略的权衡
    """

    # 交易所符号映射表
    EXCHANGE_ALIASES = {
        # 上期所
        "SHFE": ["SHF", "shfe", "shf", "上期所"],
        # 大商所
        "DCE": ["DCE", "dce", "大商所"],
        # 郑商所
        "CZCE": ["ZCE", "CZCE", "czce", "zce", "郑商所"],
        # 中金所
        "CFFEX": ["CFX", "CFFEX", "cffex", "cfx", "中金所"],
        # 能源中心
        "INE": ["INE", "ine", "能源中心"],
    }

    # 反向映射
    ALIAS_TO_EXCHANGE = {}
    for exchange, aliases in EXCHANGE_ALIASES.items():
        for alias in aliases:
            ALIAS_TO_EXCHANGE[alias] = exchange

    def __init__(
        self,
        symbol_format: str = "lowercase",  # lowercase, uppercase, mixed
        fill_method: str = "ffill",  # ffill, bfill, interpolate, zero
    ):
        """
        初始化标准化器

        Args:
            symbol_format: 符号格式（lowercase, uppercase, mixed）
            fill_method: 缺失值填充方法
        """
        self.symbol_format = symbol_format
        self.fill_method = fill_method

    def normalize_symbol(
        self,
        symbol: str,
        exchange: Exchange | None = None,
    ) -> str:
        """
        标准化合约代码

        支持多种输入格式：
        - rb2501
        - RB2501
        - rb2501.SHFE
        - RB2501.SHF

        输出标准格式：rb2501

        Args:
            symbol: 原始合约代码
            exchange: 交易所（可选）

        Returns:
            str: 标准化的合约代码

        教学要点：
        1. 字符串处理技巧
        2. 正则表达式应用
        3. 格式统一的重要性
        """
        if not symbol:
            return ""

        # 移除交易所后缀（如果有）
        if "." in symbol:
            symbol = symbol.split(".")[0]

        # 移除空格
        symbol = symbol.strip()

        # 根据配置格式化
        if self.symbol_format == "lowercase":
            symbol = symbol.lower()
        elif self.symbol_format == "uppercase":
            symbol = symbol.upper()
        # mixed 保持原样

        # 验证格式
        pattern = r'^[a-zA-Z]+\d{3,4}$'
        if not re.match(pattern, symbol):
            logger.warning(f"⚠️ 符号格式可能不正确: {symbol}")

        return symbol

    def normalize_exchange(self, exchange_str: str) -> Exchange:
        """
        标准化交易所代码

        Args:
            exchange_str: 交易所字符串（可能是各种别名）

        Returns:
            Exchange: 标准化的交易所枚举

        教学要点：
        1. 枚举类型的使用
        2. 映射表查找
        3. 错误处理
        """
        # 查找别名映射
        standard = self.ALIAS_TO_EXCHANGE.get(exchange_str)

        if not standard:
            # 尝试直接匹配枚举
            try:
                return Exchange[exchange_str.upper()]
            except KeyError:
                raise ValueError(f"未知的交易所代码: {exchange_str}")

        return Exchange[standard]

    def normalize_timeframe(self, timeframe_str: str) -> TimeFrame:
        """
        标准化时间周期

        支持多种格式：
        - 1min, 1MIN, 1分钟（注意：不支持 1m，避免与月份 1M 混淆）
        - 5m, 5min
        - 1h, 1H, 1hour, 1小时
        - 1d, 1D, 1day, 1日
        - 1M, 1month, month（月份必须用大写 M）

        Args:
            timeframe_str: 时间周期字符串

        Returns:
            TimeFrame: 标准化的时间周期

        教学要点：
        1. 格式兼容性处理
        2. 字符串匹配策略
        3. 大小写敏感性（月份用大写M）
        """
        # 先去除空格
        tf = timeframe_str.strip()

        # 首先检查是否是月份（大写 M）- 在转换为小写前检查
        if tf in ["1M", "M"]:
            return TimeFrame.MONTH_1

        # 转换为小写便于匹配其他格式
        tf_lower = tf.lower()

        # 映射表
        mapping = {
            "tick": TimeFrame.TICK,
            "1min": TimeFrame.MIN_1,
            "1分钟": TimeFrame.MIN_1,
            "5m": TimeFrame.MIN_5,
            "5min": TimeFrame.MIN_5,
            "5分钟": TimeFrame.MIN_5,
            "15m": TimeFrame.MIN_15,
            "15min": TimeFrame.MIN_15,
            "15分钟": TimeFrame.MIN_15,
            "30m": TimeFrame.MIN_30,
            "30min": TimeFrame.MIN_30,
            "30分钟": TimeFrame.MIN_30,
            "1h": TimeFrame.HOUR_1,
            "1hour": TimeFrame.HOUR_1,
            "60m": TimeFrame.HOUR_1,
            "60min": TimeFrame.HOUR_1,
            "1小时": TimeFrame.HOUR_1,
            "1d": TimeFrame.DAY_1,
            "1day": TimeFrame.DAY_1,
            "d": TimeFrame.DAY_1,
            "day": TimeFrame.DAY_1,
            "1日": TimeFrame.DAY_1,
            "日": TimeFrame.DAY_1,
            "1w": TimeFrame.WEEK_1,
            "1week": TimeFrame.WEEK_1,
            "w": TimeFrame.WEEK_1,
            "week": TimeFrame.WEEK_1,
            # 月：小写也支持，但推荐使用大写 M
            "1month": TimeFrame.MONTH_1,
            "month": TimeFrame.MONTH_1,
        }

        result = mapping.get(tf_lower)
        if not result:
            # 友好的错误提示
            raise ValueError(
                f"未知的时间周期: {timeframe_str}\n"
                f"提示: 1分钟用 '1min'，1月用 '1M'（大写M）"
            )

        return result

    def normalize_price(self, price: Any, precision: int = 2) -> Decimal:
        """
        标准化价格数据

        Args:
            price: 价格（可能是 float, int, str, Decimal）
            precision: 小数位精度

        Returns:
            Decimal: 标准化的价格

        教学要点：
        1. Decimal vs float 的选择
        2. 浮点数精度问题
        3. 金融计算的最佳实践
        """
        if price is None:
            return Decimal("0")

        # 转换为 Decimal
        if isinstance(price, Decimal):
            dec_price = price
        else:
            dec_price = Decimal(str(price))

        # 四舍五入到指定精度
        quantize_str = "0." + "0" * precision
        return dec_price.quantize(Decimal(quantize_str))

    def fill_missing_data(
        self,
        data_list: list[MarketData],
        expected_timeframe: TimeFrame,
    ) -> list[MarketData]:
        """
        填充缺失的数据点

        对于时间序列数据，可能存在某些时间点的数据缺失。
        此方法根据时间周期和填充策略补全数据。

        Args:
            data_list: 已有的数据列表（按时间排序）
            expected_timeframe: 预期的时间周期

        Returns:
            list[MarketData]: 填充后的完整数据列表

        教学要点：
        1. 时间序列的连续性
        2. 不同填充方法的适用场景
        3. 前向填充 vs 后向填充 vs 插值
        """
        if not data_list:
            return []

        # 按时间排序
        sorted_data = sorted(data_list, key=lambda x: x.datetime)

        # 检测缺失的时间点
        filled_data = []
        timeframe_delta = self._get_timedelta(expected_timeframe)

        for i in range(len(sorted_data)):
            current = sorted_data[i]
            filled_data.append(current)

            # 检查与下一个数据点的时间间隔
            if i < len(sorted_data) - 1:
                next_data = sorted_data[i + 1]
                expected_next_time = current.datetime + timeframe_delta

                # 如果时间间隔大于预期，说明有缺失
                while expected_next_time < next_data.datetime:
                    # 创建填充数据
                    filled_point = self._create_filled_data(
                        current,
                        next_data,
                        expected_next_time,
                    )
                    filled_data.append(filled_point)
                    expected_next_time += timeframe_delta

        if len(filled_data) > len(data_list):
            logger.info(
                f"📊 填充了 {len(filled_data) - len(data_list)} 个缺失数据点"
            )

        return filled_data

    def _get_timedelta(self, timeframe: TimeFrame) -> timedelta:
        """根据时间周期返回 timedelta"""
        mapping = {
            TimeFrame.MIN_1: timedelta(minutes=1),
            TimeFrame.MIN_5: timedelta(minutes=5),
            TimeFrame.MIN_15: timedelta(minutes=15),
            TimeFrame.MIN_30: timedelta(minutes=30),
            TimeFrame.HOUR_1: timedelta(hours=1),
            TimeFrame.DAY_1: timedelta(days=1),
            TimeFrame.WEEK_1: timedelta(weeks=1),
            TimeFrame.MONTH_1: timedelta(days=30),  # 简化处理
        }
        return mapping.get(timeframe, timedelta(days=1))

    def _create_filled_data(
        self,
        prev_data: MarketData,
        next_data: MarketData,
        fill_time: datetime,
    ) -> MarketData:
        """
        创建填充数据点

        根据填充方法选择不同的策略。

        教学要点：
        1. 前向填充（ffill）：使用前一个值
        2. 后向填充（bfill）：使用后一个值
        3. 线性插值（interpolate）：线性计算中间值
        4. 零填充（zero）：使用特殊值
        """
        if self.fill_method == "ffill":
            # 前向填充：使用前一个数据点的值
            return MarketData(
                symbol=prev_data.symbol,
                exchange=prev_data.exchange,
                datetime=fill_time,
                timeframe=prev_data.timeframe,
                open=prev_data.close,
                high=prev_data.close,
                low=prev_data.close,
                close=prev_data.close,
                volume=0,  # 缺失时间段无成交量
                open_interest=prev_data.open_interest,
                turnover=Decimal("0"),
                source=prev_data.source,
            )

        elif self.fill_method == "bfill":
            # 后向填充：使用后一个数据点的值
            return MarketData(
                symbol=next_data.symbol,
                exchange=next_data.exchange,
                datetime=fill_time,
                timeframe=next_data.timeframe,
                open=next_data.open,
                high=next_data.open,
                low=next_data.open,
                close=next_data.open,
                volume=0,
                open_interest=next_data.open_interest,
                turnover=Decimal("0"),
                source=next_data.source,
            )

        elif self.fill_method == "interpolate":
            # 线性插值
            total_time = (next_data.datetime - prev_data.datetime).total_seconds()
            elapsed_time = (fill_time - prev_data.datetime).total_seconds()
            ratio = Decimal(str(elapsed_time / total_time))

            interpolated_price = (
                prev_data.close + (next_data.close - prev_data.close) * ratio
            )

            return MarketData(
                symbol=prev_data.symbol,
                exchange=prev_data.exchange,
                datetime=fill_time,
                timeframe=prev_data.timeframe,
                open=interpolated_price,
                high=interpolated_price,
                low=interpolated_price,
                close=interpolated_price,
                volume=0,
                open_interest=prev_data.open_interest,
                turnover=Decimal("0"),
                source=prev_data.source,
            )

        else:  # zero
            # 使用特殊标记值
            return MarketData(
                symbol=prev_data.symbol,
                exchange=prev_data.exchange,
                datetime=fill_time,
                timeframe=prev_data.timeframe,
                open=Decimal("0"),
                high=Decimal("0"),
                low=Decimal("0"),
                close=Decimal("0"),
                volume=0,
                open_interest=0,
                turnover=Decimal("0"),
                source=prev_data.source,
            )

    def deduplicate(self, data_list: list[MarketData]) -> list[MarketData]:
        """
        去除重复数据

        根据 (symbol, exchange, datetime, timeframe) 组合判断重复。
        保留最后出现的数据（最新）。

        Args:
            data_list: 数据列表

        Returns:
            list[MarketData]: 去重后的数据列表

        教学要点：
        1. 数据去重策略
        2. 字典的使用技巧
        3. 唯一键的设计
        """
        seen = {}
        unique_data = []

        for data in data_list:
            # 生成唯一键
            key = (
                data.symbol,
                data.exchange.value,
                data.datetime,
                data.timeframe.value,
            )

            # 如果已存在，替换为最新的
            if key in seen:
                logger.debug(f"⚠️ 发现重复数据: {key}")

            seen[key] = data

        # 转换为列表并按时间排序
        unique_data = list(seen.values())
        unique_data.sort(key=lambda x: x.datetime)

        if len(unique_data) < len(data_list):
            logger.info(
                f"📊 去重完成: 移除了 {len(data_list) - len(unique_data)} 条重复数据"
            )

        return unique_data

    def normalize_batch(
        self,
        data_list: list[MarketData],
        deduplicate: bool = True,
        fill_missing: bool = False,
    ) -> list[MarketData]:
        """
        批量标准化数据

        组合多个标准化步骤的便捷方法。

        Args:
            data_list: 数据列表
            deduplicate: 是否去重
            fill_missing: 是否填充缺失值

        Returns:
            list[MarketData]: 标准化后的数据列表

        教学要点：
        1. 数据处理管道的组合
        2. 处理步骤的顺序
        3. 可配置的处理流程
        """
        result = data_list

        # 1. 去重
        if deduplicate:
            result = self.deduplicate(result)

        # 2. 填充缺失值
        if fill_missing and result:
            timeframe = result[0].timeframe
            result = self.fill_missing_data(result, timeframe)

        # 3. 符号标准化（已在采集时完成，这里仅作验证）
        for data in result:
            data.symbol = self.normalize_symbol(data.symbol, data.exchange)

        logger.info(f"✅ 批量标准化完成: {len(result)} 条数据")
        return result
