"""
多时间维度数据管理器
支持月线、周线、日线、小时线、分钟线等多时间框架的数据获取和缓存
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class TimeFrame(Enum):
    """时间周期枚举"""
    MONTHLY = "1M"       # 月线
    WEEKLY = "1W"        # 周线
    DAILY = "1D"         # 日线
    FOUR_HOURLY = "4H"   # 4小时
    HOURLY = "1H"        # 小时线
    THIRTY_MIN = "30m"   # 30分钟
    TEN_MIN = "10m"      # 10分钟
    FIFTEEN_MIN = "15m"  # 15分钟
    FIVE_MIN = "5m"      # 5分钟
    ONE_MIN = "1m"       # 1分钟

@dataclass
class MarketDataPoint:
    """市场数据点"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int = 0
    turnover: float = 0.0

@dataclass
class TechnicalIndicators:
    """技术指标数据"""
    timestamp: datetime

    # 移动平均线
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    ema12: Optional[float] = None
    ema26: Optional[float] = None

    # MACD指标
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None

    # KDJ指标
    kdj_k: Optional[float] = None
    kdj_d: Optional[float] = None
    kdj_j: Optional[float] = None

    # RSI指标
    rsi: Optional[float] = None

    # 布林带
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None

    # 其他指标
    atr: Optional[float] = None
    cci: Optional[float] = None
    williams_r: Optional[float] = None

