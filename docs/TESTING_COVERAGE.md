# 测试覆盖率指南

## 概述

CherryQuant 使用 `pytest-cov` 来生成测试覆盖率报告，帮助识别未测试的代码路径。

## 快速开始

### 运行所有测试并生成覆盖率报告

```bash
# 运行所有测试，生成覆盖率报告
uv run pytest

# 或使用传统 pip 环境
pytest
```

这将：
- 运行所有测试
- 显示覆盖率摘要
- 生成 HTML 报告（在 `htmlcov/` 目录）
- 生成 XML 报告（`coverage.xml`，用于 CI）

### 查看详细的 HTML 报告

```bash
# 生成并打开 HTML 报告
open htmlcov/index.html

# 或在 Linux 上
xdg-open htmlcov/index.html
```

## 覆盖率配置

### 当前目标

- **最低覆盖率**: 50%（配置在 `pytest.ini`）
- **目标覆盖率**: 80%（核心模块）

### 覆盖率阈值

| 模块 | 当前 | 目标 |
|------|------|------|
| AI 决策引擎 | TBD | 85% |
| 数据适配器 | TBD | 80% |
| 风险管理 | TBD | 90% |
| 数据库管理 | TBD | 75% |
| Bootstrap | TBD | 70% |

## 运行特定测试的覆盖率

### 单个测试文件

```bash
pytest tests/test_ai_engine.py --cov=src/cherryquant/ai
```

### 特定模块

```bash
# 只测试 AI 模块的覆盖率
pytest --cov=src/cherryquant/ai --cov-report=term-missing

# 只测试数据适配器
pytest --cov=src/cherryquant/adapters --cov-report=html
```

### 显示未覆盖的行

```bash
pytest --cov=src/cherryquant --cov-report=term-missing
```

输出示例：
```
src/cherryquant/ai/decision_engine/futures_engine.py    85%   45-48, 72-74
src/cherryquant/adapters/data_adapter/market_data_manager.py   92%   102, 156-158
```

## 覆盖率报告类型

### 1. 终端报告（term-missing）

最快的反馈，显示：
- 每个文件的覆盖率百分比
- 未覆盖的行号

```bash
pytest --cov-report=term-missing
```

### 2. HTML 报告

最详细的可视化报告：
- 每个文件的逐行覆盖情况
- 彩色高亮显示覆盖/未覆盖的代码
- 分支覆盖率信息

```bash
pytest --cov-report=html
open htmlcov/index.html
```

### 3. XML 报告（用于 CI）

机器可读格式，用于：
- CI/CD 集成
- 代码质量工具（SonarQube, Codecov）
- 趋势分析

```bash
pytest --cov-report=xml
```

## 提高覆盖率

### 识别未覆盖的代码

1. **运行覆盖率报告**
   ```bash
   pytest --cov=src/cherryquant --cov-report=term-missing
   ```

2. **查看 HTML 报告**
   ```bash
   open htmlcov/index.html
   ```

3. **按优先级排序**
   - 核心业务逻辑（AI 决策、风险管理）优先
   - 边缘案例次之
   - 错误处理路径

### 编写有效的测试

#### 示例 1：测试 AI 决策引擎

```python
# tests/unit/test_futures_engine.py
import pytest
from unittest.mock import AsyncMock, Mock
from cherryquant.ai.decision_engine.futures_engine import FuturesDecisionEngine


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing"""
    client = AsyncMock()
    return client


@pytest.fixture
def futures_engine(mock_llm_client):
    """Create futures engine with mocked dependencies"""
    config = Mock()
    config.ai.model = "gpt-4"
    return FuturesDecisionEngine(llm_client=mock_llm_client, config=config)


@pytest.mark.asyncio
async def test_make_decision_success(futures_engine, mock_llm_client):
    """Test successful AI decision making"""
    # Arrange
    mock_llm_client.get_decision.return_value = {
        "action": "BUY",
        "confidence": 0.85,
        "reason": "Strong uptrend"
    }

    # Act
    decision = await futures_engine.make_decision("rb2501", {"price": 3500})

    # Assert
    assert decision["action"] == "BUY"
    assert decision["confidence"] == 0.85
    mock_llm_client.get_decision.assert_called_once()


@pytest.mark.asyncio
async def test_make_decision_api_failure(futures_engine, mock_llm_client):
    """Test fallback when AI API fails"""
    # Arrange
    mock_llm_client.get_decision.side_effect = Exception("API Error")

    # Act
    decision = await futures_engine.make_decision("rb2501", {"price": 3500})

    # Assert
    assert decision["action"] == "HOLD"  # Fallback to conservative decision
    assert "error" in decision
```

#### 示例 2：参数化测试风险管理

