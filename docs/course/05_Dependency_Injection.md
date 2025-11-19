# Module 5: 依赖注入实战

## 课程信息

- **模块编号**: Module 5
- **难度**: ⭐⭐⭐⭐ 高级
- **预计时间**: 8-10 小时
- **前置要求**: Module 1, Module 2, Module 3

## 学习目标

完成本模块后，你将能够：

1. ✅ 深入理解依赖注入（Dependency Injection）的原理和价值
2. ✅ 掌握 Composition Root 模式的设计和实现
3. ✅ 理解控制反转（Inversion of Control, IoC）原则
4. ✅ 能够重构代码，消除硬编码依赖
5. ✅ 设计可测试的组件和接口
6. ✅ 应用依赖注入改善系统架构

## 为什么需要依赖注入？

### 问题场景：硬编码依赖的困境

假设我们要构建一个交易系统：

```python
# ❌ 反例：硬编码依赖
class TradingSystem:
    def __init__(self):
        # 在构造函数中直接创建依赖
        self.database = MongoDBManager()
        self.data_source = TushareAdapter()
        self.ai_engine = AIDecisionEngine()
        self.risk_manager = RiskManager()

    async def run(self):
        data = await self.data_source.fetch_data("rb2501")
        decision = await self.ai_engine.decide(data)
        if self.risk_manager.check(decision):
            await self.database.save_order(decision)
```

**这段代码的问题**:

1. **难以测试**
   - 无法替换 `MongoDBManager` 为测试桩
   - 每次测试都会连接真实数据库
   - AI 调用会消耗真实 API 配额

2. **难以替换实现**
   - 想换用 PostgreSQL？需要修改 `TradingSystem` 源码
   - 想用 QuantBox 替代 Tushare？同样需要改代码
   - 违反"开闭原则"（对扩展开放，对修改关闭）

3. **紧耦合**
   - `TradingSystem` 强依赖具体实现类
   - 一旦 `MongoDBManager` 构造函数变化，`TradingSystem` 必须修改
   - 牵一发而动全身

4. **配置分散**
   - 各个组件的配置（连接字符串、API Key）散落各处
   - 难以统一管理和修改

### 解决方案：依赖注入

```python
# ✅ 正例：依赖注入
class TradingSystem:
    def __init__(
        self,
        database: DatabaseManager,       # 注入依赖（接口）
        data_source: DataAdapter,        # 注入依赖
        ai_engine: AIDecisionEngine,     # 注入依赖
        risk_manager: RiskManager        # 注入依赖
    ):
        self.database = database
        self.data_source = data_source
        self.ai_engine = ai_engine
        self.risk_manager = risk_manager

    async def run(self):
        data = await self.data_source.fetch_data("rb2501")
        decision = await self.ai_engine.decide(data)
        if self.risk_manager.check(decision):
            await self.database.save_order(decision)

# 生产环境：注入真实实现
system = TradingSystem(
    database=MongoDBManager(),
    data_source=TushareAdapter(),
    ai_engine=AIDecisionEngine(),
    risk_manager=RiskManager()
)

# 测试环境：注入 Mock
system_test = TradingSystem(
    database=MockDatabase(),
    data_source=MockDataSource(),
    ai_engine=MockAI(),
    risk_manager=MockRiskManager()
)
```

**优势**:

- ✅ **易于测试**: 可以注入 Mock 对象
- ✅ **灵活替换**: 切换实现只需修改注入参数
- ✅ **松耦合**: `TradingSystem` 只依赖接口，不依赖具体实现
- ✅ **配置集中**: 所有依赖在一处创建和配置

---

## 课程大纲

### 第一部分：依赖注入基础 (2 小时)

#### 1.1 核心概念

**依赖注入 (Dependency Injection, DI)**

> 一个对象接收它所依赖的其他对象（依赖），而不是自己创建它们。

**控制反转 (Inversion of Control, IoC)**

> 传统模式：对象自己控制依赖的创建和生命周期
> IoC 模式：框架/容器控制依赖的创建和注入

**三种注入方式**:

1. **构造函数注入** (推荐)
   ```python
   class Service:
       def __init__(self, dependency: Dependency):
           self.dependency = dependency
   ```

2. **属性注入**
   ```python
   class Service:
       dependency: Dependency = None  # 后续赋值
   ```

