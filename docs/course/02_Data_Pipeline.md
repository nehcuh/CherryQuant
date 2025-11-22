# CherryQuant 课程讲义 - 第2章：数据管道

## 📚 本章概述

**学习目标:**
- 理解量化交易数据管道的重要性
- 掌握分层架构设计思想
- 学习 10+ 种设计模式的实战应用
- 了解数据质量管理的完整流程
- 实现一个生产级的数据管道

**预计学习时间:** 6 周
**前置知识:** Python 基础、async/await、面向对象编程

---

## 2.1 数据管道的重要性

在量化交易系统中，数据是"燃料"。**高质量、低延迟的数据是 AI 做出正确决策的前提。**

### 数据管道要解决的核心问题

1. **数据采集**: 如何从多个数据源 (Tushare、CTP、Wind 等) 统一采集数据？
2. **数据清洗**: 如何保证数据的完整性、准确性、一致性？
3. **数据存储**: 如何高效存储和检索海量时序数据？
4. **数据查询**: 如何支持复杂的查询需求？
5. **数据质量**: 如何监控和评估数据质量？

### 传统方案的问题

很多初学者会这样写代码:

```python
# ❌ 不好的做法
import tushare as ts

pro = ts.pro_api("your_token")

# 直接调用 API
df = pro.daily(ts_code='rb2501.SHF', start_date='20240101', end_date='20240131')

# 直接使用数据，没有验证、清洗、存储
for _, row in df.iterrows():
    price = row['close']
    # ... 使用 price
```

**问题:**
- ❌ 没有数据验证，可能有缺失值或异常值
- ❌ 没有数据清洗，格式不统一
- ❌ 没有数据存储，每次都要重新请求 API
- ❌ 没有缓存机制，性能低下
- ❌ 代码耦合严重，难以扩展到其他数据源

### CherryQuant 数据管道的解决方案

CherryQuant 实现了一个 **5 层架构** 的完整数据管道:

```
数据流向:
数据源 → Collector → Cleaner → Storage → Service → Query → AI Engine
```

每一层都有清晰的职责，并通过设计模式实现解耦。

---

## 2.2 五层架构详解

### 架构总览

```
┌──────────────────────────────────────────────────────────┐
│                   DataPipeline (Facade)                   │
│                      统一协调层                            │
└────────────┬─────────────────────────────────────────────┘
             ↓
┌────────────┴─────────────────────────────────────────────┐
│                   Collector Layer                         │
│  ┌─────────────────────────────────────────────┐         │
│  │ BaseCollector (抽象基类 - Template Method)   │         │
│  └──────────────────┬──────────────────────────┘         │
│                     │                                     │
│  ┌──────────────────┴──────────────────┐                 │
│  │ TushareCollector  │ VNPyCollector  │ ...             │
│  │  (具体实现)        │  (具体实现)     │                 │
│  └───────────────────┴─────────────────┘                 │
│                                                           │
│  教学要点: 模板方法模式、依赖注入                          │
└───────────────────────────────────────────────────────────┘
             ↓
┌────────────┴─────────────────────────────────────────────┐
│                   Cleaner Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │DataValidator │  │DataNormalizer│  │QualityController│ │
│  │ (4维度验证)   │  │ (5种策略)     │  │  (质量评分)     │ │
│  └──────────────┘  └──────────────┘  └────────────────┘ │
│                                                           │
│  教学要点: 策略模式、职责链模式                            │
└───────────────────────────────────────────────────────────┘
             ↓
┌────────────┴─────────────────────────────────────────────┐
│                   Storage Layer                           │
│  ┌──────────────────────┐  ┌────────────────────┐        │
│  │TimeSeriesRepository  │  │MetadataRepository  │        │
│  │ (时序数据)            │  │  (元数据)           │        │
│  └──────────┬───────────┘  └──────────┬─────────┘        │
│             └───────────┬──────────────┘                  │
│                         │                                 │
│                  ┌──────┴──────┐                          │
│                  │CacheStrategy │                         │
│                  │ (L1→L2→L3)   │                         │
│                  └──────────────┘                         │
│                                                           │
│  教学要点: Repository 模式、缓存策略                        │
└───────────────────────────────────────────────────────────┘
             ↓
┌────────────┴─────────────────────────────────────────────┐
│                   Service Layer                           │
│  ┌─────────────────┐     ┌──────────────────┐            │
│  │CalendarService  │     │ContractService   │            │
│  │ (交易日历)       │     │  (合约元数据)     │            │
│  └─────────────────┘     └──────────────────┘            │
│                                                           │
│  教学要点: Service 模式、领域逻辑封装                       │
└───────────────────────────────────────────────────────────┘
             ↓
┌────────────┴─────────────────────────────────────────────┐
│                   Query Layer                             │
│  ┌─────────────┐         ┌──────────────────┐            │
│  │QueryBuilder │         │BatchQueryExecutor│            │
│  │ (流畅接口)   │         │  (批量查询)       │            │
│  └─────────────┘         └──────────────────┘            │
│                                                           │
│  教学要点: Builder 模式、并发控制                           │
└───────────────────────────────────────────────────────────┘
```

---

