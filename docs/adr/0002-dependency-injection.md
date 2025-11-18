# ADR-0002: 采用依赖注入模式和组合根

## 状态
Accepted

## 背景

在 CherryQuant 项目的早期版本中，我们遇到了以下问题：

1. **配置分散**：环境变量在各个模块中直接读取
   ```python
   # ❌ 反模式：在适配器中直接读取环境变量
   class DatabaseManager:
       def __init__(self):
           self.uri = os.getenv("MONGODB_URI")  # 分散的配置读取
   ```

2. **测试困难**：很难为单元测试注入 mock 依赖
3. **循环依赖**：模块之间相互依赖，难以追踪
4. **sys.path 黑魔法**：大量使用 `sys.path.append()` 来解决导入问题

### 问题示例

```python
# 旧代码中的反模式
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # ❌

from config.settings import settings  # 全局单例
from data_adapter import DataAdapter  # 循环依赖

class Engine:
    def __init__(self):
        self.adapter = DataAdapter()  # ❌ 硬编码依赖
        self.db_uri = os.getenv("DB_URI")  # ❌ 直接读取环境变量
```

### 业务需求

- 支持多种运行模式（dev, test, live）
- 方便的单元测试和集成测试
- 清晰的依赖关系，避免循环依赖
- 配置的集中管理和验证

## 决策

我们将采用 **显式依赖注入（Explicit Dependency Injection）** 模式，并实现 **组合根（Composition Root）** 模式。

### 核心原则

1. **依赖通过构造函数注入**
   ```python
   # ✅ 正确的依赖注入
   class DatabaseManager:
       def __init__(
           self,
           mongodb_manager: MongoDBConnectionManager,
           redis_client: Redis,
           cache_ttl: int,
       ):
           self.mongodb = mongodb_manager
           self.redis = redis_client
           self.cache_ttl = cache_ttl
   ```

2. **组合根集中管理依赖**
   - 所有依赖的创建和组装在 `src/cherryquant/bootstrap/app_context.py`
   - 提供 `create_app_context()` 工厂函数
   - 返回 `AppContext` 数据类，包含所有核心依赖

3. **配置集中验证**
   - 使用 Pydantic 的 `BaseSettings` 进行配置管理
   - 环境变量只在配置模块中读取一次
   - 配置对象通过依赖注入传递

### 实现架构

```python
# bootstrap/app_context.py

@dataclass
class AppContext:
    """Runtime application context containing all wired dependencies."""
    config: CherryQuantConfig
    db: DatabaseManager
    ai_client: AsyncOpenAIClient

async def create_app_context(config: Optional[CherryQuantConfig] = None) -> AppContext:
    """Composition root: wire all dependencies here."""

    # 1. Load configuration (single source of truth)
    if config is None:
        config = CherryQuantConfig.from_env()

    # 2. Configure logging
    configure_logging(
        log_level=config.logging.level,
        json_logs=config.logging.json_logs,
    )

    # 3. Create MongoDB connection
    mongodb_manager = await MongoDBConnectionPool.get_manager(
        uri=config.database.mongodb_uri,
        database=config.database.mongodb_database,
    )

    # 4. Create Redis client
    redis_client = aioredis.from_url(
        f"redis://{config.database.redis_host}:{config.database.redis_port}",
        db=config.database.redis_db,
    )

    # 5. Build DatabaseManager with explicit dependencies
    db_manager = DatabaseManager(
        mongodb_manager=mongodb_manager,
        redis_client=redis_client,
        cache_ttl=config.database.cache_ttl,
    )

    # 6. Create AI client
    ai_client = AsyncOpenAIClient(config.ai)

    return AppContext(config=config, db=db_manager, ai_client=ai_client)
```

### 使用方式

```python
# run_cherryquant.py

async def main():
    # Create application context (composition root)
    ctx = await create_app_context()

    # Inject dependencies explicitly
    market_data_manager = MarketDataManager(
        config=ctx.config,
        db_manager=ctx.db
    )

    ai_engine = FuturesDecisionEngine(
        llm_client=ctx.ai_client,
        config=ctx.config
    )

    # Use the components...
    await ai_engine.make_decision("rb2501", data)
```

## 考虑的备选方案

### 方案 A：使用 DI 框架（如 dependency-injector, inject）
**描述**：使用第三方依赖注入框架自动管理依赖

**优点**：
- 自动依赖解析
- 支持装饰器语法
- 功能强大（作用域、生命周期管理）

**缺点**：
- 增加第三方依赖
- 学习曲线陡峭
- "魔法"太多，不够显式
- 调试困难

**为什么不选择**：
- Python 的动态特性使得显式 DI 已经很简单
- 不需要复杂的特性（如自动装配）
- 追求简单和明确