3. **方法注入**
   ```python
   class Service:
       def set_dependency(self, dependency: Dependency):
           self.dependency = dependency
   ```

**CherryQuant 使用构造函数注入**，因为它有以下优势：
- ✅ 依赖明确（在签名中）
- ✅ 对象创建即可用（不会出现半初始化状态）
- ✅ 便于静态类型检查

#### 1.2 接口与实现分离

**Python 的接口定义**:

```python
from typing import Protocol, List

# 方式 1: Protocol (推荐，Python 3.8+)
class DataAdapter(Protocol):
    """数据适配器接口"""

    async def fetch_kline(
        self, symbol: str, start: str, end: str
    ) -> List[KlineData]:
        """获取 K 线数据"""
        ...

# 方式 2: ABC (抽象基类)
from abc import ABC, abstractmethod

class DataAdapter(ABC):
    @abstractmethod
    async def fetch_kline(
        self, symbol: str, start: str, end: str
    ) -> List[KlineData]:
        pass
```

**实现接口**:

```python
# TushareAdapter 实现 DataAdapter 接口
class TushareAdapter:
    def __init__(self, token: str):
        self.api = ts.pro_api(token)

    async def fetch_kline(
        self, symbol: str, start: str, end: str
    ) -> List[KlineData]:
        # 调用 Tushare API
        df = self.api.daily(ts_code=symbol, start_date=start, end_date=end)
        return self._convert_to_kline(df)

# QuantBoxAdapter 实现同样的接口
class QuantBoxAdapter:
    def __init__(self, api_key: str):
        self.client = QuantBoxClient(api_key)

    async def fetch_kline(
        self, symbol: str, start: str, end: str
    ) -> List[KlineData]:
        # 调用 QuantBox API
        data = await self.client.get_kline(symbol, start, end)
        return self._convert_to_kline(data)
```

**使用接口**:

```python
class HistoryDataManager:
    def __init__(self, adapter: DataAdapter):  # 依赖接口，非具体类
        self.adapter = adapter

    async def get_history(self, symbol: str):
        return await self.adapter.fetch_kline(
            symbol, "20240101", "20241231"
        )

# 可以注入任何实现了 DataAdapter 接口的类
manager1 = HistoryDataManager(TushareAdapter(token="xxx"))
manager2 = HistoryDataManager(QuantBoxAdapter(api_key="yyy"))
```

---

### 第二部分：Composition Root 模式 (3 小时)

#### 2.1 什么是 Composition Root？

**定义**: 应用程序中**唯一**负责创建和组装所有依赖的地方。

**原则**:
- 🎯 所有依赖在应用启动时一次性创建
- 🎯 业务代码中**绝不** `new` 或直接创建依赖
- 🎯 Composition Root 是依赖图的"根"

**CherryQuant 的 Composition Root**:

`src/cherryquant/bootstrap/app_context.py`

```python
@dataclass
class AppContext:
    """运行时应用上下文"""

    config: CherryQuantConfig      # 配置
    db: DatabaseManager            # 数据库管理器
    ai_client: AsyncOpenAIClient   # AI 客户端

    async def close(self) -> None:
        """优雅关闭所有连接"""
        await self.db.close()
        await self.ai_client.aclose()

async def create_app_context(
    config: Optional[CherryQuantConfig] = None
) -> AppContext:
    """创建应用上下文（Composition Root）"""

    # 1. 加载配置
    if config is None:
        config = CherryQuantConfig.from_env()

    # 2. 配置日志
    configure_logging(
        log_level=config.logging.level,
        json_logs=config.logging.json_logs,
    )

    # 3. 创建 MongoDB 连接管理器
    mongodb_manager = await MongoDBConnectionPool.get_manager(
        uri=config.database.mongodb_uri,
        database=config.database.mongodb_database,
        min_pool_size=config.database.mongodb_min_pool_size,
        max_pool_size=config.database.mongodb_max_pool_size,
    )

    # 4. 创建 Redis 客户端
    redis_client = aioredis.from_url(
        f"redis://{config.database.redis_host}:{config.database.redis_port}",
        db=config.database.redis_db,
        decode_responses=True,
    )

    # 5. 组装 DatabaseManager (依赖注入)
    db_manager = DatabaseManager(
        mongodb_manager=mongodb_manager,
        redis_client=redis_client,
        cache_ttl=config.database.cache_ttl,
    )

    # 6. 创建 AI 客户端
    ai_client = AsyncOpenAIClient(config.ai)

    # 7. 返回应用上下文
    return AppContext(
        config=config,
        db=db_manager,
        ai_client=ai_client
    )
```

