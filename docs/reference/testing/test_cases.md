# CherryQuant 测试案例文档

## 测试概述

本文档定义了CherryQuant AI期货交易系统的测试案例，包括单元测试、集成测试和场景测试。

## 测试环境配置

### 环境要求

```bash
# Python环境
Python 3.12+
uv包管理器

# 依赖包
vnpy >= 4.0
akshare >= 1.17
openai >= 2.0
python-dotenv >= 1.0
```

### 配置文件

```bash
# .env文件
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
LOG_LEVEL=DEBUG
```

## 单元测试

### 1. AI决策引擎测试

#### 测试文件: `tests/test_ai_engine.py`

##### 测试案例1: AI决策获取

**测试目标**: 验证AI决策引擎能正确获取交易决策

**测试步骤**:
```python
import pytest
import asyncio
from ai.decision_engine.futures_engine import FuturesDecisionEngine

@pytest.mark.asyncio
async def test_get_ai_decision():
    engine = FuturesDecisionEngine()

    account_info = {
        "return_pct": 0.0,
        "win_rate": 0.0,
        "cash_available": 100000.0,
        "account_value": 100000.0
    }

    decision = await engine.get_decision(
        symbol="rb2501",
        account_info=account_info,
        current_positions=[]
    )

    # 验证决策格式
    assert decision is not None
    assert "signal" in decision
    assert "symbol" in decision
    assert "quantity" in decision
    assert "confidence" in decision
    assert 0 <= decision["confidence"] <= 1

    print(f"✅ AI决策测试通过: {decision['signal']}")
```

**预期结果**:
- 返回有效的决策字典
- 包含所有必需字段
- 置信度在有效范围内

##### 测试案例2: 市场数据获取

**测试目标**: 验证能正确获取期货市场数据

```python
@pytest.mark.asyncio
async def test_market_data():
    engine = FuturesDecisionEngine()
    market_data = await engine._get_market_data("rb2501")

    assert market_data is not None
    assert "current_price" in market_data
    assert "prices_list" in market_data
    assert len(market_data["prices_list"]) > 0

    print(f"✅ 市场数据测试通过: {market_data['current_price']}")
```

### 2. OpenAI客户端测试

#### 测试文件: `tests/test_openai_client.py`

##### 测试案例1: API连接测试

```python
import pytest
from ai.llm_client.openai_client import OpenAIClient

def test_api_connection():
    client = OpenAIClient()
    is_connected = client.test_connection()

    assert is_connected is True
    print("✅ OpenAI API连接成功")
```

##### 测试案例2: JSON验证测试

```python
def test_decision_validation():
    client = OpenAIClient()

    # 有效决策
    valid_decision = {
        "signal": "buy_to_enter",
        "symbol": "rb2501",
        "quantity": 5,
        "leverage": 5,
        "profit_target": 3600.0,
        "stop_loss": 3400.0,
        "confidence": 0.7,
        "invalidation_condition": "价格跌破3400",
        "justification": "技术指标显示上涨趋势"
    }

    assert client._validate_decision(valid_decision) is True

    # 无效决策（缺少字段）
    invalid_decision = {
        "signal": "buy_to_enter",
        "symbol": "rb2501"
    }

    with pytest.raises(ValueError):
        client._validate_decision(invalid_decision)

    print("✅ 决策验证测试通过")
```

### 3. 策略逻辑测试

#### 测试文件: `tests/test_strategy.py`

##### 测试案例1: 仓位调整测试

```python
import pytest
from src.cherryquant.cherry_quant_strategy import CherryQuantStrategy

def test_position_size_adjustment():
    # 创建策略实例（模拟）
    strategy = CherryQuantStrategy(None, "test", "rb2501.SHFE", {})

    # 测试不同置信度的仓位调整
    ai_quantity = 10
    confidence = 0.7
    leverage = 5

    adjusted = strategy._adjust_position_size(ai_quantity, confidence, leverage)

    # 验证调整逻辑
    assert 0 <= adjusted <= 10
    assert isinstance(adjusted, int)

    print(f"✅ 仓位调整测试通过: {ai_quantity} -> {adjusted}")
```

## 集成测试

### 1. 端到端AI决策流程测试

#### 测试文件: `tests/test_integration.py`

##### 测试案例1: 完整决策流程

