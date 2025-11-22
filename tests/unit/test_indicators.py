"""
技术指标库单元测试

测试范围：
1. 移动平均线 (MA)
2. 相对强弱指标 (RSI)
3. MACD
4. 布林带 (Bollinger Bands)
5. ATR (Average True Range)
6. 边界条件和异常处理

教学要点：
1. TDD 开发流程
2. 参数化测试
3. 浮点数比较
4. 边界条件测试
"""

import pytest
from typing import List, Optional
from src.cherryquant.utils.indicators import (
    calculate_ma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_atr,
)


# ==================== MA 测试 ====================

class TestMovingAverage:
    """测试移动平均线（MA）"""

    def test_ma_basic(self):
        """基本功能测试"""
        prices = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = calculate_ma(prices, period=3)

        # 前两个应该是 None（数据不足）
        assert result[0] is None
        assert result[1] is None

        # 第三个: (10+20+30)/3 = 20
        assert result[2] == pytest.approx(20.0)
        assert result[3] == pytest.approx(30.0)
        assert result[4] == pytest.approx(40.0)

    def test_ma_empty_list(self):
        """边界条件：空列表"""
        assert calculate_ma([], period=3) == []

    def test_ma_insufficient_data(self):
        """边界条件：数据不足"""
        result = calculate_ma([10.0, 20.0], period=3)
        assert result == [None, None]

    def test_ma_period_one(self):
        """边界条件：period=1"""
        prices = [10.0, 20.0, 30.0]
        result = calculate_ma(prices, period=1)
        assert result == prices

    def test_ma_invalid_period_zero(self):
        """异常情况：period=0"""
        with pytest.raises(ValueError, match="Period must be positive"):
            calculate_ma([10.0, 20.0, 30.0], period=0)

    def test_ma_invalid_period_negative(self):
        """异常情况：period为负数"""
        with pytest.raises(ValueError):
            calculate_ma([10.0, 20.0, 30.0], period=-5)

    @pytest.mark.parametrize("period", [5, 10, 20, 50])
    def test_ma_different_periods(self, period):
        """参数化测试：不同周期"""
        prices = [float(i + 100) for i in range(100)]
        result = calculate_ma(prices, period=period)

        # 前 period-1 个应该是 None
        assert all(v is None for v in result[:period-1])
        # 之后都应该有值
        assert all(v is not None for v in result[period-1:])

    def test_ma_floating_point_precision(self):
        """浮点数精度测试"""
        prices = [1.111, 2.222, 3.333]
        result = calculate_ma(prices, period=3)

        expected = (1.111 + 2.222 + 3.333) / 3
        assert result[2] == pytest.approx(expected, rel=1e-9)


# ==================== EMA 测试 ====================

class TestExponentialMovingAverage:
    """测试指数移动平均线（EMA）"""

    def test_ema_basic(self):
        """基本功能测试"""
        prices = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = calculate_ema(prices, period=3)

        # 前 period-1 个是 None
        assert result[0] is None
        assert result[1] is None

        # 第三个是 SMA
        assert result[2] == pytest.approx(20.0)

        # 之后是 EMA
        assert result[3] is not None
        assert result[4] is not None

    def test_ema_vs_ma_difference(self):
        """EMA 应该比 MA 更快反应价格变化"""
        # 价格突然上涨
        prices = [100.0] * 10 + [150.0] * 10

        ma = calculate_ma(prices, period=5)
        ema = calculate_ema(prices, period=5)

        # 在价格上涨后，EMA应该比MA更快上升
        # 检查第15个位置（价格上涨5个周期后）
        assert ema[14] > ma[14]


# ==================== RSI 测试 ====================

class TestRSI:
    """测试相对强弱指标（RSI）"""

    def test_rsi_basic(self):
        """基本功能测试"""
        # 模拟价格：先涨后跌
        prices = [
            100.0, 102.0, 104.0, 103.0, 105.0,  # 前5个
            107.0, 106.0, 108.0, 110.0, 109.0,  # 中间5个
            111.0, 110.0, 108.0, 106.0, 104.0   # 后5个
        ]

        result = calculate_rsi(prices, period=14)

        # RSI 应该在 0-100 之间
        for val in result:
            if val is not None:
                assert 0 <= val <= 100

    def test_rsi_all_rising(self):
        """所有价格上涨 → RSI 应该接近 100"""
        prices = [float(i) for i in range(1, 20)]  # 1, 2, 3, ..., 19
        result = calculate_rsi(prices, period=14)

        # 最后一个 RSI 应该很高（>80）
        assert result[-1] is not None
        assert result[-1] > 80

    def test_rsi_all_falling(self):
        """所有价格下跌 → RSI 应该接近 0"""
        prices = [float(i) for i in range(20, 1, -1)]  # 20, 19, 18, ..., 2
        result = calculate_rsi(prices, period=14)

        # 最后一个 RSI 应该很低（<20）
        assert result[-1] is not None
        assert result[-1] < 20

    def test_rsi_sideways(self):
        """价格横盘 → RSI 应该接近 50"""
        prices = [100.0, 101.0, 99.0, 100.0, 101.0, 99.0, 100.0] * 3
        result = calculate_rsi(prices, period=14)

        # RSI 应该在 40-60 之间
        if result[-1] is not None:
            assert 40 <= result[-1] <= 60

    @pytest.mark.parametrize("period", [5, 14, 21, 50])
    def test_rsi_different_periods(self, period):
        """参数化测试：不同周期"""
        prices = [100.0 + i for i in range(100)]
        result = calculate_rsi(prices, period=period)

        # 前 period 个应该是 None
        assert all(v is None for v in result[:period])
        # 之后都应该有值
        assert all(v is not None for v in result[period:])

    def test_rsi_insufficient_data(self):
        """数据不足"""
        prices = [100.0, 101.0, 102.0]
        result = calculate_rsi(prices, period=14)

        # 所有值都应该是 None
        assert all(v is None for v in result)


