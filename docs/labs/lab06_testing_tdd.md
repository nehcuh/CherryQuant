# Lab 06: 测试驱动开发（TDD）实践

## 实验信息

- **难度**: ⭐⭐⭐ 中级
- **预计时间**: 4 小时
- **相关模块**: Module 6 (测试策略)
- **截止日期**: Week 9 结束

## 学习目标

完成本实验后，你将能够：

1. ✅ 掌握 TDD 的核心工作流（Red-Green-Refactor）
2. ✅ 使用 pytest 编写单元测试和集成测试
3. ✅ Mock 外部依赖（API、数据库、时间等）
4. ✅ 测试异步代码
5. ✅ 提高测试覆盖率到 70%+
6. ✅ 构建自动化测试流程

## 实验前准备

### 前置实验

- [x] Lab 01-05: 所有前置实验

### 必备知识

- [ ] Python基础
- [ ] pytest基础（fixtures, parametrize, markers）
- [ ] async/await
- [ ] Mock概念

### 参考资料

- 📖 `docs/course/06_Testing_Strategies.md`
- 📖 `tests/unit/test_timeseries_repository.py` - 33个测试用例示例
- 📖 `tests/integration/test_data_pipeline_integration.py`

---

## 实验任务

### 任务 1: TDD 实现技术指标库 (2 小时)

使用 TDD 方法实现常用技术指标（MA, RSI, MACD, Bollinger Bands）。

#### Step 1: 编写测试（Red）

创建 `tests/unit/test_indicators_tdd.py`:

```python
import pytest
from src.cherryquant.utils.indicators import (
    calculate_ma,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands
)


class TestMovingAverage:
    """测试移动平均线（MA）"""

    def test_ma_basic(self):
        """基本功能测试"""
        prices = [10, 20, 30, 40, 50]
        result = calculate_ma(prices, period=3)

        # 前两个应该是 None（数据不足）
        assert result[0] is None
        assert result[1] is None

        # 第三个: (10+20+30)/3 = 20
        assert result[2] == 20.0
        assert result[3] == 30.0
        assert result[4] == 40.0

    def test_ma_empty_list(self):
        """边界条件：空列表"""
        assert calculate_ma([], period=3) == []

    def test_ma_insufficient_data(self):
        """边界条件：数据不足"""
        assert calculate_ma([10, 20], period=3) == [None, None]

    def test_ma_period_one(self):
        """边界条件：period=1"""
        assert calculate_ma([10, 20, 30], period=1) == [10.0, 20.0, 30.0]

    def test_ma_invalid_period(self):
        """异常情况：无效 period"""
        with pytest.raises(ValueError):
            calculate_ma([10, 20, 30], period=0)


class TestRSI:
    """测试相对强弱指标（RSI）"""

    def test_rsi_basic(self):
        """基本功能测试"""
        # 模拟价格：先涨后跌
        prices = [
            100, 102, 104, 103, 105,  # 前5个
            107, 106, 108, 110, 109,  # 中间5个
            111, 110, 108, 106, 104   # 后5个
        ]

        result = calculate_rsi(prices, period=14)

        # RSI 应该在 0-100 之间
        for val in result:
            if val is not None:
                assert 0 <= val <= 100

    def test_rsi_all_rising(self):
        """所有价格上涨 → RSI 应该接近 100"""
        prices = list(range(1, 20))  # 1, 2, 3, ..., 19
        result = calculate_rsi(prices, period=14)

        # 最后一个 RSI 应该很高（>80）
        assert result[-1] > 80

    def test_rsi_all_falling(self):
        """所有价格下跌 → RSI 应该接近 0"""
        prices = list(range(20, 1, -1))  # 20, 19, 18, ..., 2
        result = calculate_rsi(prices, period=14)

        # 最后一个 RSI 应该很低（<20）
        assert result[-1] < 20

    @pytest.mark.parametrize("period", [5, 14, 21, 50])
    def test_rsi_different_periods(self, period):
        """参数化测试：不同周期"""
        prices = [100 + i for i in range(100)]
        result = calculate_rsi(prices, period=period)

        # 前 period-1 个应该是 None
        assert all(v is None for v in result[:period-1])
        # 之后都应该有值
        assert all(v is not None for v in result[period-1:])


class TestMACD:
    """测试 MACD 指标"""

    def test_macd_basic(self):
        """基本功能测试"""
        prices = [i + 100 for i in range(50)]

        macd, signal, histogram = calculate_macd(prices)

        # 长度应该一致
        assert len(macd) == len(prices)
        assert len(signal) == len(prices)
        assert len(histogram) == len(prices)

    def test_macd_crossover(self):
        """测试 MACD 金叉"""
        # TODO: 创建模拟数据，验证金叉检测
        pass


class TestBollingerBands:
    """测试布林带"""

    def test_bollinger_basic(self):
        """基本功能测试"""
        prices = [100, 102, 101, 103, 102, 104, 103, 105]

        upper, middle, lower = calculate_bollinger_bands(prices, period=5, std_dev=2)

        # 中轨应该是 MA
        expected_ma = calculate_ma(prices, period=5)
        assert middle == expected_ma

        # 上轨 > 中轨 > 下轨
        for i in range(len(prices)):
            if upper[i] is not None:
                assert upper[i] > middle[i] > lower[i]

    def test_bollinger_squeeze(self):
        """测试布林带收窄（低波动）"""
        # 价格几乎不变
        prices = [100.0] * 20
        upper, middle, lower = calculate_bollinger_bands(prices, period=5)

        # 上下轨应该很接近中轨
        for i in range(5, len(prices)):
            band_width = upper[i] - lower[i]
            assert band_width < 1.0  # 很窄

    def test_bollinger_expansion(self):
        """测试布林带扩张（高波动）"""
        # 价格剧烈波动
        prices = []
        for i in range(20):
            prices.append(100 + (10 if i % 2 == 0 else -10))

        upper, middle, lower = calculate_bollinger_bands(prices, period=5)

        # 上下轨应该很宽
        for i in range(5, len(prices)):
            band_width = upper[i] - lower[i]
            assert band_width > 5.0  # 很宽
```

