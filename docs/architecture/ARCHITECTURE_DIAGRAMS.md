# CherryQuant 系统架构可视化

本文档包含 CherryQuant 系统的完整架构图，帮助理解系统设计和数据流向。

---

## 目录

1. [C4 模型架构图](#c4-模型架构图)
   - [Level 1: 系统上下文图](#level-1-系统上下文图)
   - [Level 2: 容器图](#level-2-容器图)
   - [Level 3: 组件图](#level-3-组件图)
   - [Level 4: 代码图](#level-4-代码图)
2. [序列图](#序列图)
   - [数据采集流程](#数据采集流程)
   - [AI 决策流程](#ai-决策流程)
   - [交易执行流程](#交易执行流程)
3. [数据流图](#数据流图)
4. [数据库架构图](#数据库架构图)
5. [部署架构图](#部署架构图)

---

## C4 模型架构图

C4 模型提供了 4 个层次的抽象，帮助理解系统架构：
- **Level 1 (Context)**: 系统与外部的关系
- **Level 2 (Container)**: 系统内的高层组件
- **Level 3 (Component)**: 每个容器的内部结构
- **Level 4 (Code)**: 关键类的设计

### Level 1: 系统上下文图

展示 CherryQuant 与外部系统的交互。

```mermaid
C4Context
    title 系统上下文图 - CherryQuant 量化交易平台

    Person(trader, "交易员/学生", "使用系统进行量化交易和学习")

    System(cherryquant, "CherryQuant", "量化交易平台<br/>数据采集、AI决策、风险管理")

    System_Ext(tushare, "Tushare Pro", "金融数据API<br/>股票、期货行情数据")
    System_Ext(openai, "OpenAI API", "大语言模型API<br/>GPT-4决策引擎")
    System_Ext(ctp, "CTP接口", "期货交易接口<br/>上期所、大商所等")
    System_Ext(mongodb, "MongoDB", "时序数据库<br/>存储市场数据")
    System_Ext(redis, "Redis", "缓存层<br/>L2缓存")

    Rel(trader, cherryquant, "使用", "CLI/Web界面")
    Rel(cherryquant, tushare, "采集数据", "HTTP/REST API")
    Rel(cherryquant, openai, "请求决策", "HTTP/REST API")
    Rel(cherryquant, ctp, "下单/查询", "CTP协议")
    Rel(cherryquant, mongodb, "读写数据", "MongoDB协议")
    Rel(cherryquant, redis, "缓存数据", "Redis协议")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

**说明**:
- **核心系统**: CherryQuant 平台
- **外部数据源**: Tushare Pro (行情数据)
- **AI 服务**: OpenAI API (决策支持)
- **交易接口**: CTP (实盘交易)
- **存储**: MongoDB (数据持久化) + Redis (缓存)

---

### Level 2: 容器图

展示 CherryQuant 内部的主要容器（应用程序、数据库等）。

```mermaid
C4Container
    title 容器图 - CherryQuant 内部架构

    Person(user, "用户")

    Container_Boundary(cherryquant, "CherryQuant 平台") {
        Container(cli, "CLI 应用", "Python/uv", "命令行界面<br/>用户交互入口")
        Container(data_pipeline, "数据管道", "Python", "数据采集、清洗<br/>存储、查询")
        Container(ai_engine, "AI 决策引擎", "Python", "LLM集成<br/>Prompt工程<br/>决策生成")
        Container(trading_engine, "交易引擎", "Python/VNPy", "订单管理<br/>执行监控<br/>成交确认")
        Container(risk_mgr, "风险管理", "Python", "仓位检查<br/>止损止盈<br/>风险监控")
        Container(backtest, "回测引擎", "Python", "历史回放<br/>性能分析<br/>策略优化")
    }

    ContainerDb(mongodb, "MongoDB", "MongoDB", "时序数据<br/>市场数据<br/>交易记录")
    ContainerDb(redis, "Redis", "Redis", "L2缓存<br/>会话数据<br/>限流控制")

    System_Ext(tushare, "Tushare API")
    System_Ext(openai, "OpenAI API")
    System_Ext(ctp, "CTP")

    Rel(user, cli, "使用")
    Rel(cli, data_pipeline, "查询数据")
    Rel(cli, ai_engine, "请求决策")
    Rel(cli, trading_engine, "下单交易")
    Rel(cli, backtest, "运行回测")

    Rel(data_pipeline, tushare, "采集", "HTTP")
    Rel(data_pipeline, mongodb, "存储", "MongoDB")
    Rel(data_pipeline, redis, "缓存", "Redis")

    Rel(ai_engine, openai, "调用LLM", "HTTP")
    Rel(ai_engine, data_pipeline, "获取行情")

    Rel(trading_engine, ctp, "交易", "CTP")
    Rel(trading_engine, risk_mgr, "风控检查")

    Rel(risk_mgr, data_pipeline, "查询持仓")
    Rel(backtest, data_pipeline, "历史数据")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

**容器说明**:

| 容器 | 职责 | 技术栈 |
|------|------|--------|
| CLI 应用 | 用户界面，命令解析 | Python, Click |
| 数据管道 | 数据全生命周期管理 | Python, Motor (MongoDB), Redis |
| AI 决策引擎 | LLM集成，决策生成 | Python, OpenAI SDK |
| 交易引擎 | 订单管理，执行监控 | Python, VNPy |
| 风险管理 | 风险检查，止损控制 | Python, Pydantic |
| 回测引擎 | 策略验证，性能分析 | Python, Pandas |

---

### Level 3: 组件图 - 数据管道

展示数据管道容器内的组件。

```mermaid
C4Component
    title 组件图 - 数据管道内部结构

    Container_Boundary(data_pipeline, "数据管道") {
        Component(collector_layer, "Collector Layer", "BaseCollector", "数据采集层<br/>支持多数据源")
        Component(cleaner_layer, "Cleaner Layer", "Validator + Normalizer", "数据清洗层<br/>验证+标准化")
        Component(storage_layer, "Storage Layer", "Repository", "存储层<br/>时序数据管理")
        Component(service_layer, "Service Layer", "Services", "服务层<br/>业务逻辑")
        Component(query_layer, "Query Layer", "QueryBuilder", "查询层<br/>复杂查询构建")

        Component(tushare_collector, "TushareCollector", "Collector", "Tushare数据采集<br/>限流+重试")
        Component(validator, "DataValidator", "Validator", "5维度验证<br/>缺失值检测")
        Component(normalizer, "DataNormalizer", "Normalizer", "5种策略<br/>数据标准化")
        Component(timeseries_repo, "TimeSeriesRepo", "Repository", "时序数据仓储<br/>98.6%测试覆盖")
        Component(cache, "CacheStrategy", "Cache", "3级缓存<br/>L1:LRU, L2:Redis")
        Component(calendar_svc, "CalendarService", "Service", "交易日历<br/>节假日判断")
    }

    ContainerDb(mongodb, "MongoDB")
    ContainerDb(redis, "Redis")
    System_Ext(tushare, "Tushare API")

    Rel(collector_layer, tushare_collector, "使用")
    Rel(tushare_collector, tushare, "调用API")

    Rel(collector_layer, cleaner_layer, "原始数据")
    Rel(cleaner_layer, validator, "验证")
    Rel(cleaner_layer, normalizer, "标准化")

    Rel(cleaner_layer, storage_layer, "清洗后数据")
    Rel(storage_layer, timeseries_repo, "存储")
    Rel(storage_layer, cache, "缓存")

    Rel(timeseries_repo, mongodb, "持久化")
    Rel(cache, redis, "L2缓存")

    Rel(service_layer, storage_layer, "使用")
    Rel(service_layer, calendar_svc, "调用")

    Rel(query_layer, storage_layer, "查询")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

**设计模式应用**:

- **Template Method**: `BaseCollector` 定义采集骨架，子类实现具体逻辑
- **Strategy**: `DataNormalizer` 支持多种标准化策略
- **Repository**: `TimeSeriesRepository` 封装数据访问
- **Facade**: `DataPipeline` 提供统一接口
- **Cache Aside**: `CacheStrategy` 实现三级缓存

---

### Level 3: 组件图 - AI 决策引擎

```mermaid
C4Component
    title 组件图 - AI 决策引擎内部结构

    Container_Boundary(ai_engine, "AI 决策引擎") {
        Component(decision_engine, "FuturesDecisionEngine", "Engine", "期货决策引擎<br/>多时间周期分析")
        Component(llm_client, "AsyncOpenAIClient", "Client", "异步LLM客户端<br/>重试+超时")
        Component(prompt_mgr, "PromptManager", "Manager", "Prompt模板管理<br/>版本控制")
        Component(context_builder, "ContextBuilder", "Builder", "上下文构建<br/>多维度数据整合")
        Component(response_parser, "ResponseParser", "Parser", "响应解析<br/>JSON提取+验证")
        Component(fallback_strategy, "FallbackStrategy", "Strategy", "降级策略<br/>模拟决策")
    }

    Container(data_pipeline, "数据管道")
    System_Ext(openai, "OpenAI API")

    Rel(decision_engine, llm_client, "调用LLM")
    Rel(decision_engine, prompt_mgr, "获取Prompt")
    Rel(decision_engine, context_builder, "构建上下文")
    Rel(decision_engine, response_parser, "解析响应")
    Rel(decision_engine, fallback_strategy, "降级", "API失败时")

    Rel(llm_client, openai, "HTTP请求")
    Rel(context_builder, data_pipeline, "获取数据")
    Rel(prompt_mgr, data_pipeline, "历史数据示例")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

**AI 引擎特点**:
- **异步调用**: 所有 API 调用使用 async/await
- **重试机制**: 指数退避 + 熔断器
- **Prompt 工程**: 模板化管理，支持 Few-shot Learning
- **降级策略**: API 不可用时使用技术指标模拟

---

### Level 4: 代码图 - 核心类设计

展示关键类的属性和方法。

```mermaid
classDiagram
    class DataPipeline {
        -collector: BaseCollector
        -validator: DataValidator
        -normalizer: DataNormalizer
        -repository: TimeSeriesRepository
        -cache: CacheStrategy
        +collect_and_store_data()
        +query_data()
        +get_data_quality_report()
    }

    class BaseCollector {
        <<abstract>>
        -rate_limiter: TokenBucket
        #_fetch_data()* abstract
        +collect()
        -_validate_response()
        -_handle_error()
    }

    class TushareCollector {
        -api_token: str
        -pro_api: TushareAPI
        #_fetch_data() override
        +fetch_daily_data()
        +fetch_minute_data()
    }

    class DataValidator {
        -validation_rules: List
        +validate()
        +check_missing_values()
        +check_data_types()
        +check_ranges()
        +detect_outliers()
    }

    class TimeSeriesRepository {
        -db: AsyncIOMotorDatabase
        -collection_name: str
        +insert_many()
        +query()
        +aggregate()
        +create_indexes()
    }

    class CacheStrategy {
        -l1_cache: LRUCache
        -l2_cache: RedisClient
        +get()
        +set()
        +invalidate()
        -_get_from_l1()
        -_get_from_l2()
    }

    DataPipeline --> BaseCollector
    DataPipeline --> DataValidator
    DataPipeline --> TimeSeriesRepository
    DataPipeline --> CacheStrategy
    BaseCollector <|-- TushareCollector
```

```mermaid
classDiagram
    class FuturesDecisionEngine {
        -llm_client: AsyncOpenAIClient
        -prompt_manager: PromptManager
        -config: AIConfig
        +make_decision()
        -_build_context()
        -_call_llm()
        -_parse_response()
        -_fallback_decision()
    }

    class AsyncOpenAIClient {
        -api_key: str
        -base_url: str
        -session: ClientSession
        +chat_completion()
        +aclose()
        -_retry_on_error()
    }

    class PromptManager {
        -templates: Dict
        +get_system_prompt()
        +get_user_prompt()
        +render_template()
    }

    class ContextBuilder {
        +build_market_context()
        +build_technical_context()
        +build_position_context()
        -_calculate_indicators()
    }

    FuturesDecisionEngine --> AsyncOpenAIClient
    FuturesDecisionEngine --> PromptManager
    FuturesDecisionEngine --> ContextBuilder
```

---

## 序列图

序列图展示系统在运行时的交互流程。

### 数据采集流程

```mermaid
sequenceDiagram
    actor User
    participant CLI
    participant DataPipeline
    participant TushareCollector
    participant RateLimiter
    participant TushareAPI
    participant DataValidator
    participant DataNormalizer
    participant CacheStrategy
    participant TimeSeriesRepo
    participant MongoDB

    User->>CLI: 执行采集命令
    CLI->>DataPipeline: collect_and_store_data()

    rect rgb(240, 248, 255)
        Note over DataPipeline,TushareAPI: Collector Layer
        DataPipeline->>TushareCollector: fetch_daily_data()
        TushareCollector->>RateLimiter: acquire_token()
        alt Token Available
            RateLimiter-->>TushareCollector: OK
            TushareCollector->>TushareAPI: pro.daily()
            TushareAPI-->>TushareCollector: DataFrame
        else Rate Limit Exceeded
            RateLimiter-->>TushareCollector: Wait
            Note over TushareCollector: 等待Token补充
            TushareCollector->>TushareAPI: pro.daily()
            TushareAPI-->>TushareCollector: DataFrame
        end
    end

    rect rgb(255, 250, 240)
        Note over DataPipeline,DataNormalizer: Cleaner Layer
        DataPipeline->>DataValidator: validate(data)
        DataValidator->>DataValidator: check_missing_values()
        DataValidator->>DataValidator: detect_outliers()
        DataValidator-->>DataPipeline: ValidationResult

        alt Validation Passed
            DataPipeline->>DataNormalizer: normalize(data)
            DataNormalizer->>DataNormalizer: apply_strategy()
            DataNormalizer-->>DataPipeline: Normalized Data
        else Validation Failed
            DataValidator-->>DataPipeline: Error Report
            DataPipeline-->>CLI: Error
            CLI-->>User: 显示错误
        end
    end

    rect rgb(240, 255, 240)
        Note over DataPipeline,MongoDB: Storage Layer
        DataPipeline->>CacheStrategy: set(data)
        CacheStrategy->>CacheStrategy: L1 Cache (LRU)
        CacheStrategy->>Redis: L2 Cache

        DataPipeline->>TimeSeriesRepo: insert_many(data)
        TimeSeriesRepo->>MongoDB: insertMany()
        MongoDB-->>TimeSeriesRepo: Ack
        TimeSeriesRepo-->>DataPipeline: Success
    end

    DataPipeline-->>CLI: Result
    CLI-->>User: 显示成功 + 统计信息
```

**关键步骤**:
1. **限流控制**: 使用 Token Bucket 算法
2. **数据验证**: 5维度验证（缺失值、类型、范围、异常值、一致性）
3. **缓存策略**: L1 (内存LRU) + L2 (Redis)
4. **错误处理**: 每一层都有错误恢复机制

---

### AI 决策流程

```mermaid
sequenceDiagram
    actor User
    participant CLI
    participant FuturesEngine
    participant ContextBuilder
    participant DataPipeline
    participant PromptManager
    participant OpenAIClient
    participant OpenAI API
    participant ResponseParser
    participant FallbackStrategy

    User->>CLI: 请求交易决策
    CLI->>FuturesEngine: make_decision(symbol)

    rect rgb(240, 248, 255)
        Note over FuturesEngine,DataPipeline: 构建上下文
        FuturesEngine->>ContextBuilder: build_context(symbol)
        ContextBuilder->>DataPipeline: query_multi_timeframe()
        DataPipeline-->>ContextBuilder: 多周期数据
        ContextBuilder->>ContextBuilder: calculate_indicators()
        ContextBuilder-->>FuturesEngine: Context Dict
    end

    rect rgb(255, 250, 240)
        Note over FuturesEngine,OpenAI API: 调用 LLM
        FuturesEngine->>PromptManager: get_prompts()
        PromptManager-->>FuturesEngine: System + User Prompt

        FuturesEngine->>OpenAIClient: chat_completion(messages)
        OpenAIClient->>OpenAI API: POST /chat/completions

        alt API Success
            OpenAI API-->>OpenAIClient: Response
            OpenAIClient-->>FuturesEngine: LLM Response
        else API Error
            OpenAI API-->>OpenAIClient: Error (429/500)
            OpenAIClient->>OpenAIClient: retry with backoff
            alt Retry Success
                OpenAI API-->>OpenAIClient: Response
            else Max Retries Exceeded
                OpenAIClient-->>FuturesEngine: Error
                FuturesEngine->>FallbackStrategy: get_fallback_decision()
                FallbackStrategy-->>FuturesEngine: Simulated Decision
            end
        end
    end

    rect rgb(240, 255, 240)
        Note over FuturesEngine,ResponseParser: 解析响应
        FuturesEngine->>ResponseParser: parse(response)
        ResponseParser->>ResponseParser: extract_json()
        ResponseParser->>ResponseParser: validate_schema()
        ResponseParser-->>FuturesEngine: Structured Decision
    end

    FuturesEngine-->>CLI: Decision Object
    CLI-->>User: 显示决策 (做多/做空/观望)
```

**决策生成步骤**:
1. **多维度上下文**: 5分钟、1小时、日线数据 + 技术指标
2. **Prompt 工程**: System Prompt (角色) + User Prompt (任务)
3. **容错机制**: 重试 + 熔断器 + 降级策略
4. **响应验证**: JSON 提取 + Schema 验证

---

### 交易执行流程

```mermaid
sequenceDiagram
    actor Trader
    participant CLI
    participant TradingEngine
    participant RiskManager
    participant PositionChecker
    participant OrderManager
    participant VNPyGateway
    participant CTP
    participant EventBus
    participant PnLTracker

    Trader->>CLI: 提交订单
    CLI->>TradingEngine: submit_order(order)

    rect rgb(255, 240, 240)
        Note over TradingEngine,PositionChecker: 风控检查
        TradingEngine->>RiskManager: check_risk(order)
        RiskManager->>PositionChecker: check_total_position()
        PositionChecker-->>RiskManager: OK
        RiskManager->>PositionChecker: check_single_position()
        PositionChecker-->>RiskManager: OK
        RiskManager->>PositionChecker: check_leverage()

        alt Risk Check Passed
            PositionChecker-->>RiskManager: OK
            RiskManager-->>TradingEngine: Approved
        else Risk Check Failed
            PositionChecker-->>RiskManager: Rejected
            RiskManager-->>TradingEngine: Error
            TradingEngine-->>CLI: 拒绝订单
            CLI-->>Trader: 显示拒绝原因
        end
    end

    rect rgb(240, 248, 255)
        Note over TradingEngine,CTP: 订单执行
        TradingEngine->>OrderManager: create_order()
        OrderManager->>VNPyGateway: send_order()
        VNPyGateway->>CTP: 报单请求

        alt Order Accepted
            CTP-->>VNPyGateway: 报单回报
            VNPyGateway->>EventBus: on_order()
            EventBus-->>OrderManager: Order Event

            CTP-->>VNPyGateway: 成交回报
            VNPyGateway->>EventBus: on_trade()
            EventBus-->>OrderManager: Trade Event
            OrderManager-->>TradingEngine: Trade Confirmed
        else Order Rejected
            CTP-->>VNPyGateway: 错误回报
            VNPyGateway->>EventBus: on_order_error()
            EventBus-->>OrderManager: Error Event
            OrderManager-->>TradingEngine: Order Failed
        end
    end

    rect rgb(240, 255, 240)
        Note over TradingEngine,PnLTracker: 持仓和盈亏更新
        TradingEngine->>PnLTracker: update_position()
        PnLTracker->>PnLTracker: calculate_pnl()
        PnLTracker->>MongoDB: store_trade_record()
        PnLTracker-->>TradingEngine: Position Updated
    end

    TradingEngine-->>CLI: Execution Result
    CLI-->>Trader: 显示成交详情
```

**风控流程**:
1. **总持仓检查**: 不超过 80% 资金
2. **单品种检查**: 不超过 30% 资金
3. **杠杆检查**: 不超过 3 倍
4. **止损止盈**: 实时监控

---

## 数据流图

展示数据在系统中的流动。

```mermaid
flowchart TD
    subgraph External["外部数据源"]
        A1[Tushare Pro API]
        A2[Wind API]
        A3[CTP 行情]
    end

    subgraph Collector["采集层 (Collector Layer)"]
        B1[TushareCollector<br/>限流: Token Bucket<br/>重试: 指数退避]
        B2[WindCollector<br/>未实现]
        B3[VNPyCollector<br/>实时行情]
    end

    subgraph Cleaner["清洗层 (Cleaner Layer)"]
        C1[DataValidator<br/>5维度验证]
        C2[DataNormalizer<br/>5种策略]
        C3[QualityController<br/>评分: A-F]
    end

    subgraph Storage["存储层 (Storage Layer)"]
        D1[CacheStrategy<br/>L1: LRU<br/>L2: Redis]
        D2[TimeSeriesRepo<br/>MongoDB<br/>98.6% 覆盖率]
    end

    subgraph Service["服务层 (Service Layer)"]
        E1[CalendarService<br/>交易日历]
        E2[ContractService<br/>合约管理]
        E3[DataService<br/>数据查询]
    end

    subgraph Query["查询层 (Query Layer)"]
        F1[QueryBuilder<br/>Fluent接口]
        F2[BatchQueryExecutor<br/>并发查询]
    end

    subgraph Consumers["数据消费者"]
        G1[AI 决策引擎]
        G2[回测引擎]
        G3[交易引擎]
        G4[监控告警]
    end

    %% 数据流向
    A1 --> B1
    A2 -.-> B2
    A3 --> B3

    B1 --> C1
    B2 -.-> C1
    B3 --> C1

    C1 --> C2
    C2 --> C3

    C3 --> D1
    C3 --> D2

    D1 --> E3
    D2 --> E3
    E1 --> E3
    E2 --> E3

    E3 --> F1
    E3 --> F2

    F1 --> G1
    F1 --> G2
    F2 --> G3
    F2 --> G4

    %% 样式
    classDef external fill:#e1f5ff,stroke:#0066cc,stroke-width:2px
    classDef collector fill:#fff4e6,stroke:#ff9800,stroke-width:2px
    classDef cleaner fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px
    classDef storage fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    classDef service fill:#fff3e0,stroke:#ff6f00,stroke-width:2px
    classDef query fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef consumer fill:#e0f2f1,stroke:#009688,stroke-width:2px

    class A1,A2,A3 external
    class B1,B2,B3 collector
    class C1,C2,C3 cleaner
    class D1,D2 storage
    class E1,E2,E3 service
    class F1,F2 query
    class G1,G2,G3,G4 consumer
```

**数据流说明**:

1. **外部数据源** → **采集层**
   - Tushare Pro: 历史数据（日线、分钟线）
   - CTP: 实时行情（Tick 级别）

2. **采集层** → **清洗层**
   - 限流控制：每秒最多 N 次请求
   - 重试机制：失败后指数退避

3. **清洗层** → **存储层**
   - 验证：缺失值、类型、范围、异常值、一致性
   - 标准化：归一化、Z-Score、MinMax、Robust、Log
   - 质量评分：A (优秀) ~ F (不可用)

4. **存储层** → **服务层**
   - L1 缓存 (内存): LRU, 最多 1000 条
   - L2 缓存 (Redis): TTL = 1 小时
   - L3 持久化 (MongoDB): 时序集合 + 压缩

5. **服务层** → **查询层**
   - CalendarService: 判断交易日
   - ContractService: 主力合约切换
   - DataService: 统一数据接口

6. **查询层** → **消费者**
   - AI 引擎: 多时间周期数据
   - 回测引擎: 历史数据回放
   - 交易引擎: 实时行情订阅
   - 监控告警: 数据质量监控

---

## 数据库架构图

展示 MongoDB 数据库的集合设计和关系。

```mermaid
erDiagram
    MARKET_DATA_1D {
        ObjectId _id PK
        string symbol "品种代码"
        datetime timestamp "时间戳"
        float open "开盘价"
        float high "最高价"
        float low "最低价"
        float close "收盘价"
        int volume "成交量"
        float amount "成交额"
        int open_interest "持仓量"
        string source "数据来源"
        datetime created_at "创建时间"
    }

    MARKET_DATA_1H {
        ObjectId _id PK
        string symbol
        datetime timestamp
        float open
        float high
        float low
        float close
        int volume
    }

    MARKET_DATA_5M {
        ObjectId _id PK
        string symbol
        datetime timestamp
        float open
        float high
        float low
        float close
        int volume
    }

    CONTRACTS {
        ObjectId _id PK
        string symbol UK "合约代码"
        string name "合约名称"
        string exchange "交易所"
        string product_type "品种类型"
        date list_date "上市日期"
        date delist_date "退市日期"
        float multiplier "合约乘数"
        float margin_rate "保证金比例"
        boolean is_main "是否主力合约"
    }

    TRADING_CALENDAR {
        ObjectId _id PK
        string exchange "交易所"
        date date UK "日期"
        boolean is_trading_day "是否交易日"
        string holiday_name "节假日名称"
    }

    TRADES {
        ObjectId _id PK
        string order_id "订单ID"
        string symbol "品种代码"
        string side "买卖方向"
        int quantity "数量"
        float price "价格"
        float commission "手续费"
        datetime timestamp "成交时间"
        string strategy_id "策略ID"
    }

    POSITIONS {
        ObjectId _id PK
        string symbol "品种代码"
        int quantity "持仓数量"
        float avg_price "平均成本"
        float current_price "当前价格"
        float pnl "浮动盈亏"
        datetime updated_at "更新时间"
    }

    ORDERS {
        ObjectId _id PK
        string order_id UK "订单ID"
        string symbol "品种代码"
        string side "买卖方向"
        string order_type "订单类型"
        int quantity "数量"
        float price "价格"
        string status "状态"
        datetime created_at "创建时间"
        datetime filled_at "成交时间"
    }

    AI_DECISIONS {
        ObjectId _id PK
        string symbol "品种代码"
        string decision "决策"
        float confidence "置信度"
        string reasoning "理由"
        string prompt_version "Prompt版本"
        string model "模型"
        datetime created_at "决策时间"
    }

    MARKET_DATA_1D ||--o{ CONTRACTS : "symbol"
    CONTRACTS ||--o{ TRADES : "symbol"
    CONTRACTS ||--o{ POSITIONS : "symbol"
    CONTRACTS ||--o{ ORDERS : "symbol"
    CONTRACTS ||--o{ AI_DECISIONS : "symbol"
    TRADING_CALENDAR ||--|| CONTRACTS : "exchange"
```

**集合说明**:

| 集合 | 类型 | 索引 | 大小估算 | 说明 |
|------|------|------|----------|------|
| market_data_1d | 时序集合 | (symbol, timestamp) | ~1GB/年 | 日线数据 |
| market_data_1h | 时序集合 | (symbol, timestamp) | ~5GB/年 | 小时线数据 |
| market_data_5m | 时序集合 | (symbol, timestamp) | ~50GB/年 | 5分钟线数据 |
| contracts | 普通集合 | (symbol unique) | ~1MB | 合约信息 |
| trading_calendar | 普通集合 | (exchange, date) | ~100KB | 交易日历 |
| trades | 普通集合 | (order_id), (symbol, timestamp) | ~10MB/年 | 交易记录 |
| positions | 普通集合 | (symbol unique) | ~10KB | 持仓信息 |
| orders | 普通集合 | (order_id unique), (status) | ~5MB/年 | 订单记录 |
| ai_decisions | 普通集合 | (symbol, created_at) | ~100MB/年 | AI决策记录 |

**性能优化**:
- **时序集合**: 使用 MongoDB 时序集合，自动压缩（~70% 空间节省）
- **复合索引**: (symbol, timestamp) 支持常见查询
- **TTL 索引**: 自动清理过期数据
- **分片策略**: 按 symbol + timestamp 分片（可选）

---

## 部署架构图

展示生产环境的部署方案。

```mermaid
flowchart TB
    subgraph User["用户层"]
        U1[交易员]
        U2[研究员]
        U3[系统管理员]
    end

    subgraph LoadBalancer["负载均衡"]
        LB[Nginx<br/>反向代理+SSL]
    end

    subgraph AppLayer["应用层 (Docker)"]
        direction LR
        A1[CherryQuant App 1<br/>主节点]
        A2[CherryQuant App 2<br/>备节点]
    end

    subgraph DataLayer["数据层"]
        direction LR
        subgraph MongoDB["MongoDB 集群"]
            M1[Primary]
            M2[Secondary 1]
            M3[Secondary 2]
        end

        subgraph Redis["Redis 集群"]
            R1[Master]
            R2[Slave]
        end
    end

    subgraph ExternalServices["外部服务"]
        E1[Tushare Pro]
        E2[OpenAI API]
        E3[CTP Gateway]
    end

    subgraph Monitoring["监控层"]
        MON1[Prometheus<br/>指标收集]
        MON2[Grafana<br/>可视化]
        MON3[AlertManager<br/>告警]
    end

    subgraph Storage["持久化存储"]
        S1[NFS<br/>日志归档]
        S2[S3<br/>数据备份]
    end

    %% 连接关系
    U1 --> LB
    U2 --> LB
    U3 --> MON2

    LB --> A1
    LB -.备用.-> A2

    A1 --> M1
    A2 -.-> M1
    M1 <--> M2
    M1 <--> M3

    A1 --> R1
    A2 --> R1
    R1 --> R2

    A1 --> E1
    A1 --> E2
    A1 --> E3

    A1 --> MON1
    A2 --> MON1
    M1 --> MON1
    R1 --> MON1

    MON1 --> MON2
    MON1 --> MON3

    A1 -.日志.-> S1
    M1 -.备份.-> S2

    %% 样式
    classDef user fill:#e3f2fd,stroke:#1976d2
    classDef app fill:#fff3e0,stroke:#f57c00
    classDef data fill:#e8f5e9,stroke:#388e3c
    classDef external fill:#fce4ec,stroke:#c2185b
    classDef monitor fill:#f3e5f5,stroke:#7b1fa2
    classDef storage fill:#fff8e1,stroke:#fbc02d

    class U1,U2,U3 user
    class A1,A2 app
    class M1,M2,M3,R1,R2 data
    class E1,E2,E3 external
    class MON1,MON2,MON3 monitor
    class S1,S2 storage
```

**部署配置**:

| 组件 | 配置 | 数量 | 备注 |
|------|------|------|------|
| Nginx | 2C4G | 1 | 反向代理+SSL |
| CherryQuant App | 4C8G | 2 | 主备模式 |
| MongoDB | 8C16G + 500GB SSD | 3 | 副本集 |
| Redis | 2C4G | 2 | 主从 |
| Prometheus | 2C4G | 1 | 监控数据保留 30 天 |
| Grafana | 2C4G | 1 | 可视化 |

**高可用方案**:
- **应用层**: 2个节点，Nginx 负载均衡
- **数据库**: MongoDB 副本集（1主2从），自动故障转移
- **缓存**: Redis 主从复制
- **监控**: Prometheus + Grafana + AlertManager

---

## 总结

本文档通过多层次、多视角的可视化图表，全面展示了 CherryQuant 系统的架构设计：

- **C4 模型**: 从宏观到微观，逐层展示系统结构
- **序列图**: 展示运行时的交互流程
- **数据流图**: 展示数据的生命周期
- **数据库架构**: 展示数据模型设计
- **部署架构**: 展示生产环境方案

这些图表不仅是文档，更是：
- **设计蓝图**: 指导开发实现
- **沟通工具**: 团队协作的共同语言
- **教学材料**: 帮助学生理解系统设计

**建议使用场景**:
- 📚 **学习**: 理解系统架构和设计思想
- 🛠️ **开发**: 查找组件位置和交互方式
- 🔍 **调试**: 追踪数据流和定位问题
- 📊 **展示**: 项目演示和技术分享

---

**相关文档**:
- [系统架构文档](./01_System_Architecture.md)
- [MongoDB Schema 设计](./MONGODB_SCHEMA_V2.md)
- [ADR 决策记录](../adr/)
