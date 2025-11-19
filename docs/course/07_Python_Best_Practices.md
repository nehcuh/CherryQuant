# Module 7: Python 代码规范与最佳实践

## 课程信息

- **模块编号**: Module 7
- **难度**: ⭐⭐⭐ 中级
- **预计时间**: 6-8 小时
- **前置要求**: Module 0, 基础 Python 知识

## 学习目标

完成本模块后，你将能够：

1. ✅ 掌握 Python 类型提示（Type Hints）的使用
2. ✅ 使用 Mypy 进行静态类型检查
3. ✅ 理解并应用 PEP 8 代码风格规范
4. ✅ 使用现代代码格式化工具（Black, Ruff）
5. ✅ 编写规范的文档字符串（Docstring）
6. ✅ 掌握异步编程最佳实践
7. ✅ 理解 Python 项目的现代工具链

## 为什么代码规范很重要？

### 真实案例对比

**❌ 不规范的代码**:

```python
def get_data(s, t):
    d = []
    for i in range(len(s)):
        if s[i]['type'] == t:
            d.append(s[i])
    return d
```

**问题**:
- 变量名不明确（`s`, `t`, `d`, `i` 是什么？）
- 没有类型提示（参数和返回值类型未知）
- 没有文档字符串（函数功能不清晰）
- 使用低效的循环模式

**✅ 规范的代码**:

```python
from typing import List, Dict, Any

def filter_data_by_type(
    data_list: List[Dict[str, Any]],
    target_type: str
) -> List[Dict[str, Any]]:
    """
    根据类型字段过滤数据列表。

    Args:
        data_list: 包含字典的列表，每个字典必须有 'type' 字段
        target_type: 目标类型字符串

    Returns:
        过滤后的数据列表，仅包含指定类型的项

    Example:
        >>> data = [{"type": "A", "value": 1}, {"type": "B", "value": 2}]
        >>> filter_data_by_type(data, "A")
        [{"type": "A", "value": 1}]
    """
    return [item for item in data_list if item.get("type") == target_type]
```

**改进**:
- ✅ 清晰的函数和变量命名
- ✅ 完整的类型提示
- ✅ 详细的文档字符串
- ✅ 更简洁的列表推导式

---

## 课程大纲

### 第一部分：类型提示（Type Hints）(2 小时)

#### 1.1 基础类型提示

**为什么需要类型提示？**

Python 是动态类型语言，但类型提示可以：
- 🐛 提前发现类型错误（通过 Mypy 静态检查）
- 📖 改善代码可读性
- 🔧 增强 IDE 的智能提示
- 🧪 帮助生成更好的文档

**基本类型**:

```python
from typing import List, Dict, Tuple, Set, Optional, Union

# 基础类型
name: str = "CherryQuant"
count: int = 100
price: float = 3500.5
is_active: bool = True

# 集合类型
symbols: List[str] = ["rb2501", "hc2501", "i2501"]
prices: Dict[str, float] = {"rb2501": 3500.0, "hc2501": 3200.0}
coordinates: Tuple[float, float] = (39.9, 116.4)
unique_ids: Set[int] = {1, 2, 3}

# 可选类型（可以是 None）
result: Optional[str] = None  # 等价于 Union[str, None]
data: Union[int, str] = 42    # 可以是 int 或 str
```

**函数类型提示**:

```python
def calculate_position_size(
    capital: float,           # 总资金
    risk_ratio: float,        # 风险比例
    entry_price: float,       # 入场价格
    stop_loss: float          # 止损价格
) -> int:                     # 返回持仓手数
    """计算持仓手数"""
    risk_amount = capital * risk_ratio
    price_diff = abs(entry_price - stop_loss)
    position_size = risk_amount / price_diff
    return int(position_size)
```

**类的类型提示**:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class KlineData:
    """K线数据"""
    symbol: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int

    def is_bullish(self) -> bool:
        """判断是否为阳线"""
        return self.close > self.open
```

#### 1.2 高级类型提示

**Protocol（结构化子类型）**:

```python
from typing import Protocol, List

class DataAdapter(Protocol):
    """数据适配器接口（使用 Protocol 定义）"""

    async def fetch_kline(
        self,
        symbol: str,
        start: str,
        end: str
    ) -> List[KlineData]:
        """获取 K 线数据"""
        ...