运行测试（此时应该全部失败）：
```bash
uv run pytest tests/unit/test_indicators_tdd.py -v
# 预期：全部失败（因为函数还不存在）
```

#### Step 2: 实现代码（Green）

创建 `src/cherryquant/utils/indicators.py`:

```python
"""
技术指标库

教学要点：
1. TDD 开发流程
2. 数值计算的边界条件处理
3. 清晰的类型提示和文档
"""
from typing import List, Optional, Tuple
import statistics


def calculate_ma(prices: List[float], period: int) -> List[Optional[float]]:
    """
    计算移动平均线（Moving Average）

    Args:
        prices: 价格序列
        period: 周期

    Returns:
        MA 序列，数据不足的位置为 None

    Raises:
        ValueError: period <= 0

    Example:
        >>> calculate_ma([10, 20, 30, 40], period=2)
        [None, 15.0, 25.0, 35.0]
    """
    if not prices:
        return []

    if period <= 0:
        raise ValueError("Period must be positive")

    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        else:
            window = prices[i - period + 1 : i + 1]
            result.append(sum(window) / period)

    return result


def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """
    计算相对强弱指标（Relative Strength Index）

    RSI = 100 - (100 / (1 + RS))
    RS = 平均上涨幅度 / 平均下跌幅度

    Args:
        prices: 价格序列
        period: 周期（默认 14）

    Returns:
        RSI 序列，范围 [0, 100]
    """
    if len(prices) < period + 1:
        return [None] * len(prices)

    result = [None] * period

    # 计算价格变化
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]

    # 分离涨跌
    gains = [max(change, 0) for change in changes]
    losses = [abs(min(change, 0)) for change in changes]

    # 初始平均值
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # 计算 RSI
    for i in range(period, len(prices)):
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        result.append(rsi)

        # 更新平均值（指数加权）
        if i < len(changes):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    return result


def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """
    计算 MACD 指标

    MACD = EMA(fast) - EMA(slow)
    Signal = EMA(MACD, signal_period)
    Histogram = MACD - Signal

    Returns:
        (MACD线, 信号线, 柱状图)
    """
    # 计算 EMA
    def ema(data: List[float], period: int) -> List[Optional[float]]:
        result = [None] * (period - 1)
        multiplier = 2 / (period + 1)

        # 初始 SMA
        sma = sum(data[:period]) / period
        result.append(sma)

        # 后续 EMA
        ema_value = sma
        for price in data[period:]:
            ema_value = (price - ema_value) * multiplier + ema_value
            result.append(ema_value)

        return result

    fast_ema = ema(prices, fast_period)
    slow_ema = ema(prices, slow_period)

    # 计算 MACD
    macd = []
    for i in range(len(prices)):
        if fast_ema[i] is None or slow_ema[i] is None:
            macd.append(None)
        else:
            macd.append(fast_ema[i] - slow_ema[i])

    # 计算信号线
    macd_values = [v for v in macd if v is not None]
    signal_ema = ema(macd_values, signal_period)

    # 补齐长度
    signal = [None] * (len(macd) - len(signal_ema)) + signal_ema

    # 计算柱状图
    histogram = []
    for i in range(len(macd)):
        if macd[i] is None or signal[i] is None:
            histogram.append(None)
        else:
            histogram.append(macd[i] - signal[i])

    return macd, signal, histogram


def calculate_bollinger_bands(
    prices: List[float],
    period: int = 20,
    std_dev: float = 2.0
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """
    计算布林带（Bollinger Bands）

    中轨 = MA(period)
    上轨 = 中轨 + (std_dev * 标准差)
    下轨 = 中轨 - (std_dev * 标准差)

    Returns:
        (上轨, 中轨, 下轨)
    """
    middle = calculate_ma(prices, period)

    upper = []
    lower = []

    for i in range(len(prices)):
        if middle[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            # 计算标准差
            window = prices[i - period + 1 : i + 1]
            std = statistics.stdev(window)

            upper.append(middle[i] + std_dev * std)
            lower.append(middle[i] - std_dev * std)

    return upper, middle, lower
```