```python
import pytest
import asyncio
from ai.decision_engine.futures_engine import FuturesDecisionEngine

@pytest.mark.asyncio
async def test_full_decision_flow():
    """测试完整的AI决策流程"""

    # 1. 初始化引擎
    engine = FuturesDecisionEngine()

    # 2. 准备测试数据
    account_info = {
        "return_pct": 1.5,
        "win_rate": 0.6,
        "cash_available": 80000.0,
        "account_value": 101500.0
    }

    # 3. 获取决策
    decision = await engine.get_decision(
        symbol="rb2501",
        account_info=account_info,
        current_positions=[]
    )

    # 4. 验证决策质量
    assert decision is not None
    assert decision["signal"] in ["buy_to_enter", "sell_to_enter", "hold", "close"]
    assert decision["confidence"] >= 0

    # 5. 验证风险管理
    if decision["signal"] not in ["hold", "close"]:
        assert decision["stop_loss"] > 0
        assert decision["profit_target"] > 0
        assert decision["quantity"] > 0

    print(f"✅ 完整决策流程测试通过")
    print(f"   信号: {decision['signal']}")
    print(f"   置信度: {decision['confidence']:.2f}")
    print(f"   理由: {decision['justification']}")
```

### 2. 多合约并行测试

##### 测试案例2: 并发决策测试

```python
@pytest.mark.asyncio
async def test_concurrent_decisions():
    """测试多合约并行决策"""

    engine = FuturesDecisionEngine()
    symbols = ["rb2501", "i2501", "cu2501"]

    account_info = {
        "return_pct": 0.0,
        "win_rate": 0.0,
        "cash_available": 100000.0,
        "account_value": 100000.0
    }

    # 并发获取决策
    tasks = []
    for symbol in symbols:
        task = engine.get_decision(
            symbol=symbol,
            account_info=account_info,
            current_positions=[]
        )
        tasks.append(task)

    decisions = await asyncio.gather(*tasks, return_exceptions=True)

    # 验证结果
    successful_decisions = 0
    for i, decision in enumerate(decisions):
        if isinstance(decision, Exception):
            print(f"❌ {symbols[i]} 决策失败: {decision}")
        elif decision:
            print(f"✅ {symbols[i]}: {decision['signal']} ({decision['confidence']:.2f})")
            successful_decisions += 1

    assert successful_decisions >= 2  # 至少2个决策成功
    print(f"✅ 并发决策测试通过: {successful_decisions}/{len(symbols)} 成功")
```

## 场景测试

### 1. 模拟交易场景

#### 测试文件: `tests/test_scenarios.py`

##### 场景1: 模拟交易日

```python
import pytest
import asyncio
from datetime import datetime
from run_cherryquant import simulate_ai_trading_loop, create_strategy_settings

@pytest.mark.asyncio
async def test_simulated_trading_day():
    """测试模拟一交易日"""

    strategy_settings = create_strategy_settings()

    print("🚀 开始模拟交易日测试...")

    # 模拟3个交易周期（每5分钟一次）
    trade_count = 0
    max_trades = 3

    async def limited_trading_loop():
        nonlocal trade_count
        strategy_settings["decision_interval"] = 2  # 2秒间隔（测试用）

        # 运行3个周期
        for i in range(max_trades):
            print(f"📊 模拟交易周期 {i+1}/{max_trades}")
            await simulate_ai_trading_loop(strategy_settings)
            trade_count += 1
            await asyncio.sleep(1)  # 短暂延迟

    # 限制运行时间
    try:
        await asyncio.wait_for(limited_trading_loop(), timeout=30)
    except asyncio.TimeoutError:
        print("⏰ 模拟交易时间到")

    assert trade_count > 0
    print(f"✅ 模拟交易日测试通过，完成 {trade_count} 个交易周期")
```

##### 场景2: 风险控制测试

```python
@pytest.mark.asyncio
async def test_risk_management():
    """测试风险控制机制"""

    # 构造极端市场情况
    extreme_account_info = {
        "return_pct": -0.08,  # 大幅亏损
        "win_rate": 0.2,      # 低胜率
        "cash_available": 20000.0,  # 资金不足
        "account_value": 92000.0
    }

    engine = FuturesDecisionEngine()

    decision = await engine.get_decision(
        symbol="rb2501",
        account_info=extreme_account_info,
        current_positions=[]
    )

    # 验证风险控制
    if decision:
        # 在大幅亏损时，AI应该更谨慎
        assert decision["confidence"] <= 0.8
        if decision["signal"] not in ["hold", "close"]:
            assert decision["quantity"] <= 5  # 应该减少仓位
        print(f"✅ 风险控制测试通过: {decision['signal']} (置信度: {decision['confidence']:.2f})")
    else:
        print("✅ 风险控制测试通过: AI选择不交易")
```

