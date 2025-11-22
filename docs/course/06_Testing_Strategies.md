# Module 6: 测试策略与质量保证

## 课程信息

- **模块编号**: Module 6
- **难度**: ⭐⭐⭐ 中级
- **预计时间**: 6-8 小时
- **前置要求**: Module 0-5, Python 基础, pytest 基础知识

## 学习目标

完成本模块后，你将能够：

1. ✅ 理解测试驱动开发（TDD）的核心思想
2. ✅ 掌握单元测试、集成测试、性能测试的区别和应用
3. ✅ 使用 pytest 编写高质量的测试代码
4. ✅ 理解测试覆盖率及其实际意义
5. ✅ 掌握异步代码的测试方法
6. ✅ 学会 Mock 外部依赖（API、数据库等）
7. ✅ 构建完整的测试金字塔

## 为什么测试很重要？

### 量化交易中的测试特殊性

在量化交易系统中，**Bug 可能导致真金白银的损失**。一个未被测试发现的错误可能导致：

- 💸 错误的交易信号 → 亏损
- 🔴 系统崩溃 → 错过交易机会
- ⚠️ 数据错误 → 错误决策
- 🐛 风控失效 → 爆仓风险

**测试不是可选项，而是必需品。**

### 真实案例：没有测试的代价

**❌ 案例 1：数据清洗 Bug**

```python
# 没有测试的代码
def normalize_price(price: float) -> float:
    """标准化价格（移除）"""
    return price / 100  # Bug: 应该是 price * 100（单位转换）

# 直接用于生产...
# 结果：所有价格都被错误计算，导致策略失效
```

如果有测试：

```python
def test_normalize_price():
    # 测试会立即发现问题
    assert normalize_price(1.23) == 123.0  # ❌ 失败！
```

**✅ 有测试的代码：**

```python
def normalize_price(price: float) -> float:
    """
    标准化价格：元 → 分

    Args:
        price: 价格（元）

    Returns:
        价格（分）

    Example:
        >>> normalize_price(1.23)
        123.0
    """
    return price * 100


# 测试用例
def test_normalize_price():
    """测试价格标准化"""
    # 基本功能
    assert normalize_price(1.23) == 123.0
    assert normalize_price(0.01) == 1.0

    # 边界条件
    assert normalize_price(0) == 0
    assert normalize_price(9999.99) == 999999.0

    # 精度问题
    assert abs(normalize_price(0.33) - 33.0) < 0.01
```

---

## 课程大纲

### 第一部分：测试基础 (2 小时)

#### 1.1 测试金字塔

```
         ┌─────────────────┐
         │   E2E Tests     │  ← 少量（5-10%）
         │  端到端测试      │     慢但全面
         ├─────────────────┤
         │Integration Tests│  ← 适量（20-30%）
         │   集成测试       │     中速，测试组件协作
         ├─────────────────┤
         │  Unit Tests     │  ← 大量（60-70%）
         │  单元测试        │     快速，测试单个功能
         └─────────────────┘
```

**金字塔原则：**
- **底层多**：单元测试应占大多数（快速、稳定、易维护）
- **中层适中**：集成测试覆盖关键交互
- **顶层少**：端到端测试只测核心流程

**CherryQuant 的测试分布：**
```
tests/
├── unit/              # 单元测试（60-70%）
│   ├── test_query_builder.py      # 测试单个组件
│   ├── test_validator.py
│   └── test_normalizer.py
├── integration/       # 集成测试（20-30%）
│   ├── test_data_pipeline_integration.py  # 测试多组件协作
│   └── test_quantbox_integration.py
└── performance/       # 性能测试（5-10%）
    └── benchmark_suite.py         # 测试性能指标
```

#### 1.2 单元测试 vs 集成测试

**单元测试**：测试单个函数或类，隔离外部依赖

```python
# src/cherryquant/data/query/query_builder.py
class QueryBuilder:
    def filter_by_symbol(self, symbol: str) -> "QueryBuilder":
        self.conditions.append({"symbol": symbol})
        return self


# tests/unit/test_query_builder.py
def test_filter_by_symbol():
    """单元测试：只测试 QueryBuilder 本身，不依赖数据库"""
    builder = QueryBuilder()
    result = builder.filter_by_symbol("rb2501")

    assert len(result.conditions) == 1
    assert result.conditions[0] == {"symbol": "rb2501"}
```