#### 2.2 使用 AppContext

**在主程序中使用**:

```python
# run_cherryquant.py
async def main():
    # 创建应用上下文（所有依赖在此组装）
    app = await create_app_context()

    try:
        # 使用注入的依赖
        decision_engine = AIDecisionEngine(
            llm_client=app.ai_client,
            db=app.db
        )

        trading_executor = TradingExecutor(
            db=app.db,
            risk_manager=RiskManager(app.config.risk)
        )

        # 运行交易循环
        await run_trading_loop(decision_engine, trading_executor)

    finally:
        # 优雅关闭
        await app.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**依赖图可视化**:

```
AppContext (Composition Root)
    ├── CherryQuantConfig (from .env)
    │
    ├── DatabaseManager
    │     ├── MongoDBConnectionPool
    │     │     └── AsyncIOMotorClient
    │     └── Redis AsyncClient
    │
    └── AsyncOpenAIClient
          └── OpenAI API

↓ 注入到

AIDecisionEngine
    ├── llm_client: AsyncOpenAIClient   ← 来自 AppContext
    └── db: DatabaseManager             ← 来自 AppContext

TradingExecutor
    ├── db: DatabaseManager             ← 来自 AppContext
    └── risk_manager: RiskManager
```

#### 2.3 为什么不使用 DI 容器/框架？

**Python 主流 DI 框架**:
- `dependency-injector`
- `injector`
- `FastAPI` 的内置 DI

**CherryQuant 选择手动 DI 的原因**:

1. **透明性**: 依赖关系一目了然，不依赖"魔法"
2. **简单性**: 避免引入额外框架，降低学习曲线
3. **控制力**: 完全掌控依赖创建和生命周期
4. **教学友好**: 学生能清晰看到依赖如何被创建和注入

**权衡**:
- ❌ 手动编写组装代码（适度的重复）
- ✅ 零学习成本，无框架锁定
- ✅ 易于调试和理解

---

### 第三部分：实战案例分析 (3 小时)

#### 3.1 案例 1：数据适配器的依赖注入

**需求**: `HistoryDataManager` 需要从数据源获取历史数据，但数据源可能是 Tushare、QuantBox 或其他。

**❌ 不好的设计**:

```python
class HistoryDataManager:
    def __init__(self, data_source_type: str, **kwargs):
        # 在内部根据类型创建依赖
        if data_source_type == "tushare":
            self.adapter = TushareAdapter(kwargs["token"])
        elif data_source_type == "quantbox":
            self.adapter = QuantBoxAdapter(kwargs["api_key"])
        else:
            raise ValueError("Unknown data source")

    async def get_data(self, symbol: str):
        return await self.adapter.fetch_kline(symbol, ...)
```

**问题**:
- 违反开闭原则（新增数据源需修改此类）
- 难以测试（无法注入 Mock）
- 配置逻辑混入业务逻辑

**✅ 好的设计**（依赖注入）:

```python
# 定义接口
class DataAdapter(Protocol):
    async def fetch_kline(self, symbol: str, ...) -> List[KlineData]:
        ...

# 实现类保持独立
class TushareAdapter:
    def __init__(self, token: str):
        self.api = ts.pro_api(token)

    async def fetch_kline(self, symbol: str, ...) -> List[KlineData]:
        ...

class QuantBoxAdapter:
    def __init__(self, api_key: str):
        self.client = QuantBoxClient(api_key)

    async def fetch_kline(self, symbol: str, ...) -> List[KlineData]:
        ...

# HistoryDataManager 只依赖接口
class HistoryDataManager:
    def __init__(
        self,
        adapter: DataAdapter,           # 注入接口
        storage: DatabaseManager        # 注入存储
    ):
        self.adapter = adapter
        self.storage = storage

    async def get_data(self, symbol: str):
        # 尝试从缓存读取
        cached = await self.storage.get_cached_data(symbol)
        if cached:
            return cached

        # 从数据源获取
        data = await self.adapter.fetch_kline(symbol, ...)
        await self.storage.save_data(symbol, data)
        return data