### 2. 异常情况测试

##### 场景3: 网络异常处理

```python
@pytest.mark.asyncio
async def test_network_failure():
    """测试网络异常处理"""

    # 使用无效的API密钥模拟网络错误
    import os
    original_key = os.getenv("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "invalid_key"

    try:
        engine = FuturesDecisionEngine()

        # 测试网络失败时的行为
        connection_ok = await engine.test_connection()
        assert connection_ok is False

        # 测试决策获取失败时的处理
        decision = await engine.get_decision(
            symbol="rb2501",
            account_info={"return_pct": 0.0, "win_rate": 0.0, "cash_available": 100000.0, "account_value": 100000.0},
            current_positions=[]
        )

        assert decision is None
        print("✅ 网络异常处理测试通过")

    finally:
        # 恢复原始API密钥
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
```

##### 场景4: 数据异常处理

```python
@pytest.mark.asyncio
async def test_invalid_data():
    """测试无效数据处理"""

    engine = FuturesDecisionEngine()

    # 测试无效合约代码
    decision = await engine.get_decision(
        symbol="INVALID_CODE",
        account_info={"return_pct": 0.0, "win_rate": 0.0, "cash_available": 100000.0, "account_value": 100000.0},
        current_positions=[]
    )

    # 应该能正常处理无效数据，不崩溃
    assert decision is not None  # 可能返回hold决策
    print("✅ 无效数据处理测试通过")
```

## 性能测试

### 1. 响应时间测试

##### 测试文件: `tests/test_performance.py`

```python
import pytest
import time
import asyncio
from ai.decision_engine.futures_engine import FuturesDecisionEngine

@pytest.mark.asyncio
async def test_response_time():
    """测试AI决策响应时间"""

    engine = FuturesDecisionEngine()

    account_info = {
        "return_pct": 0.0,
        "win_rate": 0.0,
        "cash_available": 100000.0,
        "account_value": 100000.0
    }

    start_time = time.time()

    decision = await engine.get_decision(
        symbol="rb2501",
        account_info=account_info,
        current_positions=[]
    )

    end_time = time.time()
    response_time = end_time - start_time

    # 验证响应时间（应该在10秒内）
    assert response_time < 10.0
    assert decision is not None

    print(f"✅ 响应时间测试通过: {response_time:.2f}秒")
```

### 2. 并发性能测试

```python
@pytest.mark.asyncio
async def test_concurrent_performance():
    """测试并发性能"""

    engine = FuturesDecisionEngine()
    symbols = ["rb2501"] * 5  # 5个相同请求

    account_info = {
        "return_pct": 0.0,
        "win_rate": 0.0,
        "cash_available": 100000.0,
        "account_value": 100000.0
    }

    start_time = time.time()

    tasks = []
    for symbol in symbols:
        task = engine.get_decision(
            symbol=symbol,
            account_info=account_info,
            current_positions=[]
        )
        tasks.append(task)

    decisions = await asyncio.gather(*tasks, return_exceptions=True)

    end_time = time.time()
    total_time = end_time - start_time

    successful_decisions = sum(1 for d in decisions if d is not None and not isinstance(d, Exception))

    # 验证并发性能
    assert successful_decisions >= 3
    assert total_time < 30.0  # 5个请求应该在30秒内完成

    print(f"✅ 并发性能测试通过: {successful_decisions}/5 成功，耗时 {total_time:.2f}秒")
```

## 运行测试

### 安装测试依赖

```bash
uv add --dev pytest pytest-asyncio pytest-cov
```

### 运行所有测试

```bash
uv run pytest tests/ -v
```

### 运行特定测试类型

```bash
# 单元测试
uv run pytest tests/test_ai_engine.py tests/test_openai_client.py -v

# 集成测试
uv run pytest tests/test_integration.py -v

# 场景测试
uv run pytest tests/test_scenarios.py -v

# 性能测试
uv run pytest tests/test_performance.py -v
```

### 生成测试覆盖率报告

```bash
uv run pytest tests/ --cov=cherryquant --cov-report=html
```

## 测试数据管理

### 模拟数据

- 使用真实的历史K线数据片段
- 模拟各种市场情况（上涨、下跌、震荡）
- 模拟账户和持仓状态

### 测试环境隔离

- 使用独立的测试配置
- 不影响真实交易数据
- 支持离线测试模式

---

**文档版本**: v1.0
**创建日期**: 2025-10-29
**最后更新**: 2025-10-29