```python
# tests/unit/test_risk_manager.py
import pytest
from cherryquant.risk.portfolio_risk_manager import PortfolioRiskManager


@pytest.mark.parametrize("position_value,max_value,expected", [
    (100000, 500000, True),   # Under limit
    (500000, 500000, True),   # At limit
    (600000, 500000, False),  # Over limit
    (0, 500000, True),        # Edge case: zero
    (-100000, 500000, False), # Edge case: negative
])
def test_check_position_limits(position_value, max_value, expected):
    """Test position limit checking with various scenarios"""
    risk_manager = PortfolioRiskManager(max_position_value=max_value)
    result = risk_manager.check_position_limits("rb2501", position_value)
    assert result == expected
```

#### 示例 3：测试边缘案例

```python
# tests/unit/test_contract_resolver.py
import pytest
from cherryquant.adapters.data_adapter.contract_resolver import ContractResolver


@pytest.mark.asyncio
async def test_resolve_contract_empty_commodity():
    """Test contract resolution with empty commodity code"""
    resolver = ContractResolver()

    with pytest.raises(ValueError, match="commodity code cannot be empty"):
        await resolver.resolve_dominant_contract("")


@pytest.mark.asyncio
async def test_resolve_contract_invalid_format():
    """Test contract resolution with invalid commodity format"""
    resolver = ContractResolver()

    with pytest.raises(ValueError, match="invalid commodity format"):
        await resolver.resolve_dominant_contract("INVALID123!@#")


@pytest.mark.asyncio
async def test_resolve_contract_network_timeout():
    """Test contract resolution network timeout handling"""
    resolver = ContractResolver(timeout=0.001)  # Very short timeout

    with pytest.raises(TimeoutError):
        await resolver.resolve_dominant_contract("rb")
```

## 覆盖率 vs 质量

### ⚠️ 重要提示

高覆盖率不等于高质量！

```python
# ❌ 100% 覆盖率，但测试无效
def test_calculate_total():
    result = calculate_total([1, 2, 3])
    assert result  # 只检查返回值存在，但不检查正确性！

# ✅ 有意义的测试
def test_calculate_total():
    result = calculate_total([1, 2, 3])
    assert result == 6  # 检查正确的计算结果
    assert isinstance(result, int)  # 检查类型
```

### 覆盖率目标

- **不要追求 100% 覆盖率** - 成本太高，收益递减
- **关注核心业务逻辑** - 80-90% 覆盖率是合理目标
- **忽略简单的 getter/setter** - 除非包含业务逻辑
- **边缘案例很重要** - 测试错误处理路径

## CI/CD 集成

### GitHub Actions

覆盖率报告已集成到 CI 流程（`.github/workflows/ci.yml`）：

```yaml
- name: Run tests with coverage
  run: |
    uv run pytest --cov=src/cherryquant --cov-report=xml --cov-report=term-missing

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
    fail_ci_if_error: false
```

### 覆盖率徽章

在 README.md 中显示覆盖率徽章：

```markdown
[![Coverage](https://codecov.io/gh/your-org/cherryquant/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/cherryquant)
```

## 最佳实践

### ✅ 推荐做法

1. **在每次提交前运行测试**
   ```bash
   # 添加到 .git/hooks/pre-commit
   #!/bin/bash
   uv run pytest --cov=src/cherryquant --cov-fail-under=50
   ```

2. **定期查看覆盖率报告**
   - 每周查看 HTML 报告
   - 识别低覆盖率模块
   - 优先测试核心功能

3. **使用 --cov-fail-under 保证最低覆盖率**
   ```bash
   pytest --cov-fail-under=80  # 低于 80% 会失败
   ```

4. **关注分支覆盖率**
   ```bash
   pytest --cov --cov-branch
   ```

### ❌ 避免的做法

1. **不要为了覆盖率而写测试**
   - 测试应该验证行为，不是覆盖行数

2. **不要忽略失败的测试**
   - 修复测试或移除无效测试

3. **不要在测试中使用真实的外部服务**
   - 使用 mock 和 fixture
   - 保持测试快速和可重复

4. **不要提交覆盖率文件到 git**
   - `.coverage`, `htmlcov/`, `coverage.xml` 应在 `.gitignore`

## 故障排查

### 问题：覆盖率为 0%

检查 `pytest.ini` 中的 source 路径是否正确：
```ini
[pytest]
addopts = --cov=src/cherryquant
```

### 问题：某些文件未包含在覆盖率中

检查 `.coveragerc` 中的 omit 规则：
```ini
[run]
omit =
    */tests/*
    */third_party/*
```

### 问题：覆盖率报告未生成

确保 pytest-cov 已安装：
```bash
uv sync --dev
# 或
pip install pytest-cov
```

## 参考资源

- [pytest-cov 文档](https://pytest-cov.readthedocs.io/)
- [Coverage.py 文档](https://coverage.readthedocs.io/)
- [测试金字塔模型](https://martinfowler.com/articles/practical-test-pyramid.html)
- [有效的单元测试](https://testing.googleblog.com/)