## 2.3 Layer 1: Collector (数据采集层)

### 设计目标
- 统一不同数据源的接口
- 支持扩展新的数据源
- 实现限流和错误处理

### 核心类: BaseCollector

**位置**: `src/cherryquant/data/collectors/base_collector.py`

```python
from abc import ABC, abstractmethod
from typing import List
from datetime import datetime

class BaseCollector(ABC):
    """
    数据采集器抽象基类

    教学要点:
    1. 抽象基类 (ABC) 定义统一接口
    2. 模板方法模式: 定义算法骨架
    3. 子类实现具体步骤
    """

    @abstractmethod
    async def connect(self) -> None:
        """连接数据源"""
        pass

    @abstractmethod
    async def fetch_market_data(
        self,
        symbol: str,
        exchange: Exchange,
        start_date: datetime,
        end_date: datetime,
        timeframe: TimeFrame = TimeFrame.DAY_1,
    ) -> List[MarketData]:
        """采集市场数据"""
        pass
```

### 具体实现: TushareCollector

**位置**: `src/cherryquant/data/collectors/tushare_collector.py` (600+ 行)

**关键特性:**
1. **限流机制** (Token Bucket 算法)
2. **异步封装** (将同步 API 转为异步)
3. **格式转换** (Tushare 格式 → 标准格式)

```python
class TushareCollector(BaseCollector):
    """Tushare Pro 数据采集器"""

    def __init__(self, token: str, call_limit_per_minute: int = 200):
        self.token = token
        self.call_limit_per_minute = call_limit_per_minute

        # 限流相关
        self._call_count = 0
        self._call_reset_time = datetime.now()
        self._rate_limit_lock = asyncio.Lock()

    async def _rate_limit_check(self) -> None:
        """
        限流检查 (Token Bucket 算法)

        教学要点:
        1. 令牌桶算法实现
        2. asyncio.Lock 保证线程安全
        3. 时间窗口重置
        """
        async with self._rate_limit_lock:
            now = datetime.now()

            # 重置时间窗口
            if (now - self._call_reset_time).total_seconds() >= 60:
                self._call_count = 0
                self._call_reset_time = now

            # 检查是否超限
            if self._call_count >= self.call_limit_per_minute:
                wait_seconds = 60 - (now - self._call_reset_time).total_seconds()
                logger.warning(f"触发限流，等待 {wait_seconds:.1f} 秒")
                await asyncio.sleep(wait_seconds)
                self._call_count = 0
                self._call_reset_time = datetime.now()

            self._call_count += 1
```

### 🎓 教学要点

1. **模板方法模式**: `BaseCollector` 定义接口，子类实现具体逻辑
2. **依赖倒置原则**: 上层依赖抽象，不依赖具体实现
3. **限流算法**: Token Bucket 实现 API 调用频率控制
4. **异步编程**: `asyncio.to_thread()` 封装同步库

---

## 2.4 Layer 2: Cleaner (数据清洗层)

### 设计目标
- 验证数据的完整性和准确性
- 归一化数据格式
- 评估数据质量

### 组件 1: DataValidator (数据验证器)

**位置**: `src/cherryquant/data/cleaners/validator.py` (400+ 行)

**验证维度:**

| 维度 | 检查内容 | 示例 |
|------|----------|------|
| **完整性** | 字段是否缺失 | `close` 字段为 None |
| **合理性** | 数值是否合理 | 价格 < 0 或 volume < 0 |
| **一致性** | OHLC 关系 | `high` < `low` |
| **时序性** | 时间顺序 | 当前 K 线时间早于前一根 |
| **统计性** | 离群值检测 | 使用 IQR 检测价格异常 |

```python
class DataValidator:
    """数据验证器"""

    def _check_statistical_outliers(
        self,
        data: MarketData,
        context: List[MarketData],
    ) -> List[ValidationIssue]:
        """
        统计离群值检测 (IQR 方法)

        教学要点:
        1. IQR (四分位距) 算法
        2. 离群值定义: Q1 - 1.5*IQR 或 Q3 + 1.5*IQR
        3. 统计学在数据清洗中的应用
        """
        issues = []

        # 提取价格序列
        prices = [float(d.close) for d in context]
        prices.sort()

        # 计算四分位数
        n = len(prices)
        q1 = prices[n // 4]
        q3 = prices[3 * n // 4]
        iqr = q3 - q1

        # 计算边界
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        # 检查当前数据
        current_price = float(data.close)
        if current_price < lower_bound or current_price > upper_bound:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                field="close",
                message=f"价格 {current_price} 疑似离群值 (范围: {lower_bound:.2f}~{upper_bound:.2f})",
            ))

        return issues
```

### 组件 2: DataNormalizer (数据归一化器)

**位置**: `src/cherryquant/data/cleaners/normalizer.py` (500+ 行)

**归一化策略:**

1. **符号标准化**: `rb2501`, `RB2501`, `rb2501.SHFE` → `rb2501`
2. **交易所映射**: `SHF`, `SHFE`, `shfe` → `Exchange.SHFE`
3. **缺失值填充**: 前向填充、后向填充、插值
4. **去重**: 基于 `(symbol, exchange, datetime, timeframe)` 唯一键