# 在 Composition Root 组装
async def create_app_context():
    # 根据配置选择适配器
    if config.data_source == "tushare":
        adapter = TushareAdapter(config.tushare_token)
    else:
        adapter = QuantBoxAdapter(config.quantbox_api_key)

    # 注入依赖
    history_manager = HistoryDataManager(
        adapter=adapter,
        storage=db_manager
    )

    return history_manager
```

**优势**:
- ✅ `HistoryDataManager` 对数据源类型无感知
- ✅ 新增数据源只需实现接口，无需修改现有代码
- ✅ 测试时可注入 Mock: `HistoryDataManager(adapter=MockAdapter(), storage=MockDB())`

#### 3.2 案例 2：AI 决策引擎的依赖注入

**场景**: AI 决策引擎需要调用 LLM、查询市场数据、记录决策日志。

**✅ CherryQuant 的实现**:

```python
class AIDecisionEngine:
    def __init__(
        self,
        llm_client: AsyncOpenAIClient,    # 注入 LLM 客户端
        market_data: MarketDataManager,   # 注入市场数据管理器
        logger: structlog.BoundLogger     # 注入日志器
    ):
        self.llm = llm_client
        self.market_data = market_data
        self.logger = logger

    async def make_decision(self, symbol: str) -> Decision:
        # 1. 获取市场数据（通过注入的 market_data）
        data = await self.market_data.get_latest_data(symbol)

        # 2. 构建提示词
        prompt = self._build_prompt(symbol, data)

        # 3. 调用 LLM（通过注入的 llm_client）
        response = await self.llm.chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )

        # 4. 解析决策
        decision = self._parse_response(response)

        # 5. 记录日志（通过注入的 logger）
        self.logger.info(
            "AI decision made",
            symbol=symbol,
            action=decision.action,
            confidence=decision.confidence
        )

        return decision
```

**如何组装**（在 `create_app_context` 中）:

```python
async def create_app_context():
    # 创建基础依赖
    ai_client = AsyncOpenAIClient(config.ai)
    db_manager = DatabaseManager(...)
    market_data_manager = MarketDataManager(db=db_manager, ...)
    logger = structlog.get_logger("ai_engine")

    # 注入依赖创建 AI 引擎
    decision_engine = AIDecisionEngine(
        llm_client=ai_client,
        market_data=market_data_manager,
        logger=logger
    )

    return decision_engine
```

**测试时的 Mock**:

```python
# tests/unit/test_ai_engine.py
import pytest
from unittest.mock import AsyncMock

async def test_ai_decision_engine():
    # 创建 Mock 对象
    mock_llm = AsyncMock(spec=AsyncOpenAIClient)
    mock_llm.chat_completion.return_value = {
        "choices": [
            {"message": {"content": '{"action": "BUY", "confidence": 0.8}'}}
        ]
    }

    mock_market_data = AsyncMock(spec=MarketDataManager)
    mock_market_data.get_latest_data.return_value = {
        "close": 3500,
        "volume": 12345,
        ...
    }

    mock_logger = structlog.get_logger("test")

    # 注入 Mock 依赖
    engine = AIDecisionEngine(
        llm_client=mock_llm,
        market_data=mock_market_data,
        logger=mock_logger
    )

    # 测试
    decision = await engine.make_decision("rb2501")

    assert decision.action == "BUY"
    assert decision.confidence == 0.8
    mock_llm.chat_completion.assert_called_once()
```

**优势**:
- ✅ 测试不依赖真实 OpenAI API（节省成本，提高速度）
- ✅ 测试不依赖真实数据库
- ✅ 可以精确控制测试场景

#### 3.3 案例 3：多层依赖注入

**场景**: 完整的交易系统涉及多层依赖。

**依赖链**:

```
TradingSystem
    ├── AIDecisionEngine
    │     ├── AsyncOpenAIClient
    │     ├── MarketDataManager
    │     │     ├── DatabaseManager
    │     │     │     ├── MongoDBManager
    │     │     │     └── RedisClient
    │     │     └── DataAdapter (Tushare/QuantBox)
    │     └── Logger
    │
    ├── RiskManager
    │     ├── RiskConfig
    │     └── DatabaseManager
    │
    └── TradingExecutor
          ├── VNPyGateway
          ├── DatabaseManager
          └── Logger