# ==================== MACD 测试 ====================

class TestMACD:
    """测试 MACD 指标"""

    def test_macd_basic(self):
        """基本功能测试"""
        prices = [float(i + 100) for i in range(50)]

        macd, signal, histogram = calculate_macd(prices)

        # 长度应该一致
        assert len(macd) == len(prices)
        assert len(signal) == len(prices)
        assert len(histogram) == len(prices)

    def test_macd_components(self):
        """测试 MACD 的组成"""
        prices = [float(i + 100) for i in range(50)]

        macd, signal, histogram = calculate_macd(prices)

        # 找到第一个非 None 的 MACD
        first_valid_idx = next(i for i, v in enumerate(macd) if v is not None)

        # MACD = 快线 - 慢线，应该有符号
        assert macd[first_valid_idx] is not None

        # Histogram = MACD - Signal
        if signal[first_valid_idx] is not None:
            expected_hist = macd[first_valid_idx] - signal[first_valid_idx]
            assert histogram[first_valid_idx] == pytest.approx(expected_hist, rel=1e-6)

    def test_macd_crossover_detection(self):
        """测试 MACD 金叉检测"""
        # 创建模拟数据：先跌后涨
        prices = [100.0 - i*0.5 for i in range(30)]  # 下跌
        prices += [prices[-1] + i*0.8 for i in range(30)]  # 上涨

        macd, signal, histogram = calculate_macd(prices)

        # 检查是否有金叉（MACD 从下方穿过 Signal）
        crossovers = []
        for i in range(1, len(histogram)):
            if histogram[i-1] is not None and histogram[i] is not None:
                if histogram[i-1] < 0 < histogram[i]:
                    crossovers.append(i)

        # 应该至少有一个金叉
        assert len(crossovers) > 0


# ==================== Bollinger Bands 测试 ====================

class TestBollingerBands:
    """测试布林带"""

    def test_bollinger_basic(self):
        """基本功能测试"""
        prices = [100.0, 102.0, 101.0, 103.0, 102.0, 104.0, 103.0, 105.0]

        upper, middle, lower = calculate_bollinger_bands(prices, period=5, std_dev=2)

        # 长度一致
        assert len(upper) == len(prices)
        assert len(middle) == len(prices)
        assert len(lower) == len(prices)

    def test_bollinger_middle_is_ma(self):
        """中轨应该是 MA"""
        prices = [100.0, 102.0, 101.0, 103.0, 102.0, 104.0, 103.0, 105.0]

        upper, middle, lower = calculate_bollinger_bands(prices, period=5)

        expected_ma = calculate_ma(prices, period=5)

        for i in range(len(prices)):
            if middle[i] is not None:
                assert middle[i] == pytest.approx(expected_ma[i], rel=1e-6)

    def test_bollinger_band_order(self):
        """上轨 > 中轨 > 下轨"""
        prices = [100.0, 102.0, 101.0, 103.0, 102.0, 104.0, 103.0, 105.0]

        upper, middle, lower = calculate_bollinger_bands(prices, period=5)

        for i in range(len(prices)):
            if upper[i] is not None:
                assert upper[i] > middle[i] > lower[i]

    def test_bollinger_squeeze(self):
        """测试布林带收窄（低波动）"""
        # 价格几乎不变
        prices = [100.0] * 20

        upper, middle, lower = calculate_bollinger_bands(prices, period=5)

        # 找到第一个有效值
        first_valid = next(i for i, v in enumerate(upper) if v is not None)

        # 上下轨应该很接近中轨
        band_width = upper[first_valid] - lower[first_valid]
        assert band_width < 1.0  # 很窄

    def test_bollinger_expansion(self):
        """测试布林带扩张（高波动）"""
        # 价格剧烈波动
        prices = []
        for i in range(20):
            prices.append(100.0 + (10.0 if i % 2 == 0 else -10.0))

        upper, middle, lower = calculate_bollinger_bands(prices, period=5)

        # 找到第一个有效值
        first_valid = next(i for i, v in enumerate(upper) if v is not None)

        # 上下轨应该很宽
        band_width = upper[first_valid] - lower[first_valid]
        assert band_width > 5.0  # 很宽