### 方案 B：全局单例模式
**描述**：使用全局变量或模块级单例

```python
# config.py
CONFIG = CherryQuantConfig.from_env()  # 全局单例

# database.py
DB = DatabaseManager()  # 全局单例
```

**优点**：
- 实现简单
- 全局访问方便

**缺点**：
- 测试困难（全局状态）
- 无法为不同测试提供不同配置
- 隐式依赖，难以追踪
- 不支持多实例

**为什么不选择**：
- 可测试性是核心需求
- 需要支持多配置（dev/test/live）
- 全局状态是反模式

### 方案 C：Service Locator 模式
**描述**：使用服务定位器查找依赖

```python
class ServiceLocator:
    _services = {}

    @classmethod
    def get(cls, name):
        return cls._services[name]

# 使用
db = ServiceLocator.get("database")
```

**优点**：
- 集中管理依赖
- 可以延迟加载

**缺点**：
- 隐藏依赖关系
- 运行时错误（如果服务未注册）
- 难以理解组件的真实依赖
- 被认为是反模式

**为什么不选择**：
- 隐式依赖违反了显式原则
- 降低代码可读性
- 不如构造函数注入直观

## 后果

### 正面影响

1. **极高的可测试性**
   ```python
   @pytest.fixture
   def mock_db():
       return Mock(spec=DatabaseManager)

   def test_engine(mock_db):
       engine = FuturesDecisionEngine(db=mock_db, ...)  # 轻松注入 mock
       # 测试逻辑...
   ```

2. **清晰的依赖关系**
   - 从构造函数就能看出组件需要什么依赖
   - 没有隐藏的全局状态
   - 容易理解数据流

3. **配置集中管理**
   - 所有环境变量在一处读取和验证
   - Pydantic 提供类型安全和验证
   - 配置错误在启动时就能发现

4. **消除循环依赖**
   - 依赖关系是单向的（从上层到下层）
   - 组合根在最顶层
   - 没有 `sys.path` 黑魔法

5. **易于重构**
   - 更换实现只需修改组合根
   - 不影响其他代码
   - 支持多种实现（dev/prod）

### 负面影响

1. **初始编写代码稍多**
   - 需要显式传递每个依赖
   - 构造函数参数较多
   - **缓解**：使用数据类和类型提示，增加可读性

2. **构造函数参数膨胀**
   - 复杂组件可能需要多个依赖
   - **缓解**：
     - 使用 `AppContext` 数据类封装常用依赖
     - 考虑是否违反单一职责原则（组件太大）

3. **学习曲线**
   - 团队需要理解 DI 概念
   - **缓解**：提供清晰的文档和示例

### 风险和缓解措施

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 开发者绕过 DI，直接读取环境变量 | 中 | 中 | Code Review，Linter 规则 |
| 组合根变得过于复杂 | 低 | 低 | 定期重构，保持简洁 |
| 参数传递链太长 | 低 | 低 | 使用 AppContext 封装 |

## 实施计划

1. ✅ **阶段 1：创建 AppContext**（已完成）
   - 创建 `bootstrap/app_context.py`
   - 实现 `create_app_context()` 函数
   - 定义 `AppContext` 数据类

2. ✅ **阶段 2：重构配置管理**（已完成）
   - 集中配置到 `config/settings/base.py`
   - 使用 Pydantic `BaseSettings`
   - 移除分散的 `os.getenv()` 调用

3. ✅ **阶段 3：重构核心组件**（已完成）
   - `DatabaseManager` 接受依赖注入
   - `AsyncOpenAIClient` 接受配置对象
   - 所有适配器不再直接读取环境变量

4. ✅ **阶段 4：更新入口点**（已完成）
   - `run_cherryquant.py`
   - `run_cherryquant_complete.py`
   - `run_cherryquant_multi_agent.py`

5. **阶段 5：文档和培训**（进行中）
   - 编写 ADR 文档
   - 创建代码示例
   - 团队培训

## 参考资料

- [Dependency Injection Principles](https://en.wikipedia.org/wiki/Dependency_injection)
- [Composition Root Pattern](https://blog.ploeh.dk/2011/07/28/CompositionRoot/)
- [Dependency Injection in Python](https://python-dependency-injector.ets-labs.org/)
- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Explicit is better than implicit (Zen of Python)](https://www.python.org/dev/peps/pep-0020/)

## 变更历史

- 2025-10-18: 初始决策文档（CherryQuant Team）
- 2025-10-20: 完成核心组件重构（CherryQuant Team）
- 2025-11-18: 状态更改为 Accepted，添加到 ADR 系统（CherryQuant Team）