```

**组装代码**（Composition Root）:

```python
async def create_app_context() -> AppContext:
    # 1. 配置
    config = CherryQuantConfig.from_env()

    # 2. 基础设施层
    mongodb_manager = await MongoDBConnectionPool.get_manager(...)
    redis_client = aioredis.from_url(...)
    db_manager = DatabaseManager(
        mongodb_manager=mongodb_manager,
        redis_client=redis_client,
        cache_ttl=config.database.cache_ttl
    )

    # 3. 数据层
    data_adapter = TushareAdapter(config.tushare_token)
    market_data_manager = MarketDataManager(
        db=db_manager,
        adapter=data_adapter
    )

    # 4. AI 层
    ai_client = AsyncOpenAIClient(config.ai)
    ai_engine = AIDecisionEngine(
        llm_client=ai_client,
        market_data=market_data_manager,
        logger=structlog.get_logger("ai_engine")
    )

    # 5. 风险管理层
    risk_manager = RiskManager(
        config=config.risk,
        db=db_manager
    )

    # 6. 交易执行层
    vnpy_gateway = VNPyGateway(config.ctp)
    trading_executor = TradingExecutor(
        gateway=vnpy_gateway,
        db=db_manager,
        logger=structlog.get_logger("trading")
    )

    # 7. 顶层系统
    trading_system = TradingSystem(
        ai_engine=ai_engine,
        risk_manager=risk_manager,
        trading_executor=trading_executor
    )

    return AppContext(
        config=config,
        db=db_manager,
        trading_system=trading_system
    )
```

**注意事项**:
- 🎯 依赖从底向上创建（MongoDB/Redis → DatabaseManager → MarketDataManager → AIEngine）
- 🎯 共享的依赖（如 `db_manager`）被多个组件复用
- 🎯 所有配置从 `config` 读取，单一数据源

---

### 第四部分：重构练习 (2 小时)

#### 4.1 练习：重构硬编码依赖

**原始代码**（有问题）:

```python
class ReportGenerator:
    def __init__(self, symbol: str):
        self.symbol = symbol
        # ❌ 硬编码依赖
        self.db = MongoDBManager()
        self.data_source = TushareAdapter(token="xxx")

    async def generate_report(self):
        data = await self.data_source.fetch_data(self.symbol)
        analysis = self._analyze(data)
        await self.db.save_report(self.symbol, analysis)
        return analysis

    def _analyze(self, data):
        # 分析逻辑
        ...
```

**任务**: 重构为依赖注入模式

<details>
<summary>点击查看参考答案</summary>

```python
# 1. 定义接口
class DataSource(Protocol):
    async def fetch_data(self, symbol: str) -> MarketData:
        ...

class ReportStorage(Protocol):
    async def save_report(self, symbol: str, report: Report) -> None:
        ...

# 2. 重构类
class ReportGenerator:
    def __init__(
        self,
        data_source: DataSource,      # 注入接口
        storage: ReportStorage,        # 注入接口
        logger: structlog.BoundLogger  # 注入日志
    ):
        self.data_source = data_source
        self.storage = storage
        self.logger = logger

    async def generate_report(self, symbol: str) -> Report:
        self.logger.info("Generating report", symbol=symbol)

        data = await self.data_source.fetch_data(symbol)
        analysis = self._analyze(data)
        await self.storage.save_report(symbol, analysis)

        self.logger.info("Report generated", symbol=symbol)
        return analysis

    def _analyze(self, data: MarketData) -> Report:
        # 分析逻辑
        ...

# 3. 在 Composition Root 组装
async def create_report_generator(config: Config) -> ReportGenerator:
    data_source = TushareAdapter(config.tushare_token)
    storage = MongoDBManager(config.mongodb_uri)
    logger = structlog.get_logger("report")

    return ReportGenerator(
        data_source=data_source,
        storage=storage,
        logger=logger
    )