# 任何实现了 fetch_kline 方法的类都满足 DataAdapter 协议
class TushareAdapter:
    async def fetch_kline(
        self,
        symbol: str,
        start: str,
        end: str
    ) -> List[KlineData]:
        # 实现
        ...

# Mypy 会认为 TushareAdapter 满足 DataAdapter 协议
def process_data(adapter: DataAdapter) -> None:
    # adapter 可以是任何实现了 fetch_kline 的对象
    ...
```

**泛型（Generic）**:

```python
from typing import TypeVar, Generic, List

T = TypeVar('T')  # 类型变量

class Repository(Generic[T]):
    """通用仓储模式"""

    def __init__(self):
        self._items: List[T] = []

    def add(self, item: T) -> None:
        """添加项"""
        self._items.append(item)

    def get_all(self) -> List[T]:
        """获取所有项"""
        return self._items

# 使用泛型
kline_repo: Repository[KlineData] = Repository()
kline_repo.add(KlineData(...))  # ✅ 正确
kline_repo.add("string")         # ❌ Mypy 会报错
```

**Callable（可调用对象）**:

```python
from typing import Callable

# 函数类型：接受 (str, float) 返回 bool
RiskCheckFunc = Callable[[str, float], bool]

def check_position_risk(symbol: str, size: float) -> bool:
    """检查持仓风险"""
    return size <= MAX_POSITION_SIZE

def execute_with_check(
    action: Callable[[], None],      # 无参数无返回值的函数
    risk_check: RiskCheckFunc        # 风险检查函数
) -> None:
    if risk_check("rb2501", 10.0):
        action()
```

#### 1.3 CherryQuant 中的类型提示示例

**数据模型**:

```python
# src/cherryquant/adapters/data_adapter/history_data_manager.py
from typing import List, Optional
from datetime import datetime

class HistoryDataManager:
    def __init__(
        self,
        adapter: DataAdapter,
        storage: DatabaseManager
    ):
        self.adapter: DataAdapter = adapter
        self.storage: DatabaseManager = storage

    async def fetch_history(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d"
    ) -> Optional[List[KlineData]]:
        """
        获取历史数据

        Args:
            symbol: 合约代码
            start_date: 开始日期
            end_date: 结束日期
            interval: 时间间隔

        Returns:
            K线数据列表，如果获取失败返回 None
        """
        try:
            data = await self.adapter.fetch_kline(
                symbol=symbol,
                start=start_date.strftime("%Y%m%d"),
                end=end_date.strftime("%Y%m%d")
            )
            return data
        except Exception as e:
            logger.error("Failed to fetch history", error=str(e))
            return None
```

---

### 第二部分：Mypy 静态类型检查 (1 小时)

#### 2.1 什么是 Mypy？

Mypy 是 Python 的静态类型检查器，可以在运行前发现类型错误。

**安装和使用**:

```bash
# 安装
uv add --dev mypy

# 检查单个文件
mypy src/cherryquant/adapters/data_adapter.py

# 检查整个项目
mypy src/
```

#### 2.2 配置 Mypy

**`pyproject.toml` 配置**:

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true        # 要求所有函数有类型提示
disallow_any_generics = false
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
check_untyped_defs = true
strict_equality = true

# 忽略第三方库的类型检查
[[tool.mypy.overrides]]
module = [
    "vnpy.*",
    "tushare.*",
]
ignore_missing_imports = true
```

#### 2.3 常见 Mypy 错误和修复

**错误 1: 缺少类型提示**

```python
# ❌ Mypy 错误
def process_data(data):  # error: Function is missing a type annotation
    return data

# ✅ 修复
def process_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return data
```

**错误 2: 类型不匹配**

```python
# ❌ Mypy 错误
def get_price(symbol: str) -> float:
    return "3500"  # error: Incompatible return value type (got "str", expected "float")

# ✅ 修复
def get_price(symbol: str) -> float:
    return 3500.0
```

**错误 3: Optional 类型未检查**

```python
# ❌ Mypy 错误
def process(value: Optional[str]) -> int:
    return len(value)  # error: Argument 1 has incompatible type "Optional[str]"

# ✅ 修复
def process(value: Optional[str]) -> int:
    if value is None:
        return 0
    return len(value)
```

---