```python
class DataNormalizer:
    """数据归一化器"""

    def fill_missing_data(
        self,
        data_list: List[MarketData],
        expected_timeframe: TimeFrame,
        fill_strategy: str = "ffill",
    ) -> List[MarketData]:
        """
        填充缺失的时间点

        教学要点:
        1. 时间序列的连续性要求
        2. 不同填充策略的适用场景
        3. 策略模式的应用
        """
        if not data_list:
            return []

        # 按时间排序
        data_list = sorted(data_list, key=lambda d: d.datetime)

        # 生成期望的时间点
        start = data_list[0].datetime
        end = data_list[-1].datetime
        expected_timestamps = self._generate_timestamps(
            start, end, expected_timeframe
        )

        # 检测缺失
        actual_timestamps = {d.datetime for d in data_list}
        missing_timestamps = expected_timestamps - actual_timestamps

        if not missing_timestamps:
            return data_list

        # 填充缺失数据
        logger.info(f"检测到 {len(missing_timestamps)} 个缺失时间点，使用 {fill_strategy} 策略填充")

        if fill_strategy == "ffill":
            return self._forward_fill(data_list, missing_timestamps)
        elif fill_strategy == "bfill":
            return self._backward_fill(data_list, missing_timestamps)
        elif fill_strategy == "interpolate":
            return self._interpolate_fill(data_list, missing_timestamps)
        else:
            raise ValueError(f"不支持的填充策略: {fill_strategy}")
```

### 组件 3: QualityController (质量控制器)

**位置**: `src/cherryquant/data/cleaners/quality_control.py` (300+ 行)

**质量评分体系:**

```python
@dataclass
class QualityMetrics:
    """质量指标"""
    completeness_rate: float  # 完整性: 0-1
    accuracy_rate: float      # 准确性: 0-1
    consistency_rate: float   # 一致性: 0-1
    timeliness_score: float   # 及时性: 0-1

    @property
    def overall_score(self) -> float:
        """
        综合评分

        教学要点:
        1. 加权平均
        2. 质量指标量化
        """
        return (
            self.completeness_rate * 0.3 +
            self.accuracy_rate * 0.3 +
            self.consistency_rate * 0.2 +
            self.timeliness_score * 0.2
        )

    @property
    def grade(self) -> str:
        """质量等级 (A/B/C/D/F)"""
        score = self.overall_score
        if score >= 0.9: return "A"
        elif score >= 0.8: return "B"
        elif score >= 0.7: return "C"
        elif score >= 0.6: return "D"
        else: return "F"
```

### 🎓 教学要点

1. **策略模式**: 多种填充策略可切换
2. **IQR 算法**: 统计学方法检测离群值
3. **数据质量**: 从 4 个维度量化评估
4. **职责链模式**: 验证 → 归一化 → 质量控制

---

## 2.5 Layer 3: Storage (数据存储层)

### 设计目标
- 高效存储海量时序数据
- 支持灵活的查询
- 实现多级缓存

### 组件 1: TimeSeriesRepository (时序数据仓储)

**位置**: `src/cherryquant/data/storage/timeseries_repository.py` (500+ 行)

**关键设计:**

1. **不同周期的数据存储在不同集合**
```python
COLLECTION_NAMES = {
    TimeFrame.MIN_1: "market_data_1m",
    TimeFrame.MIN_5: "market_data_5m",
    TimeFrame.DAY_1: "market_data_1d",
}
```

2. **批量操作优化**
```python
async def save_batch(
    self,
    data_list: List[MarketData],
    ordered: bool = False,
) -> int:
    """
    批量保存数据

    教学要点:
    1. 批量操作 vs 单条操作的性能差异
    2. ordered=False 允许部分失败
    3. 按 timeframe 分组插入
    """
    # 按周期分组
    grouped = {}
    for data in data_list:
        if data.timeframe not in grouped:
            grouped[data.timeframe] = []
        grouped[data.timeframe].append(data)

    # 批量插入每个集合
    total_saved = 0
    for timeframe, items in grouped.items():
        collection = self._get_collection(timeframe)

        # 转换为文档
        documents = [self._to_document(d) for d in items]

        # 批量插入 (允许重复键错误)
        try:
            result = await collection.insert_many(
                documents,
                ordered=ordered,  # False: 部分失败也继续
            )
            total_saved += len(result.inserted_ids)
        except BulkWriteError as e:
            # 统计成功插入的数量
            total_saved += e.details.get('nInserted', 0)

    return total_saved
```

### 组件 2: CacheStrategy (缓存策略)

**位置**: `src/cherryquant/data/storage/cache_strategy.py` (450+ 行)

**三级缓存架构:**

```
查询流程: L1 (内存 LRU) → L2 (Redis) → L3 (MongoDB)
          ↑                ↑              ↑
          |                |              |
    命中率 85%         命中率 12%      命中率 3%
    延迟 <1ms          延迟 2-5ms      延迟 20-50ms
```