**集成测试**：测试多个组件的协作，使用真实或接近真实的依赖

```python
# tests/integration/test_data_pipeline_integration.py
async def test_complete_data_flow():
    """集成测试：测试从采集到存储的完整流程"""
    # 使用真实的 MongoDB（测试数据库）
    pipeline = DataPipeline(
        collector=TushareCollector(token=TEST_TOKEN),
        storage=TimeSeriesRepository(db=test_db)
    )

    # 执行完整流程
    result = await pipeline.collect_and_store_data(
        symbol="rb2501",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31)
    )

    # 验证结果
    assert result["success"] == True
    assert result["records_stored"] > 0

    # 验证数据确实存储到数据库
    stored_data = await pipeline.query_data(
        symbol="rb2501",
        start_date=datetime(2024, 1, 1)
    )
    assert len(stored_data) > 0
```

#### 1.3 pytest 基础

**fixture 的威力：**

```python
import pytest
from datetime import datetime


# Fixture: 可重用的测试数据
@pytest.fixture
def sample_market_data():
    """提供测试用的市场数据"""
    return [
        {"symbol": "rb2501", "close": 3500.0, "date": datetime(2024, 1, 1)},
        {"symbol": "rb2501", "close": 3520.0, "date": datetime(2024, 1, 2)},
        {"symbol": "rb2501", "close": 3490.0, "date": datetime(2024, 1, 3)},
    ]


# 使用 fixture
def test_data_validator(sample_market_data):
    """测试数据验证器"""
    validator = DataValidator()
    result = validator.validate(sample_market_data)
    assert result.is_valid == True


def test_data_normalizer(sample_market_data):
    """测试数据标准化器"""
    normalizer = DataNormalizer()
    result = normalizer.normalize(sample_market_data)
    assert len(result) == 3
```

**参数化测试：**

```python
@pytest.mark.parametrize("input,expected", [
    (1.23, 123.0),
    (0.01, 1.0),
    (0, 0),
    (9999.99, 999999.0),
])
def test_normalize_price_parametrized(input, expected):
    """参数化测试：一次测试多个用例"""
    assert abs(normalize_price(input) - expected) < 0.01
```

---

### 第二部分：异步代码测试 (2 小时)

#### 2.1 异步测试基础

CherryQuant 大量使用 async/await，需要特殊的测试方法：

```python
import pytest


# 使用 pytest-asyncio 标记异步测试
@pytest.mark.asyncio
async def test_async_data_collection():
    """测试异步数据采集"""
    collector = TushareCollector(token=TEST_TOKEN)

    # 异步调用
    data = await collector.fetch_daily_data(
        symbol="rb2501",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31)
    )

    # 验证
    assert len(data) > 0
    assert all("close" in record for record in data)
```

#### 2.2 Mock 异步 API 调用

**问题**：测试不应该依赖外部 API（慢、不稳定、有成本）

**解决**：使用 `AsyncMock` 模拟 API 响应

```python
from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_data_collection_with_mock():
    """使用 Mock 测试数据采集（不调用真实 API）"""

    # 模拟 API 响应
    mock_response = [
        {"ts_code": "rb2501.SHF", "trade_date": "20240101", "close": 3500.0},
        {"ts_code": "rb2501.SHF", "trade_date": "20240102", "close": 3520.0},
    ]

    # Patch TushareCollector 的 API 调用方法
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

        # 验证：应该返回 mock 的数据
        assert len(data) == 2
        assert data[0]["close"] == 3500.0
```

#### 2.3 测试重试机制

CherryQuant 使用了复杂的重试逻辑（指数退避、熔断器），需要仔细测试：