### 第三部分：代码格式化工具 (1.5 小时)

#### 3.1 Black - 代码格式化

**特点**: "毫不妥协的代码格式化器"

```bash
# 安装
uv add --dev black

# 格式化文件
black src/cherryquant/

# 检查但不修改
black --check src/
```

**示例转换**:

```python
# 格式化前
def very_long_function_name(parameter_one,parameter_two,parameter_three,parameter_four,parameter_five):
    return parameter_one+parameter_two+parameter_three

# 格式化后
def very_long_function_name(
    parameter_one,
    parameter_two,
    parameter_three,
    parameter_four,
    parameter_five,
):
    return (
        parameter_one
        + parameter_two
        + parameter_three
    )
```

**配置**:

```toml
[tool.black]
line-length = 100
target-version = ['py312']
include = '\.pyi?$'
extend-exclude = '''
/(
  # 排除的目录
  \.git
  | \.mypy_cache
  | \.venv
  | build
  | dist
)/
'''
```

#### 3.2 Ruff - 快速 Linter

**特点**: 比 Flake8/Pylint 快 10-100 倍

```bash
# 安装
uv add --dev ruff

# 检查
ruff check src/

# 自动修复
ruff check --fix src/

# 格式化（Ruff 也支持格式化）
ruff format src/
```

**配置**:

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]

ignore = [
    "E501",  # 行长度由 black 处理
    "B008",  # 不禁止函数调用在参数默认值
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]  # 允许未使用的导入
```

#### 3.3 Pre-commit Hook

**自动化代码质量检查**:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

**安装和使用**:

```bash
# 安装 pre-commit
uv add --dev pre-commit

# 安装 git hooks
pre-commit install

# 手动运行所有检查
pre-commit run --all-files
```

---

### 第四部分：文档字符串规范 (1.5 小时)

#### 4.1 文档字符串风格

**CherryQuant 使用 Google 风格**:

```python
def fetch_market_data(
    symbol: str,
    start_date: str,
    end_date: str,
    data_type: str = "daily"
) -> List[KlineData]:
    """
    从数据源获取市场数据。

    这个函数会尝试从缓存读取数据，如果缓存未命中则从数据源获取。
    获取的数据会自动保存到数据库以供后续使用。

    Args:
        symbol: 期货合约代码，例如 "rb2501"
        start_date: 开始日期，格式 "YYYYMMDD"
        end_date: 结束日期，格式 "YYYYMMDD"
        data_type: 数据类型，可选值: "daily", "minute", "tick"
            默认为 "daily"

    Returns:
        K线数据列表，按时间升序排列。如果没有数据返回空列表。

    Raises:
        ValueError: 如果日期格式不正确
        APIError: 如果数据源 API 调用失败
        DatabaseError: 如果数据库操作失败

    Example:
        >>> data = await fetch_market_data("rb2501", "20240101", "20240131")
        >>> len(data)
        22
        >>> data[0].symbol
        "rb2501"

    Note:
        - 日期范围最大不超过 1 年
        - 历史数据有 15 分钟延迟
        - 数据会自动去重和排序

    See Also:
        - fetch_realtime_data: 获取实时数据
        - HistoryDataManager: 历史数据管理器
    """
    # 实现
    ...
```

**关键部分**:

1. **简短描述**: 第一行简洁说明功能
2. **详细说明**: 第二段详细描述行为
3. **Args**: 参数说明（类型、含义、默认值）
4. **Returns**: 返回值说明
5. **Raises**: 可能抛出的异常
6. **Example**: 使用示例（非常重要！）
7. **Note**: 注意事项
8. **See Also**: 相关函数/类

#### 4.2 类的文档字符串

```python
class AIDecisionEngine:
    """
    AI 驱动的交易决策引擎。

    使用大语言模型（LLM）分析市场数据并生成交易决策。
    决策基于技术指标、市场趋势和风险评估。

    Attributes:
        llm_client: OpenAI API 客户端
        market_data: 市场数据管理器
        logger: 结构化日志记录器

    Example:
        >>> engine = AIDecisionEngine(llm_client, market_data, logger)
        >>> decision = await engine.make_decision("rb2501")
        >>> decision.action
        "BUY"
        >>> decision.confidence
        0.75

    Note:
        - 需要有效的 OpenAI API Key
        - 每次决策约消耗 1000 tokens
        - 建议设置置信度阈值过滤低信心决策
    """

    def __init__(
        self,
        llm_client: AsyncOpenAIClient,
        market_data: MarketDataManager,
        logger: structlog.BoundLogger
    ):
        """
        初始化 AI 决策引擎。

        Args:
            llm_client: OpenAI API 客户端实例
            market_data: 市场数据管理器实例
            logger: 结构化日志记录器
        """
        self.llm = llm_client
        self.market_data = market_data
        self.logger = logger