```python
class CacheStrategy:
    """三级缓存策略"""

    async def get(
        self,
        key: str,
        fetcher: Optional[Callable] = None,
    ) -> Optional[Any]:
        """
        级联查询

        教学要点:
        1. 缓存穿透处理
        2. 缓存回填 (Backfill)
        3. 性能优化策略
        """
        # L1: 内存缓存 (LRU)
        value = self._l1_get(key)
        if value is not None:
            self.stats["l1_hits"] += 1
            return value

        # L2: Redis 缓存
        value = await self._l2_get(key)
        if value is not None:
            self.stats["l2_hits"] += 1
            # 回填 L1
            self._l1_set(key, value)
            return value

        # L3: 数据库
        if fetcher:
            value = await fetcher()
            if value is not None:
                self.stats["l3_hits"] += 1
                # 回填 L1 和 L2
                await self.set(key, value)
            return value

        self.stats["misses"] += 1
        return None
```

### 🎓 教学要点

1. **Repository 模式**: 封装数据访问逻辑
2. **批量操作**: 性能优化的关键
3. **LRU Cache**: 内存缓存的经典算法
4. **缓存策略**: 多级缓存的设计和实现

---

## 2.6 Layer 4: Service (服务层)

### 设计目标
- 封装业务逻辑
- 提供高级 API
- 集成多个 Repository

### CalendarService (交易日历服务)

**位置**: `src/cherryquant/data/services/calendar_service.py` (250+ 行)

```python
class CalendarService:
    """交易日历服务"""

    async def is_trading_day(
        self,
        date: datetime,
        exchange: Exchange,
    ) -> bool:
        """
        判断是否为交易日

        教学要点:
        1. 业务逻辑封装
        2. 缓存应用
        3. 数据自动同步
        """
        # 尝试从缓存获取
        cache_key = f"trading_day:{exchange.value}:{date.date()}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached

        # 从仓储查询
        calendar = await self.repository.get_trading_day(date, exchange)

        if not calendar:
            # 数据缺失，尝试自动同步
            logger.warning(f"交易日历缺失: {date.date()}, 尝试自动同步")
            await self.sync_calendar(exchange, months_ahead=1, months_back=1)
            calendar = await self.repository.get_trading_day(date, exchange)

        result = calendar.is_open if calendar else False

        # 写入缓存
        await self.cache.set(cache_key, result, ttl=86400)  # 1天

        return result
```

### 🎓 教学要点

1. **Service 模式**: 业务逻辑的家园
2. **自动修复**: 数据缺失时自动同步
3. **缓存集成**: Service 层缓存业务结果

---

## 2.7 Layer 5: Query (查询层)

### 设计目标
- 提供流畅的查询 API
- 支持复杂过滤条件
- 批量查询优化

### QueryBuilder (查询构建器)

**位置**: `src/cherryquant/data/query/query_builder.py` (500+ 行)

**Builder 模式的经典应用:**

```python
# 使用示例
query = (QueryBuilder(repository)
    .symbol("rb2501")                          # 设置合约
    .exchange(Exchange.SHFE)                   # 设置交易所
    .date_range(
        datetime(2024, 1, 1),
        datetime(2024, 1, 31)
    )                                          # 设置日期范围
    .timeframe(TimeFrame.DAY_1)                # 设置周期
    .volume_greater_than(10000)                # 成交量过滤
    .price_range(
        min_price=Decimal("3500"),
        max_price=Decimal("4000")
    )                                          # 价格范围
    .order_by("datetime", descending=False)    # 排序
    .limit(20)                                 # 限制数量
)

# 延迟执行
results = await query.execute()
```

**核心实现:**

```python
class QueryBuilder:
    """查询构建器"""

    def symbol(self, symbol: str) -> "QueryBuilder":
        """
        设置合约代码

        教学要点:
        1. 流畅接口 (Fluent Interface)
        2. 返回 self 实现方法链
        3. Type Hint 确保类型安全
        """
        self._symbol = symbol
        return self  # ← 关键: 返回自身

    def custom_filter(self, filter_func: callable) -> "QueryBuilder":
        """
        自定义过滤器

        教学要点:
        1. 高阶函数: 接收函数作为参数
        2. 策略模式: 过滤逻辑可插拔
        3. 延迟执行: 过滤器在 execute() 时才运行
        """
        self._filters.append(filter_func)
        return self

    async def execute(self) -> List[MarketData]:
        """
        执行查询

        教学要点:
        1. 延迟执行 (Lazy Evaluation)
        2. 两阶段查询: 数据库 + 内存过滤
        3. 性能优化: 数据库层先过滤大部分数据
        """
        # 1. 数据库查询 (基础条件)
        data = await self.repository.query(
            symbol=self._symbol,
            exchange=self._exchange,
            start_date=self._start_date,
            end_date=self._end_date,
            timeframe=self._timeframe,
        )

        # 2. 内存过滤 (复杂条件)
        for filter_func in self._filters:
            data = [d for d in data if filter_func(d)]

        # 3. 排序
        if self._sort_by:
            data = self._sort_data(data)

        # 4. 分页
        if self._offset or self._limit:
            data = self._paginate_data(data)

        return data
```

### BatchQueryExecutor (批量查询执行器)

**位置**: `src/cherryquant/data/query/batch_query.py` (400+ 行)