```python
@pytest.mark.asyncio
async def test_retry_on_failure():
    """测试重试机制：API 失败后应该重试"""

    call_count = 0

    async def mock_api_with_failures():
        """模拟前两次失败，第三次成功"""
        nonlocal call_count
        call_count += 1

        if call_count < 3:
            raise ConnectionError("API temporarily unavailable")
        return [{"close": 3500.0}]

    # 使用 retry 装饰器
    @retry_async(RetryConfig(max_attempts=5, base_delay=0.01))
    async def fetch_with_retry():
        return await mock_api_with_failures()

    # 执行
    result = await fetch_with_retry()

    # 验证：应该调用 3 次（2 次失败 + 1 次成功）
    assert call_count == 3
    assert result == [{"close": 3500.0}]


@pytest.mark.asyncio
async def test_circuit_breaker_opens():
    """测试熔断器：连续失败后应该打开"""

    async def always_fail():
        raise ConnectionError("Service down")

    breaker = CircuitBreaker(
        failure_threshold=3,
        timeout=60
    )

    # 连续失败 3 次
    for _ in range(3):
        with pytest.raises(ConnectionError):
            await breaker.call(always_fail)

    # 验证：熔断器应该打开
    assert breaker.state == CircuitBreakerState.OPEN

    # 再次调用应该直接失败（不调用函数）
    with pytest.raises(CircuitBreakerError):
        await breaker.call(always_fail)
```

---

### 第三部分：数据库测试 (1.5 小时)

#### 3.1 测试数据库 vs 生产数据库

**原则：永远不要在测试中使用生产数据库！**

**CherryQuant 的方案：**

```python
# tests/conftest.py (pytest 全局配置)
import pytest
from motor.motor_asyncio import AsyncIOMotorClient


@pytest.fixture(scope="session")
async def test_db():
    """提供测试用的 MongoDB 数据库"""
    # 连接测试数据库（独立于生产）
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["cherryquant_test"]  # 注意：不是 cherryquant_prod

    yield db

    # 测试结束后清理
    await client.drop_database("cherryquant_test")
    client.close()


@pytest.fixture
async def clean_db(test_db):
    """每个测试前清空数据库"""
    collections = await test_db.list_collection_names()
    for collection in collections:
        await test_db[collection].delete_many({})

    yield test_db
```

**使用测试数据库：**

```python
@pytest.mark.asyncio
async def test_timeseries_repository_insert(clean_db):
    """测试时序数据插入"""
    repo = TimeSeriesRepository(db=clean_db)

    # 插入测试数据
    data = [
        {"symbol": "rb2501", "close": 3500.0, "timestamp": datetime(2024, 1, 1)},
        {"symbol": "rb2501", "close": 3520.0, "timestamp": datetime(2024, 1, 2)},
    ]

    result = await repo.insert_many("market_data_1d", data)

    # 验证插入成功
    assert result.inserted_count == 2

    # 验证可以查询
    stored = await repo.query(
        collection="market_data_1d",
        filters={"symbol": "rb2501"}
    )
    assert len(stored) == 2
```

#### 3.2 测试数据迁移

```python
@pytest.mark.asyncio
async def test_database_schema_creation(test_db):
    """测试数据库 Schema 创建（索引、TTL 等）"""
    # 执行 Schema 初始化
    await init_database_schema(test_db)

    # 验证：时序集合应该被创建
    collections = await test_db.list_collection_names()
    assert "market_data_1d" in collections

    # 验证：索引应该被创建
    indexes = await test_db["market_data_1d"].index_information()

    # 应该有复合索引 (symbol, timestamp)
    assert any(
        "symbol" in idx.get("key", []) and "timestamp" in idx.get("key", [])
        for idx in indexes.values()
    )
```

---

### 第四部分：测试覆盖率 (1 小时)

#### 4.1 什么是测试覆盖率？

**测试覆盖率**：代码被测试执行到的比例

```bash
# 运行测试并生成覆盖率报告
pytest --cov=src/cherryquant --cov-report=html

# 输出示例：
---------- coverage: platform darwin, python 3.12.0 -----------
Name                                              Stmts   Miss  Cover
---------------------------------------------------------------------
src/cherryquant/data/storage/timeseries_repository.py   245      3   98.8%
src/cherryquant/data/utils/retry.py                     290     88   69.7%
src/cherryquant/data/cleaners/validator.py              160     50   68.8%
---------------------------------------------------------------------
TOTAL                                                  2456    812   67.0%
```

#### 4.2 覆盖率的意义与误区

**✅ 好的理解：**
- 覆盖率是**发现未测试代码**的工具
- 高覆盖率（70%+）说明大部分代码被测试过
- 关键路径应该达到 90%+ 覆盖率