#### Step 3: 运行测试（Green）

```bash
uv run pytest tests/unit/test_indicators_tdd.py -v
# 预期：大部分测试通过
```

#### Step 4: 重构（Refactor）

优化代码质量：
- 提取公共逻辑
- 优化性能（使用 numpy）
- 改进命名

---

### 任务 2: Mock 外部依赖 (1 小时)

#### 2.1 测试 API 调用（Mock HTTP）

创建 `tests/unit/test_tushare_collector_mock.py`:

```python
"""
使用 Mock 测试 TushareCollector
"""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime
from src.cherryquant.data.collectors.tushare_collector import TushareCollector


@pytest.mark.asyncio
async def test_fetch_daily_data_success():
    """测试数据采集成功（Mock API）"""

    # Mock API 响应
    mock_response = [
        {"ts_code": "rb2501.SHF", "trade_date": "20240101", "close": 3500.0, "volume": 100000},
        {"ts_code": "rb2501.SHF", "trade_date": "20240102", "close": 3520.0", "volume": 120000},
    ]

    # Patch API 调用
    with patch.object(
        TushareCollector,
        "_call_api",
        new=AsyncMock(return_value=mock_response)
    ):
        collector = TushareCollector(token="fake_token")
        data = await collector.fetch_daily_data(
            symbol="rb2501",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )

        # 验证
        assert len(data) == 2
        assert data[0]["close"] == 3500.0
        assert data[1]["close"] == 3520.0


@pytest.mark.asyncio
async def test_fetch_daily_data_api_error():
    """测试 API 错误处理"""

    # Mock API 抛出异常
    with patch.object(
        TushareCollector,
        "_call_api",
        new=AsyncMock(side_effect=ConnectionError("API unavailable"))
    ):
        collector = TushareCollector(token="fake_token")

        # 应该抛出异常或返回空
        with pytest.raises(ConnectionError):
            await collector.fetch_daily_data(
                symbol="rb2501",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31)
            )


@pytest.mark.asyncio
async def test_rate_limiting():
    """测试限流机制"""

    call_count = 0

    async def mock_api(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return []

    with patch.object(TushareCollector, "_call_api", new=AsyncMock(side_effect=mock_api)):
        collector = TushareCollector(token="fake_token")

        # 连续调用 3 次
        for _ in range(3):
            await collector.fetch_daily_data(
                symbol="rb2501",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31)
            )

        # 验证限流（应该有延迟，但测试中我们只验证调用次数）
        assert call_count == 3
```

#### 2.2 测试时间相关逻辑（Mock 时间）

```python
from unittest.mock import patch
from datetime import datetime


def test_trading_hours_check():
    """测试交易时段检查"""

    # Mock 交易时段
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30)  # 上午 10:30

        result = is_trading_hours()
        assert result == True

    # Mock 非交易时段
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 1, 15, 3, 0)  # 凌晨 3:00

        result = is_trading_hours()
        assert result == False
```

---

### 任务 3: 提高测试覆盖率 (1 小时)

#### 3.1 运行覆盖率报告

```bash
# 运行测试并生成覆盖率
uv run pytest --cov=src/cherryquant --cov-report=html --cov-report=term

# 打开 HTML 报告
open htmlcov/index.html
```

#### 3.2 补充测试覆盖未覆盖的分支

查看报告，找到未覆盖的代码分支，补充测试。

**示例：**

假设覆盖率报告显示这个分支未被测试：

```python
def process_data(data: List[Dict]) -> List[Dict]:
    if not data:  # ← 未覆盖
        logger.warning("Empty data received")
        return []

    return [normalize(item) for item in data]
```

补充测试：

```python
def test_process_data_empty():
    """测试空数据处理（补充覆盖率）"""
    result = process_data([])
    assert result == []
```

---

## 实验总结

### 完成情况自查

- [ ] 使用 TDD 实现了技术指标库
- [ ] 掌握了 Mock 技术（API、时间等）
- [ ] 测试覆盖率达到 70%+
- [ ] 理解了测试金字塔

### 关键收获

1. **TDD 工作流** - Red → Green → Refactor
2. **测试先行** - 测试即规格说明
3. **Mock 技术** - 隔离外部依赖
4. **覆盖率** - 找到未测试的代码

---

**下一步**: Lab 07 - 回测系统实验 📊