**并发控制:**

```python
class BatchQueryExecutor:
    """批量查询执行器"""

    async def execute_batch(
        self,
        requests: List[BatchQueryRequest],
    ) -> List[BatchQueryResult]:
        """
        批量执行查询

        教学要点:
        1. Semaphore 控制并发数
        2. asyncio.gather 并发执行
        3. 错误隔离: 一个失败不影响其他
        """
        # 创建信号量
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def execute_one(request: BatchQueryRequest):
            async with semaphore:  # ← 控制并发数
                return await self._execute_single(request)

        # 并发执行所有查询
        results = await asyncio.gather(
            *[execute_one(req) for req in requests],
            return_exceptions=True,  # ← 错误隔离
        )

        return results
```

### 🎓 教学要点

1. **Builder 模式**: 流畅接口的实现
2. **延迟执行**: 构建查询 vs 执行查询分离
3. **Semaphore**: 并发数控制
4. **错误隔离**: 部分失败不影响整体

---

## 2.8 完整数据流演示

### 场景: AI 请求螺纹钢最近 30 天的日线数据

```python
# 1. 初始化数据管道
from cherryquant.data.pipeline import DataPipeline
from cherryquant.data.collectors.tushare_collector import TushareCollector
from cherryquant.adapters.data_storage.mongodb_manager import MongoDBConnectionManager
from datetime import datetime, timedelta

# 1.1 创建依赖
db_manager = MongoDBConnectionManager(
    uri="mongodb://localhost:27017",
    database="cherryquant"
)

collector = TushareCollector(token="your_token")

# 1.2 创建数据管道 (Facade 模式)
pipeline = DataPipeline(
    collector=collector,
    db_manager=db_manager,
    enable_cache=True,
    enable_validation=True,
    enable_quality_control=True,
)

await pipeline.initialize()

# 2. 请求数据
data = await pipeline.get_market_data(
    symbol="rb2501",
    exchange=Exchange.SHFE,
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    timeframe=TimeFrame.DAY_1,
)

# 3. AI Engine 使用数据
for bar in data:
    print(f"{bar.datetime}: 开={bar.open} 高={bar.high} 低={bar.low} 收={bar.close}")
```

### 内部流程详解

```
1. Pipeline.get_market_data()
   ├─ 检查缓存 (CacheStrategy)
   │  ├─ L1 (内存) 命中? → 返回
   │  ├─ L2 (Redis) 命中? → 回填 L1 → 返回
   │  └─ L3 (数据库) 命中? → 回填 L1/L2 → 返回
   │
   ├─ 缓存未命中，从数据源采集
   │  ├─ Collector.fetch_market_data()
   │  │  ├─ 限流检查 (Token Bucket)
   │  │  ├─ 调用 Tushare API
   │  │  └─ 格式转换 (Tushare → MarketData)
   │  │
   │  ├─ Validator.validate_batch()
   │  │  ├─ 完整性检查
   │  │  ├─ 合理性检查
   │  │  ├─ 一致性检查
   │  │  └─ 统计离群值检测
   │  │
   │  ├─ Normalizer.normalize_batch()
   │  │  ├─ 符号标准化
   │  │  ├─ 缺失值填充
   │  │  └─ 去重
   │  │
   │  ├─ QualityController.assess()
   │  │  └─ 计算质量评分 (A/B/C/D/F)
   │  │
   │  ├─ TimeSeriesRepository.save_batch()
   │  │  └─ 批量插入 MongoDB
   │  │
   │  └─ CacheStrategy.set()
   │     ├─ 写入 L1 (内存)
   │     └─ 写入 L2 (Redis)
   │
   └─ 返回数据给 AI Engine
```

---

## 2.9 设计模式总结

### 本章涉及的设计模式

| 模式 | 位置 | 作用 |
|------|------|------|
| **Facade** | `DataPipeline` | 简化复杂系统的接口 |
| **Template Method** | `BaseCollector` | 定义算法骨架，子类实现细节 |
| **Repository** | `TimeSeriesRepository` | 封装数据访问逻辑 |
| **Service** | `CalendarService` | 封装业务逻辑 |
| **Builder** | `QueryBuilder` | 流畅接口构建复杂对象 |
| **Strategy** | `DataNormalizer` | 可切换的算法族 |
| **Dependency Injection** | 全局 | 依赖从外部注入 |
| **Cache-Aside** | `CacheStrategy` | 旁路缓存模式 |

### 设计原则总结

1. **SOLID 原则**
   - **S**: 单一职责 - 每个类职责明确
   - **O**: 开闭原则 - 对扩展开放，对修改关闭
   - **L**: 里氏替换 - `TushareCollector` 可替换 `BaseCollector`
   - **I**: 接口隔离 - 接口职责单一
   - **D**: 依赖倒置 - 依赖抽象，不依赖具体