# 4. 使用
generator = await create_report_generator(config)
report = await generator.generate_report("rb2501")
```

</details>

---

## 最佳实践

### 1. 依赖注入的"黄金法则"

✅ **DO (推荐做法)**:

- 通过构造函数注入依赖
- 依赖接口（Protocol/ABC），非具体类
- 在 Composition Root 统一组装
- 让对象接收依赖，而非创建依赖
- 使用不可变对象（`@dataclass(frozen=True)`）

❌ **DON'T (避免做法)**:

- 在业务代码中使用 `new` 或直接实例化依赖
- 使用全局变量/单例模式（除非必要）
- 在多个地方重复依赖创建逻辑
- 构造函数中包含复杂逻辑（仅赋值，不执行）

### 2. 依赖生命周期管理

**单例（Singleton）**: 整个应用生命周期只创建一次

```python
# DatabaseManager 应该是单例
db_manager = DatabaseManager(...)  # 创建一次
# 多个组件共享同一个实例
component1 = Component1(db=db_manager)
component2 = Component2(db=db_manager)
```

**瞬时（Transient）**: 每次使用都创建新实例

```python
# 每次请求创建新的决策引擎
decision = AIDecisionEngine(...)  # 每次新建
```

**作用域（Scoped）**: 在某个作用域内复用

```python
async with AppContext() as app:
    # 在这个作用域内复用依赖
    result1 = await app.trading_system.run()
    result2 = await app.trading_system.run()
# 离开作用域，依赖被释放
```

### 3. 配置管理

**单一配置源**: 所有配置从 `.env` 加载到 `Config` 对象

```python
# config/settings/base.py
from pydantic_settings import BaseSettings

class CherryQuantConfig(BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    # 数据库配置
    mongodb_uri: str
    mongodb_database: str
    redis_host: str
    redis_port: int

    # API 配置
    tushare_token: str
    openai_api_key: str

    @classmethod
    def from_env(cls) -> "CherryQuantConfig":
        return cls()  # Pydantic 自动从 .env 加载
```

**在 Composition Root 使用**:

```python
async def create_app_context():
    config = CherryQuantConfig.from_env()  # 单一配置源

    # 所有依赖从 config 读取配置
    db = DatabaseManager(uri=config.mongodb_uri, ...)
    ai = AsyncOpenAIClient(api_key=config.openai_api_key, ...)
```

---

## 实践练习

### Lab 05: 依赖注入重构实验 (4 小时)

**目标**: 将一个硬编码依赖的模块重构为依赖注入模式

**任务**:

1. **阅读代码**: 理解 `src/cherryquant/bootstrap/app_context.py` 的实现
2. **绘制依赖图**: 画出 CherryQuant 的完整依赖关系图
3. **重构练习**: 重构一个自定义的交易策略模块，应用依赖注入
4. **编写测试**: 为重构后的模块编写单元测试（使用 Mock）

**提交内容**:
- 依赖关系图（可手绘或工具绘制）
- 重构前后的代码对比
- 单元测试代码
- 学习反思（500 字以上）

**评分标准** (20 分):
- 依赖图准确性 (5 分)
- 重构质量 (8 分)
- 测试覆盖率和质量 (5 分)
- 学习反思深度 (2 分)

---

## 自我评估

- [ ] 我理解依赖注入的原理和价值
- [ ] 我能识别硬编码依赖的代码坏味道
- [ ] 我理解 Composition Root 模式
- [ ] 我能设计和实现依赖注入的组件
- [ ] 我能使用 Protocol 定义接口
- [ ] 我能为使用依赖注入的代码编写测试

## 扩展阅读

- **《Clean Architecture》** by Robert C. Martin - Chapter 11: DI Containers
- **《Dependency Injection Principles, Practices, and Patterns》** by Steven van Deursen & Mark Seemann
- **Martin Fowler 的文章**: [Inversion of Control Containers and the Dependency Injection pattern](https://martinfowler.com/articles/injection.html)
- **Python Protocol**: [PEP 544 - Protocols: Structural subtyping](https://www.python.org/dev/peps/pep-0544/)

## 下一步

- **Module 6**: 单元测试与 TDD
- **Module 7**: Python 代码规范
- **Lab 06**: 测试驱动开发实践

---

**🎓 祝贺**: 完成本模块后，你已掌握高级软件架构设计技能，这是成为优秀软件工程师的重要里程碑！