```

#### 4.3 模块级文档字符串

```python
"""
数据适配器模块。

这个模块包含所有数据源的适配器实现，遵循适配器模式。
每个适配器实现 DataAdapter 协议，提供统一的数据获取接口。

支持的数据源:
    - Tushare: 中国金融数据接口
    - VNPy: 实时行情和交易接口
    - QuantBox: 高性能历史数据

Example:
    >>> from cherryquant.adapters.data_adapter import TushareAdapter
    >>> adapter = TushareAdapter(token="your_token")
    >>> data = await adapter.fetch_kline("rb2501", "20240101", "20240131")

See Also:
    - docs/course/02_Data_Pipeline.md: 数据管道设计文档
    - DataAdapter Protocol: 数据适配器接口定义
"""

from .tushare_adapter import TushareAdapter
from .vnpy_adapter import VNPyAdapter
from .quantbox_adapter import QuantBoxAdapter

__all__ = ["TushareAdapter", "VNPyAdapter", "QuantBoxAdapter"]
```

---

### 第五部分：异步编程最佳实践 (2 小时)

#### 5.1 Async/Await 基础

**基本概念**:

```python
import asyncio

# 定义异步函数
async def fetch_data(symbol: str) -> dict:
    """异步获取数据"""
    await asyncio.sleep(1)  # 模拟 I/O 等待
    return {"symbol": symbol, "price": 3500}

# 调用异步函数
async def main():
    # 单次调用
    data = await fetch_data("rb2501")

    # 并发调用
    results = await asyncio.gather(
        fetch_data("rb2501"),
        fetch_data("hc2501"),
        fetch_data("i2501")
    )
```

#### 5.2 常见错误和最佳实践

**❌ 错误 1: 忘记 await**

```python
# ❌ 错误
async def bad_example():
    data = fetch_data("rb2501")  # 返回 coroutine 对象，未执行
    print(data)  # <coroutine object fetch_data at 0x...>

# ✅ 正确
async def good_example():
    data = await fetch_data("rb2501")  # 等待执行完成
    print(data)  # {"symbol": "rb2501", "price": 3500}
```

**❌ 错误 2: 阻塞事件循环**

```python
# ❌ 错误：使用同步库阻塞事件循环
async def bad_example():
    import time
    time.sleep(5)  # 阻塞整个事件循环！

# ✅ 正确：使用异步等待
async def good_example():
    await asyncio.sleep(5)  # 不阻塞事件循环

# ✅ 正确：使用 run_in_executor 运行同步代码
async def good_example_2():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,  # 使用默认线程池
        blocking_function,  # 同步函数
        arg1, arg2  # 参数
    )
```

**✅ 最佳实践: 异步上下文管理器**

```python
class DatabaseConnection:
    async def __aenter__(self):
        """异步进入上下文"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步退出上下文"""
        await self.close()

# 使用
async def main():
    async with DatabaseConnection() as db:
        data = await db.query("SELECT * FROM kline")
    # 自动关闭连接
```

**✅ 最佳实践: 并发控制**

```python
from asyncio import Semaphore

# 限制并发数
async def fetch_with_limit(symbols: List[str], max_concurrent: int = 5):
    """限制最大并发数的数据获取"""
    semaphore = Semaphore(max_concurrent)

    async def fetch_one(symbol: str):
        async with semaphore:  # 获取信号量
            return await fetch_data(symbol)

    tasks = [fetch_one(symbol) for symbol in symbols]
    return await asyncio.gather(*tasks)
```

#### 5.3 CherryQuant 中的异步模式

**模式 1: 异步初始化**

```python
class MarketDataManager:
    def __init__(self, config: Config):
        """同步构造函数（仅赋值）"""
        self.config = config
        self._client = None

    async def initialize(self) -> None:
        """异步初始化（建立连接等）"""
        self._client = await create_async_client(self.config)

    async def close(self) -> None:
        """异步清理"""
        if self._client:
            await self._client.close()