**❌ 常见误区：**
- ❌ "100% 覆盖率 = 没有 Bug" → **错！覆盖率只是指标之一**
- ❌ "追求 100% 覆盖率" → **不现实，性价比低**
- ❌ "为了覆盖率而写测试" → **本末倒置，应该为质量而测试**

**CherryQuant 的覆盖率目标：**

| 模块 | 目标覆盖率 | 原因 |
|------|-----------|------|
| 数据存储（Repository） | 90%+ | 核心路径，数据正确性至关重要 |
| 数据清洗（Validator, Normalizer） | 80%+ | 影响数据质量，需要高覆盖 |
| 重试机制（Retry, CircuitBreaker） | 70%+ | 错误处理逻辑，需要充分测试 |
| AI 决策引擎 | 60%+ | 外部依赖多，Mock 测试即可 |
| 配置管理 | 50%+ | 主要是数据定义，测试重点字段验证 |

#### 4.3 提高覆盖率的策略

**1. 找到未覆盖的分支：**

```bash
# 生成 HTML 报告，查看未覆盖的行
pytest --cov=src/cherryquant --cov-report=html
open htmlcov/index.html
```

**2. 针对性补充测试：**

```python
# 假设覆盖率报告显示这个分支未被测试
def process_data(data: List[Dict]) -> List[Dict]:
    if not data:  # ← 这个分支没有被测试覆盖
        return []

    return [normalize(item) for item in data]


# 补充测试
def test_process_data_empty_input():
    """测试空输入（补充覆盖率）"""
    result = process_data([])
    assert result == []
```

---

### 第五部分：测试驱动开发（TDD） (1.5 小时)

#### 5.1 TDD 工作流

```
┌─────────────────┐
│  1. 写测试       │ ← 先写测试（红色，失败）
│  (Red)          │
└────────┬────────┘
         ↓
┌────────┴────────┐
│  2. 写代码       │ ← 让测试通过（绿色）
│  (Green)        │
└────────┬────────┘
         ↓
┌────────┴────────┐
│  3. 重构        │ ← 优化代码（保持绿色）
│  (Refactor)     │
└────────┬────────┘
         │
         └──────→ 循环
```

#### 5.2 TDD 实战：实现 MA 指标计算

**需求**：实现移动平均线（MA）计算函数

**Step 1: 写测试（Red）**

```python
# tests/unit/test_indicators.py
import pytest
from cherryquant.utils.indicators import calculate_ma


def test_calculate_ma_basic():
    """测试 MA 计算基本功能"""
    prices = [10, 20, 30, 40, 50]

    # MA(3) = 移动平均，窗口 3
    result = calculate_ma(prices, period=3)

    # 前两个应该是 NaN（数据不足）
    assert result[0] is None
    assert result[1] is None

    # 第三个：(10 + 20 + 30) / 3 = 20
    assert result[2] == 20.0

    # 第四个：(20 + 30 + 40) / 3 = 30
    assert result[3] == 30.0

    # 第五个：(30 + 40 + 50) / 3 = 40
    assert result[4] == 40.0


def test_calculate_ma_edge_cases():
    """测试边界条件"""
    # 空列表
    assert calculate_ma([], period=3) == []

    # 数据不足
    assert calculate_ma([10, 20], period=3) == [None, None]

    # period = 1（等于自身）
    assert calculate_ma([10, 20, 30], period=1) == [10, 20, 30]
```

**运行测试：**

```bash
pytest tests/unit/test_indicators.py
# ❌ 失败！因为 calculate_ma 还不存在
```

**Step 2: 写代码（Green）**

```python
# src/cherryquant/utils/indicators.py
from typing import List, Optional


def calculate_ma(prices: List[float], period: int) -> List[Optional[float]]:
    """
    计算移动平均线（MA）

    Args:
        prices: 价格序列
        period: 周期

    Returns:
        MA 序列，数据不足的位置为 None

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
            # 数据不足，返回 None
            result.append(None)
        else:
            # 计算平均值
            window = prices[i - period + 1 : i + 1]
            ma_value = sum(window) / period
            result.append(ma_value)

    return result
```

**运行测试：**

```bash
pytest tests/unit/test_indicators.py
# ✅ 通过！
```

**Step 3: 重构（Refactor）**

