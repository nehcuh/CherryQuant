"""
Technical Analysis Indicators

支持两种接口：
1. pandas.Series (用于生产环境，高性能)
2. list[float] (用于教学和测试，简单直观)

教学要点：
1. 技术指标的数学原理
2. 滑动窗口计算
3. 边界条件处理
"""
from typing import Union
import pandas as pd
import numpy as np


# ==================== List-based implementations (for teaching) ====================

def calculate_ma(prices: Union[pd.Series, list[float]], period: int = 5, window: int = None) -> Union[pd.Series, list[float | None]]:
    """
    Calculate Simple Moving Average (SMA).

    Args:
        prices: Price data (pd.Series or list[float])
        period: MA period (for list interface)
        window: MA window (for pandas interface, backward compatibility)

    Returns:
        MA values (same type as input)

    教学要点：
    - MA是最简单的技术指标
    - 使用滑动窗口计算
    - 前N-1个值为None（数据不足）
    """
    # Pandas interface (backward compatibility)
    if isinstance(prices, pd.Series):
        w = window if window is not None else period
        return prices.rolling(window=w).mean()

    # List interface
    if period <= 0:
        raise ValueError("Period must be positive")

    if not prices:
        return []

    if len(prices) < period:
        return [None] * len(prices)

    result = [None] * (period - 1)

    for i in range(period - 1, len(prices)):
        window_sum = sum(prices[i - period + 1:i + 1])
        result.append(window_sum / period)

    return result


def calculate_ema(prices: list[float], period: int = 12) -> list[float | None]:
    """
    Calculate Exponential Moving Average (EMA).

    Args:
        prices: Price list
        period: EMA period

    Returns:
        EMA values

    教学要点：
    - EMA对近期价格赋予更高权重
    - alpha = 2 / (period + 1)
    - EMA[t] = alpha * price[t] + (1 - alpha) * EMA[t-1]
    """
    if period <= 0:
        raise ValueError("Period must be positive")

    if not prices:
        return []

    if len(prices) < period:
        return [None] * len(prices)

    result = [None] * (period - 1)

    # 初始EMA使用SMA
    first_ema = sum(prices[:period]) / period
    result.append(first_ema)

    # 计算后续EMA
    alpha = 2.0 / (period + 1)
    for i in range(period, len(prices)):
        ema = alpha * prices[i] + (1 - alpha) * result[-1]
        result.append(ema)

    return result


def calculate_rsi(prices: Union[pd.Series, list[float]], period: int = 14) -> Union[pd.Series, list[float | None]]:
    """
    Calculate Relative Strength Index (RSI).

    Args:
        prices: Price data
        period: RSI period

    Returns:
        RSI values (0-100)

    教学要点：
    - RSI衡量价格变动的速度和幅度
    - RSI > 70: 超买
    - RSI < 30: 超卖
    """
    # Pandas interface
    if isinstance(prices, pd.Series):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        loss = loss.replace(0, np.nan)
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    # List interface
    if period <= 0:
        raise ValueError("Period must be positive")

    if not prices or len(prices) <= period:
        return [None] * len(prices)

    # 计算价格变化
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

    # 分离涨跌
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    result = [None] * period

    # 初始平均涨跌
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100 - (100 / (1 + rs)))

    # 后续RSI
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100 - (100 / (1 + rs)))

    return result