# 使用
async def main():
    manager = MarketDataManager(config)
    await manager.initialize()
    try:
        data = await manager.get_data("rb2501")
    finally:
        await manager.close()
```

**模式 2: 异步迭代器**

```python
class RealtimeDataStream:
    """实时数据流（异步迭代器）"""

    async def __aiter__(self):
        return self

    async def __anext__(self):
        data = await self._fetch_next()
        if data is None:
            raise StopAsyncIteration
        return data

# 使用
async def consume_stream():
    async for tick_data in RealtimeDataStream():
        await process_tick(tick_data)
```

---

### 第六部分：项目工具链集成 (1 小时)

#### 6.1 完整的 pyproject.toml

```toml
[project]
name = "cherryquant"
version = "0.1.0"
description = "AI-Driven Quantitative Trading Education Project"
requires-python = ">=3.12"

[tool.uv]
dev-dependencies = [
    "black>=23.12.0",
    "ruff>=0.1.9",
    "mypy>=1.8.0",
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pre-commit>=3.6.0",
]

[tool.black]
line-length = 100
target-version = ['py312']

[tool.ruff]
target-version = "py312"
line-length = 100
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
disallow_untyped_defs = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
```

#### 6.2 Makefile 快捷命令

```makefile
.PHONY: format check test

# 代码格式化
format:
	uv run black src/ tests/
	uv run ruff check --fix src/ tests/

# 代码检查
check:
	uv run black --check src/ tests/
	uv run ruff check src/ tests/
	uv run mypy src/

# 运行测试
test:
	uv run pytest tests/ -v

# 全面检查
ci: check test

# 安装开发依赖
setup:
	uv sync --dev
	pre-commit install
```

**使用**:

```bash
make format  # 格式化代码
make check   # 检查代码质量
make test    # 运行测试
make ci      # CI 流程
```

---

## 实践练习

### Lab 07: 代码规范实践 (4 小时)

**目标**: 应用所学的代码规范改进现有代码

**任务**:

1. **类型提示练习** (1 小时)
   - 为 `examples/` 下的示例添加完整类型提示
   - 运行 `mypy` 确保无错误

2. **文档字符串练习** (1 小时)
   - 为一个模块编写完整的文档字符串
   - 包括模块级、类级、函数级文档

3. **代码格式化** (30 分钟)
   - 使用 Black 和 Ruff 格式化代码
   - 修复所有 Ruff 警告

4. **异步重构** (1.5 小时)
   - 将一个同步函数重构为异步版本
   - 添加适当的错误处理和资源清理

**提交内容**:
- 重构后的代码文件
- Mypy 检查通过的截图
- 学习笔记（重点记录遇到的问题和解决方法）

**评分标准** (15 分):
- 类型提示完整性 (4 分)
- 文档字符串质量 (4 分)
- 代码格式规范 (3 分)
- 异步重构正确性 (4 分)

---

## 自我评估

- [ ] 我能为函数和类添加准确的类型提示
- [ ] 我能使用 Mypy 检查并修复类型错误
- [ ] 我能使用 Black/Ruff 格式化代码
- [ ] 我能编写规范的 Google 风格文档字符串
- [ ] 我理解异步编程的最佳实践
- [ ] 我能配置和使用现代 Python 工具链

## 扩展阅读

- **PEP 8**: [Style Guide for Python Code](https://peps.python.org/pep-0008/)
- **PEP 484**: [Type Hints](https://peps.python.org/pep-0484/)
- **PEP 544**: [Protocols](https://peps.python.org/pep-0544/)
- **Mypy 文档**: https://mypy.readthedocs.io/
- **Black 文档**: https://black.readthedocs.io/
- **Ruff 文档**: https://docs.astral.sh/ruff/
- **Python Async/Await**: https://docs.python.org/3/library/asyncio.html

## 下一步

- **Module 6**: 单元测试与 TDD
- **Module 8**: 系统集成与部署
- **综合实践**: 构建完整的交易策略

---

**💡 学习提示**: 代码规范不是一蹴而就的，需要在实践中不断应用和内化。建议每次写代码时都使用工具检查，逐渐养成良好习惯。