```python
# 优化：使用更 Pythonic 的方式
from typing import List, Optional


def calculate_ma(prices: List[float], period: int) -> List[Optional[float]]:
    """计算移动平均线（MA）"""
    if not prices:
        return []

    if period <= 0:
        raise ValueError("Period must be positive")

    # 使用列表推导式，更简洁
    return [
        None if i < period - 1
        else sum(prices[i - period + 1 : i + 1]) / period
        for i in range(len(prices))
    ]
```

**再次运行测试：**

```bash
pytest tests/unit/test_indicators.py
# ✅ 依然通过！重构成功
```

#### 5.3 TDD 的好处

- ✅ **先定义行为**：测试即规格说明
- ✅ **快速反馈**：立即知道代码是否正确
- ✅ **自信重构**：有测试保护，重构不怕破坏功能
- ✅ **文档化**：测试代码是最好的使用示例

---

### 第六部分：CI/CD 中的测试 (1 小时)

#### 6.1 自动化测试流程

**GitHub Actions 配置示例：**

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Run tests
        run: |
          uv run pytest --cov=src/cherryquant --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true
```

#### 6.2 Pre-commit Hooks

**防止提交未测试的代码：**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

---

## 实战练习

### 练习 1：为数据验证器编写测试

**任务**：为 `DataValidator` 编写完整的单元测试

```python
# 提示：需要测试的场景
# 1. 正常数据验证（应该通过）
# 2. 缺失必需字段（应该失败）
# 3. 数据类型错误（应该失败）
# 4. 异常值检测（应该标记）
```

### 练习 2：测试重试机制

**任务**：为 `retry_async` 装饰器编写测试

```python
# 提示：需要测试的场景
# 1. 首次成功（不应重试）
# 2. 重试后成功
# 3. 达到最大重试次数后失败
# 4. 指数退避延迟是否正确
```

### 练习 3：TDD 实现 RSI 指标

**任务**：使用 TDD 方法实现 RSI（相对强弱指标）计算

```python
# 步骤：
# 1. 先写测试（定义 RSI 的预期行为）
# 2. 实现代码让测试通过
# 3. 重构优化

# RSI 公式：
# RSI = 100 - (100 / (1 + RS))
# RS = 平均上涨幅度 / 平均下跌幅度
```

---

## 思考题

1. **为什么单元测试应该占测试的大多数（60-70%），而不是端到端测试？**

2. **在量化交易系统中，哪些模块的测试覆盖率应该最高？为什么？**

3. **Mock 和真实依赖各有什么优缺点？什么时候应该用 Mock？**

4. **如何测试随机性代码（如蒙特卡洛模拟）？**

5. **测试驱动开发（TDD）适合所有场景吗？什么时候不适合用 TDD？**

---

## 延伸阅读

### 推荐书籍

- 📖 *Test Driven Development: By Example* - Kent Beck
- 📖 *Growing Object-Oriented Software, Guided by Tests* - Steve Freeman & Nat Pryce
- 📖 *Python Testing with pytest* - Brian Okken

### 推荐资源

- 🎓 [pytest 官方文档](https://docs.pytest.org/)
- 🎓 [coverage.py 文档](https://coverage.readthedocs.io/)
- 🎓 [Python Mock 对象库](https://docs.python.org/3/library/unittest.mock.html)

### CherryQuant 相关文档

- 📄 `tests/unit/test_timeseries_repository.py` - 单元测试示例（33 个测试用例）
- 📄 `tests/integration/test_data_pipeline_integration.py` - 集成测试示例
- 📄 `tests/performance/benchmark_suite.py` - 性能测试示例

---

## 总结

完成本模块后，你应该：

- ✅ 理解测试金字塔（单元测试、集成测试、E2E 测试）
- ✅ 能使用 pytest 编写高质量测试
- ✅ 掌握异步代码和数据库测试方法
- ✅ 理解测试覆盖率的意义和局限性
- ✅ 能使用 TDD 方法开发新功能
- ✅ 了解 CI/CD 中的自动化测试流程

**记住：测试不是负担，而是保护你代码质量的盾牌。** 🛡️

在量化交易中，**好的测试 = 避免真金白银的损失**。

---

**下一步**: Lab 06 - 测试驱动开发实践 🧪