# ==================== ATR 测试 ====================

class TestATR:
    """测试平均真实波幅（ATR）"""

    def test_atr_basic(self):
        """基本功能测试"""
        high = [105.0, 108.0, 107.0, 110.0, 112.0]
        low = [100.0, 102.0, 101.0, 104.0, 106.0]
        close = [103.0, 106.0, 105.0, 108.0, 110.0]

        result = calculate_atr(high, low, close, period=3)

        # 长度一致
        assert len(result) == len(high)

    def test_atr_always_positive(self):
        """ATR 应该总是正数"""
        high = [105.0, 108.0, 107.0, 110.0, 112.0] * 5
        low = [100.0, 102.0, 101.0, 104.0, 106.0] * 5
        close = [103.0, 106.0, 105.0, 108.0, 110.0] * 5

        result = calculate_atr(high, low, close, period=14)

        for val in result:
            if val is not None:
                assert val >= 0

    def test_atr_high_volatility(self):
        """高波动 → ATR 应该更大"""
        # 低波动
        high_low_vol = [101.0, 102.0, 101.0, 102.0, 101.0] * 5
        low_low_vol = [100.0, 101.0, 100.0, 101.0, 100.0] * 5
        close_low_vol = [100.5, 101.5, 100.5, 101.5, 100.5] * 5

        atr_low = calculate_atr(high_low_vol, low_low_vol, close_low_vol, period=5)

        # 高波动
        high_high_vol = [110.0, 105.0, 115.0, 100.0, 120.0] * 5
        low_high_vol = [90.0, 95.0, 85.0, 95.0, 80.0] * 5
        close_high_vol = [100.0, 100.0, 100.0, 100.0, 100.0] * 5

        atr_high = calculate_atr(high_high_vol, low_high_vol, close_high_vol, period=5)

        # 高波动的 ATR 应该更大
        # 找到第一个有效值
        first_valid_low = next(i for i, v in enumerate(atr_low) if v is not None)
        first_valid_high = next(i for i, v in enumerate(atr_high) if v is not None)

        assert atr_high[first_valid_high] > atr_low[first_valid_low]

    def test_atr_mismatched_lengths(self):
        """输入长度不匹配应该抛出异常"""
        high = [105.0, 108.0, 107.0]
        low = [100.0, 102.0]  # 长度不一致
        close = [103.0, 106.0, 105.0]

        with pytest.raises(ValueError, match="lengths must match"):
            calculate_atr(high, low, close, period=3)


# ==================== 边界条件和异常测试 ====================

class TestEdgeCasesAndExceptions:
    """边界条件和异常测试"""

    def test_empty_inputs(self):
        """空输入"""
        assert calculate_ma([], 5) == []
        assert calculate_rsi([], 14) == []

        macd, signal, hist = calculate_macd([])
        assert macd == []
        assert signal == []
        assert hist == []

    def test_single_value(self):
        """单个值"""
        result = calculate_ma([100.0], period=1)
        assert result == [100.0]

    def test_all_same_values(self):
        """所有值相同"""
        prices = [100.0] * 50

        ma = calculate_ma(prices, period=5)
        # 所有 MA 应该都是 100
        assert all(v is None or v == pytest.approx(100.0) for v in ma)

        rsi = calculate_rsi(prices, period=14)
        # RSI 应该是 50（无涨跌）
        for v in rsi:
            if v is not None:
                assert 45 <= v <= 55  # 允许一些浮点误差

    def test_very_large_numbers(self):
        """非常大的数字"""
        prices = [1e10 + i for i in range(100)]
        result = calculate_ma(prices, period=5)

        assert result[4] == pytest.approx(1e10 + 2.0, rel=1e-9)

    def test_very_small_numbers(self):
        """非常小的数字"""
        prices = [1e-10 * i for i in range(1, 101)]
        result = calculate_ma(prices, period=5)

        # 应该能正确计算
        assert result[4] is not None


# ==================== 性能测试 ====================

class TestPerformance:
    """性能测试（确保算法效率）"""

    def test_large_dataset_ma(self):
        """大数据集 MA 计算"""
        import time

        prices = [float(i) for i in range(10000)]

        start = time.time()
        result = calculate_ma(prices, period=50)
        elapsed = time.time() - start

        assert len(result) == 10000
        # 应该在 0.1 秒内完成
        assert elapsed < 0.1

    def test_large_dataset_rsi(self):
        """大数据集 RSI 计算"""
        import time

        prices = [float(i % 100) for i in range(10000)]

        start = time.time()
        result = calculate_rsi(prices, period=14)
        elapsed = time.time() - start

        assert len(result) == 10000
        # 应该在 0.5 秒内完成
        assert elapsed < 0.5