class TimeFrameDataManager:
    """多时间维度数据管理器"""

    def __init__(self, cache_duration_hours: int = 24):
        """
        初始化时间维度数据管理器

        Args:
            cache_duration_hours: 数据缓存时间（小时）
        """
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.data_cache: Dict[str, Dict[TimeFrame, Tuple[pd.DataFrame, datetime]]] = {}
        self.indicators_cache: Dict[str, Dict[TimeFrame, Tuple[List[TechnicalIndicators], datetime]]] = {}

        # 时间周期的数据保留策略
        self.retention_policy = {
            TimeFrame.MONTHLY: 24,       # 保留24个月
            TimeFrame.WEEKLY: 52,        # 保留52周
            TimeFrame.DAILY: 365,        # 保留365天
            TimeFrame.FOUR_HOURLY: 720,  # 保留720个4小时 (30天)
            TimeFrame.HOURLY: 720,       # 保留720小时 (30天)
            TimeFrame.THIRTY_MIN: 2880,  # 保留2880个30分钟 (60天)
            TimeFrame.TEN_MIN: 10080,    # 保留10080个10分钟 (约70天)
            TimeFrame.FIFTEEN_MIN: 5760, # 保留5760个15分钟 (60天)
            TimeFrame.FIVE_MIN: 17280,   # 保留17280个5分钟 (60天)
            TimeFrame.ONE_MIN: 1440      # 保留1440分钟 (24小时)
        }

    async def get_multi_timeframe_data(
        self,
        symbol: str,
        exchange: str,
        timeframes: List[TimeFrame] = None,
        limit: int = None
    ) -> Dict[TimeFrame, pd.DataFrame]:
        """
        获取多时间维度数据

        Args:
            symbol: 合约代码
            exchange: 交易所代码
            timeframes: 需要的时间周期列表
            limit: 数据条数限制

        Returns:
            各时间周期的OHLCV数据
        """
        if timeframes is None:
            timeframes = [TimeFrame.DAILY, TimeFrame.FOUR_HOURLY, TimeFrame.HOURLY, TimeFrame.FIFTEEN_MIN, TimeFrame.FIVE_MIN]

        results = {}
        cache_key = f"{symbol}.{exchange}"

        for timeframe in timeframes:
            try:
                # 检查缓存
                if self._is_cache_valid(cache_key, timeframe):
                    cached_data, _ = self.data_cache[cache_key][timeframe]
                    results[timeframe] = self._apply_limit(cached_data, limit)
                    continue

                # 获取新数据
                fresh_data = await self._fetch_timeframe_data(symbol, exchange, timeframe)
                if fresh_data is not None and not fresh_data.empty:
                    # 更新缓存
                    self.data_cache[cache_key] = self.data_cache.get(cache_key, {})
                    self.data_cache[cache_key][timeframe] = (fresh_data, datetime.now())

                    results[timeframe] = self._apply_limit(fresh_data, limit)
                    logger.info(f"获取{symbol} {timeframe.value}数据: {len(fresh_data)}条")

            except Exception as e:
                logger.error(f"获取{symbol} {timeframe.value}数据失败: {e}")
                # 尝试使用过期缓存
                if cache_key in self.data_cache and timeframe in self.data_cache[cache_key]:
                    cached_data, _ = self.data_cache[cache_key][timeframe]
                    results[timeframe] = self._apply_limit(cached_data, limit)

        return results

    async def get_multi_timeframe_indicators(
        self,
        symbol: str,
        exchange: str,
        timeframes: List[TimeFrame] = None
    ) -> Dict[TimeFrame, List[TechnicalIndicators]]:
        """
        获取多时间维度技术指标

        Args:
            symbol: 合约代码
            exchange: 交易所代码
            timeframes: 需要的时间周期列表

        Returns:
            各时间周期的技术指标数据
        """
        if timeframes is None:
            timeframes = [TimeFrame.DAILY, TimeFrame.FOUR_HOURLY, TimeFrame.HOURLY, TimeFrame.FIFTEEN_MIN]

        # 首先获取OHLCV数据
        ohlcv_data = await self.get_multi_timeframe_data(symbol, exchange, timeframes)

        results = {}
        cache_key = f"{symbol}.{exchange}"

        for timeframe, df in ohlcv_data.items():
            try:
                # 检查指标缓存
                if self._is_indicators_cache_valid(cache_key, timeframe):
                    cached_indicators, _ = self.indicators_cache[cache_key][timeframe]
                    results[timeframe] = cached_indicators
                    continue

                # 计算技术指标
                indicators = self._calculate_all_indicators(df, timeframe)

                # 更新缓存
                self.indicators_cache[cache_key] = self.indicators_cache.get(cache_key, {})
                self.indicators_cache[cache_key][timeframe] = (indicators, datetime.now())

                results[timeframe] = indicators
                logger.info(f"计算{symbol} {timeframe.value}技术指标: {len(indicators)}条")

            except Exception as e:
                logger.error(f"计算{symbol} {timeframe.value}技术指标失败: {e}")

        return results

    async def get_ai_optimized_data(
        self,
        symbol: str,
        exchange: str,
        max_context_points: int = 1000
    ) -> Dict[str, Any]:
        """
        获取AI优化的数据格式

        Args:
            symbol: 合约代码
            exchange: 交易所代码
            max_context_points: 最大上下文数据点数

        Returns:
            AI决策所需的优化数据格式
        """
        try:
            # 获取关键时间周期数据
            key_timeframes = [
                TimeFrame.DAILY,       # 趋势判断
                TimeFrame.FOUR_HOURLY,  # 中期趋势
                TimeFrame.HOURLY,       # 短期趋势
                TimeFrame.FIFTEEN_MIN   # 入场时机
            ]

            ohlcv_data = await self.get_multi_timeframe_data(symbol, exchange, key_timeframes)
            indicators_data = await self.get_multi_timeframe_indicators(symbol, exchange, key_timeframes)

            # 构建AI友好的数据格式
            ai_data = {
                "symbol": f"{symbol}.{exchange}",
                "update_time": datetime.now().isoformat(),
                "trend_analysis": self._analyze_multi_timeframe_trend(ohlcv_data, indicators_data),
                "key_levels": self._identify_key_levels(ohlcv_data.get(TimeFrame.DAILY)),
                "momentum_analysis": self._analyze_momentum(indicators_data),
                "volatility_analysis": self._analyze_volatility(ohlcv_data),
                "recent_price_action": self._summarize_recent_action(ohlcv_data.get(TimeFrame.FIFTEEN_MIN), 50),
                "technical_summary": self._generate_technical_summary(indicators_data),
                "risk_metrics": self._calculate_risk_metrics(ohlcv_data)
            }

            return ai_data

        except Exception as e:
            logger.error(f"获取AI优化数据失败: {e}")
            return {}

    async def _fetch_timeframe_data(
        self,
        symbol: str,
        exchange: str,
        timeframe: TimeFrame
    ) -> Optional[pd.DataFrame]:
        """获取指定时间周期数据"""
        try:
            # 这里应该调用真实的数据源
            # 暂时返回模拟数据
            return self._generate_sample_data(symbol, timeframe)

        except Exception as e:
            logger.error(f"获取{timeframe.value}数据失败: {e}")
            return None

    def _calculate_all_indicators(
        self,
        df: pd.DataFrame,
        timeframe: TimeFrame
    ) -> List[TechnicalIndicators]:
        """计算所有技术指标"""
        indicators = []

        if len(df) < 20:
            return indicators

        try:
            # 计算移动平均线
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma10'] = df['close'].rolling(window=10).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['ma60'] = df['close'].rolling(window=60).mean()

            # 计算EMA
            df['ema12'] = df['close'].ewm(span=12).mean()
            df['ema26'] = df['close'].ewm(span=26).mean()

            # 计算MACD
            df['macd'] = df['ema12'] - df['ema26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']

            # 计算RSI
            df['rsi'] = self._calculate_rsi(df['close'], 14)

            # 计算布林带
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            df['bb_std'] = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
            df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)

            # 计算KDJ
            kdj_data = self._calculate_kdj(df['high'], df['low'], df['close'])
            df['kdj_k'] = kdj_data['k']
            df['kdj_d'] = kdj_data['d']
            df['kdj_j'] = kdj_data['j']

            # 计算ATR
            df['atr'] = self._calculate_atr(df['high'], df['low'], df['close'], 14)

            # 生成指标对象
            for i in range(len(df)):
                if pd.isna(df.iloc[i]['ma20']):  # 跳过数据不足的行
                    continue

                indicator = TechnicalIndicators(
                    timestamp=df.iloc[i]['timestamp'] if 'timestamp' in df.columns else df.index[i],
                    ma5=df.iloc[i]['ma5'],
                    ma10=df.iloc[i]['ma10'],
                    ma20=df.iloc[i]['ma20'],
                    ma60=df.iloc[i]['ma60'] if not pd.isna(df.iloc[i]['ma60']) else None,
                    ema12=df.iloc[i]['ema12'],
                    ema26=df.iloc[i]['ema26'],
                    macd=df.iloc[i]['macd'],
                    macd_signal=df.iloc[i]['macd_signal'],
                    macd_histogram=df.iloc[i]['macd_histogram'],
                    rsi=df.iloc[i]['rsi'],
                    bb_upper=df.iloc[i]['bb_upper'],
                    bb_middle=df.iloc[i]['bb_middle'],
                    bb_lower=df.iloc[i]['bb_lower'],
                    kdj_k=df.iloc[i]['kdj_k'],
                    kdj_d=df.iloc[i]['kdj_d'],
                    kdj_j=df.iloc[i]['kdj_j'],
                    atr=df.iloc[i]['atr']
                )
                indicators.append(indicator)

        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")

        return indicators

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9) -> Dict[str, pd.Series]:
        """计算KDJ指标"""
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()

        rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
        k = rsv.ewm(com=2).mean()
        d = k.ewm(com=2).mean()
        j = 3 * k - 2 * d

        return {'k': k, 'd': d, 'j': j}

    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """计算ATR（平均真实范围）"""
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    def _is_cache_valid(self, cache_key: str, timeframe: TimeFrame) -> bool:
        """检查数据缓存是否有效"""
        if cache_key not in self.data_cache:
            return False
        if timeframe not in self.data_cache[cache_key]:
            return False

        _, last_update = self.data_cache[cache_key][timeframe]
        return datetime.now() - last_update < self.cache_duration

    def _is_indicators_cache_valid(self, cache_key: str, timeframe: TimeFrame) -> bool:
        """检查指标缓存是否有效"""
        if cache_key not in self.indicators_cache:
            return False
        if timeframe not in self.indicators_cache[cache_key]:
            return False

        _, last_update = self.indicators_cache[cache_key][timeframe]
        return datetime.now() - last_update < self.cache_duration

    def _apply_limit(self, df: pd.DataFrame, limit: Optional[int]) -> pd.DataFrame:
        """应用数据条数限制"""
        if limit is not None and len(df) > limit:
            return df.tail(limit)
        return df

    def _generate_sample_data(self, symbol: str, timeframe: TimeFrame) -> pd.DataFrame:
        """生成示例数据"""
        import random

        # 根据时间周期确定数据点数量
        data_points = {
            TimeFrame.MONTHLY: 24,
            TimeFrame.WEEKLY: 52,
            TimeFrame.DAILY: 365,
            TimeFrame.FOUR_HOURLY: 720,
            TimeFrame.HOURLY: 720,
            TimeFrame.THIRTY_MIN: 2880,
            TimeFrame.TEN_MIN: 10080,
            TimeFrame.FIFTEEN_MIN: 5760,
            TimeFrame.FIVE_MIN: 17280,
            TimeFrame.ONE_MIN: 1440
        }

        points = data_points.get(timeframe, 100)
        base_price = 3500 if symbol == 'rb' else 68000 if symbol == 'cu' else 780

        # 生成时间序列
        end_time = datetime.now()
        if timeframe == TimeFrame.MONTHLY:
            freq = 'M'
        elif timeframe == TimeFrame.WEEKLY:
            freq = 'W'
        elif timeframe == TimeFrame.DAILY:
            freq = 'D'
        elif timeframe in [TimeFrame.FOUR_HOURLY, TimeFrame.HOURLY]:
            freq = '4h' if timeframe == TimeFrame.FOUR_HOURLY else 'h'
        else:
            if timeframe == TimeFrame.TEN_MIN:
                freq = '10min'
            elif timeframe == TimeFrame.FIFTEEN_MIN:
                freq = '15min'
            else:
                freq = '5min'

        timestamps = pd.date_range(end=end_time, periods=points, freq=freq)

        # 生成OHLCV数据
        data = []
        price = base_price

        for i, timestamp in enumerate(timestamps):
            # 模拟价格变动
            change = random.uniform(-0.02, 0.02)
            price = price * (1 + change)

            high = price * random.uniform(1.0, 1.01)
            low = price * random.uniform(0.99, 1.0)
            close = price
            open_price = price * random.uniform(0.995, 1.005)

            volume = random.randint(10000, 100000)

            data.append({
                'timestamp': timestamp,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })

        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)

        return df

    def _analyze_multi_timeframe_trend(
        self,
        ohlcv_data: Dict[TimeFrame, pd.DataFrame],
        indicators_data: Dict[TimeFrame, List[TechnicalIndicators]]
    ) -> Dict[str, Any]:
        """分析多时间框架趋势"""
        trend_analysis = {}

        for timeframe in [TimeFrame.DAILY, TimeFrame.FOUR_HOURLY, TimeFrame.HOURLY]:
            if timeframe in ohlcv_data and not ohlcv_data[timeframe].empty:
                df = ohlcv_data[timeframe]

                # 趋势判断
                current_price = df['close'].iloc[-1]
                ma20 = df['close'].rolling(20).mean().iloc[-1]
                ma60 = df['close'].rolling(60).mean().iloc[-1] if len(df) >= 60 else None

                trend_strength = "neutral"
                if current_price > ma20:
                    if ma60 and ma20 > ma60:
                        trend_strength = "strong_bullish"
                    else:
                        trend_strength = "bullish"
                elif current_price < ma20:
                    if ma60 and ma20 < ma60:
                        trend_strength = "strong_bearish"
                    else:
                        trend_strength = "bearish"

                trend_analysis[timeframe.value] = {
                    "trend": trend_strength,
                    "current_price": current_price,
                    "ma20": ma20,
                    "ma60": ma60,
                    "price_vs_ma20_pct": ((current_price - ma20) / ma20) * 100 if ma20 else 0
                }

        return trend_analysis

    def _identify_key_levels(self, df: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """识别关键价位"""
        if df is None or df.empty:
            return {}

        recent_data = df.tail(100)  # 最近100个数据点

        current_price = df['close'].iloc[-1]
        resistance_levels = []
        support_levels = []

        # 寻找支撑阻力位
        highs = recent_data['high']
        lows = recent_data['low']

        # 简化的支撑阻力位识别
        for i in range(2, len(highs) - 2):
            # 局部高点作为阻力位
            if highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i-2] and \
               highs.iloc[i] > highs.iloc[i+1] and highs.iloc[i] > highs.iloc[i+2]:
                if highs.iloc[i] > current_price:
                    resistance_levels.append(highs.iloc[i])

            # 局部低点作为支撑位
            if lows.iloc[i] < lows.iloc[i-1] and lows.iloc[i] < lows.iloc[i-2] and \
               lows.iloc[i] < lows.iloc[i+1] and lows.iloc[i] < lows.iloc[i+2]:
                if lows.iloc[i] < current_price:
                    support_levels.append(lows.iloc[i])

        return {
            "current_price": current_price,
            "resistance_levels": sorted(resistance_levels)[-3:],  # 最近3个阻力位
            "support_levels": sorted(support_levels)[:3],          # 最近3个支撑位
            "recent_high": recent_data['high'].max(),
            "recent_low": recent_data['low'].min()
        }

    def _analyze_momentum(self, indicators_data: Dict[TimeFrame, List[TechnicalIndicators]]) -> Dict[str, Any]:
        """分析动能指标"""
        momentum_analysis = {}

        for timeframe, indicators in indicators_data.items():
            if not indicators:
                continue

            latest = indicators[-1]
            prev = indicators[-2] if len(indicators) >= 2 else latest

            momentum_analysis[timeframe.value] = {
                "rsi": latest.rsi,
                "rsi_trend": "rising" if latest.rsi and prev.rsi and latest.rsi > prev.rsi else "falling",
                "macd": latest.macd,
                "macd_signal": latest.macd_signal,
                "macd_histogram": latest.macd_histogram,
                "kdj_k": latest.kdj_k,
                "kdj_d": latest.kdj_d,
                "kdj_j": latest.kdj_j,
                "momentum_strength": self._assess_momentum_strength(latest)
            }

        return momentum_analysis

    def _assess_momentum_strength(self, indicator: TechnicalIndicators) -> str:
        """评估动能强度"""
        strength_scores = []

        # RSI评估
        if indicator.rsi:
            if indicator.rsi > 70:
                strength_scores.append(("overbought", -1))
            elif indicator.rsi < 30:
                strength_scores.append(("oversold", 1))
            elif 50 < indicator.rsi < 70:
                strength_scores.append(("bullish", 1))
            elif 30 < indicator.rsi < 50:
                strength_scores.append(("bearish", -1))

        # MACD评估
        if indicator.macd and indicator.macd_signal:
            if indicator.macd > indicator.macd_signal and indicator.macd_histogram > 0:
                strength_scores.append(("macd_bullish", 1))
            elif indicator.macd < indicator.macd_signal and indicator.macd_histogram < 0:
                strength_scores.append(("macd_bearish", -1))

        # KDJ评估
        if indicator.kdj_k and indicator.kdj_d:
            if indicator.kdj_k > indicator.kdj_d and indicator.kdj_k < 80:
                strength_scores.append(("kdj_bullish", 1))
            elif indicator.kdj_k < indicator.kdj_d and indicator.kdj_k > 20:
                strength_scores.append(("kdj_bearish", -1))

        # 综合评分
        total_score = sum(score for _, score in strength_scores)

        if total_score >= 2:
            return "strong_bullish"
        elif total_score >= 1:
            return "bullish"
        elif total_score <= -2:
            return "strong_bearish"
        elif total_score <= -1:
            return "bearish"
        else:
            return "neutral"

    def _analyze_volatility(self, ohlcv_data: Dict[TimeFrame, pd.DataFrame]) -> Dict[str, Any]:
        """分析波动性"""
        volatility_analysis = {}

        for timeframe, df in ohlcv_data.items():
            if len(df) < 20:
                continue

            # 计算价格波动率
            returns = df['close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252) if timeframe in [TimeFrame.DAILY, TimeFrame.WEEKLY, TimeFrame.MONTHLY] else returns.std() * 100

            # ATR作为波动率指标
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(14).mean().iloc[-1]
            atr_pct = (atr / df['close'].iloc[-1]) * 100

            volatility_analysis[timeframe.value] = {
                "volatility": volatility,
                "atr": atr,
                "atr_percentage": atr_pct,
                "volatility_regime": self._classify_volatility(atr_pct)
            }

        return volatility_analysis

    def _classify_volatility(self, atr_pct: float) -> str:
        """分类波动率状态"""
        if atr_pct > 3:
            return "high"
        elif atr_pct > 1.5:
            return "medium"
        else:
            return "low"

    def _summarize_recent_action(self, df: Optional[pd.DataFrame], lookback: int = 50) -> Dict[str, Any]:
        """总结近期价格行为"""
        if df is None or df.empty or len(df) < lookback:
            return {}

        recent = df.tail(lookback)
        current_price = df['close'].iloc[-1]

        # 价格变化
        price_change = current_price - recent['close'].iloc[0]
        price_change_pct = (price_change / recent['close'].iloc[0]) * 100

        # 成交量分析
        avg_volume = recent['volume'].mean()
        recent_volume = recent['volume'].tail(10).mean()
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1

        # 波动性
        price_range = recent['high'].max() - recent['low'].min()
        price_range_pct = (price_range / recent['close'].mean()) * 100

        return {
            "price_change": price_change,
            "price_change_pct": price_change_pct,
            "current_price": current_price,
            "period_high": recent['high'].max(),
            "period_low": recent['low'].min(),
            "avg_volume": avg_volume,
            "recent_volume_ratio": volume_ratio,
            "price_range_pct": price_range_pct,
            "action_type": "trending_up" if price_change_pct > 2 else "trending_down" if price_change_pct < -2 else "sideways"
        }

    def _generate_technical_summary(self, indicators_data: Dict[TimeFrame, List[TechnicalIndicators]]) -> Dict[str, Any]:
        """生成技术分析摘要"""
        summary = {
            "overall_signal": "neutral",
            "confidence": 0.0,
            "key_timeframes": {},
            "signal_strength": {}
        }

        signal_counts = {"bullish": 0, "bearish": 0, "neutral": 0}

        for timeframe, indicators in indicators_data.items():
            if not indicators:
                continue

            latest = indicators[-1]

            # 生成时间框架信号
            timeframe_signal = self._generate_timeframe_signal(latest)
            signal_counts[timeframe_signal] += 1

            summary["key_timeframes"][timeframe.value] = {
                "signal": timeframe_signal,
                "rsi": latest.rsi,
                "macd_above_signal": latest.macd > latest.macd_signal if latest.macd and latest.macd_signal else False,
                "price_above_ma20": True,  # 需要从价格数据计算
                "momentum": latest.macd_histogram if latest.macd_histogram else 0
            }

        # 确定总体信号
        total_signals = sum(signal_counts.values())
        if total_signals > 0:
            if signal_counts["bullish"] > signal_counts["bearish"] and signal_counts["bullish"] > signal_counts["neutral"]:
                summary["overall_signal"] = "bullish"
                summary["confidence"] = signal_counts["bullish"] / total_signals
            elif signal_counts["bearish"] > signal_counts["bullish"] and signal_counts["bearish"] > signal_counts["neutral"]:
                summary["overall_signal"] = "bearish"
                summary["confidence"] = signal_counts["bearish"] / total_signals

        return summary

    def _generate_timeframe_signal(self, indicator: TechnicalIndicators) -> str:
        """生成单个时间框架的信号"""
        signals = []

        # RSI信号
        if indicator.rsi:
            if indicator.rsi > 70:
                signals.append(("sell", -1))
            elif indicator.rsi < 30:
                signals.append(("buy", 1))
            elif 50 < indicator.rsi < 70:
                signals.append(("buy", 0.5))
            elif 30 < indicator.rsi < 50:
                signals.append(("sell", -0.5))

        # MACD信号
        if indicator.macd and indicator.macd_signal and indicator.macd_histogram:
            if indicator.macd > indicator.macd_signal and indicator.macd_histogram > 0:
                signals.append(("buy", 1))
            elif indicator.macd < indicator.macd_signal and indicator.macd_histogram < 0:
                signals.append(("sell", -1))

        # KDJ信号
        if indicator.kdj_k and indicator.kdj_d:
            if indicator.kdj_k > indicator.kdj_d and indicator.kdj_k < 80:
                signals.append(("buy", 0.5))
            elif indicator.kdj_k < indicator.kdj_d and indicator.kdj_k > 20:
                signals.append(("sell", -0.5))

        # 综合信号
        total_score = sum(score for _, score in signals)

        if total_score >= 1.5:
            return "bullish"
        elif total_score >= 0.5:
            return "bullish"
        elif total_score <= -1.5:
            return "bearish"
        elif total_score <= -0.5:
            return "bearish"
        else:
            return "neutral"

    def _calculate_risk_metrics(self, ohlcv_data: Dict[TimeFrame, pd.DataFrame]) -> Dict[str, Any]:
        """计算风险指标"""
        risk_metrics = {}

        if TimeFrame.DAILY in ohlcv_data:
            df = ohlcv_data[TimeFrame.DAILY]

            if len(df) >= 20:
                # 计算最大回撤
                peak = df['close'].expanding().max()
                drawdown = (df['close'] - peak) / peak
                max_drawdown = drawdown.min()

                # 计算波动率
                returns = df['close'].pct_change().dropna()
                volatility = returns.std()

                # 计算夏普比率（简化版）
                avg_return = returns.mean()
                sharpe_ratio = avg_return / volatility if volatility > 0 else 0

                risk_metrics["max_drawdown"] = max_drawdown
                risk_metrics["volatility"] = volatility
                risk_metrics["sharpe_ratio"] = sharpe_ratio
                risk_metrics["risk_level"] = self._assess_risk_level(max_drawdown, volatility)

        return risk_metrics

    def _assess_risk_level(self, max_drawdown: float, volatility: float) -> str:
        """评估风险等级"""
        if max_drawdown < -0.2 or volatility > 0.05:
            return "high"
        elif max_drawdown < -0.1 or volatility > 0.03:
            return "medium"
        else:
            return "low"

    def clear_cache(self):
        """清空缓存"""
        self.data_cache.clear()
        self.indicators_cache.clear()
        logger.info("已清空时间维度数据缓存")

    def get_cache_status(self) -> Dict[str, Any]:
        """获取缓存状态"""
        cache_info = {
            "data_cache_size": sum(len(timeframes) for timeframes in self.data_cache.values()),
            "indicators_cache_size": sum(len(timeframes) for timeframes in self.indicators_cache.values()),
            "cached_symbols": list(self.data_cache.keys()),
            "cache_duration_hours": self.cache_duration.total_seconds() / 3600
        }

        return cache_info

# 全局时间维度数据管理器实例
timeframe_manager = TimeFrameDataManager()