def calculate_macd(
    prices: Union[pd.Series, list[float]],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Union[tuple[pd.Series, pd.Series, pd.Series], tuple[list[float | None], list[float | None], list[float | None]]]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Args:
        prices: Price data
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period

    Returns:
        (macd, signal_line, histogram)

    教学要点：
    - MACD = 快线EMA - 慢线EMA
    - Signal = MACD的EMA
    - Histogram = MACD - Signal
    - 金叉：MACD上穿Signal，看涨
    - 死叉：MACD下穿Signal，看跌
    """
    # Pandas interface
    if isinstance(prices, pd.Series):
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return macd, signal_line, histogram

    # List interface
    if not prices or len(prices) < slow + signal:
        n = len(prices) if prices else 0
        return [None] * n, [None] * n, [None] * n

    # 计算快慢EMA
    fast_ema = calculate_ema(prices, fast)
    slow_ema = calculate_ema(prices, slow)

    # 计算MACD线
    macd_line = []
    for i in range(len(prices)):
        if fast_ema[i] is not None and slow_ema[i] is not None:
            macd_line.append(fast_ema[i] - slow_ema[i])
        else:
            macd_line.append(None)

    # 计算Signal线（MACD的EMA）
    # 找到第一个非None的MACD值
    first_valid_idx = slow - 1
    signal_line = [None] * first_valid_idx

    valid_macd = [m for m in macd_line[first_valid_idx:] if m is not None]
    if len(valid_macd) < signal:
        signal_line.extend([None] * len(valid_macd))
    else:
        # 初始signal使用SMA
        first_signal = sum(valid_macd[:signal]) / signal
        signal_line.extend([None] * (signal - 1))
        signal_line.append(first_signal)

        # 后续signal使用EMA
        alpha = 2.0 / (signal + 1)
        for i in range(signal, len(valid_macd)):
            sig = alpha * valid_macd[i] + (1 - alpha) * signal_line[-1]
            signal_line.append(sig)

    # 计算Histogram
    histogram = []
    for i in range(len(prices)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram.append(macd_line[i] - signal_line[i])
        else:
            histogram.append(None)

    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    prices: list[float],
    period: int = 20,
    std_dev: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """
    Calculate Bollinger Bands.

    Args:
        prices: Price list
        period: Period for MA and std
        std_dev: Number of standard deviations

    Returns:
        (upper_band, middle_band, lower_band)

    教学要点：
    - 中轨 = SMA
    - 上轨 = SMA + std_dev * STD
    - 下轨 = SMA - std_dev * STD
    - 布林带收窄：波动率降低
    - 布林带扩张：波动率增加
    """
    if period <= 0:
        raise ValueError("Period must be positive")

    if not prices or len(prices) < period:
        n = len(prices) if prices else 0
        return [None] * n, [None] * n, [None] * n

    # 计算中轨（MA）
    middle_band = calculate_ma(prices, period=period)

    # 计算上下轨
    upper_band = [None] * (period - 1)
    lower_band = [None] * (period - 1)

    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1:i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5

        upper_band.append(mean + std_dev * std)
        lower_band.append(mean - std_dev * std)

    return upper_band, middle_band, lower_band


def calculate_atr(
    high: list[float],
    low: list[float],
    close: list[float],
    period: int = 14
) -> list[float | None]:
    """
    Calculate Average True Range (ATR).

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period

    Returns:
        ATR values

    教学要点：
    - ATR衡量价格波动性
    - True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
    - ATR = TR的移动平均
    """
    if period <= 0:
        raise ValueError("Period must be positive")

    if not high:
        return []

    if len(high) != len(low) or len(high) != len(close):
        raise ValueError("high, low, and close lengths must match")

    if len(high) < period:
        return [None] * len(high)

    # 计算True Range
    tr_list = [high[0] - low[0]]  # 第一天的TR

    for i in range(1, len(high)):
        h_l = high[i] - low[i]
        h_pc = abs(high[i] - close[i-1])
        l_pc = abs(low[i] - close[i-1])
        tr = max(h_l, h_pc, l_pc)
        tr_list.append(tr)

    # 计算ATR（使用Wilder's smoothing，类似EMA）
    result = [None] * (period - 1)

    # 初始ATR使用SMA
    first_atr = sum(tr_list[:period]) / period
    result.append(first_atr)

    # 后续ATR
    for i in range(period, len(tr_list)):
        atr = (result[-1] * (period - 1) + tr_list[i]) / period
        result.append(atr)

    return result