2. **DRY 原则** (Don't Repeat Yourself)
   - 公共逻辑抽取到基类
   - 工具函数复用

3. **KISS 原则** (Keep It Simple, Stupid)
   - 每层职责清晰
   - 避免过度设计

---

## 2.10 性能优化总结

### 关键性能指标

| 操作 | 无缓存 | 有缓存 | 加速比 |
|------|--------|--------|--------|
| 7天数据查询 | ~45ms | ~2ms | **22.5x** |
| 30天数据查询 | ~120ms | ~6ms | **20x** |
| 批量查询(10个) | ~180ms | ~15ms | **12x** |

### 优化技巧

1. **三级缓存**: 内存 → Redis → 数据库
2. **批量操作**: `save_batch()` vs 逐条 `save()`
3. **索引优化**: 复合索引 `(symbol, exchange, datetime)`
4. **连接池**: 复用数据库连接
5. **并发控制**: Semaphore 限制并发数

---

## 2.10 Quantbox 工具整合 ✨ (New in v0.2.0)

CherryQuant v0.2.0 整合了生产级 Quantbox 项目的核心工具和设计模式，为数据管道提供强大的工具支持。

### 2.10.1 基础工具层 (cherryquant.utils)

#### 日期工具 (date_utils.py)

处理交易日历，支持多个交易所的交易日判断和查询：

```python
from cherryquant.utils.date_utils import (
    get_trading_dates,
    is_trading_day,
    get_next_trading_day,
    get_previous_trading_day,
)

# 获取交易日列表
dates = get_trading_dates("20241101", "20241130", exchange="SHFE")
print(f"11月交易日数量: {len(dates)}")

# 判断是否交易日
if is_trading_day("20241122", exchange="SHFE"):
    print("今天是交易日，可以采集数据")

# 获取下一个交易日
next_day = get_next_trading_day("20241122", exchange="SHFE")
print(f"下一个交易日: {next_day}")
```

**教学要点**:
- ✅ LRU 缓存避免重复计算
- ✅ 支持多交易所（期货、股票）
- ✅ 自动处理节假日

#### 交易所工具 (exchange_utils.py)

统一不同数据源的交易所代码表示：

```python
from cherryquant.utils.exchange_utils import (
    normalize_exchange,
    denormalize_exchange,
    is_futures_exchange,
)

# 标准化交易所代码
exchange = normalize_exchange("SHF")   # "SHFE"
exchange = normalize_exchange("ZCE")   # "CZCE"

# 反标准化为特定数据源格式
ts_code = denormalize_exchange("SHFE", "tushare")  # "SHF"
gm_code = denormalize_exchange("CZCE", "goldminer")  # "CZCE"

# 判断交易所类型
if is_futures_exchange("SHFE"):
    print("这是期货交易所")
```

**教学要点**:
- ✅ 解决不同数据源命名不一致问题
- ✅ 支持双向转换
- ✅ 类型安全的交易所判断

#### 合约代码工具 (contract_utils.py)

智能解析和转换合约代码，支持多种数据源格式：

```python
from cherryquant.utils.contract_utils import (
    parse_contract,
    format_contract,
    ParsedContractInfo,
)

# 解析合约代码（自动识别格式）
info = parse_contract("SHFE.rb2501")
print(f"交易所: {info.exchange}")    # "SHFE"
print(f"标的: {info.underlying}")     # "rb"
print(f"年月: {info.year}-{info.month}")  # 2025-1

# 解析不同格式
info2 = parse_contract("RB2501.SHF")  # Tushare 格式
info3 = parse_contract("SR501", default_exchange="CZCE")  # 郑商所3位年月

# 格式转换
tushare_code = format_contract("SHFE.rb2501", "tushare")  # "RB2501.SHF"
vnpy_code = format_contract("SHFE.rb2501", "vnpy")        # "RB2501.SHFE"
gm_code = format_contract("RB2501.SHF", "goldminer")     # "SHFE.rb2501"

# 批量转换
contracts = ["SHFE.rb2501", "DCE.m2501", "CZCE.SR501"]
tushare_codes = format_contracts(contracts, "tushare")
```

**教学要点**:
- ✅ 自动识别：掘金、Tushare、VNPy 等多种格式
- ✅ 智能处理：郑商所 3 位/4 位年月格式
- ✅ 特殊合约：主力合约(888)、连续合约(000) 等
- ✅ 正则优化：预编译模式提高性能

**使用场景**：
```python
# 场景 1: 统一数据源格式
def collect_from_tushare(symbol):
    # Tushare 使用 "RB2501.SHF" 格式
    ts_code = format_contract(symbol, "tushare")
    df = pro.daily(ts_code=ts_code)
    return df

# 场景 2: 合约信息提取
def is_near_expiry(symbol):
    info = parse_contract(symbol)
    if info.year == 2024 and info.month == 12:
        return True
    return False
```

### 2.10.2 存储优化层 (cherryquant.data.storage)

#### SaveResult 追踪器 (save_result.py)

详细记录每次数据保存操作的结果和统计信息：

```python
from cherryquant.data.storage.save_result import SaveResult

# 创建结果追踪器
result = SaveResult()

# 记录操作
result.inserted_count = 100
result.modified_count = 50

# 记录错误
if invalid_data:
    result.add_error(
        "VALIDATION_ERROR",
        "日期格式无效",
        {"date": "invalid_date"}
    )

# 完成操作
result.complete()

# 查看结果
print(result)
# SaveResult(✓ total=150, inserted=100, modified=50, errors=1, duration=0.52s)

print(f"成功率: {result.success_rate:.1%}")  # 99.3%
print(f"耗时: {result.duration.total_seconds():.2f}秒")

# 导出为字典（用于日志）
logger.info("保存结果", extra=result.to_dict())
```

**教学要点**:
- ✅ 完整的操作统计（插入、修改、错误数）
- ✅ 性能度量（开始时间、结束时间、持续时间）
- ✅ 错误详情（类型、消息、数据）
- ✅ 可序列化（to_dict）

#### BulkWriter 批量写入工具 (bulk_writer.py)

**性能提升 100 倍的批量数据写入工具**，使用 MongoDB bulk_write 优化：

```python
from cherryquant.data.storage.bulk_writer import BulkWriter
from cherryquant.data.storage.save_result import SaveResult

# 批量 upsert 数据
data = [
    {"symbol": "rb2501", "date": 20241122, "close": 3500.0, "volume": 100000},
    {"symbol": "rb2501", "date": 20241123, "close": 3510.0, "volume": 120000},
    {"symbol": "hc2501", "date": 20241122, "close": 3200.0, "volume": 80000},
]

result = SaveResult()
await BulkWriter.bulk_upsert(
    collection=db.market_data,
    data=data,
    key_fields=["symbol", "date"],  # 唯一键，用于判断是否重复
    result=result
)

result.complete()
print(result)
# SaveResult(✓ total=3, inserted=2, modified=1, errors=0, duration=0.05s)
```

**性能对比**：
```python
# ❌ 旧方案（慢）- 1000条数据约 10 秒
for item in data:
    await collection.insert_one(item)

# ✅ 新方案（快）- 1000条数据约 0.1 秒
await BulkWriter.bulk_upsert(collection, data, ["symbol", "date"])
```

**索引管理**：
```python
# 批量创建索引
await BulkWriter.ensure_indexes(
    collection=db.market_data,
    index_specs=[
        {
            "keys": [("symbol", 1), ("date", 1)],
            "unique": True  # 唯一索引，防止重复数据
        },
        {
            "keys": [("date", -1)],  # 降序索引，适合时间倒序查询
            "unique": False
        }
    ]
)
```

**教学要点**:
- ✅ Upsert 模式：存在则更新，不存在则插入
- ✅ 批量操作：一次性执行所有操作，减少网络开销
- ✅ 自动索引：后台创建，不阻塞数据库
- ✅ 错误容忍：单条失败不影响整批操作

**集成到数据管道**：
```python
class TushareCollector(BaseCollector):
    async def save_market_data(
        self,
        data: list[MarketData]
    ) -> SaveResult:
        """保存市场数据（使用批量写入优化）"""
        # 转换为字典列表
        docs = [item.to_dict() for item in data]

        # 批量 upsert
        result = SaveResult()
        await BulkWriter.bulk_upsert(
            collection=self.db.market_data,
            data=docs,
            key_fields=["symbol", "date", "timeframe"],
            result=result
        )

        result.complete()

        # 记录日志
        if result.success:
            logger.info(f"✓ 保存成功: {result}")
        else:
            logger.error(f"✗ 保存失败: {result}")
            for error in result.errors:
                logger.error(f"  - {error['type']}: {error['message']}")

        return result
```

#### 数据源切换策略 (data_source_strategy.py)

实现智能的数据源选择：本地优先，远程备用，自动降级：

```python
from cherryquant.data.collectors.data_source_strategy import (
    DataSourceStrategy,
    LocalDataSource,
    RemoteDataSource,
)

# 创建本地和远程数据源
local_source = LocalDataSource()    # MongoDB
remote_source = RemoteDataSource()  # Tushare API

# 创建策略（本地优先）
strategy = DataSourceStrategy(
    local_source=local_source,
    remote_source=remote_source,
    prefer_local=True  # 优先使用本地
)

# 自动选择数据源获取数据
data = await strategy.get_data(symbol="rb2501", date="2024-11-22")
# 日志: ✓ Using local data source: LocalMongoDB

# 如果本地不可用，自动降级到远程
# 日志: ⚠ Local source unavailable, falling back to remote

# 强制使用远程数据源
data = await strategy.get_data(use_local=False, symbol="rb2501")
# 日志: ✓ Using remote data source: RemoteAPI
```

**教学要点**:
- ✅ 策略模式：封装数据源选择算法
- ✅ 自动降级：本地失败自动切换到远程
- ✅ 配置灵活：支持显式指定数据源
- ✅ 透明切换：调用方无需关心数据来自哪里

**实际应用**：
```python
class MarketDataService:
    def __init__(self, db, api):
        self.strategy = DataSourceStrategy(
            local_source=MongoDBAdapter(db),
            remote_source=TushareAdapter(api),
            prefer_local=True
        )

    async def get_daily_data(self, symbol, start_date, end_date):
        """获取日线数据（优先本地，自动降级）"""
        return await self.strategy.get_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
```

### 2.10.3 实战示例：整合新工具改进数据管道

下面展示如何使用这些新工具优化我们的数据采集流程：

```python
from cherryquant.data.collectors.tushare_collector import TushareCollector
from cherryquant.data.storage.bulk_writer import BulkWriter
from cherryquant.data.storage.save_result import SaveResult
from cherryquant.utils.date_utils import get_trading_dates
from cherryquant.utils.contract_utils import format_contract

class OptimizedDataPipeline:
    """优化后的数据管道（使用 Quantbox 工具）"""

    async def collect_recent_data(self, symbols: list[str], days: int = 30):
        """采集最近N天的数据"""
        # 1. 使用日期工具获取交易日
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        trading_dates = get_trading_dates(start_date, end_date, exchange="SHFE")
        logger.info(f"需要采集 {len(trading_dates)} 个交易日的数据")

        # 2. 批量转换合约格式
        tushare_symbols = [
            format_contract(sym, "tushare") for sym in symbols
        ]

        # 3. 采集数据
        all_data = []
        for ts_sym in tushare_symbols:
            df = await self.collector.fetch_daily(ts_sym, start_date, end_date)
            all_data.extend(df.to_dict('records'))

        # 4. 批量保存（使用 BulkWriter，速度快100倍）
        result = SaveResult()
        await BulkWriter.bulk_upsert(
            collection=self.db.market_data,
            data=all_data,
            key_fields=["symbol", "date"],
            result=result
        )

        result.complete()

        # 5. 记录详细结果
        logger.info(f"数据采集完成: {result}")
        logger.info(f"  - 插入: {result.inserted_count} 条")
        logger.info(f"  - 更新: {result.modified_count} 条")
        logger.info(f"  - 错误: {result.error_count} 条")
        logger.info(f"  - 耗时: {result.duration.total_seconds():.2f} 秒")
        logger.info(f"  - 成功率: {result.success_rate:.1%}")

        return result

# 使用示例
pipeline = OptimizedDataPipeline(db, api)
result = await pipeline.collect_recent_data(
    symbols=["SHFE.rb2501", "DCE.m2501", "CZCE.SR501"],
    days=30
)
```

### 2.10.4 迁移指南

如果你已经有使用旧 API 的代码，请参考 `docs/MIGRATION_GUIDE.md` 了解如何迁移。

**关键变更**:
1. `ContractInfo` → `ParsedContractInfo`（合约解析工具）
2. `Exchange` 枚举新增 GFEX、SHSE、SZSE、BSE

**建议优先级**:
- 🔥 高优先级：批量数据写入改用 `BulkWriter`（性能提升 100 倍）
- ⚡ 中优先级：合约代码转换改用 `contract_utils`（避免重复代码）
- 📌 低优先级：交易日判断改用 `date_utils`（减少数据库查询）

---

## 2.11 实战练习

### 练习 1: 实现自定义数据源

**任务**: 实现一个 `AKShareCollector`，从 AKShare 采集期货数据。

**提示**:
```python
from cherryquant.data.collectors.base_collector import BaseCollector
import akshare as ak

class AKShareCollector(BaseCollector):
    async def fetch_market_data(self, symbol, exchange, start_date, end_date, timeframe):
        # TODO: 实现采集逻辑
        pass
```

### 练习 2: 实现自定义过滤器

**任务**: 使用 `QueryBuilder` 实现以下查询:
- 合约: rb2501
- 日期: 最近 30 天
- 条件: 收盘价涨幅 > 2% 且成交量 > 50000

**提示**:
```python
def high_volume_gain_filter(data: MarketData) -> bool:
    # TODO: 实现过滤逻辑
    pass

query = (QueryBuilder(repo)
    .symbol("rb2501")
    .custom_filter(high_volume_gain_filter)
)
```

### 练习 3: 性能优化

**任务**: 对比以下两种方式的性能:
1. 逐条插入 vs 批量插入
2. 无缓存 vs 三级缓存

**提示**: 使用 `/tests/performance/benchmark_suite.py` 作为参考。

---

## 2.12 思考题

1. **缓存一致性**: 如果数据库中的数据被更新了，但缓存没有失效，会发生什么问题？如何解决？

2. **数据质量**: 如果 `QualityController` 评分为 `F`，我们应该拒绝这批数据吗？还是打个标记继续使用？

3. **性能 vs 可读性**: CherryQuant 的性能略低于 QuantBox (10-20%)，但代码更易读。你认为这个权衡合理吗？

4. **扩展性**: 如果要支持股票数据，需要修改哪些模块？修改量大吗？

5. **异常处理**: 如果 Tushare API 突然不可用了，数据管道应该如何优雅降级？

---

## 2.13 延伸阅读

- **设计模式**: 《Head First 设计模式》
- **缓存策略**: 《缓存更新的套路》(coolshell.cn)
- **时序数据库**: MongoDB Time Series Collections 官方文档
- **异步编程**: 《Python Asyncio 教程》
- **数据质量**: 《数据质量管理最佳实践》

---

## 2.14 下一章预告

第 3 章我们将学习 **AI 决策引擎**，包括:
- 强化学习基础
- 策略网络设计
- 训练和回测
- 模型部署

---

**本章完** 🎉

如有问题，请提交 Issue 或参加课程答疑。
